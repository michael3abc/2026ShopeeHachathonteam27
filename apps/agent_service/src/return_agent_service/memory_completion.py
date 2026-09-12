"""Join immutable correction input and APPLIED in either arrival order."""
from sqlalchemy import JSON, Boolean, Column, MetaData, String, Table, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from return_agent_contracts.completion import RefundAppliedEvent
from return_agent_contracts.policy_v2 import content_hash
from return_agent_contracts.service import MemoryDistillationJob

METADATA = MetaData()
JOINS = Table("memory_completion_joins", METADATA,
    Column("resolution_ref", String(256), primary_key=True),
    Column("case_ref", String(128), nullable=False),
    Column("resolution_hash", String(64), nullable=False),
    Column("correction_job", JSON(none_as_null=True)),
    Column("applied_event", JSON(none_as_null=True)),
    Column("published", Boolean, nullable=False, default=False))


class MemoryCompletionStore:
    def __init__(self, engine):
        self.engine = engine

    def correction(self, job: MemoryDistillationJob):
        resolution = job.payload.input.final_resolution
        self._record(resolution.handoff_id,job.case_ref,content_hash(resolution),
            "correction_job",job.model_dump(mode="json"))

    def applied(self, event: RefundAppliedEvent):
        if event.authorization_ref != f"authorization:{event.resolution_ref}":
            raise ValueError("completion authorization does not match resolution")
        self._record(event.resolution_ref,event.case_ref,event.resolution_hash,
            "applied_event",event.model_dump(mode="json"))

    def _record(self, ref, case_ref, digest, field, payload):
        with self.engine.begin() as connection:
            insert = pg_insert if connection.dialect.name == "postgresql" else sqlite_insert
            connection.execute(insert(JOINS).values(resolution_ref=ref,case_ref=case_ref,
                resolution_hash=digest,published=False).on_conflict_do_nothing(index_elements=["resolution_ref"]))
            row = connection.execute(select(JOINS).where(JOINS.c.resolution_ref == ref).with_for_update()).mappings().one()
            if row["case_ref"] != case_ref or row["resolution_hash"] != digest:
                raise ValueError("completion join binding mismatch")
            if row[field] is not None:
                before, after = dict(row[field]), dict(payload)
                if field == "correction_job":
                    before.pop("issued_at",None)
                    after.pop("issued_at",None)
                if before != after:
                    raise ValueError("completion join immutable input changed")
                return
            connection.execute(update(JOINS).where(JOINS.c.resolution_ref == ref).values({field:payload}))

    def next_job(self):
        with self.engine.connect() as connection:
            row = connection.execute(select(JOINS).where(JOINS.c.published.is_(False),
                JOINS.c.correction_job.is_not(None),JOINS.c.applied_event.is_not(None))
                .order_by(JOINS.c.resolution_ref).limit(1)).mappings().first()
            return MemoryDistillationJob.model_validate(row["correction_job"]) if row else None

    def published(self, job):
        with self.engine.begin() as connection:
            connection.execute(update(JOINS).where(JOINS.c.resolution_ref == job.payload.input.final_resolution.handoff_id)
                .values(published=True))
