"""API-owned trusted inputs and durable deterministic authorization records."""
from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from return_agent_contracts.domain import CaseContext, CaseContextLoadResult, EvidenceItem, FailedVerificationResult, OrderSnapshot, PassedVerificationResult, PolicyBundle, PolicyClause, ProposedDecisionHandoff, ReviewerGateConfig, VerificationIssue, VerificationResult
from return_agent_contracts.providers import ContractConflict, FetchHumanReviewParams, LoadCaseContextParams, ProviderUnavailable, ResolveEvidenceParams, RetrievePolicyParams, SubmitHumanReviewParams, VerifyHandoffParams
from return_agent_contracts.human import HumanReviewResult
from return_agent_contracts.primitives import payload_hash, unique
from return_agent_contracts.validation import validate_dossier, validate_handoff, validate_policy, validate_resolved_evidence

from .cases import CaseNotFound, CaseStore
from .db import CaseRow, EvidenceRow, HumanReviewRow, PolicyClauseRow, PolicyRetrievalRow, TrustedOrderRow, VerificationRow


class CapabilityNotFound(LookupError):
    pass


def lock_identifier(session: Session, namespace: str, identifier: str) -> None:
    # Hash collisions only serialize unrelated work; identity still uses the full key.
    session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"{namespace}:{identifier}", 0))))


