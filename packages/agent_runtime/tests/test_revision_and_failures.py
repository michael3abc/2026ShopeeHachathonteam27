from __future__ import annotations

import pytest
from return_agent_contracts.enums import ClaimId, ClaimStatus, OutcomeSource
from return_agent_contracts.models import (
    FailedVerificationResult,
    MemoryCandidateOutput,
    MemorySkipOutput,
    PolicyBundle,
    ResolverConflictOutput,
    ResolverEvidenceRequestOutput,
    RevisedReviewResult,
    RevisionReason,
    UnavailableVerificationResult,
    VerificationIssue,
)
from return_agent_contracts.runtime import (
    AgentInterruptKind,
    AgentRunStatus,
    EvidenceResume,
)
from return_agent_runtime import MemoryDistiller
from return_agent_runtime.model import ModelTask
from return_agent_runtime.state import MemoryRetrievalStatus

from .conftest import (
    TIME,
    approved_review,
    evidence_item,
    findings,
    four_verifications,
    make_runtime,
    policy_bundle,
    proposal_output,
    queue_human_review,
    supported_assessment,
    user_turn,
)
from .fakes import QueuedModel
from .test_interrupt_resume import complete_intake


def verification_issue(code="BAD_RETURN") -> VerificationIssue:
    return VerificationIssue(
        code=code,
        message="Return decision violates a hard rule.",
        field_path="proposed_decision.return_decision",
    )


def revised_review(*, findings_override=None, code="DECISION_INCONSISTENT"):
    return RevisedReviewResult(
        verdict="REVISE",
        reviewer_claim_findings=findings_override or findings(),
        revision_reasons=[
            RevisionReason(
                code=code,
                message="The proposal needs a concrete correction.",
                policy_refs=["POLICY-12:v3#4.2"],
                evidence_refs=["EV-002"],
                subject="LI-002",
                required_change="Correct the proposal using the cited evidence.",
            )
        ],
        reviewer_prompt_version="reviewer:1.0",
        reviewed_at=TIME,
    )


def queue_initial_resolution(model: QueuedModel) -> None:
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.ASSESS, supported_assessment())
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())


