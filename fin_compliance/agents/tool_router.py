from typing import List

from fin_compliance.domain.schemas import AuditIntent, ReimbursementClaim, ToolCall


class ToolRouter:
    def route(self, claim: ReimbursementClaim, intent: AuditIntent) -> List[ToolCall]:
        calls: List[ToolCall] = [
            ToolCall(
                tool_name="policy_retriever",
                purpose="检索企业财务制度、发票制度、审批制度和合同制度。",
                inputs={"task_type": intent.task_type},
            ),
            ToolCall(
                tool_name="rule_engine",
                purpose="执行金额、日期、发票抬头、审批链、重复报销和交通标准校验。",
                inputs={"claim_id": claim.claim_id},
            ),
            ToolCall(
                tool_name="evidence_verifier",
                purpose="检查每个风险结论是否绑定了真实检索证据。",
                inputs={"claim_id": claim.claim_id},
            ),
            ToolCall(
                tool_name="report_writer",
                purpose="生成结构化 Markdown 审核报告。",
                inputs={"claim_id": claim.claim_id},
            ),
        ]

        if claim.attachments:
            calls.insert(
                0,
                ToolCall(
                    tool_name="ocr_parser",
                    purpose="解析发票图片、扫描件或 OCR 文本附件。",
                    inputs={"attachments": claim.attachments},
                ),
            )

        if any(item.item_type == "contract" for item in claim.items):
            calls.insert(
                1,
                ToolCall(
                    tool_name="contract_parser",
                    purpose="抽取合同金额、预付款比例和验收节点。",
                    inputs={"claim_id": claim.claim_id},
                ),
            )

        return calls