class CapabilityStore:
    def __init__(self, cases: CaseStore, *, gates: ReviewerGateConfig | None = None):
        self.cases, self.sessions = cases, cases.sessions
        self.gates = gates or ReviewerGateConfig()

    def context(self, session: Session, case_ref: str) -> CaseContextLoadResult:
        case = session.get(CaseRow, case_ref)
        if case is None:
            raise CaseNotFound(case_ref)
        row = session.get(TrustedOrderRow, case.order_ref)
        if row is None:
            raise CapabilityNotFound("Trusted order not found")
        snapshot = OrderSnapshot.model_validate(row.snapshot)
        if snapshot.order_ref != case.order_ref:
            raise ProviderUnavailable("Trusted order identity is inconsistent")
        return CaseContextLoadResult(case_context=CaseContext(case_ref=case_ref, order_ref=case.order_ref, market=row.market, case_opened_at=case.created_at, snapshot_version=snapshot.snapshot_version), order_snapshot=snapshot)

    def load_case_context(self, params: LoadCaseContextParams) -> CaseContextLoadResult:
        with self.sessions() as session:
            return self.context(session, params.case_ref)

    def resolve_in_session(self, session: Session, artifact_ref: str) -> EvidenceItem:
        row = session.get(EvidenceRow, artifact_ref)
        if row is None:
            raise CapabilityNotFound("Evidence artifact not found")
        evidence = EvidenceItem.model_validate(row.payload)
        if evidence.artifact_ref != artifact_ref:
            raise ProviderUnavailable("Evidence identity is inconsistent")
        return evidence

    def resolve(self, params: ResolveEvidenceParams) -> EvidenceItem:
        with self.sessions() as session:
            return self.resolve_in_session(session, params.artifact_ref)

    def retrieve_policy(self, params: RetrievePolicyParams) -> PolicyBundle:
        with self.sessions.begin() as session:
            self.cases.locked_case(session, params.case_context.case_ref)
            trusted = self.context(session, params.case_context.case_ref)
            if params.case_context != trusted.case_context or params.order_snapshot != trusted.order_snapshot:
                raise ContractConflict("Policy request does not match canonical context")
            unique(params.claimed_line_item_ids, "claimed item")
            lines = {line.line_item_id: line for line in trusted.order_snapshot.line_items}
            if not set(params.claimed_line_item_ids) <= lines.keys():
                raise ValueError("Policy request contains unknown items")
            categories = {lines[item].category_ref for item in params.claimed_line_item_ids}
            clauses = []
            for row in session.scalars(select(PolicyClauseRow).order_by(PolicyClauseRow.clause_id, PolicyClauseRow.policy_version)):
                clause = PolicyClause.model_validate(row.payload)
                scope, context = clause.applicable_conditions, trusted.case_context
                if context.case_opened_at < clause.effective_from or (clause.effective_to and context.case_opened_at > clause.effective_to):
                    continue
                if (scope.markets and context.market not in scope.markets) or (scope.categories and not categories.intersection(scope.categories)) or (scope.reason_codes and params.reason_code not in scope.reason_codes):
                    continue
                clauses.append(clause)
            # Overlapping versions of one clause cannot be silently picked.
            ambiguous = len({clause.clause_id for clause in clauses}) != len(clauses)
            bundle = PolicyBundle(policy_bundle_version=self.cases.ids("policy-bundle"), retrieved_at=self.cases.clock(), retrieval_status="AMBIGUOUS" if ambiguous else "OK" if clauses else "NOT_FOUND", clauses=[] if ambiguous else clauses)
            if bundle.retrieval_status == "OK":
                try:
                    validate_policy(trusted.case_context, trusted.order_snapshot, bundle, params.reason_code, params.claimed_line_item_ids)
                except ValueError:
                    bundle = bundle.model_copy(update={"retrieval_status": "AMBIGUOUS"})
            session.add(PolicyRetrievalRow(bundle_version=bundle.policy_bundle_version, case_ref=trusted.case_context.case_ref, request=params.model_dump(mode="json"), bundle=bundle.model_dump(mode="json")))
            return bundle

    def persisted_policy(self, session: Session, handoff: ProposedDecisionHandoff) -> tuple[PolicyBundle, RetrievePolicyParams]:
        row = session.get(PolicyRetrievalRow, handoff.policy_bundle_version)
        if row is None or row.case_ref != handoff.case_ref:
            raise ValueError("Exact persisted policy bundle is missing")
        request = RetrievePolicyParams.model_validate(row.request)
        if request.reason_code != handoff.proposed_decision.reason_code:
            raise ValueError("Decision reason differs from the policy retrieval")
        return PolicyBundle.model_validate(row.bundle), request

    def validate_trusted_handoff(self, session: Session, handoff: ProposedDecisionHandoff) -> tuple[CaseContextLoadResult, PolicyBundle, RetrievePolicyParams]:
        trusted = self.context(session, handoff.case_ref)
        policy, request = self.persisted_policy(session, handoff)
        if request.order_snapshot != trusted.order_snapshot or request.case_context != trusted.case_context:
            raise ValueError("Order changed after policy retrieval")
        validate_handoff(handoff, trusted.case_context, trusted.order_snapshot, policy, request.claimed_line_item_ids)
        subjects = {trusted.order_snapshot.order_ref, *(item.line_item_id for item in trusted.order_snapshot.line_items)}
        for item in handoff.evidence_bundle:
            actual = self.resolve_in_session(session, item.artifact_ref)
            validate_resolved_evidence(item.artifact_ref, actual, subjects)
            if item != actual:
                raise ValueError("Handoff altered trusted evidence metadata")
        return trusted, policy, request

    def verify(self, params: VerifyHandoffParams) -> VerificationResult:
        handoff = params.handoff
        with self.sessions.begin() as session:
            self.cases.locked_case(session, handoff.case_ref)
            lock_identifier(session, "handoff", handoff.handoff_id)
            row = session.get(VerificationRow, handoff.handoff_id)
            digest = payload_hash(handoff)
            if row:
                if row.payload_hash != digest or row.case_ref != handoff.case_ref:
                    raise ContractConflict("Handoff ID reused with different content")
                return TypeAdapter(VerificationResult).validate_python(row.result)
            try:
                self.validate_trusted_handoff(session, handoff)
                result = PassedVerificationResult(status="PASS", verification_version="verification:1.0")
            except (ValueError, CapabilityNotFound):
                # Persist a safe structured issue, never a raw external payload.
                result = FailedVerificationResult(status="FAIL", verification_version="verification:1.0", issues=[VerificationIssue(code="TRUSTED_INPUT_MISMATCH", field_path="handoff", message="Handoff failed the trusted order, policy or evidence checks")])
            session.add(VerificationRow(handoff_id=handoff.handoff_id, case_ref=handoff.case_ref, payload_hash=digest, handoff=handoff.model_dump(mode="json"), result=result.model_dump(mode="json"), created_at=self.cases.clock()))
            return result

    def submit_for_review(self, params: SubmitHumanReviewParams) -> str:
        if params.dossier is None:
            raise ValueError("A persisted human review requires a complete dossier")
        handoff, dossier = params.handoff, params.dossier
        with self.sessions.begin() as session:
            self.cases.locked_case(session, handoff.case_ref)
            lock_identifier(session, "handoff", handoff.handoff_id)
            existing = session.scalar(select(HumanReviewRow).where(HumanReviewRow.handoff_id == handoff.handoff_id))
            if existing:
                if existing.payload_hash != payload_hash(params):
                    raise ContractConflict("Human review ID reused with different content")
                return existing.review_ref
            trusted, policy, retrieval = self.validate_trusted_handoff(session, handoff)
            if dossier.order_snapshot != trusted.order_snapshot or dossier.policy_bundle != policy or dossier.claimed_line_item_ids != retrieval.claimed_line_item_ids:
                raise ValueError("Dossier differs from persisted trusted inputs")
            validate_dossier(dossier, handoff, params.review, trusted.case_context, self.gates)
            for proposal in dossier.proposal_history:
                record = session.get(VerificationRow, proposal.handoff_id)
                if record is None or record.payload_hash != payload_hash(proposal) or record.result["status"] != "PASS":
                    raise ValueError("Every dossier proposal requires a persisted PASS verification")
            ref = self.cases.ids("human-review")
            session.add(HumanReviewRow(review_ref=ref, handoff_id=handoff.handoff_id, case_ref=handoff.case_ref, payload_hash=payload_hash(params), request=params.model_dump(mode="json"), created_at=self.cases.clock()))
            return ref

    def fetch_result(self, params: FetchHumanReviewParams) -> HumanReviewResult | None:
        with self.sessions() as session:
            row = session.get(HumanReviewRow, params.review_ref)
            if row is None:
                raise CapabilityNotFound("Human review not found")
            return TypeAdapter(HumanReviewResult).validate_python(row.result) if row.result else None
