"""Explicit deterministic model profile for local integration and CI."""
from collections import defaultdict, deque
from typing import Any

from pydantic import TypeAdapter

from return_agent_contracts.registry import REGISTRY_VERSION


class TypedFakeModel:
    def __init__(self, *, scripted: dict[str, list[Any]] | None = None):
        self.scripted = {key: list(values) for key, values in (scripted or {}).items()}
        self.calls = deque(maxlen=1024)
        self.counts = defaultdict(int)

    def generate(self, task: str, payload: dict[str, Any], output_type: Any):
        self.calls.append((task, payload))
        self.counts[task] += 1
        if self.scripted.get(task):
            result = self.scripted[task].pop(0)
            if isinstance(result, Exception):
                raise result
            if callable(result):
                result = result(payload)
        else:
            result = self.default(task, payload)
        return TypeAdapter(output_type).validate_python(result)

    def findings(self, payload):
        evidence = payload.get("evidence_bundle", payload.get("proposed_decision_handoff", {}).get("evidence_bundle", []))
        findings = []
        for pair in payload["expected_claim_subject_pairs"]:
            refs = [item["evidence_id"] for item in evidence if item["subject"] == pair["subject"]]
            if pair["claim_id"] == "DAMAGE_PRESENT_ON_ARRIVAL":
                refs = [item["evidence_id"] for item in evidence if item["subject"] == pair["subject"] and "連續拆封" in item["extracted_summary"]]
            system = pair["claim_id"] in ("DELIVERY_CONFIRMED", "ORDER_WITHIN_RETURN_WINDOW")
            findings.append({**pair, "status": "SUPPORTED" if system or refs else "UNSUPPORTED", "explanation": "合成測試：依可信日期與指定 metadata 檢查。", "supporting_evidence_refs": [] if system else refs})
        return findings

    def default(self, task, payload):
        if task == "INTAKE":
            return {"completeness": "COMPLETE", "requested_action": "REFUND", "order_ref": payload["trusted_order_ref"], "reason_code": "ITEM_DAMAGED", "reason_summary": "申請退回有外觀損壞的音訊商品。", "claimed_line_item_ids": [item["line_item_id"] for item in payload["order_line_items"] or []]}
        if task == "MEMORY_QUERY_SUMMARY":
            return {"query_summary": "音訊商品外觀損壞，需逐項確認損壞與退回檢測必要性。"}
        if task == "ASSESS":
            findings = self.findings(payload)
            missing = [{"claim_id": f["claim_id"], "subject": f["subject"]} for f in findings if f["status"] == "UNSUPPORTED"]
            result = {"claim_registry_version": REGISTRY_VERSION, "claim_findings": findings, "evidence_status": "INSUFFICIENT" if missing else "SUFFICIENT_FOR_APPROVAL"}
            if missing:
                claims = {item["claim_id"] for item in missing}
                types = sorted({kind for entry in payload["claim_registry"] if entry["claim_id"] in claims for kind in entry["accepted_evidence_types"]})
                result["missing_evidence_request"] = {"request_id": "fake-evidence-request", "missing_claims": missing, "accepted_evidence_types": types, "policy_refs": [c["clause_id"] for c in payload["policy_bundle"]["clauses"]], "user_message": "請補充顯示品項外觀損壞的照片或影片。"}
            return result
        if task == "PROPOSE_OR_REVISE":
            fixed = {c["return_policy"] for c in payload["policy_bundle"]["clauses"]} - {"MODEL_JUDGMENT"}
            return_decision = {"source": "MODEL_JUDGMENT", "requirement": {"required": True, "reason_code": "RETURN_REQUIRED_FOR_INSPECTION"}}
            if fixed:
                required = "REQUIRED" in fixed
                return_decision = {"source": "POLICY", "reason_code": "RETURN_REQUIRED_FOR_INSPECTION" if required else "EVIDENCE_SUFFICIENT_WITHOUT_RETURN"}
            feedback = payload.get("review_feedback")
            rationale = "依指定 metadata 與政策逐項評估退款及退回需求。"
            if feedback:
                rationale += "修正：" + "；".join(r["required_change"] for r in feedback["revision_reasons"])
            return {"result_type": "DRAFT", "draft": {"action": "FULL_REFUND", "reason_code": payload["normalized_intent"]["reason_code"], "policy_refs": [c["clause_id"] for c in payload["policy_bundle"]["clauses"]], "evidence_refs": [e["evidence_id"] for e in payload["evidence_bundle"]], "refund_scope": {"line_item_ids": payload["claimed_line_item_ids"]}, "return_decision": return_decision, "rationale_summary": rationale}}
        if task == "REVIEW":
            return {"verdict": "APPROVE", "reviewed_at": payload["reviewed_at_utc"], "reviewer_prompt_version": "reviewer:2.1", "reviewer_claim_findings": self.findings(payload)}
        if task == "ACTIVITY_NARRATION":
            raise ValueError("Narration is disabled in the offline profile")
        raise ValueError("Fake task has not been configured")