@pytest.mark.asyncio
async def test_closed_revision_prepares_and_distills_memory_candidate():
    model = QueuedModel()
    queue_initial_resolution(model)
    model.queue(
        ModelTask.PROPOSE_OR_REVISE,
        proposal_output(rationale="Reviewer feedback was applied."),
    )
    model.queue(ModelTask.REVIEW, revised_review(), approved_review())
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        verification_results=[
            {"status": "PASS", "issues": [], "verification_version": "verify:1"},
            {"status": "PASS", "issues": [], "verification_version": "verify:1"},
        ],
        evidence_items={evidence.artifact_ref: evidence},
    )

    completed = runtime.start(
        thread_id="THREAD-MEMORY",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert completed.status is AgentRunStatus.COMPLETED
    memory_input = await runtime.aget_memory_distillation_input(
        thread_id="THREAD-MEMORY"
    )
    assert memory_input is not None
    assert len(memory_input.proposal_history) == 2
    assert len(memory_input.revision_events) == 1

    model.queue(
        ModelTask.MEMORY_DISTILL,
        {
            "result_type": "CREATE_CANDIDATE",
            "candidate": {
                "memory_id": "MODEL-MEMORY-ID",
                "retrieval_summary": "Reviewer correction required; apply the cited correction before review.",
                "trigger_conditions": ["The first proposal needs reviewer correction."],
                "recommended_behavior": "Apply the cited correction before review.",
                "rationale": "The revised proposal was approved.",
                "source_case_refs": ["MODEL-CASE"],
                "source_revision_event_refs": ["MODEL-REVISION"],
                "policy_version": "MODEL-POLICY",
                "claim_registry_version": "model-registry:9.0",
                "scope": {
                    "market": "MODEL-MARKET",
                    "reason_codes": ["ITEM_DAMAGED"],
                    "claim_ids": ["DAMAGE_PRESENT_ON_ARRIVAL"],
                    "categories": ["CAT-AUDIO-SPEAKERS"],
                },
                "confidence": 0.8,
                "status": "CANDIDATE",
            },
        },
    )
    output = MemoryDistiller(model).distill(memory_input)
    assert isinstance(output, MemoryCandidateOutput)
    assert output.candidate.memory_id != "MODEL-MEMORY-ID"
    assert output.candidate.source_case_refs == ["CASE-001"]
    assert output.candidate.policy_version == "POLICY-12:v3"
    assert output.candidate.claim_registry_version == "claim-registry:1.0"
    assert output.candidate.scope.market == "TW"
    distillation_call = model.calls[-1]
    assert distillation_call.payload["allowed_scope"] == {
        "market": "TW",
        "reason_codes": ["ITEM_DAMAGED"],
        "claim_ids": [
            "DELIVERY_CONFIRMED",
            "ORDER_WITHIN_RETURN_WINDOW",
            "ITEM_PHYSICALLY_DAMAGED",
            "DAMAGE_PRESENT_ON_ARRIVAL",
        ],
        "categories": ["CAT-AUDIO-SPEAKERS"],
    }

    leaked = output.candidate.model_copy(
        update={"recommended_behavior": "Call 0912-345-678 for more evidence."}
    )
    model.queue(
        ModelTask.MEMORY_DISTILL,
        MemoryCandidateOutput(result_type="CREATE_CANDIDATE", candidate=leaked),
    )
    with pytest.raises(ValueError, match="PII or a raw artifact"):
        MemoryDistiller(model).distill(memory_input)

    out_of_scope = output.candidate.model_copy(
        update={
            "scope": output.candidate.scope.model_copy(
                update={"categories": ["CAT-UNRELATED"]}
            )
        }
    )
    model.queue(
        ModelTask.MEMORY_DISTILL,
        MemoryCandidateOutput(result_type="CREATE_CANDIDATE", candidate=out_of_scope),
    )
    with pytest.raises(ValueError, match="category scope exceeds claimed items"):
        MemoryDistiller(model).distill(memory_input)


@pytest.mark.asyncio
async def test_memory_distiller_skips_unknown_claim_registry_version():
    model = QueuedModel()
    queue_initial_resolution(model)
    model.queue(
        ModelTask.PROPOSE_OR_REVISE,
        proposal_output(rationale="Reviewer feedback was applied."),
    )
    model.queue(ModelTask.REVIEW, revised_review(), approved_review())
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        verification_results=[
            {"status": "PASS", "issues": [], "verification_version": "verify:1"},
            {"status": "PASS", "issues": [], "verification_version": "verify:1"},
        ],
        evidence_items={evidence.artifact_ref: evidence},
    )
    runtime.start(
        thread_id="THREAD-MEMORY-REGISTRY",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    memory_input = await runtime.aget_memory_distillation_input(
        thread_id="THREAD-MEMORY-REGISTRY"
    )
    assert memory_input is not None
    latest = memory_input.proposal_history[-1].model_copy(
        update={"claim_registry_version": "unknown-registry:9.0"}
    )
    incompatible = memory_input.model_copy(
        update={"proposal_history": [*memory_input.proposal_history[:-1], latest]}
    )

    output = MemoryDistiller(model).distill(incompatible)

    assert isinstance(output, MemorySkipOutput)
    assert output.reason_code == "CLAIM_REGISTRY_VERSION_UNKNOWN"


def test_verification_fail_returns_issues_to_new_proposal():
    model = QueuedModel()
    queue_initial_resolution(model)
    model.queue(
        ModelTask.PROPOSE_OR_REVISE,
        proposal_output(rationale="Verification feedback was applied."),
    )
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    issue = verification_issue()
    runtime, providers = make_runtime(
        model=model,
        verification_results=[
            FailedVerificationResult(
                status="FAIL", issues=[issue], verification_version="verify:1"
            ),
            {
                "status": "PASS",
                "issues": [],
                "verification_version": "verify:1",
            },
        ],
        evidence_items={evidence.artifact_ref: evidence},
    )

    completed = runtime.start(
        thread_id="THREAD-VERIFY-RETRY",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )

    assert completed.status is AgentRunStatus.COMPLETED
    assert len(providers["verification"].calls) == 2
    assert (
        providers["verification"].calls[0].handoff_id
        != providers["verification"].calls[1].handoff_id
    )
    proposal_calls = [
        call for call in model.calls if call.task is ModelTask.PROPOSE_OR_REVISE
    ]
    assert proposal_calls[1].payload["verification_feedback"][0]["code"] == "BAD_RETURN"
    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-VERIFY-RETRY"}}
    ).values
    assert state["verification_round"] == 1


