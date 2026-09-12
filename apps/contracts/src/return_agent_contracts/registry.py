"""The executable Claim Registry v1."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .base import ContractModel, NonEmptyText
from .enums import ClaimId, EvidenceType, SatisfiableBy, SubjectScope

CLAIM_REGISTRY_VERSION = "claim-registry:1.0"
CLAIM_REGISTRY_MAJOR = 1


class ClaimDefinition(ContractModel):
    claim_id: ClaimId
    description: NonEmptyText
    subject_scope: SubjectScope
    satisfiable_by: tuple[SatisfiableBy, ...]
    accepted_evidence_types: tuple[EvidenceType, ...] = ()
    observable_requirement: NonEmptyText
    distinguish_from: tuple[ClaimId, ...] = ()


def _claim(
    claim_id: ClaimId,
    description: str,
    subject_scope: SubjectScope,
    satisfiable_by: tuple[SatisfiableBy, ...],
    accepted_evidence_types: tuple[EvidenceType, ...],
    observable_requirement: str,
    distinguish_from: tuple[ClaimId, ...] = (),
) -> ClaimDefinition:
    return ClaimDefinition(
        claim_id=claim_id,
        description=description,
        subject_scope=subject_scope,
        satisfiable_by=satisfiable_by,
        accepted_evidence_types=accepted_evidence_types,
        observable_requirement=observable_requirement,
        distinguish_from=distinguish_from,
    )


CLAIM_REGISTRY_V1: Mapping[ClaimId, ClaimDefinition] = MappingProxyType(
    {
        ClaimId.DELIVERY_CONFIRMED: _claim(
            ClaimId.DELIVERY_CONFIRMED,
            "The shipment was delivered.",
            SubjectScope.ORDER,
            (SatisfiableBy.SYSTEM_FACTS,),
            (),
            "Determine from the logistics snapshot; never request it from the user.",
        ),
        ClaimId.ORDER_WITHIN_RETURN_WINDOW: _claim(
            ClaimId.ORDER_WITHIN_RETURN_WINDOW,
            "The order is within the applicable return window.",
            SubjectScope.ORDER,
            (SatisfiableBy.SYSTEM_FACTS,),
            (),
            "Determine from delivered_at and the applicable policy; never request it from the user.",
        ),
        ClaimId.SHIPMENT_SEAL_INTACT: _claim(
            ClaimId.SHIPMENT_SEAL_INTACT,
            "The shipment seal was intact.",
            SubjectScope.ORDER,
            (SatisfiableBy.USER_EVIDENCE,),
            (EvidenceType.IMAGE, EvidenceType.VIDEO),
            "The intact state of the carton seal or tape must be identifiable.",
        ),
        ClaimId.ITEM_PHYSICALLY_DAMAGED: _claim(
            ClaimId.ITEM_PHYSICALLY_DAMAGED,
            "The item has visible physical damage.",
            SubjectScope.LINE_ITEM,
            (SatisfiableBy.USER_EVIDENCE,),
            (EvidenceType.IMAGE, EvidenceType.VIDEO),
            "The damaged area of the item must be clearly visible.",
            (ClaimId.DAMAGE_PRESENT_ON_ARRIVAL, ClaimId.ITEM_FUNCTIONALLY_IMPAIRED),
        ),
        ClaimId.DAMAGE_PRESENT_ON_ARRIVAL: _claim(
            ClaimId.DAMAGE_PRESENT_ON_ARRIVAL,
            "The item was damaged when delivered, not afterwards.",
            SubjectScope.LINE_ITEM,
            (SatisfiableBy.USER_EVIDENCE,),
            (EvidenceType.IMAGE, EvidenceType.VIDEO),
            "An image must show both outer packaging and the damaged item area.",
            (ClaimId.ITEM_PHYSICALLY_DAMAGED,),
        ),
        ClaimId.ITEM_FUNCTIONALLY_IMPAIRED: _claim(
            ClaimId.ITEM_FUNCTIONALLY_IMPAIRED,
            "The item cannot perform its intended function.",
            SubjectScope.LINE_ITEM,
            (SatisfiableBy.USER_EVIDENCE,),
            (EvidenceType.IMAGE, EvidenceType.VIDEO, EvidenceType.TEXT),
            "Show the attempted operation or its result demonstrating failed function.",
            (ClaimId.ITEM_PHYSICALLY_DAMAGED,),
        ),
        ClaimId.ITEM_DIFFERS_FROM_LISTING: _claim(
            ClaimId.ITEM_DIFFERS_FROM_LISTING,
            "The received item differs from the listing.",
            SubjectScope.LINE_ITEM,
            (SatisfiableBy.USER_EVIDENCE,),
            (EvidenceType.IMAGE, EvidenceType.VIDEO),
            "Identifiable received-item characteristics must be comparable with the listing.",
            (ClaimId.WRONG_ITEM_RECEIVED,),
        ),
        ClaimId.WRONG_ITEM_RECEIVED: _claim(
            ClaimId.WRONG_ITEM_RECEIVED,
            "A different item was received.",
            SubjectScope.LINE_ITEM,
            (SatisfiableBy.USER_EVIDENCE,),
            (EvidenceType.IMAGE,),
            "The received item name or SKU must be identifiable and differ from the ordered item.",
            (ClaimId.ITEM_DIFFERS_FROM_LISTING, ClaimId.ITEM_NOT_IN_SHIPMENT),
        ),
        ClaimId.ITEM_NOT_IN_SHIPMENT: _claim(
            ClaimId.ITEM_NOT_IN_SHIPMENT,
            "The ordered item was missing from the shipment.",
            SubjectScope.LINE_ITEM,
            (SatisfiableBy.USER_EVIDENCE, SatisfiableBy.SYSTEM_FACTS),
            (EvidenceType.IMAGE, EvidenceType.VIDEO),
            "The full contents of the opened package must show the item is absent.",
            (ClaimId.WRONG_ITEM_RECEIVED,),
        ),
        ClaimId.ITEM_UNUSED: _claim(
            ClaimId.ITEM_UNUSED,
            "The item is unused.",
            SubjectScope.LINE_ITEM,
            (SatisfiableBy.USER_EVIDENCE,),
            (EvidenceType.IMAGE,),
            "The item, accessories, and tags must show an unused state.",
        ),
    }
)


def get_claim_definition(claim_id: ClaimId) -> ClaimDefinition:
    return CLAIM_REGISTRY_V1[claim_id]


def validate_claim_registry(
    registry: Mapping[ClaimId, ClaimDefinition] = CLAIM_REGISTRY_V1,
) -> None:
    """Raise ValueError if registry references are incomplete or asymmetric."""

    if set(registry) != set(ClaimId):
        raise ValueError("registry must define every ClaimId exactly once")
    for claim_id, definition in registry.items():
        if definition.claim_id != claim_id:
            raise ValueError(f"registry key and claim_id differ for {claim_id}")
        if (
            SatisfiableBy.USER_EVIDENCE in definition.satisfiable_by
            and not definition.accepted_evidence_types
        ):
            raise ValueError(f"{claim_id} requires accepted evidence types")
        for counterpart in definition.distinguish_from:
            if counterpart not in registry:
                raise ValueError(f"{claim_id} references missing {counterpart}")
            if claim_id not in registry[counterpart].distinguish_from:
                raise ValueError(
                    f"distinguish_from must be symmetric: {claim_id} <-> {counterpart}"
                )


validate_claim_registry()
