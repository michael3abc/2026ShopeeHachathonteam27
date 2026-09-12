"""Explicit Demo credentials, opaque sessions and role-aware API projections."""
from __future__ import annotations
import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import re
import secrets
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse
from return_agent_contracts.base import ContractModel, OpaqueRef
from .db.models import DemoSessionRecord
from .db.case import CaseRecord
from .capabilities.user_risk import utc

COOKIE = "return_agent_session"


class DemoIdentity(ContractModel):
    user_ref: OpaqueRef
    role: Literal["buyer","reviewer","operator"]


class ConfigIdentity(DemoIdentity):
    credential_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class DemoAuthConfig(ContractModel):
    identities: list[ConfigIdentity] = Field(min_length=1)
    allowed_origins: list[OpaqueRef] = Field(min_length=1)


class LoginRequest(ContractModel):
    user_ref: OpaqueRef
    credential: OpaqueRef


def configure_auth(app) -> None:
    path = os.environ.get("RETURN_AGENT_DEMO_IDENTITIES_FILE")
    app.state.demo_auth_config = DemoAuthConfig.model_validate_json(Path(path).read_text()) if path else None


def identity(request: Request, roles: set[str] | None = None) -> DemoIdentity:
    principal = getattr(request.state,"demo_identity",None)
    if principal is None:
        raise HTTPException(401,"Demo sign-in required")
    if roles is not None and principal.role not in roles:
        raise HTTPException(403,"Role is not authorized")
    return principal


def public_projection(value):
    """Risk and human notes never enter buyer/operator JSON or SSE."""
    if isinstance(value,list):
        return [public_projection(item) for item in value]
    if not isinstance(value,dict):
        return value
    if value.get("type") == "narration" and value.get("text") and re.search(
        r"(?i)risk|風險|欺詐|詐欺|黑名單|退款率|帳號年齡|REPEATED_SAME_REASON|HIGH_REFUND_RATE",value["text"]):
        value = dict(value,text="案件處理進度已更新，請參考目前狀態。")
    result = {}
    for key,item in value.items():
        if key in {"user_risk_snapshot","user_risk_gate","risk_score","risk_tags","account_age_days","same_reason_claims_90d","refunded_orders_90d","orders_90d","dossier","review_note"}:
            continue
        if key in {"human_review","human_review_result"} or (key == "review" and value.get("interrupt_kind") == "HUMAN_REVIEW"):
            result[key] = None
        elif key == "routing_reason" and item in {"HIGH_USER_RISK","USER_RISK_UNAVAILABLE"}:
            continue
        elif key == "reason_codes" and isinstance(item,list):
            result[key] = [x for x in item if x not in {"HIGH_USER_RISK","USER_RISK_UNAVAILABLE","REPEATED_SAME_REASON_CLAIMS","HIGH_REFUND_RATE","NEW_ACCOUNT_REPEATED_CLAIMS"}]
        else:
            result[key] = public_projection(item)
    return result


