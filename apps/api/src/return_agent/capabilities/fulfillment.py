"""Durable API authorization and return fulfillment, independent of graph life."""
from __future__ import annotations
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import os
from uuid import uuid4
from pydantic import TypeAdapter
from sqlalchemy import select, or_
from return_agent_contracts.models import (CaseContextLoadResult, ExecuteRefundRequest, ProposedDecisionHandoff,
    ResolutionHandoff, HumanReviewDossier, ReviewResult, PolicyBundle)
from return_agent_contracts.enums import ResolutionAction, OutcomeSource
from return_agent_contracts.policy_v2 import PolicyEvaluation, PolicyConfirmation, content_hash, evaluate_policy
from return_agent_contracts.fulfillment import FulfillmentProjection, ReturnEventReceipt, ReturnFulfillmentEvent
from return_agent_contracts.review_gates import evaluate_review_gate
from return_agent_contracts.user_risk import evaluate_user_risk
from return_agent_contracts.validation import validate_proposed_decision_handoff, validate_human_review_entry
from return_agent_contracts.ui import CaseStatus
from return_agent_contracts.runtime import GraphNodeName
from return_agent.db.models import (PolicyEvaluationRecord, PolicyConfirmationRecord, ReturnAuthorizationRecord,
    ReturnReceiptRecord, RefundExecutionRecord, RefundItemReservation, HandoffVerificationRecord,
    PolicyRetrievalRecord, UserRiskSnapshotRecord, HumanReviewRecord)
from return_agent.db.case import CaseRecord, append_agent_event
from return_agent.store import CaseStore
from .user_risk import utc, SqlAlchemyUserRiskProvider

RESOLUTION = TypeAdapter(ResolutionHandoff)
RETURN_EVENT = TypeAdapter(ReturnFulfillmentEvent)


def save_evaluation(session, evaluation: PolicyEvaluation):
    from return_agent.db.models import PolicySelectionRecord
    selection = session.get(PolicySelectionRecord,(evaluation.case_ref,evaluation.selection.selection_version))
    raw_selection = evaluation.selection.model_dump(mode="json")
    if selection is None:
        session.add(PolicySelectionRecord(case_ref=evaluation.case_ref,
            selection_version=evaluation.selection.selection_version,payload=raw_selection))
    elif selection.payload != raw_selection:
        raise ValueError("immutable policy selection changed")
    payload = evaluation.model_dump(mode="json")
    record = session.get(PolicyEvaluationRecord,evaluation.evaluation_ref)
    if record is not None:
        if record.payload != payload or record.case_ref != evaluation.case_ref:
            raise ValueError("immutable evaluation changed")
    else:
        session.add(PolicyEvaluationRecord(evaluation_ref=evaluation.evaluation_ref,case_ref=evaluation.case_ref,payload=payload))


def transition(session, record: ReturnAuthorizationRecord, target: str, reason: str):
    store = CaseStore(session)
    case = store.lock(record.case_ref)
    before = CaseStatus(case.status)
    if before.value != target:
        store.transition(case.case_ref,CaseStatus(target))
        append_agent_event(session,case.case_ref,dict(type="state_change",ts=datetime.now(UTC),node=GraphNodeName.EMIT_RESOLUTION_HANDOFF,
            payload=dict(from_status=before,to_status=target,reason=reason)))
    record.state = target
    if target in {"RESOLVED","ESCALATED"} and before.value != target:
        append_agent_event(session,case.case_ref,dict(type="done",ts=datetime.now(UTC),node=GraphNodeName.EMIT_RESOLUTION_HANDOFF,
            payload=dict(terminal_ref=record.authorization_ref,status=target)))


def fulfillment_projection(record: ReturnAuthorizationRecord) -> FulfillmentProjection:
    resolution = RESOLUTION.validate_python(record.payload["resolution"])
    required = resolution.final_decision.return_decision.requirement.required
    payment = "NOT_STARTED"
    if record.execution_result:
        payment = record.execution_result["status"]
    elif record.state == "EXECUTING":
        payment = "IN_PROGRESS"
    return FulfillmentProjection(authorization_ref=record.authorization_ref,selected_path_id=resolution.policy_evaluation.selection.selected_path_id,
        state=record.state,return_required=required,return_requirement_hash=record.payload["requirement_hash"],
        refund_release_condition="RETURN_INSPECTION_PASSED" if required else "AUTHORIZED_NO_RETURN",payment_status=payment,
        arrived_event_id=record.arrived_event_id,inspection_event_id=record.inspection_event_id,reason=record.reason)


