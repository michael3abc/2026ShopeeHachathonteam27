"""Deterministic, non-production composition used by local transport smoke tests."""

from __future__ import annotations
from return_agent_contracts.review_gates import ReviewerGateConfig

from return_agent_contracts.models import ReviewResult

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

from langgraph.checkpoint.memory import InMemorySaver
from return_agent_contracts.enums import ClaimId, ClaimStatus, ReasonCode, ReturnPolicy
from return_agent_contracts.models import (
    ApplicableConditions,
    ApprovalEvidenceAssessment,
    ApprovedReviewResult,
    CaseContext,
    CaseContextLoadResult,
    ClaimFinding,
    EvidenceItem,
    EvidenceRequest,
    FullRefundProposedDecisionDraft,
    HumanReviewDossier,
    HumanReviewResult,
    InsufficientEvidenceAssessment,
    MemoryCandidate,
    MemorySearchHit,
    MissingClaim,
    ModelJudgmentReturnDecision,
    NonEmptyRefundScope,
    OrderLineItem,
    OrderSnapshot,
    PassedVerificationResult,
    PolicyBundle,
    PolicyClause,
    PolicyReturnDecisionDraft,
    ProposedDecisionHandoff,
    ResolverDraftOutput,
    RevisedReviewResult,
    VerificationResult,
    WaivedReturnRequirement,
)
from return_agent_runtime import (
    AgentDependencies,
    ReturnAgentRuntime,
    create_checkpoint_serializer,
)
from return_agent_runtime.model import ModelTask, OutputSchema, StructuredOutputModel

OutputT = TypeVar("OutputT")
TIME = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


@dataclass(slots=True)
class _DemoModel:
    reason_code: ReasonCode = ReasonCode.CHANGED_MIND
    outputs: dict[ModelTask, deque[Any]] = field(
        default_factory=lambda: defaultdict(deque)
    )

    def generate(
        self,
        *,
        task: ModelTask,
        system_prompt: str,
        payload: Mapping[str, Any],
        output_schema: OutputSchema[OutputT],
    ) -> OutputT:
        del system_prompt
        if task is ModelTask.MEMORY_QUERY_SUMMARY:
            return output_schema.adapter.validate_python(
                {"query_summary": "Speaker return request with current evidence."}
            )
        if task is ModelTask.ASSESS:
            assessment = (
                ApprovalEvidenceAssessment(
                    evidence_status="SUFFICIENT_FOR_APPROVAL",
                    claim_registry_version="claim-registry:1.0",
                    claim_findings=_findings(self.reason_code),
                )
                if self.reason_code is ReasonCode.CHANGED_MIND
                or payload.get("evidence_bundle")
                else _insufficient_assessment()
            )
            return output_schema.adapter.validate_python(assessment)
        if not self.outputs[task]:
            raise RuntimeError(f"demo model has no output for {task.value}")
        # Reuse the final fixture so repeated independent cases remain runnable.
        queue = self.outputs[task]
        return output_schema.adapter.validate_python(
            queue[0] if len(queue) == 1 else queue.popleft()
        )


@dataclass(frozen=True, slots=True)
class _Clock:
    def now(self) -> datetime:
        return TIME


@dataclass(frozen=True, slots=True)
class _CaseProvider:
    result: CaseContextLoadResult

    def load_case_context(self, case_ref: str) -> CaseContextLoadResult:
        # ponytail: the API mints its own case refs, so the fixture answers for
        # any of them instead of only CASE-DEMO.
        if case_ref == self.result.case_context.case_ref:
            return self.result
        return self.result.model_copy(
            update={
                "case_context": self.result.case_context.model_copy(
                    update={"case_ref": case_ref}
                )
            }
        )


@dataclass(frozen=True, slots=True)
class _PolicyProvider:
    result: PolicyBundle

    def retrieve_policy(
        self,
        case_context: CaseContext,
        order_snapshot: OrderSnapshot,
        reason_code: ReasonCode,
        claimed_line_item_ids: Sequence[str],
    ) -> PolicyBundle:
        del case_context, order_snapshot, reason_code, claimed_line_item_ids
        return self.result


class _MemoryStore:
    def query_approved(
        self,
        query_summary: str,
        market: str,
        reason_code: ReasonCode,
        required_claim_ids: Sequence[ClaimId],
        categories: Sequence[str],
        policy_versions: Sequence[str],
        claim_registry_major: int,
        top_k: int = 3,
    ) -> Sequence[MemorySearchHit]:
        del (
            market,
            reason_code,
            required_claim_ids,
            categories,
            policy_versions,
            claim_registry_major,
            top_k,
        )
        return []

    def submit_candidate(self, candidate: MemoryCandidate) -> str:
        del candidate
        raise RuntimeError("memory submission is unavailable in demo mode")


