from __future__ import annotations

import httpx
import pytest
import respx
from return_agent_contracts.http_adapters import (
    HttpHumanReviewProvider,
    HttpVerificationProvider,
    ProviderTransportError,
)
from return_agent_contracts.models import PassedVerificationResult
from return_agent_contracts.transport import (
    SubmitHumanReviewResponse,
    VerifyHandoffResponse,
)

from .fixtures import proposed_handoff, revised_review


@respx.mock
def test_http_verification_adapter_sends_envelope_and_maps_outage() -> None:
    route = respx.post("https://api.example/internal/v1/verification").mock(
        return_value=httpx.Response(
            200,
            json=VerifyHandoffResponse(
                result=PassedVerificationResult(
                    status="PASS",
                    issues=[],
                    verification_version="verification:1.0",
                )
            ).model_dump(mode="json"),
        )
    )
    provider = HttpVerificationProvider(
        base_url="https://api.example",
        service_token="secret",
    )

    assert provider.verify(proposed_handoff()).status.value == "PASS"
    assert route.called
    assert route.calls[0].request.headers["Authorization"] == "Bearer secret"

    route.mock(side_effect=httpx.ReadTimeout("unavailable"))
    assert provider.verify(proposed_handoff()).status.value == "UNAVAILABLE"

    route.mock(return_value=httpx.Response(200, content=b"not-json"))
    with pytest.raises(ProviderTransportError):
        provider.verify(proposed_handoff())


@respx.mock
def test_http_human_review_adapter_rejects_transport_or_contract_failure() -> None:
    route = respx.post("https://api.example/internal/v1/human-reviews").mock(
        return_value=httpx.Response(
            200,
            json=SubmitHumanReviewResponse(result="REVIEW-001").model_dump(mode="json"),
        )
    )
    provider = HttpHumanReviewProvider(
        base_url="https://api.example",
        service_token="secret",
    )
    assert provider.submit_for_review(proposed_handoff(), revised_review()) == "REVIEW-001"
    assert route.called
    assert route.calls[0].request.headers["Authorization"] == "Bearer secret"

    route.mock(return_value=httpx.Response(503))
    with pytest.raises(ProviderTransportError):
        provider.submit_for_review(proposed_handoff(), revised_review())

    route.mock(side_effect=httpx.ReadTimeout("unavailable"))
    with pytest.raises(ProviderTransportError):
        provider.submit_for_review(proposed_handoff(), revised_review())


@respx.mock
def test_memory_http_contract_preserves_query_and_cosine_order():
    import json

    from return_agent_contracts.http_adapters import HttpOperationalMemoryStore

    from .fixtures import TIME, memory_candidate

    candidate = memory_candidate().model_dump(mode="json")
    approved = {key: value for key, value in candidate.items() if key not in {
        "rationale", "source_case_refs", "source_revision_event_refs", "status",
    }} | {"status": "APPROVED", "approved_at": TIME}
    hits = [{"memory": approved | {"memory_id": name, "confidence": confidence}, "similarity": score}
            for name, confidence, score in [("LOW", 0.1, 0.9), ("HIGH", 0.99, 0.7)]]
    route = respx.post("https://api.example/internal/v1/memory/query").mock(
        return_value=httpx.Response(200, json={"result": hits}),
    )
    provider = HttpOperationalMemoryStore(base_url="https://api.example", service_token="test-token")
    result = provider.query_approved(query_summary="current packaging evidence", market="TW", reason_code="ITEM_DAMAGED",
        required_claim_ids=["DAMAGE_PRESENT_ON_ARRIVAL"], categories=[], policy_versions=["POLICY-12:v3"], claim_registry_major=1)
    assert [hit.memory.memory_id for hit in result] == ["LOW", "HIGH"]
    assert [hit.similarity for hit in result] == [0.9, 0.7]
    assert json.loads(route.calls[0].request.content)["params"]["query_summary"] == "current packaging evidence"
