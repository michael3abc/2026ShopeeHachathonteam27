"""Authoritative user history snapshots. All mutation stays in the API DB."""
from datetime import UTC, datetime, timedelta
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, sessionmaker
from return_agent_contracts.enums import ReasonCode
from return_agent_contracts.interfaces import CaseContextProvider
from return_agent_contracts.policy_v2 import content_hash
from return_agent_contracts.user_risk import UserRiskSnapshot
from return_agent_contracts.models import HumanReviewDossier
from return_agent.db.case import CaseRecord
from return_agent.db.models import UserRiskProfileRecord, UserRiskEventRecord, UserRiskSnapshotRecord


def utc(value: datetime) -> datetime:
    # SQLite drops tzinfo; PostgreSQL retains it. DB values are always UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def validate_persisted_dossier_snapshot(
    session: Session, dossier: HumanReviewDossier, case_ref: str
) -> None:
    """Human authority may override a gate, but cannot invent its input facts."""
    snapshot = dossier.user_risk_snapshot
    if snapshot is None:
        return  # UNKNOWN and revision exhaustion legitimately have no snapshot.
    record = session.get(UserRiskSnapshotRecord, snapshot.snapshot_ref)
    case = session.get(CaseRecord, case_ref)
    if (
        record is None
        or SqlAlchemyUserRiskProvider._snapshot(record) != snapshot
        or case is None
        or case.policy_schema_version != "v2"
        or snapshot.case_ref != case.case_ref
        or snapshot.user_ref != case.user_ref
        or snapshot.as_of != utc(case.created_at)
        or snapshot.reason_code != dossier.proposal_history[-1].proposed_decision.reason_code
    ):
        raise ValueError("human dossier differs from the persisted risk snapshot")


def append_risk_event(session: Session, *, user_ref: str, case_ref: str, order_ref: str,
    event_type: str, reason_code: str | None, occurred_at: datetime) -> None:
    """Use caller's transaction; a content-changing replay is an integrity error."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    if event_type not in {"CLAIM_REGISTERED", "REFUND_SUCCEEDED"} or (event_type == "CLAIM_REGISTERED" and reason_code is None):
        raise ValueError("invalid user risk event")
    if reason_code is not None:
        ReasonCode(reason_code)
    values = dict(event_ref=f"user-risk:{case_ref}:{event_type}", user_ref=user_ref, case_ref=case_ref,
        order_ref=order_ref, event_type=event_type, reason_code=reason_code, occurred_at=occurred_at, created_at=datetime.now(UTC))
    dialect = session.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
    if insert is None:
        raise ValueError("unsupported risk ledger database")
    session.execute(insert(UserRiskEventRecord).values(**values).on_conflict_do_nothing(index_elements=["case_ref", "event_type"]))
    record = session.scalar(select(UserRiskEventRecord).where(UserRiskEventRecord.case_ref == case_ref, UserRiskEventRecord.event_type == event_type))
    if record is None or any(getattr(record, key) != values[key] for key in ("event_ref","user_ref","order_ref","reason_code")) or utc(record.occurred_at) != utc(occurred_at):
        raise ValueError("risk event replay changed immutable facts")


class SqlAlchemyUserRiskProvider:
    def __init__(self, session_factory: sessionmaker[Session], case_context_provider: CaseContextProvider):
        self._sessions = session_factory
        self._contexts = case_context_provider

    @staticmethod
    def _snapshot(record: UserRiskSnapshotRecord) -> UserRiskSnapshot:
        result = UserRiskSnapshot.model_validate(record.payload)
        if content_hash(record.payload) != record.payload_hash or (result.snapshot_ref, result.case_ref, result.user_ref, result.reason_code, result.as_of) != (record.snapshot_ref, record.case_ref, record.user_ref, record.reason_code, utc(record.as_of)):
            raise ValueError("persisted risk snapshot integrity mismatch")
        return result

    def load_snapshot(self, snapshot_ref: str) -> UserRiskSnapshot:
        with self._sessions() as session:
            record = session.get(UserRiskSnapshotRecord, snapshot_ref)
            if record is None:
                raise LookupError("unknown risk snapshot")
            return self._snapshot(record)

    def prepare_snapshot(self, case_ref: str, reason_code: ReasonCode, as_of: datetime) -> UserRiskSnapshot:
        context = self._contexts.load_case_context(case_ref).case_context
        if context.policy_schema_version != "v2" or as_of != context.case_opened_at:
            raise ValueError("risk snapshot requires the v2 case opening time")
        ref = f"user-risk-snapshot:{content_hash([case_ref, reason_code, as_of])}"
        with self._sessions.begin() as session:
            case = session.scalar(select(CaseRecord).where(CaseRecord.case_ref == case_ref).with_for_update())
            if case is None:
                raise LookupError("unknown case")
            existing = session.get(UserRiskSnapshotRecord, ref)
            if existing is not None:
                result = self._snapshot(existing)
                if result.user_ref != case.user_ref:
                    raise ValueError("risk snapshot owner changed")
                return result
            profile = session.scalar(select(UserRiskProfileRecord).where(UserRiskProfileRecord.user_ref == case.user_ref).with_for_update())
            if profile is None:
                raise LookupError("user risk profile is unavailable")
            if utc(profile.account_created_at) > as_of:
                raise ValueError("account created after case opening")
            append_risk_event(session, user_ref=case.user_ref, case_ref=case_ref, order_ref=case.order_ref,
                event_type="CLAIM_REGISTERED", reason_code=reason_code.value, occurred_at=as_of)
            filters = [UserRiskEventRecord.user_ref == case.user_ref, UserRiskEventRecord.occurred_at >= as_of - timedelta(days=90),
                UserRiskEventRecord.occurred_at < as_of, UserRiskEventRecord.case_ref != case_ref]
            claims = session.scalar(select(func.count()).select_from(UserRiskEventRecord).where(*filters,
                UserRiskEventRecord.event_type == "CLAIM_REGISTERED", UserRiskEventRecord.reason_code == reason_code.value))
            refunds = session.scalar(select(func.count(distinct(UserRiskEventRecord.order_ref))).where(*filters,
                UserRiskEventRecord.event_type == "REFUND_SUCCEEDED"))
            result = UserRiskSnapshot(snapshot_ref=ref, case_ref=case_ref, user_ref=case.user_ref, reason_code=reason_code,
                as_of=as_of, created_at=datetime.now(UTC), account_age_days=(as_of-utc(profile.account_created_at)).days,
                orders_90d=profile.orders_90d, same_reason_claims_90d=claims, refunded_orders_90d=refunds)
            payload = result.model_dump(mode="json")
            session.add(UserRiskSnapshotRecord(snapshot_ref=ref, case_ref=case_ref,user_ref=case.user_ref,
                reason_code=reason_code.value,as_of=as_of,payload=payload,payload_hash=content_hash(payload)))
            return result
