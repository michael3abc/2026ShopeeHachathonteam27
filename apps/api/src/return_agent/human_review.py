from decimal import Decimal

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from return_agent_contracts.domain import ProposedDecisionHandoff, refund_amount
from return_agent_contracts.human import AgentFinalDecision, HumanEditedFinalDecision, HumanReviewResult, ReviewDecision
from return_agent_contracts.messages import AgentResumeCommand, AgentResumePayload, HumanReviewPollResume
from return_agent_contracts.providers import SubmitHumanReviewParams
from return_agent_contracts.public import CaseDetail
from return_agent_contracts.validation import allowed_actions, validate_dossier, validate_human_decision, validate_return

from .capabilities import CapabilityStore
from .cases import CaseStateConflict
from .db import HumanReviewRow


def proposal_final(handoff: ProposedDecisionHandoff):
    values = handoff.proposed_decision.model_dump(mode="python", exclude={"policy_refs", "evidence_refs"})
    return TypeAdapter(AgentFinalDecision).validate_python(values)


def authorized_human_final(capabilities: CapabilityStore, session: Session, submission: SubmitHumanReviewParams, result: HumanReviewResult):
    """Recheck saved authorization with the current order cap and original policy."""
    handoff, dossier = submission.handoff, submission.dossier
    if dossier is None:
        raise ValueError("Missing human dossier")
    trusted = capabilities.context(session, handoff.case_ref)
    policy, retrieval = capabilities.persisted_policy(session, handoff)
    if dossier.policy_bundle != policy or dossier.claimed_line_item_ids != retrieval.claimed_line_item_ids:
        raise ValueError("Human dossier differs from persisted policy retrieval")
    validate_dossier(dossier, handoff, submission.review, retrieval.case_context, capabilities.gates)
    current, original = trusted.order_snapshot, handoff.proposed_decision
    if current.order_ref != dossier.order_snapshot.order_ref or current.currency != dossier.order_snapshot.currency:
        raise ValueError("Human authorization cannot change order or currency")
    if result.decision == "EDIT":
        validate_human_decision(result.corrected_decision, dossier, current, policy)
        values = result.corrected_decision.model_dump(mode="python")
        values.update(amount=refund_amount(current, result.corrected_decision.refund_scope.line_item_ids), currency=current.currency, reason_code=original.reason_code)
        return TypeAdapter(HumanEditedFinalDecision).validate_python(values)
    if result.decision == "REJECT":
        if "DECLINE" not in allowed_actions(policy):
            raise ValueError("Policy does not permit decline")
        return TypeAdapter(AgentFinalDecision).validate_python({"action": "DECLINE", "amount": Decimal("0"), "currency": current.currency, "reason_code": original.reason_code, "refund_scope": {"line_item_ids": []}})
    if original.amount != refund_amount(current, original.refund_scope.line_item_ids):
        raise ValueError("Approved proposal differs from the current refundable amount")
    if original.action not in allowed_actions(policy):
        raise ValueError("Policy does not permit approval")
    if original.action == "FULL_REFUND":
        validate_return(original.return_decision, policy)
    return proposal_final(handoff)


class HumanReviewService:
    def __init__(self, capabilities: CapabilityStore):
        self.capabilities, self.cases = capabilities, capabilities.cases

    def complete(self, case_ref: str, decision: ReviewDecision) -> CaseDetail:
        decision = TypeAdapter(ReviewDecision).validate_python(decision)
        with self.cases.sessions.begin() as session:
            case = self.cases.locked_case(session, case_ref)
            if case.status != "AWAITING_HUMAN_REVIEW" or not case.human_review:
                raise CaseStateConflict("Case has no pending human review")
            handoff_id = case.human_review["handoff_id"]
            if decision.handoff_id is not None and decision.handoff_id != handoff_id:
                raise CaseStateConflict("Human review handoff is stale")
            row = session.scalar(select(HumanReviewRow).where(HumanReviewRow.case_ref == case_ref, HumanReviewRow.handoff_id == handoff_id).with_for_update())
            if row is None or row.result is not None:
                raise CaseStateConflict("Human review is missing or already completed")
            submission = SubmitHumanReviewParams.model_validate(row.request)
            values = decision.model_dump(mode="python", exclude={"handoff_id"})
            values.update(final_resolution_ref=self.cases.ids("resolution"), reviewed_at=self.cases.clock())
            result = TypeAdapter(HumanReviewResult).validate_python(values)
            try:
                authorized_human_final(self.capabilities, session, submission, result)
            except ValueError as exc:
                raise CaseStateConflict("Human decision failed the scope, policy or authorization checks") from exc
            row.result = result.model_dump(mode="json")
            case.human_review_result = row.result
            case.human_review = None
            self.cases.transition(session, case, "OBSERVING", "Human decision accepted", "await_human_review")
            self.cases.enqueue(session, AgentResumeCommand(command_type="RESUME", command_id=self.cases.ids("command"), case_ref=case_ref, thread_id=case.thread_id, issued_at=self.cases.clock(), payload=AgentResumePayload(resume=HumanReviewPollResume(kind="HUMAN_REVIEW"))))
        return self.cases.detail(case_ref)
