# Policy v2：原專案增補規格

狀態：**待實作，不是目前 runtime 行為，也不是可直接 ingest 的 v1 fixture。**

目標為 `ShopeeHackthon2026`；以現有 Agent 規格及 `485048c` 重建快照為對照，吸收獨立 Demo 的四類政策設計，不移植其程式碼或簡化架構。本次僅交付規格，未新增生效 Policy、DTO、migration 或服務設定。

## 1. 範圍與不變條件

- **PV2-S01**：新增自有合成政策包 `DEMO-TW-RETURNS:v2.0`，不宣稱為蝦皮官方系統、逐字官方政策或完整法律實作。
- **PV2-S02**：新包首版限 TW／TWD、營業賣家／商城、一般實體商品、一個申請品項且數量一。限制只屬這個包；原多品項 DTO、其他市場與既有政策仍保留，不把整個系統限縮。
- **PV2-S03**：跨境、特殊商品例外爭議、套組、部分數量、折扣重算、功能異常、描述不符、換貨維修與保固交專責售後；不推論所有退款權利消失。
- **PV2-S04**：保留原自由文字 Intake、澄清／補件、graph playback、node inspector、narration 顯示、雙 SSE、API／Agent 分 DB、durable journal／lease 與 Memory draft cache。不引入新 Demo 的按鈕取代 Intake、隱藏 narration、單 DB／單 worker 降規。
- **PV2-S05**：Reviewer 只有 APPROVE／REVISE，三次修正為 round 0～3。核准後才執行原共享 Python／Decimal 金額 gate，門檻及版本不因新 Policy 改變；兩種人審入口與人工裁決後不回 Reviewer 均保留。
- **PV2-S06**：amount/currency 仍由可信 snapshot 與原 scope 推導。Policy 資格、Reviewer verdict、退回要求、金額授權、付款結果分開；人、模型、Memory 與瀏覽器都不能擴大 scope 或創造付款授權。

## 2. 新增與補強的四類政策

| ID／path | 相對原版 | 適用情境 | 預設處理 |
| --- | --- | --- | --- |
| P01 `COOLING_OFF` | 新增 | 商品沒壞，只是改變心意，仍在適用期限 | 退回驗收後退款 |
| P02 `DAMAGED_ON_ARRIVAL` | 補強原損壞政策 | 商品在到貨時即有實體損壞 | 不足補件；預設退回，有依據才免退 |
| P03 `WRONG_ITEM` | 新增正式條文 | 實收 SKU／規格與成交約定不符 | 核對可信訂單，退回驗收後退款 |
| P04 `UNDELIVERED_ITEM` | 新增正式條文 | 訂購的一個獨立品項確認未交付 | 不要求退回，仍經授權後退款 |

原版 reason enum 已有 CHANGED_MIND、WRONG_ITEM、MISSING_ITEM，registry 也有部分相關 claims；**有 enum 不等於有可執行政策**。不能只加四段文字，便宣稱原音訊損壞 Demo 已支援全部流程。

### P01：一般猶豫期

**PV2-P01**：可信交易符合範圍、已收受相關商品、首次有效申請不晚於 Provider 截止時間，且無已成立特殊例外或待釐清爭議，才成立。不要要求 ITEM_PHYSICALLY_DAMAGED、DAMAGE_PRESENT_ON_ARRIVAL、ITEM_UNUSED 或外箱封條完整。必要拆封不直接失格；超出必要檢查的損耗爭議交專責，不自動扣費。

使用 `return_policy=REQUIRED`、新增 required reason `POLICY_RETURN_REQUIRED`、release condition `RETURN_INSPECTION_PASSED`。說明「可依一般退貨途徑處理」不表示損壞主張已被證實。

### P02：到貨實體損壞

**PV2-P02**：ITEM_PHYSICALLY_DAMAGED 與 DAMAGE_PRESENT_ON_ARRIVAL 分開判斷。特寫支持目前損壞，不自動證明到貨時點。使用本路徑的可信受理期限，不套寫死七天的通用公式。UNSUPPORTED 是未建立事實，不是反證；不足則具體補件，P01 可行時提供經買家確認的替代途徑。

