from claims_service.models.claim import ClaimStatus


VALID_STATUS_TRANSITIONS: dict[ClaimStatus, frozenset[ClaimStatus]] = {
    ClaimStatus.SUBMITTED: frozenset({ClaimStatus.UNDER_REVIEW}),
    ClaimStatus.UNDER_REVIEW: frozenset({ClaimStatus.APPROVED, ClaimStatus.DENIED, ClaimStatus.CLOSED}),
    ClaimStatus.APPROVED: frozenset({ClaimStatus.PAID}),
    ClaimStatus.DENIED: frozenset(),
    ClaimStatus.PAID: frozenset(),
    ClaimStatus.CLOSED: frozenset(),
}


def is_valid_status_transition(current: ClaimStatus, target: ClaimStatus) -> bool:
    return target in VALID_STATUS_TRANSITIONS[current]