class DemoAuthMiddleware:
    def __init__(self,app):
        self.app = app

    def _authorize(self,request):
        app = request.app
        config = getattr(app.state,"demo_auth_config",None)
        path = request.url.path
        match = re.match(r"/(?:demo/)?cases/([^/]+)",path)
        with app.state.session_factory() as session:
            case = session.get(CaseRecord,match.group(1)) if match else None
            protected = config is not None or (case is not None and case.policy_schema_version == "v2") or path.startswith("/demo/")
            if not protected:
                return None  # Explicit legacy v1 surface; v2 creation requires identity separately.
            token = request.cookies.get(COOKIE,"")
            record = session.get(DemoSessionRecord,sha256(token.encode()).hexdigest()) if token else None
            if record is None or utc(record.expires_at) <= datetime.now(UTC):
                raise HTTPException(401,"Demo sign-in required")
            principal = DemoIdentity(user_ref=record.user_ref,role=record.role)
        if config is None:
            raise HTTPException(503,"Demo authentication is not configured")
        if not any(p.user_ref == principal.user_ref and p.role == principal.role for p in config.identities):
            raise HTTPException(401,"Demo identity is no longer configured")
        if request.method not in {"GET","HEAD","OPTIONS"} and request.headers.get("origin") not in config.allowed_origins:
            raise HTTPException(403,"Origin is not authorized")
        if case is not None and principal.role == "buyer" and principal.user_ref != case.user_ref:
            raise HTTPException(403,"Case owner mismatch")
        if path.endswith("/review") and principal.role != "reviewer":
            raise HTTPException(403,"Reviewer role required")
        if path.endswith("/return-simulation") and principal.role != "operator":
            raise HTTPException(403,"Operator role required")
        if (path.endswith("/messages") or path.endswith("/policy-confirmations") or path.endswith("/return-confirmations") or path == "/cases") and request.method == "POST" and principal.role != "buyer":
            raise HTTPException(403,"Buyer role required")
        return principal

    async def __call__(self,scope,receive,send):
        if scope["type"] != "http" or not scope["path"].startswith(("/cases","/demo/")):
            return await self.app(scope,receive,send)
        request = StarletteRequest(scope,receive)
        try:
            principal = await asyncio.to_thread(self._authorize,request)
        except HTTPException as error:
            return await JSONResponse({"detail":error.detail},status_code=error.status_code)(scope,receive,send)
        scope.setdefault("state",{})["demo_identity"] = principal
        if principal is None or principal.role == "reviewer":
            return await self.app(scope,receive,send)
        pending = b""
        content_type = b""
        async def projected(message):
            nonlocal pending,content_type
            if message["type"] == "http.response.start":
                content_type = dict(message["headers"]).get(b"content-type",b"")
                message = dict(message,headers=[(k,v) for k,v in message["headers"] if k.lower() != b"content-length"])
            elif message["type"] == "http.response.body":
                pending += message.get("body",b"")
                if b"text/event-stream" in content_type:
                    frames = pending.split(b"\n\n")
                    pending = frames.pop()
                    rendered = []
                    for frame in frames:
                        lines = []
                        for line in frame.split(b"\n"):
                            if line.startswith(b"data: "):
                                line = b"data: " + json.dumps(public_projection(json.loads(line[6:])),ensure_ascii=False).encode()
                            lines.append(line)
                        rendered.append(b"\n".join(lines)+b"\n\n")
                    body = b"".join(rendered)
                    if not message.get("more_body",False):
                        body += pending
                        pending = b""
                    message = dict(message,body=body)
                elif b"application/json" in content_type:
                    if message.get("more_body",False):
                        return
                    message = dict(message,body=json.dumps(public_projection(json.loads(pending)),ensure_ascii=False).encode())
                    pending = b""
                else:
                    message = dict(message,body=pending)
                    pending = b""
            await send(message)
        await self.app(scope,receive,projected)


router = APIRouter()


@router.get("/auth/config")
def auth_config(request: Request):
    return {"enabled":getattr(request.app.state,"demo_auth_config",None) is not None}


@router.post("/auth/logout")
def logout(request: Request,response: Response):
    config = getattr(request.app.state,"demo_auth_config",None)
    if config is None or request.headers.get("origin") not in config.allowed_origins:
        raise HTTPException(403,"Origin is not authorized")
    token = request.cookies.get(COOKIE,"")
    with request.app.state.session_factory.begin() as session:
        record = session.get(DemoSessionRecord,sha256(token.encode()).hexdigest()) if token else None
        if record is not None:
            session.delete(record)
    response.delete_cookie(COOKIE)
    return {"signed_out":True}


@router.post("/auth/login")
def login(payload: LoginRequest,request: Request,response: Response) -> DemoIdentity:
    config = getattr(request.app.state,"demo_auth_config",None)
    if config is None:
        raise HTTPException(503,"Demo authentication is not configured")
    if request.headers.get("origin") not in config.allowed_origins:
        raise HTTPException(403,"Origin is not authorized")
    match = next((p for p in config.identities if p.user_ref == payload.user_ref),None)
    digest = sha256(payload.credential.encode()).hexdigest()
    if match is None or not hmac.compare_digest(match.credential_sha256,digest):
        raise HTTPException(401,"Invalid Demo credentials")
    token = secrets.token_urlsafe(32)
    with request.app.state.session_factory.begin() as session:
        session.add(DemoSessionRecord(token_hash=sha256(token.encode()).hexdigest(),user_ref=match.user_ref,role=match.role,expires_at=datetime.now(UTC)+timedelta(hours=8)))
    response.set_cookie(COOKIE,token,max_age=28800,httponly=True,samesite="strict",secure=request.url.scheme == "https")
    return DemoIdentity(user_ref=match.user_ref,role=match.role)


@router.get("/auth/session")
def session_identity(request: Request) -> DemoIdentity:
    config = getattr(request.app.state,"demo_auth_config",None)
    if config is None:
        raise HTTPException(503,"Demo authentication is not configured")
    token = request.cookies.get(COOKIE,"")
    with request.app.state.session_factory() as session:
        record = session.get(DemoSessionRecord,sha256(token.encode()).hexdigest()) if token else None
        if record is None or utc(record.expires_at) <= datetime.now(UTC):
            raise HTTPException(401,"Demo sign-in required")
        if not any(p.user_ref == record.user_ref and p.role == record.role for p in config.identities):
            raise HTTPException(401,"Demo identity is no longer configured")
        return DemoIdentity(user_ref=record.user_ref,role=record.role)
