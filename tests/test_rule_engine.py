from fin_compliance.domain.schemas import Evidence
from fin_compliance.parsers.claim_parser import ClaimParser
from fin_compliance.tools.rule_engine import RuleEngine


def test_rule_engine_detects_beijing_hotel_over_limit():
    claim = ClaimParser().parse("fin_compliance/data/samples/claim_beijing_hotel_over_limit.json")
    evidence = [
        Evidence(
            clause_id="TRAVEL-3.2",
            title="住宿标准",
            text="普通员工一线城市住宿费标准为 600 元/晚。",
            score=1.0,
            metadata={"risk_type": "hotel_fee_over_limit"},
        )
    ]

    findings = RuleEngine().audit(claim, evidence)
    failed = [item for item in findings if not item.passed]

    assert any(item.risk_type == "hotel_fee_over_limit" for item in failed)
    hotel_finding = next(item for item in failed if item.risk_type == "hotel_fee_over_limit")
    assert hotel_finding.expected == "<= 600 CNY/night"
    assert hotel_finding.actual == "680 CNY/night"
    assert hotel_finding.evidence_clause_ids == ["TRAVEL-3.2"]
