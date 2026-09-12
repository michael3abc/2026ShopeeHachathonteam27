"""Export/check synthetic cross-object examples using baseline semantic validators."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path

from pydantic import TypeAdapter
from return_agent_contracts import models as m
from return_agent_contracts import validation as v
from return_agent_contracts.activity import ActivityEvent, ActivityEmission, NarrationJob
from return_agent_contracts.review_gates import ReviewerGateConfig, evaluate_review_gate
from return_agent_contracts.enums import ResolutionAction
from return_agent_contracts.ui import CreateCaseRequest, SendMessageRequest, ReviewDecision

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs/reconstruction"


def baseline_candidate(candidate):
    """Explicit v1 snapshot projection, not a production compatibility path."""
    payload = candidate.model_dump(mode="json")
    assert payload.pop("applicability_limits") == []
    assert payload.pop("prohibited_inferences") == []
    payload["source_revision_event_refs"] = payload.pop("source_event_refs")
    return payload


def validate_baseline_candidate(raw):
    payload = dict(raw)
    assert "source_event_refs" not in payload
    payload["source_event_refs"] = payload.pop("source_revision_event_refs")
    v.validate_memory_candidate(m.MemoryCandidate.model_validate(payload))


def build():
    spec = importlib.util.spec_from_file_location("contract_fixtures", ROOT / "apps/contracts/tests/contracts/fixtures.py")
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    snapshot, policy, assessment, draft = fixtures.order_snapshot(), fixtures.policy_bundle(), fixtures.supported_assessment(), fixtures.proposed_decision_draft()
    handoff, review = fixtures.proposed_handoff(), fixtures.approved_review()
    handoff.agent_prompt_version = "resolver:1.1"
    review.reviewer_prompt_version = "reviewer:2.1"
    revised = fixtures.revised_review()
    revised.reviewer_prompt_version = "reviewer:2.1"
    config = ReviewerGateConfig()
    proposals = [handoff.model_copy(update={"handoff_id": f"HANDOFF-ROUND-{i}", "revision_round": i}) for i in range(4)]
    events = [m.DecisionRevisionEvent(event_id=f"REV-{i}", case_ref=handoff.case_ref, handoff_before_ref=proposals[i].handoff_id, review_result=revised, revision_round=i+1, created_at=fixtures.TIME) for i in range(3)]
    dossier = m.HumanReviewDossier(claimed_line_item_ids=["LI-002"], claim_registry_version="claim-registry:1.0", order_snapshot=snapshot, policy_bundle=policy, proposal_history=proposals, review_history=[revised]*4, revision_events=events)
    high_snapshot = snapshot.model_copy(deep=True)
    high_snapshot.line_items[1].refundable_amount = "6200"
    high_snapshot.refundable_amount_max = "6900"
    high_snapshot = m.OrderSnapshot.model_validate(high_snapshot.model_dump(mode="json", warnings=False))
    high_handoff = handoff.model_copy(deep=True)
    high_handoff.proposed_decision.amount = high_snapshot.line_items[1].refundable_amount
    high_gate = evaluate_review_gate(ResolutionAction.FULL_REFUND, high_handoff.proposed_decision.amount, "TWD", config)
    high = m.HumanReviewDossier(claimed_line_item_ids=["LI-002"], claim_registry_version="claim-registry:1.0", routing_reason="HIGH_VALUE_ITEM", review_gate=high_gate, order_snapshot=high_snapshot, policy_bundle=policy, proposal_history=[high_handoff], review_history=[review])
    common = dict(case_ref="CASE-001", run_id="run-demo", scope="CASE", node="reviewer", operation_id="op-review-node", attempt_id="attempt-demo", occurred_at=fixtures.TIME)
    activities = [ActivityEvent(**common, event_id="evt-start", seq=1, payload={"type": "node", "phase": "STARTED", "name": "reviewer"}), ActivityEvent(**common, event_id="evt-complete", seq=2, payload={"type": "node", "phase": "COMPLETED", "name": "reviewer", "duration_ms": 140}), ActivityEvent(**common, event_id="evt-summary", seq=3, payload={"type": "node_summary", "facts": {"verdict": "APPROVE", "next_node": "emit_resolution_handoff"}}), ActivityEvent(**common, event_id="evt-disabled", seq=4, payload={"type": "narration", "source_event_id": "evt-summary", "status": "UNAVAILABLE", "error_code": "NARRATION_DISABLED_OFFLINE_DEMO"})]
    return {"synthetic": True, "case_context": fixtures.case_context().model_dump(mode="json"), "order_snapshot": snapshot.model_dump(mode="json"), "policy_bundle": policy.model_dump(mode="json"), "claimed_line_item_ids": ["LI-002"], "assessment": assessment.model_dump(mode="json"), "draft": draft.model_dump(mode="json"), "handoff": handoff.model_dump(mode="json"), "review": review.model_dump(mode="json"), "revision_dossier": dossier.model_dump(mode="json"), "amount_dossier": high.model_dump(mode="json"), "candidate": baseline_candidate(fixtures.memory_candidate()), "activities": [a.model_dump(mode="json") for a in activities]}


def validate(raw):
    context = m.CaseContext.model_validate(raw["case_context"])
    snapshot = m.OrderSnapshot.model_validate(raw["order_snapshot"])
    policy = m.PolicyBundle.model_validate(raw["policy_bundle"])
    handoff = m.ProposedDecisionHandoff.model_validate(raw["handoff"])
    assessment = TypeAdapter(m.EvidenceAssessment).validate_python(raw["assessment"])
    draft = TypeAdapter(m.ProposedDecisionDraft).validate_python(raw["draft"])
    review = TypeAdapter(m.ReviewResult).validate_python(raw["review"])
    claimed = raw["claimed_line_item_ids"]
    v.validate_case_context_load_result(context.case_ref, m.CaseContextLoadResult(case_context=context, order_snapshot=snapshot))
    v.validate_applicable_policy_bundle(context, policy)
    v.validate_evidence_assessment(assessment, policy, snapshot, claimed)
    v.validate_proposed_decision_draft(draft, assessment, policy, snapshot, claimed)
    v.validate_proposed_decision_handoff(handoff, policy, snapshot)
    v.validate_review_result(review, handoff, policy, snapshot, claimed)
    validate_baseline_candidate(raw["candidate"])
    for key in ("revision_dossier", "amount_dossier"):
        dossier = m.HumanReviewDossier.model_validate(raw[key])
        v.validate_human_review_entry(dossier.proposal_history[-1], dossier.review_history[-1], dossier, ReviewerGateConfig())
        for proposal in dossier.proposal_history:
            v.validate_proposed_decision_handoff(proposal, dossier.policy_bundle, dossier.order_snapshot)
    for item in raw["activities"]:
        ActivityEvent.model_validate(item)
    source = ActivityEmission.model_validate({k: value for k, value in raw["activities"][2].items() if k != "seq"})
    NarrationJob(job_id="narration:evt-summary", source=source)
    rejected = 0
    for field in ("policy_bundle_version", "order_snapshot_ref", "claim_registry_version", "case_ref", "revision_round"):
        changed = copy.deepcopy(raw["revision_dossier"])
        changed["proposal_history"][0][field] = 1 if field == "revision_round" else "incorrect"
        try:
            m.HumanReviewDossier.model_validate(changed)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError(field)
    for field, value in (("handoff_before_ref", "other"), ("revision_round", 3), ("case_ref", "other")):
        changed = copy.deepcopy(raw["revision_dossier"])
        changed["revision_events"][0][field] = value
        try:
            m.HumanReviewDossier.model_validate(changed)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError(field)
    from decimal import Decimal
    for currency, amount, action, expected in (("TWD", "4999.99", "FULL_REFUND", "PASS"), ("TWD", "5000", "FULL_REFUND", "PASS"), ("TWD", "5000.01", "FULL_REFUND", "HUMAN_REQUIRED"), ("SGD", "200", "FULL_REFUND", "PASS"), ("SGD", "200.01", "FULL_REFUND", "HUMAN_REQUIRED"), ("USD", "1", "FULL_REFUND", "HUMAN_REQUIRED"), ("TWD", "0", "DECLINE", "NOT_APPLICABLE")):
        assert evaluate_review_gate(ResolutionAction(action), Decimal(amount), currency, ReviewerGateConfig()).status == expected
    return rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    expected = build()
    path = PACKAGE / "examples/semantic-fixtures.json"
    encoded = json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.export:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded)
        frames = "".join(f"id: {a['seq']}\nevent: activity\ndata: {json.dumps(a, ensure_ascii=False, separators=(',', ':'))}\n\n" for a in expected["activities"])
        path.with_name("activity.sse").write_text(frames + ": end of synthetic sample\n")
    assert path.read_text() == encoded, "semantic fixture drift"
    rejected = validate(json.loads(path.read_text()))
    from return_agent.capabilities.evidence import load_evidence_fixture
    from return_agent.capabilities.policy import load_policy_fixture
    demo = PACKAGE / "assets/demo"
    evidence = load_evidence_fixture(demo / "evidence.json.example")
    policies = load_policy_fixture(demo / "policy.json.example")
    for letter in "abc":
        case = json.loads((demo / f"case-{letter}.json.example").read_text())
        loaded = m.CaseContextLoadResult.model_validate({k: case[k] for k in ("case_context", "order_snapshot")})
        v.validate_case_context_load_result(loaded.case_context.case_ref, loaded)
        CreateCaseRequest.model_validate(case["create_case_request"])
        m.UserTurn.model_validate(case["initial_user_turn"])
        for message in case["followup_messages"]:
            SendMessageRequest.model_validate(message)
        subjects = {item.line_item_id for item in loaded.order_snapshot.line_items}
        applicable = [c for doc in policies for c in doc.contract_clauses() if set(c.applicable_conditions.categories).intersection(item.category_ref for item in loaded.order_snapshot.line_items)]
        bundle = m.PolicyBundle(policy_bundle_version="bundle-synthetic", retrieval_status="OK", retrieved_at=loaded.case_context.case_opened_at, clauses=applicable)
        v.validate_applicable_policy_bundle(loaded.case_context, bundle)
        refs = case["create_case_request"]["attached_artifact_refs"] + [ref for message in case["followup_messages"] for ref in message["attached_artifact_refs"]]
        by_ref = {item.artifact_ref: item for item in evidence}
        assert all(ref in by_ref and by_ref[ref].subject in subjects for ref in refs)
    preload = json.loads((demo / "memory-preload.json.example").read_text())
    validate_baseline_candidate(preload["candidate"])
    for template in json.loads((demo / "human-review.json.example").read_text()):
        request = dict(template["request"], handoff_id="synthetic-bound-handoff")
        TypeAdapter(ReviewDecision).validate_python(request)
    print(json.dumps({"semantic_examples": "PASS", "negative_dossier_mutations_rejected": rejected, "gate_boundaries": 7, "demo_cases": 3, "evidence_fixtures": len(evidence), "policy_documents": len(policies)}))


if __name__ == "__main__":
    main()