@pytest.mark.asyncio
async def test_observed_revision_loop_reports_each_repeated_node_task():
    model = QueuedModel()
    queue_initial_resolution(model)
    model.queue(
        ModelTask.PROPOSE_OR_REVISE,
        proposal_output(rationale="Verification feedback was applied."),
    )
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    issue = verification_issue()
    runtime, _ = make_runtime(
        model=model,
        verification_results=[
            FailedVerificationResult(
                status="FAIL", issues=[issue], verification_version="verify:1"
            ),
            {
                "status": "PASS",
                "issues": [],
                "verification_version": "verify:1",
            },
        ],
        evidence_items={evidence.artifact_ref: evidence},
    )
    observations = []

    result = await runtime.astart(
        thread_id="THREAD-OBSERVED-VERIFY-RETRY",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
        observer=observations.append,
    )

    assert result.status is AgentRunStatus.COMPLETED
    proposal_enters = [
        item
        for item in observations
        if item.node == "propose_decision" and item.phase == "ENTER"
    ]
    assert len(proposal_enters) == 2
    assert len({item.task_ref for item in proposal_enters}) == 2
    phases_by_task = {
        item.task_ref: {
            event.phase for event in observations if event.task_ref == item.task_ref
        }
        for item in proposal_enters
    }
    assert all(phases == {"ENTER", "EXIT"} for phases in phases_by_task.values())


def test_verification_unavailable_and_retry_budget_fail_closed():
    evidence = evidence_item()

    unavailable_model = QueuedModel()
    queue_initial_resolution(unavailable_model)
    unavailable_runtime, _ = make_runtime(
        model=unavailable_model,
        verification_results=[
            UnavailableVerificationResult(
                status="UNAVAILABLE", issues=[], verification_version="verify:1"
            )
        ],
        evidence_items={evidence.artifact_ref: evidence},
    )
    unavailable = unavailable_runtime.start(
        thread_id="THREAD-VERIFY-UNAVAILABLE",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert unavailable.manual_escalation.escalation_reason == "VERIFICATION_UNAVAILABLE"

    budget_model = QueuedModel()
    queue_initial_resolution(budget_model)
    budget_model.queue(
        ModelTask.PROPOSE_OR_REVISE,
        proposal_output(rationale="Revision one."),
        proposal_output(rationale="Revision two."),
    )
    issue = verification_issue()
    budget_runtime, _ = make_runtime(
        model=budget_model,
        verification_results=[
            FailedVerificationResult(
                status="FAIL", issues=[issue], verification_version="verify:1"
            )
            for _ in range(3)
        ],
        evidence_items={evidence.artifact_ref: evidence},
    )
    budget = budget_runtime.start(
        thread_id="THREAD-VERIFY-BUDGET",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert budget.manual_escalation.escalation_reason == "VERIFICATION_BUDGET_EXCEEDED"
    assert budget.manual_escalation.accumulated_context.verification_round == 2


def test_reviewer_revision_evidence_interrupt_preserves_feedback_and_history():
    model = QueuedModel()
    queue_initial_resolution(model)
    reviewer_findings = findings()
    reviewer_findings[-1] = reviewer_findings[-1].model_copy(
        update={
            "status": ClaimStatus.UNSUPPORTED,
            "supporting_evidence_refs": ["EV-002"],
            "explanation": "The close-up does not establish arrival condition.",
        }
    )
    model.queue(
        ModelTask.REVIEW,
        revised_review(
            findings_override=reviewer_findings,
            code="EVIDENCE_INSUFFICIENT",
        ),
        approved_review(),
    )
    request = ResolverEvidenceRequestOutput(
        result_type="REQUEST_EVIDENCE",
        evidence_request={
            "request_id": "EREQ-REVIEW",
            "missing_claims": [
                {
                    "claim_id": ClaimId.DAMAGE_PRESENT_ON_ARRIVAL,
                    "subject": "LI-002",
                }
            ],
            "accepted_evidence_types": ["IMAGE", "VIDEO"],
            "user_message": "請補充外箱與受損商品同框的照片。",
            "policy_refs": ["POLICY-12:v3#4.2"],
        },
    )
    model.queue(
        ModelTask.PROPOSE_OR_REVISE,
        request,
        proposal_output(rationale="New evidence addresses reviewer feedback."),
    )
    model.queue(ModelTask.ASSESS, supported_assessment())
    close_up = evidence_item()
    wide = evidence_item("artifact://evidence/EV-003", evidence_id="EV-003")
    runtime, providers = make_runtime(
        model=model,
        verification_results=[
            {"status": "PASS", "issues": [], "verification_version": "verify:1"},
            {"status": "PASS", "issues": [], "verification_version": "verify:1"},
        ],
        evidence_items={
            close_up.artifact_ref: close_up,
            wide.artifact_ref: wide,
        },
    )

    paused = runtime.start(
        thread_id="THREAD-REVIEW-EVIDENCE",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[close_up.artifact_ref]),
    )
    assert paused.interrupt_kind is AgentInterruptKind.EVIDENCE_REQUEST
    paused_state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-REVIEW-EVIDENCE"}}
    ).values
    assert paused_state["revision_round"] == 1
    assert paused_state["pending_review_result"].verdict == "REVISE"
    assert len(paused_state["revision_events"]) == 1

    completed = runtime.resume(
        thread_id="THREAD-REVIEW-EVIDENCE",
        payload=EvidenceResume(
            kind="EVIDENCE_REQUEST", artifact_refs=[wide.artifact_ref]
        ),
    )

    assert completed.status is AgentRunStatus.COMPLETED
    assert len(providers["verification"].calls) == 2
    first, second = providers["verification"].calls
    assert first.handoff_id != second.handoff_id
    assert {item.evidence_id for item in second.evidence_bundle} == {"EV-002", "EV-003"}
    final_state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-REVIEW-EVIDENCE"}}
    ).values
    assert len(final_state["review_history"]) == 2
    assert final_state["pending_review_result"] is None
    proposal_calls = [
        call for call in model.calls if call.task is ModelTask.PROPOSE_OR_REVISE
    ]
    assert proposal_calls[1].payload["review_feedback"]["verdict"] == "REVISE"
    assert proposal_calls[2].payload["review_feedback"]["verdict"] == "REVISE"


