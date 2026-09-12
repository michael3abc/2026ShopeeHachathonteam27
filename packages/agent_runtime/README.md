# Return Agent Runtime

`packages/agent_runtime` 提供 Adaptive Return Resolution Agent 的純 Python library：LangGraph、LLM structured-output adapter、deterministic assembly，以及 typed start/resume 介面。它直接使用 [`apps/contracts`](../../apps/contracts/README.md) 的 DTO 與 Provider Protocol，不複製 contract。

本 package **不包含** FastAPI route、前端、DB、HTTP client、真實 Provider 實作或退款執行。Operational Memory 在 graph 內提供 `query_approved` retrieval 與全案 typed learning trace，並提供可由 service worker 呼叫的純 `MemoryDistiller`；Redis transport、candidate submission 與 approval 不屬於 runtime。

所有完成裁決的案件（含無修正與拒絕）可輸出整案回顧、學習判定及至多一則經驗候選；缺失、不安全或超限歷程明確 SKIP，不阻塞結案。Trace 存於 checkpoint，不依賴 Activity／narration。經驗不能改寫 Policy 或直接核准退款；整案回顧不進入向量索引。

Trace 保存可追溯的去識別化初始／澄清／補件對話，標記使用者未驗證主張及 Agent 要求；每句 2000 字元、每事件 4 句，超限不截斷。`EvidenceResume.turn` 的文字僅供學習，不改 Resolver evidence／assessment 或 conversation_turns；附件須與 artifact_refs 相同。旧無對話 trace 會明示 SKIP。

Distiller prompt 為 `memory-distiller:3.1`。Service 獨立注入 Sol/high model；adapter 的 `reasoning_effort` 只支援 Responses，`max_output_tokens` 轉為實際 output budget。模型錯誤不 fallback。配置、replay migration 與 rollout 邊界見 [Agent Service](../../apps/agent_service/README.md)。

## 安裝與測試

從 repository root 執行：

```bash
uv sync --locked --all-packages
uv run --package return-agent-runtime pytest packages/agent_runtime/tests
```

測試使用 in-process deterministic fakes，不呼叫 live LLM 或外部 API。

## OpenAI-compatible model

`OpenAIStructuredOutputModel` 可連接 Chat Completions compatible endpoint。
Endpoint、model 與 API key 都由 composition root 注入，不硬編在 runtime：

```python
import os

from return_agent_runtime import OpenAIStructuredOutputModel

model = OpenAIStructuredOutputModel(
    model_name="qwen3.8-27b-q4-gguf",
    api_key=os.environ["RETURN_AGENT_MODEL_API_KEY"],
    base_url=os.environ["RETURN_AGENT_MODEL_BASE_URL"],
    timeout_seconds=180,
    max_retries=0,
    temperature=0,
    use_responses_api=False,
    include_schema_in_prompt=True,
    streaming=True,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)
```

公開 Gateway 可使用 `https://qwen.yoyoserver.com/v1`；API key 與 base URL 必須
由 Agent Service composition root 或環境變數注入。若 Gateway 尚未部署，開發機也可建立
SSH tunnel，再把 base URL 設為 `http://127.0.0.1:18080/v1`：

```bash
ssh -N -L 18080:127.0.0.1:8080 yoyo-server
```

`include_schema_in_prompt=True` 是 compatible-server 模式：JSON Schema 除了
傳給 `response_format` 約束解碼，也會放入 model input，避免 server 只套用
grammar、模型本身卻看不到欄位語意。正式 OpenAI endpoint 可維持預設 `False`。
連線或 schema 驗證錯誤會原樣回到 graph 的 fail-closed 路徑，不降級成 JSON
mode，也不做隱藏 retry。

## Python runtime

```python
from langgraph.checkpoint.memory import InMemorySaver

from return_agent_runtime import (
    AgentDependencies,
    ReturnAgentRuntime,
    create_checkpoint_serializer,
)

dependencies = AgentDependencies(
    model=model,
    case_context_provider=case_context_provider,
    policy_provider=policy_provider,
    verification_provider=verification_provider,
    human_review_provider=human_review_provider,
    operational_memory_store=operational_memory_store,
    evidence_provider=evidence_provider,
)

# InMemorySaver 只適合本機開發與測試；正式環境必須注入 durable checkpointer。
runtime = ReturnAgentRuntime(
    dependencies,
    InMemorySaver(serde=create_checkpoint_serializer()),
)
result = runtime.start(
    thread_id="THREAD-001",
    case_ref="CASE-001",
    initial_turn=user_turn,
)
```

