from fin_compliance.domain.schemas import AuditIntent, ReimbursementClaim


class AuditPlanner:
    def plan(self, claim: ReimbursementClaim, intent: AuditIntent | None = None) -> list[str]:
        steps = [
            "识别任务意图，判断是差旅报销、通用费用、合同付款还是需要补充材料。",
            "解析报销单中的金额、日期、城市、员工级别、发票类型和审批链。",
            "检索公司差旅报销制度、发票制度和审批权限制度。",
            "调用规则引擎校验住宿金额、发票日期、发票抬头和审批链。",
            "为每个风险项绑定制度条款证据。",
            "生成包含结论、风险等级、证据链和整改建议的审核报告。",
        ]

        if any(item.item_type == "hotel" for item in claim.items):
            steps.insert(2, "根据城市和员工级别匹配住宿费标准。")
        if claim.attachments:
            steps.insert(1, "调用 OCR/文档解析工具抽取附件中的发票字段。")
        if intent and intent.task_type == "contract_payment_audit":
            steps.insert(3, "解析合同付款条款，识别预付款比例和验收节点。")
        return steps
