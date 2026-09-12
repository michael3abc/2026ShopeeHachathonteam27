# 生成欄位字典（baseline固定）

每個JSON property的required、形狀／限制均由schema生成；巢狀ref到同檔$defs，enum/oneOf/anyOf完整保留。schema以外的驗證見M01及semantic-validation-inventory。資料庫所有約束另見fresh SQL。

## AccumulatedEscalationContext

[完整巢狀Schema](assets/schemas/types/AccumulatedEscalationContext.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| clarification_round | 是 | {"minimum":0,"type":"integer"} |
| evidence_round | 是 | {"minimum":0,"type":"integer"} |
| review_history_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| revision_round | 是 | {"minimum":0,"type":"integer"} |
| verification_issues | 否 | {"items":{"$ref":"#/$defs/VerificationIssue"},"type":"array"} |
| verification_round | 是 | {"minimum":0,"type":"integer"} |

## ActivityEmission

[完整巢狀Schema](assets/schemas/types/ActivityEmission.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| attempt_id | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| case_ref | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| event_id | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| job_id | 否 | {"anyOf":[{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},{"type":"null"}],"default":null} |
| node | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| occurred_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| operation_id | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| parent_operation_id | 否 | {"anyOf":[{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},{"type":"null"}],"default":null} |
| payload | 是 | {"discriminator":{"mapping":{"background":"#/$defs/BackgroundStatus","model":"#/$defs/Lifecycle","narration":"#/$defs/Narration","node":"#/$defs/Lifecycle","node_summary":"#/$defs/NodeSummary","tool":"#/$defs/Lifecycle"},"propertyName":"type"},"oneOf":[{"$ref":"#/$defs/Lifecycle"},{"$ref":"#/$defs/NodeSummary"},{"$ref":"#/$defs/Narration"},{"$ref":"#/$defs/BackgroundStatus"}]} |
| run_id | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| schema_version | 否 | {"const":"1.0","default":"1.0","type":"string"} |
| scope | 是 | {"enum":["CASE","REFUND","MEMORY"],"type":"string"} |

## ActivityEvent

[完整巢狀Schema](assets/schemas/types/ActivityEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| attempt_id | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| case_ref | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| event_id | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| job_id | 否 | {"anyOf":[{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},{"type":"null"}],"default":null} |
| node | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| occurred_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| operation_id | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| parent_operation_id | 否 | {"anyOf":[{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},{"type":"null"}],"default":null} |
| payload | 是 | {"discriminator":{"mapping":{"background":"#/$defs/BackgroundStatus","model":"#/$defs/Lifecycle","narration":"#/$defs/Narration","node":"#/$defs/Lifecycle","node_summary":"#/$defs/NodeSummary","tool":"#/$defs/Lifecycle"},"propertyName":"type"},"oneOf":[{"$ref":"#/$defs/Lifecycle"},{"$ref":"#/$defs/NodeSummary"},{"$ref":"#/$defs/Narration"},{"$ref":"#/$defs/BackgroundStatus"}]} |
| run_id | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| schema_version | 否 | {"const":"1.0","default":"1.0","type":"string"} |
| scope | 是 | {"enum":["CASE","REFUND","MEMORY"],"type":"string"} |
| seq | 是 | {"minimum":1,"type":"integer"} |

## ActivityFacts

[完整巢狀Schema](assets/schemas/types/ActivityFacts.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 否 | {"anyOf":[{"enum":["FULL_REFUND","DECLINE"],"type":"string"},{"type":"null"}],"default":null} |
| count | 否 | {"anyOf":[{"minimum":0,"type":"integer"},{"type":"null"}],"default":null} |
| finding_statuses | 否 | {"items":{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},"maxItems":30,"type":"array"} |
| findings | 否 | {"items":{"$ref":"#/$defs/ActivityFinding"},"maxItems":30,"type":"array"} |
| next_node | 否 | {"anyOf":[{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},{"type":"null"}],"default":null} |
| outcome | 否 | {"anyOf":[{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},{"type":"null"}],"default":null} |
| reason_codes | 否 | {"items":{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},"maxItems":30,"type":"array"} |
| references | 否 | {"items":{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},"maxItems":30,"type":"array"} |
| revision_round | 否 | {"anyOf":[{"minimum":0,"type":"integer"},{"type":"null"}],"default":null} |
| verdict | 否 | {"anyOf":[{"enum":["APPROVE","REVISE"],"type":"string"},{"type":"null"}],"default":null} |

## ActivityFinding

[完整巢狀Schema](assets/schemas/types/ActivityFinding.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| claim_id | 是 | {"$ref":"#/$defs/ClaimId"} |
| evidence_refs | 否 | {"items":{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},"maxItems":30,"type":"array"} |
| status | 是 | {"$ref":"#/$defs/ClaimStatus"} |

## ActivityInputs

[完整巢狀Schema](assets/schemas/types/ActivityInputs.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| argument_count | 是 | {"minimum":0,"type":"integer"} |
| reason_code | 否 | {"anyOf":[{"$ref":"#/$defs/ReasonCode"},{"type":"null"}],"default":null} |
| required_claim_ids | 否 | {"items":{"$ref":"#/$defs/ClaimId"},"maxItems":30,"type":"array"} |
| top_k | 否 | {"anyOf":[{"maximum":3,"minimum":1,"type":"integer"},{"type":"null"}],"default":null} |

## ActivityPage

[完整巢狀Schema](assets/schemas/types/ActivityPage.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| events | 是 | {"items":{"$ref":"#/$defs/ActivityEvent"},"type":"array"} |
| has_more | 是 | {"type":"boolean"} |
| next_cursor | 是 | {"minimum":0,"type":"integer"} |

## AgentCommandDeadLetter

[完整巢狀Schema](assets/schemas/types/AgentCommandDeadLetter.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| error_code | 是 | {"minLength":1,"type":"string"} |
| error_message | 是 | {"minLength":1,"type":"string"} |
| failed_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| raw_body | 是 | {"type":"string"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| source_message_id | 是 | {"minLength":1,"type":"string"} |
| source_stream | 否 | {"const":"return-agent.commands.v1","default":"return-agent.commands.v1","type":"string"} |

## AgentEscalatedEvent

[完整巢狀Schema](assets/schemas/types/AgentEscalatedEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| command_id | 是 | {"minLength":1,"type":"string"} |
| event_id | 是 | {"minLength":1,"type":"string"} |
| event_index | 是 | {"minimum":1,"type":"integer"} |
| event_type | 是 | {"const":"ESCALATED","type":"string"} |
| occurred_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| payload | 是 | {"$ref":"#/$defs/AgentEscalatedPayload"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## AgentEscalatedPayload

[完整巢狀Schema](assets/schemas/types/AgentEscalatedPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"$ref":"#/$defs/ManualEscalationAgentRunResult"} |

## AgentFullRefundFinalDecision

[完整巢狀Schema](assets/schemas/types/AgentFullRefundFinalDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"FULL_REFUND","type":"string"} |
| amount | 是 | {"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"} |
| currency | 是 | {"maxLength":3,"minLength":3,"pattern":"^[A-Z]{3}$","type":"string"} |
| reason_code | 是 | {"$ref":"#/$defs/ReasonCode"} |
| refund_scope | 是 | {"$ref":"#/$defs/NonEmptyRefundScope"} |
| return_decision | 是 | {"discriminator":{"mapping":{"MODEL_JUDGMENT":"#/$defs/ModelJudgmentReturnDecision","POLICY":"#/$defs/PolicyReturnDecision"},"propertyName":"source"},"oneOf":[{"$ref":"#/$defs/PolicyReturnDecision"},{"$ref":"#/$defs/ModelJudgmentReturnDecision"}]} |

## AgentInterruptedEvent

[完整巢狀Schema](assets/schemas/types/AgentInterruptedEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| command_id | 是 | {"minLength":1,"type":"string"} |
| event_id | 是 | {"minLength":1,"type":"string"} |
| event_index | 是 | {"minimum":1,"type":"integer"} |
| event_type | 是 | {"const":"INTERRUPTED","type":"string"} |
| occurred_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| payload | 是 | {"$ref":"#/$defs/AgentInterruptedPayload"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## AgentInterruptedPayload

[完整巢狀Schema](assets/schemas/types/AgentInterruptedPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"$ref":"#/$defs/InterruptedAgentRunResult"} |

## AgentNodeObservedEvent

[完整巢狀Schema](assets/schemas/types/AgentNodeObservedEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| command_id | 是 | {"minLength":1,"type":"string"} |
| event_id | 是 | {"minLength":1,"type":"string"} |
| event_index | 是 | {"minimum":1,"type":"integer"} |
| event_type | 是 | {"const":"NODE_OBSERVED","type":"string"} |
| occurred_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| payload | 是 | {"$ref":"#/$defs/AgentNodeObservedPayload"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## AgentNodeObservedPayload

[完整巢狀Schema](assets/schemas/types/AgentNodeObservedPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| observation | 是 | {"$ref":"#/$defs/NodeExecutionObservation"} |

## AgentResolvedEvent

[完整巢狀Schema](assets/schemas/types/AgentResolvedEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| command_id | 是 | {"minLength":1,"type":"string"} |
| event_id | 是 | {"minLength":1,"type":"string"} |
| event_index | 是 | {"minimum":1,"type":"integer"} |
| event_type | 是 | {"const":"RESOLVED","type":"string"} |
| occurred_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| payload | 是 | {"$ref":"#/$defs/AgentResolvedPayload"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## AgentResolvedPayload

[完整巢狀Schema](assets/schemas/types/AgentResolvedPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"$ref":"#/$defs/ResolutionAgentRunResult"} |

## AgentResumeCommand

[完整巢狀Schema](assets/schemas/types/AgentResumeCommand.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| command_id | 是 | {"minLength":1,"type":"string"} |
| command_type | 是 | {"const":"RESUME","type":"string"} |
| issued_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| payload | 是 | {"$ref":"#/$defs/AgentResumePayload"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## AgentResumePayload

[完整巢狀Schema](assets/schemas/types/AgentResumePayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| resume | 是 | {"discriminator":{"mapping":{"CLARIFICATION":"#/$defs/ClarificationResume","EVIDENCE_REQUEST":"#/$defs/EvidenceResume","HUMAN_REVIEW":"#/$defs/HumanReviewPollResume"},"propertyName":"kind"},"oneOf":[{"$ref":"#/$defs/ClarificationResume"},{"$ref":"#/$defs/EvidenceResume"},{"$ref":"#/$defs/HumanReviewPollResume"}]} |

## AgentResumeRequest

[完整巢狀Schema](assets/schemas/types/AgentResumeRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| payload | 是 | {"discriminator":{"mapping":{"CLARIFICATION":"#/$defs/ClarificationResume","EVIDENCE_REQUEST":"#/$defs/EvidenceResume","HUMAN_REVIEW":"#/$defs/HumanReviewPollResume"},"propertyName":"kind"},"oneOf":[{"$ref":"#/$defs/ClarificationResume"},{"$ref":"#/$defs/EvidenceResume"},{"$ref":"#/$defs/HumanReviewPollResume"}]} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## AgentRunFailedEvent

[完整巢狀Schema](assets/schemas/types/AgentRunFailedEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| command_id | 是 | {"minLength":1,"type":"string"} |
| event_id | 是 | {"minLength":1,"type":"string"} |
| event_index | 是 | {"minimum":1,"type":"integer"} |
| event_type | 是 | {"const":"RUN_FAILED","type":"string"} |
| occurred_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| payload | 是 | {"$ref":"#/$defs/AgentRunFailedPayload"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## AgentRunFailedPayload

[完整巢狀Schema](assets/schemas/types/AgentRunFailedPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| code | 是 | {"minLength":1,"type":"string"} |
| failed_node | 否 | {"anyOf":[{"$ref":"#/$defs/GraphNodeName"},{"type":"null"}],"default":null} |
| message | 是 | {"minLength":1,"type":"string"} |
| retryable | 是 | {"type":"boolean"} |

## AgentStartCommand

[完整巢狀Schema](assets/schemas/types/AgentStartCommand.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| command_id | 是 | {"minLength":1,"type":"string"} |
| command_type | 是 | {"const":"START","type":"string"} |
| issued_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| payload | 是 | {"$ref":"#/$defs/AgentStartPayload"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## AgentStartPayload

[完整巢狀Schema](assets/schemas/types/AgentStartPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| initial_turn | 是 | {"$ref":"#/$defs/AgentUserTurn"} |
| order_ref | 是 | {"minLength":1,"type":"string"} |

## AgentStartRequest

[完整巢狀Schema](assets/schemas/types/AgentStartRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| initial_turn | 是 | {"$ref":"#/$defs/AgentUserTurn"} |
| order_ref | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## AgentUserTurn

[完整巢狀Schema](assets/schemas/types/AgentUserTurn.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| attached_artifact_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| received_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| role | 是 | {"const":"USER","type":"string"} |
| text | 是 | {"minLength":1,"type":"string"} |
| turn_id | 是 | {"minLength":1,"type":"string"} |

## ApplicableConditions

[完整巢狀Schema](assets/schemas/types/ApplicableConditions.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| categories | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| markets | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| reason_codes | 否 | {"items":{"$ref":"#/$defs/ReasonCode"},"type":"array"} |

## AppliedRefundApplicationResult

[完整巢狀Schema](assets/schemas/types/AppliedRefundApplicationResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| application_ref | 是 | {"minLength":1,"type":"string"} |
| applied_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| status | 是 | {"const":"APPLIED","type":"string"} |

## ApplyRefundRequest

[完整巢狀Schema](assets/schemas/types/ApplyRefundRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| execution_ref | 是 | {"minLength":1,"type":"string"} |
| resolution_handoff | 是 | {"discriminator":{"mapping":{"HUMAN_APPROVE":"#/$defs/HumanApproveResolutionHandoff","HUMAN_EDIT":"#/$defs/HumanEditResolutionHandoff","HUMAN_REJECT":"#/$defs/HumanRejectResolutionHandoff","REVIEWER_APPROVE":"#/$defs/ReviewerApprovedResolutionHandoff"},"propertyName":"outcome_source"},"oneOf":[{"$ref":"#/$defs/ReviewerApprovedResolutionHandoff"},{"$ref":"#/$defs/HumanApproveResolutionHandoff"},{"$ref":"#/$defs/HumanEditResolutionHandoff"},{"$ref":"#/$defs/HumanRejectResolutionHandoff"}]} |

## ApprovalEvidenceAssessment

[完整巢狀Schema](assets/schemas/types/ApprovalEvidenceAssessment.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| claim_findings | 是 | {"items":{"$ref":"#/$defs/ClaimFinding"},"minItems":1,"type":"array"} |
| claim_registry_version | 是 | {"minLength":1,"type":"string"} |
| evidence_status | 是 | {"const":"SUFFICIENT_FOR_APPROVAL","type":"string"} |

## ApproveReviewDecision

[完整巢狀Schema](assets/schemas/types/ApproveReviewDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| decision | 是 | {"const":"APPROVE","type":"string"} |
| generalizable | 否 | {"anyOf":[{"type":"boolean"},{"type":"null"}],"default":null} |
| handoff_id | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| review_note | 是 | {"minLength":1,"type":"string"} |
| reviewer_id | 否 | {"default":"demo_reviewer","minLength":1,"type":"string"} |

## ApprovedHumanReviewResult

[完整巢狀Schema](assets/schemas/types/ApprovedHumanReviewResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| decision | 是 | {"const":"APPROVE","type":"string"} |
| final_resolution_ref | 是 | {"minLength":1,"type":"string"} |
| generalizable | 否 | {"anyOf":[{"type":"boolean"},{"type":"null"}],"default":null} |
| review_note | 是 | {"minLength":1,"type":"string"} |
| reviewed_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| reviewer_id | 否 | {"default":"demo_reviewer","minLength":1,"type":"string"} |

## ApprovedMemory

[完整巢狀Schema](assets/schemas/types/ApprovedMemory.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| approved_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| claim_registry_version | 是 | {"minLength":1,"type":"string"} |
| confidence | 是 | {"maximum":1,"minimum":0,"type":"number"} |
| memory_id | 是 | {"minLength":1,"type":"string"} |
| policy_version | 是 | {"minLength":1,"type":"string"} |
| recommended_behavior | 是 | {"minLength":1,"type":"string"} |
| retrieval_summary | 是 | {"maxLength":2000,"minLength":1,"type":"string"} |
| scope | 是 | {"$ref":"#/$defs/MemoryScope"} |
| status | 是 | {"const":"APPROVED","type":"string"} |
| trigger_conditions | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |

## ApprovedMemoryRecordView

[完整巢狀Schema](assets/schemas/types/ApprovedMemoryRecordView.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"minLength":1,"type":"string"} |
| boundary | 是 | {"minLength":1,"type":"string"} |
| created_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| hit_count | 否 | {"anyOf":[{"minimum":0,"type":"integer"},{"type":"null"}],"default":null} |
| memory_id | 是 | {"minLength":1,"type":"string"} |
| scope | 是 | {"$ref":"#/$defs/MemoryScope"} |
| source_case_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| status | 是 | {"const":"APPROVED","type":"string"} |
| trigger | 是 | {"minLength":1,"type":"string"} |

## ApprovedReviewResult

[完整巢狀Schema](assets/schemas/types/ApprovedReviewResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| reviewed_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| reviewer_claim_findings | 是 | {"items":{"$ref":"#/$defs/ClaimFinding"},"minItems":1,"type":"array"} |
| reviewer_prompt_version | 是 | {"minLength":1,"type":"string"} |
| revision_reasons | 否 | {"items":{"$ref":"#/$defs/RevisionReason"},"maxItems":0,"type":"array"} |
| verdict | 是 | {"const":"APPROVE","type":"string"} |

## BackgroundStatus

[完整巢狀Schema](assets/schemas/types/BackgroundStatus.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| error_code | 否 | {"anyOf":[{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},{"type":"null"}],"default":null} |
| status | 是 | {"enum":["SCHEDULED","STARTED","RETRYING","COMPLETED","SKIPPED","FAILED"],"type":"string"} |
| type | 否 | {"const":"background","default":"background","type":"string"} |

## CaseContext

[完整巢狀Schema](assets/schemas/types/CaseContext.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_opened_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| market | 是 | {"minLength":1,"type":"string"} |
| order_ref | 是 | {"minLength":1,"type":"string"} |
| snapshot_version | 是 | {"minimum":1,"type":"integer"} |

## CaseContextLoadResult

[完整巢狀Schema](assets/schemas/types/CaseContextLoadResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_context | 是 | {"$ref":"#/$defs/CaseContext"} |
| order_snapshot | 是 | {"$ref":"#/$defs/OrderSnapshot"} |

## CaseDetail

[完整巢狀Schema](assets/schemas/types/CaseDetail.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| clarification_request | 否 | {"anyOf":[{"$ref":"#/$defs/ClarificationRequest"},{"type":"null"}],"default":null} |
| created_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| evidence_request | 否 | {"anyOf":[{"$ref":"#/$defs/EvidenceRequestView"},{"type":"null"}],"default":null} |
| human_review | 否 | {"anyOf":[{"discriminator":{"mapping":{"DECLINE":"#/$defs/DeclineHumanReviewPayload","FULL_REFUND":"#/$defs/FullRefundHumanReviewPayload"},"propertyName":"action"},"oneOf":[{"$ref":"#/$defs/FullRefundHumanReviewPayload"},{"$ref":"#/$defs/DeclineHumanReviewPayload"}]},{"type":"null"}],"default":null} |
| human_review_result | 否 | {"anyOf":[{"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedHumanReviewResult","EDIT":"#/$defs/EditedHumanReviewResult","REJECT":"#/$defs/RejectedHumanReviewResult"},"propertyName":"decision"},"oneOf":[{"$ref":"#/$defs/ApprovedHumanReviewResult"},{"$ref":"#/$defs/EditedHumanReviewResult"},{"$ref":"#/$defs/RejectedHumanReviewResult"}]},{"type":"null"}],"default":null} |
| order_ref | 是 | {"minLength":1,"type":"string"} |
| status | 是 | {"$ref":"#/$defs/CaseStatus"} |
| updated_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| user_ref | 是 | {"minLength":1,"type":"string"} |

## ClaimDefinition

[完整巢狀Schema](assets/schemas/types/ClaimDefinition.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| accepted_evidence_types | 否 | {"default":[],"items":{"$ref":"#/$defs/EvidenceType"},"type":"array"} |
| claim_id | 是 | {"$ref":"#/$defs/ClaimId"} |
| description | 是 | {"minLength":1,"type":"string"} |
| distinguish_from | 否 | {"default":[],"items":{"$ref":"#/$defs/ClaimId"},"type":"array"} |
| observable_requirement | 是 | {"minLength":1,"type":"string"} |
| satisfiable_by | 是 | {"items":{"$ref":"#/$defs/SatisfiableBy"},"type":"array"} |
| subject_scope | 是 | {"$ref":"#/$defs/SubjectScope"} |

## ClaimFinding

[完整巢狀Schema](assets/schemas/types/ClaimFinding.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| claim_id | 是 | {"$ref":"#/$defs/ClaimId"} |
| explanation | 是 | {"minLength":1,"type":"string"} |
| status | 是 | {"$ref":"#/$defs/ClaimStatus"} |
| subject | 是 | {"minLength":1,"type":"string"} |
| supporting_evidence_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |

## ClarificationInterruptPayload

[完整巢狀Schema](assets/schemas/types/ClarificationInterruptPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| interrupt_kind | 是 | {"const":"CLARIFICATION","type":"string"} |
| request | 是 | {"$ref":"#/$defs/ClarificationRequest"} |

## ClarificationRequest

[完整巢狀Schema](assets/schemas/types/ClarificationRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| clarification_question | 是 | {"minLength":1,"type":"string"} |
| clarification_round | 是 | {"minimum":1,"type":"integer"} |
| missing_fields | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| request_id | 是 | {"minLength":1,"type":"string"} |

## ClarificationResume

[完整巢狀Schema](assets/schemas/types/ClarificationResume.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| kind | 是 | {"const":"CLARIFICATION","type":"string"} |
| turn | 是 | {"$ref":"#/$defs/AgentUserTurn"} |

## CorrectedDeclineDecision

[完整巢狀Schema](assets/schemas/types/CorrectedDeclineDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"DECLINE","type":"string"} |
| refund_scope | 是 | {"$ref":"#/$defs/EmptyRefundScope"} |

## CorrectedFullRefundDecision

[完整巢狀Schema](assets/schemas/types/CorrectedFullRefundDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"FULL_REFUND","type":"string"} |
| refund_scope | 是 | {"$ref":"#/$defs/NonEmptyRefundScope"} |
| return_decision | 是 | {"$ref":"#/$defs/HumanReviewReturnDecision"} |

## CreateCaseRequest

[完整巢狀Schema](assets/schemas/types/CreateCaseRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| attached_artifact_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| initial_message | 是 | {"minLength":1,"type":"string"} |
| order_ref | 是 | {"minLength":1,"type":"string"} |
| user_ref | 是 | {"minLength":1,"type":"string"} |

## CreateCaseResponse

[完整巢狀Schema](assets/schemas/types/CreateCaseResponse.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |

## DecisionRevisionEvent

[完整巢狀Schema](assets/schemas/types/DecisionRevisionEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| created_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| event_id | 是 | {"minLength":1,"type":"string"} |
| handoff_before_ref | 是 | {"minLength":1,"type":"string"} |
| review_result | 是 | {"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedReviewResult","REVISE":"#/$defs/RevisedReviewResult"},"propertyName":"verdict"},"oneOf":[{"$ref":"#/$defs/ApprovedReviewResult"},{"$ref":"#/$defs/RevisedReviewResult"}]} |
| revision_round | 是 | {"minimum":1,"type":"integer"} |

## DeclineEvidenceAssessment

[完整巢狀Schema](assets/schemas/types/DeclineEvidenceAssessment.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| claim_findings | 是 | {"items":{"$ref":"#/$defs/ClaimFinding"},"minItems":1,"type":"array"} |
| claim_registry_version | 是 | {"minLength":1,"type":"string"} |
| evidence_status | 是 | {"const":"SUFFICIENT_FOR_DECLINE","type":"string"} |

## DeclineFinalDecision

[完整巢狀Schema](assets/schemas/types/DeclineFinalDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"DECLINE","type":"string"} |
| amount | 是 | {"pattern":"^0(?:\\.0+)?$","type":"string"} |
| currency | 是 | {"maxLength":3,"minLength":3,"pattern":"^[A-Z]{3}$","type":"string"} |
| reason_code | 是 | {"$ref":"#/$defs/ReasonCode"} |
| refund_scope | 是 | {"$ref":"#/$defs/EmptyRefundScope"} |

## DeclineHumanReviewPayload

[完整巢狀Schema](assets/schemas/types/DeclineHumanReviewPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"DECLINE","type":"string"} |
| amount | 是 | {"pattern":"^0(?:\\.0+)?$","type":"string"} |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| currency | 是 | {"maxLength":3,"minLength":3,"pattern":"^[A-Z]{3}$","type":"string"} |
| dossier | 否 | {"anyOf":[{"$ref":"#/$defs/HumanReviewDossier"},{"type":"null"}],"default":null} |
| evidence_refs | 否 | {"items":{"$ref":"#/$defs/EvidenceDisplayRef"},"type":"array"} |
| handoff_id | 是 | {"minLength":1,"type":"string"} |
| memories_used | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| policy_hits | 否 | {"items":{"$ref":"#/$defs/PolicyDisplayRef"},"type":"array"} |
| rationale_summary | 是 | {"minLength":1,"type":"string"} |
| refund_scope | 是 | {"$ref":"#/$defs/EmptyRefundScope"} |
| review_result | 是 | {"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedReviewResult","REVISE":"#/$defs/RevisedReviewResult"},"propertyName":"verdict"},"oneOf":[{"$ref":"#/$defs/ApprovedReviewResult"},{"$ref":"#/$defs/RevisedReviewResult"}]} |
| routing_reason | 否 | {"default":"REVISION_BUDGET_EXCEEDED","enum":["REVISION_BUDGET_EXCEEDED","HIGH_VALUE_ITEM","CURRENCY_THRESHOLD_UNCONFIGURED"],"type":"string"} |

## DeclineProposedDecision

[完整巢狀Schema](assets/schemas/types/DeclineProposedDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"DECLINE","type":"string"} |
| amount | 是 | {"pattern":"^0(?:\\.0+)?$","type":"string"} |
| currency | 是 | {"maxLength":3,"minLength":3,"pattern":"^[A-Z]{3}$","type":"string"} |
| evidence_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| policy_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| reason_code | 是 | {"$ref":"#/$defs/ReasonCode"} |
| refund_scope | 是 | {"$ref":"#/$defs/EmptyRefundScope"} |

## DeclineProposedDecisionDraft

[完整巢狀Schema](assets/schemas/types/DeclineProposedDecisionDraft.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"DECLINE","type":"string"} |
| evidence_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| policy_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| rationale_summary | 是 | {"minLength":1,"type":"string"} |
| reason_code | 是 | {"$ref":"#/$defs/ReasonCode"} |
| refund_scope | 是 | {"$ref":"#/$defs/EmptyRefundScope"} |

## DoneEvent

[完整巢狀Schema](assets/schemas/types/DoneEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| payload | 是 | {"$ref":"#/$defs/DonePayload"} |
| seq | 是 | {"minimum":1,"type":"integer"} |
| ts | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| type | 是 | {"const":"done","type":"string"} |

## DonePayload

[完整巢狀Schema](assets/schemas/types/DonePayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| status | 是 | {"enum":["RESOLVED","ESCALATED"],"type":"string"} |
| terminal_ref | 是 | {"minLength":1,"type":"string"} |

## EditReviewDecision

[完整巢狀Schema](assets/schemas/types/EditReviewDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| corrected_decision | 是 | {"discriminator":{"mapping":{"DECLINE":"#/$defs/CorrectedDeclineDecision","FULL_REFUND":"#/$defs/CorrectedFullRefundDecision"},"propertyName":"action"},"oneOf":[{"$ref":"#/$defs/CorrectedFullRefundDecision"},{"$ref":"#/$defs/CorrectedDeclineDecision"}]} |
| correction_reason_code | 是 | {"$ref":"#/$defs/HumanCorrectionReasonCode"} |
| decision | 是 | {"const":"EDIT","type":"string"} |
| generalizable | 否 | {"anyOf":[{"type":"boolean"},{"type":"null"}],"default":null} |
| handoff_id | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| review_note | 是 | {"minLength":1,"type":"string"} |
| reviewer_id | 否 | {"default":"demo_reviewer","minLength":1,"type":"string"} |

## EditedHumanReviewResult

[完整巢狀Schema](assets/schemas/types/EditedHumanReviewResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| corrected_decision | 是 | {"discriminator":{"mapping":{"DECLINE":"#/$defs/CorrectedDeclineDecision","FULL_REFUND":"#/$defs/CorrectedFullRefundDecision"},"propertyName":"action"},"oneOf":[{"$ref":"#/$defs/CorrectedFullRefundDecision"},{"$ref":"#/$defs/CorrectedDeclineDecision"}]} |
| correction_reason_code | 是 | {"$ref":"#/$defs/HumanCorrectionReasonCode"} |
| decision | 是 | {"const":"EDIT","type":"string"} |
| final_resolution_ref | 是 | {"minLength":1,"type":"string"} |
| generalizable | 否 | {"anyOf":[{"type":"boolean"},{"type":"null"}],"default":null} |
| review_note | 是 | {"minLength":1,"type":"string"} |
| reviewed_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| reviewer_id | 否 | {"default":"demo_reviewer","minLength":1,"type":"string"} |

## EmptyRefundScope

[完整巢狀Schema](assets/schemas/types/EmptyRefundScope.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| line_item_ids | 否 | {"items":{"minLength":1,"type":"string"},"maxItems":0,"type":"array"} |

## ErrorEvent

[完整巢狀Schema](assets/schemas/types/ErrorEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| payload | 是 | {"$ref":"#/$defs/ErrorPayload"} |
| seq | 是 | {"minimum":1,"type":"integer"} |
| ts | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| type | 是 | {"const":"error","type":"string"} |

## ErrorPayload

[完整巢狀Schema](assets/schemas/types/ErrorPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| code | 是 | {"minLength":1,"type":"string"} |
| message | 是 | {"minLength":1,"type":"string"} |
| retryable | 是 | {"type":"boolean"} |

## EvidenceDisplayRef

[完整巢狀Schema](assets/schemas/types/EvidenceDisplayRef.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| artifact_ref | 是 | {"minLength":1,"type":"string"} |
| caption | 是 | {"minLength":1,"type":"string"} |
| evidence_id | 是 | {"minLength":1,"type":"string"} |
| subject | 是 | {"minLength":1,"type":"string"} |
| type | 是 | {"$ref":"#/$defs/EvidenceType"} |

## EvidenceInterruptPayload

[完整巢狀Schema](assets/schemas/types/EvidenceInterruptPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| interrupt_kind | 是 | {"const":"EVIDENCE_REQUEST","type":"string"} |
| request | 是 | {"$ref":"#/$defs/EvidenceRequestView"} |

## EvidenceItem

[完整巢狀Schema](assets/schemas/types/EvidenceItem.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| artifact_ref | 是 | {"minLength":1,"type":"string"} |
| collected_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| evidence_id | 是 | {"minLength":1,"type":"string"} |
| extracted_summary | 是 | {"minLength":1,"type":"string"} |
| source | 是 | {"$ref":"#/$defs/EvidenceSource"} |
| subject | 是 | {"minLength":1,"type":"string"} |
| type | 是 | {"$ref":"#/$defs/EvidenceType"} |

## EvidenceRequest

[完整巢狀Schema](assets/schemas/types/EvidenceRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| accepted_evidence_types | 是 | {"items":{"$ref":"#/$defs/EvidenceType"},"minItems":1,"type":"array"} |
| missing_claims | 是 | {"items":{"$ref":"#/$defs/MissingClaim"},"minItems":1,"type":"array"} |
| policy_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| request_id | 是 | {"minLength":1,"type":"string"} |
| user_message | 是 | {"minLength":1,"type":"string"} |

## EvidenceRequestView

[完整巢狀Schema](assets/schemas/types/EvidenceRequestView.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| accepted_evidence_types | 是 | {"items":{"$ref":"#/$defs/EvidenceType"},"minItems":1,"type":"array"} |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| missing_claims | 是 | {"items":{"$ref":"#/$defs/MissingClaim"},"minItems":1,"type":"array"} |
| policy_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| request_id | 是 | {"minLength":1,"type":"string"} |
| user_message | 是 | {"minLength":1,"type":"string"} |

## EvidenceResume

[完整巢狀Schema](assets/schemas/types/EvidenceResume.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| artifact_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| kind | 是 | {"const":"EVIDENCE_REQUEST","type":"string"} |

## ExecuteRefundRequest

[完整巢狀Schema](assets/schemas/types/ExecuteRefundRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| resolution_handoff | 是 | {"discriminator":{"mapping":{"HUMAN_APPROVE":"#/$defs/HumanApproveResolutionHandoff","HUMAN_EDIT":"#/$defs/HumanEditResolutionHandoff","HUMAN_REJECT":"#/$defs/HumanRejectResolutionHandoff","REVIEWER_APPROVE":"#/$defs/ReviewerApprovedResolutionHandoff"},"propertyName":"outcome_source"},"oneOf":[{"$ref":"#/$defs/ReviewerApprovedResolutionHandoff"},{"$ref":"#/$defs/HumanApproveResolutionHandoff"},{"$ref":"#/$defs/HumanEditResolutionHandoff"},{"$ref":"#/$defs/HumanRejectResolutionHandoff"}]} |

## FailedVerificationResult

[完整巢狀Schema](assets/schemas/types/FailedVerificationResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| issues | 是 | {"items":{"$ref":"#/$defs/VerificationIssue"},"minItems":1,"type":"array"} |
| status | 是 | {"const":"FAIL","type":"string"} |
| verification_version | 是 | {"minLength":1,"type":"string"} |

## FetchHumanReviewParams

[完整巢狀Schema](assets/schemas/types/FetchHumanReviewParams.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| review_ref | 是 | {"minLength":1,"type":"string"} |

## FetchHumanReviewRequest

[完整巢狀Schema](assets/schemas/types/FetchHumanReviewRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| method | 是 | {"const":"HumanReviewProvider.fetch_result","type":"string"} |
| params | 是 | {"$ref":"#/$defs/FetchHumanReviewParams"} |

## FetchHumanReviewResponse

[完整巢狀Schema](assets/schemas/types/FetchHumanReviewResponse.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"anyOf":[{"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedHumanReviewResult","EDIT":"#/$defs/EditedHumanReviewResult","REJECT":"#/$defs/RejectedHumanReviewResult"},"propertyName":"decision"},"oneOf":[{"$ref":"#/$defs/ApprovedHumanReviewResult"},{"$ref":"#/$defs/EditedHumanReviewResult"},{"$ref":"#/$defs/RejectedHumanReviewResult"}]},{"type":"null"}]} |

## FullRefundFinalDecision

[完整巢狀Schema](assets/schemas/types/FullRefundFinalDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"FULL_REFUND","type":"string"} |
| amount | 是 | {"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"} |
| currency | 是 | {"maxLength":3,"minLength":3,"pattern":"^[A-Z]{3}$","type":"string"} |
| reason_code | 是 | {"$ref":"#/$defs/ReasonCode"} |
| refund_scope | 是 | {"$ref":"#/$defs/NonEmptyRefundScope"} |
| return_decision | 是 | {"discriminator":{"mapping":{"HUMAN_REVIEW":"#/$defs/HumanReviewReturnDecision","MODEL_JUDGMENT":"#/$defs/ModelJudgmentReturnDecision","POLICY":"#/$defs/PolicyReturnDecision"},"propertyName":"source"},"oneOf":[{"$ref":"#/$defs/PolicyReturnDecision"},{"$ref":"#/$defs/ModelJudgmentReturnDecision"},{"$ref":"#/$defs/HumanReviewReturnDecision"}]} |

## FullRefundHumanReviewPayload

[完整巢狀Schema](assets/schemas/types/FullRefundHumanReviewPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"FULL_REFUND","type":"string"} |
| amount | 是 | {"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"} |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| currency | 是 | {"maxLength":3,"minLength":3,"pattern":"^[A-Z]{3}$","type":"string"} |
| dossier | 否 | {"anyOf":[{"$ref":"#/$defs/HumanReviewDossier"},{"type":"null"}],"default":null} |
| evidence_refs | 否 | {"items":{"$ref":"#/$defs/EvidenceDisplayRef"},"type":"array"} |
| handoff_id | 是 | {"minLength":1,"type":"string"} |
| memories_used | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| policy_hits | 否 | {"items":{"$ref":"#/$defs/PolicyDisplayRef"},"type":"array"} |
| rationale_summary | 是 | {"minLength":1,"type":"string"} |
| refund_scope | 是 | {"$ref":"#/$defs/NonEmptyRefundScope"} |
| return_decision | 是 | {"discriminator":{"mapping":{"MODEL_JUDGMENT":"#/$defs/ModelJudgmentReturnDecision","POLICY":"#/$defs/PolicyReturnDecision"},"propertyName":"source"},"oneOf":[{"$ref":"#/$defs/PolicyReturnDecision"},{"$ref":"#/$defs/ModelJudgmentReturnDecision"}]} |
| review_result | 是 | {"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedReviewResult","REVISE":"#/$defs/RevisedReviewResult"},"propertyName":"verdict"},"oneOf":[{"$ref":"#/$defs/ApprovedReviewResult"},{"$ref":"#/$defs/RevisedReviewResult"}]} |
| routing_reason | 否 | {"default":"REVISION_BUDGET_EXCEEDED","enum":["REVISION_BUDGET_EXCEEDED","HIGH_VALUE_ITEM","CURRENCY_THRESHOLD_UNCONFIGURED"],"type":"string"} |

## FullRefundProposedDecision

[完整巢狀Schema](assets/schemas/types/FullRefundProposedDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"FULL_REFUND","type":"string"} |
| amount | 是 | {"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"} |
| currency | 是 | {"maxLength":3,"minLength":3,"pattern":"^[A-Z]{3}$","type":"string"} |
| evidence_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| policy_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| reason_code | 是 | {"$ref":"#/$defs/ReasonCode"} |
| refund_scope | 是 | {"$ref":"#/$defs/NonEmptyRefundScope"} |
| return_decision | 是 | {"discriminator":{"mapping":{"MODEL_JUDGMENT":"#/$defs/ModelJudgmentReturnDecision","POLICY":"#/$defs/PolicyReturnDecision"},"propertyName":"source"},"oneOf":[{"$ref":"#/$defs/PolicyReturnDecision"},{"$ref":"#/$defs/ModelJudgmentReturnDecision"}]} |

## FullRefundProposedDecisionDraft

[完整巢狀Schema](assets/schemas/types/FullRefundProposedDecisionDraft.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"FULL_REFUND","type":"string"} |
| evidence_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| policy_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| rationale_summary | 是 | {"minLength":1,"type":"string"} |
| reason_code | 是 | {"$ref":"#/$defs/ReasonCode"} |
| refund_scope | 是 | {"$ref":"#/$defs/NonEmptyRefundScope"} |
| return_decision | 是 | {"discriminator":{"mapping":{"MODEL_JUDGMENT":"#/$defs/ModelJudgmentReturnDecision","POLICY":"#/$defs/PolicyReturnDecisionDraft"},"propertyName":"source"},"oneOf":[{"$ref":"#/$defs/PolicyReturnDecisionDraft"},{"$ref":"#/$defs/ModelJudgmentReturnDecision"}]} |

## HumanApproveResolutionHandoff

[完整巢狀Schema](assets/schemas/types/HumanApproveResolutionHandoff.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| emitted_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| execution_blocked | 是 | {"const":false,"type":"boolean"} |
| final_decision | 是 | {"discriminator":{"mapping":{"DECLINE":"#/$defs/DeclineFinalDecision","FULL_REFUND":"#/$defs/AgentFullRefundFinalDecision"},"propertyName":"action"},"oneOf":[{"$ref":"#/$defs/AgentFullRefundFinalDecision"},{"$ref":"#/$defs/DeclineFinalDecision"}]} |
| handoff_id | 是 | {"minLength":1,"type":"string"} |
| outcome_source | 是 | {"const":"HUMAN_APPROVE","type":"string"} |
| review_gate | 否 | {"anyOf":[{"$ref":"#/$defs/ReviewGateResult"},{"type":"null"}],"default":null} |
| review_result | 是 | {"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedReviewResult","REVISE":"#/$defs/RevisedReviewResult"},"propertyName":"verdict"},"oneOf":[{"$ref":"#/$defs/ApprovedReviewResult"},{"$ref":"#/$defs/RevisedReviewResult"}]} |

## HumanEditResolutionHandoff

[完整巢狀Schema](assets/schemas/types/HumanEditResolutionHandoff.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| emitted_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| execution_blocked | 是 | {"const":false,"type":"boolean"} |
| final_decision | 是 | {"discriminator":{"mapping":{"DECLINE":"#/$defs/DeclineFinalDecision","FULL_REFUND":"#/$defs/HumanEditedFullRefundFinalDecision"},"propertyName":"action"},"oneOf":[{"$ref":"#/$defs/HumanEditedFullRefundFinalDecision"},{"$ref":"#/$defs/DeclineFinalDecision"}]} |
| handoff_id | 是 | {"minLength":1,"type":"string"} |
| outcome_source | 是 | {"const":"HUMAN_EDIT","type":"string"} |
| review_gate | 否 | {"anyOf":[{"$ref":"#/$defs/ReviewGateResult"},{"type":"null"}],"default":null} |
| review_result | 是 | {"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedReviewResult","REVISE":"#/$defs/RevisedReviewResult"},"propertyName":"verdict"},"oneOf":[{"$ref":"#/$defs/ApprovedReviewResult"},{"$ref":"#/$defs/RevisedReviewResult"}]} |

## HumanEditedFullRefundFinalDecision

[完整巢狀Schema](assets/schemas/types/HumanEditedFullRefundFinalDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"const":"FULL_REFUND","type":"string"} |
| amount | 是 | {"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"} |
| currency | 是 | {"maxLength":3,"minLength":3,"pattern":"^[A-Z]{3}$","type":"string"} |
| reason_code | 是 | {"$ref":"#/$defs/ReasonCode"} |
| refund_scope | 是 | {"$ref":"#/$defs/NonEmptyRefundScope"} |
| return_decision | 是 | {"$ref":"#/$defs/HumanReviewReturnDecision"} |

## HumanRejectResolutionHandoff

[完整巢狀Schema](assets/schemas/types/HumanRejectResolutionHandoff.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| emitted_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| execution_blocked | 是 | {"const":false,"type":"boolean"} |
| final_decision | 是 | {"$ref":"#/$defs/DeclineFinalDecision"} |
| handoff_id | 是 | {"minLength":1,"type":"string"} |
| outcome_source | 是 | {"const":"HUMAN_REJECT","type":"string"} |
| review_gate | 否 | {"anyOf":[{"$ref":"#/$defs/ReviewGateResult"},{"type":"null"}],"default":null} |
| review_result | 是 | {"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedReviewResult","REVISE":"#/$defs/RevisedReviewResult"},"propertyName":"verdict"},"oneOf":[{"$ref":"#/$defs/ApprovedReviewResult"},{"$ref":"#/$defs/RevisedReviewResult"}]} |

## HumanReviewDossier

[完整巢狀Schema](assets/schemas/types/HumanReviewDossier.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| claim_registry_version | 是 | {"minLength":1,"type":"string"} |
| claimed_line_item_ids | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| order_snapshot | 是 | {"$ref":"#/$defs/OrderSnapshot"} |
| policy_bundle | 是 | {"$ref":"#/$defs/PolicyBundle"} |
| proposal_history | 是 | {"items":{"$ref":"#/$defs/ProposedDecisionHandoff"},"minItems":1,"type":"array"} |
| review_gate | 否 | {"anyOf":[{"$ref":"#/$defs/ReviewGateResult"},{"type":"null"}],"default":null} |
| review_history | 是 | {"items":{"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedReviewResult","REVISE":"#/$defs/RevisedReviewResult"},"propertyName":"verdict"},"oneOf":[{"$ref":"#/$defs/ApprovedReviewResult"},{"$ref":"#/$defs/RevisedReviewResult"}]},"minItems":1,"type":"array"} |
| revision_events | 否 | {"items":{"$ref":"#/$defs/DecisionRevisionEvent"},"type":"array"} |
| routing_reason | 否 | {"default":"REVISION_BUDGET_EXCEEDED","enum":["REVISION_BUDGET_EXCEEDED","HIGH_VALUE_ITEM","CURRENCY_THRESHOLD_UNCONFIGURED"],"type":"string"} |

## HumanReviewInterruptPayload

[完整巢狀Schema](assets/schemas/types/HumanReviewInterruptPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| interrupt_kind | 是 | {"const":"HUMAN_REVIEW","type":"string"} |
| review | 是 | {"discriminator":{"mapping":{"DECLINE":"#/$defs/DeclineHumanReviewPayload","FULL_REFUND":"#/$defs/FullRefundHumanReviewPayload"},"propertyName":"action"},"oneOf":[{"$ref":"#/$defs/FullRefundHumanReviewPayload"},{"$ref":"#/$defs/DeclineHumanReviewPayload"}]} |

## HumanReviewPollResume

[完整巢狀Schema](assets/schemas/types/HumanReviewPollResume.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| kind | 是 | {"const":"HUMAN_REVIEW","type":"string"} |

## HumanReviewReturnDecision

[完整巢狀Schema](assets/schemas/types/HumanReviewReturnDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| requirement | 是 | {"discriminator":{"mapping":{"False":"#/$defs/WaivedReturnRequirement","True":"#/$defs/RequiredReturnRequirement"},"propertyName":"required"},"oneOf":[{"$ref":"#/$defs/RequiredReturnRequirement"},{"$ref":"#/$defs/WaivedReturnRequirement"}]} |
| source | 是 | {"const":"HUMAN_REVIEW","type":"string"} |

## InsufficientEvidenceAssessment

[完整巢狀Schema](assets/schemas/types/InsufficientEvidenceAssessment.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| claim_findings | 是 | {"items":{"$ref":"#/$defs/ClaimFinding"},"minItems":1,"type":"array"} |
| claim_registry_version | 是 | {"minLength":1,"type":"string"} |
| evidence_status | 是 | {"const":"INSUFFICIENT","type":"string"} |
| missing_evidence_request | 是 | {"$ref":"#/$defs/EvidenceRequest"} |

## IntakeResult

[完整巢狀Schema](assets/schemas/types/IntakeResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| claimed_line_item_ids | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| clarification_question | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| completeness | 是 | {"$ref":"#/$defs/IntakeCompleteness"} |
| missing_fields | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| order_ref | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| reason_code | 否 | {"anyOf":[{"$ref":"#/$defs/ReasonCode"},{"type":"null"}],"default":null} |
| reason_summary | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| requested_action | 是 | {"$ref":"#/$defs/RequestedAction"} |

## InterruptEvent

[完整巢狀Schema](assets/schemas/types/InterruptEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| payload | 是 | {"discriminator":{"mapping":{"CLARIFICATION":"#/$defs/ClarificationInterruptPayload","EVIDENCE_REQUEST":"#/$defs/EvidenceInterruptPayload","HUMAN_REVIEW":"#/$defs/HumanReviewInterruptPayload"},"propertyName":"interrupt_kind"},"oneOf":[{"$ref":"#/$defs/ClarificationInterruptPayload"},{"$ref":"#/$defs/EvidenceInterruptPayload"},{"$ref":"#/$defs/HumanReviewInterruptPayload"}]} |
| seq | 是 | {"minimum":1,"type":"integer"} |
| ts | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| type | 是 | {"const":"interrupt","type":"string"} |

## InterruptedAgentRunResult

[完整巢狀Schema](assets/schemas/types/InterruptedAgentRunResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| interrupt_payload | 是 | {"discriminator":{"mapping":{"CLARIFICATION":"#/$defs/ClarificationInterruptPayload","EVIDENCE_REQUEST":"#/$defs/EvidenceInterruptPayload","HUMAN_REVIEW":"#/$defs/HumanReviewInterruptPayload"},"propertyName":"kind"},"oneOf":[{"$ref":"#/$defs/ClarificationInterruptPayload"},{"$ref":"#/$defs/EvidenceInterruptPayload"},{"$ref":"#/$defs/HumanReviewInterruptPayload"}]} |
| result_type | 是 | {"const":"INTERRUPTED","type":"string"} |
| status | 是 | {"const":"INTERRUPTED","type":"string"} |

## Lifecycle

[完整巢狀Schema](assets/schemas/types/Lifecycle.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| duration_ms | 否 | {"anyOf":[{"minimum":0,"type":"integer"},{"type":"null"}],"default":null} |
| error_code | 否 | {"anyOf":[{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},{"type":"null"}],"default":null} |
| facts | 否 | {"$ref":"#/$defs/ActivityFacts"} |
| inputs | 否 | {"anyOf":[{"$ref":"#/$defs/ActivityInputs"},{"type":"null"}],"default":null} |
| model | 否 | {"anyOf":[{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},{"type":"null"}],"default":null} |
| name | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| phase | 是 | {"enum":["STARTED","COMPLETED","PAUSED","FAILED"],"type":"string"} |
| type | 是 | {"enum":["node","model","tool"],"type":"string"} |

## LoadCaseContextParams

[完整巢狀Schema](assets/schemas/types/LoadCaseContextParams.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |

## LoadCaseContextRequest

[完整巢狀Schema](assets/schemas/types/LoadCaseContextRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| method | 是 | {"const":"CaseContextProvider.load_case_context","type":"string"} |
| params | 是 | {"$ref":"#/$defs/LoadCaseContextParams"} |

## LoadCaseContextResponse

[完整巢狀Schema](assets/schemas/types/LoadCaseContextResponse.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"$ref":"#/$defs/CaseContextLoadResult"} |

## ManualEscalationAgentRunResult

[完整巢狀Schema](assets/schemas/types/ManualEscalationAgentRunResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| manual_escalation | 是 | {"$ref":"#/$defs/ManualEscalationHandoff"} |
| result_type | 是 | {"const":"MANUAL_ESCALATION","type":"string"} |
| status | 是 | {"const":"COMPLETED","type":"string"} |

## ManualEscalationHandoff

[完整巢狀Schema](assets/schemas/types/ManualEscalationHandoff.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| accumulated_context | 是 | {"$ref":"#/$defs/AccumulatedEscalationContext"} |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| created_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| escalation_reason | 是 | {"$ref":"#/$defs/EscalationReason"} |
| last_known_handoff_ref | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## MemoryCandidate

[完整巢狀Schema](assets/schemas/types/MemoryCandidate.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| claim_registry_version | 是 | {"minLength":1,"type":"string"} |
| confidence | 是 | {"maximum":1,"minimum":0,"type":"number"} |
| memory_id | 是 | {"minLength":1,"type":"string"} |
| policy_version | 是 | {"minLength":1,"type":"string"} |
| rationale | 是 | {"minLength":1,"type":"string"} |
| recommended_behavior | 是 | {"minLength":1,"type":"string"} |
| retrieval_summary | 是 | {"maxLength":2000,"minLength":1,"type":"string"} |
| scope | 是 | {"$ref":"#/$defs/MemoryScope"} |
| source_case_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| source_revision_event_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| status | 是 | {"const":"CANDIDATE","type":"string"} |
| trigger_conditions | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |

## MemoryCandidateCompletedPayload

[完整巢狀Schema](assets/schemas/types/MemoryCandidateCompletedPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| distiller_prompt_version | 是 | {"minLength":1,"type":"string"} |
| result | 是 | {"$ref":"#/$defs/MemoryCandidateOutput"} |
| submission_ref | 是 | {"minLength":1,"type":"string"} |

## MemoryCandidateOutput

[完整巢狀Schema](assets/schemas/types/MemoryCandidateOutput.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| candidate | 是 | {"$ref":"#/$defs/MemoryCandidate"} |
| result_type | 是 | {"const":"CREATE_CANDIDATE","type":"string"} |

## MemoryDistillationCompletedEvent

[完整巢狀Schema](assets/schemas/types/MemoryDistillationCompletedEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| event_id | 是 | {"minLength":1,"type":"string"} |
| event_type | 是 | {"const":"COMPLETED","type":"string"} |
| job_id | 是 | {"minLength":1,"type":"string"} |
| occurred_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| payload | 是 | {"anyOf":[{"$ref":"#/$defs/MemoryCandidateCompletedPayload"},{"$ref":"#/$defs/MemorySkipCompletedPayload"}]} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| source_command_id | 是 | {"minLength":1,"type":"string"} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## MemoryDistillationFailedEvent

[完整巢狀Schema](assets/schemas/types/MemoryDistillationFailedEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| event_id | 是 | {"minLength":1,"type":"string"} |
| event_type | 是 | {"const":"FAILED","type":"string"} |
| job_id | 是 | {"minLength":1,"type":"string"} |
| occurred_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| payload | 是 | {"$ref":"#/$defs/MemoryDistillationFailedPayload"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| source_command_id | 是 | {"minLength":1,"type":"string"} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## MemoryDistillationFailedPayload

[完整巢狀Schema](assets/schemas/types/MemoryDistillationFailedPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| code | 是 | {"minLength":1,"type":"string"} |
| distiller_prompt_version | 是 | {"minLength":1,"type":"string"} |
| message | 是 | {"minLength":1,"type":"string"} |
| retryable | 是 | {"type":"boolean"} |

## MemoryDistillationInput

[完整巢狀Schema](assets/schemas/types/MemoryDistillationInput.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_context | 是 | {"$ref":"#/$defs/CaseContext"} |
| claimed_categories | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| evidence_assessment | 是 | {"discriminator":{"mapping":{"INSUFFICIENT":"#/$defs/InsufficientEvidenceAssessment","SUFFICIENT_FOR_APPROVAL":"#/$defs/ApprovalEvidenceAssessment","SUFFICIENT_FOR_DECLINE":"#/$defs/DeclineEvidenceAssessment"},"propertyName":"evidence_status"},"oneOf":[{"$ref":"#/$defs/ApprovalEvidenceAssessment"},{"$ref":"#/$defs/DeclineEvidenceAssessment"},{"$ref":"#/$defs/InsufficientEvidenceAssessment"}]} |
| final_resolution | 是 | {"discriminator":{"mapping":{"HUMAN_APPROVE":"#/$defs/HumanApproveResolutionHandoff","HUMAN_EDIT":"#/$defs/HumanEditResolutionHandoff","HUMAN_REJECT":"#/$defs/HumanRejectResolutionHandoff","REVIEWER_APPROVE":"#/$defs/ReviewerApprovedResolutionHandoff"},"propertyName":"outcome_source"},"oneOf":[{"$ref":"#/$defs/ReviewerApprovedResolutionHandoff"},{"$ref":"#/$defs/HumanApproveResolutionHandoff"},{"$ref":"#/$defs/HumanEditResolutionHandoff"},{"$ref":"#/$defs/HumanRejectResolutionHandoff"}]} |
| human_review_result | 否 | {"anyOf":[{"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedHumanReviewResult","EDIT":"#/$defs/EditedHumanReviewResult","REJECT":"#/$defs/RejectedHumanReviewResult"},"propertyName":"decision"},"oneOf":[{"$ref":"#/$defs/ApprovedHumanReviewResult"},{"$ref":"#/$defs/EditedHumanReviewResult"},{"$ref":"#/$defs/RejectedHumanReviewResult"}]},{"type":"null"}],"default":null} |
| policy_bundle | 是 | {"$ref":"#/$defs/PolicyBundle"} |
| proposal_history | 是 | {"items":{"$ref":"#/$defs/ProposedDecisionHandoff"},"minItems":1,"type":"array"} |
| revision_events | 否 | {"items":{"$ref":"#/$defs/DecisionRevisionEvent"},"type":"array"} |

## MemoryDistillationJob

[完整巢狀Schema](assets/schemas/types/MemoryDistillationJob.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| issued_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| job_id | 是 | {"minLength":1,"type":"string"} |
| payload | 是 | {"$ref":"#/$defs/MemoryDistillationJobPayload"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| source_command_id | 是 | {"minLength":1,"type":"string"} |
| thread_id | 是 | {"minLength":1,"type":"string"} |

## MemoryDistillationJobPayload

[完整巢狀Schema](assets/schemas/types/MemoryDistillationJobPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| input | 是 | {"$ref":"#/$defs/MemoryDistillationInput"} |

## MemoryJobDeadLetter

[完整巢狀Schema](assets/schemas/types/MemoryJobDeadLetter.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| error_code | 是 | {"minLength":1,"type":"string"} |
| error_message | 是 | {"minLength":1,"type":"string"} |
| failed_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| raw_body | 是 | {"type":"string"} |
| schema_version | 否 | {"const":"v1","default":"v1","type":"string"} |
| source_message_id | 是 | {"minLength":1,"type":"string"} |
| source_stream | 否 | {"const":"return-agent.memory-jobs.v1","default":"return-agent.memory-jobs.v1","type":"string"} |

## MemoryQuerySummary

[完整巢狀Schema](assets/schemas/types/MemoryQuerySummary.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| query_summary | 是 | {"maxLength":2000,"minLength":1,"type":"string"} |

## MemoryRecordView

[完整巢狀Schema](assets/schemas/types/MemoryRecordView.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| action | 是 | {"minLength":1,"type":"string"} |
| boundary | 是 | {"minLength":1,"type":"string"} |
| created_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| hit_count | 否 | {"anyOf":[{"minimum":0,"type":"integer"},{"type":"null"}],"default":null} |
| memory_id | 是 | {"minLength":1,"type":"string"} |
| scope | 是 | {"$ref":"#/$defs/MemoryScope"} |
| source_case_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| status | 是 | {"$ref":"#/$defs/MemoryStatus"} |
| trigger | 是 | {"minLength":1,"type":"string"} |

## MemoryRetrievalEvent

[完整巢狀Schema](assets/schemas/types/MemoryRetrievalEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| payload | 是 | {"$ref":"#/$defs/MemoryRetrievalPayload"} |
| seq | 是 | {"minimum":1,"type":"integer"} |
| ts | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| type | 是 | {"const":"memory_retrieval","type":"string"} |

## MemoryRetrievalObservation

[完整巢狀Schema](assets/schemas/types/MemoryRetrievalObservation.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| error_code | 否 | {"anyOf":[{"enum":["SUMMARY_UNAVAILABLE","RETRIEVAL_UNAVAILABLE"],"type":"string"},{"type":"null"}],"default":null} |
| hits | 否 | {"items":{"$ref":"#/$defs/MemorySearchHit"},"maxItems":3,"type":"array"} |
| query_summary | 否 | {"anyOf":[{"maxLength":2000,"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| status | 是 | {"enum":["OK","UNAVAILABLE"],"type":"string"} |

## MemoryRetrievalPayload

[完整巢狀Schema](assets/schemas/types/MemoryRetrievalPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| error_code | 否 | {"anyOf":[{"enum":["SUMMARY_UNAVAILABLE","RETRIEVAL_UNAVAILABLE"],"type":"string"},{"type":"null"}],"default":null} |
| hits | 否 | {"items":{"$ref":"#/$defs/MemorySearchHit"},"maxItems":3,"type":"array"} |
| query_summary | 否 | {"anyOf":[{"maxLength":2000,"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| status | 是 | {"enum":["OK","UNAVAILABLE"],"type":"string"} |

## MemoryScope

[完整巢狀Schema](assets/schemas/types/MemoryScope.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| categories | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| claim_ids | 否 | {"items":{"$ref":"#/$defs/ClaimId"},"type":"array"} |
| market | 是 | {"minLength":1,"type":"string"} |
| reason_codes | 否 | {"items":{"$ref":"#/$defs/ReasonCode"},"type":"array"} |

## MemorySearchHit

[完整巢狀Schema](assets/schemas/types/MemorySearchHit.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| memory | 是 | {"$ref":"#/$defs/ApprovedMemory"} |
| similarity | 是 | {"maximum":1,"minimum":-1,"type":"number"} |

## MemorySkipCompletedPayload

[完整巢狀Schema](assets/schemas/types/MemorySkipCompletedPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| distiller_prompt_version | 是 | {"minLength":1,"type":"string"} |
| result | 是 | {"$ref":"#/$defs/MemorySkipOutput"} |
| submission_ref | 否 | {"default":null,"type":"null"} |

## MemorySkipOutput

[完整巢狀Schema](assets/schemas/types/MemorySkipOutput.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| reason_code | 是 | {"$ref":"#/$defs/MemorySkipReasonCode"} |
| result_type | 是 | {"const":"SKIP","type":"string"} |

## MissingClaim

[完整巢狀Schema](assets/schemas/types/MissingClaim.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| claim_id | 是 | {"$ref":"#/$defs/ClaimId"} |
| subject | 是 | {"minLength":1,"type":"string"} |

## ModelJudgmentReturnDecision

[完整巢狀Schema](assets/schemas/types/ModelJudgmentReturnDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| requirement | 是 | {"discriminator":{"mapping":{"False":"#/$defs/WaivedReturnRequirement","True":"#/$defs/RequiredReturnRequirement"},"propertyName":"required"},"oneOf":[{"$ref":"#/$defs/RequiredReturnRequirement"},{"$ref":"#/$defs/WaivedReturnRequirement"}]} |
| source | 是 | {"const":"MODEL_JUDGMENT","type":"string"} |

## Narration

[完整巢狀Schema](assets/schemas/types/Narration.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| error_code | 否 | {"anyOf":[{"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"},{"type":"null"}],"default":null} |
| source_event_id | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| status | 是 | {"enum":["COMPLETED","UNAVAILABLE"],"type":"string"} |
| text | 否 | {"anyOf":[{"maxLength":600,"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| type | 否 | {"const":"narration","default":"narration","type":"string"} |

## NarrationJob

[完整巢狀Schema](assets/schemas/types/NarrationJob.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| job_id | 是 | {"maxLength":200,"minLength":1,"pattern":"^[A-Za-z0-9_:.-]+$","type":"string"} |
| source | 是 | {"$ref":"#/$defs/ActivityEmission"} |

## NodeEnterEvent

[完整巢狀Schema](assets/schemas/types/NodeEnterEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| payload | 否 | {"$ref":"#/$defs/NodeLifecyclePayload"} |
| seq | 是 | {"minimum":1,"type":"integer"} |
| ts | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| type | 是 | {"const":"node_enter","type":"string"} |

## NodeExecutionObservation

[完整巢狀Schema](assets/schemas/types/NodeExecutionObservation.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| error_message | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| memory_retrieval | 否 | {"anyOf":[{"$ref":"#/$defs/MemoryRetrievalObservation"},{"type":"null"}],"default":null} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| phase | 是 | {"$ref":"#/$defs/NodeExecutionPhase"} |
| review_gate | 否 | {"anyOf":[{"$ref":"#/$defs/ReviewGateResult"},{"type":"null"}],"default":null} |
| task_ref | 是 | {"minLength":1,"type":"string"} |

## NodeExitEvent

[完整巢狀Schema](assets/schemas/types/NodeExitEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| payload | 否 | {"$ref":"#/$defs/NodeLifecyclePayload"} |
| seq | 是 | {"minimum":1,"type":"integer"} |
| ts | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| type | 是 | {"const":"node_exit","type":"string"} |

## NodeLifecyclePayload

[完整巢狀Schema](assets/schemas/types/NodeLifecyclePayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| detail | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| review_gate | 否 | {"anyOf":[{"$ref":"#/$defs/ReviewGateResult"},{"type":"null"}],"default":null} |

## NodeSummary

[完整巢狀Schema](assets/schemas/types/NodeSummary.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| facts | 是 | {"$ref":"#/$defs/ActivityFacts"} |
| memory_retrieval | 否 | {"anyOf":[{"$ref":"#/$defs/MemoryRetrievalObservation"},{"type":"null"}],"default":null} |
| review_gate | 否 | {"anyOf":[{"$ref":"#/$defs/ReviewGateResult"},{"type":"null"}],"default":null} |
| type | 否 | {"const":"node_summary","default":"node_summary","type":"string"} |

## NonEmptyRefundScope

[完整巢狀Schema](assets/schemas/types/NonEmptyRefundScope.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| line_item_ids | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |

## OrderLineItem

[完整巢狀Schema](assets/schemas/types/OrderLineItem.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| category_ref | 是 | {"minLength":1,"type":"string"} |
| line_item_id | 是 | {"minLength":1,"type":"string"} |
| quantity | 是 | {"minimum":1,"type":"integer"} |
| refundable_amount | 是 | {"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"} |
| sku_ref | 是 | {"minLength":1,"type":"string"} |
| title | 是 | {"minLength":1,"type":"string"} |

## OrderSnapshot

[完整巢狀Schema](assets/schemas/types/OrderSnapshot.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| already_refunded_amount | 是 | {"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"} |
| captured_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| currency | 是 | {"maxLength":3,"minLength":3,"pattern":"^[A-Z]{3}$","type":"string"} |
| delivered_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| line_items | 是 | {"items":{"$ref":"#/$defs/OrderLineItem"},"minItems":1,"type":"array"} |
| order_ref | 是 | {"minLength":1,"type":"string"} |
| order_snapshot_ref | 是 | {"minLength":1,"type":"string"} |
| refundable_amount_max | 是 | {"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"} |
| snapshot_version | 是 | {"minimum":1,"type":"integer"} |

## PassedVerificationResult

[完整巢狀Schema](assets/schemas/types/PassedVerificationResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| issues | 否 | {"items":{"$ref":"#/$defs/VerificationIssue"},"maxItems":0,"type":"array"} |
| status | 是 | {"const":"PASS","type":"string"} |
| verification_version | 是 | {"minLength":1,"type":"string"} |

## PolicyBundle

[完整巢狀Schema](assets/schemas/types/PolicyBundle.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| clauses | 否 | {"items":{"$ref":"#/$defs/PolicyClause"},"type":"array"} |
| policy_bundle_version | 是 | {"minLength":1,"type":"string"} |
| retrieval_status | 是 | {"$ref":"#/$defs/RetrievalStatus"} |
| retrieved_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |

## PolicyClause

[完整巢狀Schema](assets/schemas/types/PolicyClause.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| allowed_actions | 是 | {"items":{"$ref":"#/$defs/ResolutionAction"},"minItems":1,"type":"array"} |
| applicable_conditions | 是 | {"$ref":"#/$defs/ApplicableConditions"} |
| clause_id | 是 | {"minLength":1,"type":"string"} |
| effective_from | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| effective_to | 否 | {"anyOf":[{"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"},{"type":"null"}],"default":null} |
| policy_version | 是 | {"minLength":1,"type":"string"} |
| required_claim_ids | 是 | {"items":{"$ref":"#/$defs/ClaimId"},"minItems":1,"type":"array"} |
| return_policy | 是 | {"$ref":"#/$defs/ReturnPolicy"} |
| text | 是 | {"minLength":1,"type":"string"} |

## PolicyDisplayRef

[完整巢狀Schema](assets/schemas/types/PolicyDisplayRef.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| clause_id | 是 | {"minLength":1,"type":"string"} |
| excerpt | 是 | {"minLength":1,"type":"string"} |
| policy_version | 是 | {"minLength":1,"type":"string"} |
| relevance | 否 | {"anyOf":[{"maximum":1,"minimum":0,"type":"number"},{"type":"null"}],"default":null} |
| title | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |

## PolicyReturnDecision

[完整巢狀Schema](assets/schemas/types/PolicyReturnDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| requirement | 是 | {"discriminator":{"mapping":{"False":"#/$defs/WaivedReturnRequirement","True":"#/$defs/RequiredReturnRequirement"},"propertyName":"required"},"oneOf":[{"$ref":"#/$defs/RequiredReturnRequirement"},{"$ref":"#/$defs/WaivedReturnRequirement"}]} |
| source | 是 | {"const":"POLICY","type":"string"} |

## PolicyReturnDecisionDraft

[完整巢狀Schema](assets/schemas/types/PolicyReturnDecisionDraft.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| reason_code | 是 | {"anyOf":[{"$ref":"#/$defs/RequiredReturnReasonCode"},{"$ref":"#/$defs/WaivedReturnReasonCode"}]} |
| source | 是 | {"const":"POLICY","type":"string"} |

## ProposedDecisionHandoff

[完整巢狀Schema](assets/schemas/types/ProposedDecisionHandoff.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| agent_prompt_version | 是 | {"minLength":1,"type":"string"} |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| claim_registry_version | 是 | {"minLength":1,"type":"string"} |
| evidence_bundle | 否 | {"items":{"$ref":"#/$defs/EvidenceItem"},"type":"array"} |
| handoff_id | 是 | {"minLength":1,"type":"string"} |
| handoff_version | 是 | {"const":"1.0","type":"string"} |
| order_snapshot_ref | 是 | {"minLength":1,"type":"string"} |
| policy_bundle_version | 是 | {"minLength":1,"type":"string"} |
| policy_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| proposed_decision | 是 | {"discriminator":{"mapping":{"DECLINE":"#/$defs/DeclineProposedDecision","FULL_REFUND":"#/$defs/FullRefundProposedDecision"},"propertyName":"action"},"oneOf":[{"$ref":"#/$defs/FullRefundProposedDecision"},{"$ref":"#/$defs/DeclineProposedDecision"}]} |
| rationale_summary | 是 | {"minLength":1,"type":"string"} |
| revision_round | 是 | {"minimum":0,"type":"integer"} |

## QueryApprovedMemoryParams

[完整巢狀Schema](assets/schemas/types/QueryApprovedMemoryParams.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| categories | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| claim_registry_major | 是 | {"minimum":1,"type":"integer"} |
| market | 是 | {"minLength":1,"type":"string"} |
| policy_versions | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| query_summary | 是 | {"maxLength":2000,"minLength":1,"type":"string"} |
| reason_code | 是 | {"$ref":"#/$defs/ReasonCode"} |
| required_claim_ids | 是 | {"items":{"$ref":"#/$defs/ClaimId"},"minItems":1,"type":"array"} |
| top_k | 否 | {"default":3,"maximum":3,"minimum":1,"type":"integer"} |

## QueryApprovedMemoryRequest

[完整巢狀Schema](assets/schemas/types/QueryApprovedMemoryRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| method | 是 | {"const":"OperationalMemoryStore.query_approved","type":"string"} |
| params | 是 | {"$ref":"#/$defs/QueryApprovedMemoryParams"} |

## QueryApprovedMemoryResponse

[完整巢狀Schema](assets/schemas/types/QueryApprovedMemoryResponse.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"items":{"$ref":"#/$defs/MemorySearchHit"},"maxItems":3,"type":"array"} |

## RefundScope

[完整巢狀Schema](assets/schemas/types/RefundScope.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| line_item_ids | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |

## RejectReviewDecision

[完整巢狀Schema](assets/schemas/types/RejectReviewDecision.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| decision | 是 | {"const":"REJECT","type":"string"} |
| generalizable | 否 | {"anyOf":[{"type":"boolean"},{"type":"null"}],"default":null} |
| handoff_id | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| review_note | 是 | {"minLength":1,"type":"string"} |
| reviewer_id | 否 | {"default":"demo_reviewer","minLength":1,"type":"string"} |

## RejectedHumanReviewResult

[完整巢狀Schema](assets/schemas/types/RejectedHumanReviewResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| decision | 是 | {"const":"REJECT","type":"string"} |
| final_resolution_ref | 是 | {"minLength":1,"type":"string"} |
| generalizable | 否 | {"anyOf":[{"type":"boolean"},{"type":"null"}],"default":null} |
| review_note | 是 | {"minLength":1,"type":"string"} |
| reviewed_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| reviewer_id | 否 | {"default":"demo_reviewer","minLength":1,"type":"string"} |

## RejectedRefundApplicationResult

[完整巢狀Schema](assets/schemas/types/RejectedRefundApplicationResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| reason_codes | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| rejected_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| status | 是 | {"const":"REJECTED","type":"string"} |

## RejectedRefundExecutionRecord

[完整巢狀Schema](assets/schemas/types/RejectedRefundExecutionRecord.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| application_result | 是 | {"$ref":"#/$defs/RejectedRefundApplicationResult"} |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| created_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| execution_ref | 是 | {"minLength":1,"type":"string"} |
| handoff_id | 是 | {"minLength":1,"type":"string"} |
| status | 是 | {"const":"REJECTED","type":"string"} |
| updated_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |

## RequiredReturnRequirement

[完整巢狀Schema](assets/schemas/types/RequiredReturnRequirement.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| reason_code | 是 | {"$ref":"#/$defs/RequiredReturnReasonCode"} |
| required | 是 | {"const":true,"type":"boolean"} |

## ResolutionAgentRunResult

[完整巢狀Schema](assets/schemas/types/ResolutionAgentRunResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| resolution_handoff | 是 | {"discriminator":{"mapping":{"HUMAN_APPROVE":"#/$defs/HumanApproveResolutionHandoff","HUMAN_EDIT":"#/$defs/HumanEditResolutionHandoff","HUMAN_REJECT":"#/$defs/HumanRejectResolutionHandoff","REVIEWER_APPROVE":"#/$defs/ReviewerApprovedResolutionHandoff"},"propertyName":"outcome_source"},"oneOf":[{"$ref":"#/$defs/ReviewerApprovedResolutionHandoff"},{"$ref":"#/$defs/HumanApproveResolutionHandoff"},{"$ref":"#/$defs/HumanEditResolutionHandoff"},{"$ref":"#/$defs/HumanRejectResolutionHandoff"}]} |
| result_type | 是 | {"const":"RESOLUTION","type":"string"} |
| status | 是 | {"const":"COMPLETED","type":"string"} |

## ResolveEvidenceParams

[完整巢狀Schema](assets/schemas/types/ResolveEvidenceParams.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| artifact_ref | 是 | {"minLength":1,"type":"string"} |

## ResolveEvidenceRequest

[完整巢狀Schema](assets/schemas/types/ResolveEvidenceRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| method | 是 | {"const":"EvidenceProvider.resolve","type":"string"} |
| params | 是 | {"$ref":"#/$defs/ResolveEvidenceParams"} |

## ResolveEvidenceResponse

[完整巢狀Schema](assets/schemas/types/ResolveEvidenceResponse.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"$ref":"#/$defs/EvidenceItem"} |

## ResolverConflictOutput

[完整巢狀Schema](assets/schemas/types/ResolverConflictOutput.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| conflict | 是 | {"$ref":"#/$defs/RevisionConflictReport"} |
| result_type | 是 | {"const":"CONFLICTING_REVISIONS","type":"string"} |

## ResolverDraftOutput

[完整巢狀Schema](assets/schemas/types/ResolverDraftOutput.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| draft | 是 | {"discriminator":{"mapping":{"DECLINE":"#/$defs/DeclineProposedDecisionDraft","FULL_REFUND":"#/$defs/FullRefundProposedDecisionDraft"},"propertyName":"action"},"oneOf":[{"$ref":"#/$defs/FullRefundProposedDecisionDraft"},{"$ref":"#/$defs/DeclineProposedDecisionDraft"}]} |
| result_type | 是 | {"const":"DRAFT","type":"string"} |

## ResolverEvidenceRequestOutput

[完整巢狀Schema](assets/schemas/types/ResolverEvidenceRequestOutput.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| evidence_request | 是 | {"$ref":"#/$defs/EvidenceRequest"} |
| result_type | 是 | {"const":"REQUEST_EVIDENCE","type":"string"} |

## RetrievePolicyParams

[完整巢狀Schema](assets/schemas/types/RetrievePolicyParams.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_context | 是 | {"$ref":"#/$defs/CaseContext"} |
| claimed_line_item_ids | 是 | {"items":{"minLength":1,"type":"string"},"minItems":1,"type":"array"} |
| order_snapshot | 是 | {"$ref":"#/$defs/OrderSnapshot"} |
| reason_code | 是 | {"$ref":"#/$defs/ReasonCode"} |

## RetrievePolicyRequest

[完整巢狀Schema](assets/schemas/types/RetrievePolicyRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| method | 是 | {"const":"PolicyProvider.retrieve_policy","type":"string"} |
| params | 是 | {"$ref":"#/$defs/RetrievePolicyParams"} |

## RetrievePolicyResponse

[完整巢狀Schema](assets/schemas/types/RetrievePolicyResponse.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"$ref":"#/$defs/PolicyBundle"} |

## ReviewGateResult

[完整巢狀Schema](assets/schemas/types/ReviewGateResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| amount | 是 | {"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"} |
| config_hash | 是 | {"pattern":"^[a-f0-9]{64}$","type":"string"} |
| config_version | 是 | {"minLength":1,"type":"string"} |
| currency | 是 | {"maxLength":3,"minLength":3,"pattern":"^[A-Z]{3}$","type":"string"} |
| reason | 是 | {"anyOf":[{"enum":["HIGH_VALUE_ITEM","CURRENCY_THRESHOLD_UNCONFIGURED"],"type":"string"},{"type":"null"}]} |
| status | 是 | {"enum":["PASS","HUMAN_REQUIRED","NOT_APPLICABLE"],"type":"string"} |
| threshold | 是 | {"anyOf":[{"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"},{"type":"null"}]} |

## ReviewerApprovedResolutionHandoff

[完整巢狀Schema](assets/schemas/types/ReviewerApprovedResolutionHandoff.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| emitted_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| execution_blocked | 是 | {"const":false,"type":"boolean"} |
| final_decision | 是 | {"discriminator":{"mapping":{"DECLINE":"#/$defs/DeclineFinalDecision","FULL_REFUND":"#/$defs/AgentFullRefundFinalDecision"},"propertyName":"action"},"oneOf":[{"$ref":"#/$defs/AgentFullRefundFinalDecision"},{"$ref":"#/$defs/DeclineFinalDecision"}]} |
| handoff_id | 是 | {"minLength":1,"type":"string"} |
| outcome_source | 是 | {"const":"REVIEWER_APPROVE","type":"string"} |
| review_gate | 否 | {"anyOf":[{"$ref":"#/$defs/ReviewGateResult"},{"type":"null"}],"default":null} |
| review_result | 是 | {"$ref":"#/$defs/ApprovedReviewResult"} |

## ReviewerGateConfig

[完整巢狀Schema](assets/schemas/types/ReviewerGateConfig.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| thresholds | 否 | {"patternProperties":{"^[A-Z]{3}$":{"pattern":"^(?:0&#124;[1-9]\\d*)(?:\\.\\d+)?$","type":"string"}},"propertyNames":{"maxLength":3,"minLength":3},"type":"object"} |
| version | 否 | {"default":"reviewer-gates:1.0","minLength":1,"type":"string"} |

## RevisedReviewResult

[完整巢狀Schema](assets/schemas/types/RevisedReviewResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| reviewed_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| reviewer_claim_findings | 是 | {"items":{"$ref":"#/$defs/ClaimFinding"},"minItems":1,"type":"array"} |
| reviewer_prompt_version | 是 | {"minLength":1,"type":"string"} |
| revision_reasons | 是 | {"items":{"$ref":"#/$defs/RevisionReason"},"minItems":1,"type":"array"} |
| verdict | 是 | {"const":"REVISE","type":"string"} |

## RevisionConflictReport

[完整巢狀Schema](assets/schemas/types/RevisionConflictReport.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| conflicting_reason_codes | 是 | {"items":{"$ref":"#/$defs/RevisionReasonCode"},"minItems":2,"type":"array"} |
| conflicting_review_refs | 是 | {"items":{"minLength":1,"type":"string"},"minItems":2,"type":"array"} |
| explanation | 是 | {"minLength":1,"type":"string"} |

## RevisionReason

[完整巢狀Schema](assets/schemas/types/RevisionReason.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| code | 是 | {"$ref":"#/$defs/RevisionReasonCode"} |
| evidence_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| message | 是 | {"minLength":1,"type":"string"} |
| policy_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| required_change | 是 | {"minLength":1,"type":"string"} |
| subject | 是 | {"minLength":1,"type":"string"} |

## SendMessageRequest

[完整巢狀Schema](assets/schemas/types/SendMessageRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| attached_artifact_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| message | 是 | {"minLength":1,"type":"string"} |

## StateChangeEvent

[完整巢狀Schema](assets/schemas/types/StateChangeEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| payload | 是 | {"$ref":"#/$defs/StateChangePayload"} |
| seq | 是 | {"minimum":1,"type":"integer"} |
| ts | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| type | 是 | {"const":"state_change","type":"string"} |

## StateChangePayload

[完整巢狀Schema](assets/schemas/types/StateChangePayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| from_status | 否 | {"anyOf":[{"$ref":"#/$defs/CaseStatus"},{"type":"null"}],"default":null} |
| reason | 是 | {"minLength":1,"type":"string"} |
| to_status | 是 | {"$ref":"#/$defs/CaseStatus"} |

## SubmitHumanReviewParams

[完整巢狀Schema](assets/schemas/types/SubmitHumanReviewParams.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| dossier | 否 | {"anyOf":[{"$ref":"#/$defs/HumanReviewDossier"},{"type":"null"}],"default":null} |
| handoff | 是 | {"$ref":"#/$defs/ProposedDecisionHandoff"} |
| review | 是 | {"discriminator":{"mapping":{"APPROVE":"#/$defs/ApprovedReviewResult","REVISE":"#/$defs/RevisedReviewResult"},"propertyName":"verdict"},"oneOf":[{"$ref":"#/$defs/ApprovedReviewResult"},{"$ref":"#/$defs/RevisedReviewResult"}]} |

## SubmitHumanReviewRequest

[完整巢狀Schema](assets/schemas/types/SubmitHumanReviewRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| method | 是 | {"const":"HumanReviewProvider.submit_for_review","type":"string"} |
| params | 是 | {"$ref":"#/$defs/SubmitHumanReviewParams"} |

## SubmitHumanReviewResponse

[完整巢狀Schema](assets/schemas/types/SubmitHumanReviewResponse.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"minLength":1,"type":"string"} |

## SubmitMemoryCandidateParams

[完整巢狀Schema](assets/schemas/types/SubmitMemoryCandidateParams.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| candidate | 是 | {"$ref":"#/$defs/MemoryCandidate"} |

## SubmitMemoryCandidateRequest

[完整巢狀Schema](assets/schemas/types/SubmitMemoryCandidateRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| method | 是 | {"const":"OperationalMemoryStore.submit_candidate","type":"string"} |
| params | 是 | {"$ref":"#/$defs/SubmitMemoryCandidateParams"} |

## SubmitMemoryCandidateResponse

[完整巢狀Schema](assets/schemas/types/SubmitMemoryCandidateResponse.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"minLength":1,"type":"string"} |

## SucceededRefundExecutionRecord

[完整巢狀Schema](assets/schemas/types/SucceededRefundExecutionRecord.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| application_result | 是 | {"$ref":"#/$defs/AppliedRefundApplicationResult"} |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| created_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| execution_ref | 是 | {"minLength":1,"type":"string"} |
| handoff_id | 是 | {"minLength":1,"type":"string"} |
| status | 是 | {"const":"SUCCEEDED","type":"string"} |
| updated_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |

## TokenEvent

[完整巢狀Schema](assets/schemas/types/TokenEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| payload | 是 | {"$ref":"#/$defs/TokenPayload"} |
| seq | 是 | {"minimum":1,"type":"integer"} |
| ts | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| type | 是 | {"const":"token","type":"string"} |

## TokenPayload

[完整巢狀Schema](assets/schemas/types/TokenPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| text | 是 | {"minLength":1,"type":"string"} |

## ToolCallEvent

[完整巢狀Schema](assets/schemas/types/ToolCallEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| payload | 是 | {"$ref":"#/$defs/ToolCallPayload"} |
| seq | 是 | {"minimum":1,"type":"integer"} |
| ts | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| type | 是 | {"const":"tool_call","type":"string"} |

## ToolCallPayload

[完整巢狀Schema](assets/schemas/types/ToolCallPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| arguments | 否 | {"additionalProperties":{"minLength":1,"type":"string"},"propertyNames":{"minLength":1},"type":"object"} |
| call_id | 是 | {"minLength":1,"type":"string"} |
| tool_name | 是 | {"minLength":1,"type":"string"} |

## ToolResultEvent

[完整巢狀Schema](assets/schemas/types/ToolResultEvent.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| case_ref | 是 | {"minLength":1,"type":"string"} |
| node | 是 | {"$ref":"#/$defs/GraphNodeName"} |
| payload | 是 | {"$ref":"#/$defs/ToolResultPayload"} |
| seq | 是 | {"minimum":1,"type":"integer"} |
| ts | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| type | 是 | {"const":"tool_result","type":"string"} |

## ToolResultPayload

[完整巢狀Schema](assets/schemas/types/ToolResultPayload.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| call_id | 是 | {"minLength":1,"type":"string"} |
| duration_ms | 是 | {"minimum":0,"type":"integer"} |
| error | 否 | {"anyOf":[{"minLength":1,"type":"string"},{"type":"null"}],"default":null} |
| ok | 是 | {"type":"boolean"} |
| summary | 是 | {"minLength":1,"type":"string"} |
| tool_name | 是 | {"minLength":1,"type":"string"} |

## UnavailableVerificationResult

[完整巢狀Schema](assets/schemas/types/UnavailableVerificationResult.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| issues | 否 | {"items":{"$ref":"#/$defs/VerificationIssue"},"maxItems":0,"type":"array"} |
| status | 是 | {"const":"UNAVAILABLE","type":"string"} |
| verification_version | 是 | {"minLength":1,"type":"string"} |

## UserTurn

[完整巢狀Schema](assets/schemas/types/UserTurn.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| attached_artifact_refs | 否 | {"items":{"minLength":1,"type":"string"},"type":"array"} |
| received_at | 是 | {"format":"date-time","pattern":"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z&#124;\\+00:00)$","type":"string"} |
| role | 是 | {"$ref":"#/$defs/UserRole"} |
| text | 是 | {"minLength":1,"type":"string"} |
| turn_id | 是 | {"minLength":1,"type":"string"} |

## VerificationIssue

[完整巢狀Schema](assets/schemas/types/VerificationIssue.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| code | 是 | {"minLength":1,"type":"string"} |
| field_path | 是 | {"minLength":1,"type":"string"} |
| message | 是 | {"minLength":1,"type":"string"} |

## VerifyHandoffParams

[完整巢狀Schema](assets/schemas/types/VerifyHandoffParams.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| handoff | 是 | {"$ref":"#/$defs/ProposedDecisionHandoff"} |

## VerifyHandoffRequest

[完整巢狀Schema](assets/schemas/types/VerifyHandoffRequest.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| method | 是 | {"const":"VerificationProvider.verify","type":"string"} |
| params | 是 | {"$ref":"#/$defs/VerifyHandoffParams"} |

## VerifyHandoffResponse

[完整巢狀Schema](assets/schemas/types/VerifyHandoffResponse.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| result | 是 | {"discriminator":{"mapping":{"FAIL":"#/$defs/FailedVerificationResult","PASS":"#/$defs/PassedVerificationResult","UNAVAILABLE":"#/$defs/UnavailableVerificationResult"},"propertyName":"status"},"oneOf":[{"$ref":"#/$defs/PassedVerificationResult"},{"$ref":"#/$defs/FailedVerificationResult"},{"$ref":"#/$defs/UnavailableVerificationResult"}]} |

## WaivedReturnRequirement

[完整巢狀Schema](assets/schemas/types/WaivedReturnRequirement.schema.json)

| 欄位 | 必填 | 形狀／限制 |
| --- | --- | --- |
| reason_code | 是 | {"$ref":"#/$defs/WaivedReturnReasonCode"} |
| required | 是 | {"const":false,"type":"boolean"} |

## DB activity_narration_outbox

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| source_event_id | VARCHAR(200) | False | True | case_activities.event_id | None / None |
| payload | JSON | False | False |  | None / None |
| dispatched | BOOLEAN | False | False |  | None / False |
| result_event_id | VARCHAR(200) | True | False |  | None / None |

## DB agent_command_outbox

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| command_id | VARCHAR(128) | False | True |  | None / None |
| payload | JSON | False | False |  | None / None |
| created_at | TIMESTAMP WITH TIME ZONE | False | False |  | now() / None |
| published_at | TIMESTAMP WITH TIME ZONE | True | False |  | None / None |
| claimed_by | VARCHAR(256) | True | False |  | None / None |
| claimed_until | TIMESTAMP WITH TIME ZONE | True | False |  | None / None |
| lease_token | VARCHAR(32) | True | False |  | None / None |
| attempt_count | INTEGER | False | False |  | 0 / 0 |
| last_error | TEXT | True | False |  | None / None |

## DB agent_event_projection_cursors

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| command_id | VARCHAR(128) | False | True |  | None / None |
| case_ref | VARCHAR(128) | False | False | cases.case_ref | None / None |
| last_event_index | INTEGER | False | False |  | None / None |
| terminated_at | TIMESTAMP WITH TIME ZONE | True | False |  | None / None |
| termination_event_id | VARCHAR(256) | True | False |  | None / None |
| updated_at | TIMESTAMP WITH TIME ZONE | False | False |  | now() / None |

## DB case_activities

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| event_id | VARCHAR(200) | False | True |  | None / None |
| case_ref | VARCHAR(128) | False | False | cases.case_ref | None / None |
| seq | INTEGER | False | False |  | None / None |
| payload | JSON | False | False |  | None / None |

## DB case_events

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| id | INTEGER | False | True |  | None / None |
| case_ref | VARCHAR(128) | False | False | cases.case_ref | None / None |
| seq | INTEGER | False | False |  | None / None |
| kind | VARCHAR(16) | False | False |  | None / None |
| payload | JSON | False | False |  | None / None |
| created_at | TIMESTAMP WITH TIME ZONE | False | False |  | now() / None |

## DB cases

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| case_ref | VARCHAR(128) | False | True |  | None / None |
| thread_id | VARCHAR(128) | False | False |  | None / None |
| order_ref | VARCHAR(128) | False | False |  | None / None |
| user_ref | VARCHAR(128) | False | False |  | None / None |
| status | VARCHAR(32) | False | False |  | None / None |
| created_at | TIMESTAMP WITH TIME ZONE | False | False |  | now() / None |
| updated_at | TIMESTAMP WITH TIME ZONE | False | False |  | now() / None |

## DB evidence_items

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| evidence_id | VARCHAR(128) | False | True |  | None / None |
| type | VARCHAR(16) | False | False |  | None / None |
| source | VARCHAR(32) | False | False |  | None / None |
| subject | VARCHAR(128) | False | False |  | None / None |
| artifact_ref | VARCHAR(512) | False | False |  | None / None |
| extracted_summary | TEXT | False | False |  | None / None |
| collected_at | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |
| created_at | TIMESTAMP WITH TIME ZONE | False | False |  | now() / None |
| content_hash | VARCHAR(64) | False | False |  | None / None |

## DB handoff_verifications

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| verification_id | VARCHAR(128) | False | True |  | None / None |
| handoff_id | VARCHAR(256) | False | False |  | None / None |
| payload_hash | VARCHAR(64) | False | False |  | None / None |
| handoff_payload | JSON | False | False |  | None / None |
| result_payload | JSON | False | False |  | None / None |
| verification_status | VARCHAR(16) | False | False |  | None / None |
| verification_version | VARCHAR(128) | False | False |  | None / None |
| created_at | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |
| updated_at | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |

## DB human_reviews

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| review_ref | VARCHAR(256) | False | True |  | None / None |
| handoff_id | VARCHAR(256) | False | False |  | None / None |
| case_ref | VARCHAR(128) | False | False |  | None / None |
| payload_hash | VARCHAR(64) | False | False |  | None / None |
| handoff_payload | JSON | False | False |  | None / None |
| review_payload | JSON | True | False |  | None / None |
| dossier_payload | JSON | True | False |  | None / None |
| result_payload | JSON | True | False |  | None / None |
| submitted_at | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |
| reviewed_at | TIMESTAMP WITH TIME ZONE | True | False |  | None / None |

## DB memory_job_results

owner: agent-memory。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| job_id | VARCHAR(256) | False | True |  | None / None |
| input_hash | VARCHAR(64) | False | False |  | None / None |
| prompt_version | VARCHAR(256) | False | False |  | None / None |
| result | JSON | True | False |  | None / None |
| terminal_event | JSON | True | False |  | None / None |

## DB operational_memories

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| memory_id | VARCHAR(128) | False | True |  | None / None |
| submission_ref | VARCHAR(256) | False | False |  | None / None |
| candidate_payload_hash | VARCHAR(64) | False | False |  | None / None |
| retrieval_summary | TEXT | True | False |  | None / None |
| summary_version | VARCHAR(64) | True | False |  | None / None |
| summary_hash | VARCHAR(64) | True | False |  | None / None |
| embedding_model | VARCHAR(128) | True | False |  | None / None |
| embedding | VECTOR(1536) | True | False |  | None / None |
| trigger_conditions | JSON | False | False |  | None / None |
| recommended_behavior | TEXT | False | False |  | None / None |
| rationale | TEXT | False | False |  | None / None |
| source_case_refs | JSON | False | False |  | None / None |
| source_revision_event_refs | JSON | False | False |  | None / None |
| policy_version | VARCHAR(256) | False | False |  | None / None |
| claim_registry_version | VARCHAR(128) | False | False |  | None / None |
| scope_market | VARCHAR(64) | False | False |  | None / None |
| scope_reason_codes | VARCHAR[] | False | False |  | None / None |
| scope_claim_ids | VARCHAR[] | False | False |  | None / None |
| scope_categories | VARCHAR[] | False | False |  | None / None |
| confidence | FLOAT | False | False |  | None / None |
| status | VARCHAR(16) | False | False |  | None / None |
| submitted_at | TIMESTAMP WITH TIME ZONE | False | False |  | now() / None |
| approved_at | TIMESTAMP WITH TIME ZONE | True | False |  | None / None |
| retired_at | TIMESTAMP WITH TIME ZONE | True | False |  | None / None |

## DB operational_memory_events

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| event_id | VARCHAR(128) | False | True |  | None / None |
| memory_id | VARCHAR(128) | False | False | operational_memories.memory_id | None / None |
| event_type | VARCHAR(16) | False | False |  | None / None |
| from_status | VARCHAR(16) | False | False |  | None / None |
| to_status | VARCHAR(16) | False | False |  | None / None |
| occurred_at | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |

## DB policy_clauses

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| clause_id | VARCHAR(256) | False | True |  | None / None |
| document_id | VARCHAR(128) | False | False | policy_documents.document_id | None / None |
| policy_version | VARCHAR(256) | False | False |  | None / None |
| effective_from | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |
| effective_to | TIMESTAMP WITH TIME ZONE | True | False |  | None / None |
| markets | VARCHAR[] | False | False |  | None / None |
| reason_codes | VARCHAR[] | False | False |  | None / None |
| categories | VARCHAR[] | False | False |  | None / None |
| required_claim_ids | VARCHAR[] | False | False |  | None / None |
| allowed_actions | VARCHAR[] | False | False |  | None / None |
| return_policy | VARCHAR(32) | False | False |  | None / None |
| clause_text | TEXT | False | False |  | None / None |
| embedding_model | VARCHAR(128) | False | False |  | None / None |
| embedding | VECTOR(1536) | False | False |  | None / None |

## DB policy_documents

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| document_id | VARCHAR(128) | False | True |  | None / None |
| policy_family | VARCHAR(128) | False | False |  | None / None |
| version | VARCHAR(128) | False | False |  | None / None |
| source_ref | VARCHAR(512) | False | False |  | None / None |
| checksum | VARCHAR(64) | False | False |  | None / None |
| is_active | BOOLEAN | False | False |  | None / True |
| ingested_at | TIMESTAMP WITH TIME ZONE | False | False |  | now() / None |

## DB policy_retrievals

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| retrieval_id | VARCHAR(128) | False | True |  | None / None |
| request_hash | VARCHAR(64) | False | False |  | None / None |
| bundle_version | VARCHAR(128) | False | False |  | None / None |
| retrieval_status | VARCHAR(32) | False | False |  | None / None |
| bundle_payload | JSON | False | False |  | None / None |
| retrieved_at | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |

## DB processed_agent_events

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| event_id | VARCHAR(256) | False | True |  | None / None |
| case_ref | VARCHAR(128) | False | False | cases.case_ref | None / None |
| command_id | VARCHAR(128) | False | False |  | None / None |
| event_index | INTEGER | False | False |  | None / None |
| payload_hash | VARCHAR(64) | False | False |  | None / None |
| processed_at | TIMESTAMP WITH TIME ZONE | False | False |  | now() / None |

## DB refund_execution_items

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| execution_ref | VARCHAR(128) | False | True | refund_executions.execution_ref | None / None |
| line_item_ref | VARCHAR(128) | False | True |  | None / None |
| order_ref | VARCHAR(128) | False | False |  | None / None |
| applied_at | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |

## DB refund_executions

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| execution_ref | VARCHAR(128) | False | True |  | None / None |
| handoff_id | VARCHAR(256) | False | False |  | None / None |
| case_ref | VARCHAR(128) | False | False |  | None / None |
| payload_hash | VARCHAR(64) | False | False |  | None / None |
| request_payload | JSON | False | False |  | None / None |
| order_ref | VARCHAR(128) | True | False |  | None / None |
| application_result_payload | JSON | True | False |  | None / None |
| state | VARCHAR(16) | False | False |  | None / None |
| created_at | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |
| application_started_at | TIMESTAMP WITH TIME ZONE | True | False |  | None / None |
| completed_at | TIMESTAMP WITH TIME ZONE | True | False |  | None / None |
| updated_at | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |

## DB refund_item_reservations

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| order_ref | VARCHAR(128) | False | True |  | None / None |
| line_item_ref | VARCHAR(128) | False | True |  | None / None |
| execution_ref | VARCHAR(128) | False | False | refund_executions.execution_ref | None / None |
| reserved_at | TIMESTAMP WITH TIME ZONE | False | False |  | None / None |

## DB rejected_agent_events

owner: api。完整check/unique/index見assets/db中的SQL與dictionary.json。

| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |
| --- | --- | --- | --- | --- | --- |
| source_message_id | VARCHAR(128) | False | True |  | None / None |
| event_id | VARCHAR(256) | True | False |  | None / None |
| case_ref | VARCHAR(128) | True | False |  | None / None |
| raw_body | TEXT | False | False |  | None / None |
| error_code | VARCHAR(64) | False | False |  | None / None |
| error_message | TEXT | False | False |  | None / None |
| rejected_at | TIMESTAMP WITH TIME ZONE | False | False |  | now() / None |
