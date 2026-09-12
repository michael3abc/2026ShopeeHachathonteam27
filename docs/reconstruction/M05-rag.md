# M05：Policy／Memory RAG

## 責任與非責任

API 擁有 embedding、Policy ingest/reembed、Memory atomic vector storage、query、governance/backfill。Agent Service 擁有 LLM query summary/distiller。Memory 僅存蒸餾經驗，不建歷史案件搜尋。無 reranker、未校準 similarity threshold、confidence-only fallback。

## 依賴

M01/M03/M04/M06；PostgreSQL pgvector；相同 `text-embedding-3-large`、1536 維。重建者提供相容 embedding endpoint，請求須明訂 dimensions=1536，不依 default dimensions。vector 必須 finite、長度正確、非零。

## 輸入輸出

Policy fixture 是 documents→clauses；scope、effective time、required claims、allowed actions、return policy、text 全部保留。MemoryCandidate 有 retrieval_summary、trigger_conditions、recommended_behavior、rationale、sources、versions、scope、confidence、CANDIDATE；ApprovedMemory 是檢索 projection，不包含完整來源 rationale。query 產生 MemorySearchHit(memory,similarity)，observation 是 OK（可 hits=[]）或 UNAVAILABLE(error_code)。

## 資料與演算法

- **M05-R01**：Policy 一 clause 一 vector，family/version 和 source/version 唯一。同版本 checksum 變更拒絕；active 可調整。`--reembed` 僅換 vector/model，保留文字／版本與歷史 retrieval bundles；同 transaction 全成或全失敗。
- **M05-R02**：先篩 active、case_opened_at 在 effective 範圍（兩端包含；to=null 無截止）、market/reason/category（空清單 wildcard，category 有交集）。沒有 clauses → NOT_FOUND；同 family 多個 active version、REQUIRED 與 NOT_REQUIRED 衝突、allowed_actions 交集空 → AMBIGUOUS。不能用 cosine 排名掩蓋相衝 Policy。
- **M05-R03**：Policy query 由程式構造 `Return policy for market {market}; reason {reason}; categories {sorted comma categories}.`；無 category 使用 ALL_CATEGORIES。cosine 距離排序＋clause_id tie break，回**全部**符合 clauses，非 Memory 的 Top3。保存精確 PolicyBundle 與 request hash；execution 依 bundle_version 取回，不重新選政策。
- **M05-R04**：首次解析附件後、每次補件後，各重新呼叫 query summary LLM。只輸入主張、原品項 title/category、market、opened/delivered time、evidence subject/type/source/summary。禁止 old Memory、資格結論、臆測 missing evidence、個資／URL。模型不得改 hard filter。
- **M05-R05**：Memory 先篩 APPROVED、market、policy_version ∈ 當前版本，再 reason（空 wildcard）、claim scope 與 required claims 有交集、category scope 與 claimed categories 有交集（空 wildcard）、registry major 相同。不是必須完整 subset 匹配；精確定義以此為準。Candidate／Retired 永不命中。
- **M05-R06**：符合記錄須有 summary/version/hash、1536 vector、embedding_model 同當前；任一不完整不能冒充正常結果。沒有 eligible records 直接 []，不需呼叫 query embedding。有資料才 embed query；I/O 後再次確認 APPROVED，排除並行退休。
- **M05-R07**：SQL `<=>` 精確 cosine distance asc、confidence desc、approved_at desc、memory_id asc，取最多 3；similarity=clamp(1-distance,-1,1)。graph 再查 scope/去重並保留順位，不重新按 confidence 排序。每次以新 observation 取代舊 hits。
- **M05-R08**：submit candidate 先合法性/hash 查重，外部 embedding 在 insert transaction 外，成功後 transaction 二次查重並一次存 summary+vector+metadata。相同 memory_id/content 回原 submission_ref，不重新 embed；異 hash conflict。並發競爭 unique constraint 後取既有判定；embedding 失敗不得 committed 半筆。
- **M05-R09**：distiller 只接受有 correction source 的完成 trace；輸出 CREATE_CANDIDATE 或 SKIP。Python 覆寫 memory ID、來源案件／revision refs、Policy/registry、market/status；限制 reason/claim/category 範圍不能超來源。多 Policy version、未知 registry 可 SKIP，不冒充產生經驗。
- **M05-R10**：governance 是 trusted service method，CANDIDATE→APPROVED→RETIRED，保存 event／approved_at／retired_at。沒有 public approval endpoint/UI。本版檢索為 runtime 補充建議，永不取代 Policy。
- **M05-R11**：舊資料 summary 由原 trigger_conditions＋recommended_behavior 一次組成，不重新讓 LLM 改寫。dry-run 列待回填；只處理 missing/stale vectors；成功逐筆完成可續跑、錯誤顯式報告，保留 Memory ID/hash、status、source、approval history。維護時先排空舊工作、備份；API/Agent/Web 配置一致、兩種 VDB 完成同模型後恢復。

## 正常／失敗流程

Policy unavailable 為安全依賴，終止自動化；Memory summary／embedding／VDB unavailable → clear hits＋UNAVAILABLE＋案件繼續。artifact resolve 失敗仍 fail closed。B 的真實 candidate 核准前 query 空、核准後 C 可見；不得預填耳機 Memory 替代 B 學習。

## 驗收條件

C22～C29：同 scope 較相關但低 confidence 排前；tie 精確、Top3 到 UI 不變；empty/unavailable 清卡；模型不符、retired、版本/market/reason/category/claim 不合永不正常命中；atomic insert/replay/backfill續跑；A/B/C 真模型依 [部署](M08-deployment.md)。
