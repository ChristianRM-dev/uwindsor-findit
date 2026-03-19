from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.listings.models import Claim, Item


AUTO_REJECT_NOTE = "Closed automatically because another claim for this item was approved."


class ClaimReviewError(Exception):
    pass


@dataclass
class ClaimReviewResult:
    claim: Claim
    auto_rejected_claims: list[Claim] = field(default_factory=list)


@transaction.atomic
def review_claim(*, claim: Claim, reviewer, decision: str, reviewer_notes: str = "") -> ClaimReviewResult:
    claim = Claim.objects.select_for_update().select_related(
        "item",
        "claimant",
        "item__reporter",
        "reviewer",
    ).get(pk=claim.pk)

    if claim.status != Claim.Status.PENDING:
        raise ClaimReviewError("This claim has already been reviewed.")

    if decision not in {"approve", "reject"}:
        raise ClaimReviewError("Unsupported claim review decision.")

    if decision == "approve" and claim.item.status != Item.Status.LOST:
        raise ClaimReviewError("Only items that are still marked as lost can be approved.")

    review_time = timezone.now()
    claim.reviewer = reviewer
    claim.reviewer_notes = reviewer_notes.strip()
    claim.reviewed_at = review_time

    if decision == "approve":
        claim.status = Claim.Status.APPROVED
        claim.save()

        item = claim.item
        item.status = Item.Status.CLAIMED
        item.claimed_by = claim.claimant
        item.save()

        auto_rejected_claims = list(
            Claim.objects.select_related("item", "claimant", "item__reporter")
            .filter(item=item, status=Claim.Status.PENDING)
            .exclude(pk=claim.pk)
        )
        if auto_rejected_claims:
            Claim.objects.filter(pk__in=[pending_claim.pk for pending_claim in auto_rejected_claims]).update(
                status=Claim.Status.REJECTED,
                reviewer_id=reviewer.pk,
                reviewer_notes=AUTO_REJECT_NOTE,
                reviewed_at=review_time,
                updated_at=review_time,
            )
            for pending_claim in auto_rejected_claims:
                pending_claim.status = Claim.Status.REJECTED
                pending_claim.reviewer = reviewer
                pending_claim.reviewer_notes = AUTO_REJECT_NOTE
                pending_claim.reviewed_at = review_time
                pending_claim.updated_at = review_time
    else:
        claim.status = Claim.Status.REJECTED
        claim.save()
        auto_rejected_claims = []

    return ClaimReviewResult(
        claim=claim,
        auto_rejected_claims=auto_rejected_claims,
    )
