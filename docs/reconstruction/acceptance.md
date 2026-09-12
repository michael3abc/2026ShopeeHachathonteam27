# 驗收：規格包與重建系統分開

## 本次規格包

1. baseline程式／依賴／fixture drift，schema確定性生成。
2. Markdown離線連結不出包；schema refs可解；fixture index指定schema與JSON pointer。
3. 既有semantic validators驗證 [cross-object fixtures](examples/semantic-fixtures.json)，覆蓋兩人審入口及schema以外限制。
4. manifest精確檔案集合與hash，ZIP解壓fresh temp後不import原repo也可驗證；禁應用code/secrets。
5. 模組/section/rule、任務DAG、七模型task/prompts、registry/gate、A/B/C必需images全部存在。

只證明文件／資產完整性與baseline語意相容，不等於另建系統已成功。無法機械證明文字對任意工程師都充分。

## 重建後 deterministic conformance

fake model依task/schema輸出；固定Clock/IDfactory；Provider可設barrier/failure；embedding用同維合成向量。不呼叫真LLM。基底為semantic-fixtures的context/snapshot/policy/assessment/draft/handoff/review及兩dossier；每個負例deep-copy再改，避免污染其他case。

| ID／rule | Arrange／操作 | 必須assert |
| --- | --- | --- |
| C01 / M01-R03,R04 | 全supported、refund LI-002 | evidence足以退款、scopeLI-002、amount1200、reviewAPPROVE |
| C02 / M01-R04 | 移除／重複pair，或只有UNSUPPORTED | 前兩者reject；後者INSUFFICIENT而非DECLINE |
| C03 / M01-R04 | 每item一requiredclaim CONTRADICTED，proposalDECLINE | scope[]、amount0、無return_decision、review可APPROVE、apply0次 |
| C04 / M01-R05 | unknownartifact、request漏pair／索取system-only | failclosed／reject，非optional Memory失敗 |
| C05 / M01-R06 | amount1201、unknownitem、wrongcurrency、REQUIREDpolicy免退 | 每項拒絕，不能靠LLMrationale放行 |
| C06 / M01-R08 | earlyproposal改case/policy/snapshot/registry/round，刪/倒序event、錯before/ref/review | schema可能有效但semanticreject |
| C07 / M02-R01,R05 | INTAKE INCOMPLETE→clarificationresume→COMPLETE，重啟checkpoint | 正確interrupt；第3次仍不完整超limit2；wrongkind/duplicate turn拒絕 |
| C08 / M02-R01,R02 | ASSESS insufficient→evidence；REVISE要求補件後resume | resolve→重摘要→重查；reviewfeedback保留；第3次需補件超limit2 |
| C09 / M02-R01,R04 | reviewer連續4次REVISE，每次不同有效draft | rounds0..3、三event；第4次human；verification-only不加reviewround |
| C10 / M04-R04 | TWD4999.99/5000/5000.01、SGD199.99/200/200.01 | below/equalPASS、aboveHUMAN_REQUIRED，Decimal |
| C11 / M04-R04 | USD1退款、DECLINE、REVISE | USD人工未配置；DECLINE NOT_APPLICABLE；REVISE無gate／額外budget |
| C12 / M04-R05 | 高額偽造REVIEWER_APPROVE、改configversion/hash/threshold | executeREJECTED、apply0次 |
| C13 / M01-R09,R10 | 兩dossier提交；humanEDIT原scope改return；超scope/假handoff/result | 兩入口可裁決，Policy約束不變；偽造拒絕；resume不再Reviewer |
| C14 / M02-R06 | verificationFAIL三次/UNAVAILABLE、model malformed、ResolverCONFLICT、PolicyAMBIGUOUS/NOT_FOUND | 對應escalation；terminate非humaninterrupt |
| C15 / M03-R02,R03 | create commit前fail、outboxpublish後markfail、messages雙送 | 無orphan；重送一logicalcommand；第二resume409 |
| C16 / M03-R05,R06 | 同event重送、同ID改body、index亂序、poison | dedup、collision、順序保護、persistreject後ACK |
| C17 / M06-R12 | case/activity交錯、limit2多頁、header/query不同 | 獨立cursor、header優先、去重、has_more；userturn序號洞非遺失 |
| C18 / M07-R01,R09 | humanawaiting刷新、結案刷新、斷線重連 | dossier/latestmemory/final重建；非完整usertranscript |
| C19 / M04-R07,R08 | 兩case同order/item並發、不同executionref | 唯一owner、另一REFUND_ITEM_RESERVED；多item失敗atomicrollback |
| C20 / M04-R08 | apply已成功但response/DBfail，same request重送 | 同idempotencykey；一次APPLIED；unknownowner不釋放 |
| C21 / M04-R09 | applyREJECTED、throwtransport、fakehuman | 非SUCCEEDED；unknown保留IN_PROGRESS，不發明公開FAILED |
| C22 / M05-R05 | 相同vector但Candidate/Retired/wrongscope/version/registry | 全不命中；空scopewildcard；claim/category交集非subset |
| C23 / M05-R07 | query=e1、record e1(conf.2)/e2(conf.9)，四筆同分 | 語意優先；tieconfidence/time desc/id asc；Top3到UI保序 |
| C24 / M05-R04,R06 | querybarrier時退休matchingmemory；初次/補件查 | embed後退休不可見；各新summary，無matching不callqueryembed |
| C25 / M05-R06,R08 | wrongmodel/missingvector/stalehash、candidateembedfail | UNAVAILABLE不confidencefallback；無DB半筆 |
| C26 / M05-R08 | candidate同ID同payload重送/並行及異payload | 一row/ref；已存在不embed；異payloadconflict |
| C27 / M05-R09,R10 | distill→query→approve→query→retire→query | 空／命中／空，有治理event；超來源scope拒絕 |
| C28 / M05-R11 | dryrun、第二row回填fail再續跑；Policyreembedfail | dryrun無寫；不重做成功row，保id/status/source/hash；Policy全rollback |
| C29 / M07-R04 | hits3→補件[]/UNAVAILABLE→refresh | 清舊卡、重建query/status；scores/confidence分開 |
| C30 / M06-R06 | fakeprovider/model barrier阻塞，API/SSE持續讀 | 放開前已有STARTED；返回後COMPLETED/duration/summary |
| C31 / M06-R06,R08 | 同node兩attempt、兩case、interrupt-resume | operation/attempt可分、case隔離、PAUSED非COMPLETED |
| C32 / M06-R08,R09 | 捕捉narration input、late、timeout/invalid/虛構nextstep | 僅node/facts、≤2句；失敗不模板、不影響refund；source關聯 |
| C33 / M06-R10 | demo model=None、job重送三次 | generate0、model事件0；UNAVAILABLE/disabledcode/textnull；cache/ACK |
| C34 / M06-R08,R11 | duplicate summary、outboxpublish後crash、fake sourcecase/attempt | 一source一outbox/result；重送無二次成功解說；錯關聯reject |
| C35 / SYS-R07,M06-R07 | 注入URL/email/bearer/phone/rawobject | Activity Redis/DB/SSE無原值；allowlist/拒絕；無hiddenCoT |
| C36 / M06-R05,R11,R12 | terminal後Memory完成/SKIP/retry/fail/late narration；queue滿 | stream仍開；case不回running；failed可觀察、不改業務判斷 |

各C需真正執行，不是確認文檔行數。testdriver由T05/T10實作；本包提供合法基底及輸出schema，未提供另一套完整graph測試runtime。

## 真模型A/B/C與輸出

操作見 [M08](M08-deployment.md)。每run保存run.json：baseline_spec、package_manifest_hash、model/profile、embedding_model/dimensions、gate_version/hash、started_at/finished_at、每段status(PASS/FAIL/SKIP)、actual_case_ref/candidate_id、reason、elapsed_ms。每case保存request/response、case.json、events.sse、全部activities分頁、refundrecord、Memory首次/補件摘要/順序/scores、Candidate/approval證據。

不得存Bearer/key；真個資去識別化。成功條件是路徑與持久化證據，不是固定句子/分數/耗時。預填耳機Memory讓C命中、B蒸餾SKIP卻手動造candidate、ReviewerAPPROVE但refund未APPLIED均不通過。
