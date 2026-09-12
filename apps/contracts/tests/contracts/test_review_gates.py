from decimal import Decimal
import pytest
from pydantic import ValidationError
from return_agent_contracts.enums import ResolutionAction
from return_agent_contracts.review_gates import ReviewerGateConfig, evaluate_review_gate, load_reviewer_gate_config

@pytest.mark.parametrize("currency,amount,status,reason", [
    ("TWD", "4999.99", "PASS", None), ("TWD", "5000", "PASS", None),
    ("TWD", "5000.01", "HUMAN_REQUIRED", "HIGH_VALUE_ITEM"),
    ("SGD", "199.99", "PASS", None), ("SGD", "200", "PASS", None),
    ("SGD", "200.01", "HUMAN_REQUIRED", "HIGH_VALUE_ITEM"),
    ("USD", "1", "HUMAN_REQUIRED", "CURRENCY_THRESHOLD_UNCONFIGURED"),
])
def test_currency_specific_exact_decimal_boundaries(currency, amount, status, reason):
    result = evaluate_review_gate(ResolutionAction.FULL_REFUND, Decimal(amount), currency, ReviewerGateConfig())
    assert (result.status, result.reason) == (status, reason)
    assert result.amount == Decimal(amount)

def test_decline_is_not_subject_to_monetary_authorization():
    result = evaluate_review_gate(ResolutionAction.DECLINE, Decimal(0), "USD", ReviewerGateConfig())
    assert result.status == "NOT_APPLICABLE" and result.reason is None

@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", 5000.0])
def test_invalid_config_never_becomes_a_default_threshold(value):
    with pytest.raises(ValidationError):
        ReviewerGateConfig(thresholds={"TWD": value})

def test_config_hash_detects_content_changes_with_same_version():
    assert ReviewerGateConfig().fingerprint != ReviewerGateConfig(thresholds={"TWD": "6000"}).fingerprint

def test_missing_explicit_config_fails_instead_of_defaulting(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_reviewer_gate_config(str(tmp_path / "missing.json"))
