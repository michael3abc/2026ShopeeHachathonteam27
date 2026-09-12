"""Operational-memory distillation, independent from case graph routing."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import TypeAdapter
from return_agent_contracts.enums import HumanDecision, MemorySkipReasonCode
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
                "distillation_input": input_,
                "allowed_scope": {
                    "market": input_.case_context.market,
                    "reason_codes": [latest.proposed_decision.reason_code.value],
                    "claim_ids": required_claim_ids,
                    "categories": list(input_.claimed_categories),
                },
            },
            output_schema=MEMORY_OUTPUT_SCHEMA,
        )
        if not isinstance(output, MemoryCandidateOutput):
            return output

        source_refs = [event.event_id for event in input_.revision_events]
        human = input_.human_review_result
        if human is not None and human.decision in {
            HumanDecision.EDIT,
            HumanDecision.REJECT,
        }:
            source_refs.append(human.final_resolution_ref)
        source_refs = list(dict.fromkeys(source_refs))
        if not source_refs:
            raise ContractInvariantError("candidate has no correction source")

        candidate = output.candidate.model_copy(
            update={
                "memory_id": self.id_factory.make(
                    "memory", input_.case_context.case_ref, latest.handoff_id
                ),
                "source_case_refs": [input_.case_context.case_ref],
                "source_revision_event_refs": source_refs,
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
            result_type="CREATE_CANDIDATE", candidate=candidate
        )

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
        if not set(candidate.scope.reason_codes).issubset(allowed_reasons):
            raise ContractInvariantError("memory reason scope exceeds source case")
        if not set(candidate.scope.claim_ids).issubset(required_claims):
            raise ContractInvariantError("memory claim scope exceeds applicable policy")
        if not set(candidate.scope.categories).issubset(allowed_categories):
            raise ContractInvariantError("memory category scope exceeds claimed items")
