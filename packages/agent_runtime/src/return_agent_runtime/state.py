"""Typed working state and Python invocation DTOs."""

from __future__ import annotations

from return_agent_contracts.review_gates import ReviewGateResult, HumanReviewRoutingReason

from enum import StrEnum
from typing import Literal, TypedDict

from return_agent_contracts.enums import EscalationReason
from return_agent_contracts.models import (
    ApprovedMemory,
    CaseContext,
    ClarificationRequest,
    DecisionRevisionEvent,
    EvidenceAssessment,
    EvidenceItem,
    EvidenceRequest,
    HumanReviewResult,
    IntakeResult,
    ManualEscalationHandoff,
    MemoryDistillationInput,
    MemoryRetrievalObservation,
    OrderSnapshot,
    PolicyBundle,
    ProposedDecisionHandoff,
    ResolutionHandoff,
    ReviewResult,
    UserTurn,
    VerificationIssue,
)


class MemoryRetrievalStatus(StrEnum):
    OK = "OK"
    UNAVAILABLE = "UNAVAILABLE"


class AgentState(TypedDict, total=False):
    """LangGraph state; canonical case status remains outside the Agent."""

    thread_id: str
    case_ref: str
    trusted_order_ref: str | None
    conversation_turns: list[UserTurn]
    normalized_intent: IntakeResult | None
    claimed_line_item_ids: list[str]
    case_context: CaseContext
    order_snapshot: OrderSnapshot
    policy_bundle: PolicyBundle
    operational_memory: list[ApprovedMemory]
    memory_retrieval_status: MemoryRetrievalStatus
    memory_query_summary: str | None
    memory_retrieval: MemoryRetrievalObservation | None
    evidence_bundle: list[EvidenceItem]
    evidence_assessment: EvidenceAssessment | None
    current_handoff: ProposedDecisionHandoff | None
    proposal_history: list[ProposedDecisionHandoff]
    pending_review_result: ReviewResult | None
    verification_feedback: list[VerificationIssue]
    review_history: list[ReviewResult]
    review_routing_reason: HumanReviewRoutingReason | None
    review_gate: ReviewGateResult | None
    revision_events: list[DecisionRevisionEvent]
    pending_clarification_request: ClarificationRequest | None
    pending_evidence_request: EvidenceRequest | None
    human_review_ref: str | None
    human_review_result: HumanReviewResult | None
    resolution_handoff: ResolutionHandoff | None
    memory_distillation_input: MemoryDistillationInput | None
    manual_escalation: ManualEscalationHandoff | None
    escalation_reason: EscalationReason | None
    clarification_round: int
    evidence_round: int
    verification_round: int
    revision_round: int
    propose_round: int
    _route: str