def register_authorization(session, case: CaseRecord, resolution, executor):
    from .refund import SqlAlchemyRefundExecutionRepository, _execution_ref, _canonical_hash
    if executor is None or case.policy_schema_version != "v2":
        raise ValueError("v2 fulfillment requires an executor and a pinned v2 case")
    context = CaseContextLoadResult.model_validate(case.v2_context_payload)
    verification = session.scalar(select(HandoffVerificationRecord).where(HandoffVerificationRecord.handoff_id == resolution.handoff_id))
    if verification is None or verification.verification_status != "PASS":
        raise ValueError("verified proposal is required")
    handoff = ProposedDecisionHandoff.model_validate(verification.handoff_payload)
    if content_hash(handoff) != verification.payload_hash:
        raise ValueError("verified proposal content changed")
    bundle_record = session.scalar(select(PolicyRetrievalRecord).where(PolicyRetrievalRecord.bundle_version == handoff.policy_bundle_version))
    if bundle_record is None:
        raise ValueError("exact policy bundle is unavailable")
    bundle = PolicyBundle.model_validate(bundle_record.bundle_payload)
    validate_proposed_decision_handoff(handoff,bundle,context.order_snapshot)
    if handoff.handoff_version != "2.0" or handoff.case_ref != case.case_ref or resolution.case_ref != case.case_ref:
        raise ValueError("fulfillment case or policy version mismatch")
    original_scope = sorted({x.line_item_id for x in handoff.policy_evaluation.item_evaluations})
    decision = resolution.final_decision
    if decision.action is not ResolutionAction.FULL_REFUND or not set(decision.refund_scope.line_item_ids).issubset(x.line_item_id for x in context.order_snapshot.line_items):
        raise ValueError("invalid fulfillment scope")
    if len(original_scope) != 1 or decision.refund_scope.line_item_ids != original_scope:
        raise ValueError("v2 authorization requires the single original item")
    expected_amount = sum(x.refundable_amount for x in context.order_snapshot.line_items if x.line_item_id in decision.refund_scope.line_item_ids)
    if decision.amount != expected_amount or decision.currency != context.order_snapshot.currency:
        raise ValueError("fulfillment amount must come from the pinned order")
    evaluation = resolution.policy_evaluation
    if evaluation is None:
        raise ValueError("reviewer policy evaluation is required")
    human = session.scalar(select(HumanReviewRecord).where(HumanReviewRecord.handoff_id == handoff.handoff_id))
    if resolution.outcome_source is OutcomeSource.REVIEWER_APPROVE:
        if decision.action != handoff.proposed_decision.action or decision.refund_scope != handoff.proposed_decision.refund_scope or decision.return_decision != handoff.proposed_decision.return_decision:
            raise ValueError("machine resolution changed the reviewed proposal")
        expected = evaluate_policy(context=context.case_context,order=context.order_snapshot,bundle=bundle,
            claimed_line_item_ids=original_scope,findings=resolution.review_result.reviewer_claim_findings,
            evidence=handoff.evidence_bundle,selection=handoff.policy_selection,evaluated_at=evaluation.evaluated_at)
        if evaluation != expected or any(x.status != "ELIGIBLE" for x in evaluation.item_evaluations if x.path_id is handoff.policy_selection.selected_path_id):
            raise ValueError("reviewer evaluation does not establish eligibility")
        gate = evaluate_review_gate(decision.action,decision.amount,decision.currency,executor._reviewer_gate_config)
        if resolution.review_gate != gate or gate.status != "PASS":
            raise ValueError("monetary authorization is invalid")
        risk = resolution.user_risk_gate
        snapshot_record = session.get(UserRiskSnapshotRecord,risk.snapshot_ref) if risk and risk.snapshot_ref else None
        if snapshot_record is None:
            raise ValueError("risk snapshot is missing")
        snapshot = SqlAlchemyUserRiskProvider._snapshot(snapshot_record)
        expected_risk = evaluate_user_risk(decision.action,snapshot,executor._user_risk_config)
        if snapshot.case_ref != case.case_ref or snapshot.user_ref != case.user_ref or snapshot.reason_code != decision.reason_code or snapshot.as_of != context.case_context.case_opened_at or risk != expected_risk or risk.status != "PASS":
            raise ValueError("risk authorization is invalid")
    else:
        if human is None or human.result_payload is None or human.dossier_payload is None:
            raise ValueError("persisted human authorization is required")
        dossier = HumanReviewDossier.model_validate(human.dossier_payload)
        validate_human_review_entry(handoff,TypeAdapter(ReviewResult).validate_python(human.review_payload),dossier,executor._reviewer_gate_config,executor._user_risk_config)
        if resolution.user_risk_gate != dossier.user_risk_gate or not executor._matches_human_authorization(resolution,executor._repository.load_authorization(handoff.handoff_id)):
            raise ValueError("human authorization binding mismatch")
        if human.result_payload.get("policy_evaluation") != evaluation.model_dump(mode="json"):
            raise ValueError("human policy evaluation binding mismatch")
    save_evaluation(session,evaluation)
    required = decision.return_decision.requirement.required
    expected_release = "RETURN_INSPECTION_PASSED" if required else "AUTHORIZED_NO_RETURN"
    if resolution.refund_release_condition != expected_release:
        raise ValueError("refund release condition mismatches return decision")
    ref = f"authorization:{resolution.handoff_id}"
    payload = dict(resolution=resolution.model_dump(mode="json"),context=context.model_dump(mode="json"),
        proposal=handoff.model_dump(mode="json"),policy_bundle=bundle.model_dump(mode="json"),
        requirement_hash=content_hash(decision.return_decision.requirement),scope_hash=content_hash(decision.refund_scope),
        monetary_config_hash=executor._reviewer_gate_config.fingerprint,risk_config_hash=executor._user_risk_config.fingerprint,
        human_authorization_hash=human.payload_hash if human else None)
    existing = session.get(ReturnAuthorizationRecord,ref)
    if existing is not None:
        if existing.payload_hash != content_hash(payload):
            raise ValueError("fulfillment authorization changed")
        return existing
    now = datetime.now(UTC)
    request = ExecuteRefundRequest(resolution_handoff=resolution)
    execution_ref = _execution_ref(resolution.handoff_id)
    SqlAlchemyRefundExecutionRepository._insert_do_nothing(session,RefundExecutionRecord,dict(
        execution_ref=execution_ref,handoff_id=resolution.handoff_id,case_ref=case.case_ref,
        payload_hash=_canonical_hash(request.model_dump(mode="json")),request_payload=request.model_dump(mode="json"),
        order_ref=case.order_ref,state="IN_PROGRESS",created_at=now,updated_at=now,application_started_at=None,
        application_result_payload=None,completed_at=None))
    ledger = session.get(RefundExecutionRecord, execution_ref)
    if ledger is None or ledger.payload_hash != _canonical_hash(request.model_dump(mode="json")) or ledger.state != "IN_PROGRESS" or ledger.application_started_at is not None:
        raise ValueError("fulfillment execution identity is already used")
    for item in sorted(decision.refund_scope.line_item_ids):
        SqlAlchemyRefundExecutionRepository._insert_do_nothing(session,RefundItemReservation,dict(
            order_ref=case.order_ref,line_item_ref=item,execution_ref=execution_ref,reserved_at=now))
        reservation = session.get(RefundItemReservation,(case.order_ref,item))
        if reservation is None or reservation.execution_ref != execution_ref:
            raise ValueError("item is reserved by another authorization")
    confirmation = handoff.policy_confirmation
    consent = None
    if confirmation is not None and confirmation.accepted and confirmation.request.return_requirement_hash == payload["requirement_hash"]:
        canonical = session.get(PolicyConfirmationRecord,confirmation.request.request_ref)
        if canonical is None or canonical.response_payload != confirmation.model_dump(mode="json"):
            raise ValueError("buyer consent is not persisted")
        consent = confirmation.model_dump(mode="json")
    target = "EXECUTING" if not required else "AWAITING_RETURN" if consent else "AWAITING_RETURN_CONFIRMATION"
    record = ReturnAuthorizationRecord(authorization_ref=ref,case_ref=case.case_ref,execution_ref=execution_ref,
        payload=payload,payload_hash=content_hash(payload),state=target,confirmation_payload=consent,created_at=now)
    session.add(record)
    transition(session,record,target,"審核已完成；等待退回履約。" if required else "免退授權已確認；準備執行退款。")
    return record


