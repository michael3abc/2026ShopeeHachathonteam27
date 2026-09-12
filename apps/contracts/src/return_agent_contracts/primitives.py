"""Wire primitives: decimal strings and UTC instants, never coerced floats."""
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
import hashlib
import json
import re
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, WithJsonSchema

MONEY_PATTERN = r"^(?:0|[1-9]\d*)(?:\.\d+)?$"
UTC_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, revalidate_instances="always")


def parse_amount(value: object) -> Decimal:
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str) and re.fullmatch(MONEY_PATTERN, value):
        result = Decimal(value)
    else:
        raise ValueError("Money requires a decimal string or Decimal; numeric JSON is forbidden")
    if not result.is_finite() or result < 0 or result.is_signed():
        raise ValueError("Money must be finite and nonnegative")
    return result


def parse_utc(value: object) -> datetime:
    if isinstance(value, str):
        if not re.fullmatch(UTC_PATTERN, value):
            raise ValueError("Timestamp must use Z or +00:00")
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must have an explicit UTC offset")
    return value


Ref = Annotated[str, Field(min_length=1)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$", min_length=3, max_length=3)]
Amount = Annotated[
    Decimal, BeforeValidator(parse_amount),
    PlainSerializer(lambda value: format(value, "f"), return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": MONEY_PATTERN}),
]
UTCDateTime = Annotated[
    datetime, BeforeValidator(parse_utc),
    WithJsonSchema({"type": "string", "format": "date-time", "pattern": UTC_PATTERN}),
]


def exact_total(values: list[Decimal]) -> Decimal:
    """Keep all significant digits even when the caller's decimal context is small."""
    with localcontext() as context:
        context.prec = max(28, sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent) for v in values) + 10)
        return sum(values, Decimal(0))


def unique(values: list[Any], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label}")


def payload_hash(value: ContractModel) -> str:
    serialized = json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()
