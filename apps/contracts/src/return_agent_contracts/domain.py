"""Typed return-case domain contracts, without persistence or I/O."""
from typing import Annotated, Literal, Self

from pydantic import Field, WithJsonSchema, model_validator

from .primitives import Amount, ContractModel, Currency, Ref, UTCDateTime, exact_total, unique

ClaimId = Literal[
    "DELIVERY_CONFIRMED", "ORDER_WITHIN_RETURN_WINDOW", "SHIPMENT_SEAL_INTACT",
    "ITEM_PHYSICALLY_DAMAGED", "DAMAGE_PRESENT_ON_ARRIVAL", "ITEM_FUNCTIONALLY_IMPAIRED",
    "ITEM_DIFFERS_FROM_LISTING", "WRONG_ITEM_RECEIVED", "ITEM_NOT_IN_SHIPMENT", "ITEM_UNUSED",
]
EvidenceType = Literal["IMAGE", "VIDEO", "TEXT", "DOCUMENT"]
ReasonCode = Literal["ITEM_DAMAGED", "ITEM_NOT_AS_DESCRIBED", "MISSING_ITEM", "WRONG_ITEM", "QUALITY_ISSUE", "CHANGED_MIND"]
Action = Literal["FULL_REFUND", "DECLINE"]
ReturnPolicy = Literal["REQUIRED", "NOT_REQUIRED", "MODEL_JUDGMENT"]
RequiredReturnReasonCode = Literal["RESALE_VALUE_RETAINED", "RETURN_REQUIRED_FOR_INSPECTION"]
WaivedReturnReasonCode = Literal["ITEM_UNSALVAGEABLE", "HYGIENE_RISK", "RETURN_UNECONOMICAL", "EVIDENCE_SUFFICIENT_WITHOUT_RETURN"]
RevisionReasonCode = Literal[
    "EVIDENCE_INSUFFICIENT", "POLICY_MISMATCH", "DECISION_UNSUPPORTED", "DECISION_INCONSISTENT",
    "SCOPE_UNSUPPORTED", "RETURN_REQUIREMENT_INCONSISTENT", "HANDOFF_INCOMPLETE", "OTHER",
]


class OrderLineItem(ContractModel):
    line_item_id: Ref
    sku_ref: Ref
    category_ref: Ref
    title: Ref
    quantity: Annotated[int, Field(ge=1, strict=True)]
    refundable_amount: Amount


