from hashlib import sha256
import json
import pytest
from fastapi.testclient import TestClient
from return_agent.app import app, get_session
from return_agent.auth import DemoAuthConfig, public_projection
from .test_policy_v2_fulfillment import setup_case


@pytest.fixture
def signed_client():
    env = setup_case()
    previous = getattr(app.state,"demo_auth_config",None)
    app.state.demo_auth_config = DemoAuthConfig(allowed_origins=["http://testserver"],identities=[
        dict(user_ref=user,role=role,credential_sha256=sha256(user.encode()).hexdigest())
        for user,role in [("USER-NORMAL","buyer"),("OTHER","buyer"),("REVIEWER","reviewer"),("OPERATOR","operator")]])
    app.state.session_factory = env.sessions
    def session():
        with env.sessions() as value:
            yield value
    app.dependency_overrides[get_session] = session
    client = TestClient(app)
    yield client,env
    app.dependency_overrides.clear()
    app.state.demo_auth_config = previous


def login(client, user="USER-NORMAL"):
    return client.post("/auth/login",headers={"origin":"http://testserver"},json={"user_ref":user,"credential":user})


def test_opaque_session_owner_and_role_boundaries(signed_client):
    client,env = signed_client
    url = f"/cases/{env.case.case_ref}"
    assert client.get(url).status_code == 401
    assert client.get(url+"/events").status_code == 401
    assert client.get(url+"/activities/stream").status_code == 401
    client.cookies.set("return_agent_session",'{"role":"reviewer"}')
    assert client.get(url).status_code == 401
    client.cookies.clear()
    response = login(client)
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get(url).status_code == 200
    assert client.post(url+"/review",headers={"origin":"http://testserver"},json={}).status_code == 403
    assert client.post("/demo"+url+"/return-simulation",headers={"origin":"http://testserver"},json={}).status_code == 403
    assert client.post(url+"/messages",json={"message":"hello"}).status_code == 403
    assert client.post("/internal/v2/return-events",json={}).status_code in {401,503}
    login(client,"OTHER")
    for suffix in ["","/events","/activities","/activities/stream"]:
        assert client.get(url+suffix).status_code == 403
    login(client,"OPERATOR")
    assert client.post(url+"/review",headers={"origin":"http://testserver"},json={}).status_code == 403
    assert client.post("/auth/logout",headers={"origin":"http://testserver"}).status_code == 200
    assert client.get(url).status_code == 401


def test_public_projection_removes_dossier_risk_and_narration():
    raw = {"seq":12,"human_review":{"dossier":{"user_risk_snapshot":{"orders_90d":4}}},
        "payload":{"user_risk_gate":{"score":80},"review_note":"private", "reason_codes":["HIGH_USER_RISK"]},
        "events":[{"type":"narration","source_event_id":"source","text":"買家退款率屬高風險。"}]}
    projected = public_projection(raw)
    assert projected["seq"] == 12
    assert projected["events"][0]["source_event_id"] == "source"
    rendered = json.dumps(projected,ensure_ascii=False)
    for private in ["orders_90d","user_risk_gate","HIGH_USER_RISK","private","退款率","風險"]:
        assert private not in rendered


def test_session_rejects_removed_identity_and_role_forgery(signed_client):
    client, _ = signed_client
    assert client.post("/auth/login", headers={"origin": "http://testserver"},
        json={"user_ref": "USER-NORMAL", "credential": "USER-NORMAL", "role": "reviewer"}).status_code == 422
    assert login(client).status_code == 200
    assert client.get("/auth/session").json()["role"] == "buyer"
    app.state.demo_auth_config = app.state.demo_auth_config.model_copy(update={"identities": [
        p for p in app.state.demo_auth_config.identities if p.user_ref != "USER-NORMAL"
    ]})
    assert client.get("/auth/session").status_code == 401


