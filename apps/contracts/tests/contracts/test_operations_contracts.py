from __future__ import annotations

from copy import deepcopy

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.models import (
    ApplyRefundRequest,
    ExecuteRefundRequest,
    RefundApplicationResult,
    RefundExecutionRecord,
)

from .fixtures import approved_review, TIME


def _resolution_handoff() -> dict[str, object]:
    return {
        "case_ref": "CASE-001",
        "handoff_id": "HANDOFF-001",
        "outcome_source": "REVIEWER_APPROVE",
        "final_decision": {
            "action": "FULL_REFUND",
            "refund_scope": {"line_item_ids": ["LI-002"]},
            "amount": "1200",
            "currency": "TWD",
            "return_decision": {
                "source": "MODEL_JUDGMENT",
                "requirement": {
                    "required": False,
                    "reason_code": "ITEM_UNSALVAGEABLE",
                },
            },
            "reason_code": "ITEM_DAMAGED",
        },
        "review_result": approved_review().model_dump(mode="json"),
        "execution_blocked": False,
        "emitted_at": TIME,
    }


def _assert_parity(contract: object, payload: object, expected: bool) -> None:
    try:
        TypeAdapter(contract).validate_python(payload)
        pydantic_accepts = True
    except ValidationError:
        pydantic_accepts = False

    schema = TypeAdapter(contract).json_schema(mode="validation")
    schema_accepts = Draft202012Validator(
        schema, format_checker=FormatChecker()
    ).is_valid(payload)
    assert pydantic_accepts is expected
    assert schema_accepts is expected


def test_refund_operation_contracts_are_schema_parity_safe() -> None:
    handoff = _resolution_handoff()
    execute_request = {"resolution_handoff": handoff}
    apply_request = {"execution_ref": "EXEC-001", "resolution_handoff": handoff}
    applied = {
        "status": "APPLIED",
        "application_ref": "REFUND-APPLICATION-001",
        "applied_at": TIME,
    }
    execution = {
        "execution_ref": "EXEC-001",
        "handoff_id": "HANDOFF-001",
        "case_ref": "CASE-001",
        "status": "SUCCEEDED",
        "application_result": applied,
        "created_at": TIME,
        "updated_at": TIME,
    }

    for contract, payload in (
        (ExecuteRefundRequest, execute_request),
        (ApplyRefundRequest, apply_request),
        (RefundApplicationResult, applied),
        (RefundExecutionRecord, execution),
    ):
        _assert_parity(contract, payload, True)

    with_unknown_field = deepcopy(execute_request)
    with_unknown_field["unexpected"] = "no"
    _assert_parity(ExecuteRefundRequest, with_unknown_field, False)

    with_non_utc_timestamp = deepcopy(execution)
    with_non_utc_timestamp["created_at"] = "2026-09-01T18:00:00+08:00"
    _assert_parity(RefundExecutionRecord, with_non_utc_timestamp, False)

    invalid_union = deepcopy(execution)
    invalid_union["status"] = "REJECTED"
    _assert_parity(RefundExecutionRecord, invalid_union, False)

    numeric_money = deepcopy(execute_request)
    numeric_money["resolution_handoff"]["final_decision"]["amount"] = 1200
    _assert_parity(ExecuteRefundRequest, numeric_money, False)
