"""LangGraph construction and node implementations."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.enums import (
    ClaimId,
    EscalationReason,
    EvidenceStatus,
    IntakeCompleteness,
    RetrievalStatus,
    ReviewVerdict,
    UserRole,
    VerificationStatus,
)
from return_agent_contracts.models import (
    REVIEW_REVISION_LIMIT,
    CaseContextLoadResult,
    ClarificationRequest,
    EvidenceAssessment,
    EvidenceItem,
    EvidenceRequest,
    HumanReviewResult,
    IntakeResult,
    LearningTrace,
    MemoryQuerySummary,
    MemoryRetrievalObservation,
    MemorySearchHit,
    PolicyBundle,
    ResolverConflictOutput,
    ResolverDraftOutput,
    ResolverEvidenceRequestOutput,
    ResolverOutput,
    ReviewResult,
    UserTurn,
    VerificationResult,
)
from return_agent_contracts.registry import (
    CLAIM_REGISTRY_MAJOR,
    CLAIM_REGISTRY_V1,
    CLAIM_REGISTRY_VERSION,
)
from return_agent_contracts.review_gates import evaluate_review_gate
from return_agent_contracts.runtime import (
    AgentInterruptKind,
    ClarificationResume,
    EvidenceResume,
    HumanReviewPollResume,
)
from return_agent_contracts.validation import (
    ContractInvariantError,
    derive_memory_categories,
    expected_claim_pairs,
    validate_applicable_policy_bundle,
    validate_case_context_load_result,
    validate_evidence_assessment,
    validate_evidence_request,
    validate_human_review_entry,
    validate_memory_summary,
    validate_resolved_evidence_item,
    validate_review_result,
)

from .assembly import (
    build_human_review_dossier,
    build_manual_escalation,
    build_memory_distillation_input,
    build_proposed_handoff,
    build_resolution_handoff,
    build_revision_event,
)
from .dependencies import AgentDependencies
from .model import ModelTask, OutputSchema
from .prompts import (
    INTAKE_PROMPT_VERSION,
    INTAKE_SYSTEM_PROMPT,
    MEMORY_QUERY_PROMPT_VERSION,
    MEMORY_QUERY_SYSTEM_PROMPT,
    RESOLVER_PROMPT_VERSION,
    RESOLVER_SYSTEM_PROMPT,
    REVIEWER_PROMPT_VERSION,
    REVIEWER_SYSTEM_PROMPT,
)
from .serialization import json_value
from .state import (
    AgentState,
    MemoryRetrievalStatus,
)

INTAKE_SCHEMA = OutputSchema("IntakeResult", TypeAdapter(IntakeResult))
ASSESSMENT_SCHEMA = OutputSchema("EvidenceAssessment", TypeAdapter(EvidenceAssessment))
RESOLVER_SCHEMA = OutputSchema("ResolverOutput", TypeAdapter(ResolverOutput))
REVIEW_SCHEMA = OutputSchema("ReviewResult", TypeAdapter(ReviewResult))

CASE_CONTEXT_LOAD_ADAPTER = TypeAdapter(CaseContextLoadResult)
POLICY_BUNDLE_ADAPTER = TypeAdapter(PolicyBundle)
MEMORY_HITS_ADAPTER = TypeAdapter(list[MemorySearchHit])
MEMORY_QUERY_SCHEMA = OutputSchema(
    "MemoryQuerySummary", TypeAdapter(MemoryQuerySummary)
)
EVIDENCE_ITEM_ADAPTER = TypeAdapter(EvidenceItem)
VERIFICATION_RESULT_ADAPTER = TypeAdapter(VerificationResult)
HUMAN_REVIEW_RESULT_ADAPTER = TypeAdapter(HumanReviewResult)

CLARIFICATION_LIMIT = 2
EVIDENCE_LIMIT = 2
VERIFICATION_LIMIT = 2
REVISION_LIMIT = REVIEW_REVISION_LIMIT
PROPOSE_LIMIT = 1 + VERIFICATION_LIMIT + REVISION_LIMIT
GRAPH_RECURSION_LIMIT = 100
LOGGER = logging.getLogger(__name__)


def initial_state(
    *,
    thread_id: str,
    case_ref: str,
    order_ref: str | None,
    initial_turn: UserTurn,
) -> AgentState:
    return AgentState(
        thread_id=thread_id,
        case_ref=case_ref,
        trusted_order_ref=order_ref,
        conversation_turns=[initial_turn],
        normalized_intent=None,
        claimed_line_item_ids=[],
        operational_memory=[],
        memory_retrieval_status=MemoryRetrievalStatus.OK,
        memory_query_summary=None,
        memory_retrieval=None,
        evidence_bundle=[],
        evidence_assessment=None,
        current_handoff=None,
        proposal_history=[],
        pending_review_result=None,
        verification_feedback=[],
        review_history=[],
        review_routing_reason=None,
        revision_events=[],
        pending_clarification_request=None,
        pending_evidence_request=None,
        human_review_ref=None,
        human_review_result=None,
        resolution_handoff=None,
        memory_distillation_input=None,
        learning_trace=LearningTrace(case_ref=case_ref, thread_id=thread_id),
        verification_result=None,
        manual_escalation=None,
        escalation_reason=None,
        clarification_round=0,
        evidence_round=0,
        verification_round=0,
        revision_round=0,
        propose_round=0,
        _route="parse_request",
    )


def _fail(reason: EscalationReason) -> dict[str, object]:
    return {
        "escalation_reason": reason,
        "_route": "terminate_automation",
    }


def _validate_provider_result(adapter: TypeAdapter[Any], value: Any) -> Any:
    """Force validation even when a provider returns a mutated model instance."""

    return adapter.validate_python(json_value(value))


def _graph_evidence_request(
    *,
    request: EvidenceRequest,
    state: AgentState,
    evidence_round: int,
    dependencies: AgentDependencies,
) -> EvidenceRequest:
    """Replace the LLM placeholder with the graph-owned request identifier."""

    return request.model_copy(
        update={
            "request_id": dependencies.id_factory.make(
                "evidence-request",
                state["thread_id"],
                evidence_round,
            )
        }
    )


def _line_item_prompt_view(state: AgentState) -> list[dict[str, object]] | None:
    snapshot = state.get("order_snapshot")
    if snapshot is None:
        return None
    return [
        {
            "line_item_id": item.line_item_id,
            "sku_ref": item.sku_ref,
            "category_ref": item.category_ref,
            "title": item.title,
            "quantity": item.quantity,
        }
        for item in snapshot.line_items
    ]


def _order_facts_without_money(state: AgentState) -> dict[str, object]:
    snapshot = state["order_snapshot"]
    return {
        "order_snapshot_ref": snapshot.order_snapshot_ref,
        "order_ref": snapshot.order_ref,
        "snapshot_version": snapshot.snapshot_version,
        "captured_at": json_value(snapshot.captured_at),
        "delivered_at": json_value(snapshot.delivered_at),
        "line_items": _line_item_prompt_view(state),
    }


def _relevant_registry(state: AgentState) -> list[dict[str, object]]:
    bundle = state["policy_bundle"]
    claim_ids = {
        claim_id for clause in bundle.clauses for claim_id in clause.required_claim_ids
    }
    return [
        cast(dict[str, object], json_value(CLAIM_REGISTRY_V1[claim_id]))
        for claim_id in sorted(claim_ids, key=lambda item: item.value)
    ]


def _expected_claim_pair_prompt_view(state: AgentState) -> list[dict[str, str]]:
    pairs = expected_claim_pairs(state["policy_bundle"], state["claimed_line_item_ids"])
    return [
        {"claim_id": claim_id, "subject": subject}
        for claim_id, subject in sorted(pairs)
    ]


def _validate_intake_result(state: AgentState, result: IntakeResult) -> None:
    snapshot = state.get("order_snapshot")
    if snapshot is None:
        if result.claimed_line_item_ids:
            raise ContractInvariantError(
                "first-pass intake cannot bind line items before loading the order"
            )
    else:
        known = {item.line_item_id for item in snapshot.line_items}
        if result.order_ref != state["case_context"].order_ref:
            raise ContractInvariantError(
                "post-context intake order_ref differs from loaded order"
            )
        if not set(result.claimed_line_item_ids).issubset(known):
            raise ContractInvariantError("intake returned unknown claimed line items")
        if (
            result.completeness is IntakeCompleteness.COMPLETE
            and not result.claimed_line_item_ids
        ):
            raise ContractInvariantError(
                "complete post-context intake requires claimed line items"
            )
    if result.completeness is IntakeCompleteness.COMPLETE and (
        result.order_ref is None
        or result.reason_code is None
        or result.reason_summary is None
    ):
        raise ContractInvariantError(
            "complete intake requires order_ref, reason_code, and reason_summary"
        )


def _bind_trusted_order_ref(state: AgentState, result: IntakeResult) -> IntakeResult:
    """Bind API-owned order identity before deciding whether to clarify."""

    trusted_order_ref = state.get("trusted_order_ref")
    if trusted_order_ref is None:
        return result
    if result.order_ref not in {None, trusted_order_ref}:
        raise ContractInvariantError(
            "intake order_ref conflicts with the trusted case order"
        )
    missing_fields = [
        field_name for field_name in result.missing_fields if field_name != "order_ref"
    ]
    update: dict[str, object] = {
        "order_ref": trusted_order_ref,
        "missing_fields": missing_fields,
    }
    if result.completeness is IntakeCompleteness.INCOMPLETE and not missing_fields:
        update.update(
            {
                "completeness": IntakeCompleteness.COMPLETE,
                "clarification_question": None,
            }
        )
    return result.model_copy(update=update)


def _parse_request_node(
    dependencies: AgentDependencies,
):
    def node(state: AgentState) -> dict[str, object]:
        payload = {
            "prompt_version": INTAKE_PROMPT_VERSION,
            "trusted_order_ref": state.get("trusted_order_ref"),
            "conversation_turns": json_value(state["conversation_turns"]),
            "existing_intent": json_value(state.get("normalized_intent")),
            "order_line_items": _line_item_prompt_view(state),
        }
        try:
            result = dependencies.model.generate(
                task=ModelTask.INTAKE,
                system_prompt=INTAKE_SYSTEM_PROMPT,
                payload=payload,
                output_schema=INTAKE_SCHEMA,
            )
            result = _bind_trusted_order_ref(state, result)
            _validate_intake_result(state, result)
        except Exception:  # noqa: BLE001 - model boundary fails closed
            return _fail(EscalationReason.CONTRACT_VIOLATION)

        update: dict[str, object] = {
            "normalized_intent": result,
            "claimed_line_item_ids": list(result.claimed_line_item_ids),
        }
        if result.completeness is IntakeCompleteness.INCOMPLETE:
            if state["clarification_round"] >= CLARIFICATION_LIMIT:
                return update | _fail(EscalationReason.CLARIFICATION_BUDGET_EXCEEDED)
            next_round = state["clarification_round"] + 1
            update.update(
                {
                    "clarification_round": next_round,
                    "pending_clarification_request": ClarificationRequest(
                        request_id=dependencies.id_factory.make(
                            "clarification",
                            state["thread_id"],
                            next_round,
                        ),
                        missing_fields=result.missing_fields,
                        clarification_question=result.clarification_question,
                        clarification_round=next_round,
                    ),
                    "_route": "request_clarification",
                }
            )
            return update

        update["pending_clarification_request"] = None
        update["_route"] = (
            "retrieve_policy"
            if state.get("case_context") is not None
            else "load_case_context"
        )
        return update

    return node


def _request_clarification_node(state: AgentState) -> dict[str, object]:
    request = state["pending_clarification_request"]
    if request is None:
        return _fail(EscalationReason.CONTRACT_VIOLATION)
    value = interrupt(
        {
            "kind": AgentInterruptKind.CLARIFICATION.value,
            "case_ref": state["case_ref"],
            "request": request.model_dump(mode="json"),
        }
    )
    try:
        resume = ClarificationResume.model_validate(value)
        if resume.turn.role is not UserRole.USER:
            raise ContractInvariantError(
                "clarification resume must contain a USER turn"
            )
        if any(
            turn.turn_id == resume.turn.turn_id for turn in state["conversation_turns"]
        ):
            raise ContractInvariantError("UserTurn.turn_id must be unique")
    except (ValidationError, ContractInvariantError):
        return _fail(EscalationReason.CONTRACT_VIOLATION)
    return {
        "conversation_turns": [*state["conversation_turns"], resume.turn],
        "_route": "parse_request",
    }


def _load_case_context_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        intent = state.get("normalized_intent")
        try:
            result = _validate_provider_result(
                CASE_CONTEXT_LOAD_ADAPTER,
                dependencies.case_context_provider.load_case_context(state["case_ref"]),
            )
            if result is None:
                raise ContractInvariantError("case context provider returned None")
            validate_case_context_load_result(state["case_ref"], result)
            if (
                state.get("trusted_order_ref") is not None
                and result.case_context.order_ref != state["trusted_order_ref"]
            ):
                raise ContractInvariantError(
                    "loaded case context differs from the trusted order"
                )
            if intent is None or intent.order_ref != result.case_context.order_ref:
                raise ContractInvariantError(
                    "intake order_ref does not match loaded case context"
                )
        except Exception:  # noqa: BLE001 - provider boundary fails closed
            return _fail(EscalationReason.CONTRACT_VIOLATION)

        update: dict[str, object] = {
            "case_context": result.case_context,
            "order_snapshot": result.order_snapshot,
        }
        if len(result.order_snapshot.line_items) == 1:
            only_item = result.order_snapshot.line_items[0].line_item_id
            update["claimed_line_item_ids"] = [only_item]
            update["normalized_intent"] = intent.model_copy(
                update={"claimed_line_item_ids": [only_item]}
            )
            update["_route"] = "retrieve_policy"
        else:
            update["_route"] = "parse_request"
        return update

    return node


def _retrieve_policy_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        intent = state["normalized_intent"]
        if intent is None or intent.reason_code is None:
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        try:
            bundle = _validate_provider_result(
                POLICY_BUNDLE_ADAPTER,
                dependencies.policy_provider.retrieve_policy(
                    state["case_context"],
                    state["order_snapshot"],
                    intent.reason_code,
                    state["claimed_line_item_ids"],
                ),
            )
            if bundle.retrieval_status is RetrievalStatus.AMBIGUOUS:
                return {"policy_bundle": bundle} | _fail(
                    EscalationReason.POLICY_AMBIGUOUS
                )
            if bundle.retrieval_status is RetrievalStatus.NOT_FOUND:
                return {"policy_bundle": bundle} | _fail(
                    EscalationReason.POLICY_NOT_FOUND
                )
            validate_applicable_policy_bundle(state["case_context"], bundle)
        except Exception:  # noqa: BLE001 - provider boundary fails closed
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        return {"policy_bundle": bundle, "_route": "prepare_memory_query"}

    return node


def _memory_matches(
    memory: Any,
    *,
    market: str,
    reason_code: Any,
    required_claim_ids: set[ClaimId],
    categories: set[str],
    policy_versions: set[str],
) -> bool:
    scope = memory.scope
    return (
        memory.policy_version in policy_versions
        and memory.claim_registry_version.split(":", 1)[-1].split(".", 1)[0]
        == CLAIM_REGISTRY_VERSION.split(":", 1)[-1].split(".", 1)[0]
        and scope.market == market
        and (not scope.reason_codes or reason_code in scope.reason_codes)
        and (not scope.claim_ids or bool(set(scope.claim_ids) & required_claim_ids))
        and (not scope.categories or bool(set(scope.categories) & categories))
    )


def _memory_unavailable(code: str, summary: str | None = None) -> dict[str, object]:
    return {
        "operational_memory": [],
        "memory_query_summary": summary,
        "memory_retrieval_status": MemoryRetrievalStatus.UNAVAILABLE,
        "memory_retrieval": MemoryRetrievalObservation(
            status="UNAVAILABLE",
            query_summary=summary,
            error_code=code,
        ),
        "_route": "assess_case",
    }


def _prepare_memory_query_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        try:
            evidence = _resolve_initial_evidence(state, dependencies)
        except Exception:  # noqa: BLE001 - attachment provider fails closed
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        try:
            intent = state["normalized_intent"]
            claimed = set(state["claimed_line_item_ids"])
            snapshot = state["order_snapshot"]
            payload = {
                "prompt_version": MEMORY_QUERY_PROMPT_VERSION,
                "reason": intent.reason_summary,
                "reason_code": intent.reason_code.value,
                "market": state["case_context"].market,
                "case_opened_at": json_value(state["case_context"].case_opened_at),
                "delivered_at": json_value(snapshot.delivered_at),
                "claimed_items": [
                    {"title": item.title, "category": item.category_ref}
                    for item in snapshot.line_items
                    if item.line_item_id in claimed
                ],
                "evidence": [
                    {
                        "subject": item.subject,
                        "type": item.type.value,
                        "source": item.source.value,
                        "summary": item.extracted_summary,
                    }
                    for item in evidence
                ],
            }
            result = dependencies.model.generate(
                task=ModelTask.MEMORY_QUERY_SUMMARY,
                system_prompt=MEMORY_QUERY_SYSTEM_PROMPT,
                payload=payload,
                output_schema=MEMORY_QUERY_SCHEMA,
            )
            result = _validate_provider_result(TypeAdapter(MemoryQuerySummary), result)
            validate_memory_summary(result.query_summary)
        except Exception:  # noqa: BLE001 - optional model boundary
            return {"evidence_bundle": evidence} | _memory_unavailable(
                "SUMMARY_UNAVAILABLE"
            )
        return {
            "evidence_bundle": evidence,
            "operational_memory": [],
            "memory_query_summary": result.query_summary,
            "memory_retrieval": None,
            "_route": "retrieve_memory",
        }

    return node


def _retrieve_memory_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        intent = state["normalized_intent"]
        if intent is None or intent.reason_code is None:
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        bundle = state["policy_bundle"]
        required_claim_ids = {
            claim_id
            for clause in bundle.clauses
            for claim_id in clause.required_claim_ids
        }
        categories = derive_memory_categories(
            state["order_snapshot"], state["claimed_line_item_ids"]
        )
        policy_versions = sorted({clause.policy_version for clause in bundle.clauses})
        try:
            returned = _validate_provider_result(
                MEMORY_HITS_ADAPTER,
                list(
                    dependencies.operational_memory_store.query_approved(
                        query_summary=state["memory_query_summary"],
                        market=state["case_context"].market,
                        reason_code=intent.reason_code,
                        required_claim_ids=sorted(
                            required_claim_ids, key=lambda claim_id: claim_id.value
                        ),
                        categories=categories,
                        policy_versions=policy_versions,
                        claim_registry_major=CLAIM_REGISTRY_MAJOR,
                        top_k=3,
                    )
                ),
            )
            if len({hit.memory.memory_id for hit in returned}) != len(returned):
                raise ContractInvariantError("memory provider returned duplicate IDs")
            matched = [
                hit
                for hit in returned
                if _memory_matches(
                    hit.memory,
                    market=state["case_context"].market,
                    reason_code=intent.reason_code,
                    required_claim_ids=required_claim_ids,
                    categories=set(categories),
                    policy_versions=set(policy_versions),
                )
            ][:3]
            observation = MemoryRetrievalObservation(
                status="OK",
                query_summary=state["memory_query_summary"],
                hits=matched,
            )
            return {
                "operational_memory": [hit.memory for hit in matched],
                "memory_retrieval": observation,
                "memory_retrieval_status": MemoryRetrievalStatus.OK,
                "_route": "assess_case",
            }
        except Exception:  # noqa: BLE001 - optional memory, never fallback-ranked
            return _memory_unavailable(
                "RETRIEVAL_UNAVAILABLE", state.get("memory_query_summary")
            )

    return node


def _merge_evidence(
    current: Iterable[EvidenceItem], new_items: Iterable[EvidenceItem]
) -> list[EvidenceItem]:
    merged = list(current)
    by_id = {item.evidence_id: item for item in merged}
    by_artifact = {item.artifact_ref: item for item in merged}
    for item in new_items:
        existing_id = by_id.get(item.evidence_id)
        existing_artifact = by_artifact.get(item.artifact_ref)
        if existing_id is not None and existing_id != item:
            raise ContractInvariantError("evidence_id maps to conflicting evidence")
        if existing_artifact is not None and existing_artifact != item:
            raise ContractInvariantError("artifact_ref maps to conflicting evidence")
        if existing_id is None and existing_artifact is None:
            merged.append(item)
            by_id[item.evidence_id] = item
            by_artifact[item.artifact_ref] = item
    return merged


def _resolve_initial_evidence(
    state: AgentState, dependencies: AgentDependencies
) -> list[EvidenceItem]:
    existing = list(state.get("evidence_bundle", []))
    resolved_artifacts = {item.artifact_ref for item in existing}
    artifact_refs = list(
        dict.fromkeys(
            artifact_ref
            for turn in state["conversation_turns"]
            for artifact_ref in turn.attached_artifact_refs
            if artifact_ref not in resolved_artifacts
        )
    )
    allowed_subjects = {"ORDER", *state["claimed_line_item_ids"]}
    new_items = []
    for artifact_ref in artifact_refs:
        item = _validate_provider_result(
            EVIDENCE_ITEM_ADAPTER,
            dependencies.evidence_provider.resolve(artifact_ref),
        )
        if item.artifact_ref != artifact_ref:
            raise ContractInvariantError(
                "resolved evidence artifact_ref differs from requested reference"
            )
        if item.subject not in allowed_subjects:
            raise ContractInvariantError(
                "initial evidence subject is outside the claimed case scope"
            )
        new_items.append(item)
    return _merge_evidence(existing, new_items)


def _resolver_payload(state: AgentState) -> dict[str, object]:
    intent = state["normalized_intent"]
    return {
        "prompt_version": RESOLVER_PROMPT_VERSION,
        "normalized_intent": json_value(intent),
        "claimed_line_item_ids": list(state["claimed_line_item_ids"]),
        "case_context": json_value(state["case_context"]),
        "order_facts": _order_facts_without_money(state),
        "policy_bundle": json_value(state["policy_bundle"]),
        "claim_registry_version": CLAIM_REGISTRY_VERSION,
        "claim_registry": _relevant_registry(state),
        "expected_claim_subject_pairs": _expected_claim_pair_prompt_view(state),
        "evidence_bundle": json_value(state.get("evidence_bundle", [])),
        "evidence_assessment": json_value(state.get("evidence_assessment")),
        "operational_memory": json_value(state.get("operational_memory", [])),
        "verification_feedback": json_value(state.get("verification_feedback", [])),
        "review_feedback": json_value(state.get("pending_review_result")),
    }


def _assess_case_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        try:
            evidence = state["evidence_bundle"]
            working = dict(state)
            working["evidence_bundle"] = evidence
            assessment = dependencies.model.generate(
                task=ModelTask.ASSESS,
                system_prompt=RESOLVER_SYSTEM_PROMPT,
                payload=_resolver_payload(cast(AgentState, working)),
                output_schema=ASSESSMENT_SCHEMA,
            )
            assessment = assessment.model_copy(
                update={"claim_registry_version": CLAIM_REGISTRY_VERSION}
            )
            if assessment.evidence_status is EvidenceStatus.INSUFFICIENT:
                request = _graph_evidence_request(
                    request=assessment.missing_evidence_request,
                    state=state,
                    evidence_round=state["evidence_round"] + 1,
                    dependencies=dependencies,
                )
                assessment = assessment.model_copy(
                    update={"missing_evidence_request": request}
                )
            if assessment.claim_registry_version != CLAIM_REGISTRY_VERSION:
                raise ContractInvariantError("assessment registry version mismatch")
            validate_evidence_assessment(
                assessment,
                state["policy_bundle"],
                state["order_snapshot"],
                state["claimed_line_item_ids"],
            )
        except Exception:  # noqa: BLE001 - model/provider boundary fails closed
            return _fail(EscalationReason.CONTRACT_VIOLATION)

        update: dict[str, object] = {
            "evidence_bundle": evidence,
            "evidence_assessment": assessment,
        }
        if assessment.evidence_status is EvidenceStatus.INSUFFICIENT:
            if state["evidence_round"] >= EVIDENCE_LIMIT:
                return update | _fail(EscalationReason.EVIDENCE_BUDGET_EXCEEDED)
            next_round = state["evidence_round"] + 1
            update.update(
                {
                    "evidence_round": next_round,
                    "pending_evidence_request": assessment.missing_evidence_request,
                    "_route": "request_evidence",
                }
            )
        else:
            update.update(
                {"pending_evidence_request": None, "_route": "propose_decision"}
            )
        return update

    return node


def _request_evidence_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        request = state["pending_evidence_request"]
        if request is None:
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        value = interrupt(
            {
                "kind": AgentInterruptKind.EVIDENCE_REQUEST.value,
                "case_ref": state["case_ref"],
                "request": request.model_dump(mode="json"),
            }
        )
        try:
            resume = EvidenceResume.model_validate(value)
            if len(resume.artifact_refs) != len(set(resume.artifact_refs)):
                raise ContractInvariantError("artifact_refs must be unique")
            new_items = []
            for artifact_ref in resume.artifact_refs:
                item = _validate_provider_result(
                    EVIDENCE_ITEM_ADAPTER,
                    dependencies.evidence_provider.resolve(artifact_ref),
                )
                validate_resolved_evidence_item(item, artifact_ref, request)
                new_items.append(item)
            evidence = _merge_evidence(state.get("evidence_bundle", []), new_items)
        except Exception:  # noqa: BLE001 - provider boundary fails closed
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        return {"evidence_bundle": evidence, "_route": "prepare_memory_query"}

    return node


def _request_findings(state: AgentState):
    review = state.get("pending_review_result")
    if review is not None:
        return review.reviewer_claim_findings
    assessment = state["evidence_assessment"]
    if assessment is None:
        raise ContractInvariantError("proposal requires an evidence assessment")
    return assessment.claim_findings


def _draft_matches_current_handoff(state: AgentState, draft: Any) -> bool:
    handoff = state.get("current_handoff")
    if handoff is None:
        return False
    draft_value = draft.model_dump(mode="json")
    current_value = handoff.proposed_decision.model_dump(mode="json")
    draft_value.pop("policy_refs", None)
    draft_value.pop("evidence_refs", None)
    current_value.pop("policy_refs", None)
    current_value.pop("evidence_refs", None)
    current_value.pop("amount", None)
    current_value.pop("currency", None)
    return_decision = current_value.get("return_decision")
    if isinstance(return_decision, dict) and return_decision.get("source") == "POLICY":
        current_value["return_decision"] = {
            "source": "POLICY",
            "reason_code": return_decision["requirement"]["reason_code"],
        }
    current_value["rationale_summary"] = handoff.rationale_summary
    return draft_value == current_value


def _propose_decision_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        if state["propose_round"] >= PROPOSE_LIMIT:
            return _fail(EscalationReason.PROPOSE_BUDGET_EXCEEDED)
        next_round = state["propose_round"] + 1
        working = dict(state)
        working["propose_round"] = next_round
        try:
            output = dependencies.model.generate(
                task=ModelTask.PROPOSE_OR_REVISE,
                system_prompt=RESOLVER_SYSTEM_PROMPT,
                payload=_resolver_payload(cast(AgentState, working)),
                output_schema=RESOLVER_SCHEMA,
            )
            if isinstance(output, ResolverConflictOutput):
                return {
                    "propose_round": next_round,
                } | _fail(EscalationReason.CONFLICTING_REVISIONS)
            if isinstance(output, ResolverEvidenceRequestOutput):
                evidence_round = state["evidence_round"] + 1
                evidence_request = _graph_evidence_request(
                    request=output.evidence_request,
                    state=state,
                    evidence_round=evidence_round,
                    dependencies=dependencies,
                )
                validate_evidence_request(
                    evidence_request,
                    _request_findings(state),
                    state["policy_bundle"],
                    state["order_snapshot"],
                    state["claimed_line_item_ids"],
                )
                if state["evidence_round"] >= EVIDENCE_LIMIT:
                    return {"propose_round": next_round} | _fail(
                        EscalationReason.EVIDENCE_BUDGET_EXCEEDED
                    )
                return {
                    "propose_round": next_round,
                    "evidence_round": evidence_round,
                    "pending_evidence_request": evidence_request,
                    "_route": "request_evidence",
                }
            if not isinstance(output, ResolverDraftOutput):
                raise ContractInvariantError("unknown ResolverOutput variant")
            if (
                state.get("pending_review_result") is not None
                or state.get("verification_feedback")
            ) and _draft_matches_current_handoff(state, output.draft):
                raise ContractInvariantError(
                    "revised proposal must not repeat the prior handoff unchanged"
                )
            handoff = build_proposed_handoff(
                state=cast(AgentState, working),
                draft=output.draft,
                dependencies=dependencies,
            )
        except Exception:  # noqa: BLE001 - model/contract boundary fails closed
            return {"propose_round": next_round} | _fail(
                EscalationReason.CONTRACT_VIOLATION
            )
        return {
            "propose_round": next_round,
            "current_handoff": handoff,
            "proposal_history": [*state.get("proposal_history", []), handoff],
            "pending_evidence_request": None,
            "pending_review_result": None,
            "verification_feedback": [],
            "_route": "external_verification",
        }

    return node


def _external_verification_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        handoff = state.get("current_handoff")
        if handoff is None:
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        try:
            result = _validate_provider_result(
                VERIFICATION_RESULT_ADAPTER,
                dependencies.verification_provider.verify(handoff),
            )
        except Exception:  # noqa: BLE001 - provider boundary fails closed
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        if result.status is VerificationStatus.PASS:
            return {"verification_result": result, "verification_feedback": [], "_route": "reviewer"}
        if result.status is VerificationStatus.UNAVAILABLE:
            return {"verification_result": result} | _fail(EscalationReason.VERIFICATION_UNAVAILABLE)
        if state["verification_round"] >= VERIFICATION_LIMIT:
            return {"verification_result": result, "verification_feedback": list(result.issues)} | _fail(
                EscalationReason.VERIFICATION_BUDGET_EXCEEDED
            )
        return {
            "verification_result": result,
            "verification_feedback": list(result.issues),
            "verification_round": state["verification_round"] + 1,
            "_route": "propose_decision",
        }

    return node


def _reviewer_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        handoff = state.get("current_handoff")
        if handoff is None:
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        payload = {
            "prompt_version": REVIEWER_PROMPT_VERSION,
            "reviewed_at_utc": json_value(dependencies.clock.now()),
            "case_context": json_value(state["case_context"]),
            "order_snapshot": json_value(state["order_snapshot"]),
            "policy_bundle": json_value(state["policy_bundle"]),
            "claim_registry_version": CLAIM_REGISTRY_VERSION,
            "claim_registry": _relevant_registry(state),
            "expected_claim_subject_pairs": _expected_claim_pair_prompt_view(state),
            "proposed_decision_handoff": json_value(handoff),
        }
        try:
            result = dependencies.model.generate(
                task=ModelTask.REVIEW,
                system_prompt=REVIEWER_SYSTEM_PROMPT,
                payload=payload,
                output_schema=REVIEW_SCHEMA,
            )
            result = result.model_copy(
                update={
                    "reviewer_prompt_version": REVIEWER_PROMPT_VERSION,
                    "reviewed_at": dependencies.clock.now(),
                }
            )
            validate_review_result(
                result,
                handoff,
                state["policy_bundle"],
                state["order_snapshot"],
                state["claimed_line_item_ids"],
            )
        except Exception as error:  # noqa: BLE001 - boundary fails closed
            LOGGER.error(
                "reviewer failed closed (%s): %s",
                type(error).__name__,
                error,
            )
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        history = [*state.get("review_history", []), result]
        if result.verdict is ReviewVerdict.APPROVE:
            decision = handoff.proposed_decision
            gate = evaluate_review_gate(decision.action, decision.amount, decision.currency, dependencies.reviewer_gate_config)
            if gate.status == "HUMAN_REQUIRED":
                return {"review_history": history, "review_gate": gate,
                    "review_routing_reason": gate.reason, "human_review_ref": None,
                    "human_review_result": None, "_route": "await_human_review"}
            return {
                "review_history": history,
                "review_gate": gate,
                "review_routing_reason": None,
                "_route": "emit_resolution_handoff",
            }
        if state["revision_round"] >= REVISION_LIMIT:
            return {
                "review_history": history,
                "review_gate": None,
                "review_routing_reason": "REVISION_BUDGET_EXCEEDED",
                "human_review_ref": None,
                "human_review_result": None,
                "_route": "await_human_review",
            }
        return {
            "review_history": history,
            "review_gate": None,
            "pending_review_result": result,
            "review_routing_reason": None,
            "_route": "record_revision_event",
        }

    return node


def _record_revision_event_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        review = state.get("pending_review_result")
        if review is None:
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        try:
            event = build_revision_event(
                state=state,
                review_result=review,
                dependencies=dependencies,
            )
        except Exception:  # noqa: BLE001 - state contract fails closed
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        return {
            "revision_events": [*state.get("revision_events", []), event],
            "revision_round": event.revision_round,
            "_route": "propose_decision",
        }

    return node


def _await_human_review_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        handoff = state.get("current_handoff")
        review = state["review_history"][-1]
        if handoff is None:
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        try:
            validate_human_review_entry(handoff, review, build_human_review_dossier(state), dependencies.reviewer_gate_config)
        except ValueError:
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        review_ref = state.get("human_review_ref")
        if review_ref is None:
            try:
                review_ref = dependencies.human_review_provider.submit_for_review(
                    handoff, review, build_human_review_dossier(state)
                )
                if not review_ref or not str(review_ref).strip():
                    raise ContractInvariantError("human review_ref must be non-empty")
            except Exception:  # noqa: BLE001 - provider boundary fails closed
                return _fail(EscalationReason.CONTRACT_VIOLATION)
            return {
                "human_review_ref": str(review_ref),
                "_route": "await_human_review",
            }

        try:
            result = dependencies.human_review_provider.fetch_result(review_ref)
            if result is not None:
                result = _validate_provider_result(HUMAN_REVIEW_RESULT_ADAPTER, result)
        except Exception:  # noqa: BLE001 - provider boundary fails closed
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        if result is not None:
            return {
                "human_review_result": result,
                "_route": "emit_resolution_handoff",
            }

        value = interrupt(
            {
                "kind": AgentInterruptKind.HUMAN_REVIEW.value,
                "routing_reason": state["review_routing_reason"],
                "case_ref": state["case_ref"],
                "handoff_id": handoff.handoff_id,
                "review_ref": review_ref,
            }
        )
        try:
            HumanReviewPollResume.model_validate(value)
        except ValidationError:
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        return {"_route": "await_human_review"}

    return node


def _emit_resolution_handoff_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        try:
            resolution = build_resolution_handoff(
                state=state,
                dependencies=dependencies,
            )
        except Exception:  # noqa: BLE001 - terminal contract fails closed
            return _fail(EscalationReason.CONTRACT_VIOLATION)
        return {
            "resolution_handoff": resolution,
            "_route": "enqueue_memory_distillation",
        }

    return node


def _enqueue_memory_distillation_node(state: AgentState) -> dict[str, object]:
    """Prepare a durable-job payload; Agent Service owns the Redis enqueue."""

    try:
        memory_input = build_memory_distillation_input(state)
    except Exception:
        LOGGER.exception("memory distillation input could not be assembled")
        return {"memory_distillation_input": None, "_route": "__end__"}
    return {"memory_distillation_input": memory_input, "_route": "__end__"}


def _terminate_automation_node(dependencies: AgentDependencies):
    def node(state: AgentState) -> dict[str, object]:
        reason = state.get("escalation_reason")
        if reason is None:
            reason = EscalationReason.CONTRACT_VIOLATION
        handoff = build_manual_escalation(
            state=state,
            reason=reason,
            dependencies=dependencies,
        )
        return {"manual_escalation": handoff}

    return node


def _route(state: AgentState) -> str:
    return state["_route"]


def build_graph(
    *,
    dependencies: AgentDependencies,
    checkpointer: BaseCheckpointSaver[Any],
) -> CompiledStateGraph:
    """Compile the return-resolution graph with an injected checkpointer."""

    from dataclasses import replace

    from return_agent_contracts.activity_observer import ObservedProvider

    from .activity import traced_node
    from .learning import record_learning_node

    dependencies = replace(dependencies, **{
        key: ObservedProvider(getattr(dependencies, key), key, "model" if key == "model" else "tool")
        for key in ("model", "case_context_provider", "policy_provider",
                    "verification_provider", "human_review_provider",
                    "operational_memory_store", "evidence_provider")
    })
    builder = StateGraph(AgentState)
    def add_node(name, function):
        builder.add_node(name, traced_node(name, record_learning_node(name, function, dependencies.learning_trace_limits)))
    add_node("parse_request", _parse_request_node(dependencies))
    add_node("request_clarification", _request_clarification_node)
    add_node("load_case_context", _load_case_context_node(dependencies))
    add_node("retrieve_policy", _retrieve_policy_node(dependencies))
    add_node("prepare_memory_query", _prepare_memory_query_node(dependencies))
    add_node("retrieve_memory", _retrieve_memory_node(dependencies))
    add_node("assess_case", _assess_case_node(dependencies))
    add_node("request_evidence", _request_evidence_node(dependencies))
    add_node("propose_decision", _propose_decision_node(dependencies))
    add_node("external_verification", _external_verification_node(dependencies))
    add_node("reviewer", _reviewer_node(dependencies))
    add_node("record_revision_event", _record_revision_event_node(dependencies))
    add_node("await_human_review", _await_human_review_node(dependencies))
    add_node(
        "emit_resolution_handoff", _emit_resolution_handoff_node(dependencies)
    )
    add_node("enqueue_memory_distillation", _enqueue_memory_distillation_node)
    add_node(
        "terminate_automation",
        _terminate_automation_node(dependencies),
    )

    builder.add_edge(START, "parse_request")
    destinations = {
        "parse_request": "parse_request",
        "request_clarification": "request_clarification",
        "load_case_context": "load_case_context",
        "retrieve_policy": "retrieve_policy",
        "prepare_memory_query": "prepare_memory_query",
        "retrieve_memory": "retrieve_memory",
        "assess_case": "assess_case",
        "request_evidence": "request_evidence",
        "propose_decision": "propose_decision",
        "external_verification": "external_verification",
        "reviewer": "reviewer",
        "record_revision_event": "record_revision_event",
        "await_human_review": "await_human_review",
        "emit_resolution_handoff": "emit_resolution_handoff",
        "enqueue_memory_distillation": "enqueue_memory_distillation",
        "terminate_automation": "terminate_automation",
        "__end__": END,
    }
    for source in (
        "parse_request",
        "request_clarification",
        "load_case_context",
        "retrieve_policy",
        "prepare_memory_query",
        "retrieve_memory",
        "assess_case",
        "request_evidence",
        "propose_decision",
        "external_verification",
        "reviewer",
        "record_revision_event",
        "await_human_review",
        "emit_resolution_handoff",
        "enqueue_memory_distillation",
    ):
        builder.add_conditional_edges(source, _route, destinations)
    builder.add_edge("terminate_automation", END)
    return builder.compile(checkpointer=checkpointer, name="return-resolution-agent")
