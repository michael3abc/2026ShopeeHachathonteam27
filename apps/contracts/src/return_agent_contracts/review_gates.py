"""Versioned deterministic authorization rules, independent of LLM verdicts."""

from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Literal
import json
from pydantic import Field, model_validator
from .base import ContractModel, CurrencyCode, Money, OpaqueRef
from .enums import ResolutionAction

HumanReviewRoutingReason = Literal["REVISION_BUDGET_EXCEEDED", "HIGH_VALUE_ITEM", "CURRENCY_THRESHOLD_UNCONFIGURED"]

def _canonical_decimal(value: Decimal) -> str:
    # Decimal.normalize() can round under the process decimal context.
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text

class ReviewerGateConfig(ContractModel):
    version: OpaqueRef = "reviewer-gates:1.0"
    thresholds: dict[CurrencyCode, Money] = Field(default_factory=lambda: {"TWD": Decimal("5000"), "SGD": Decimal("200")})

    @property
    def fingerprint(self) -> str:
        payload = {"version": self.version, "thresholds": {key: _canonical_decimal(value) for key, value in sorted(self.thresholds.items())}}
        return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

class ReviewGateResult(ContractModel):
    config_version: OpaqueRef
    config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["PASS", "HUMAN_REQUIRED", "NOT_APPLICABLE"]
    amount: Money
    currency: CurrencyCode
    threshold: Money | None
    reason: Literal["HIGH_VALUE_ITEM", "CURRENCY_THRESHOLD_UNCONFIGURED"] | None

    @model_validator(mode="after")
    def _consistent_result(self):
        if self.status == "NOT_APPLICABLE":
            valid = self.reason is None
        elif self.status == "PASS":
            valid = self.reason is None and self.threshold is not None and self.amount <= self.threshold
        elif self.reason == "HIGH_VALUE_ITEM":
            valid = self.threshold is not None and self.amount > self.threshold
        else:
            valid = self.reason == "CURRENCY_THRESHOLD_UNCONFIGURED" and self.threshold is None
        if not valid:
            raise ValueError("inconsistent monetary gate result")
        return self

def load_reviewer_gate_config(path: str | None = None) -> ReviewerGateConfig:
    if path is None:
        return ReviewerGateConfig()
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict) or set(payload) != {"version", "thresholds"}:
        raise ValueError("review gate config requires explicit version and thresholds")
    return ReviewerGateConfig.model_validate(payload)

def evaluate_review_gate(action: ResolutionAction, amount: Decimal, currency: str, config: ReviewerGateConfig) -> ReviewGateResult:
    threshold = config.thresholds.get(currency)
    status, reason = "PASS", None
    if action is ResolutionAction.DECLINE:
        status = "NOT_APPLICABLE"
    elif threshold is None:
        status, reason = "HUMAN_REQUIRED", "CURRENCY_THRESHOLD_UNCONFIGURED"
    elif amount > threshold:
        status, reason = "HUMAN_REQUIRED", "HIGH_VALUE_ITEM"
    return ReviewGateResult(config_version=config.version, config_hash=config.fingerprint, status=status, reason=reason, amount=amount, currency=currency, threshold=threshold)
