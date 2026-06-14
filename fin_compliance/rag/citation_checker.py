from fin_compliance.domain.schemas import Evidence, RuleFinding


class CitationChecker:
    def check(self, findings: list[RuleFinding], evidence: list[Evidence]) -> dict:
        evidence_ids = {item.clause_id for item in evidence}
        missing = []
        invalid = []
        for finding in findings:
            if finding.passed:
                continue
            if not finding.evidence_clause_ids:
                missing.append(finding.rule_id)
            for clause_id in finding.evidence_clause_ids:
                if clause_id not in evidence_ids:
                    invalid.append({"rule_id": finding.rule_id, "clause_id": clause_id})
        return {
            "passed": not missing and not invalid,
            "missing_citations": missing,
            "invalid_citations": invalid,
        }

