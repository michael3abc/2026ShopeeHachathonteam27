"""Versioned claim behavior; descriptions authored for the new implementation."""
from types import MappingProxyType
from typing import Mapping, get_args

from .domain import ClaimDefinition, ClaimId, EvidenceType

REGISTRY_VERSION = "claim-registry:1.0"
REGISTRY_MAJOR = 1


def _definition(
    claim: ClaimId, description: str, observable: str, *,
    order: bool = False, system: bool = False, user: bool = True,
    evidence: tuple[EvidenceType, ...] = ("IMAGE", "VIDEO"),
    distinct: tuple[ClaimId, ...] = (),
) -> ClaimDefinition:
    return ClaimDefinition(
        claim_id=claim, description=description, observable_requirement=observable,
        subject_scope="ORDER" if order else "LINE_ITEM",
        satisfiable_by=(["SYSTEM_FACTS"] if system else []) + (["USER_EVIDENCE"] if user else []),
        accepted_evidence_types=list(evidence) if user else [], distinguish_from=list(distinct),
    )


def build_registry() -> Mapping[ClaimId, ClaimDefinition]:
    definitions = [
        _definition("DELIVERY_CONFIRMED", "訂單已送達", "以可信物流的送達紀錄核對", order=True, system=True, user=False),
        _definition("ORDER_WITHIN_RETURN_WINDOW", "案件在可退貨期間提出", "比較案件時間、送達時間與適用政策", order=True, system=True, user=False),
        _definition("SHIPMENT_SEAL_INTACT", "開箱前封條完整", "查看包裝封條狀態與可核對的時間關係", order=True),
        _definition("ITEM_PHYSICALLY_DAMAGED", "品項有物理損壞", "顯示可辨識品項的裂痕或結構破損", distinct=("DAMAGE_PRESENT_ON_ARRIVAL", "ITEM_FUNCTIONALLY_IMPAIRED")),
        _definition("DAMAGE_PRESENT_ON_ARRIVAL", "損壞在收貨時已存在", "證據須能將損壞狀態連結至到貨時點", distinct=("ITEM_PHYSICALLY_DAMAGED",)),
        _definition("ITEM_FUNCTIONALLY_IMPAIRED", "品項無法正常運作", "描述或展示具體功能測試及結果", evidence=("IMAGE", "VIDEO", "TEXT"), distinct=("ITEM_PHYSICALLY_DAMAGED",)),
        _definition("ITEM_DIFFERS_FROM_LISTING", "品項與商品描述不符", "比對宣稱的商品特徵與收到的品項", distinct=("WRONG_ITEM_RECEIVED",)),
        _definition("WRONG_ITEM_RECEIVED", "收到不同品項", "比對訂單識別與收件品項識別", evidence=("IMAGE",), distinct=("ITEM_DIFFERS_FROM_LISTING", "ITEM_NOT_IN_SHIPMENT")),
        _definition("ITEM_NOT_IN_SHIPMENT", "包裹缺少訂購品項", "核對包裹內容及可信出貨資料", system=True, distinct=("WRONG_ITEM_RECEIVED",)),
        _definition("ITEM_UNUSED", "品項未使用", "可核對的外觀或封裝狀態顯示尚未使用", evidence=("IMAGE",)),
    ]
    registry = {entry.claim_id: entry for entry in definitions}
    validate_registry(registry)
    return MappingProxyType(registry)


def validate_registry(registry: Mapping[ClaimId, ClaimDefinition]) -> None:
    if set(registry) != set(get_args(ClaimId)):
        raise ValueError("Registry must define exactly the supported claims")
    for key, entry in registry.items():
        if key != entry.claim_id:
            raise ValueError("Registry key does not match its definition")
        if "USER_EVIDENCE" in entry.satisfiable_by and not entry.accepted_evidence_types:
            raise ValueError("User evidence claims need accepted types")
        for other in entry.distinguish_from:
            if other not in registry or key not in registry[other].distinguish_from:
                raise ValueError("Claim distinctions must be symmetric")


REGISTRY = build_registry()
