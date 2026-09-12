"""Simulated refunds with independently checked authority and durable item ownership."""
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from pydantic import TypeAdapter
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from return_agent_contracts.domain import ProposedDecisionHandoff
from return_agent_contracts.gates import evaluate_gate
from return_agent_contracts.human import HumanReviewResult
from return_agent_contracts.primitives import exact_total, payload_hash
from return_agent_contracts.providers import AppliedRefundApplicationResult, ApplyRefundRequest, ContractConflict, ExecuteRefundRequest, ProviderUnavailable, RefundApplicationProvider, RefundApplicationResult, RefundExecutionRecord, RejectedRefundApplicationResult, SubmitHumanReviewParams
from return_agent_contracts.validation import validate_review

from .capabilities import CapabilityStore, lock_identifier
from .db import CaseRow, HumanReviewRow, MockRefundReceiptRow, RefundExecutionRow, RefundItemRow, RefundReservationRow, TrustedOrderRow, VerificationRow
from .human_review import authorized_human_final, proposal_final


class AuthorizationRejected(ValueError):
    pass


class ReservationConflict(ValueError):
    pass


class SimulatedRefundApplication:
    """Durable fake money boundary; the receipt commits before returning to its caller."""
    def __init__(self, capabilities: CapabilityStore):
        self.capabilities = capabilities

    def apply(self, request: ApplyRefundRequest) -> RefundApplicationResult:
        with self.capabilities.sessions.begin() as session:
            lock_identifier(session, "mock-application", request.execution_ref)
            digest = payload_hash(request)
            receipt = session.get(MockRefundReceiptRow, request.execution_ref)
            if receipt:
                if receipt.payload_hash != digest:
                    raise ContractConflict("Application key reused with different content")
                return TypeAdapter(RefundApplicationResult).validate_python(receipt.result)
            result = AppliedRefundApplicationResult(status="APPLIED", application_ref=self.capabilities.cases.ids("simulated-payment"), applied_at=self.capabilities.cases.clock())
            session.add(MockRefundReceiptRow(execution_ref=request.execution_ref, payload_hash=digest, result=result.model_dump(mode="json")))
            return result