def test_reviewer_revision_budget_enters_human_review():
    model = QueuedModel()
    queue_initial_resolution(model)
    model.queue(
        ModelTask.PROPOSE_OR_REVISE,
        proposal_output(rationale="Reviewer revision one."),
        proposal_output(rationale="Reviewer revision two."),
        proposal_output(rationale="Reviewer revision three."),
    )
    model.queue(
        ModelTask.REVIEW,
        revised_review(),
        revised_review(),
        revised_review(),
        revised_review(),
    )
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        human_results=[None],
        verification_results=[
            {"status": "PASS", "issues": [], "verification_version": "verify:1"}
            for _ in range(4)
        ],
        evidence_items={evidence.artifact_ref: evidence},
    )

    result = runtime.start(
        thread_id="THREAD-REVIEW-BUDGET",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )

    assert result.interrupt_kind is AgentInterruptKind.HUMAN_REVIEW
    assert result.interrupt_payload.handoff.revision_round == 3
    assert result.interrupt_payload.review_result.verdict == "REVISE"


@pytest.mark.parametrize("last_verdict", ["APPROVE", "REVISE"])
def test_three_revisions_and_two_verification_retries_fit_proposal_budget(last_verdict):
    model = QueuedModel()
    queue_initial_resolution(model)
    for number in range(1, 6):
        model.queue(
            ModelTask.PROPOSE_OR_REVISE,
            proposal_output(rationale=f"Correction {number} applies the latest feedback."),
        )
    model.queue(
        ModelTask.REVIEW,
        revised_review(),
        revised_review(),
        revised_review(),
        approved_review() if last_verdict == "APPROVE" else revised_review(),
    )
    evidence = evidence_item()
    failed = FailedVerificationResult(
        status="FAIL", issues=[verification_issue()], verification_version="verify:1"
    )
    passed = {"status": "PASS", "issues": [], "verification_version": "verify:1"}
    runtime, providers = make_runtime(
        model=model,
        verification_results=[failed, passed, failed, passed, passed, passed],
        human_results=[None],
        evidence_items={evidence.artifact_ref: evidence},
    )
    result = runtime.start(
        thread_id="THREAD-MIXED-BUDGET",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-MIXED-BUDGET"}}
    ).values
    assert state["propose_round"] == 6
    assert state["verification_round"] == 2
    assert state["revision_round"] == 3
    assert len(state["review_history"]) == 4
    assert len(providers["verification"].calls) == 6
    if last_verdict == "APPROVE":
        assert result.resolution_handoff.outcome_source is OutcomeSource.REVIEWER_APPROVE
        assert providers["human"].submit_calls == []
    else:
        assert result.interrupt_kind is AgentInterruptKind.HUMAN_REVIEW
        assert result.interrupt_payload.routing_reason == "REVISION_BUDGET_EXCEEDED"
        assert len(providers["human"].submit_calls) == 1
        dossier = result.interrupt_payload.dossier
        assert len(dossier.proposal_history) == len(dossier.review_history) == 4
        assert len(dossier.revision_events) == 3
        assert dossier.proposal_history[-1] == state["current_handoff"]
        assert dossier.claimed_line_item_ids == state["claimed_line_item_ids"]


