from datetime import datetime
import re
from typing import List, Optional

from fin_compliance.domain.risk_taxonomy import RISK_LABELS, merge_risk_level
from fin_compliance.domain.schemas import AuditReport, Evidence, ReimbursementClaim, RuleFinding, ToolCall


class ReportAgent:
    def write(
        self,
        claim: ReimbursementClaim,
        findings: List[RuleFinding],
        evidence: List[Evidence],
        missing_info: List[str],
        plan: Optional[List[str]] = None,
        tool_calls: Optional[List[ToolCall]] = None,
    ) -> AuditReport:
        failed_findings = [finding for finding in findings if not finding.passed]
        conclusion = "合规" if not failed_findings and not missing_info else "不合规" if failed_findings else "需补充材料"
        risk_level = merge_risk_level([finding.risk_level for finding in failed_findings])
        markdown = self._to_markdown(claim, conclusion, risk_level, findings, evidence, missing_info, plan, tool_calls)

        return AuditReport(
            claim_id=claim.claim_id,
            conclusion=conclusion,
            risk_level=risk_level,
            findings=findings,
            evidence=evidence,
            missing_info=missing_info,
            markdown=markdown,
        )

    def _to_markdown(
        self,
        claim: ReimbursementClaim,
        conclusion: str,
        risk_level: str,
        findings: List[RuleFinding],
        evidence: List[Evidence],
        missing_info: List[str],
        plan: Optional[List[str]],
        tool_calls: Optional[List[ToolCall]],
    ) -> str:
        lines = [
            f"# 财务合规审核报告 - {claim.claim_id}",
            "",
            f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 员工：{claim.employee_name}",
            f"- 部门：{claim.department}",
            f"- 出差城市：{claim.trip_city}",
            f"- 出差期间：{claim.trip_start} 至 {claim.trip_end}",
            f"- 审核结论：**{conclusion}**",
            f"- 风险等级：**{self._risk_level_text(risk_level)}**",
            "",
            "## 审核摘要",
            "",
        ]

        failed_findings = [finding for finding in findings if not finding.passed]
        if failed_findings:
            for finding in failed_findings:
                evidence_item = self._find_evidence_for(finding, evidence)
                lines.extend(
                    [
                        f"### {RISK_LABELS.get(finding.risk_type, finding.risk_type)}",
                        f"- 审核结论：**不合规**",
                        f"- 风险类型：{RISK_LABELS.get(finding.risk_type, finding.risk_type)}",
                        f"- 具体原因：{finding.reason}",
                        f"- 超标/差异：{self._difference_text(finding)}",
                        f"- 制度依据：{self._evidence_text(finding, evidence_item)}",
                        f"- 风险等级：{self._risk_level_text(finding.risk_level)}",
                        f"- 处理建议：{finding.suggestion}",
                        f"- 证据来源：{self._source_text(evidence_item)}",
                        "",
                    ]
                )
        else:
            lines.extend(["- 审核结论：**合规**", "- 未发现违反当前制度的风险项。", ""])

        lines.extend(
            [
            "## Agent 执行计划",
            "",
            ]
        )

        for index, step in enumerate(plan or [], start=1):
            lines.append(f"{index}. {step}")

        lines.extend(
            [
                "",
                "## 工具调用链路",
                "",
            ]
        )

        for call in tool_calls or []:
            lines.extend(
                [
                    f"- `{call.tool_name}`：{call.purpose}",
                    f"  - 状态：{call.status}",
                ]
            )

        lines.extend(
            [
                "",
            "## 风险项与规则判断",
            "",
            ]
        )

        for finding in findings:
            status = "通过" if finding.passed else "未通过"
            lines.extend(
                [
                    f"### {finding.rule_id} - {status}",
                    f"- 风险类型：{finding.risk_type}",
                    f"- 风险等级：{finding.risk_level}",
                    f"- 判断原因：{finding.reason}",
                    f"- 期望值：{finding.expected or '无'}",
                    f"- 实际值：{finding.actual or '无'}",
                    f"- 证据条款：{', '.join(finding.evidence_clause_ids) or '无'}",
                    f"- 处理建议：{finding.suggestion}",
                    "",
                ]
            )

        if missing_info:
            lines.extend(["## 待补充信息", ""])
            lines.extend([f"- {item}" for item in missing_info])
            lines.append("")

        lines.extend(["## 检索证据链", ""])
        for item in evidence:
            lines.extend(
                [
                    f"### {item.clause_id} {item.title}",
                    f"- 匹配分数：{item.score}",
                    f"- 文档类型：{item.metadata.get('doc_type')}",
                    f"- 风险类型：{item.metadata.get('risk_type')}",
                    f"- 来源页：{item.metadata.get('source_page')}",
                    f"- 来源文件：{item.metadata.get('source_file')}",
                    f"- 命中词：{', '.join(item.metadata.get('matched_terms') or [])}",
                    f"> {item.text}",
                    "",
                ]
            )

        return "\n".join(lines)

    def _find_evidence_for(self, finding: RuleFinding, evidence: List[Evidence]) -> Optional[Evidence]:
        for clause_id in finding.evidence_clause_ids:
            for item in evidence:
                if item.clause_id == clause_id:
                    return item
        return None

    def _evidence_text(self, finding: RuleFinding, evidence_item: Optional[Evidence]) -> str:
        if not evidence_item:
            return "未检索到可引用制度条款"
        return f"《{evidence_item.metadata.get('source_file', '制度文件')}》{evidence_item.title}：{evidence_item.text}"

    def _source_text(self, evidence_item: Optional[Evidence]) -> str:
        if not evidence_item:
            return "无"
        return (
            f"制度文件：{evidence_item.metadata.get('source_file', 'unknown')}；"
            f"页码：第 {evidence_item.metadata.get('source_page', 'unknown')} 页；"
            f"条款：{evidence_item.clause_id} {evidence_item.title}"
        )

    def _difference_text(self, finding: RuleFinding) -> str:
        expected = self._first_number(finding.expected)
        actual = self._first_number(finding.actual)
        if expected is not None and actual is not None:
            diff = actual - expected
            if diff > 0:
                unit = " 元/晚" if "night" in (finding.expected or "") or "night" in (finding.actual or "") else ""
                return f"{actual:.0f} - {expected:.0f} = {diff:.0f}{unit}"
        return f"期望值：{finding.expected or '无'}；实际值：{finding.actual or '无'}"

    def _first_number(self, text: Optional[str]) -> Optional[float]:
        if not text:
            return None
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
        return float(match.group(1)) if match else None

    def _risk_level_text(self, level: str) -> str:
        return {
            "low": "低风险",
            "medium": "中风险",
            "high": "高风险",
        }.get(level, level)