需要觀察 node lifecycle 時使用 async gateway；它從 LangGraph `tasks` stream
統一產生 `NodeExecutionObservation`，不修改 node，也不暴露 state 或 node output：

```python
observations = []
result = await runtime.astart(
    thread_id="THREAD-001",
    case_ref="CASE-001",
    initial_turn=user_turn,
    observer=observations.append,
)
```

`aresume()` 提供相同 observer contract。Observer 是 best-effort telemetry；其
validation、callback 或 transport exception 只記錄 log，不改變 graph execution。
同步 `start()` / `resume()` 保持不變。

`start()` 會執行到 terminal 或第一個 interrupt。`resume()` 必須使用相同 `thread_id`，並傳入符合目前 pause point 的 payload：

```python
from return_agent_runtime import (
    ClarificationResume,
    EvidenceResume,
    HumanReviewPollResume,
)

runtime.resume(
    thread_id="THREAD-001",
    payload=ClarificationResume(kind="CLARIFICATION", turn=new_user_turn),
)

runtime.resume(
    thread_id="THREAD-001",
    payload=EvidenceResume(
        kind="EVIDENCE_REQUEST",
        artifact_refs=["artifact://evidence/EV-002"],
    ),
)

runtime.resume(
    thread_id="THREAD-001",
    payload=HumanReviewPollResume(kind="HUMAN_REVIEW"),
)
```

`AgentRunResult.status` 為 `INTERRUPTED` 或 `COMPLETED`。完成時只會帶一個 [`ResolutionHandoff`](../../apps/contracts/schemas/agent/v1/ResolutionHandoff.schema.json) 或 [`ManualEscalationHandoff`](../../apps/contracts/schemas/agent/v1/ManualEscalationHandoff.schema.json)；Agent 不會執行退款。

`create_checkpoint_serializer()` 只允許 graph state 使用到的專案 DTO 與 enum
反序列化。自行注入 checkpointer 時也應使用相同 serializer；跨 interrupt 的 E2E
會以 `LANGGRAPH_STRICT_MSGPACK=true` 驗證 checkpoint 可安全還原。

## Runtime 邊界

astart／aresume 可傳 activity_observer 與 run_id（Agent Service 使用 command_id）。
custom stream 在實際 node/model/provider 執行期間傳遞 ActivityEmission，與既有 NodeObserver
並存。只觀察、不改 routing；observer 失敗安全記錄後繼續。GraphInterrupt 為 PAUSED，
每個真正完成 node 才產生安全 NodeSummary。Runtime 不組裝 narration 或傳輸。

- Provider 仍使用 [`return_agent_contracts.interfaces`](../../apps/contracts/src/return_agent_contracts/interfaces.py) 的同步 signature，由 service/integration owner 提供真實 adapter。
- OpenAI runtime 必須明確提供 model name；API key 交給 `ChatOpenAI` 的標準環境設定或 constructor，不寫死於 repository。
- 所有 prompt packaged resource 都與 [`docs/spec/05-prompts`](../../docs/spec/05-prompts/) 的 system prompt 做 exact-match regression test。
- Resolver 看不到退款金額；Reviewer 看不到 Resolver assessment 或 Operational Memory。
- Runtime 會覆寫 LLM schema 中的 evidence request ID、Reviewer prompt version 與 review timestamp；進入 state 的值一律由 graph 產生。
- `UserTurn.attached_artifact_refs` 會在 context 與 claimed items 確定後解析，不要求使用者於補件 interrupt 重傳既有附件。
- Node lifecycle 由 runtime 外層觀察；graph node 不呼叫 Backend/UI HTTP endpoint。
- Correction trace 與 proposal history 會保留在 graph state；有修正的結案案件會組裝 `MemoryDistillationInput` 存入 checkpoint。此 package 提供獨立 `MemoryDistiller`，但不擁有 Redis enqueue、worker lifecycle、candidate storage 或 approval。
