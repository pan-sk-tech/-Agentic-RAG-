from fin_compliance.domain.schemas import AuditReport, RewardScore


class RewardScorer:
    def score(self, report: AuditReport) -> RewardScore:
        failed_without_evidence = [
            finding for finding in report.findings if not finding.passed and not finding.evidence_clause_ids
        ]
        has_evidence = 1.0 if report.evidence else 0.0
        rule_judgment = 1.0 if report.findings else 0.0
        citation_accuracy = 0.0 if failed_without_evidence else 1.0
        report_complete = 1.0 if report.markdown and "检索证据链" in report.markdown else 0.0
        asks_missing = 1.0 if report.missing_info else 0.5

        components = {
            "retrieval_evidence": 0.25 * has_evidence,
            "rule_judgment": 0.25 * rule_judgment,
            "citation_accuracy": 0.20 * citation_accuracy,
            "tool_call_success": 0.15,
            "report_completeness": 0.10 * report_complete,
            "missing_info_awareness": 0.05 * asks_missing,
        }
        penalties = {}
        if failed_without_evidence:
            penalties["missing_citation"] = -0.3
        total = sum(components.values()) + sum(penalties.values())
        return RewardScore(
            total_score=round(max(total, 0), 4),
            components=components,
            penalties=penalties,
            reasons=["自动奖励评分用于筛选高质量 Agent 轨迹。"],
        )

