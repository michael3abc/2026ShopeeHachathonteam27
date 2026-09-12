"""Trusted Backend-to-capability operation contracts.

These DTOs are intentionally separate from Agent graph provider envelopes and
from UI projection contracts.
"""

from .models import (
    ApplyRefundRequest,
    ExecuteRefundRequest,
    RefundApplicationResult,
    RefundExecutionRecord,
)

OPERATIONS_SCHEMA_MODELS: dict[str, object] = {
    "ApplyRefundRequest.schema.json": ApplyRefundRequest,
    "RefundApplicationResult.schema.json": RefundApplicationResult,
    "ExecuteRefundRequest.schema.json": ExecuteRefundRequest,
    "RefundExecutionRecord.schema.json": RefundExecutionRecord,
}