def check_release(session, resolution, monetary_config, risk_config):
    record = session.scalar(select(ReturnAuthorizationRecord).where(ReturnAuthorizationRecord.case_ref == resolution.case_ref))
    if record is None or record.payload_hash != content_hash(record.payload) or record.payload["resolution"] != resolution.model_dump(mode="json"):
        raise ValueError("fulfillment authorization is missing or invalid")
    if record.payload["monetary_config_hash"] != monetary_config.fingerprint or record.payload["risk_config_hash"] != risk_config.fingerprint:
        raise ValueError("AUTHORIZATION_CONFIG_CHANGED")
    if record.state != "EXECUTING":
        raise ValueError("RETURN_FULFILLMENT_PENDING")
    required = resolution.final_decision.return_decision.requirement.required
    if required:
        if record.confirmation_payload is None or record.arrived_event_id is None or record.inspection_event_id is None:
            raise ValueError("RETURN_FULFILLMENT_PENDING")
        receipt = session.scalar(select(ReturnReceiptRecord).where(ReturnReceiptRecord.authorization_ref == record.authorization_ref,ReturnReceiptRecord.event_id == record.inspection_event_id))
        if receipt is None:
            raise ValueError("inspection receipt missing")
        event = RETURN_EVENT.validate_python(receipt.event_payload)
        scope = resolution.final_decision.refund_scope.line_item_ids
        if len(scope) != 1 or event.line_item_id != scope[0] or event.case_ref != resolution.case_ref or event.authorization_ref != record.authorization_ref or event.event_type != "INSPECTION_PASSED" or event.payload.arrived_event_id != record.arrived_event_id:
            raise ValueError("inspection binding mismatch")
        consent = record.confirmation_payload
        if "input" in consent:
            raw = consent["input"]
            if not raw["accept"] or raw["authorization_ref"] != record.authorization_ref or raw["return_requirement_hash"] != record.payload["requirement_hash"]:
                raise ValueError("return consent binding mismatch")
        else:
            confirmation = PolicyConfirmation.model_validate(consent)
            canonical = session.get(PolicyConfirmationRecord, confirmation.request.request_ref)
            if not confirmation.accepted or canonical is None or canonical.response_payload != consent or confirmation.request.return_requirement_hash != record.payload["requirement_hash"]:
                raise ValueError("policy consent binding mismatch")
    for item in resolution.final_decision.refund_scope.line_item_ids:
        reservation = session.get(RefundItemReservation,(record.payload["context"]["case_context"]["order_ref"],item))
        if reservation is None or reservation.execution_ref != record.execution_ref:
            raise ValueError("fulfillment reservation ownership changed")