@dataclass(frozen=True, slots=True)
class _EvidenceProvider:
    evidence: EvidenceItem

    def resolve(self, artifact_ref: str) -> EvidenceItem:
        if artifact_ref != self.evidence.artifact_ref:
            raise ValueError("unknown demo artifact")
        return self.evidence


class _VerificationProvider:
    def verify(self, handoff: ProposedDecisionHandoff) -> VerificationResult:
        del handoff
        return PassedVerificationResult(
            status="PASS", issues=[], verification_version="demo-verification:v1"
        )


class _HumanProvider:
    def submit_for_review(
        self, handoff: ProposedDecisionHandoff, review: ReviewResult,
        dossier: HumanReviewDossier | None = None,
    ) -> str:
        del handoff, review
        raise RuntimeError("human review is unavailable in demo mode")

    def fetch_result(self, review_ref: str) -> HumanReviewResult | None:
        del review_ref
        return None


def _findings(reason_code: ReasonCode = ReasonCode.CHANGED_MIND) -> list[ClaimFinding]:
    findings = [
        ClaimFinding(
            claim_id="DELIVERY_CONFIRMED",
            subject="ORDER",
            status=ClaimStatus.SUPPORTED,
            supporting_evidence_refs=["EV-SYS-DELIVERY"],
            explanation="Order was delivered.",
        ),
        ClaimFinding(
            claim_id="ORDER_WITHIN_RETURN_WINDOW",
            subject="ORDER",
            status=ClaimStatus.SUPPORTED,
            supporting_evidence_refs=["EV-SYS-WINDOW"],
            explanation="Case is within the return window.",
        ),
    ]
    if reason_code is ReasonCode.ITEM_DAMAGED:
        findings.extend(
            ClaimFinding(
                claim_id=claim_id,
                subject="LI-DEMO",
                status=ClaimStatus.SUPPORTED,
                supporting_evidence_refs=["EV-DEMO"],
                explanation="Packaging and item damage are visible together.",
            )
            for claim_id in ("ITEM_PHYSICALLY_DAMAGED", "DAMAGE_PRESENT_ON_ARRIVAL")
        )
    return findings


def _insufficient_assessment() -> InsufficientEvidenceAssessment:
    findings = _findings(ReasonCode.ITEM_DAMAGED)
    for index in (2, 3):
        findings[index] = findings[index].model_copy(
            update={
                "status": ClaimStatus.UNSUPPORTED,
                "supporting_evidence_refs": [],
                "explanation": "Buyer evidence has not been supplied yet.",
            }
        )
    return InsufficientEvidenceAssessment(
        evidence_status="INSUFFICIENT",
        claim_registry_version="claim-registry:1.0",
        claim_findings=findings,
        missing_evidence_request=EvidenceRequest(
            request_id="REQUEST-DEMO",
            missing_claims=[
                MissingClaim(
                    claim_id="ITEM_PHYSICALLY_DAMAGED",
                    subject="LI-DEMO",
                ),
                MissingClaim(
                    claim_id="DAMAGE_PRESENT_ON_ARRIVAL",
                    subject="LI-DEMO",
                ),
            ],
            accepted_evidence_types=["IMAGE", "VIDEO"],
            user_message="Please provide one image showing the package and damage.",
            policy_refs=["POLICY-DEMO:v1#damaged"],
        ),
    )