def test_revision_cannot_repeat_same_proposal_or_choose_between_conflicts():
    evidence = evidence_item()

    repeated_model = QueuedModel()
    queue_initial_resolution(repeated_model)
    repeated_model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    repeated_model.queue(ModelTask.REVIEW, revised_review())
    repeated_runtime, repeated_providers = make_runtime(
        model=repeated_model,
        evidence_items={evidence.artifact_ref: evidence},
    )
    repeated = repeated_runtime.start(
        thread_id="THREAD-REPEAT-REVISION",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert repeated.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"
    assert len(repeated_providers["verification"].calls) == 1

    conflict_model = QueuedModel()
    queue_initial_resolution(conflict_model)
    conflict_model.queue(
        ModelTask.PROPOSE_OR_REVISE,
        ResolverConflictOutput(
            result_type="CONFLICTING_REVISIONS",
            conflict={
                "conflicting_reason_codes": [
                    "POLICY_MISMATCH",
                    "RETURN_REQUIREMENT_INCONSISTENT",
                ],
                "conflicting_review_refs": ["REV-A", "REV-B"],
                "explanation": "The required changes cannot both be satisfied.",
            },
        ),
    )
    conflict_model.queue(ModelTask.REVIEW, revised_review())
    conflict_runtime, _ = make_runtime(
        model=conflict_model,
        evidence_items={evidence.artifact_ref: evidence},
    )
    conflict = conflict_runtime.start(
        thread_id="THREAD-CONFLICT-REVISION",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert conflict.manual_escalation.escalation_reason == "CONFLICTING_REVISIONS"


def test_policy_status_and_provider_exceptions_fail_closed():
    for status, reason in (
        ("AMBIGUOUS", "POLICY_AMBIGUOUS"),
        ("NOT_FOUND", "POLICY_NOT_FOUND"),
    ):
        model = QueuedModel()
        model.queue(ModelTask.INTAKE, complete_intake())
        bundle = PolicyBundle(
            policy_bundle_version="bundle:bad",
            retrieval_status=status,
            retrieved_at=TIME,
            clauses=[],
        )
        runtime, _ = make_runtime(model=model, policy_result=bundle)
        result = runtime.start(
            thread_id=f"THREAD-POLICY-{status}",
            case_ref="CASE-001",
            initial_turn=user_turn(),
        )
        assert result.manual_escalation.escalation_reason == reason

    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    runtime, _ = make_runtime(model=model, case_result=RuntimeError("down"))
    result = runtime.start(
        thread_id="THREAD-CONTEXT-ERROR",
        case_ref="CASE-001",
        initial_turn=user_turn(),
    )
    assert result.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"


def test_malformed_provider_payload_fails_closed():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    runtime, _ = make_runtime(
        model=model,
        policy_result={"retrieval_status": "OK"},
    )

    result = runtime.start(
        thread_id="THREAD-MALFORMED-PROVIDER",
        case_ref="CASE-001",
        initial_turn=user_turn(),
    )

    assert result.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"


def test_memory_failure_is_non_blocking_and_observable():
    model = QueuedModel()
    queue_initial_resolution(model)
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        memory_results=RuntimeError("memory unavailable"),
        evidence_items={evidence.artifact_ref: evidence},
    )

    result = runtime.start(
        thread_id="THREAD-MEMORY-FAIL",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )

    assert result.resolution_handoff is not None
    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-MEMORY-FAIL"}}
    ).values
    assert state["memory_retrieval_status"] is MemoryRetrievalStatus.UNAVAILABLE
    assert state["operational_memory"] == []


