# 本次交付的驗證紀錄

驗證基準：485048cc73dc5c8f64d08034f49e318827418f80；日期2026-09-11。只改文件、規格資產與文件工具／測試，未改runtime、API或UI業務程式。

| 檢查／命令（原專案內執行） | 結果 |
| --- | --- |
| scripts/export_reconstruction.py --check | baseline程式drift檢查、330項確定性資產逐byte一致；包含13份逐版upgrade SQL與0012保護downgrade，無DB連線 |
| scripts/check_reconstruction_semantics.py | cross-object正例含兩人審入口PASS；8種錯誤dossier拒絕、7組gate邊界PASS；A/B/C、12筆Evidence、1份Policy document合法 |
| tools/verify_package.py --schemas | manifest檔案/hash、離線連結、schema refs、45組schema範例、8modules/10tasks/36cases、12必需images、private-material與source排除PASS |
| pytest tests/test_reconstruction_package.py -q | 10 passed；fresh temp解壓、Python -I隔離執行；兩次ZIP逐byte一致；hash損毀、缺件、外連、壞schema ref、任務循環、invalid fixture、混入application code均拒絕 |
| pytest apps/contracts/tests/contracts -o addopts='' -q | 80 passed |
| pytest apps/api/tests -q | 205 passed；2個既有warning（Starlette/AnyIO deprecated alias、負例Pydanticserialization） |
| pytest packages/agent_runtime/tests -o addopts='' -q | 79 passed |
| pytest apps/agent_service/tests -o addopts='' -q | 68 passed；1個既有Starlette/AnyIO warning |
| scripts/render_reconstruction.mjs | architecture 5697×4044、sequence 7152×6978；Mermaid source與PNG並存，已檢視 |
| baseline Agent graph copy | 8976×8022；原Mermaid與PNG逐byte複製 |

以上Python命令使用uv run --all-packages。合計442個測試通過。最初把不同目錄測試混在同一pytest invocation，API test的relative import收集失敗；改用既有各package suite入口即通過，沒有改動測試/validator或弱化CI。

## 未執行與不宣稱

- 未從空專案另實作完整系統；本包通過不等於重建系統已成功。
- 未重跑真LLM A/B/C；提供的是實跑步驟、syntheticfixtures與需保存的output定義。
- 未對現存DB執行migration、未Docker build／部署、未改UI或重跑Web build；這次是文件改動，驗證重點為資產與既有契約一致性。
- 未push／merge／上傳Drive；ZIP無credentials、DBdump、影片或原應用程式碼。
- 文件工具的hash/常見secret-pattern检查不是通用個資認證；真實部署資料／真模型輸出另需審核。

交付ZIP的SHA256由打包命令輸出，另附於ZIP旁；不寫入包內以避免自我引用hash。修改本紀錄後必須重建manifest/ZIP並再驗證。