保留 `return_policy=MODEL_JUDGMENT`；預設退回，免退須引用可信處置 facts 或案件證據，經 Verification、Reviewer、gate／必要人審。Memory 建議不是免退授權；損壞證據足夠也不單獨等於免退。不加低額必免退或高額必拒絕的新規則。超出本包期限的瑕疵主張交專責，不宣告全部救濟消失。

### P03：寄錯商品

**PV2-P03**：WRONG_ITEM_RECEIVED findings 比較不可變成交 SKU／規格與實收證據；不得用目前商品頁或買家任填 SKU 代替成交訂單。實收不可辨識可補件；可信成交資料缺失交 Provider 修復／專責，不叫買家證明後端缺失。

使用 REQUIRED、POLICY_RETURN_REQUIRED、RETURN_INSPECTION_PASSED；退回錯寄實物，但綁原申請 line item／authorization，不新增退款 scope。功能不佳、描述落差不硬套寄錯。

### P04：獨立品項未交付

**PV2-P04**：由可信逐品項配送／調查結果確認未交付，排除仍在配送中的分批貨件、取消、已退款與其他 reservation。查不到簽收不等於確認未交付。新增 system-fact claim `ITEM_CONFIRMED_UNDELIVERED`；原 ITEM_NOT_IN_SHIPMENT 描述包裹缺件，不能暗改成同義詞。

不要求拍攝不存在的商品。使用 NOT_REQUIRED、新增 waived reason ITEM_NOT_RECEIVED、AUTHORIZED_NO_RETURN；仍須獨立審核及高額授權。缺配件、套組缺一部分轉專責，不把缺零件自動當整件全額退款。

## 3. 官方依據與 Demo 設計分離

2026-09-12 查核以下官方資料；不搬運整頁條款，本節不是法律意見。

