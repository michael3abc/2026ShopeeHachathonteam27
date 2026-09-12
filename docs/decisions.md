> 以下保留原重建工作的歷史記錄。2026-09-12 起工作樹改為既有實作整合，
> 不表示下列未完成項目已重新實作；現行範圍與驗證入口見根目錄 README。

# 技術與產品決策

| ID | 決策 | 原因與影響 |
| --- | --- | --- |
| D01 | GitHub 個人帳號下建立 public `2026ShopeeHachathonteam27`，分支 `main` | 使用者已授權建立與推送；同名既有 repo 不覆寫。登入由正式流程完成。 |
| D02 | 使用合成訂單與模擬退款 | 不接真實金流，不以 evidence metadata 宣稱已完成 OCR／vision。 |
| D03 | 安裝、建置與測試自包含 | 依賴、fixtures、migrations 與生成契約均納入版本控制；本機設定與 secrets 除外。 |
| D04 | Prompt 與契約分別版本化 | 模型輸出須通過形狀與跨物件驗證，模型不擁有金額或退款授權權限。 |
| D05 | 首先交付 T01–T02，再按依賴前進 | 分別記錄骨架、契約、跨服務與真模型驗證，不把 health 或 mock 當作完整功能通過。 |
| D06 | 不新增 LICENSE、不部署公開服務 | 公開可見性不代表選定授權條款；此次授權限 repo 與實作。 |
| D07 | Python 為跨服務契約單一來源 | 從 Pydantic 產生 JSON Schema 與 TypeScript；CI 檢查 drift。 |
| D08 | CaseDetail 新增 typed final_resolution／refund_execution，Memory 由 events replay 還原 | 使用者已確認新增兩欄，完整呈現最終金額與退款結果；裁決核准與 APPLIED 分開保存，HTTP 路徑不變。 |
| D09 | 模型傳輸 schema 將 union 放入 object envelope，所有 object 欄位 required | 符合 [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 限制；傳輸 oneOf 轉 anyOf，程式仍用原 Pydantic discriminator 與語意驗證，不修改公開 DTO。 |

版本差異、外部限制與後續確認均在此記錄。

## Policy v2 與 User Risk 整合決策

以下是目前獨立 `feat/policy-v2-user-risk` worktree 的契約決策；D01–D09 保留
歷史意義。交付與驗收狀態見 [progress](progress.md)，不由本表宣稱完成。

| ID | 決策 | 原因與影響 |
| --- | --- | --- |
| D10 | API 以可信 Demo scenario 在建案時固定 v1／v2 與 owner；User Risk 僅供 v2 新案 | 不接受瀏覽器指定可信版本／配送 facts；保留 v1 語意，禁止跨版 checkpoint 重播或自動降級。 |
| D11 | Policy v2 四條獨立路徑，以 deterministic evaluation、版本化 selection／consent 持久化 | 不交叉套用路徑條件；P01 空 claims 仍驗可信 predicates，P04 僅用逐品項未交付 facts。 |
| D12 | Reviewer 只讀自己的 findings，不讀 Assessment 結論、Memory 或 risk；gate 在核准後計算 | LOW／MEDIUM 可放行；HIGH／UNKNOWN 與金額 gate 走既有人審，保留兩個 gate 與原始 Reviewer verdict，金額原因優先。 |
| D13 | API 擁有 cutoff snapshot 與人工授權；dossier snapshot 逐 facts 比對持久化原件 | cutoff 固定 case_opened_at、排除 current case；重送保持原 facts，不能以相同 snapshot_ref 冒充可信 risk assessment。 |
| D14 | 退款核准與付款釋放分開；required return 仍須買家同意與合法驗收 | 人工授權不跳過履約；付款前重驗 scope／可退額／reservation／consent／evaluation／config。config 改變交專責，不重跑 Reviewer；unknown 用原 execution key 恢復。 |
| D15 | APPLIED ledger、REFUND_SUCCEEDED 與 completion outbox 同 transaction；Agent 以 durable join 排程 v2 Memory | correction／APPLIED 任意順序與重送只對應一個 logical job；未付款不學習；v1／DECLINE 保留原流程。 |
| D16 | 最小 Demo 認證使用個別憑證與 opaque HttpOnly session；角色由後端配置 | owner buyer 操作自己的案件、reviewer 讀 dossier／裁決、operator 模擬物流；JSON、雙 SSE、inspector／narration 都由 API 做角色投影；狀態變更驗 Origin，Provider 保留 service token。 |
| D17 | API migration 維持0013→0014→0015，Agent 使用獨立0001→0002 | 新 risk 三表不讀寫 legacy risk_evaluations；非空 online／offline 降版均阻擋；Agent 首次並行 journal claim 以衝突安全 insert／row lock 處理。 |
| D18 | Launcher project／ports／env file 可參數化，Web build 綁定相同 API URL | 新 worktree 使用獨立 Compose volumes／Redis／ports；不切換原服務，不修改固定 docs/reconstruction。 |
