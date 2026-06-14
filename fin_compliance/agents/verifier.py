from typing import List

from fin_compliance.domain.schemas import Evidence, RuleFinding


class EvidenceVerifier:
    def verify(self, findings: List[RuleFinding], evidence: List[Evidence]) -> List[str]:
        available_ids = {item.clause_id for item in evidence}
        issues = []

        for finding in findings:
            if finding.passed:
                continue
            if not finding.evidence_clause_ids:
                issues.append(f"{finding.rule_id} 缺少证据条款。")
                continue
            missing = [clause_id for clause_id in finding.evidence_clause_ids if clause_id not in available_ids]
            if missing:
                issues.append(f"{finding.rule_id} 引用了未检索到的条款：{', '.join(missing)}。")

        return issues