| 來源 | 可支持的政策背景 | 不可推導的結論 |
| --- | --- | --- |
| [S01 蝦皮期限與逾期協商說明](https://help.shopee.tw/portal/4/article/79715?seo=1) | 列商城十五天、其他類型七天，另有適用排除 | 不是每種交易／商品都適用；逾期不等於無任何權利 |
| [S02 蝦皮退款與退貨政策](https://help.shopee.tw/portal/4/article/77275) | 包含未收到、受損、寄錯與猶豫期事由；有退回驗收及特定免退處理 | 本文件的 evaluator、gate、狀態機不是官方演算法 |
| [S03 消保會必要檢查與拆封說明](https://cpc.ey.gov.tw/Page/BC16ACF0BBB9CCC2/2055825e-e262-47da-9f56-398a71c92c5b) | 必要檢查的拆封／變更不當然消滅解除權 | 不等於任意使用或損壞都可無條件退回 |
| [S04 行政院通訊交易解除權合理例外](https://www.ey.gov.tw/Page/4FF303AE95592945/80289438-3b0c-456b-a79d-1f93cbbc6aa4) | 須依商品／服務情形與告知等要件判斷 | 分類標籤或模型衛生疑慮不能當已成立法定例外 |

**PV2-SRC01**：每條 rule 保存 basis[]（LEGAL_REFERENCE／PLATFORM_REFERENCE／DEMO_OPERATIONAL）、sources[]、checked_at、source_effective_from/to、source_version、source_content_hash、interpretation_hash。未知來源版本／生效日用 null，不拿查核日期替代；未存原始內容不得宣稱有網頁 checksum。本地規則雜湊與來源雜湊分開，Demo 自己的 effective_from/to 也與來源日期分開。

**PV2-SRC02**：Demo 不模擬完整賣家爭議、逾期未回覆自動撥款或法律例外引擎。退回逾期／驗收爭議轉專責、不自動失權，是安全範圍限制，不宣稱複製官方所有處理。

## 4. Contracts 最小必要增補

以下為待落地的 v2 欄位，不是目前 schema。實作時在 apps/contracts 一次更新 Python、Provider adapters、JSON Schema、TypeScript 與跨物件 validators；不只修改 prompt、不手改生成 schema。

### 4.1 可信訂單與時間

| 物件／欄位 | 契約與資料來源 |
| --- | --- |
| CaseContext.first_valid_submitted_at | API 保存首次可綁訂單／原申請 scope 的有效申請時間；不能因 LLM 延遲、補件或人審改晚；保留原接收紀錄及選用依據 |
| OrderSnapshot.platform／seller_type | Provider；本包接受 SHOPEE_TW 與 BUSINESS／MALL，unknown 不自動通過 |
| transaction_version／purchased_spec | 不可變成交版本、SKU、約定規格，不是目前商品頁 |
| line_items[].delivery | shipment refs、逐品項狀態、收受時間、分批與調查結果 refs；unknown／in transit 不代表確認未交付 |
| line_items[].returnable_quantity | Provider；本包只接受原 quantity=1 且可退一件，不按數量猜金額 |
| line_items[].exception | NONE_CONFIRMED／ESTABLISHED／UNKNOWN／DISPUTED，分類及依據 refs；只有明確無例外走一般途徑，其餘交專責 |
| line_items[].deadlines[] | policy_path_id、deadline_at、timezone、rule_source_ref/version；猶豫期與其他路徑的受理期限分開 |

- **PV2-T01**：保持原 UTC wire datetime，時間傳 Z；另外 timezone=Asia/Taipei 描述期限來源。比較 first_valid_submitted_at <= deadline_at，等於仍受理。日曆／假日計算由可信 Provider 給定，不另建法律日期引擎。
- **PV2-T02**：期限／例外／scope 缺失須 typed unknown／error，交資料修復或專責，不讓 LLM 補值。P04 沒有 delivered_at 時不能套猶豫期公式；要有該路徑自己的受理依據。

### 4.2 路徑化 PolicyBundle

**PV2-C01**：保留 bundle 身分與歷史版本；新增 v2 discriminator、paths[]、common_constraints[]。每個 path 至少有 path_id、policy_version、clause_refs、可信 scope、入口 reasons、effective time、required_claim_ids、固定 system_predicates、allowed_actions、return_policy、release conditions、來源與解讀 hash。四條為具名固定邏輯，不新增任意條件 DSL。

| path | claims | 額外 deterministic 條件 |
| --- | --- | --- |
| P01 | 空集合；空集合本身不得核准 | 適用交易、收受、期限、例外、scope；同意另在授權階段檢查 |
| P02 | ITEM_PHYSICALLY_DAMAGED、DAMAGE_PRESENT_ON_ARRIVAL | 本路徑期限、scope／可退額、退回授權 |
| P03 | WRONG_ITEM_RECEIVED | 完整成交規格、本路徑期限、scope |
| P04 | ITEM_CONFIRMED_UNDELIVERED，SYSTEM_FACTS-only | 排除分批待送、取消、既付／reservation，受理範圍 |

**PV2-C02**：v1 的全部 clauses 聯集 claims／交集 actions／退回衝突檢查只保留在 v1。v2 在單一 path 內組合必要條件，跨 path 是 alternatives。P01 REQUIRED 與 P04 NOT_REQUIRED 不互斥；同一路徑內真正衝突、缺版本或 scope 不明仍 AMBIGUOUS／fail closed。替代 P01 不因原 reason=ITEM_DAMAGED 被 retrieval 排除。

**PV2-C03**：新包採明確的新 registry major 隔離，保留原 IDs 語意；不暗改 ORDER claim 成 LINE_ITEM。新增 ITEM_CONFIRMED_UNDELIVERED 為 LINE_ITEM／SYSTEM_FACTS-only，必須可信 source refs，不能進 EvidenceRequest。不增加影像證據種類，不宣稱 metadata adapter 已可辨識圖片。

**PV2-C05**：system_predicates 是下列固定 enum，不是可執行字串。各結果為 PASS／FAIL／UNKNOWN，附可信 source ref：

| predicate | 資料／算法與適用路徑 |
| --- | --- |
| TRANSACTION_IN_SCOPE | platform／market／currency／seller／商品類型符合 §1，全部 paths；不符或未知轉專責 |
| SINGLE_REFUNDABLE_ITEM | 原申請一品項且 quantity=1、returnable_quantity=1、非套組，全部 paths |
| NO_EXCEPTION_ESTABLISHED | exception=NONE_CONFIRMED；其餘專責，不由模型自行判例外 |
| WITHIN_PATH_WINDOW | 以可信 path deadline 與首次有效申請時間比較；P01 過期只是不適用 P01，P02～P04 逾期轉專責 |
| RECEIPT_CONFIRMED | P01 要有相關商品收受依據；不得借別品項 delivered_at 代入 |
| PURCHASE_SPEC_AVAILABLE | P03 成交 SKU／約定規格完整，不用現行 listing |
| NONDELIVERY_CONFIRMED | P04 可信調查確認，不能從缺簽收推論 |
| NO_PENDING_SPLIT_DELIVERY | P04 沒有尚待配送的相關分批貨件 |
| PAYMENT_SCOPE_AVAILABLE | 全部 paths；未取消、未退款、無他案 reservation，最新可退額足夠；本案自己的 reservation 不誤判成他案衝突 |

同意／gate／驗收不放進 eligibility predicates，它們是授權或履約條件；尚未驗收不應把政策資格改成 INELIGIBLE。

### 4.3 PolicyEvaluation 與確認

**PV2-E01**：PolicyEvaluation 是程式根據可信 facts 與經驗證 findings 算出的結果，不是 LLM verdict。

| 必要欄位 | 語意 |
| --- | --- |
| evaluation_ref／version／hash | 程式產生的不可變識別、evaluator 版本與內容 hash |
| case_ref／order_snapshot_ref／policy_bundle_version／claim_registry_version | 精確案件／版本綁定，不只比對 family |
| evidence_bundle_hash／findings_ref | 哪次 evidence、哪組 Assessment／Reviewer／Human findings |
| item_evaluations[] | line_item_id、path_id、status、clause／system fact／claim refs、reason codes |
| status | 每路徑 ELIGIBLE／INELIGIBLE／NEEDS_INFORMATION／SPECIALIST_REQUIRED |
| selection | selected_path_id、selection_version、原 requested_action、必要 confirmation_ref |
| evaluated_at | UTC，不是新的首次申請時間 |

- **PV2-E02**：ELIGIBLE 只表示資格成立，不能授權付款。INELIGIBLE 只限該 path，不是整案 DECLINE。可向買家補的資料才 NEEDS_INFORMATION；可信資料缺失或範圍外交專責，不能無限索證。
- **PV2-E03**：P02 不足而 P01 可行時，graph 發出 typed 路徑確認，列原主張、替代 path、scope、退回要求；買家接受並持久化後才切換。拒絕／未回覆不付款、不編造同意；仍可依 budget 補原主張，否則專責。
- **PV2-E04**：希望免退但核准須退回，即使沒換 path 也要確認。確認綁 case_ref、original_scope_hash、path_id、selection_version、return_requirement_hash；同內容冪等，異內容／過期 409。不重設申請時間、revision budget 或舊異議。
- **PV2-E05**：Assessment 與 Reviewer 各依自己的 findings 產生 evaluation；Reviewer 看完整 bundle、可信 facts 與 selection／consent，不讀 Assessment 結論或 Memory。Human EDIT 由 API 依人工 findings／處置重算，舊紀錄不可覆寫。
- **PV2-E06**：proposal 引用當輪 evaluation hash。Dossier 每筆驗證 binding、連續 round、revision chain；補件後 hash 可以不同，不強制歷輪用最新 hash。切換 path 必有合法 confirmation lineage，不能清掉異議換取新的修正 budget。
- **PV2-E07**：先套範圍／衝突／可信資料完整性，再依各路徑期限與 claims 計算；所需 claims 全 SUPPORTED 且 system predicates 全 PASS 才 ELIGIBLE。claim 有 CONTRADICTED 可判該 path INELIGIBLE；沒有反證但有 USER_EVIDENCE 可補的 UNSUPPORTED 才 NEEDS_INFORMATION。P01 claims 為空仍要所有 predicates PASS。
- **PV2-E08**：取證只針對目前選取路徑，其他路徑可列為選項，不能因為 P01 不需要的 P02 claim 不足而阻塞 P01。相同 claim／subject 共用可信依據可去重，但每個 path 的成立結果獨立。沒有買家確認不得用替代 path 授權退款。
- **PV2-E09**：v2 自動 DECLINE 仍須滿足原有反證門檻，且不能有未處理的可行替代路徑；僅期限不適用、資料不足、使用者未接受替代或範圍外，停止自動處理／專責，而非硬造 CONTRADICTED。人審 REJECT 保留，但理由限本次請求，不宣告所有法律權利。
- **PV2-E10**：若初次申請已明確同意 RETURN_AND_REFUND，API 可保存原同意紀錄作為對應要求的 confirmation，不必重複點選；不可只採 LLM 推測的同意。核准後退回條件改變則舊同意失效，重新確認。

### 4.4 退回與撥款分開

**PV2-C04**：保留 return_decision.source=POLICY／MODEL_JUDGMENT／HUMAN_REVIEW。擴充 required reason POLICY_RETURN_REQUIRED、waived reason ITEM_NOT_RECEIVED，不能用 ITEM_UNSALVAGEABLE 描述沒收到。

新增 refund_release_condition=RETURN_INSPECTION_PASSED／AUTHORIZED_NO_RETURN，API 依驗證後 return_decision 決定並保存。required=true 只能前者，false 只能後者且有合法免退依據。授權包含 scope、bundle、path、evaluation、dossier、decision 與 gate hashes；缺失或版本不符禁止自動付款。

## 5. 原 Graph 整合

不刪現有 nodes；v2 增補明確節點／typed branch，v1 checkpoint 不直接以 v2 重播。

| 現有位置 | v2 增補與責任 |
| --- | --- |
| parse_request／request_clarification | 保留自由文字、品項對照、requested_action；另以明確偏好或澄清區分是否接受退回，不把所有 REFUND 當拒絕退回 |
| load_case_context | Provider 給可信期限／成交／配送／例外；程式檢查本包範圍 |
| retrieve_policy | 完整包／common constraints／可替代 paths，固定版本，不靠 Top-K 決定能漏哪些限制 |
| prepare_memory_query／retrieve_memory | 保留首次附件先解析、補件後重新摘要；程式產生 path scope，換路徑清舊命中並重查 |
| assess_case | 逐 path 建 expected claim pairs；不合併全部 paths 當共同門檻，system-only finding 必與 facts 一致 |
| 新增 evaluate_policy | Assessment 後 deterministic node，產生逐路徑 evaluation／選項 |
| 新增 confirm_policy_path | 沿用 interrupt／checkpoint，新增 typed resume；接受後重走 Memory／Assessment，保留 budget／異議 |
| propose_decision | FULL_REFUND 只提已選且成立／已確認的 path；DECLINE 須符合 PV2-E09，reason／return requirement 相容 |
| external_verification | 原 binding／金額／scope 檢查加 evaluation／selection／consent；FAIL 沿原 verification budget |
| reviewer／record_revision_event／await_human_review | 保留獨立複核、兩人審入口；顯示 path／依據／退回要求，不製造高額異議 |
| emit_resolution_handoff | 只表示審核完成；API 決定待退回、待驗收或 execute，不宣稱已付款 |
| terminate_automation | 專責移交用明確 reason，仍是 ESCALATED 自動化終點，不冒充可 resume 的人審面板 |

**PV2-G01**：模型 tasks／prompts 同步版本：Intake 保留自然語言；Assessment／Reviewer 用 path-specific findings；Resolver 區分資格與免退；query summary 不預判資格或臆測缺口；Distiller 記 path lineage。不能僅靠改 prompt 實現 deterministic evaluator。

## 6. API 擁有退回履約

這是 API canonical lifecycle 增補，不讓 Agent 等物流。

| 起點／條件 | 下一狀態 | 付款 Provider 呼叫 |
| --- | --- | --- |
| 核准須退回，尚缺買家同意 | AWAITING_RETURN_CONFIRMATION（新增） | 0 |
| 須退回且同意已具備 | AWAITING_RETURN（新增） | 0 |
| 可信退回送達 | AWAITING_RETURN_INSPECTION（新增） | 0 |
| 驗收 PASS，完整授權重驗通過 | 原 EXECUTING | 依原冪等 key 執行 |
| 有效免退授權，重驗通過 | 原 EXECUTING | 依原冪等 key 執行 |
| application APPLIED | 原 RESOLVED，退款成功 | 不另發新付款 |
| 結果未知／transport error | 保留 IN_PROGRESS 與 reservation | 原 key 恢復，不能換 execution |
| 驗收爭議／退回逾期 | ESCALATED，專責售後，明確未付款 | 0 |

- **PV2-F01**：API transaction 保存授權、reservation、case event、projection 與必要 outbox 後才回應。退回途中 reservation 不自動過期讓別案取走；確定取消且未呼叫付款才由受權流程釋放。未知付款不能釋放。
- **PV2-F02**：新增 ReturnFulfillmentEvent，必帶 event_id、producer_id、case_ref、authorization_ref、line_item_id、event_type、occurred_at、payload_hash。RETURN_ARRIVED／INSPECTION_PASSED／INSPECTION_DISPUTED／RETURN_OVERDUE 各有 typed payload；驗收引用已接受的 arrived event。同 producer＋event_id 同內容重送回原 receipt，異內容衝突；錯案、錯授權、錯品項、倒序不可付款。
- **PV2-F03**：付款前重驗持久化授權、原 bundle／scope、最新 refundable balance、reservation、同意、驗收及目前 gate config。設定缺失／變更須顯式暫停或轉人工再授權，不沿用舊放行、不偽裝成 Reviewer REVISE。
- **PV2-F04**：保留原 RefundExecutionRecord 的 SUCCEEDED／REJECTED 與 application APPLIED／REJECTED；不偷塞新 Demo 付款 enums。DECLINE 仍可依原規則結案且不付款；只有 APPLIED 才成功是指 FULL_REFUND 的退款，不把所有 RESOLVED 改定義成退款。
- **PV2-F05**：待退回不是 terminal，case SSE 繼續且 refresh 能還原。審核階段換 path 用 graph resume；核准後確認退回／物流／驗收則只續 API 履約，不重跑 Reviewer。

### 6.1 待實作介面

以下不是既有可用 endpoint。既有 case events／activities 的 cursor／replay 語意不變。

| 介面 | 認證、輸入與語意 |
| --- | --- |
| POST /cases/{case_ref}/policy-confirmations | case owner；confirmation request ref、selection_version、accept、冪等 key；API 同意紀錄＋outbox，202，再 graph resume |
| POST /cases/{case_ref}/return-confirmations | case owner；authorization_ref、要求 hash、accept、冪等 key；202，只續 API 履約，拒絕不付款並交專責 |
| POST /internal/v2/return-events | service 認證與 producer allowlist；typed event，200 receipt，同內容重送回原值；瀏覽器不能呼叫 |
| POST /demo/cases/{case_ref}/return-simulation | 受限 Demo operator；只提交 ARRIVED／PASS／DISPUTE 等意圖，由後端產生可信事件；不接受任意授權／付款結果／producer credential；202 |
| 既有 GET /cases/{case_ref} | 加 evaluation、selection、pending confirmation、fulfillment／payment projection，排除任意內部物件與敏感資料 |

共同錯誤：shape 422、未認證 401／無權限 403、舊版本／錯案 binding／異內容重送／非法順序 409；所有拒絕都不能推進履約或付款。實作時與 shared DTO、API client、tests 同步；API 不 import runtime，不新增匿名通用 payload。

## 7. RAG、Memory、Activity 與 Web

- **PV2-R01**：保留原 Policy ingest、pgvector、完整 clauses 取回與 exact persisted bundle。原 Policy 已不是 Memory 式 Top 3，本次修的是 alternatives 的語意，不是宣稱修復不存在的 Policy Top-K。可信 scope 先取完整規則，向量只排序／輔助引用，同 path 衝突不靠分數決定。
- **PV2-R02**：維持原 embedding model identity 與 1536 維；新 Policy version ingest 新向量，無須為此換模型。reembed 只換向量，不改同版本文字或歷史 bundles。
- **PV2-M01**：保留 Reviewer REVISE 與 Human EDIT／REJECT correction 來源，不採新 Demo 僅 generalizable 人工 EDIT 的限制。保留 Agent DB 首次 draft cache、submission 冪等、APPROVED 治理、cosine Top 3；Reviewer 不讀 Memory。
- **PV2-M02**：v2 FULL_REFUND 可在 graph 結束時封存 correction，但要等 API APPLIED 再釋出蒸餾工作。按 authorization／resolution ref join，不能只看同 case 任意付款；API completion outbox 與 Agent durable enqueue 保證兩事件任意順序／重送只一 logical job，晚到 trace 不遺失。DECLINE 可沿原完成 correction 邏輯蒸餾，但明示未付款。
- **PV2-M03**：Memory scope 納入來源 path／Policy／registry；query filters 由程式產生，v1 Memory 不自動當 v2 核准經驗、不手改版本冒充。換 path／補件重查替換；empty／UNAVAILABLE 清卡，無 confidence-only fallback。
- **PV2-M04**：P01 沒有 required claims，不能沿用舊 claim 交集條件導致永遠零命中，也不能放成所有 Memory 都適用。v2 必須 exact policy／registry／path＋原 market／reason／category 篩選；所選 path claims 非空時再驗 claim scope，P01 以明確 path scope 取代 claim 交集。未選 path 時不混合不同路徑的建議，待選定後重新查詢。
- **PV2-O01**：Activity 加 typed evaluation／confirmation／fulfillment summary，含結果、依據、下一步及是否尚未付款。沿用 CASE／REFUND／MEMORY、operation／attempt、source_event_id 與 allowlist，不能直接 dump 新 DTO。
- **PV2-O02**：保留原 Intake／playback／node inspector／narration，追加政策途徑選擇、待退回／待驗收與明示 Demo 操作。Memory governance UI 可另加，但不是四政策的必要依賴，B/C 可用既有受信任治理方法。

## 8. 舊假設、資料與版本遷移

| 原版假設／文字 | v2 整合要求 |
| --- | --- |
| 損壞 fixture 的無法確認可拒絕，與 validators 禁止 UNSUPPORTED 拒絕矛盾 | P02 新版本明確修訂並有獨立測試；不覆寫 v1，不假借 reembed 改文字 |
| 全部 required claims 聯集、全包 return_policy 衝突 | 明確 v2 discriminator 分流 path-aware evaluator；空 claims 的 all([]) 不能單獨放行 |
| 逾期／未送達由同一 ORDER claim 反證 | 各 path 的期限分開；P04 不因缺 delivered_at 全面拒絕或虛構日期 |
| Agent RESOLVED 後可蒸餾 | v2 退款等待 API APPLIED，保留 correction 來源與 durable cache |
| 審核完成即可 execute | 保存授權及 reservation，履約條件符合才由 API execute |

- **PV2-MIG01**：新 contracts discriminator／Policy 包明確版本化，API／Agent／Web 同步支援後，案件由可信配置 opt-in v2。v1 案件固定原 bundle／evaluator；不做 try-v2-fallback-v1。未知 enum 不能被舊 client 當成功／terminal。
- **PV2-MIG02**：API Alembic 加 immutable evaluations／selections／confirmations、fulfillment authorization／receipts、projection 與去重 constraints；擴充原 reservation／execution ledger，不複製一套。Agent 新增 durable join 使用自己的 migration，不合 DB。
- **PV2-MIG03**：不回填假期限、同意、驗收或 APPLIED。v2 必填只套明確 v2 紀錄；v1 歷史可讀，in-flight 先排空或留原版本完成，不硬 resume 跨版 checkpoint。
- **PV2-MIG04**：隔離 DB 測 upgrade、offline SQL、非空 downgrade 保護、replay；備份與協調切換另行授權。新政策與 embedding model migration 分開；固定 docs/reconstruction、manifest／ZIP 不改。

## 9. 實作任務與驗收

| 任務 | 輸入／落點 | 完成條件 |
| --- | --- | --- |
| T1 Policy／Contracts | 本規格；apps/contracts、Policy fixtures／ingest | 四條來源／版本、期限／scope／path evaluator、registry、consent hash 測試；DTO/schema/TS 一致 |
| T2 Agent | 原 Runtime、prompts、providers | 自由文字、P01 無損壞索證、P02 補件／替代確認、P03／P04、獨立 Reviewer、history／interrupt fake tests |
| T3 API 履約 | 原 API／DB／execution | consent、reservation、receipt、未驗收零付款、偽造／倒序／UNKNOWN／gate mismatch 通過 |
| T4 背景與觀察 | 原 journal／workers、Memory／Activity | durable correction＋APPLIED join、兩種 correction 來源、path filter、SSE／late narration 不退步 |
| T5 Web／整合 | 原案件頁、API client | 原互動保留、新狀態／確認完整；HTTP／Redis／DB／browser A–F、Python／TS／lint／migration／Docker |
| T6 真模型 Demo | 自備憑證、隔離 fixtures | 保存 path、findings、evaluation、gate、人審、驗收、付款、Memory ID／分數與耗時，不只 HTTP 200 |

依賴 T1 → T2/T3 → T4 → T5 → T6。每個實作任務同步相關規格、prompts、AGENTS 與生成契約；實際 graph 改動時重產高解析度圖，不先把規劃畫成已部署。

### 9.1 確定性驗收矩陣

| 測試 ID | 情境與必要結果 |
| --- | --- |
| PV2-AT01 | 同為收貨第十天，Provider fixtures 分別給已過七天／仍在十五天 deadline，P01 結果不同；等於可受理、補件不重設 |
| PV2-AT02 | P01 無附件／必要拆封可成立，不取 damage／unused；system predicates 未過時空 claims 不放行 |
| PV2-AT03 | P02 損壞成立但到貨時點不足 → NEEDS_INFORMATION，不 DECLINE；P01 替代必有持久化同意 |
| PV2-AT04 | 逾期瑕疵、未知期限／例外／seller、範圍外 → 專責且付款零次；不能宣稱全部權利消失 |
| PV2-AT05 | P03 比較成交 SKU；現在商品頁變更不能改判；缺可信資料不向買家索後端資料 |
| PV2-AT06 | P04 確認未交付才可免退；在途／分批／缺配件／取消／已付不誤通過；system claim 不索商品照片 |
| PV2-AT07 | P01／P02 同包不合併 damage 門檻；跨 path 不誤報 return 衝突，同 path 真衝突 fail closed |
| PV2-AT08 | 原 gate 低於／等於／高於、未知幣別防護，REVISE 不跑 gate，round 0～3，verification 不耗 review round |
| PV2-AT09 | scope 外 Human EDIT、偽造 APPROVE、換 evaluation／bundle／registry、漏 round、舊 consent 重用全拒 |
| PV2-AT10 | 未同意／未送達／未驗收付款零次；合法驗收只一付款；合法免退仍驗 gate |
| PV2-AT11 | producer event 同內容冪等，異內容／錯案／授權／品項／先驗收倒序不付款，receipt commit 後 crash 可恢復 |
| PV2-AT12 | 同品項並行只一 reservation；UNKNOWN 留 owner，原 key 恢復，不新建退款 |
| PV2-AT13 | Memory Policy／registry／path 不符與 Candidate／Retired 不命中；補件空結果清卡、cosine 排序到 UI |
| PV2-AT14 | 審核完成但付款未完成不蒸餾；APPLIED／correction 任意順序／重送只一 job；Reviewer-only correction 可學習 |
| PV2-AT15 | refresh／雙 SSE 還原路徑、同意、履約、人審、退款；cursor 分離，late narration 掛回 source |
| PV2-AT16 | v1 歷史、Intake、多品項 DTO、DECLINE、人審、playback 不退步；unknown discriminator／跨版 checkpoint 不靜默降級 |
| PV2-AT17 | API／Agent 分 DB migrations、outbox／journal lease／draft cache／ACK replay 仍通過，不用單 worker 略過併發測試 |

### 9.2 A–F 真模型展示

| 案例 | 合成主張 | 成功證據 |
| --- | --- | --- |
| A | 低額到貨損壞，希望免退 | 不足補件，獨立核准；需退回時經同意／到貨／驗收後 APPLIED |
| B | 高額到貨損壞，希望免退 | Reviewer 核准後人審；真正可泛化 EDIT 才成立該學習故事，付款後 Candidate→核准 |
| C | 與 B 相同新 Policy／path 的另一案 | 命中 B 同筆 Memory ID，仍經獨立 Reviewer／高額授權，最終 APPLIED |
| D | 一般猶豫期，商品沒壞 | 不取損壞證據，退回驗收後退款 |
| E | 寄錯 SKU | 成交／實收比較與引用，退回驗收後退款 |
| F | 獨立品項確認未交付 | 可信配送依據，不退回，授權後退款 |

真模型可合理選擇不同處置，Distiller 可 SKIP。B 無實際修正、未生 Candidate、C 未命中同筆時如實記錄學習未達成；不得強迫犯錯、手造 Memory、拿 fake vectors 冒充 large。訂單、物流、金流與 Evidence metadata 都標 synthetic；保存去敏完整輸出，不要求文字／相似度／耗時一致。

## 10. 交付判讀

這份是把新政策帶回原專案的規格，不是用獨立 Demo 替換原系統。政策文字、路徑化評估與付款釋放是三個必要部分；原 Intake、Reviewer、Memory 學習與 Activity 體驗均應保留。相關章節正文與可執行 DTO 目前仍描述 v1；待實作驗收後才切換成現行 v2，不宣稱本文件等於已完成整合。
