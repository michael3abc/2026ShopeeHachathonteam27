"""Transport-neutral instrumentation shared by runtime and workers."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from time import monotonic
from typing import NotRequired, TypedDict
from uuid import uuid4

from .activity import (
    ActivityEmission,
    ActivityFacts,
    ActivityFinding,
    ActivityInputs,
    ActivityPayload,
    Lifecycle,
    NodeSummary,
    safe_reference,
)
from .models import MemoryRetrievalObservation
from .review_gates import ReviewGateResult

LOGGER = logging.getLogger(__name__)
Sink = Callable[[ActivityEmission], None]


class SpanResult(TypedDict):
    facts: ActivityFacts
    memory_retrieval: NotRequired[MemoryRetrievalObservation | None]
    review_gate: NotRequired[ReviewGateResult | None]


@dataclass
class ActivityContext:
    case_ref: str
    run_id: str
    scope: str
    node: str
    attempt_id: str
    sink: Sink
    job_id: str | None = None
    parent: str | None = None
    observations: dict[str, ActivityFacts] = field(default_factory=dict)

    def emit(self, payload: ActivityPayload, operation_id: str) -> None:
        try:
            self.sink(
                ActivityEmission(
                    event_id=uuid4().hex,
                    case_ref=self.case_ref,
                    run_id=self.run_id,
                    scope=self.scope,
                    node=self.node,
                    job_id=self.job_id,
                    operation_id=operation_id,
                    parent_operation_id=self.parent,
                    attempt_id=self.attempt_id,
                    occurred_at=datetime.now(UTC),
                    payload=payload,
                )
            )
        except Exception:  # noqa: BLE001 - arbitrary observer failure cannot affect business
            LOGGER.error("activity delivery failed; trace may be incomplete")


CURRENT_ACTIVITY: ContextVar[ActivityContext | None] = ContextVar(
    "activity", default=None
)


def facts_from(value: object) -> ActivityFacts:
    """Project enum/status/count only; never recursively dump a model or raw text."""

    def attr(key):
        return value.get(key) if isinstance(value, dict) else getattr(value, key, None)

    fields = {}
    for key in ("action", "verdict", "revision_round"):
        item = attr(key)
        if item is not None:
            fields[key] = item
    decision = attr("proposed_decision")
    if decision is not None:
        fields["action"] = decision.action
    for key in (
        "status",
        "evidence_status",
        "completeness",
        "kind",
        "outcome_source",
        "result_type",
        "decision",
    ):
        item = attr(key)
        if item is not None:
            fields["outcome"] = item
            break
    if isinstance(value, (list, tuple)):
        fields["count"] = len(value)
    for key in ("clauses", "hits", "line_items"):
        item = attr(key)
        if isinstance(item, list):
            fields["count"] = len(item)
    for key in ("revision_reasons", "issues"):
        items = attr(key)
        if items:
            fields["reason_codes"] = [str(getattr(i, "code", "ISSUE")) for i in items][
                :30
            ]
    items = attr("reviewer_claim_findings") or attr("claim_findings")
    if items:
        fields["finding_statuses"] = [str(i.status) for i in items][:30]
        fields["findings"] = [
            ActivityFinding(
                claim_id=i.claim_id,
                status=i.status,
                evidence_refs=[
                    safe_reference(ref) for ref in i.supporting_evidence_refs[:30]
                ],
            )
            for i in items[:30]
        ]
    refs = list(attr("policy_refs") or []) + list(attr("evidence_refs") or [])
    fields["references"] = [safe_reference(ref) for ref in refs[:30]]
    if decision is not None:
        fields["reason_codes"] = [str(decision.reason_code)]
    if attr("reason") and not isinstance(attr("reason"), str):
        fields["reason_codes"] = [str(attr("reason"))]
    try:
        return ActivityFacts(**fields)
    except ValueError:
        LOGGER.error("activity projection rejected invalid facts")
        return ActivityFacts(outcome="SUMMARY_UNAVAILABLE")


@contextmanager
def span(
    kind: str,
    name: str,
    *,
    model: str | None = None,
    inputs: ActivityInputs | None = None,
) -> Iterator[SpanResult]:
    context = CURRENT_ACTIVITY.get()
    operation = uuid4().hex
    start = monotonic()
    result: SpanResult = {"facts": ActivityFacts()}
    if context:
        context.emit(
            Lifecycle(
                type=kind, phase="STARTED", name=name, model=model, inputs=inputs
            ),
            operation,
        )
    token = (
        CURRENT_ACTIVITY.set(replace(context, parent=operation)) if context else None
    )
    try:
        yield result
    except BaseException as error:
        if context:
            paused = type(error).__name__ == "GraphInterrupt"
            context.emit(
                Lifecycle(
                    type=kind,
                    phase="PAUSED" if paused else "FAILED",
                    name=name,
                    model=model,
                    duration_ms=int((monotonic() - start) * 1000),
                    error_code=None if paused else "OPERATION_FAILED",
                ),
                operation,
            )
        raise
    else:
        if context:
            context.emit(
                Lifecycle(
                    type=kind,
                    phase="COMPLETED",
                    name=name,
                    model=model,
                    duration_ms=int((monotonic() - start) * 1000),
                    facts=result["facts"],
                ),
                operation,
            )
            if kind == "node":
                try:
                    summary = NodeSummary(
                        facts=result["facts"],
                        memory_retrieval=result.get("memory_retrieval"),
                        review_gate=result.get("review_gate"),
                    )
                except (ValueError, TypeError, AttributeError):
                    LOGGER.error("activity summary invalid; details unavailable")
                    summary = NodeSummary(
                        facts=ActivityFacts(outcome="SUMMARY_UNAVAILABLE")
                    )
                context.emit(summary, operation)
    finally:
        if token is not None:
            CURRENT_ACTIVITY.reset(token)


class ObservedProvider:
    """Delegate public synchronous operations without exposing their arguments."""

    def __init__(self, delegate: object, name: str, kind: str = "tool"):
        self.delegate, self.name, self.kind = delegate, name, kind

    def __getattr__(self, name):
        member = getattr(self.delegate, name)
        if not callable(member) or name.startswith("_"):
            return member

        def observed(*args, **kwargs):
            label = f"{self.name}.{name}"
            if self.kind == "model" and kwargs.get("task") is not None:
                label = str(kwargs["task"].value)
            model = (
                getattr(self.delegate, "model_name", type(self.delegate).__name__)
                if self.kind == "model"
                else None
            )
            inputs = None
            if self.kind == "tool":
                try:
                    inputs = ActivityInputs(
                        argument_count=len(args) + len(kwargs),
                        reason_code=kwargs.get("reason_code"),
                        required_claim_ids=list(kwargs.get("required_claim_ids", []))[
                            :30
                        ],
                        top_k=kwargs.get("top_k"),
                    )
                except ValueError:
                    LOGGER.error("activity input projection unavailable")
            with span(
                self.kind,
                label,
                model=safe_reference(model) if model else None,
                inputs=inputs,
            ) as outcome:
                result = member(*args, **kwargs)
                try:
                    outcome["facts"] = facts_from(result)
                except (ValueError, TypeError, AttributeError):
                    LOGGER.error("activity projection failed; details unavailable")
                    outcome["facts"] = ActivityFacts(outcome="SUMMARY_UNAVAILABLE")
                context = CURRENT_ACTIVITY.get()
                if context:
                    context.observations[self.name] = outcome["facts"]
                return result

        return observed
