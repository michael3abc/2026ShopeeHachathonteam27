"""Authenticated consent and trusted return-event ingress."""
from datetime import UTC, datetime
import os
from typing import Annotated
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from return_agent_contracts.fulfillment import (PolicyConfirmationInput,ReturnConfirmationInput,ReturnSimulationInput,ReturnFulfillmentEvent,ReturnEventReceipt)
from return_agent_contracts.policy_v2 import PolicyConfirmation,PolicyConfirmationRequest,content_hash
from return_agent_contracts.runtime import PolicyConfirmationResume,GraphNodeName
from return_agent_contracts.service import AgentResumeCommand
from return_agent_contracts.ui import CaseStatus
from .auth import identity
from .db.models import PolicyConfirmationRecord,ReturnAuthorizationRecord,ReturnReceiptRecord
from .db.case import append_agent_event
from .store import CaseStore
from .capabilities.fulfillment import accept_return_event,transition,RETURN_EVENT

router = APIRouter()


def require_service(request: Request):
    from .app import require_internal_service
    require_internal_service(request,request.headers.get("authorization"))


@router.post("/cases/{case_ref}/policy-confirmations",status_code=202)
def confirm_policy(case_ref: str,payload: PolicyConfirmationInput,request: Request) -> PolicyConfirmation:
    identity(request,{"buyer"})
    with request.app.state.session_factory.begin() as session:
        store = CaseStore(session)
        case = store.lock(case_ref)
        record = session.get(PolicyConfirmationRecord,payload.request_ref)
        if record is None or record.case_ref != case_ref:
            raise HTTPException(409,"Unknown confirmation request")
        pending = PolicyConfirmationRequest.model_validate(record.request_payload)
        if pending.selection_version != payload.selection_version:
            raise HTTPException(409,"Confirmation version is stale")
        if record.response_payload is not None:
            result = PolicyConfirmation.model_validate(record.response_payload)
            if result.accepted != payload.accept or record.idempotency_key != payload.idempotency_key:
                raise HTTPException(409,"Confirmation replay changed content")
            return result
        latest = store.latest_interrupt(case_ref)
        if case.status != "AWAITING_POLICY_CONFIRMATION" or latest is None or getattr(latest.payload,"request",None) != pending:
            raise HTTPException(409,"Confirmation request is no longer active")
        result = PolicyConfirmation(confirmation_ref=f"consent:{content_hash([case_ref,payload.request_ref,payload.idempotency_key])}",
            request=pending,accepted=payload.accept,confirmed_at=datetime.now(UTC))
        record.response_payload = result.model_dump(mode="json")
        record.idempotency_key = payload.idempotency_key
        store.transition(case_ref,CaseStatus.OBSERVING)
        append_agent_event(session,case_ref,dict(type="state_change",ts=datetime.now(UTC),node=GraphNodeName.CONFIRM_POLICY_PATH,
            payload=dict(from_status="AWAITING_POLICY_CONFIRMATION",to_status="OBSERVING",reason="政策途徑選擇已保存。")))
        request.app.state.agent_command_outbox.enqueue(session,AgentResumeCommand(command_type="RESUME",
            command_id=f"COMMAND-{uuid4().hex}",case_ref=case_ref,thread_id=case.thread_id,issued_at=datetime.now(UTC),
            payload={"resume":PolicyConfirmationResume(kind="POLICY_CONFIRMATION",confirmation=result)}))
        return result


@router.post("/cases/{case_ref}/return-confirmations",status_code=202)
def confirm_return(case_ref: str,payload: ReturnConfirmationInput,request: Request):
    identity(request,{"buyer"})
    with request.app.state.session_factory.begin() as session:
        record = session.scalar(select(ReturnAuthorizationRecord).where(ReturnAuthorizationRecord.authorization_ref == payload.authorization_ref).with_for_update())
        if record is None or record.case_ref != case_ref or record.payload["requirement_hash"] != payload.return_requirement_hash:
            raise HTTPException(409,"Return confirmation binding mismatch")
        raw = payload.model_dump(mode="json")
        if record.confirmation_payload is not None:
            if record.confirmation_payload.get("input") != raw:
                raise HTTPException(409,"Return confirmation already recorded")
            return {"authorization_ref":record.authorization_ref,"state":record.state}
        if record.state != "AWAITING_RETURN_CONFIRMATION":
            raise HTTPException(409,"Return confirmation is no longer active")
        record.confirmation_payload = {"input":raw,"confirmed_at":datetime.now(UTC).isoformat()}
        transition(session,record,"AWAITING_RETURN" if payload.accept else "ESCALATED",
            "退回要求已確認；等待退回。" if payload.accept else "買家未接受退回要求，交由專責處理；尚未退款。")
        return {"authorization_ref":record.authorization_ref,"state":record.state}


@router.post("/internal/v2/return-events")
def return_event(event: ReturnFulfillmentEvent,request: Request,service: Annotated[None,Depends(require_service)]) -> ReturnEventReceipt:
    producers = set(os.environ.get("RETURN_AGENT_RETURN_PRODUCERS","demo-simulator").split(","))
    if event.producer_id not in producers:
        raise HTTPException(403,"Producer is not allowlisted")
    try:
        with request.app.state.session_factory.begin() as session:
            return accept_return_event(session,event)
    except ValueError as error:
        raise HTTPException(409,str(error)) from error


@router.post("/demo/cases/{case_ref}/return-simulation",status_code=202)
def simulate_return(case_ref: str,payload: ReturnSimulationInput,request: Request) -> ReturnEventReceipt:
    identity(request,{"operator"})
    types = {"ARRIVED":"RETURN_ARRIVED","PASS":"INSPECTION_PASSED","DISPUTE":"INSPECTION_DISPUTED","OVERDUE":"RETURN_OVERDUE"}
    event_id = f"simulation:{content_hash([case_ref,payload.idempotency_key])}"
    try:
        with request.app.state.session_factory.begin() as session:
            existing = session.scalar(select(ReturnReceiptRecord).where(ReturnReceiptRecord.producer_id == "demo-simulator",ReturnReceiptRecord.event_id == event_id))
            if existing is not None:
                if existing.event_payload["event_type"] != types[payload.intent]:
                    raise ValueError("Simulation identity reused with another intent")
                return ReturnEventReceipt.model_validate(existing.receipt_payload)
            record = session.scalar(select(ReturnAuthorizationRecord).where(ReturnAuthorizationRecord.case_ref == case_ref).with_for_update())
            if record is None:
                raise ValueError("No return authorization exists")
            body = {"tracking_ref":"synthetic:tracking"} if payload.intent == "ARRIVED" else {"deadline_ref":"synthetic:deadline"} if payload.intent == "OVERDUE" else {"arrived_event_id":record.arrived_event_id or "missing","inspection_ref":"synthetic:inspection"}
            raw = dict(event_id=event_id,producer_id="demo-simulator",case_ref=case_ref,authorization_ref=record.authorization_ref,
                line_item_id=record.payload["resolution"]["final_decision"]["refund_scope"]["line_item_ids"][0],
                event_type=types[payload.intent],occurred_at=datetime.now(UTC),payload=body)
            event = RETURN_EVENT.validate_python(dict(raw,payload_hash=content_hash(raw)))
            return accept_return_event(session,event)
    except ValueError as error:
        raise HTTPException(409,str(error)) from error
