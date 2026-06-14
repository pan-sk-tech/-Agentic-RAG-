from fin_compliance.parsers.claim_parser import ClaimParser


def test_claim_parser_loads_json_sample():
    claim = ClaimParser().parse("fin_compliance/data/samples/claim_beijing_hotel_over_limit.json")

    assert claim.claim_id == "RC-2026-0001"
    assert claim.trip_city == "北京"
    assert claim.items[0].item_type == "hotel"
    assert claim.items[0].amount == 680
