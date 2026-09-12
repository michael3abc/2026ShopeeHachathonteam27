# Cross-app Tests

Cross-app integration and end-to-end tests live here. Contract unit tests live in
[`apps/contracts/tests`](../apps/contracts/tests/).

The no-UI E2E uses SQLite and `fakeredis` while exercising the real Case API,
transactional outbox, Redis adapters, Agent Service worker, LangGraph runtime,
and Agent-event projection:

```bash
LANGGRAPH_STRICT_MSGPACK=true \
  uv run --all-packages pytest tests/test_no_ui_e2e.py
```

The test creates a case over HTTP, observes an evidence interrupt, resumes it
with an artifact reference, and receives a valid `FULL_REFUND` handoff. Because the
production refund mutation adapter is intentionally not composed yet, the API
must remain at `EXECUTING` and leave that terminal service event pending. The
test treats this as an explicit integration boundary, not a completed refund.
Strict msgpack mode additionally verifies that the evidence interrupt checkpoint can
be restored without enabling unrestricted Python-object deserialization.

Browser regression tests live with the Web app (`apps/web/tests`) and use mocked
Backend responses. The opt-in cross-service browser smoke is
[`scripts/run_ui_e2e.mjs`](../scripts/run_ui_e2e.mjs); it drives the real UI, Case API,
Redis, Agent, Qwen, and Providers and requires an actual `RESOLVED / REVIEWER_APPROVE` result.
Run `npm --prefix apps/web run test:e2e:live` only against the integrated demo stack.

Run the complete Python checks using `make check`; the monorepo invokes test suites separately to avoid the two `tests` package names colliding in a single pytest collection. Reviewer budget exhaustion, human resume and authorization are covered by runtime/API tests; browser tests display unresolved objections and exercise APPROVE / EDIT / REJECT.
