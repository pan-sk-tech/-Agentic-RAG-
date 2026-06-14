RISK_LEVEL_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


RISK_LABELS = {
    "hotel_fee_over_limit": "住宿费超标",
    "invoice_date_out_of_trip": "发票日期异常",
    "invoice_title_mismatch": "发票抬头不一致",
    "approval_chain_missing": "审批链缺失",
    "transport_policy_violation": "交通标准异常",
    "meal_fee_over_limit": "餐饮费超标",
    "duplicate_reimbursement": "重复报销",
    "supplier_name_mismatch": "供应商名称不一致",
    "contract_payment_risk": "合同付款条款异常",
    "missing_material": "材料缺失",
}


def merge_risk_level(levels):
    if not levels:
        return "low"
    return max(levels, key=lambda level: RISK_LEVEL_ORDER.get(level, 0))
