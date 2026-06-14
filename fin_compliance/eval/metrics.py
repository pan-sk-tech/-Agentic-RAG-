from typing import Dict, List, Set

from fin_compliance.domain.schemas import AuditReport


def evaluate_report(report: AuditReport, expected: Dict) -> Dict[str, float]:
    failed_risk_types: Set[str] = {
        finding.risk_type
        for finding in report.findings
        if not finding.passed
    }
    expected_risk_types = set(expected.get("expected_risk_types", []))

    evidence_ids = {item.clause_id for item in report.evidence}
    expected_evidence = set(expected.get("expected_evidence", []))

    failed_findings = [finding for finding in report.findings if not finding.passed]
    cited_failed_findings = [
        finding for finding in failed_findings if finding.evidence_clause_ids
    ]
    citation_accuracy = (
        1.0
        if not failed_findings
        else len(cited_failed_findings) / len(failed_findings)
    )
    conclusion_accuracy = 1.0 if report.conclusion == expected["expected_conclusion"] else 0.0
    risk_recall = _recall(failed_risk_types, expected_risk_types)
    evidence_recall = _recall(evidence_ids, expected_evidence)

    return {
        "conclusion_accuracy": conclusion_accuracy,
        "rule_accuracy": conclusion_accuracy,
        "risk_type_recall": risk_recall,
        "risk_type_precision": _precision(failed_risk_types, expected_risk_types),
        "evidence_recall": evidence_recall,
        "citation_accuracy": citation_accuracy,
        "faithfulness": 1.0 if report.evidence and citation_accuracy == 1.0 else 0.0,
        "action_success_rate": 1.0 if report.markdown and report.findings else 0.0,
        "hallucination_rate": 0.0 if citation_accuracy == 1.0 else 1.0,
    }


def average_metrics(rows: List[Dict[str, float]]) -> Dict[str, float]:
    if not rows:
        return {}
    keys = rows[0].keys()
    return {
        key: round(sum(row[key] for row in rows) / len(rows), 4)
        for key in keys
    }


def _recall(actual: Set[str], expected: Set[str]) -> float:
    if not expected:
        return 1.0
    return len(actual & expected) / len(expected)


def _precision(actual: Set[str], expected: Set[str]) -> float:
    if not actual:
        return 1.0 if not expected else 0.0
    return len(actual & expected) / len(actual)