@pytest.mark.parametrize("user", ["USER-NORMAL", "OPERATOR", "REVIEWER"])
@pytest.mark.parametrize("surface", ["json", "events", "activities/stream"])
def test_projected_json_and_fragmented_sse_preserve_cursor(signed_client, user, surface):
    """Exercise the HTTP middleware including split Unicode/frame boundaries."""
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from return_agent.auth import DemoAuthMiddleware

    client, env = signed_client
    assert login(client, user).status_code == 200
    server = FastAPI()
    server.state.session_factory = env.sessions
    server.state.demo_auth_config = app.state.demo_auth_config
    server.add_middleware(DemoAuthMiddleware)
    raw = {"seq": 17, "event_id": "EVENT-17", "next_cursor": 17,
        "human_review": {"dossier": {"user_risk_gate": {"score": 65}}},
        "payload": {"type": "narration", "source_event_id": "SOURCE-16",
            "text": "帳號退款率造成高風險，轉人工審核。"},
        "resolution": {"user_risk_gate": {"tags": ["HIGH_REFUND_RATE"]}}}
    url = f"/cases/{env.case.case_ref}/{surface}"

    @server.get(url)
    async def output():
        if surface == "json":
            return raw
        body = ("id: 17\nevent: activity\ndata: " + json.dumps(raw, ensure_ascii=False) + "\n\n").encode()
        async def chunks():
            for offset in range(0, len(body), 7):
                yield body[offset:offset + 7]
        return StreamingResponse(chunks(), media_type="text/event-stream")

    response = TestClient(server, cookies=client.cookies).get(url)
    assert response.status_code == 200
    if surface == "json":
        projected = response.json()
    else:
        assert "id: 17\nevent: activity\n" in response.text
        projected = json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith("data: ")))
    assert projected["seq"] == projected["next_cursor"] == 17
    assert projected["event_id"] == "EVENT-17"
    assert projected["payload"]["source_event_id"] == "SOURCE-16"
    if user == "REVIEWER":
        assert projected == raw
    else:
        for private in ("user_risk_gate", "HIGH_REFUND_RATE", "退款率", "風險"):
            assert private not in response.text


def test_policy_confirmation_persists_typed_resume_and_replays_once(signed_client):
    from return_agent.db.models import PolicyConfirmationRecord
    from return_agent.db.case import CaseRecord, append_agent_event
    from return_agent_contracts.policy_v2 import PolicyConfirmationRequest, content_hash
    from .test_cases import RecordingOutbox
    from .test_policy_v2_fulfillment import NOW
    client,env=signed_client
    pending=PolicyConfirmationRequest(request_ref="request",case_ref=env.case.case_ref,
        original_scope_hash=content_hash(["LI-DEMO-SPEAKER"]),original_path_id="COOLING_OFF",path_id="COOLING_OFF",
        selection_version=2,return_required=True,return_requirement_hash=content_hash({"required":True,"reason_code":"POLICY_RETURN_REQUIRED"}))
    with env.sessions.begin() as session:
        session.get(CaseRecord,env.case.case_ref).status="AWAITING_POLICY_CONFIRMATION"
        session.add(PolicyConfirmationRecord(request_ref=pending.request_ref,case_ref=env.case.case_ref,request_payload=pending.model_dump(mode="json")))
        append_agent_event(session,env.case.case_ref,dict(type="interrupt",ts=NOW,node="confirm_policy_path",
            payload=dict(interrupt_kind="POLICY_CONFIRMATION",request=pending.model_dump(mode="json"))))
    app.state.agent_command_outbox=RecordingOutbox()
    login(client)
    payload=dict(request_ref="request",selection_version=2,accept=True,idempotency_key="consent")
    url=f"/cases/{env.case.case_ref}/policy-confirmations"
    response=client.post(url,headers={"origin":"http://testserver"},json=payload)
    assert response.status_code == 202, response.text
    again=client.post(url,headers={"origin":"http://testserver"},json=payload)
    assert again.json() == response.json()
    commands=app.state.agent_command_outbox.commands
    assert len(commands) == 1
    assert commands[0].payload.resume.kind == "POLICY_CONFIRMATION"
    assert client.post(url,headers={"origin":"http://testserver"},json=payload|{"accept":False}).status_code == 409
    app.state.agent_command_outbox=None
