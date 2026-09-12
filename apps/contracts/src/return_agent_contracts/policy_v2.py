"""Fixed Policy v2 paths and deterministic, source-bound eligibility evaluation.

Eligibility never grants payment authority. Consent, gates and fulfillment are
validated separately. No condition strings are executed.
"""
from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
import json
from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from .base import ContractModel, NonNegativeInt, OpaqueRef, PositiveInt, UTCDateTime
from .enums import ClaimId, ClaimStatus, ReasonCode, RequestedAction, ReturnPolicy

if TYPE_CHECKING:
    from .models import CaseContext, ClaimFinding, EvidenceItem, OrderSnapshot, PolicyBundle

POLICY_V2_VERSION = "DEMO-TW-RETURNS:v2.0"
REGISTRY_V2_VERSION = "claim-registry:2.0"
EVALUATOR_VERSION = "policy-evaluator:2.0"


def active_clauses(bundle: PolicyBundle):
    if bundle.schema_version == "v1":
        return bundle.clauses
    return [c for c in bundle.clauses if c.path_id is bundle.selected_path_id]


def content_hash(value: object) -> str:
    """Hash JSON wire values, never process-dependent reprs."""
    from pydantic import TypeAdapter
    data = TypeAdapter(object).dump_python(value, mode="json")
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class PolicyPathId(StrEnum):
    COOLING_OFF = "COOLING_OFF"
    DAMAGED_ON_ARRIVAL = "DAMAGED_ON_ARRIVAL"
    WRONG_ITEM = "WRONG_ITEM"
    UNDELIVERED_ITEM = "UNDELIVERED_ITEM"


class SystemPredicate(StrEnum):
    TRANSACTION_IN_SCOPE = "TRANSACTION_IN_SCOPE"
    SINGLE_REFUNDABLE_ITEM = "SINGLE_REFUNDABLE_ITEM"
    NO_EXCEPTION_ESTABLISHED = "NO_EXCEPTION_ESTABLISHED"
    WITHIN_PATH_WINDOW = "WITHIN_PATH_WINDOW"
    RECEIPT_CONFIRMED = "RECEIPT_CONFIRMED"
    PURCHASE_SPEC_AVAILABLE = "PURCHASE_SPEC_AVAILABLE"
    NONDELIVERY_CONFIRMED = "NONDELIVERY_CONFIRMED"
    NO_PENDING_SPLIT_DELIVERY = "NO_PENDING_SPLIT_DELIVERY"
    PAYMENT_SCOPE_AVAILABLE = "PAYMENT_SCOPE_AVAILABLE"


class RefundReleaseCondition(StrEnum):
    RETURN_INSPECTION_PASSED = "RETURN_INSPECTION_PASSED"
    AUTHORIZED_NO_RETURN = "AUTHORIZED_NO_RETURN"


class PathDeadline(ContractModel):
    policy_path_id: PolicyPathId
    deadline_at: UTCDateTime
    timezone: Literal["Asia/Taipei"] = "Asia/Taipei"
    rule_source_ref: OpaqueRef
    rule_source_version: OpaqueRef