class OrderSnapshot(ContractModel):
    order_ref: Ref
    order_snapshot_ref: Ref
    snapshot_version: Annotated[int, Field(ge=1, strict=True)]
    currency: Currency
    captured_at: UTCDateTime
    delivered_at: UTCDateTime
    refundable_amount_max: Amount
    already_refunded_amount: Amount
    line_items: Annotated[list[OrderLineItem], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_items(self) -> Self:
        unique([item.line_item_id for item in self.line_items], "order line item")
        if self.already_refunded_amount > self.refundable_amount_max:
            raise ValueError("Previously refunded amount exceeds the trusted order maximum")
        return self


class CaseContext(ContractModel):
    case_ref: Ref
    order_ref: Ref
    market: Ref
    case_opened_at: UTCDateTime
    snapshot_version: Annotated[int, Field(ge=1, strict=True)]


class CaseContextLoadResult(ContractModel):
    case_context: CaseContext
    order_snapshot: OrderSnapshot

    @model_validator(mode="after")
    def matching_order(self) -> Self:
        if self.case_context.order_ref != self.order_snapshot.order_ref or self.case_context.snapshot_version != self.order_snapshot.snapshot_version:
            raise ValueError("Context and snapshot do not identify the same order version")
        return self


class ClaimDefinition(ContractModel):
    claim_id: ClaimId
    description: Ref
    observable_requirement: Ref
    subject_scope: Literal["ORDER", "LINE_ITEM"]
    satisfiable_by: list[Literal["SYSTEM_FACTS", "USER_EVIDENCE"]]
    accepted_evidence_types: list[EvidenceType] = Field(default_factory=list)
    distinguish_from: list[ClaimId] = Field(default_factory=list)


class EvidenceItem(ContractModel):
    evidence_id: Ref
    artifact_ref: Ref
    type: EvidenceType
    source: Literal["USER", "ORDER_TOOL", "LOGISTICS_TOOL", "SYSTEM"]
    subject: Ref
    extracted_summary: Ref
    collected_at: UTCDateTime


class ApplicableConditions(ContractModel):
    markets: list[Ref] = Field(default_factory=list)
    categories: list[Ref] = Field(default_factory=list)
    reason_codes: list[ReasonCode] = Field(default_factory=list)


class PolicyClause(ContractModel):
    clause_id: Ref
    policy_version: Ref
    text: Ref
    required_claim_ids: Annotated[list[ClaimId], Field(min_length=1)]
    allowed_actions: Annotated[list[Action], Field(min_length=1)]
    return_policy: ReturnPolicy
    applicable_conditions: ApplicableConditions
    effective_from: UTCDateTime
    effective_to: UTCDateTime | None = None

    @model_validator(mode="after")
    def coherent_clause(self) -> Self:
        unique(self.required_claim_ids, "required claim")
        unique(self.allowed_actions, "allowed action")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("Policy effective interval is reversed")
        return self


class PolicyBundle(ContractModel):
    policy_bundle_version: Ref
    retrieval_status: Literal["OK", "NOT_FOUND", "AMBIGUOUS"]
    retrieved_at: UTCDateTime
    clauses: list[PolicyClause] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent_bundle(self) -> Self:
        unique([clause.clause_id for clause in self.clauses], "policy clause")
        if self.retrieval_status == "OK" and not self.clauses:
            raise ValueError("An OK policy bundle needs clauses")
        return self


class ClaimFinding(ContractModel):
    claim_id: ClaimId
    subject: Ref
    status: Literal["SUPPORTED", "UNSUPPORTED", "CONTRADICTED"]
    explanation: Ref
    supporting_evidence_refs: list[Ref] = Field(default_factory=list)


class MissingClaim(ContractModel):
    claim_id: ClaimId
    subject: Ref


class EvidenceRequest(ContractModel):
    request_id: Ref
    missing_claims: Annotated[list[MissingClaim], Field(min_length=1)]
    accepted_evidence_types: Annotated[list[EvidenceType], Field(min_length=1)]
    policy_refs: Annotated[list[Ref], Field(min_length=1)]
    user_message: Ref


class AssessmentBase(ContractModel):
    claim_registry_version: Ref
    claim_findings: Annotated[list[ClaimFinding], Field(min_length=1)]


class ApprovalEvidenceAssessment(AssessmentBase):
    evidence_status: Literal["SUFFICIENT_FOR_APPROVAL"]


class DeclineEvidenceAssessment(AssessmentBase):
    evidence_status: Literal["SUFFICIENT_FOR_DECLINE"]


class InsufficientEvidenceAssessment(AssessmentBase):
    evidence_status: Literal["INSUFFICIENT"]
    missing_evidence_request: EvidenceRequest


EvidenceAssessment = Annotated[ApprovalEvidenceAssessment | DeclineEvidenceAssessment | InsufficientEvidenceAssessment, Field(discriminator="evidence_status")]


class NonEmptyRefundScope(ContractModel):
    line_item_ids: Annotated[list[Ref], Field(min_length=1)]

    @model_validator(mode="after")
    def distinct(self) -> Self:
        unique(self.line_item_ids, "refund item")
        return self


class EmptyRefundScope(ContractModel):
    line_item_ids: Annotated[list[Ref], Field(max_length=0)]


class RequiredReturnRequirement(ContractModel):
    required: Literal[True]
    reason_code: RequiredReturnReasonCode


class WaivedReturnRequirement(ContractModel):
    required: Literal[False]
    reason_code: WaivedReturnReasonCode


ReturnRequirement = Annotated[RequiredReturnRequirement | WaivedReturnRequirement, Field(discriminator="required")]


class PolicyReturnDecision(ContractModel):
    source: Literal["POLICY"]
    requirement: ReturnRequirement


class ModelJudgmentReturnDecision(ContractModel):
    source: Literal["MODEL_JUDGMENT"]
    requirement: ReturnRequirement


class HumanReviewReturnDecision(ContractModel):
    source: Literal["HUMAN_REVIEW"]
    requirement: ReturnRequirement


class PolicyReturnDecisionDraft(ContractModel):
    source: Literal["POLICY"]
    reason_code: RequiredReturnReasonCode | WaivedReturnReasonCode


AgentReturnDecision = Annotated[PolicyReturnDecision | ModelJudgmentReturnDecision, Field(discriminator="source")]
DraftReturnDecision = Annotated[PolicyReturnDecisionDraft | ModelJudgmentReturnDecision, Field(discriminator="source")]


class ProposedDecisionBase(ContractModel):
    reason_code: ReasonCode
    policy_refs: Annotated[list[Ref], Field(min_length=1)]
    evidence_refs: list[Ref] = Field(default_factory=list)
    amount: Amount
    currency: Currency


class FullRefundProposedDecision(ProposedDecisionBase):
    action: Literal["FULL_REFUND"]
    refund_scope: NonEmptyRefundScope
    return_decision: AgentReturnDecision


class DeclineProposedDecision(ProposedDecisionBase):
    action: Literal["DECLINE"]
    amount: Annotated[Amount, WithJsonSchema({"type": "string", "pattern": r"^0(?:\.0+)?$"})]
    refund_scope: EmptyRefundScope

    @model_validator(mode="after")
    def zero_amount(self) -> Self:
        if self.amount != 0:
            raise ValueError("DECLINE must have zero amount")
        return self


ProposedDecision = Annotated[FullRefundProposedDecision | DeclineProposedDecision, Field(discriminator="action")]


class DraftBase(ContractModel):
    reason_code: ReasonCode
    policy_refs: Annotated[list[Ref], Field(min_length=1)]
    evidence_refs: list[Ref] = Field(default_factory=list)
    rationale_summary: Ref


class FullRefundProposedDecisionDraft(DraftBase):
    action: Literal["FULL_REFUND"]
    refund_scope: NonEmptyRefundScope
    return_decision: DraftReturnDecision


class DeclineProposedDecisionDraft(DraftBase):
    action: Literal["DECLINE"]
    refund_scope: EmptyRefundScope


ProposedDecisionDraft = Annotated[FullRefundProposedDecisionDraft | DeclineProposedDecisionDraft, Field(discriminator="action")]


class ProposedDecisionHandoff(ContractModel):
    handoff_id: Ref
    handoff_version: Literal["1.0"]
    case_ref: Ref
    agent_prompt_version: Ref
    claim_registry_version: Ref
    order_snapshot_ref: Ref
    policy_bundle_version: Ref
    policy_refs: Annotated[list[Ref], Field(min_length=1)]
    evidence_bundle: list[EvidenceItem] = Field(default_factory=list)
    proposed_decision: ProposedDecision
    rationale_summary: Ref
    revision_round: Annotated[int, Field(ge=0, strict=True)]

    @model_validator(mode="after")
    def references_exist(self) -> Self:
        refs = [e.evidence_id for e in self.evidence_bundle]
        unique(refs, "evidence ID")
        if not set(self.proposed_decision.evidence_refs) <= set(refs):
            raise ValueError("Decision cites evidence outside the handoff")
        if not set(self.proposed_decision.policy_refs) <= set(self.policy_refs):
            raise ValueError("Decision cites policy outside the handoff")
        return self


class RevisionReason(ContractModel):
    code: RevisionReasonCode
    subject: Ref
    message: Ref
    required_change: Ref
    policy_refs: list[Ref] = Field(default_factory=list)
    evidence_refs: list[Ref] = Field(default_factory=list)


class ReviewBase(ContractModel):
    reviewed_at: UTCDateTime
    reviewer_prompt_version: Ref
    reviewer_claim_findings: Annotated[list[ClaimFinding], Field(min_length=1)]


class ApprovedReviewResult(ReviewBase):
    verdict: Literal["APPROVE"]
    revision_reasons: Annotated[list[RevisionReason], Field(max_length=0)] = Field(default_factory=list)


class RevisedReviewResult(ReviewBase):
    verdict: Literal["REVISE"]
    revision_reasons: Annotated[list[RevisionReason], Field(min_length=1)]


ReviewResult = Annotated[ApprovedReviewResult | RevisedReviewResult, Field(discriminator="verdict")]


class VerificationIssue(ContractModel):
    code: Ref
    field_path: Ref
    message: Ref


class PassedVerificationResult(ContractModel):
    status: Literal["PASS"]
    verification_version: Ref
    issues: Annotated[list[VerificationIssue], Field(max_length=0)] = Field(default_factory=list)


class FailedVerificationResult(ContractModel):
    status: Literal["FAIL"]
    verification_version: Ref
    issues: Annotated[list[VerificationIssue], Field(min_length=1)]


class UnavailableVerificationResult(ContractModel):
    status: Literal["UNAVAILABLE"]
    verification_version: Ref
    issues: Annotated[list[VerificationIssue], Field(max_length=0)] = Field(default_factory=list)


VerificationResult = Annotated[PassedVerificationResult | FailedVerificationResult | UnavailableVerificationResult, Field(discriminator="status")]


class ReviewerGateConfig(ContractModel):
    version: Ref = "reviewer-gates:1.0"
    thresholds: dict[Currency, Amount] = Field(default_factory=lambda: {"TWD": "5000", "SGD": "200"}, validate_default=True)


class ReviewGateResult(ContractModel):
    config_version: Ref
    config_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    status: Literal["PASS", "HUMAN_REQUIRED", "NOT_APPLICABLE"]
    reason: Literal["HIGH_VALUE_ITEM", "CURRENCY_THRESHOLD_UNCONFIGURED"] | None
    amount: Amount
    currency: Currency
    threshold: Amount | None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        valid = (
            (self.status == "NOT_APPLICABLE" and self.amount == 0 and self.reason is None and self.threshold is None)
            or (self.status == "PASS" and self.reason is None and self.threshold is not None and self.amount <= self.threshold)
            or (self.status == "HUMAN_REQUIRED" and self.reason == "HIGH_VALUE_ITEM" and self.threshold is not None and self.amount > self.threshold)
            or (self.status == "HUMAN_REQUIRED" and self.reason == "CURRENCY_THRESHOLD_UNCONFIGURED" and self.threshold is None)
        )
        if not valid:
            raise ValueError("Gate fields contradict each other")
        return self


class DecisionRevisionEvent(ContractModel):
    event_id: Ref
    case_ref: Ref
    handoff_before_ref: Ref
    review_result: ReviewResult
    revision_round: Annotated[int, Field(ge=1, strict=True)]
    created_at: UTCDateTime


class HumanReviewDossier(ContractModel):
    claim_registry_version: Ref
    claimed_line_item_ids: Annotated[list[Ref], Field(min_length=1)]
    order_snapshot: OrderSnapshot
    policy_bundle: PolicyBundle
    proposal_history: Annotated[list[ProposedDecisionHandoff], Field(min_length=1)]
    review_history: Annotated[list[ReviewResult], Field(min_length=1)]
    revision_events: list[DecisionRevisionEvent] = Field(default_factory=list)
    review_gate: ReviewGateResult | None = None
    routing_reason: Literal["REVISION_BUDGET_EXCEEDED", "HIGH_VALUE_ITEM", "CURRENCY_THRESHOLD_UNCONFIGURED"] = "REVISION_BUDGET_EXCEEDED"


class CorrectedFullRefundDecision(ContractModel):
    action: Literal["FULL_REFUND"]
    refund_scope: NonEmptyRefundScope
    return_decision: HumanReviewReturnDecision


class CorrectedDeclineDecision(ContractModel):
    action: Literal["DECLINE"]
    refund_scope: EmptyRefundScope


CorrectedDecision = Annotated[CorrectedFullRefundDecision | CorrectedDeclineDecision, Field(discriminator="action")]


def refund_amount(snapshot: OrderSnapshot, items: list[str]) -> Amount:
    unique(items, "refund item")
    lines = {item.line_item_id: item for item in snapshot.line_items}
    if not set(items) <= lines.keys():
        raise ValueError("Unknown order item")
    amount = exact_total([lines[item].refundable_amount for item in items])
    if exact_total([amount, snapshot.already_refunded_amount]) > snapshot.refundable_amount_max:
        raise ValueError("Refund exceeds the trusted order maximum")
    return amount
