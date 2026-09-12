from datetime import UTC, datetime
import pytest
from pydantic import ValidationError
from return_agent_contracts.enums import ResolutionAction
from return_agent_contracts.user_risk import (
    UserRiskConfig, UserRiskSnapshot, UserRiskGateResult, evaluate_user_risk,
    unavailable_user_risk_gate,
)


def snapshot(**updates):
    values = dict(snapshot_ref="S1", case_ref="C1", user_ref="U1", reason_code="ITEM_DAMAGED",
        as_of=datetime(2026, 9, 1, tzinfo=UTC), created_at=datetime(2026, 9, 2, tzinfo=UTC),
        account_age_days=180, orders_90d=8, same_reason_claims_90d=1, refunded_orders_90d=1)
    return UserRiskSnapshot(**(values | updates))


@pytest.mark.parametrize("claims,refunds,score,level,status", [
    (1,1,0,"LOW","PASS"), (3,1,40,"MEDIUM","PASS"), (3,4,65,"HIGH","HUMAN_REQUIRED"),
])
def test_personas(claims, refunds, score, level, status):
    result = evaluate_user_risk(ResolutionAction.FULL_REFUND, snapshot(same_reason_claims_90d=claims, refunded_orders_90d=refunds), UserRiskConfig())
    assert (result.score, result.risk_level, result.status) == (score,level,status)
    assert result.matched_rules == [tag.value for tag in result.tags]


@pytest.mark.parametrize("score,level,status", [(39,"LOW","PASS"), (40,"MEDIUM","PASS"), (59,"MEDIUM","PASS"), (60,"HIGH","HUMAN_REQUIRED")])
def test_score_boundaries(score, level, status):
    config = UserRiskConfig(rules={"repeated_same_reason_claims":{"points":score}})
    result = evaluate_user_risk(ResolutionAction.FULL_REFUND, snapshot(same_reason_claims_90d=3), config)
    assert (result.risk_level, result.status) == (level,status)


def test_minimum_orders_zero_and_exact_ratio():
    for orders, refunds in [(0,0),(4,4)]:
        result = evaluate_user_risk(ResolutionAction.FULL_REFUND, snapshot(orders_90d=orders,refunded_orders_90d=refunds), UserRiskConfig())
        assert result.score == 0
    assert evaluate_user_risk(ResolutionAction.FULL_REFUND, snapshot(orders_90d=5,refunded_orders_90d=2), UserRiskConfig()).score == 25


def test_new_account_and_ordered_tags():
    result = evaluate_user_risk(ResolutionAction.FULL_REFUND, snapshot(account_age_days=30,same_reason_claims_90d=3,refunded_orders_90d=4), UserRiskConfig())
    assert result.score == 95
    assert result.matched_rules == ["REPEATED_SAME_REASON_CLAIMS","HIGH_REFUND_RATE","NEW_ACCOUNT_REPEATED_CLAIMS"]


def test_unknown_decline_and_invalid_gate():
    config = UserRiskConfig()
    assert unavailable_user_risk_gate(config).status == "HUMAN_REQUIRED"
    assert evaluate_user_risk(ResolutionAction.DECLINE,snapshot(),config).status == "NOT_APPLICABLE"
    payload = unavailable_user_risk_gate(config).model_dump()
    for updates in ({"status":"PASS"},{"status":"BLOCK"},{"risk_level":"HIGH"},{"score":1}):
        with pytest.raises(ValidationError):
            UserRiskGateResult.model_validate(payload | updates)


def test_config_strict_and_canonical():
    one = UserRiskConfig(rules={"high_refund_rate":{"refund_rate_gte":"0.40"}})
    two = UserRiskConfig(rules={"high_refund_rate":{"refund_rate_gte":"0.400"}})
    assert one.fingerprint == two.fingerprint
    for payload in ({"extra":1},{"low_max_score":60},{"rules":{"high_refund_rate":{"refund_rate_gte":"1.1"}}}):
        with pytest.raises(ValidationError):
            UserRiskConfig.model_validate(payload)
    with pytest.raises(ValidationError):
        snapshot(orders_90d=1,refunded_orders_90d=2)
