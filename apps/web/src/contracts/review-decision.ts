/* Generated from apps/contracts. Do not edit manually. */

export type ReviewDecision = ApproveReviewDecision | EditReviewDecision | RejectReviewDecision;
export type Decision = "APPROVE";
export type Generalizable = boolean | null;
export type HandoffId = string | null;
export type ReviewNote = string;
export type ReviewerId = string;
export type CorrectedDecision = CorrectedFullRefundDecision | CorrectedDeclineDecision;
export type Action = "FULL_REFUND";
/**
 * @minItems 1
 */
export type LineItemIds = [string, ...string[]];
export type Requirement = RequiredReturnRequirement | WaivedReturnRequirement;
export type RequiredReturnReasonCode = "RESALE_VALUE_RETAINED" | "RETURN_REQUIRED_FOR_INSPECTION";
export type Required = true;
export type WaivedReturnReasonCode =
  "ITEM_UNSALVAGEABLE" | "HYGIENE_RISK" | "RETURN_UNECONOMICAL" | "EVIDENCE_SUFFICIENT_WITHOUT_RETURN";
export type Required1 = false;
export type Source = "HUMAN_REVIEW";
export type Action1 = "DECLINE";
/**
 * @maxItems 0
 */
export type LineItemIds1 = [];
export type HumanCorrectionReasonCode =
  "CLAIM_NOT_ESTABLISHED" | "POLICY_MISAPPLIED" | "SCOPE_INCORRECT" | "RETURN_REQUIREMENT_INCORRECT" | "OTHER";
export type Decision1 = "EDIT";
export type Generalizable1 = boolean | null;
export type HandoffId1 = string | null;
export type ReviewNote1 = string;
export type ReviewerId1 = string;
export type Decision2 = "REJECT";
export type Generalizable2 = boolean | null;
export type HandoffId2 = string | null;
export type ReviewNote2 = string;
export type ReviewerId2 = string;

export interface ApproveReviewDecision {
  decision: Decision;
  generalizable?: Generalizable;
  handoff_id?: HandoffId;
  review_note: ReviewNote;
  reviewer_id?: ReviewerId;
}
export interface EditReviewDecision {
  corrected_decision: CorrectedDecision;
  correction_reason_code: HumanCorrectionReasonCode;
  decision: Decision1;
  generalizable?: Generalizable1;
  handoff_id?: HandoffId1;
  review_note: ReviewNote1;
  reviewer_id?: ReviewerId1;
}
export interface CorrectedFullRefundDecision {
  action: Action;
  refund_scope: NonEmptyRefundScope;
  return_decision: HumanReviewReturnDecision;
}
export interface NonEmptyRefundScope {
  line_item_ids: LineItemIds;
}
export interface HumanReviewReturnDecision {
  requirement: Requirement;
  source: Source;
}
export interface RequiredReturnRequirement {
  reason_code: RequiredReturnReasonCode;
  required: Required;
}
export interface WaivedReturnRequirement {
  reason_code: WaivedReturnReasonCode;
  required: Required1;
}
export interface CorrectedDeclineDecision {
  action: Action1;
  refund_scope: EmptyRefundScope;
}
export interface EmptyRefundScope {
  line_item_ids?: LineItemIds1;
}
export interface RejectReviewDecision {
  decision: Decision2;
  generalizable?: Generalizable2;
  handoff_id?: HandoffId2;
  review_note: ReviewNote2;
  reviewer_id?: ReviewerId2;
}
