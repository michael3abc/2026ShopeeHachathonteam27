# 規格→來源／測試對照

下列路徑只供baseline稽核，不是重建必備source。資產來源/hash在 [source-assets](assets/source-assets.json)，全部交付hash在 [manifest](manifest.json)。生成schemas不可手改；source-only匯出工具留repo scripts，不在ZIP帶應用程式碼。

| 規則族 | baseline來源（稽核用） | 既有測試證據／重建cases |
| --- | --- | --- |
| M01-R01..11 | apps/contracts/src/return_agent_contracts/{base,enums,models,registry,validation,review_gates,transport,operations,ui,activity}.py | apps/contracts/tests/contracts/test_{models,validation,json_schema_parity,review_gates,activity}.py；C01..06,C10..13 |
| M02-R01..06 | packages/agent_runtime/src/return_agent_runtime/{graph,state,assembly,runtime,checkpoint,serialization,model,prompts,memory}.py | packages/agent_runtime/tests/test_{graph_workflow,interrupt_resume,decision_semantics,revision_and_failures,memory_retrieval,prompt_and_boundaries,checkpoint,activity_tracing}.py；C07..14 |
| M03-R01..08 | apps/api/src/return_agent/{app,store,sse,agent_commands,agent_bridge,activities,activity_bridge}.py與db/* | apps/api/tests/test_{cases,agent_bridge,human_adjudication,dossier_integrity,activities}.py；C13..18 |
| M04-R01..09 | apps/api/src/return_agent/capabilities/{integration,evidence,safety,human_review,refund}.py | apps/api/tests/test_{safety,evidence_capability,refund_execution,reviewer_handoff,human_adjudication}.py；C10..13,C19..21 |
| M05-R01..11 | apps/api/src/return_agent/capabilities/{policy,embeddings,operational_memory}.py；memory_cli.py；runtime/memory.py | apps/api/tests/test_{policy_rag,memory_vectors,operational_memory}.py；runtime/test_memory_retrieval.py；C22..29 |
| M06-R01..12 | apps/agent_service/src/return_agent_service/{main,settings,composition,worker,broker,journal,memory_replay,memory_worker,memory_enqueue_worker,memory_supervision,activity_workers}.py | apps/agent_service/tests/test_{worker,broker,memory_worker,memory_enqueue_worker,activity_workers,model_profiles}.py；tests/test_activity_transport.py；C15..18,C30..36 |
| M07-R01..09 | apps/web/src/{app,components,lib,contracts}；components/case-workspace.tsx；lib/use-case-activities.ts | apps/web/src/lib/*.test.mjs；apps/web/e2e/*；C15..18,C29..36 |
| M08-R01..08 | docker-compose.yml、各Dockerfile/pyproject、uv.lock、apps/web/package-lock.json、data/demo-case-study/* | tests/test_no_ui_e2e.py、test_review_gate_compose.py；scripts/run_no_ui_e2e.py、run_ui_e2e.mjs；A/B/C |

完整schema欄位、SQLconstraints、validator拒絕字串、env access、Provider參數固定baseline機械匯出。此表是語意分組，不宣稱每個既有test本次都重跑；實際執行以驗證報告為準。