class RefundService:
    def __init__(self, capabilities: CapabilityStore, application: RefundApplicationProvider):
        self.capabilities, self.application = capabilities, application
        self.cases, self.sessions = capabilities.cases, capabilities.sessions

    def authorize(self, session: Session, request: ExecuteRefundRequest):
        resolution = request.resolution_handoff
        record = session.get(VerificationRow, resolution.handoff_id)
        if record is None or record.case_ref != resolution.case_ref or record.result["status"] != "PASS":
            raise AuthorizationRejected("Persisted PASS verification is required")
        proposal = ProposedDecisionHandoff.model_validate(record.handoff)
        if record.payload_hash != payload_hash(proposal):
            raise AuthorizationRejected("Verification payload integrity failed")
        try:
            if resolution.outcome_source == "REVIEWER_APPROVE":
                trusted, policy, retrieval = self.capabilities.validate_trusted_handoff(session, proposal)
                validate_review(resolution.review_result, proposal, trusted.order_snapshot, policy, retrieval.claimed_line_item_ids)
                expected = proposal_final(proposal)
                gate = evaluate_gate(expected.action, expected.amount, expected.currency, self.capabilities.gates)
                if gate.status == "HUMAN_REQUIRED" or gate != resolution.review_gate:
                    raise ValueError("Current gate does not permit automatic execution")
                existing_human = session.scalar(select(HumanReviewRow).where(HumanReviewRow.handoff_id == resolution.handoff_id))
                if existing_human is not None:
                    raise ValueError("Human handoff cannot be bypassed with automatic approval")
            else:
                human = session.scalar(select(HumanReviewRow).where(HumanReviewRow.handoff_id == resolution.handoff_id, HumanReviewRow.case_ref == resolution.case_ref))
                if human is None or human.result is None:
                    raise ValueError("Persisted human authorization is required")
                submission = SubmitHumanReviewParams.model_validate(human.request)
                result = TypeAdapter(HumanReviewResult).validate_python(human.result)
                case = session.get(CaseRow, resolution.case_ref)
                if human.payload_hash != payload_hash(submission) or submission.handoff != proposal or submission.review != resolution.review_result or case.human_review_result != human.result:
                    raise ValueError("Human authorization differs from the canonical result")
                if resolution.outcome_source != "HUMAN_" + result.decision or resolution.review_gate != submission.dossier.review_gate:
                    raise ValueError("Human outcome or gate does not match its authorization")
                expected = authorized_human_final(self.capabilities, session, submission, result)
                trusted = self.capabilities.context(session, resolution.case_ref)
            if expected != resolution.final_decision:
                raise ValueError("Final decision differs from its authorized proposal")
        except ValueError as exc:
            raise AuthorizationRejected("Refund authorization failed") from exc
        return trusted.order_snapshot

    def record(self, row: RefundExecutionRow) -> RefundExecutionRecord | None:
        if row.status == "IN_PROGRESS":
            return None
        return TypeAdapter(RefundExecutionRecord).validate_python({"execution_ref": row.execution_ref, "case_ref": row.case_ref, "handoff_id": row.handoff_id, "status": row.status, "created_at": row.created_at, "updated_at": row.updated_at, "application_result": row.application_result})

    def get_status(self, execution_ref: str) -> RefundExecutionRecord | None:
        with self.sessions() as session:
            row = session.get(RefundExecutionRow, execution_ref)
            return self.record(row) if row else None

    def owned_items(self, session: Session, row: RefundExecutionRow, scope: list[str]) -> None:
        owners = list(session.scalars(select(RefundReservationRow).where(RefundReservationRow.execution_ref == row.execution_ref)))
        if {(owner.order_ref, owner.line_item_ref) for owner in owners} != {(row.order_ref, item) for item in scope}:
            raise ProviderUnavailable("Attempted application lost reservation integrity")

    def execute(self, request: ExecuteRefundRequest) -> RefundExecutionRecord:
        request = ExecuteRefundRequest.model_validate(request)
        resolution = request.resolution_handoff
        if resolution.final_decision.action != "FULL_REFUND":
            raise AuthorizationRejected("Decline decisions do not invoke payment")
        execution_ref = "EXECUTION-" + uuid5(NAMESPACE_URL, resolution.handoff_id).hex
        digest, scope = payload_hash(request), resolution.final_decision.refund_scope.line_item_ids
        with self.sessions.begin() as session:
            lock_identifier(session, "refund-execution", execution_ref)
            row = session.get(RefundExecutionRow, execution_ref)
            if row and (row.payload_hash != digest or row.request != request.model_dump(mode="json")):
                raise ContractConflict("Execution key reused with different content")
            if row and row.status != "IN_PROGRESS":
                return self.record(row)
            case = session.get(CaseRow, resolution.case_ref)
            if case is None:
                raise AuthorizationRejected("Unknown canonical case")
            # Serialize aggregate reservations per order, across all cases and items.
            order_row = session.scalar(select(TrustedOrderRow).where(TrustedOrderRow.order_ref == case.order_ref).with_for_update())
            if order_row is None:
                raise AuthorizationRejected("Trusted order is missing")
            snapshot = self.authorize(session, request)
            now = self.cases.clock()
            if row is None:
                row = RefundExecutionRow(execution_ref=execution_ref, handoff_id=resolution.handoff_id, case_ref=resolution.case_ref, order_ref=case.order_ref, payload_hash=digest, request=request.model_dump(mode="json"), status="IN_PROGRESS", created_at=now, updated_at=now)
                session.add(row)
                session.flush()
            if row.application_started_at is not None:
                self.owned_items(session, row, scope)
            else:
                try:
                    with session.begin_nested():
                        reservations = list(session.scalars(select(RefundReservationRow).where(RefundReservationRow.order_ref == snapshot.order_ref)))
                        existing = {item.line_item_ref: item for item in reservations}
                        amounts = {item.line_item_id: item.refundable_amount for item in snapshot.line_items}
                        for item in scope:
                            if item in existing and existing[item].execution_ref != execution_ref:
                                raise ReservationConflict("An item already has a refund owner")
                            if item not in existing:
                                session.add(RefundReservationRow(order_ref=snapshot.order_ref, line_item_ref=item, execution_ref=execution_ref, amount=str(amounts[item])))
                        reserved = exact_total([Decimal(item.amount) for item in reservations] + [amounts[item] for item in scope if item not in existing] + [snapshot.already_refunded_amount])
                        if reserved > snapshot.refundable_amount_max:
                            raise ReservationConflict("Concurrent refunds exceed the order cap")
                        session.flush()
                except ReservationConflict:
                    rejected = RejectedRefundApplicationResult(status="REJECTED", reason_codes=["ITEM_RESERVATION_CONFLICT"], rejected_at=now)
                    row.status, row.application_result, row.updated_at = "REJECTED", rejected.model_dump(mode="json"), now
                    session.flush()
                    return self.record(row)
                row.application_started_at, row.updated_at = now, now
        # No transaction or database lock crosses the external application boundary.
        try:
            result = TypeAdapter(RefundApplicationResult).validate_python(self.application.apply(ApplyRefundRequest(execution_ref=execution_ref, resolution_handoff=resolution)))
        except ContractConflict:
            raise
        except Exception as exc:
            raise ProviderUnavailable("Refund application outcome is unknown; retry the same execution") from exc
        with self.sessions.begin() as session:
            lock_identifier(session, "refund-execution", execution_ref)
            row = session.get(RefundExecutionRow, execution_ref)
            if row.payload_hash != digest:
                raise ProviderUnavailable("Execution integrity failed")
            if row.status != "IN_PROGRESS":
                if row.application_result != result.model_dump(mode="json"):
                    raise ProviderUnavailable("Application returned conflicting terminal results")
                return self.record(row)
            self.owned_items(session, row, scope)
            if result.status == "APPLIED":
                for reservation in session.scalars(select(RefundReservationRow).where(RefundReservationRow.execution_ref == execution_ref)):
                    session.add(RefundItemRow(order_ref=reservation.order_ref, line_item_ref=reservation.line_item_ref, execution_ref=execution_ref, amount=reservation.amount))
                row.status = "SUCCEEDED"
            else:
                session.execute(delete(RefundReservationRow).where(RefundReservationRow.execution_ref == execution_ref))
                row.status = "REJECTED"
            row.application_result, row.updated_at = result.model_dump(mode="json"), self.cases.clock()
            session.flush()
            return self.record(row)
