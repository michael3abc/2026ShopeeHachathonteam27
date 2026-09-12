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

## 2026-09-12 全流程 Memory 蒸餾

- 以每節點完成時的 typed checkpoint learning trace 取代 correction-only 的學習限制；無修正與合法拒絕也可回顧。
- 回顧不進向量索引；只索引經治理核准的操作經驗，附適用限制與不可推論事項。Policy、Reviewer verdict、退款授權及 Resolver 決策流程不變。
- 新 schema／streams／job IDs 與舊 pending jobs 分隔；API migration 保留歷史來源與治理。切換須先排空或隔離舊工作，不直接重啟現有服務。
- 固定 reconstruction 快照不更新；semantic checker 僅對 v1 Memory fixture 做明示欄位轉接，仍逐 byte 驗證原快照且執行全部負向語意測試。
- 契約／模擬測試不等於真模型學習效益，A/B/C 配對實測須另行報告。

## 2026-09-12 可追溯對話與獨立 Sol-high

- 去識別化對話與 structured request 共用來源 ID，直接記於 learning checkpoint；不依賴 Activity/narration，不存 hidden reasoning。使用者回覆是未驗證主張，Agent 要求不是執行或送達證明。
- 補件文字只供 Distiller 回顧，不新增 Resolver 決策輸入；缺輸入能力是系統缺口，不學成成功方法。既有 Policy、授權、Reviewer 與治理不變。
- Compass Distiller 獨立 Sol/high／Responses，其他模型不變；不 silent retry/fallback。Qwen 不誤套 Compass profile。
- 以 prompt 3.1、dialogue version 與 replay model_profile 區別新工作；已保存結果原樣重播、舊 hash 保留、pending 不換 prompt/model 重算。部署前處理舊 pending；本批不部署。
