"""Operational-memory distillation, independent from case graph routing."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import TypeAdapter
from return_agent_contracts.enums import MemorySkipReasonCode
from return_agent_contracts.models import (
    MemoryCandidateOutput,
    MemoryDistillationInput,
    MemoryDistillationOutput,
    MemorySkipOutput,
)
from return_agent_contracts.registry import CLAIM_REGISTRY_VERSION
from return_agent_contracts.validation import (
    ContractInvariantError,
    validate_memory_candidate,
)

from .dependencies import IdFactory, StableIdFactory
from .learning import LearningTraceLimits, validate_safe_learning_text
from .model import ModelTask, OutputSchema, StructuredOutputModel
from .prompts import MEMORY_DISTILLER_PROMPT_VERSION, MEMORY_DISTILLER_SYSTEM_PROMPT

MEMORY_OUTPUT_SCHEMA = OutputSchema(
    "MemoryDistillationOutput", TypeAdapter(MemoryDistillationOutput)
)


@dataclass(frozen=True, slots=True)
class MemoryDistiller:
    """Create a governed candidate or an explicit skip from a closed trace."""

    model: StructuredOutputModel
    id_factory: IdFactory = field(default_factory=StableIdFactory)
    prompt_version: str = MEMORY_DISTILLER_PROMPT_VERSION
    trace_limits: LearningTraceLimits = field(default_factory=LearningTraceLimits)
    model_profile: dict[str, object] | None = None

    def distill(self, input_: MemoryDistillationInput) -> MemoryDistillationOutput:
        latest = input_.proposal_history[-1]
        if latest.claim_registry_version != CLAIM_REGISTRY_VERSION:
            return MemorySkipOutput(
                result_type="SKIP",
                reason_code=MemorySkipReasonCode.CLAIM_REGISTRY_VERSION_UNKNOWN,
            )
        policy_versions = {
            clause.policy_version for clause in input_.policy_bundle.clauses
        }
        if len(policy_versions) != 1:
            return MemorySkipOutput(
                result_type="SKIP",
                reason_code=MemorySkipReasonCode.POLICY_VERSION_UNKNOWN,
            )
        trace = input_.learning_trace
        if trace is None or trace.status in {"RECORDING", "INCOMPLETE"}:
            return MemorySkipOutput(result_type="SKIP", reason_code="TRACE_INCOMPLETE")
        if trace.status == "UNSAFE_CONTENT":
            return MemorySkipOutput(result_type="SKIP", reason_code="TRACE_UNSAFE_CONTENT")
        if (trace.status == "LIMIT_EXCEEDED" or len(trace.events) > self.trace_limits.max_events
                or len(trace.model_dump_json().encode()) > self.trace_limits.max_bytes):
            return MemorySkipOutput(result_type="SKIP", reason_code="TRACE_LIMIT_EXCEEDED")
        if (trace.dialogue_version != "learning-dialogue:1"
                or any(event.dialogue_missing for event in trace.events)
                or not trace.events or not trace.events[0].dialogue):
            return MemorySkipOutput(result_type="SKIP", reason_code="TRACE_INCOMPLETE")
        required_nodes = {"parse_request", "load_case_context", "retrieve_policy",
                          "assess_case", "propose_decision", "external_verification",
                          "reviewer", "emit_resolution_handoff"}
        if (not required_nodes.issubset(event.node for event in trace.events)
                or trace.case_ref != input_.case_context.case_ref
                or not trace.events[-1].decision
                or trace.events[-1].decision.handoff_id != input_.final_resolution.handoff_id
                or trace.events[-1].decision.action != input_.final_resolution.final_decision.action):
            return MemorySkipOutput(result_type="SKIP", reason_code="TRACE_INCOMPLETE")
        for previous, current in zip(trace.events, trace.events[1:]):
            if previous.next_node != current.node:
                return MemorySkipOutput(result_type="SKIP", reason_code="TRACE_INCOMPLETE")
        try:
            # Validate even model_copy-mutated DTOs before they reach a model.
            type(trace).model_validate(trace.model_dump(mode="json"))
            validate_safe_learning_text(trace.model_dump(mode="json"))
            validate_safe_learning_text(input_.policy_bundle.model_dump(mode="json"))
        except ValueError:
            return MemorySkipOutput(result_type="SKIP", reason_code="TRACE_UNSAFE_CONTENT")
        required_claim_ids = list(
            dict.fromkeys(
                claim_id.value
                for clause in input_.policy_bundle.clauses
                for claim_id in clause.required_claim_ids
            )
        )
        output = self.model.generate(
            task=ModelTask.MEMORY_DISTILL,
            system_prompt=MEMORY_DISTILLER_SYSTEM_PROMPT,
            payload={
                "learning_trace": trace,
                "policy_bundle": input_.policy_bundle,
                "downstream_execution_verified": False,
                "allowed_scope": {
                    "market": input_.case_context.market,
                    "reason_codes": [latest.proposed_decision.reason_code.value],
                    "claim_ids": required_claim_ids,
                    "categories": list(input_.claimed_categories),
                },
            },
            output_schema=MEMORY_OUTPUT_SCHEMA,
        )
        self._validate_review(output, input_)
        if not isinstance(output, MemoryCandidateOutput):
            return output
        if output.learning.category not in {"VERIFIABLE_ERROR", "OPERATIONAL_METHOD"}:
            raise ContractInvariantError("learning category cannot create operational memory")
        self._validate_sources(output.candidate.source_event_refs, input_)
        if not set(output.candidate.source_event_refs).issubset(output.learning.source_event_refs):
            raise ContractInvariantError("candidate sources must support the learning judgment")
        if not output.candidate.applicability_limits or not output.candidate.prohibited_inferences:
            raise ContractInvariantError("new experience requires applicability limits and prohibited inferences")
        existing_lessons = {m.recommended_behavior.strip().casefold() for e in trace.events for m in e.memories}
        if output.candidate.recommended_behavior.strip().casefold() in existing_lessons:
            return MemorySkipOutput(result_type="SKIP", reason_code="RESTATES_EXISTING_POLICY",
                                    case_review=output.case_review, learning=output.learning)

        candidate = output.candidate.model_copy(
            update={
                "memory_id": self.id_factory.make(
                    "memory-v2", input_.case_context.case_ref, latest.handoff_id
                ),
                "source_case_refs": [input_.case_context.case_ref],
                "policy_version": next(iter(policy_versions)),
                "claim_registry_version": latest.claim_registry_version,
                "scope": output.candidate.scope.model_copy(
                    update={"market": input_.case_context.market}
                ),
                "status": "CANDIDATE",
            }
        )
        self._validate_scope(candidate, input_)
        validate_memory_candidate(candidate)
        return MemoryCandidateOutput(
            result_type="CREATE_CANDIDATE", candidate=candidate,
            case_review=output.case_review, learning=output.learning,
        )

    @staticmethod
    def _validate_sources(refs: list[str], input_: MemoryDistillationInput) -> None:
        known = {event.event_id for event in input_.learning_trace.events}
        if not refs or len(refs) != len(set(refs)) or not set(refs).issubset(known):
            raise ContractInvariantError("learning source events must exist in this case trace")

    def _validate_review(self, output, input_: MemoryDistillationInput) -> None:
        if output.case_review is None or output.learning is None:
            raise ContractInvariantError("model output requires whole-case review and learning judgment, including SKIP")
        if output.case_review.final_action != input_.final_resolution.final_decision.action:
            raise ContractInvariantError("case review contradicts final adjudication")
        self._validate_sources(output.case_review.source_event_refs, input_)
        self._validate_sources(output.learning.source_event_refs, input_)
        if input_.learning_trace.events[-1].event_id not in output.case_review.source_event_refs:
            raise ContractInvariantError("case review must cite the final resolution event")
        validate_safe_learning_text(output.case_review.model_dump(mode="json"))
        validate_safe_learning_text(output.learning.model_dump(mode="json"))

    @staticmethod
    def _validate_scope(candidate, input_: MemoryDistillationInput) -> None:
        latest = input_.proposal_history[-1]
        allowed_reasons = {latest.proposed_decision.reason_code}
        required_claims = {
            claim_id
            for clause in input_.policy_bundle.clauses
            for claim_id in clause.required_claim_ids
        }
        allowed_categories = set(input_.claimed_categories)
        # Empty scope lists are wildcards in the store, not an empty subset.
        for scope_field, allowed in (("reason_codes", allowed_reasons),
                               ("claim_ids", required_claims),
                               ("categories", allowed_categories)):
            if allowed and not getattr(candidate.scope, scope_field):
                raise ContractInvariantError("memory wildcard scope exceeds source case")
        if not set(candidate.scope.reason_codes).issubset(allowed_reasons):
            raise ContractInvariantError("memory reason scope exceeds source case")
        if not set(candidate.scope.claim_ids).issubset(required_claims):
            raise ContractInvariantError("memory claim scope exceeds applicable policy")
        if not set(candidate.scope.categories).issubset(allowed_categories):
            raise ContractInvariantError("memory category scope exceeds claimed items")