def test_expired_policy_and_provider_errors_fail_closed():
    evidence = evidence_item()
    expired = policy_bundle()
    expired.clauses[0].effective_to = "2026-08-01T00:00:00Z"
    expired_model = QueuedModel()
    expired_model.queue(ModelTask.INTAKE, complete_intake())
    expired_runtime, _ = make_runtime(
        model=expired_model,
        policy_result=expired,
    )
    expired_result = expired_runtime.start(
        thread_id="THREAD-POLICY-EXPIRED",
        case_ref="CASE-001",
        initial_turn=user_turn(),
    )
    assert expired_result.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"

    policy_model = QueuedModel()
    policy_model.queue(ModelTask.INTAKE, complete_intake())
    policy_runtime, _ = make_runtime(
        model=policy_model,
        policy_result=RuntimeError("policy down"),
    )
    policy_error = policy_runtime.start(
        thread_id="THREAD-POLICY-ERROR",
        case_ref="CASE-001",
        initial_turn=user_turn(),
    )
    assert policy_error.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"

    evidence_model = QueuedModel()
    evidence_model.queue(ModelTask.INTAKE, complete_intake())
    evidence_runtime, _ = make_runtime(
        model=evidence_model,
        evidence_items={evidence.artifact_ref: RuntimeError("evidence down")},
    )
    evidence_error = evidence_runtime.start(
        thread_id="THREAD-EVIDENCE-ERROR",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert evidence_error.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"

    verification_model = QueuedModel()
    queue_initial_resolution(verification_model)
    verification_runtime, _ = make_runtime(
        model=verification_model,
        verification_results=[RuntimeError("verification down")],
        evidence_items={evidence.artifact_ref: evidence},
    )
    verification_error = verification_runtime.start(
        thread_id="THREAD-VERIFICATION-ERROR",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert (
        verification_error.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"
    )


def test_human_submit_and_fetch_errors_fail_closed():
    evidence = evidence_item()

    submit_model = QueuedModel()
    queue_initial_resolution(submit_model)
    queue_human_review(submit_model)
    submit_runtime, submit_providers = make_runtime(
        model=submit_model,
        verification_results=four_verifications(),
        evidence_items={evidence.artifact_ref: evidence},
    )
    submit_providers["human"].submit_error = RuntimeError("submit down")
    submit_error = submit_runtime.start(
        thread_id="THREAD-HUMAN-SUBMIT-ERROR",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert submit_error.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"

    fetch_model = QueuedModel()
    queue_initial_resolution(fetch_model)
    queue_human_review(fetch_model)
    fetch_runtime, _ = make_runtime(
        model=fetch_model,
        verification_results=four_verifications(),
        human_results=[RuntimeError("fetch down")],
        evidence_items={evidence.artifact_ref: evidence},
    )
    fetch_error = fetch_runtime.start(
        thread_id="THREAD-HUMAN-FETCH-ERROR",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert fetch_error.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"


@pytest.mark.parametrize("corrections", [0, 1, 2, 3])
def test_approval_at_any_revision_completes_without_human_review(corrections):
    model = QueuedModel()
    queue_initial_resolution(model)
    for rationale in ["First corrected explanation.", "Second corrected explanation.", "Third corrected explanation."][:corrections]:
        model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output(rationale=rationale))
    model.queue(ModelTask.REVIEW, *[revised_review() for _ in range(corrections)], approved_review())
    evidence = evidence_item()
    runtime, providers = make_runtime(
        model=model, verification_results=four_verifications()[:corrections + 1],
        evidence_items={evidence.artifact_ref: evidence},
    )
    result = runtime.start(thread_id="THREAD-LAST-APPROVAL", case_ref="CASE-001",
                           initial_turn=user_turn(artifacts=[evidence.artifact_ref]))
    assert result.resolution_handoff.outcome_source is OutcomeSource.REVIEWER_APPROVE
    assert providers["human"].submit_calls == []
    state = runtime.graph.get_state({"configurable": {"thread_id": "THREAD-LAST-APPROVAL"}}).values
    assert state["revision_round"] == corrections
    assert state["review_routing_reason"] is None
    assert len(state["review_history"]) == corrections + 1
