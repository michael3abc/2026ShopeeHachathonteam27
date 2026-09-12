"""Run summary-only narration against the configured model and isolated Redis."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from uuid import uuid4

from redis.asyncio import Redis
from return_agent_contracts.activity import (
    NARRATION_STREAM,
    ActivityEmission,
    ActivityFacts,
    NarrationJob,
    NodeSummary,
)
from return_agent_service.activity_workers import NarrationWorker
from return_agent_service.main import _configured_model


async def run(redis_url: str, output: Path | None = None) -> None:
    redis = Redis.from_url(redis_url, decode_responses=True)
    model = _configured_model(compass=True)
    worker = NarrationWorker(redis, model, timeout=45, concurrency=1)
    await worker.setup()
    records = []
    try:
        for node, facts in (
            (
                "assess_case",
                ActivityFacts(
                    outcome="SUFFICIENT_FOR_APPROVAL", next_node="propose_decision"
                ),
            ),
            (
                "reviewer",
                ActivityFacts(verdict="REVISE", next_node="record_revision_event"),
            ),
            (
                "reviewer",
                ActivityFacts(
                    verdict="APPROVE",
                    reason_codes=["HIGH_VALUE_ITEM"],
                    next_node="await_human_review",
                ),
            ),
        ):
            source = ActivityEmission(
                event_id=uuid4().hex,
                case_ref="CASE-SYNTHETIC-NARRATION-SMOKE",
                run_id="RUN-SMOKE",
                scope="CASE",
                node=node,
                operation_id=uuid4().hex,
                attempt_id=uuid4().hex,
                occurred_at=datetime.now(UTC),
                payload=NodeSummary(facts=facts),
            )
            job = NarrationJob(job_id="narration:" + source.event_id, source=source)
            await redis.xadd(NARRATION_STREAM, {"body": job.model_dump_json()})
            started = monotonic()
            await worker.run_once()
            raw = await redis.get("activity-narration-result:" + job.job_id)
            if raw is None:
                raise RuntimeError(
                    "smoke requires a dedicated Redis with no other narration jobs"
                )
            result = ActivityEmission.model_validate_json(raw)
            record = {
                "synthetic": True,
                "model": model.model_name,
                "summary": source.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
                "elapsed_seconds": round(monotonic() - started, 3),
            }
            records.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
            if result.payload.status != "COMPLETED":
                raise RuntimeError(
                    "narration smoke unavailable; inspect safe result above"
                )
    finally:
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(records, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        await redis.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redis-url", required=True, help="Dedicated test Redis only")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.redis_url, args.output))
