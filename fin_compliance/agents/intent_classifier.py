from fin_compliance.domain.schemas import AuditIntent, ReimbursementClaim


class IntentClassifier:
    def classify(self, claim: ReimbursementClaim) -> AuditIntent:
        item_types = {item.item_type for item in claim.items}
        reasons = []
        task_type = "reimbursement_audit"

        if "contract" in item_types:
            task_type = "contract_payment_audit"
            reasons.append("报销项目包含合同付款内容。")
        elif "hotel" in item_types or "transport" in item_types or "meal" in item_types:
            task_type = "travel_reimbursement_audit"
            reasons.append("报销项目包含差旅住宿、交通或餐饮。")
        else:
            reasons.append("未命中特定业务类型，使用通用费用审核流程。")

        if claim.attachments:
            reasons.append("存在附件，需要调用解析/OCR 工具。")

        return AuditIntent(task_type=task_type, confidence=0.9, reasons=reasons)

