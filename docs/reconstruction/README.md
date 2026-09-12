# 退貨案件 Agent：完整重建規格包

固定基準：`485048cc73dc5c8f64d08034f49e318827418f80`。本包是繁體中文重建快照，不是原應用程式備份。依本包從空專案實作，目標為功能與 A/B/C Demo 等價，UI 不要求像素相同。

## 閱讀與交付順序

1. [總體規格](00-system.md)：邊界、流程、資料所有權。
2. [M01 Contracts](M01-contracts.md)、[M02 Runtime](M02-runtime.md)、[M03 API／DB](M03-api.md)、[M04 能力／退款](M04-capabilities.md)。
3. [M05 RAG](M05-rag.md)、[M06 非同步服務](M06-service.md)、[M07 Web](M07-web.md)、[M08 部署與 Demo](M08-deployment.md)。
4. [完整介面](interfaces.md)、[資料字典與交易](data.md)、[模型輸入與 prompt](model-tasks.md)。
5. [重建任務](implementation-plan.md)、[驗收案例](acceptance.md)、[本次驗證](verification.md)、[現況限制與矛盾](limitations.md)、[來源對照](traceability.md)。
6. [資產索引](assets/contract-catalog.json)、[檔案雜湊](manifest.json)。所有 JSON Schema、prompt、registry、設定、合成圖片均在本包；來源路徑只供稽核。

規範中的 `Mxx-Rnn` 為穩定行為 ID，`Txx` 為重建任務，`Cxx` 為驗收案例。生成型資產不可手改，須從相同 baseline 重新匯出；規格文字與實作矛盾時先看 limitations，不自行擴增業務需求。

## 離線使用

解壓後在本目錄執行：

```sh
python3 tools/verify_package.py
```

標準函式庫即可核對雜湊、檔案集合、相對連結、schema refs、模組及任務 DAG。完整 fixture JSON Schema 驗證另外需要 `jsonschema`（版本見 dependencies）：

```sh
python3 tools/verify_package.py --schemas
```

工具不連網、不匯入原專案、不接 DB、不讀環境 secret。Python/Node、套件 wheel/npm cache、PostgreSQL/Docker 映像並未打包；「離線交付」指文件／素材／驗收定義自包含，不宣稱離線安裝所有依賴或離線使用真實 LLM。

本次僅驗證規格包與既有語意相容，**沒有另寫一套系統證明重建成功**。真實 LLM 需自行提供相容 endpoint、模型名稱與 credentials；不得依賴原作者的主機、gateway 或路徑。