def accept_return_event(session, event):
    previous = session.scalar(select(ReturnReceiptRecord).where(ReturnReceiptRecord.producer_id == event.producer_id,ReturnReceiptRecord.event_id == event.event_id))
    raw = event.model_dump(mode="json")
    if previous is not None:
        if previous.event_payload != raw:
            raise ValueError("return event identity reused with different content")
        return ReturnEventReceipt.model_validate(previous.receipt_payload)
    record = session.scalar(select(ReturnAuthorizationRecord).where(ReturnAuthorizationRecord.authorization_ref == event.authorization_ref).with_for_update())
    if record is None or record.case_ref != event.case_ref or record.payload_hash != content_hash(record.payload):
        raise ValueError("return event authorization mismatch")
    # Recheck after the lock: an identical concurrent delivery may have committed.
    previous = session.scalar(select(ReturnReceiptRecord).where(ReturnReceiptRecord.producer_id == event.producer_id,ReturnReceiptRecord.event_id == event.event_id))
    if previous is not None:
        if previous.event_payload != raw:
            raise ValueError("return event identity reused with different content")
        return ReturnEventReceipt.model_validate(previous.receipt_payload)
    if session.scalar(select(ReturnReceiptRecord).where(ReturnReceiptRecord.authorization_ref == event.authorization_ref,ReturnReceiptRecord.event_id == event.event_id)):
        raise ValueError("return event reference is already used in this authorization")
    resolution = RESOLUTION.validate_python(record.payload["resolution"])
    if event.line_item_id not in resolution.final_decision.refund_scope.line_item_ids or event.occurred_at < utc(record.created_at):
        raise ValueError("return event item or timestamp mismatch")
    if event.event_type == "RETURN_ARRIVED":
        if record.state != "AWAITING_RETURN" or record.arrived_event_id is not None:
            raise ValueError("arrival is out of order")
        record.arrived_event_id = event.event_id
        target = "AWAITING_RETURN_INSPECTION"
    elif event.event_type in {"INSPECTION_PASSED","INSPECTION_DISPUTED"}:
        arrived = session.scalar(select(ReturnReceiptRecord).where(ReturnReceiptRecord.authorization_ref == record.authorization_ref,ReturnReceiptRecord.event_id == event.payload.arrived_event_id))
        if record.state != "AWAITING_RETURN_INSPECTION" or event.payload.arrived_event_id != record.arrived_event_id or arrived is None or event.occurred_at < RETURN_EVENT.validate_python(arrived.event_payload).occurred_at:
            raise ValueError("inspection must follow the accepted arrival")
        arrival = RETURN_EVENT.validate_python(arrived.event_payload)
        if arrival.event_type != "RETURN_ARRIVED" or arrival.line_item_id != event.line_item_id or arrival.case_ref != event.case_ref:
            raise ValueError("inspection arrival item binding mismatch")
        record.inspection_event_id = event.event_id
        target = "EXECUTING" if event.event_type == "INSPECTION_PASSED" else "ESCALATED"
    else:
        if record.state not in {"AWAITING_RETURN","AWAITING_RETURN_INSPECTION"}:
            raise ValueError("return overdue event is out of order")
        target = "ESCALATED"
    if target == "ESCALATED":
        record.reason = event.event_type
    transition(session,record,target,"退回驗收已確認；準備執行退款。" if target == "EXECUTING" else "退回進度已更新；尚未退款。")
    receipt = ReturnEventReceipt(receipt_ref=f"return-receipt:{content_hash([event.producer_id,event.event_id])}",
        event_id=event.event_id,producer_id=event.producer_id,authorization_ref=record.authorization_ref,accepted_at=datetime.now(UTC),state=target)
    session.add(ReturnReceiptRecord(receipt_ref=receipt.receipt_ref,producer_id=event.producer_id,event_id=event.event_id,
        authorization_ref=record.authorization_ref,event_payload=raw,receipt_payload=receipt.model_dump(mode="json")))
    return receipt


