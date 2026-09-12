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
| D08 | CaseDetail 維持案件與待辦快照，Memory／結果由 events replay 還原 | 採已提出的預設解讀；保留既有 HTTP 欄位與獨立 cursor，不添加隱含的公開欄位。 |

版本差異、外部限制與後續確認均在此記錄。
