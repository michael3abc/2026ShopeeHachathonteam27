from typing import Any

from pydantic import Field

from return_agent_contracts.distillation import MemoryDistillationInput
from return_agent_contracts.domain import CaseContext, DecisionRevisionEvent, EvidenceAssessment, EvidenceItem, EvidenceRequest, HumanReviewDossier, OrderSnapshot, PolicyBundle, ProposedDecisionHandoff, ReviewGateResult, ReviewResult, VerificationIssue
from return_agent_contracts.human import HumanReviewResult, ResolutionHandoff
from return_agent_contracts.memory import MemoryRetrievalObservation
from return_agent_contracts.messages import AgentUserTurn, ClarificationRequest, IntakeResult
from return_agent_contracts.primitives import ContractModel, Ref
from return_agent_contracts.workflow import EscalationReason, ManualEscalationHandoff, RoutingReason


class RuntimeState(ContractModel):
    case_ref: Ref
    thread_id: Ref
    trusted_order_ref: Ref | None = None
    conversation_turns: list[AgentUserTurn] = Field(default_factory=list)
    normalized_intent: IntakeResult | None = None
    claimed_line_item_ids: list[Ref] = Field(default_factory=list)
    case_context: CaseContext | None = None
    order_snapshot: OrderSnapshot | None = None
    policy_bundle: PolicyBundle | None = None
    evidence_bundle: list[EvidenceItem] = Field(default_factory=list)
    evidence_assessment: EvidenceAssessment | None = None
    memory_retrieval: MemoryRetrievalObservation | None = None
    current_handoff: ProposedDecisionHandoff | None = None
    proposal_history: list[ProposedDecisionHandoff] = Field(default_factory=list)
    review_history: list[ReviewResult] = Field(default_factory=list)
    reviewed_proposal_ids: list[Ref] = Field(default_factory=list)
    pending_review_result: ReviewResult | None = None
    verification_feedback: list[VerificationIssue] = Field(default_factory=list)
    revision_events: list[DecisionRevisionEvent] = Field(default_factory=list)
    review_gate: ReviewGateResult | None = None
    routing_reason: RoutingReason | None = None
    clarification_request: ClarificationRequest | None = None
    evidence_request: EvidenceRequest | None = None
    human_dossier: HumanReviewDossier | None = None
    human_review_ref: Ref | None = None
    human_review_result: HumanReviewResult | None = None
    resolution: ResolutionHandoff | None = None
    memory_distillation_input: MemoryDistillationInput | None = None
    escalation_reason: EscalationReason | None = None
    escalation: ManualEscalationHandoff | None = None
    clarification_round: int = Field(default=0, ge=0)
    evidence_round: int = Field(default=0, ge=0)
    verification_round: int = Field(default=0, ge=0)
    revision_round: int = Field(default=0, ge=0)
    propose_round: int = Field(default=0, ge=0)
    node_attempts: dict[str, int] = Field(default_factory=dict)
    route: str = "parse_request"

    def checkpoint_values(self) -> dict[str, Any]:
        # Only JSON primitives enter the checkpoint, never clients or arbitrary classes.
        return self.model_dump(mode="json")
