"""Versioned automation authority; never a fraud or eligibility classifier."""

from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .base import ContractModel, Money, NonNegativeInt, OpaqueRef, PositiveInt, UTCDateTime
from .enums import ReasonCode, ResolutionAction


class RiskTag(StrEnum):
    REPEATED_SAME_REASON_CLAIMS = "REPEATED_SAME_REASON_CLAIMS"
    HIGH_REFUND_RATE = "HIGH_REFUND_RATE"
    NEW_ACCOUNT_REPEATED_CLAIMS = "NEW_ACCOUNT_REPEATED_CLAIMS"


class UserRiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class RepeatedClaimsRule(ContractModel):
    same_reason_claims_90d_gte: PositiveInt = 3
    points: NonNegativeInt = 40


class RefundRateRule(ContractModel):
    minimum_orders_90d: PositiveInt = 5
    refund_rate_gte: Money = Decimal("0.40")
    points: NonNegativeInt = 25

    @model_validator(mode="after")
    def _ratio(self):
        if self.refund_rate_gte > 1:
            raise ValueError("refund rate must be at most one")
        return self


class NewAccountRule(ContractModel):
    account_age_days_lte: NonNegativeInt = 30
    same_reason_claims_90d_gte: PositiveInt = 2
    points: NonNegativeInt = 30


class UserRiskRules(ContractModel):
    repeated_same_reason_claims: RepeatedClaimsRule = Field(default_factory=RepeatedClaimsRule)
    high_refund_rate: RefundRateRule = Field(default_factory=RefundRateRule)
    new_account_repeated_claims: NewAccountRule = Field(default_factory=NewAccountRule)


class UserRiskConfig(ContractModel):
    version: OpaqueRef = "user-risk:1.0"
    low_max_score: NonNegativeInt = 39
    medium_max_score: NonNegativeInt = 59
    rules: UserRiskRules = Field(default_factory=UserRiskRules)

    @model_validator(mode="after")
    def _thresholds(self):
        if self.low_max_score >= self.medium_max_score:
            raise ValueError("risk thresholds must be ordered")
        return self

    @property
    def fingerprint(self) -> str:
        from .review_gates import _canonical_decimal
        payload = self.model_dump(mode="json")
        payload["rules"]["high_refund_rate"]["refund_rate_gte"] = _canonical_decimal(self.rules.high_refund_rate.refund_rate_gte)
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class UserRiskSnapshot(ContractModel):
    snapshot_ref: OpaqueRef
    case_ref: OpaqueRef
    user_ref: OpaqueRef
    reason_code: ReasonCode
    as_of: UTCDateTime
    account_age_days: NonNegativeInt
    orders_90d: NonNegativeInt
    same_reason_claims_90d: NonNegativeInt
    refunded_orders_90d: NonNegativeInt
    created_at: UTCDateTime

    @model_validator(mode="after")
    def _counts(self):
        if self.refunded_orders_90d > self.orders_90d:
            raise ValueError("refunded orders cannot exceed orders")
        return self


class UserRiskGateResult(ContractModel):
    config_version: OpaqueRef
    config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["PASS", "HUMAN_REQUIRED", "NOT_APPLICABLE"]
    risk_level: UserRiskLevel
    score: NonNegativeInt
    tags: list[RiskTag]
    matched_rules: list[OpaqueRef]
    reason: Literal["HIGH_USER_RISK", "USER_RISK_UNAVAILABLE"] | None
    snapshot_ref: OpaqueRef | None

    @model_validator(mode="after")
    def _consistent(self):
        if len(set(self.tags)) != len(self.tags) or self.matched_rules != [tag.value for tag in self.tags]:
            raise ValueError("risk tags and rules must be unique and aligned")
        if self.status == "PASS":
            valid = self.risk_level in {UserRiskLevel.LOW, UserRiskLevel.MEDIUM} and self.reason is None and self.snapshot_ref is not None
        elif self.status == "NOT_APPLICABLE":
            valid = self.reason is None and self.snapshot_ref is None and self.risk_level is UserRiskLevel.UNKNOWN and self.score == 0 and not self.tags
        elif self.reason == "HIGH_USER_RISK":
            valid = self.risk_level is UserRiskLevel.HIGH and self.snapshot_ref is not None
        else:
            valid = self.reason == "USER_RISK_UNAVAILABLE" and self.risk_level is UserRiskLevel.UNKNOWN and self.score == 0 and not self.tags
        if not valid:
            raise ValueError("inconsistent user risk gate")
        return self


def load_user_risk_config(path: str | None = None) -> UserRiskConfig:
    if path is None:
        return UserRiskConfig()
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict) or set(payload) != {"version", "low_max_score", "medium_max_score", "rules"}:
        raise ValueError("risk config requires explicit version, thresholds and rules")
    return UserRiskConfig.model_validate(payload)


def unavailable_user_risk_gate(config: UserRiskConfig) -> UserRiskGateResult:
    return UserRiskGateResult(config_version=config.version, config_hash=config.fingerprint,
        status="HUMAN_REQUIRED", risk_level="UNKNOWN", score=0, tags=[], matched_rules=[],
        reason="USER_RISK_UNAVAILABLE", snapshot_ref=None)


def not_applicable_user_risk_gate(config: UserRiskConfig) -> UserRiskGateResult:
    return UserRiskGateResult(config_version=config.version, config_hash=config.fingerprint,
        status="NOT_APPLICABLE", risk_level="UNKNOWN", score=0, tags=[], matched_rules=[],
        reason=None, snapshot_ref=None)


def evaluate_user_risk(action: ResolutionAction, snapshot: UserRiskSnapshot, config: UserRiskConfig) -> UserRiskGateResult:
    if action is ResolutionAction.DECLINE:
        return not_applicable_user_risk_gate(config)
    rules = config.rules
    repeated, rate, new = rules.repeated_same_reason_claims, rules.high_refund_rate, rules.new_account_repeated_claims
    matches = [
        (RiskTag.REPEATED_SAME_REASON_CLAIMS, snapshot.same_reason_claims_90d >= repeated.same_reason_claims_90d_gte, repeated.points),
        (RiskTag.HIGH_REFUND_RATE, snapshot.orders_90d >= rate.minimum_orders_90d and Decimal(snapshot.refunded_orders_90d) >= rate.refund_rate_gte * snapshot.orders_90d, rate.points),
        (RiskTag.NEW_ACCOUNT_REPEATED_CLAIMS, snapshot.account_age_days <= new.account_age_days_lte and snapshot.same_reason_claims_90d >= new.same_reason_claims_90d_gte, new.points),
    ]
    tags = [tag for tag, matched, _ in matches if matched]
    score = sum(points for _, matched, points in matches if matched)
    level = UserRiskLevel.LOW if score <= config.low_max_score else UserRiskLevel.MEDIUM if score <= config.medium_max_score else UserRiskLevel.HIGH
    high = level is UserRiskLevel.HIGH
    return UserRiskGateResult(config_version=config.version, config_hash=config.fingerprint,
        status="HUMAN_REQUIRED" if high else "PASS", risk_level=level, score=score,
        tags=tags, matched_rules=[tag.value for tag in tags],
        reason="HIGH_USER_RISK" if high else None, snapshot_ref=snapshot.snapshot_ref)