class FulfillmentWorker:
    def __init__(self,sessions,executor,owner=None,lease_seconds=None):
        self.sessions,self.executor = sessions,executor
        self.owner = owner or uuid4().hex
        self.lease_seconds = lease_seconds or int(os.environ.get("RETURN_AGENT_FULFILLMENT_LEASE_SECONDS","120"))

    def run_once(self):
        if self.executor is None:
            return False
        now = datetime.now(UTC)
        with self.sessions.begin() as session:
            record = session.scalar(select(ReturnAuthorizationRecord).where(ReturnAuthorizationRecord.state == "EXECUTING",
                or_(ReturnAuthorizationRecord.lease_until.is_(None),ReturnAuthorizationRecord.lease_until <= now)).order_by(ReturnAuthorizationRecord.created_at).with_for_update(skip_locked=True).limit(1))
            if record is None:
                return False
            record.lease_owner,record.lease_until = self.owner,now+timedelta(seconds=self.lease_seconds)
            ref = record.authorization_ref
            resolution = RESOLUTION.validate_python(record.payload["resolution"])
        # Unknown application results retain this lease and the existing execution key.
        result = self.executor.execute(ExecuteRefundRequest(resolution_handoff=resolution))
        with self.sessions.begin() as session:
            record = session.scalar(select(ReturnAuthorizationRecord).where(ReturnAuthorizationRecord.authorization_ref == ref).with_for_update())
            if record.state != "EXECUTING" or record.lease_owner != self.owner:
                return True
            record.execution_result = result.model_dump(mode="json")
            target = "RESOLVED" if result.status.value == "SUCCEEDED" else "ESCALATED"
            record.reason = None if target == "RESOLVED" else "REFUND_AUTHORIZATION_REJECTED"
            transition(session,record,target,"退款已完成。" if target == "RESOLVED" else "退款未執行，案件交由專責處理。")
            record.lease_owner,record.lease_until = None,None
        return True
