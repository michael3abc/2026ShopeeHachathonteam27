# A／B／C Runtime E2E 操作

本操作使用按 `order_ref` 選取 snapshot 的 fixture provider，在同一隔離
DB／Redis／API 中依序執行三案退款測試。完整 B → C 學習仍須以實際產生、人工核准並由
C 命中的 Memory ID 為準；不能因退款測試通過就宣稱學習流程通過。

## 1. 準備與注入

先完成 [README 環境設定](README.md#3-環境與啟動)：隔離 Compose project、ports、
DB／Redis、模型與 secret 設定。執行 Alembic `upgrade head`，需包含
`0013_activity_tracing`（case_activities、activity_narration_outbox）。
先核對 assets manifest 與所有 Evidence summary；啟動 integrated-demo 會實際寫入資料並呼叫 embedding。

從 repo root 執行以下準備命令，只產生檔案、不寫 DB。輸出目錄必須尚不存在；重跑請換新目錄。

```bash
uv run --package return-agent-api python data/demo-case-study/prepare_runtime.py --case all --output /tmp/refund-demo-all
export DEMO_FIXTURE_DIR=/tmp/refund-demo-all
docker compose -f docker-compose.yml -f data/demo-case-study/compose.demo.yaml config --quiet
docker compose -f docker-compose.yml -f data/demo-case-study/compose.demo.yaml up -d --build api agent-service
```

四個 loader 固定檔名由準備程式產生；case-context fixture 內含三筆以 `order_ref` keyed 的
snapshot。API bootstrap 載入 Policy、12 筆 Evidence metadata，
提交並自動核准指定的 speaker-only 合成 preload；這是此整合 profile 的既有行為。
操作者必須在啟動前同意該 preload，無需另外執行 README 的手動 preload submission／approval。
B／C 仍使用同一 preload ID，bootstrap 不改既有治理狀態，也不預載耳機 Memory。
Case／order 不直接寫入 DB；使用各案原始 `create_case_request` 經公開 API 建案。
Gate 設定沿用根目錄共用 JSON；準備目錄不包含金額規則。

以 README 的只讀 Memory query 核對 preload scope、可見性與 B 無匹配耳機記憶。
啟動健康並不保證 fixture 正確，錄下本次選用目錄、order_ref、金額及案例回傳 ID。

## 2. 依序執行三案

依 README 第 6 節建案、觀察補件、送出對應 followup，B／C 的 review request
必須綁定各自最新 pending handoff_id。案件不符合預期時保留紀錄並停止。

| 案例 | 預期核對 | 完成條件 |
| --- | --- | --- |
| A | 1200 TWD、音箱、speaker preload 命中；補件後 Reviewer APPROVE、gate PASS | refund SUCCEEDED 且 case RESOLVED |
| B | 6200 TWD、耳機、Memory 無匹配；LLM APPROVE 後 HIGH_VALUE_ITEM，人工依實況 EDIT 退回要求 | refund SUCCEEDED、case RESOLVED，且 correction trace 進入 Memory worker |
| C | 6800 TWD、獨立耳機素材；命中已核准的 B Memory 後仍需高額人工授權 | refund SUCCEEDED 且 case RESOLVED；`human_review.memories_used` 保留 B 的實際 Memory ID |

每案完成後再建立下一案，避免錄影時交錯 activity。Provider 會從同一 fixture 精確選取
snapshot；未知 `order_ref` 必須失敗，不能套用其他案例模板。
等待相關 Memory job 終態並記錄結果；若沒有 job，依第 4 節判斷，不能以 sleep 推定完成。
保留同一 COMPOSE_PROJECT_NAME、DB 與 Redis，不刪除歷史資料。

## 3. Activity 與結果查核

```bash
curl --fail -sS "$DEMO_API_URL/cases/$DEMO_CASE_REF/activities?after_seq=0&limit=100"
curl --fail -N "$DEMO_API_URL/cases/$DEMO_CASE_REF/activities/stream?after_seq=0"
```

分頁依回傳 cursor 與 has_more 繼續讀取；SSE 可在 case terminal 後保持連線，
追蹤晚到的 narration／Memory 活動。原 `/events` 用於 case 狀態、gate 與 memory_retrieval；
新的 `/activities` 用於 provider、node summary 與背景工作，不以文字解說替代退款 DB audit。
Narration UNAVAILABLE 不代表退款失敗；trace 可能缺失，仍以持久化退款與 Memory 紀錄查核。
Web 已透過 Activity API 與 SSE 顯示案件 graph、node summary、model／tool lifecycle；
原始事件、背景 Memory 與退款 audit 的驗收仍以上述 API 與持久化紀錄為準，不能只憑動畫判定成功。

## 4. 測試結果分類

- 三案退款：逐案記錄 case_ref、handoff_id、gate、human decision、refund execution_ref 與終態。
- Memory 學習：B 的範例是實際 `EDIT`，將已通過 Reviewer 的退回要求改為免退，形成可蒸餾的
  correction trace；Distiller 仍可回傳 SKIP。此時記錄學習子測試 BLOCKED／SKIP，可繼續 C 的
  獨立高額退款測試，但不得宣稱它檢索 B 經驗。
- 只有實際產生 B candidate、核對 source_case_refs／scope 並經 governance approval，才驗證 C 命中該 ID。
  C 到達人工審核後，`GET /cases/{case_ref}` 的 `human_review.memories_used` 必須保留該 ID，
  且結案後重新讀取仍一致；不以預填 candidate 製造成功。

## 5. 人工尚需完成的素材

12 張圖片已在 `images/`，實際路徑見 assets manifest。人工需逐張確認商品身份、
損壞位置、拆箱連續性與 Evidence summary 相符，並确认清楚標示 DEMO／AI-GENERATED。
圖片存在不表示 artifact 已可下載。metadata-only E2E 使用核對後的人工 extracted_summary，
現有 Evidence loader 不處理 image bytes；若要 UI 開圖，仍需素材服務／前端接入。
可先用本機圖片檢視器呈現素材，但不得稱為 runtime 即時影像辨識。
三段 unboxing.mp4 為選配，不阻擋 metadata-only 測試；若另行提供，須為對應商品獨立素材。
