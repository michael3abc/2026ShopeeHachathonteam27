from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.enums import ClaimId
from return_agent_contracts.models import (
    PassedVerificationResult,
)
from return_agent_contracts.transport import (
    PROVIDER_REQUEST_MODELS,
    PROVIDER_RESPONSE_MODELS,
    FetchHumanReviewRequest,
    FetchHumanReviewResponse,
    LoadCaseContextRequest,
    LoadCaseContextResponse,
    QueryApprovedMemoryRequest,
    QueryApprovedMemoryResponse,
    ResolveEvidenceRequest,
    ResolveEvidenceResponse,
    RetrievePolicyRequest,
    RetrievePolicyResponse,
    SubmitHumanReviewRequest,
    SubmitHumanReviewResponse,
    SubmitMemoryCandidateRequest,
    SubmitMemoryCandidateResponse,
    VerifyHandoffRequest,
    VerifyHandoffResponse,
)

from .fixtures import (
    case_context,
    case_context_load_result,
    evidence_item,
    memory_candidate,
    order_snapshot,
    policy_bundle,
    proposed_handoff,
    revised_review,
)


def test_all_nine_provider_requests_are_modelled() -> None:
    assert len(PROVIDER_REQUEST_MODELS) == 8
    assert len(PROVIDER_RESPONSE_MODELS) == 8
    requests = [
        LoadCaseContextRequest(
            method="CaseContextProvider.load_case_context",
            params={"case_ref": "CASE-001"},
        ),
        RetrievePolicyRequest(
            method="PolicyProvider.retrieve_policy",
            params={
                "case_context": case_context(),
                "order_snapshot": order_snapshot(),
                "reason_code": "ITEM_DAMAGED",
                "claimed_line_item_ids": ["LI-002"],
            },
        ),
        QueryApprovedMemoryRequest(
            method="OperationalMemoryStore.query_approved",
            params={
                "query_summary": "Damaged item with current evidence.",
                "market": "TW",
                "reason_code": "ITEM_DAMAGED",
                "required_claim_ids": [ClaimId.DAMAGE_PRESENT_ON_ARRIVAL],
                "categories": ["CAT-AUDIO-SPEAKERS"],
                "policy_versions": ["POLICY-12:v3"],
                "claim_registry_major": 1,
            },
        ),
        ResolveEvidenceRequest(
            method="EvidenceProvider.resolve",
            params={"artifact_ref": "artifact://evidence/EV-002"},
        ),
        VerifyHandoffRequest(
            method="VerificationProvider.verify", params={"handoff": proposed_handoff()}
        ),
        SubmitHumanReviewRequest(
            method="HumanReviewProvider.submit_for_review",
            params={
                "handoff": proposed_handoff(),
                "review": revised_review(),
            },
        ),
        FetchHumanReviewRequest(
            method="HumanReviewProvider.fetch_result",
            params={"review_ref": "HUMAN-REVIEW-001"},
        ),
        SubmitMemoryCandidateRequest(
            method="OperationalMemoryStore.submit_candidate",
            params={"candidate": memory_candidate()},
        ),
    ]
    assert len(requests) == 8
    responses = [
        LoadCaseContextResponse(result=case_context_load_result()),
        RetrievePolicyResponse(result=policy_bundle()),
        QueryApprovedMemoryResponse(result=[]),
        ResolveEvidenceResponse(result=evidence_item()),
        VerifyHandoffResponse(
            result=PassedVerificationResult(
                status="PASS", issues=[], verification_version="verification:1.0"
            )
        ),
        SubmitHumanReviewResponse(result="HUMAN-REVIEW-001"),
        FetchHumanReviewResponse(result=None),
        SubmitMemoryCandidateResponse(result="MEMORY-SUBMISSION-001"),
    ]
    assert len(responses) == 8
    for envelope in [*requests, *responses]:
        type(envelope).model_validate(envelope.model_dump(mode="json"))

    with pytest.raises(ValidationError):
        LoadCaseContextRequest(
            method="PolicyProvider.retrieve_policy",
            params={"case_ref": "CASE-001"},
        )


def test_external_interface_json_examples_match_transport_contracts() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    text = (repository_root / "docs/spec/08-external-interfaces.md").read_text(
        encoding="utf-8"
    )
    payloads = [
        json.loads(block)
        for block in re.findall(r"```json\n(.*?)\n```", text, flags=re.DOTALL)
    ]
    assert len(payloads) == 16
    for index, (request_model, response_model) in enumerate(
        zip(PROVIDER_REQUEST_MODELS, PROVIDER_RESPONSE_MODELS, strict=True)
    ):
        TypeAdapter(request_model).validate_python(payloads[index * 2])
        TypeAdapter(response_model).validate_python(payloads[index * 2 + 1])