class ItemPolicyFacts(ContractModel):
    line_item_id: OpaqueRef
    source_ref: OpaqueRef
    transaction_version: OpaqueRef | None = None
    purchased_spec: dict[str, str] = Field(default_factory=dict)
    delivery_status: Literal["RECEIVED", "CONFIRMED_UNDELIVERED", "IN_TRANSIT", "UNKNOWN"] = "UNKNOWN"
    received_at: UTCDateTime | None = None
    shipment_refs: list[OpaqueRef] = Field(default_factory=list)
    investigation_ref: OpaqueRef | None = None
    pending_split_delivery: bool | None = None
    returnable_quantity: NonNegativeInt | None = None
    exception: Literal["NONE_CONFIRMED", "ESTABLISHED", "UNKNOWN", "DISPUTED"] = "UNKNOWN"
    exception_source_ref: OpaqueRef | None = None
    is_bundle: bool | None = None
    cancelled: bool | None = None
    refunded: bool | None = None
    reservation_case_ref: OpaqueRef | None = None
    deadlines: list[PathDeadline] = Field(default_factory=list)
    waiver_basis_refs: list[OpaqueRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique(self):
        if len({d.policy_path_id for d in self.deadlines}) != len(self.deadlines):
            raise ValueError("duplicate path deadline")
        return self


class OrderPolicyFacts(ContractModel):
    platform: Literal["SHOPEE_TW", "OTHER", "UNKNOWN"] = "UNKNOWN"
    seller_type: Literal["BUSINESS", "MALL", "PERSONAL", "UNKNOWN"] = "UNKNOWN"
    product_type: Literal["GENERAL_PHYSICAL", "SPECIAL", "UNKNOWN"] = "UNKNOWN"
    cross_border: bool | None = None
    source_ref: OpaqueRef
    items: list[ItemPolicyFacts]

    @model_validator(mode="after")
    def _unique(self):
        if len({item.line_item_id for item in self.items}) != len(self.items):
            raise ValueError("duplicate item facts")
        return self


PATH_CLAIMS = {
    PolicyPathId.COOLING_OFF: (),
    PolicyPathId.DAMAGED_ON_ARRIVAL: (ClaimId.ITEM_PHYSICALLY_DAMAGED, ClaimId.DAMAGE_PRESENT_ON_ARRIVAL),
    PolicyPathId.WRONG_ITEM: (ClaimId.WRONG_ITEM_RECEIVED,),
    PolicyPathId.UNDELIVERED_ITEM: (ClaimId.ITEM_CONFIRMED_UNDELIVERED,),
}
COMMON_PREDICATES = (SystemPredicate.TRANSACTION_IN_SCOPE, SystemPredicate.SINGLE_REFUNDABLE_ITEM,
    SystemPredicate.NO_EXCEPTION_ESTABLISHED, SystemPredicate.WITHIN_PATH_WINDOW, SystemPredicate.PAYMENT_SCOPE_AVAILABLE)
PATH_PREDICATES = {
    PolicyPathId.COOLING_OFF: (*COMMON_PREDICATES, SystemPredicate.RECEIPT_CONFIRMED),
    PolicyPathId.DAMAGED_ON_ARRIVAL: COMMON_PREDICATES,
    PolicyPathId.WRONG_ITEM: (*COMMON_PREDICATES, SystemPredicate.PURCHASE_SPEC_AVAILABLE),
    PolicyPathId.UNDELIVERED_ITEM: (*COMMON_PREDICATES, SystemPredicate.NONDELIVERY_CONFIRMED, SystemPredicate.NO_PENDING_SPLIT_DELIVERY),
}
REASON_PATH = {ReasonCode.CHANGED_MIND: PolicyPathId.COOLING_OFF, ReasonCode.ITEM_DAMAGED: PolicyPathId.DAMAGED_ON_ARRIVAL,
    ReasonCode.WRONG_ITEM: PolicyPathId.WRONG_ITEM, ReasonCode.MISSING_ITEM: PolicyPathId.UNDELIVERED_ITEM}


class PolicyPath(ContractModel):
    path_id: PolicyPathId
    policy_version: Literal["DEMO-TW-RETURNS:v2.0"] = POLICY_V2_VERSION
    clause_refs: list[OpaqueRef] = Field(min_length=1)
    required_claim_ids: list[ClaimId]
    system_predicates: list[SystemPredicate]
    entry_reasons: list[ReasonCode] = Field(min_length=1)
    return_policy: ReturnPolicy
    effective_from: UTCDateTime
    effective_to: UTCDateTime | None = None
    source_refs: list[OpaqueRef] = Field(min_length=1)
    interpretation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _fixed_logic(self):
        if self.required_claim_ids != list(PATH_CLAIMS[self.path_id]) or self.system_predicates != list(PATH_PREDICATES[self.path_id]):
            raise ValueError("v2 paths must retain their fixed claims and predicates")
        expected = ReturnPolicy.MODEL_JUDGMENT if self.path_id is PolicyPathId.DAMAGED_ON_ARRIVAL else ReturnPolicy.NOT_REQUIRED if self.path_id is PolicyPathId.UNDELIVERED_ITEM else ReturnPolicy.REQUIRED
        if self.return_policy is not expected:
            raise ValueError("path return policy conflicts with v2")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("invalid policy effective interval")
        return self


class PolicySelection(ContractModel):
    selected_path_id: PolicyPathId
    selection_version: PositiveInt
    original_requested_action: RequestedAction
    confirmation_ref: OpaqueRef | None = None


class PolicyConfirmationRequest(ContractModel):
    request_ref: OpaqueRef
    case_ref: OpaqueRef
    original_scope_hash: str
    original_path_id: PolicyPathId
    path_id: PolicyPathId
    selection_version: PositiveInt
    return_required: bool
    return_requirement_hash: str


def policy_confirmation_request_ref(request: PolicyConfirmationRequest | dict[str, object], bundle: PolicyBundle) -> str:
    """Bind consent to exact rules, independent of retrieval time and selection.

    A path switch retrieves the same complete package under a new retrieval
    reference. Only that reference, retrieval time and selected path are omitted;
    every rule, clause, interpretation and source remains in the digest.
    """
    if bundle.schema_version != "v2" or bundle.retrieval_status != "OK":
        raise ValueError("policy confirmation requires an explicit v2 package")
    payload = request.model_dump(mode="json", exclude={"request_ref"}) if isinstance(request, PolicyConfirmationRequest) else dict(request)
    payload.pop("request_ref", None)
    package = bundle.model_dump(mode="json", exclude={"retrieved_at", "policy_bundle_version", "selected_path_id"})
    package["clauses"] = sorted(package["clauses"], key=lambda clause: clause["clause_id"])
    package["paths"] = sorted(package["paths"], key=lambda path: path["path_id"])
    return f"policy-confirmation:{content_hash(dict(request=payload, policy_version=POLICY_V2_VERSION, claim_registry_version=REGISTRY_V2_VERSION, package=package))}"


def validate_policy_confirmation_request(request: PolicyConfirmationRequest, bundle: PolicyBundle) -> None:
    if request.request_ref != policy_confirmation_request_ref(request, bundle):
        raise ValueError("policy confirmation is not bound to the current versioned rule package")


class PolicyConfirmation(ContractModel):
    confirmation_ref: OpaqueRef
    request: PolicyConfirmationRequest
    accepted: bool
    confirmed_at: UTCDateTime


class PredicateFinding(ContractModel):
    predicate: SystemPredicate
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    source_ref: OpaqueRef | None


class ItemPolicyEvaluation(ContractModel):
    line_item_id: OpaqueRef
    path_id: PolicyPathId
    status: Literal["ELIGIBLE", "INELIGIBLE", "NEEDS_INFORMATION", "SPECIALIST_REQUIRED"]
    predicates: list[PredicateFinding]
    clause_refs: list[OpaqueRef]
    claim_refs: list[ClaimId]
    reason_codes: list[OpaqueRef]


class PolicyEvaluation(ContractModel):
    evaluation_ref: OpaqueRef
    evaluator_version: Literal["policy-evaluator:2.0"] = EVALUATOR_VERSION
    evaluation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    case_ref: OpaqueRef
    order_snapshot_ref: OpaqueRef
    policy_bundle_version: OpaqueRef
    claim_registry_version: Literal["claim-registry:2.0"] = REGISTRY_V2_VERSION
    evidence_bundle_hash: str
    findings_ref: OpaqueRef
    item_evaluations: list[ItemPolicyEvaluation] = Field(min_length=1)
    selection: PolicySelection
    evaluated_at: UTCDateTime

    @model_validator(mode="after")
    def _hash(self):
        payload = self.model_dump(mode="json", exclude={"evaluation_ref", "evaluation_hash"})
        if self.evaluation_hash != content_hash(payload) or self.evaluation_ref != f"evaluation:{self.evaluation_hash}":
            raise ValueError("policy evaluation content binding is invalid")
        pairs = [(item.line_item_id, item.path_id) for item in self.item_evaluations]
        if len(set(pairs)) != len(pairs):
            raise ValueError("duplicate evaluated path")
        return self


def _predicate_values(context: CaseContext, order: OrderSnapshot, item_id: str, path: PolicyPathId, scope: list[str]) -> dict[SystemPredicate, PredicateFinding]:
    facts = order.policy_facts
    item = next((x for x in order.line_items if x.line_item_id == item_id), None)
    details = next((x for x in facts.items if x.line_item_id == item_id), None) if facts else None
    deadline = next((d for d in details.deadlines if d.policy_path_id is path), None) if details else None
    def found(predicate, value, source=None):
        return PredicateFinding(predicate=predicate, status="UNKNOWN" if value is None else "PASS" if value else "FAIL", source_ref=source)
    source = details.source_ref if details else None
    values = {
        SystemPredicate.TRANSACTION_IN_SCOPE: found(SystemPredicate.TRANSACTION_IN_SCOPE, None if facts is None else facts.platform == "SHOPEE_TW" and facts.seller_type in {"BUSINESS", "MALL"} and facts.product_type == "GENERAL_PHYSICAL" and facts.cross_border is False and context.market == "TW" and order.currency == "TWD", facts.source_ref if facts else None),
        SystemPredicate.SINGLE_REFUNDABLE_ITEM: found(SystemPredicate.SINGLE_REFUNDABLE_ITEM, None if details is None or item is None else len(scope) == 1 and item.quantity == 1 and details.returnable_quantity == 1 and details.is_bundle is False, source),
        SystemPredicate.NO_EXCEPTION_ESTABLISHED: found(SystemPredicate.NO_EXCEPTION_ESTABLISHED, None if details is None or not details.exception_source_ref or details.exception == "UNKNOWN" else details.exception == "NONE_CONFIRMED", details.exception_source_ref if details else None),
        SystemPredicate.WITHIN_PATH_WINDOW: found(SystemPredicate.WITHIN_PATH_WINDOW, None if deadline is None or context.first_valid_submitted_at is None else context.first_valid_submitted_at <= deadline.deadline_at, deadline.rule_source_ref if deadline else None),
        SystemPredicate.PAYMENT_SCOPE_AVAILABLE: found(SystemPredicate.PAYMENT_SCOPE_AVAILABLE, None if details is None or item is None or details.cancelled is None or details.refunded is None else not details.cancelled and not details.refunded and details.reservation_case_ref in {None, context.case_ref} and item.refundable_amount > 0 and item.refundable_amount <= order.refundable_amount_max, source),
        SystemPredicate.RECEIPT_CONFIRMED: found(SystemPredicate.RECEIPT_CONFIRMED, None if details is None or details.delivery_status == "UNKNOWN" else details.delivery_status == "RECEIVED" and details.received_at is not None and bool(details.shipment_refs), source),
        SystemPredicate.PURCHASE_SPEC_AVAILABLE: found(SystemPredicate.PURCHASE_SPEC_AVAILABLE, None if details is None else bool(details.transaction_version and details.purchased_spec.get("sku") and details.purchased_spec.get("specification")), source),
        SystemPredicate.NONDELIVERY_CONFIRMED: found(SystemPredicate.NONDELIVERY_CONFIRMED, None if details is None or details.delivery_status == "UNKNOWN" else details.delivery_status == "CONFIRMED_UNDELIVERED" and details.investigation_ref is not None, details.investigation_ref if details else None),
        SystemPredicate.NO_PENDING_SPLIT_DELIVERY: found(SystemPredicate.NO_PENDING_SPLIT_DELIVERY, None if details is None or details.pending_split_delivery is None else not details.pending_split_delivery, source),
    }
    return values


def evaluate_policy(*, context: CaseContext, order: OrderSnapshot, bundle: PolicyBundle,
    claimed_line_item_ids: list[str], findings: list[ClaimFinding], evidence: list[EvidenceItem],
    selection: PolicySelection, evaluated_at: UTCDateTime) -> PolicyEvaluation:
    if context.policy_schema_version != "v2" or bundle.schema_version != "v2" or not claimed_line_item_ids or len(set(claimed_line_item_ids)) != len(claimed_line_item_ids):
        raise ValueError("v2 evaluation requires explicit v2 inputs and unique scope")
    if context.order_ref != order.order_ref or not set(claimed_line_item_ids).issubset(x.line_item_id for x in order.line_items):
        raise ValueError("policy evaluation order or scope mismatch")
    by_pair = {(f.claim_id, f.subject): f for f in findings}
    if len(by_pair) != len(findings):
        raise ValueError("duplicate claim findings")
    evidence_refs = {e.evidence_id for e in evidence}
    outcomes = []
    for item_id in claimed_line_item_ids:
        for path in bundle.paths:
            values = _predicate_values(context, order, item_id, path.path_id, claimed_line_item_ids)
            predicates = [values[p] for p in path.system_predicates]
            failures = [p.predicate.value for p in predicates if p.status != "PASS"]
            instant = context.first_valid_submitted_at
            if instant is None or instant < path.effective_from or (path.effective_to is not None and instant > path.effective_to):
                failures.append("PATH_NOT_EFFECTIVE")
            status = "ELIGIBLE"
            if failures:
                status = "INELIGIBLE" if failures == ["WITHIN_PATH_WINDOW"] and values[SystemPredicate.WITHIN_PATH_WINDOW].status == "FAIL" and path.path_id is PolicyPathId.COOLING_OFF else "SPECIALIST_REQUIRED"
            else:
                statuses = []
                for claim in path.required_claim_ids:
                    finding = by_pair.get((claim, item_id))
                    if claim is ClaimId.ITEM_CONFIRMED_UNDELIVERED:
                        expected_ref = values[SystemPredicate.NONDELIVERY_CONFIRMED].source_ref
                        if finding is not None and (finding.status is not ClaimStatus.SUPPORTED or expected_ref not in finding.supporting_evidence_refs):
                            raise ValueError("system-only finding contradicts trusted delivery facts")
                        statuses.append(ClaimStatus.SUPPORTED)
                    else:
                        if finding and finding.status is not ClaimStatus.UNSUPPORTED and (not finding.supporting_evidence_refs or not set(finding.supporting_evidence_refs).issubset(evidence_refs)):
                            raise ValueError("claim requires cited evidence in the bound bundle")
                        statuses.append(finding.status if finding else ClaimStatus.UNSUPPORTED)
                if ClaimStatus.CONTRADICTED in statuses:
                    status, failures = "INELIGIBLE", ["CLAIM_CONTRADICTED"]
                elif ClaimStatus.UNSUPPORTED in statuses:
                    status, failures = "NEEDS_INFORMATION", ["USER_EVIDENCE_REQUIRED"]
            outcomes.append(ItemPolicyEvaluation(line_item_id=item_id, path_id=path.path_id, status=status,
                predicates=predicates, clause_refs=path.clause_refs, claim_refs=path.required_claim_ids, reason_codes=failures))
    payload = dict(evaluator_version=EVALUATOR_VERSION, case_ref=context.case_ref, order_snapshot_ref=order.order_snapshot_ref,
        policy_bundle_version=bundle.policy_bundle_version, claim_registry_version=REGISTRY_V2_VERSION,
        evidence_bundle_hash=content_hash(evidence), findings_ref=f"findings:{content_hash(findings)}",
        item_evaluations=outcomes, selection=selection, evaluated_at=evaluated_at)
    digest = content_hash(payload)
    return PolicyEvaluation(evaluation_ref=f"evaluation:{digest}", evaluation_hash=digest, **payload)
