"""Small JSON-safe projection helpers used by model prompts and interrupts."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

_JSON_VALUE_ADAPTER = TypeAdapter(Any)


def json_value(value: Any) -> Any:
    """Convert nested Python and contract values into JSON-safe wire values."""

    return _JSON_VALUE_ADAPTER.dump_python(value, mode="json")
