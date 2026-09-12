# Demo data templates

For the three-case, five-minute recording plan, fixture payloads, manual media
checklist, DB loading instructions and runtime integration blockers, see
[Demo Case Study](demo-case-study/README.md). This data pack is not auto-loaded.
For sequential A/B/C execution with the keyed multi-order fixture provider, use
the [E2E runbook](demo-case-study/E2E.md), fixture preparation script and Compose override.
API bootstrap then ingests the prepared fixtures and approves the synthetic speaker preload.

This directory contains safe, versioned templates for provider integration and
future end-to-end tests. Every JSON file ends in `.json.example` so it is not
loaded automatically and must not be treated as production policy or customer
data.

## Files

| File | Owner / consumer | Purpose |
| --- | --- | --- |
| `policy.json.example` | Louis / Policy RAG | Versioned, active policy documents and clauses. |
| `evidence.json.example` | Louis / Evidence provider | Neutral metadata for user and system evidence. |
| `operational-memory.json.example` | Yoyo submits, Louis stores | Memory candidates and intended approval state. |
| `case-context.json.example` | Allen / CaseContextProvider | Authoritative order snapshot and initial user turn. |
| `human-review.json.example` | Allen / Human Review | Contract-shaped APPROVE, EDIT and REJECT outcomes. |
| `scenarios.json.example` | Integration owner | Cross-provider test cases and expected observations. |

## Use rules

- Keep `policy` categories equal to `case-context.order_snapshot.line_items[].category_ref`.
- Keep `evidence.subject` equal to a line-item ID or `ORDER`.
- Keep Memory `policy_version`, market, reason code, claims and category consistent
  with the policy and scenario being tested.
- Policy and Evidence arrays can be copied to the existing fixture locations and
  loaded using `return-agent-ingest-policy` and `return-agent-seed-evidence`.
- Memory is submitted as `CANDIDATE`, then approved by the governance service;
  do not edit the stored status to manufacture an approved memory.
- Reviewer approves or requests concrete revisions; after three corrections an unresolved review enters Human Review. After APPROVE, Python monetary authorization also requires Human Review for high amounts or unconfigured currencies.
- Compose mounts `config/reviewer-gates.json` read-only into API and Agent; keep their effective version/hash identical. Thresholds are configuration, not DB seed.
- Memory candidates require `retrieval_summary`; submission and retrieval require a compatible embedding provider. Queries require `query_summary` and return ordered `MemorySearchHit` objects (`memory`, `similarity`).
- Human review requests must bind the actual pending `handoff_id`. Human APPROVE alone does not trigger distillation; correction traces may still yield SKIP. The three-case learning demonstration remains conditional on an actual approved candidate.
- Case context, Human Review and scenarios require Allen/Yoyo integration adapters.
- All amounts are decimal strings. All timestamps are UTC RFC 3339 strings.

## Fixture commands

```bash
uv run --package return-agent-api return-agent-ingest-policy \
  --input data/policy.json.example

uv run --package return-agent-api return-agent-seed-evidence \
  --input data/evidence.json.example
```

Policy ingestion uses the runtime embedding provider. Integration tests should
inject a deterministic embedding adapter rather than make live model calls.
