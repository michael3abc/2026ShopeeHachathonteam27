"""A closed correction trace is required before a memory job can exist."""
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .domain import CaseContext, DecisionRevisionEvent, EvidenceAssessment, PolicyBundle, ProposedDecisionHandoff
from .human import HumanReviewResult, ResolutionHandoff
from .memory import MemoryCandidate
from .primitives import ContractModel, Ref, UTCDateTime, unique


class MemoryDistillationInput(ContractModel):
    case_context: CaseContext
    claimed_categories: list[Ref] = Field(default_factory=list)
    evidence_assessment: EvidenceAssessment
    final_resolution: ResolutionHandoff
    human_review_result: HumanReviewResult | None = None
    policy_bundle: PolicyBundle
    proposal_history: Annotated[list[ProposedDecisionHandoff], Field(min_length=1)]
    revision_events: list[DecisionRevisionEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def closed_trace(self) -> Self:
        case = self.case_context.case_ref
        proposals = {p.handoff_id: p for p in self.proposal_history}
        unique([p.handoff_id for p in self.proposal_history], "distillation proposal ID")
        unique([e.event_id for e in self.revision_events], "distillation correction ID")
        unique(self.claimed_categories, "claimed category")
        if self.final_resolution.case_ref != case or any(p.case_ref != case for p in self.proposal_history):
            raise ValueError("Distillation trace mixes cases")
        for event in self.revision_events:
            if event.case_ref != case or event.handoff_before_ref not in proposals:
                raise ValueError("Correction does not belong to the proposal trace")
        latest = self.proposal_history[-1]
        if self.final_resolution.handoff_id != latest.handoff_id or latest.policy_bundle_version != self.policy_bundle.policy_bundle_version or latest.claim_registry_version != self.evidence_assessment.claim_registry_version:
            raise ValueError("Final resolution is not bound to the latest proposal and versions")
        human = self.human_review_result
        if self.final_resolution.outcome_source == "REVIEWER_APPROVE":
            if human is not None:
                raise ValueError("An automated resolution cannot carry a human result")
        elif human is None or self.final_resolution.outcome_source != f"HUMAN_{human.decision}":
            raise ValueError("Human resolution and recorded result disagree")
        if not self.revision_events and not (human is not None and human.decision in ("EDIT", "REJECT")):
            raise ValueError("A confirmed correction is required for memory distillation")
        return self


class MemoryCandidateOutput(ContractModel):
    result_type: Literal["CREATE_CANDIDATE"]
    candidate: MemoryCandidate


class MemorySkipOutput(ContractModel):
    result_type: Literal["SKIP"]
    reason_code: Literal["NO_FINAL_OUTCOME", "CASE_SPECIFIC_ONLY", "DATA_ENTRY_ERROR", "POLICY_VERSION_UNKNOWN", "CLAIM_REGISTRY_VERSION_UNKNOWN", "RESTATES_EXISTING_POLICY", "CONFLICTS_WITH_POLICY", "NO_CONFIRMED_GENERALIZABLE_CORRECTION"]


MemoryDistillationOutput = Annotated[MemoryCandidateOutput | MemorySkipOutput, Field(discriminator="result_type")]


class MemoryDistillationJobPayload(ContractModel):
    input: MemoryDistillationInput


class MemoryDistillationJob(ContractModel):
    schema_version: Literal["v1"] = "v1"
    job_id: Ref
    source_command_id: Ref
    case_ref: Ref
    thread_id: Ref
    issued_at: UTCDateTime
    payload: MemoryDistillationJobPayload

    @model_validator(mode="after")
    def same_case(self) -> Self:
        if self.case_ref != self.payload.input.case_context.case_ref:
            raise ValueError("Memory job case differs from its input")
        return self


class MemoryCandidateCompletedPayload(ContractModel):
    distiller_prompt_version: Ref
    result: MemoryCandidateOutput
    submission_ref: Ref


class MemorySkipCompletedPayload(ContractModel):
    distiller_prompt_version: Ref
    result: MemorySkipOutput
    submission_ref: None = None


class MemoryDistillationFailedPayload(ContractModel):
    code: Ref
    message: Ref
    retryable: bool
    distiller_prompt_version: Ref


class MemoryEventBase(ContractModel):
    schema_version: Literal["v1"] = "v1"
    event_id: Ref
    job_id: Ref
    source_command_id: Ref
    case_ref: Ref
    thread_id: Ref
    occurred_at: UTCDateTime


class MemoryDistillationCompletedEvent(MemoryEventBase):
    event_type: Literal["COMPLETED"]
    payload: MemoryCandidateCompletedPayload | MemorySkipCompletedPayload


class MemoryDistillationFailedEvent(MemoryEventBase):
    event_type: Literal["FAILED"]
    payload: MemoryDistillationFailedPayload


MemoryServiceEvent = Annotated[MemoryDistillationCompletedEvent | MemoryDistillationFailedEvent, Field(discriminator="event_type")]
