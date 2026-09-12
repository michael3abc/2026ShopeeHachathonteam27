"""Checkpoint serialization helpers for trusted Agent state types."""

from __future__ import annotations

from enum import Enum
from inspect import getmembers, isclass

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel
from return_agent_contracts import enums, models, runtime, review_gates
from return_agent_contracts import policy_v2, user_risk

from . import state


def create_checkpoint_serializer() -> JsonPlusSerializer:
    """Allow only project-owned DTO and enum types stored in graph checkpoints."""

    trusted_types: list[type[BaseModel | Enum]] = []
    for module in (enums, models, runtime, review_gates, policy_v2, user_risk, state):
        trusted_types.extend(
            member
            for _, member in getmembers(module, isclass)
            if member.__module__ == module.__name__
            and issubclass(member, (BaseModel, Enum))
        )
    return JsonPlusSerializer(allowed_msgpack_modules=trusted_types)