def create_demo_runtime(
    model_override: StructuredOutputModel | None = None,
    *,
    reason_code: ReasonCode = ReasonCode.CHANGED_MIND,
    reviewer_gate_config: ReviewerGateConfig | None = None,
) -> ReturnAgentRuntime:
    """Build a deterministic happy-path graph for a demo API case."""

    if reason_code not in {ReasonCode.CHANGED_MIND, ReasonCode.ITEM_DAMAGED}:
        raise ValueError("unsupported demo reason")
    damaged = reason_code is ReasonCode.ITEM_DAMAGED
    clause_ref = "POLICY-DEMO:v1#damaged" if damaged else "POLICY-DEMO:v1#changed-mind"
    fixture_model = _DemoModel(reason_code=reason_code)
    fixture_model.outputs[ModelTask.INTAKE].append(
        {
            "completeness": "COMPLETE",
            "order_ref": "ORDER-DEMO",
            "reason_code": reason_code,
            "reason_summary": "Speaker arrived damaged."
            if damaged
            else "Buyer no longer wants the speaker.",
            "requested_action": "RETURN_AND_REFUND",
            "claimed_line_item_ids": [],
            "missing_fields": [],
            "clarification_question": None,
        }
    )
    fixture_model.outputs[ModelTask.PROPOSE_OR_REVISE].append(
        ResolverDraftOutput(
            result_type="DRAFT",
            draft=FullRefundProposedDecisionDraft(
                action="FULL_REFUND",
                refund_scope=NonEmptyRefundScope(line_item_ids=["LI-DEMO"]),
                reason_code=reason_code,
                return_decision=ModelJudgmentReturnDecision(
                    source="MODEL_JUDGMENT",
                    requirement=WaivedReturnRequirement(
                        required=False, reason_code="ITEM_UNSALVAGEABLE"
                    ),
                )
                if damaged
                else PolicyReturnDecisionDraft(
                    source="POLICY",
                    reason_code="RESALE_VALUE_RETAINED",
                ),
                policy_refs=[clause_ref],
                # Only the damage scenario requires a user artifact.
                evidence_refs=["EV-DEMO"] if damaged else [],
                rationale_summary="All required claims are supported.",
            ),
        )
    )
    fixture_model.outputs[ModelTask.REVIEW].append(
        ApprovedReviewResult(
            verdict="APPROVE",
            reviewer_claim_findings=_findings(reason_code),
            revision_reasons=[],
            reviewer_prompt_version="reviewer:1.0",
            reviewed_at=TIME,
        )
    )

    order = OrderSnapshot(
        order_snapshot_ref="ORDER-DEMO@1",
        order_ref="ORDER-DEMO",
        snapshot_version=1,
        captured_at=TIME,
        currency="TWD",
        delivered_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        line_items=[
            OrderLineItem(
                line_item_id="LI-DEMO",
                sku_ref="SKU-DEMO",
                category_ref="CAT-AUDIO-SPEAKERS",
                title="Demo speaker",
                quantity=1,
                refundable_amount="1200",
            )
        ],
        refundable_amount_max="1200",
        already_refunded_amount="0",
    )
    case = CaseContextLoadResult(
        case_context=CaseContext(
            case_ref="CASE-DEMO",
            order_ref="ORDER-DEMO",
            market="TW",
            case_opened_at=TIME,
            snapshot_version=1,
        ),
        order_snapshot=order,
    )
    policy = PolicyBundle(
        policy_bundle_version="demo-bundle:v1",
        retrieval_status="OK",
        retrieved_at=TIME,
        clauses=[
            PolicyClause(
                clause_id=clause_ref,
                policy_version="POLICY-DEMO:v1",
                effective_from=datetime(2026, 1, 1, tzinfo=UTC),
                applicable_conditions=ApplicableConditions(
                    markets=["TW"],
                    reason_codes=[reason_code],
                    categories=["CAT-AUDIO-SPEAKERS"],
                ),
                # Changed-mind eligibility uses system facts; damage adds user claims.
                required_claim_ids=[
                    "DELIVERY_CONFIRMED",
                    "ORDER_WITHIN_RETURN_WINDOW",
                ]
                + (
                    ["ITEM_PHYSICALLY_DAMAGED", "DAMAGE_PRESENT_ON_ARRIVAL"]
                    if damaged
                    else []
                ),
                allowed_actions=["FULL_REFUND", "DECLINE"],
                return_policy=ReturnPolicy.MODEL_JUDGMENT
                if damaged
                else ReturnPolicy.REQUIRED,
                text="Delivered damaged items may be refunded."
                if damaged
                else "Items may be returned within the cooling-off window.",
            )
        ],
    )
    evidence = EvidenceItem(
        evidence_id="EV-DEMO",
        type="IMAGE",
        source="USER",
        subject="LI-DEMO",
        artifact_ref="artifact://demo/damage",
        extracted_summary=(
            "The same image clearly shows both the crushed outer shipping box "
            "and the cracked area of the speaker as received."
        ),
        collected_at=TIME,
    )
    dependencies = AgentDependencies(
        reviewer_gate_config=reviewer_gate_config or ReviewerGateConfig(),
        model=model_override or fixture_model,
        case_context_provider=_CaseProvider(case),
        policy_provider=_PolicyProvider(policy),
        verification_provider=_VerificationProvider(),
        human_review_provider=_HumanProvider(),
        operational_memory_store=_MemoryStore(),
        evidence_provider=_EvidenceProvider(evidence),
        clock=_Clock(),
    )
    return ReturnAgentRuntime(
        dependencies,
        InMemorySaver(serde=create_checkpoint_serializer()),
    )
