"""Isolated migration and real LLM/embedding rehearsal; never deploy services.

Requires a NEW empty PostgreSQL database named memory_rehearsal*. Fixtures are
synthetic; summaries and vectors use real providers. Full JSONL output includes
inputs, scored hits, preservation assertions and timings, never credentials.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

from alembic import command
from alembic.config import Config
from return_agent.capabilities.embeddings import embedding_provider_from_env
from return_agent.capabilities.evidence import (
    SqlAlchemyEvidenceProvider,
    load_evidence_fixture,
    upsert_evidence,
)
from return_agent.capabilities.operational_memory import (
    OperationalMemoryGovernanceService,
    SqlAlchemyOperationalMemoryStore,
)
from return_agent.capabilities.policy import (
    SqlAlchemyPolicyProvider,
    ingest_policy_documents,
    load_policy_fixture,
)
from return_agent.db.models import (
    OperationalMemoryRecord,
    PolicyClauseRecord,
    PolicyRetrievalRecord,
)
from return_agent.db.session import create_session_factory
from return_agent.memory_cli import backfill_memory_vectors
from return_agent_contracts.models import (
    CaseContextLoadResult,
    IntakeResult,
    MemoryCandidate,
    UserTurn,
)
from return_agent_runtime.graph import _prepare_memory_query_node, _retrieve_memory_node
from return_agent_runtime.model import OpenAIStructuredOutputModel
from return_agent_runtime.serialization import json_value
from sqlalchemy import MetaData, Table, inspect, select, text

ROOT = Path(__file__).resolve().parents[1]


def load_provider_env(path: Path) -> None:
    for line in path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if not key.startswith(("RETURN_AGENT_MODEL_", "RETURN_AGENT_EMBEDDING_")):
            continue
        value = value.strip().strip("\"'")
        if key.endswith("_FILE") and not Path(value).is_absolute():
            value = str(path.parent / value)
        os.environ[key] = value


class LegacyEmbedding:
    # Explicit synthetic old-model vectors only for migration invariance checks.
    model_name = "rehearsal-legacy-vector"
    dimensions = 1536

    def embed(self, _text: str) -> list[float]:
        return [1.0] + [0.0] * 1535


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--provider-env", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sessions = create_session_factory(args.database_url)
    engine = sessions.kw["bind"]
    with engine.connect() as connection:
        name = connection.scalar(text("select current_database()"))
    if not name.startswith("memory_rehearsal") or inspect(engine).get_table_names():
        raise RuntimeError(
            "requires a NEW empty isolated database named memory_rehearsal*"
        )
    load_provider_env(args.provider_env.resolve())
    embedding = embedding_provider_from_env()
    if embedding.model_name != "text-embedding-3-large" or embedding.dimensions != 1536:
        raise RuntimeError("rehearsal requires text-embedding-3-large / 1536")
    api_key = os.environ.get("RETURN_AGENT_MODEL_API_KEY")
    if not api_key:
        api_key = (
            Path(os.environ["RETURN_AGENT_MODEL_API_KEY_FILE"]).read_text().strip()
        )
    model = OpenAIStructuredOutputModel(
        model_name=os.environ["RETURN_AGENT_MODEL_NAME"],
        api_key=api_key,
        base_url=os.environ["RETURN_AGENT_MODEL_BASE_URL"],
        temperature=None,
        use_responses_api=True,
        streaming=True,
        timeout_seconds=90,
        max_retries=0,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse to overwrite previous evidence, including partial failed runs.
    with args.output.open("x", encoding="utf-8") as output:

        def emit(step, started, **fields):
            record = {
                "step": step,
                "seconds": round(perf_counter() - started, 4),
                **json_value(fields),
            }
            line = json.dumps(record, ensure_ascii=False)
            output.write(line + "\n")
            output.flush()
            print(line, flush=True)

        os.environ["DATABASE_URL"] = args.database_url
        config = Config(str(ROOT / "apps/api/alembic.ini"))
        started = perf_counter()
        command.upgrade(config, "0010_reviewer_handoff")
        legacy = Table("operational_memories", MetaData(), autoload_with=engine)
        now = datetime.now(UTC)
        with engine.begin() as connection:
            for index, status in enumerate(["CANDIDATE", "APPROVED", "RETIRED"]):
                connection.execute(
                    legacy.insert().values(
                        memory_id=f"LEGACY-{index}",
                        submission_ref=f"legacy-submission:{index}",
                        candidate_payload_hash=str(index) * 64,
                        trigger_conditions=["音箱序號需核對"],
                        recommended_behavior="比較商品與包裝的型號標籤。",
                        rationale="標籤比對有助釐清品項。",
                        source_case_refs=["CASE-LEGACY"],
                        source_revision_event_refs=["REV-LEGACY"],
                        policy_version="LEGACY:v1",
                        claim_registry_version="claim-registry:1.0",
                        scope_market="TW",
                        scope_reason_codes=[],
                        scope_claim_ids=[],
                        scope_categories=[],
                        confidence=0.8,
                        status=status,
                        submitted_at=now,
                        approved_at=now if status != "CANDIDATE" else None,
                        retired_at=now if status == "RETIRED" else None,
                    )
                )
            before = [
                dict(row)
                for row in connection.execute(
                    select(legacy).order_by(legacy.c.memory_id)
                ).mappings()
            ]
        command.upgrade(config, "head")
        emit(
            "migration", started, revision="0011_memory_vectors", legacy_records=before
        )
        started = perf_counter()
        dry = list(backfill_memory_vectors(sessions, embedding, dry_run=True))
        embedded = list(backfill_memory_vectors(sessions, embedding))
        resumed = list(backfill_memory_vectors(sessions, embedding))
        with engine.connect() as connection:
            after = [
                dict(row)
                for row in connection.execute(
                    select(legacy).order_by(legacy.c.memory_id)
                ).mappings()
            ]
        assert before == after
        assert all(item["action"] == "unchanged" for item in resumed)
        emit(
            "backfill",
            started,
            dry_run=dry,
            embedded=embedded,
            resumed=resumed,
            original_columns_unchanged=True,
        )

        fixture = json.loads((ROOT / "data/case-context.json.example").read_text())
        context = CaseContextLoadResult.model_validate(
            {k: fixture[k] for k in ["case_context", "order_snapshot"]}
        )
        docs = load_policy_fixture(ROOT / "data/policy.json.example")
        legacy_embedding = LegacyEmbedding()
        with sessions.begin() as session:
            ingest_policy_documents(session, docs, legacy_embedding)
        historical = SqlAlchemyPolicyProvider(
            sessions, legacy_embedding
        ).retrieve_policy(
            context.case_context,
            context.order_snapshot,
            "ITEM_DAMAGED",
            ["LI-DEMO-SPEAKER"],
        )
        with sessions() as session:
            old_bundles = list(
                session.scalars(select(PolicyRetrievalRecord.bundle_payload))
            )
            old_texts = [
                (r.clause_id, r.clause_text, r.policy_version)
                for r in session.scalars(select(PolicyClauseRecord))
            ]
        started = perf_counter()
        # Same implementation used by return-agent-ingest-policy --reembed.
        with sessions.begin() as session:
            ingest_policy_documents(session, docs, embedding, reembed=True)
        policy = SqlAlchemyPolicyProvider(sessions, embedding)
        bundle = policy.retrieve_policy(
            context.case_context,
            context.order_snapshot,
            "ITEM_DAMAGED",
            ["LI-DEMO-SPEAKER"],
        )
        with sessions() as session:
            assert old_bundles == list(
                session.scalars(select(PolicyRetrievalRecord.bundle_payload))
            )
            assert old_texts == [
                (r.clause_id, r.clause_text, r.policy_version)
                for r in session.scalars(select(PolicyClauseRecord))
            ]
        assert historical == bundle
        emit(
            "policy_reembed",
            started,
            bundle=bundle,
            historical_bundles_and_text_unchanged=True,
        )

        store = SqlAlchemyOperationalMemoryStore(sessions, embedding)
        governance = OperationalMemoryGovernanceService(sessions)
        experiences = [
            (
                "MEM-CLOSEUP",
                "只有商品裂痕近拍，無法觀察包裝與商品的相對位置",
                "補拍外箱和商品同框的全景，並保留裂痕細節。",
                0.3,
            ),
            (
                "MEM-ARRIVAL",
                "收貨當下的開箱影像同時顯示外箱撞擊與商品對應位置裂痕",
                "對照影像時間、外箱撞擊位置與商品損傷位置，記錄彼此是否吻合。",
                0.7,
            ),
            (
                "MEM-SERIAL",
                "音箱與訂單型號不符或序號標籤難辨",
                "比對商品型號和包裝標籤，釐清申請品項。",
                0.99,
            ),
            (
                "MEM-BATTERY",
                "音箱電池膨脹、充電過熱或續航異常",
                "依現有照片與描述區分電池膨脹和一般外殼裂痕，記錄觀察。",
                0.95,
            ),
        ]
        policy_version = bundle.clauses[0].policy_version
        started = perf_counter()
        for name, trigger, action, confidence in experiences:
            candidate = MemoryCandidate(
                memory_id=name,
                retrieval_summary=trigger + "；" + action,
                trigger_conditions=[trigger],
                recommended_behavior=action,
                rationale="經人工確認的可泛化操作經驗（隔離驗收 fixture）。",
                source_case_refs=["CASE-REHEARSAL"],
                source_event_refs=["REV-REHEARSAL"],
                policy_version=policy_version,
                claim_registry_version="claim-registry:1.0",
                scope={
                    "market": "TW",
                    "reason_codes": ["ITEM_DAMAGED"],
                    "categories": ["CAT-AUDIO-SPEAKERS"],
                },
                confidence=confidence,
                status="CANDIDATE",
            )
            store.submit_candidate(candidate)
            store.submit_candidate(candidate)
            governance.approve(name)
        emit("candidate_submission", started, experiences=experiences, idempotent=True)
        with sessions.begin() as session:
            for item in load_evidence_fixture(ROOT / "data/evidence.json.example"):
                upsert_evidence(session, item)
        evidence = SqlAlchemyEvidenceProvider(sessions)
        dependencies = SimpleNamespace(
            model=model, evidence_provider=evidence, operational_memory_store=store
        )
        state = {
            "case_context": context.case_context,
            "order_snapshot": context.order_snapshot,
            "normalized_intent": IntakeResult(
                completeness="COMPLETE",
                order_ref="ORDER-DEMO-001",
                reason_code="ITEM_DAMAGED",
                reason_summary="買家表示音箱收到時有裂痕，希望退貨。",
                requested_action="REFUND",
                claimed_line_item_ids=["LI-DEMO-SPEAKER"],
            ),
            "claimed_line_item_ids": ["LI-DEMO-SPEAKER"],
            "policy_bundle": bundle,
            "evidence_bundle": [],
            "operational_memory": [],
            "conversation_turns": [],
        }
        for phase, artifact in [
            ("initial", "EV-DEMO-DAMAGE-CLOSEUP"),
            ("supplement", "EV-DEMO-ARRIVAL-PACKAGING-AND-DAMAGE"),
        ]:
            state["conversation_turns"].append(
                UserTurn(
                    turn_id=phase,
                    role="USER",
                    text="提供照片。",
                    attached_artifact_refs=["artifact://demo/" + artifact],
                    received_at=now,
                )
            )
            started = perf_counter()
            state.update(_prepare_memory_query_node(dependencies)(state))
            summary_seconds = perf_counter() - started
            if state["_route"] != "retrieve_memory":
                emit(phase, started, result=state.get("memory_retrieval"))
                raise RuntimeError("live summary failed; see observation")
            search_started = perf_counter()
            state.update(_retrieve_memory_node(dependencies)(state))
            emit(
                phase,
                started,
                summary_seconds=round(summary_seconds, 4),
                search_seconds=round(perf_counter() - search_started, 4),
                evidence=state["evidence_bundle"],
                result=state["memory_retrieval"],
            )
            assert (
                state["memory_retrieval"].status == "OK"
                and len(state["operational_memory"]) == 3
            )
        with sessions() as session:
            memory_models = list(
                session.scalars(
                    select(OperationalMemoryRecord.embedding_model).distinct()
                )
            )
            policy_models = list(
                session.scalars(select(PolicyClauseRecord.embedding_model).distinct())
            )
        assert memory_models == policy_models == ["text-embedding-3-large"]
        emit(
            "complete",
            perf_counter(),
            embedding_model=embedding.model_name,
            dimensions=1536,
            memory_models=memory_models,
            policy_models=policy_models,
        )
    engine.dispose()


if __name__ == "__main__":
    main()
