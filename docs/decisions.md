# 重建決策

| ID | 決策 | 原因與影響 |
| --- | --- | --- |
| D01 | GitHub 個人帳號下建立 public `2026ShopeeHachathonteam27`，分支 `main` | 使用者已授權建立與推送；同名既有 repo 不覆寫。登入由正式流程完成。 |
| D02 | 只依本機規格文字重新實作 | 不複製或執行附帶 schemas、prompts、fixtures、SQL、工具或部署資產。不接觸原 repository、歷史或私人服務。 |
| D03 | `reference/`、`AGENTS.md` 留在本機且忽略 | 沿用使用者既有設定。公開專案的安裝、建置、測試必須自包含。 |
| D04 | 重寫 prompt 使用本次獨立版本 | 無法宣稱與原 prompt 逐字等價；保留任務輸入、輸出與安全規則，行為以本次測試判斷。 |
| D05 | 首先交付 T01–T02，再按依賴前進 | 不以骨架、health 或 mock 通過宣稱完整重建。 |
| D06 | 不新增 LICENSE、不部署公開服務 | 公開可見性不代表選定授權條款；此次授權限 repo 與實作。 |
| D07 | 保留欄位定義與業務常數，重新編寫其實作 | 唯讀核對字典、schemas 的欄位／enum 及 registry 的行為關係；不匯入或複製資產檔案、不以原 schema 生成程式。registry 說明文字、所有實作與 fixtures 重新撰寫。 |
| D08 | CaseDetail 文字與 schema 差異待確認 | 文字要求最新 Memory／final，公開 schema 沒有對應欄位。已提出保持 schema、由持久化 events replay 還原的解讀；目前尚未實作该 API。 |

版本差異、外部限制與後续確認均在此記錄，不修改唯讀規格。
