"""Versioned structured Policy RAG with deterministic hard applicability gates."""

from __future__ import annotations
from return_agent_contracts.policy_v2 import PolicyPath, PolicyPathId, REASON_PATH, POLICY_V2_VERSION

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from math import sqrt
from pathlib import Path

from pydantic import Field, ValidationError, model_validator
from return_agent_contracts.base import (
    ContractModel,
    NonEmptyText,
    OpaqueRef,
    UTCDateTime,
)
from return_agent_contracts.enums import (
    ClaimId,
    ReasonCode,
    ResolutionAction,
    RetrievalStatus,
    ReturnPolicy,
)
from return_agent_contracts.interfaces import PolicyProvider
from return_agent_contracts.models import (
    ApplicableConditions,
    CaseContext,
    OrderSnapshot,
    PolicyBundle,
    PolicyClause,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from return_agent.capabilities.embeddings import (
    POLICY_EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    validate_embedding,
)
from return_agent.db.models import (
    PolicyClauseRecord,
    PolicyDocumentRecord,
    PolicyRetrievalRecord,
)


class PolicyFixtureError(ValueError):
    """Raised for unreadable or contract-invalid policy fixture content."""


class PolicyIngestionConflictError(ValueError):
    """Raised when a policy family/version is reused with changed content."""


class PolicyRetrievalInputError(ValueError):
    """Raised when supplied external context cannot form a safe policy query."""


class PolicyDataIntegrityError(RuntimeError):
    """Raised when a persisted policy record disagrees with its stable identity."""


class PolicyEmbeddingModelMismatchError(RuntimeError):
    """Stored and configured embeddings occupy different vector spaces."""


def _require_embedding_model(
    clauses: Sequence[PolicyClauseRecord], model_name: str
) -> None:
    incompatible = sorted({row.embedding_model for row in clauses} - {model_name})
    if incompatible:
        raise PolicyEmbeddingModelMismatchError(
            f"stored policy embedding models {incompatible!r} do not match "
            f"configured model {model_name!r}; run return-agent-ingest-policy "
            "--input <canonical-fixture> --reembed with the target model "
            "before restarting retrieval"
        )


@dataclass(frozen=True)
class PolicyIngestionResult:
    inserted_documents: int
    updated_documents: int
    unchanged_documents: int


class PolicyClauseFixture(ContractModel):
    """Fixture form of PolicyClause; document version is derived at ingestion."""

    clause_id: OpaqueRef
    path_id: PolicyPathId | None = Field(default=None,exclude_if=lambda v: v is None)
    effective_from: UTCDateTime
    effective_to: UTCDateTime | None = None
    applicable_conditions: ApplicableConditions
    required_claim_ids: list[ClaimId]
    allowed_actions: list[ResolutionAction]
    return_policy: ReturnPolicy
    text: NonEmptyText

    @model_validator(mode="after")
    def _validate_clause_shape(self) -> PolicyClauseFixture:
        if not self.required_claim_ids and self.path_id is not PolicyPathId.COOLING_OFF:
            raise ValueError("policy clause requires at least one claim")
        if not self.allowed_actions:
            raise ValueError("policy clause requires at least one action")
        if len(self.required_claim_ids) != len(set(self.required_claim_ids)):
            raise ValueError("policy clause claim IDs must be unique")
        if len(self.allowed_actions) != len(set(self.allowed_actions)):
            raise ValueError("policy clause allowed actions must be unique")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("policy clause effective range is invalid")
        return self

    def to_contract(self, policy_version: str) -> PolicyClause:
        """Validate the final executable PolicyClause using shared contracts."""

        return PolicyClause(
            path_id=self.path_id,
            clause_id=self.clause_id,
            policy_version=policy_version,
            effective_from=self.effective_from,
            effective_to=self.effective_to,
            applicable_conditions=self.applicable_conditions,
            required_claim_ids=self.required_claim_ids,
            allowed_actions=self.allowed_actions,
            return_policy=self.return_policy,
            text=self.text,
        )


class PolicyDocumentFixture(ContractModel):
    """A versioned source containing structured clauses, not raw RAG chunks."""

    policy_family: NonEmptyText
    paths: list[PolicyPath] = Field(default_factory=list,exclude_if=lambda v: not v)
    version: NonEmptyText
    source_ref: OpaqueRef
    active: bool = True
    clauses: list[PolicyClauseFixture]

    @model_validator(mode="after")
    def _validate_document_shape(self) -> PolicyDocumentFixture:
        if self.paths:
            PolicyBundle(schema_version="v2",policy_bundle_version=POLICY_V2_VERSION+":bundle:validation",
                retrieval_status="OK",retrieved_at=self.paths[0].effective_from,paths=self.paths,
                selected_path_id=self.paths[0].path_id,clauses=self.contract_clauses())
        if not self.clauses:
            raise ValueError("policy document requires at least one clause")
        clause_ids = [clause.clause_id for clause in self.clauses]
        if len(clause_ids) != len(set(clause_ids)):
            raise ValueError("policy document clause IDs must be unique")
        return self

    @property
    def policy_version(self) -> str:
        return f"{self.policy_family}:{self.version}"

    def contract_clauses(self) -> list[PolicyClause]:
        return [clause.to_contract(self.policy_version) for clause in self.clauses]


@dataclass(frozen=True)
class _PolicyCandidate:
    document: PolicyDocumentRecord
    clause: PolicyClauseRecord


def load_policy_fixture(path: Path) -> list[PolicyDocumentFixture]:
    """Load a strict JSON array of versioned policy documents."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyFixtureError(f"unable to read policy fixture {path}") from error
    if not isinstance(payload, list):
        raise PolicyFixtureError("policy fixture must be a JSON array")
    try:
        documents = [PolicyDocumentFixture.model_validate(item) for item in payload]
        for document in documents:
            document.contract_clauses()
    except ValidationError as error:
        raise PolicyFixtureError(
            "policy fixture contains invalid structured clauses"
        ) from error
    family_versions = [
        (document.policy_family, document.version) for document in documents
    ]
    source_versions = [
        (document.source_ref, document.version) for document in documents
    ]
    if len(family_versions) != len(set(family_versions)):
        raise PolicyFixtureError("policy fixture repeats a policy family/version")
    if len(source_versions) != len(set(source_versions)):
        raise PolicyFixtureError("policy fixture repeats a source_ref/version")
    return documents


def _canonical_hash(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _fixture_checksum(document: PolicyDocumentFixture) -> str:
    return _canonical_hash(document.model_dump(mode="json", exclude={"active"}))


def _document_id(document: PolicyDocumentFixture) -> str:
    return f"policy-document:{_fixture_checksum(document)[:32]}"


def ingest_policy_documents(
    session: Session,
    documents: Iterable[PolicyDocumentFixture],
    embedding_provider: EmbeddingProvider,
    *,
    reembed: bool = False,
) -> PolicyIngestionResult:
    """Validate, embed, and idempotently store policy documents by version."""

    inserted = 0
    updated = 0
    unchanged = 0
    for document in documents:
        checksum = _fixture_checksum(document)
        existing = session.scalar(
            select(PolicyDocumentRecord).where(
                PolicyDocumentRecord.policy_family == document.policy_family,
                PolicyDocumentRecord.version == document.version,
            )
        )
        if existing is not None:
            if existing.checksum != checksum:
                raise PolicyIngestionConflictError(
                    "policy family/version is already associated with different content"
                )
            clauses = session.scalars(
                select(PolicyClauseRecord)
                .where(PolicyClauseRecord.document_id == existing.document_id)
                .with_for_update()
            ).all()
            if not reembed:
                _require_embedding_model(clauses, embedding_provider.model_name)
            else:
                # Explicit maintenance operation: the caller owns one transaction,
                # so an embedding failure leaves all old vectors intact.
                for clause in clauses:
                    clause.embedding = validate_embedding(
                        embedding_provider.embed(clause.clause_text),
                        dimensions=POLICY_EMBEDDING_DIMENSIONS,
                    )
                    clause.embedding_model = embedding_provider.model_name
                existing.is_active = document.active
                updated += 1
                continue
            if existing.is_active == document.active:
                unchanged += 1
            else:
                existing.is_active = document.active
                updated += 1
            continue

        source_version = session.scalar(
            select(PolicyDocumentRecord).where(
                PolicyDocumentRecord.source_ref == document.source_ref,
                PolicyDocumentRecord.version == document.version,
            )
        )
        if source_version is not None:
            raise PolicyIngestionConflictError(
                "source_ref/version is already associated with another policy family"
            )

        clauses = document.contract_clauses()
        document_id = _document_id(document)
        document_record = PolicyDocumentRecord(
            path_payload=[p.model_dump(mode="json") for p in document.paths] or None,
            document_id=document_id,
            policy_family=document.policy_family,
            version=document.version,
            source_ref=document.source_ref,
            checksum=checksum,
            is_active=document.active,
        )
        session.add(document_record)
        # No ORM relationship exists between the records, so SQLAlchemy cannot
        # infer the FK insert order. Persist the parent before its clauses.
        session.flush([document_record])
        for clause in clauses:
            vector = validate_embedding(
                embedding_provider.embed(clause.text),
                dimensions=POLICY_EMBEDDING_DIMENSIONS,
            )
            session.add(
                PolicyClauseRecord(
                    path_id=clause.path_id.value if clause.path_id else None,
                    clause_id=clause.clause_id,
                    document_id=document_id,
                    policy_version=clause.policy_version,
                    effective_from=clause.effective_from,
                    effective_to=clause.effective_to,
                    markets=list(clause.applicable_conditions.markets),
                    reason_codes=[
                        reason_code.value
                        for reason_code in clause.applicable_conditions.reason_codes
                    ],
                    categories=list(clause.applicable_conditions.categories),
                    required_claim_ids=[
                        claim_id.value for claim_id in clause.required_claim_ids
                    ],
                    allowed_actions=[action.value for action in clause.allowed_actions],
                    return_policy=clause.return_policy.value,
                    clause_text=clause.text,
                    embedding_model=embedding_provider.model_name,
                    embedding=vector,
                )
            )
        inserted += 1
    return PolicyIngestionResult(
        inserted_documents=inserted,
        updated_documents=updated,
        unchanged_documents=unchanged,
    )


def _as_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _string_values(values: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(values or ())


def _cosine_distance(left: Sequence[float], right: Sequence[float]) -> float:
    denominator = sqrt(sum(value * value for value in left)) * sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 1.0
    return 1 - sum(a * b for a, b in zip(left, right, strict=True)) / denominator


class SqlAlchemyPolicyProvider(PolicyProvider):
    """Return all structurally compatible clauses; vectors only determine order."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider

    def retrieve_policy(
        self,
        case_context: CaseContext,
        order_snapshot: OrderSnapshot,
        reason_code: ReasonCode,
        claimed_line_item_ids: Sequence[OpaqueRef],
        *, selected_path_id: PolicyPathId | None = None,
    ) -> PolicyBundle:
        try:
            normalized_reason_code = ReasonCode(reason_code)
        except ValueError as error:
            raise PolicyRetrievalInputError("reason_code is not recognized") from error
        claimed_categories = self._claimed_categories(
            case_context,
            order_snapshot,
            claimed_line_item_ids,
        )
        request_hash = self._request_hash(
            case_context,
            order_snapshot,
            normalized_reason_code,
            claimed_line_item_ids,
        )
        if selected_path_id is not None:
            if case_context.policy_schema_version != "v2":
                raise PolicyRetrievalInputError("v1 cannot select a v2 path")
            request_hash = _canonical_hash([request_hash, selected_path_id])
        with self._session_factory.begin() as session:
            candidates = self._eligible_candidates(
                session,
                case_context,
                normalized_reason_code,
                claimed_categories,
            )
            _require_embedding_model(
                [candidate.clause for candidate in candidates],
                self._embedding_provider.model_name,
            )
            is_v2 = case_context.policy_schema_version == "v2"
            paths = [PolicyPath.model_validate(p) for p in (candidates[0].document.path_payload or [])] if is_v2 and candidates else []
            status = RetrievalStatus.OK if is_v2 and paths and normalized_reason_code in REASON_PATH else self._retrieval_status(candidates) if not is_v2 else RetrievalStatus.NOT_FOUND
            clauses = (
                self._ranked_contract_clauses(
                    session,
                    candidates,
                    case_context,
                    normalized_reason_code,
                    claimed_categories,
                )
                if status is RetrievalStatus.OK
                else []
            )
            bundle = self._bundle(request_hash, status, clauses) if not is_v2 else PolicyBundle(
                schema_version="v2",policy_bundle_version=POLICY_V2_VERSION+":bundle:"+request_hash[:32],
                retrieval_status=status,retrieved_at=datetime.now(UTC),clauses=clauses,paths=paths,
                common_constraints=["TW_TWD_BUSINESS_GENERAL_PHYSICAL_SINGLE_ITEM"],
                selected_path_id=selected_path_id or REASON_PATH.get(normalized_reason_code))
            bundle = self._persist_bundle(session, request_hash, bundle)
        return bundle

    def get_persisted_bundle(self, bundle_version: OpaqueRef) -> PolicyBundle | None:
        """Recover the exact bundle later referenced by verification."""

        with self._session_factory() as session:
            retrieval = session.scalar(
                select(PolicyRetrievalRecord).where(
                    PolicyRetrievalRecord.bundle_version == bundle_version
                )
            )
        if retrieval is None:
            return None
        try:
            return PolicyBundle.model_validate(retrieval.bundle_payload)
        except ValidationError as error:
            raise RuntimeError(
                "persisted policy bundle violates shared contracts"
            ) from error

    @staticmethod
    def _claimed_categories(
        case_context: CaseContext,
        order_snapshot: OrderSnapshot,
        claimed_line_item_ids: Sequence[OpaqueRef],
    ) -> tuple[str, ...]:
        if case_context.order_ref != order_snapshot.order_ref:
            raise PolicyRetrievalInputError("case context and order snapshot disagree")
        claimed = tuple(claimed_line_item_ids)
        if not claimed:
            raise PolicyRetrievalInputError("claimed_line_item_ids must not be empty")
        if len(claimed) != len(set(claimed)):
            raise PolicyRetrievalInputError("claimed_line_item_ids must be unique")
        categories_by_item = {
            item.line_item_id: item.category_ref for item in order_snapshot.line_items
        }
        unknown = set(claimed) - categories_by_item.keys()
        if unknown:
            raise PolicyRetrievalInputError(
                f"unknown claimed line items: {sorted(unknown)}"
            )
        return tuple(
            sorted({categories_by_item[line_item_id] for line_item_id in claimed})
        )

    @staticmethod
    def _request_hash(
        case_context: CaseContext,
        order_snapshot: OrderSnapshot,
        reason_code: ReasonCode,
        claimed_line_item_ids: Sequence[OpaqueRef],
    ) -> str:
        return _canonical_hash(
            {
                "case_ref": case_context.case_ref,
                "policy_schema_version": case_context.policy_schema_version,
                "first_valid_submitted_at": case_context.first_valid_submitted_at.isoformat() if case_context.first_valid_submitted_at else None,
                "order_facts": order_snapshot.policy_facts.model_dump(mode="json") if order_snapshot.policy_facts else None,
                "market": case_context.market,
                "case_opened_at": case_context.case_opened_at.isoformat(),
                "order_snapshot_ref": order_snapshot.order_snapshot_ref,
                "reason_code": reason_code.value,
                "claimed_line_item_ids": sorted(claimed_line_item_ids),
            }
        )

    @staticmethod
    def _eligible_candidates(
        session: Session,
        case_context: CaseContext,
        reason_code: ReasonCode,
        claimed_categories: Sequence[str],
    ) -> list[_PolicyCandidate]:
        rows = session.execute(
            select(PolicyDocumentRecord, PolicyClauseRecord)
            .join(
                PolicyClauseRecord,
                PolicyClauseRecord.document_id == PolicyDocumentRecord.document_id,
            )
            .where(PolicyDocumentRecord.is_active.is_(True))
        ).all()
        candidates: list[_PolicyCandidate] = []
        for document, clause in rows:
            if case_context.policy_schema_version == "v2":
                if document.policy_family == "DEMO-TW-RETURNS" and document.version == "v2.0" and document.path_payload:
                    candidates.append(_PolicyCandidate(document=document,clause=clause))
                continue
            if document.path_payload:
                continue
            if _as_utc(clause.effective_from) > case_context.case_opened_at:
                continue
            if (
                clause.effective_to is not None
                and _as_utc(clause.effective_to) < case_context.case_opened_at
            ):
                continue
            markets = _string_values(clause.markets)
            if markets and case_context.market not in markets:
                continue
            reason_codes = _string_values(clause.reason_codes)
            if reason_codes and reason_code.value not in reason_codes:
                continue
            categories = _string_values(clause.categories)
            if categories and not set(categories).intersection(claimed_categories):
                continue
            candidates.append(_PolicyCandidate(document=document, clause=clause))
        return candidates

    @staticmethod
    def _retrieval_status(candidates: Sequence[_PolicyCandidate]) -> RetrievalStatus:
        if not candidates:
            return RetrievalStatus.NOT_FOUND
        versions_by_family: dict[str, set[str]] = defaultdict(set)
        for candidate in candidates:
            versions_by_family[candidate.document.policy_family].add(
                candidate.document.version
            )
        if any(len(versions) > 1 for versions in versions_by_family.values()):
            return RetrievalStatus.AMBIGUOUS

        return_policies = {candidate.clause.return_policy for candidate in candidates}
        if {
            ReturnPolicy.REQUIRED.value,
            ReturnPolicy.NOT_REQUIRED.value,
        }.issubset(return_policies):
            return RetrievalStatus.AMBIGUOUS

        common_actions = set(candidates[0].clause.allowed_actions)
        for candidate in candidates[1:]:
            common_actions.intersection_update(candidate.clause.allowed_actions)
        if not common_actions:
            return RetrievalStatus.AMBIGUOUS
        return RetrievalStatus.OK

    def _ranked_contract_clauses(
        self,
        session: Session,
        candidates: Sequence[_PolicyCandidate],
        case_context: CaseContext,
        reason_code: ReasonCode,
        claimed_categories: Sequence[str],
    ) -> list[PolicyClause]:
        query_embedding = validate_embedding(
            self._embedding_provider.embed(
                self._embedding_query(case_context, reason_code, claimed_categories)
            ),
            dimensions=POLICY_EMBEDDING_DIMENSIONS,
        )
        ranked = self._rank_candidates(session, candidates, query_embedding)
        return [self._to_contract_clause(candidate.clause) for candidate in ranked]

    @staticmethod
    def _embedding_query(
        case_context: CaseContext,
        reason_code: ReasonCode,
        claimed_categories: Sequence[str],
    ) -> str:
        category_text = ",".join(claimed_categories) or "ALL_CATEGORIES"
        return (
            f"Return policy for market {case_context.market}; "
            f"reason {reason_code.value}; categories {category_text}."
        )

    @staticmethod
    def _rank_candidates(
        session: Session,
        candidates: Sequence[_PolicyCandidate],
        query_embedding: Sequence[float],
    ) -> list[_PolicyCandidate]:
        if session.get_bind().dialect.name == "postgresql":
            candidate_by_id = {
                candidate.clause.clause_id: candidate for candidate in candidates
            }
            clause_ids = list(candidate_by_id)
            ordered_clause_ids = session.scalars(
                select(PolicyClauseRecord.clause_id)
                .where(PolicyClauseRecord.clause_id.in_(clause_ids))
                .order_by(PolicyClauseRecord.embedding.cosine_distance(query_embedding))
            ).all()
            return [candidate_by_id[clause_id] for clause_id in ordered_clause_ids]

        return sorted(
            candidates,
            key=lambda candidate: _cosine_distance(
                query_embedding,
                candidate.clause.embedding,
            ),
        )

    @staticmethod
    def _to_contract_clause(record: PolicyClauseRecord) -> PolicyClause:
        return PolicyClause(
            path_id=record.path_id,
            clause_id=record.clause_id,
            policy_version=record.policy_version,
            effective_from=_as_utc(record.effective_from),
            effective_to=(
                _as_utc(record.effective_to)
                if record.effective_to is not None
                else None
            ),
            applicable_conditions=ApplicableConditions(
                markets=list(_string_values(record.markets)),
                reason_codes=list(_string_values(record.reason_codes)),
                categories=list(_string_values(record.categories)),
            ),
            required_claim_ids=list(_string_values(record.required_claim_ids)),
            allowed_actions=list(_string_values(record.allowed_actions)),
            return_policy=record.return_policy,
            text=record.clause_text,
        )

    @staticmethod
    def _bundle(
        request_hash: str,
        status: RetrievalStatus,
        clauses: list[PolicyClause],
    ) -> PolicyBundle:
        retrieved_at = datetime.now(UTC)
        bundle_version = "bundle:" + _canonical_hash(
            {
                "request_hash": request_hash,
                "status": status.value,
                "clauses": [clause.model_dump(mode="json") for clause in clauses],
            }
        )[:32]
        return PolicyBundle(
            policy_bundle_version=bundle_version,
            retrieval_status=status,
            retrieved_at=retrieved_at,
            clauses=clauses,
        )

    @staticmethod
    def _persist_bundle(
        session: Session,
        request_hash: str,
        bundle: PolicyBundle,
    ) -> PolicyBundle:
        retrieval_id = "policy-retrieval:" + bundle.policy_bundle_version.removeprefix(
            "bundle:"
        )
        values = {
            "retrieval_id": retrieval_id,
            "request_hash": request_hash,
            "bundle_version": bundle.policy_bundle_version,
            "retrieval_status": bundle.retrieval_status.value,
            "bundle_payload": bundle.model_dump(mode="json"),
            "retrieved_at": bundle.retrieved_at,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(PolicyRetrievalRecord).values(**values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(PolicyRetrievalRecord).values(**values)
        else:
            raise PolicyDataIntegrityError(
                f"unsupported policy retrieval persistence dialect: {dialect_name}"
            )
        session.execute(statement.on_conflict_do_nothing())

        existing = session.scalar(
            select(PolicyRetrievalRecord).where(
                PolicyRetrievalRecord.bundle_version == bundle.policy_bundle_version
            )
        )
        if existing is None:
            raise PolicyDataIntegrityError(
                "policy bundle identity conflicted without a canonical record"
            )
        try:
            persisted = PolicyBundle.model_validate(existing.bundle_payload)
        except ValidationError as error:
            raise PolicyDataIntegrityError(
                "persisted policy bundle violates shared contracts"
            ) from error
        if (
            existing.request_hash != request_hash
            or existing.retrieval_status != bundle.retrieval_status.value
            or persisted.model_dump(mode="json", exclude={"retrieved_at"})
            != bundle.model_dump(mode="json", exclude={"retrieved_at"})
        ):
            raise PolicyDataIntegrityError(
                "policy bundle identity is associated with different content"
            )
        return persisted
