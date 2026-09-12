"""Shared request-scoped database and internal authentication dependencies."""

import hmac
from collections.abc import Iterator
from typing import Annotated

from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def require_internal_service(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    token = request.app.state.internal_service_token
    if not token or not token.strip():
        raise HTTPException(503, "Internal service authentication is not configured")
    if authorization is None or not hmac.compare_digest(
        authorization, f"Bearer {token}"
    ):
        raise HTTPException(401, "Invalid service credentials")
