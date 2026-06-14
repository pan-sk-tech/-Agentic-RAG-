from fin_compliance.domain.schemas import AuditReport, Evidence, RuleFinding
from fin_compliance.eval.metrics import evaluate_report


def test_evaluate_report_scores_expected_risk_and_evidence():
    report = AuditReport(
        claim_id="RC-TEST",
        conclusion="不合规",
        risk_level="medium",
        findings=[
            RuleFinding(
                rule_id="RULE-HOTEL-FEE",
                passed=False,
                risk_type="hotel_fee_over_limit",
                risk_level="medium",
                reason="住宿费超标。",
                evidence_clause_ids=["TRAVEL-3.2"],
            )
        ],
        evidence=[
            Evidence(
                clause_id="TRAVEL-3.2",
                title="住宿标准",
                text="普通员工一线城市住宿费标准为 600 元/晚。",
                score=1.0,
                metadata={"risk_type": "hotel_fee_over_limit"},
            )
        ],
        markdown="# 财务合规审核报告",
    )

    metrics = evaluate_report(
        report,
        {
            "expected_conclusion": "不合规",
            "expected_risk_types": ["hotel_fee_over_limit"],
            "expected_evidence": ["TRAVEL-3.2"],
        },
    )

    assert metrics["conclusion_accuracy"] == 1.0
    assert metrics["risk_type_recall"] == 1.0
    assert metrics["evidence_recall"] == 1.0
    assert metrics["hallucination_rate"] == 0.0
