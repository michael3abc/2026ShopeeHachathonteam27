"""Shared Pydantic configuration and scalar types for contract DTOs."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
)

UTC_WIRE_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$"
MONEY_WIRE_PATTERN = r"^(?:0|[1-9]\d*)(?:\.\d+)?$"


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("datetime must be ISO 8601 UTC")
    return value.astimezone(UTC)


def _require_utc_wire(value: object) -> object:
    if isinstance(value, str) and re.search(UTC_WIRE_PATTERN, value) is None:
        raise ValueError("datetime string must end with Z or +00:00")
    return value


def _parse_money(value: object) -> Decimal:
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, str) and re.fullmatch(MONEY_WIRE_PATTERN, value):
        try:
            amount = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("invalid decimal money string") from error
    else:
        raise ValueError("money must be a non-negative decimal string")
    if not amount.is_finite() or amount < 0:
        raise ValueError("money must be finite and non-negative")
    return amount


def _parse_zero_money(value: object) -> Decimal:
    amount = _parse_money(value)
    if amount != 0:
        raise ValueError("money must equal zero")
    return amount


def _serialize_money(value: Decimal) -> str:
    return format(value, "f")


UTCDateTime = Annotated[
    datetime,
    BeforeValidator(_require_utc_wire),
    AfterValidator(_require_utc),
    WithJsonSchema(
        {
            "type": "string",
            "format": "date-time",
            "pattern": UTC_WIRE_PATTERN,
        }
    ),
]
OpaqueRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, ge=1)]
UnitInterval = Annotated[float, Field(ge=0, le=1)]
CurrencyCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    ),
]
Money = Annotated[
    Decimal,
    BeforeValidator(_parse_money),
    PlainSerializer(_serialize_money, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": MONEY_WIRE_PATTERN}),
]
ZeroMoney = Annotated[
    Decimal,
    BeforeValidator(_parse_zero_money),
    PlainSerializer(_serialize_money, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": r"^0(?:\.0+)?$"}),
]


class ContractModel(BaseModel):
    """Base model for all JSON exchange objects."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )
