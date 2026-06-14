DOC_TYPE_DESCRIPTIONS = {
    "reimbursement_policy": "费用报销和差旅制度",
    "invoice_policy": "发票管理制度",
    "approval_policy": "财务审批权限制度",
    "procurement_policy": "采购与供应商管理制度",
    "contract_policy": "合同审批与付款条款制度",
}


RISK_TO_DOC_TYPES = {
    "hotel_fee_over_limit": ["reimbursement_policy"],
    "meal_fee_over_limit": ["reimbursement_policy"],
    "invoice_date_out_of_trip": ["reimbursement_policy", "invoice_policy"],
    "invoice_title_mismatch": ["invoice_policy"],
    "approval_chain_missing": ["approval_policy"],
    "transport_policy_violation": ["reimbursement_policy"],
    "duplicate_reimbursement": ["reimbursement_policy"],
    "supplier_name_mismatch": ["procurement_policy", "invoice_policy"],
    "contract_payment_risk": ["contract_policy"],
}


def infer_doc_types_from_query(query: str) -> list[str]:
    doc_types = set()
    keyword_map = {
        "住宿": "reimbursement_policy",
        "餐饮": "reimbursement_policy",
        "交通": "reimbursement_policy",
        "报销": "reimbursement_policy",
        "发票": "invoice_policy",
        "审批": "approval_policy",
        "供应商": "procurement_policy",
        "合同": "contract_policy",
        "付款": "contract_policy",
    }
    for keyword, doc_type in keyword_map.items():
        if keyword in query:
            doc_types.add(doc_type)
    return sorted(doc_types)
