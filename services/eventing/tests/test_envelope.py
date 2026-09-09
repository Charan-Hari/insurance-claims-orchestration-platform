from eventing_service.envelope import claim_created, workflow_transitioned


def test_claim_event_has_stable_contract():
    event = claim_created(claim_id="c-1", idempotency_key="claim:c-1")
    assert event.event_type == "claim.created"
    assert event.payload["claim_id"] == "c-1"
    assert event.producer == "claims-service"


def test_workflow_event_carries_transition():
    event = workflow_transitioned(
        workflow_id="w-1", from_state="received", to_state="review", idempotency_key="w-1:review"
    )
    assert event.payload["to_state"] == "review"
