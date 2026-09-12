"""API-owned return fulfillment. These messages do not authorize payment."""
from typing import Annotated, Literal, TypeAlias
from pydantic import Field, model_validator
from .base import ContractModel, OpaqueRef, PositiveInt, UTCDateTime
from .policy_v2 import content_hash, RefundReleaseCondition, PolicyPathId


class PolicyConfirmationInput(ContractModel):
    request_ref: OpaqueRef
    selection_version: PositiveInt
    accept: bool
    idempotency_key: OpaqueRef


class ReturnConfirmationInput(ContractModel):
    authorization_ref: OpaqueRef
    return_requirement_hash: OpaqueRef
    accept: bool
    idempotency_key: OpaqueRef


class ArrivalPayload(ContractModel):
    tracking_ref: OpaqueRef


class InspectionPayload(ContractModel):
    arrived_event_id: OpaqueRef
    inspection_ref: OpaqueRef


class OverduePayload(ContractModel):
    deadline_ref: OpaqueRef


class _ReturnEvent(ContractModel):
    event_id: OpaqueRef
    producer_id: OpaqueRef
    case_ref: OpaqueRef
    authorization_ref: OpaqueRef
    line_item_id: OpaqueRef
    occurred_at: UTCDateTime
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _hash(self):
        if content_hash(self.model_dump(mode="json",exclude={"payload_hash"})) != self.payload_hash:
            raise ValueError("return event content hash mismatch")
        return self


class ReturnArrivedEvent(_ReturnEvent):
    event_type: Literal["RETURN_ARRIVED"]
    payload: ArrivalPayload


class InspectionPassedEvent(_ReturnEvent):
    event_type: Literal["INSPECTION_PASSED"]
    payload: InspectionPayload


class InspectionDisputedEvent(_ReturnEvent):
    event_type: Literal["INSPECTION_DISPUTED"]
    payload: InspectionPayload


class ReturnOverdueEvent(_ReturnEvent):
    event_type: Literal["RETURN_OVERDUE"]
    payload: OverduePayload


ReturnFulfillmentEvent: TypeAlias = Annotated[ReturnArrivedEvent | InspectionPassedEvent | InspectionDisputedEvent | ReturnOverdueEvent,Field(discriminator="event_type")]


class ReturnEventReceipt(ContractModel):
    receipt_ref: OpaqueRef
    event_id: OpaqueRef
    producer_id: OpaqueRef
    authorization_ref: OpaqueRef
    accepted_at: UTCDateTime
    state: OpaqueRef


class ReturnSimulationInput(ContractModel):
    intent: Literal["ARRIVED", "PASS", "DISPUTE", "OVERDUE"]
    idempotency_key: OpaqueRef


class FulfillmentProjection(ContractModel):
    authorization_ref: OpaqueRef
    selected_path_id: PolicyPathId
    state: Literal["AWAITING_RETURN_CONFIRMATION","AWAITING_RETURN","AWAITING_RETURN_INSPECTION","EXECUTING","RESOLVED","ESCALATED"]
    return_required: bool
    return_requirement_hash: OpaqueRef
    refund_release_condition: RefundReleaseCondition
    payment_status: Literal["NOT_STARTED","IN_PROGRESS","SUCCEEDED","REJECTED"]
    arrived_event_id: OpaqueRef | None = None
    inspection_event_id: OpaqueRef | None = None
    reason: str | None = None
