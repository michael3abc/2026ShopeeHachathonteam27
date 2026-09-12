import hashlib
import json
from decimal import Decimal

from .domain import Action, ReviewGateResult, ReviewResult, ReviewerGateConfig
from .primitives import parse_amount


def normalized_decimal(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def gate_fingerprint(config: ReviewerGateConfig) -> str:
    config = ReviewerGateConfig.model_validate(config)
    payload = {"version": config.version, "thresholds": {key: normalized_decimal(value) for key, value in sorted(config.thresholds.items())}}
    # Gate identity deliberately uses JSON's default separators per wire contract.
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def evaluate_gate(action: Action, amount: Decimal, currency: str, config: ReviewerGateConfig) -> ReviewGateResult:
    config = ReviewerGateConfig.model_validate(config)
    amount = parse_amount(amount)
    threshold = config.thresholds.get(currency)
    if action == "DECLINE":
        if amount != 0:
            raise ValueError("DECLINE cannot carry a refund amount")
        status, reason, threshold = "NOT_APPLICABLE", None, None
    elif action != "FULL_REFUND":
        raise ValueError("Unknown refund action")
    elif threshold is None:
        status, reason = "HUMAN_REQUIRED", "CURRENCY_THRESHOLD_UNCONFIGURED"
    elif amount > threshold:
        status, reason = "HUMAN_REQUIRED", "HIGH_VALUE_ITEM"
    else:
        status, reason = "PASS", None
    return ReviewGateResult(
        config_version=config.version, config_hash=gate_fingerprint(config),
        status=status, reason=reason, amount=amount, currency=currency, threshold=threshold,
    )


def gate_after_review(review: ReviewResult, action: Action, amount: Decimal, currency: str, config: ReviewerGateConfig) -> ReviewGateResult | None:
    if review.verdict == "REVISE":
        return None
    return evaluate_gate(action, amount, currency, config)
