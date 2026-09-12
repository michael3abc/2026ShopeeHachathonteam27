from typing import Annotated, Literal

from pydantic import Field, WithJsonSchema, model_validator

from .domain import (
    AgentReturnDecision, ApprovedReviewResult, CorrectedDecision, EmptyRefundScope,
    HumanReviewReturnDecision, NonEmptyRefundScope, ReasonCode, ReviewGateResult, ReviewResult,
)
from .primitives import Amount, ContractModel, Currency, Ref, UTCDateTime

HumanCorrectionReasonCode = Literal["CLAIM_NOT_ESTABLISHED", "POLICY_MISAPPLIED", "SCOPE_INCORRECT", "RETURN_REQUIREMENT_INCORRECT", "OTHER"]


class ReviewDecisionBase(ContractModel):
    handoff_id: Ref | None = None
    reviewer_id: Ref = "demo_reviewer"
    review_note: Ref
    generalizable: bool | None = None


class ApproveReviewDecision(ReviewDecisionBase):
    decision: Literal["APPROVE"]


class RejectReviewDecision(ReviewDecisionBase):
    decision: Literal["REJECT"]


class EditReviewDecision(ReviewDecisionBase):
    decision: Literal["EDIT"]
    corrected_decision: CorrectedDecision
    correction_reason_code: HumanCorrectionReasonCode


ReviewDecision = Annotated[ApproveReviewDecision | RejectReviewDecision | EditReviewDecision, Field(discriminator="decision")]


class HumanResultBase(ContractModel):
    final_resolution_ref: Ref
    reviewed_at: UTCDateTime
    review_note: Ref
    reviewer_id: Ref = "demo_reviewer"
    generalizable: bool | None = None


class ApprovedHumanReviewResult(HumanResultBase):
    decision: Literal["APPROVE"]


class RejectedHumanReviewResult(HumanResultBase):
    decision: Literal["REJECT"]


class EditedHumanReviewResult(HumanResultBase):
    decision: Literal["EDIT"]
    corrected_decision: CorrectedDecision
    correction_reason_code: HumanCorrectionReasonCode


HumanReviewResult = Annotated[ApprovedHumanReviewResult | RejectedHumanReviewResult | EditedHumanReviewResult, Field(discriminator="decision")]


class FinalBase(ContractModel):
    amount: Amount
    currency: Currency
    reason_code: ReasonCode


class AgentFullRefundFinalDecision(FinalBase):
    action: Literal["FULL_REFUND"]
    refund_scope: NonEmptyRefundScope
    return_decision: AgentReturnDecision


class HumanEditedFullRefundFinalDecision(FinalBase):
    action: Literal["FULL_REFUND"]
    refund_scope: NonEmptyRefundScope
    return_decision: HumanReviewReturnDecision


class DeclineFinalDecision(FinalBase):
    action: Literal["DECLINE"]
    amount: Annotated[Amount, WithJsonSchema({"type": "string", "pattern": r"^0(?:\.0+)?$"})]
    refund_scope: EmptyRefundScope

    @model_validator(mode="after")
    def amount_is_zero(self):
        if self.amount != 0:
            raise ValueError("DECLINE final amount must be zero")
        return self


AgentFinalDecision = Annotated[AgentFullRefundFinalDecision | DeclineFinalDecision, Field(discriminator="action")]
HumanEditedFinalDecision = Annotated[HumanEditedFullRefundFinalDecision | DeclineFinalDecision, Field(discriminator="action")]


class ResolutionBase(ContractModel):
    handoff_id: Ref
    case_ref: Ref
    emitted_at: UTCDateTime
    execution_blocked: Literal[False]
    review_gate: ReviewGateResult | None = None


class ReviewerApprovedResolutionHandoff(ResolutionBase):
    outcome_source: Literal["REVIEWER_APPROVE"]
    final_decision: AgentFinalDecision
    review_result: ApprovedReviewResult


class HumanApproveResolutionHandoff(ResolutionBase):
    outcome_source: Literal["HUMAN_APPROVE"]
    final_decision: AgentFinalDecision
    review_result: ReviewResult


class HumanEditResolutionHandoff(ResolutionBase):
    outcome_source: Literal["HUMAN_EDIT"]
    final_decision: HumanEditedFinalDecision
    review_result: ReviewResult


class HumanRejectResolutionHandoff(ResolutionBase):
    outcome_source: Literal["HUMAN_REJECT"]
    final_decision: DeclineFinalDecision
    review_result: ReviewResult


ResolutionHandoff = Annotated[ReviewerApprovedResolutionHandoff | HumanApproveResolutionHandoff | HumanEditResolutionHandoff | HumanRejectResolutionHandoff, Field(discriminator="outcome_source")]
