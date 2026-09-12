"""API payment facts delivered to the Agent's durable correction join."""
from typing import Literal
from .base import ContractModel, OpaqueRef, UTCDateTime
from pydantic import Field

REFUND_COMPLETION_STREAM = "return-agent.refund-completions.v2"
REFUND_COMPLETION_GROUP = "return-agent.memory-completion.v2"


class RefundAppliedEvent(ContractModel):
    schema_version: Literal["v2"] = "v2"
    status: Literal["APPLIED"] = "APPLIED"
    case_ref: OpaqueRef
    resolution_ref: OpaqueRef
    authorization_ref: OpaqueRef
    resolution_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    execution_ref: OpaqueRef
    application_ref: OpaqueRef
    applied_at: UTCDateTime
