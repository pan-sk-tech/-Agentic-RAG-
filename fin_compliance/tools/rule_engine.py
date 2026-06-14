from datetime import date
from typing import Dict, List

from fin_compliance.domain.schemas import Evidence, ReimbursementClaim, RuleFinding
from fin_compliance.tools.calculator import FinanceCalculator


FIRST_TIER_CITIES = {"北京", "上海", "广州", "深圳"}

HOTEL_STANDARDS: Dict[str, Dict[str, float]] = {
    "first_tier": {
        "staff": 600,
        "manager": 800,
    },
    "second_tier": {
        "staff": 450,
        "manager": 650,
    },
}


class RuleEngine:
    def __init__(self):
        self.calculator = FinanceCalculator()

    def audit(self, claim: ReimbursementClaim, evidence: List[Evidence]) -> List[RuleFinding]:
        findings: List[RuleFinding] = []
        findings.extend(self._check_hotel_fee(claim, evidence))
        findings.extend(self._check_meal_fee(claim, evidence))
        findings.extend(self._check_transport_class(claim, evidence))
        findings.extend(self._check_invoice_dates(claim, evidence))
        findings.extend(self._check_invoice_titles(claim, evidence))
        findings.extend(self._check_supplier_consistency(claim, evidence))
        findings.extend(self._check_duplicate_reimbursement(claim, evidence))
        findings.extend(self._check_approval_chain(claim, evidence))
        return findings

    def _check_hotel_fee(self, claim: ReimbursementClaim, evidence: List[Evidence]) -> List[RuleFinding]:
        findings = []
        clause_ids = self._evidence_ids_for(evidence, "hotel_fee_over_limit")

        for item in claim.items:
            if item.item_type != "hotel":
                continue

            city = item.city or claim.trip_city
            city_tier = "first_tier" if city in FIRST_TIER_CITIES else "second_tier"
            standard = HOTEL_STANDARDS[city_tier].get(claim.employee_level, HOTEL_STANDARDS[city_tier]["staff"])
            allowed_total = standard * max(item.nights, 1)
            passed = item.amount <= allowed_total
            actual_per_night = item.amount / max(item.nights, 1)
            level_label = "普通员工" if claim.employee_level == "staff" else "经理级员工" if claim.employee_level == "manager" else claim.employee_level

            findings.append(
                RuleFinding(
                    rule_id="RULE-HOTEL-FEE",
                    passed=passed,
                    risk_type="hotel_fee_over_limit",
                    risk_level="medium" if not passed else "low",
                    reason=(
                        f"报销单中住宿费为 {actual_per_night:.0f} 元/晚，"
                        f"但公司差旅制度规定{level_label}在{city}住宿标准不得超过 {standard:.0f} 元/晚。"
                    ),
                    expected=f"<= {standard:.0f} CNY/night",
                    actual=f"{actual_per_night:.0f} CNY/night",
                    evidence_clause_ids=clause_ids,
                    suggestion="退回修改或要求补充特殊审批说明。" if not passed else "通过住宿金额校验。",
                )
            )

        return findings

    def _check_meal_fee(self, claim: ReimbursementClaim, evidence: List[Evidence]) -> List[RuleFinding]:
        findings = []
        clause_ids = self._evidence_ids_for(evidence, "meal_fee_over_limit")
        standards = {"staff": 120, "manager": 180}

        for item in claim.items:
            if item.item_type != "meal":
                continue
            standard = standards.get(claim.employee_level, standards["staff"])
            passed = item.amount <= standard
            findings.append(
                RuleFinding(
                    rule_id="RULE-MEAL-FEE",
                    passed=passed,
                    risk_type="meal_fee_over_limit",
                    risk_level="medium" if not passed else "low",
                    reason=f"{claim.employee_level} 餐饮标准为 {standard:.0f} 元/天，实际 {item.amount:.0f} 元。",
                    expected=f"<= {standard:.0f} CNY",
                    actual=f"{item.amount:.0f} CNY",
                    evidence_clause_ids=clause_ids,
                    suggestion="退回修改或要求补充特殊审批说明。" if not passed else "通过餐饮金额校验。",
                )
            )
        return findings

    def _check_transport_class(self, claim: ReimbursementClaim, evidence: List[Evidence]) -> List[RuleFinding]:
        findings = []
        clause_ids = self._evidence_ids_for(evidence, "transport_policy_violation")
        risky_classes = {"商务舱", "头等舱", "高铁商务座", "business", "first"}

        for item in claim.items:
            if item.item_type != "transport":
                continue
            transport_class = item.transport_class or item.invoice_type or item.description
            passed = not any(risky in transport_class for risky in risky_classes)
            if not passed and {"department_manager", "finance_director"}.issubset(set(claim.approval_chain)):
                passed = True
            findings.append(
                RuleFinding(
                    rule_id="RULE-TRANSPORT-CLASS",
                    passed=passed,
                    risk_type="transport_policy_violation",
                    risk_level="medium" if not passed else "low",
                    reason=f"{item.item_id} 交通类型为 {transport_class or '未知'}，当前审批链：{', '.join(claim.approval_chain) or '无'}。",
                    expected="高铁二等座/经济舱；高等级交通需部门负责人和财务负责人审批",
                    actual=transport_class or "missing",
                    evidence_clause_ids=clause_ids,
                    suggestion="补充高等级交通审批。" if not passed else "通过交通标准校验。",
                )
            )
        return findings

    def _check_invoice_dates(self, claim: ReimbursementClaim, evidence: List[Evidence]) -> List[RuleFinding]:
        findings = []
        clause_ids = self._evidence_ids_for(evidence, "invoice_date_out_of_trip")
        start = date.fromisoformat(claim.trip_start)
        end = date.fromisoformat(claim.trip_end)

        for item in claim.items:
            if not item.date:
                findings.append(
                    RuleFinding(
                        rule_id="RULE-INVOICE-DATE",
                        passed=False,
                        risk_type="invoice_date_out_of_trip",
                        risk_level="medium",
                        reason=f"{item.item_id} 缺少发票日期，无法校验是否落在出差期间。",
                        expected=f"{claim.trip_start} 至 {claim.trip_end}",
                        actual="missing",
                        evidence_clause_ids=clause_ids,
                        suggestion="要求员工补充发票日期或票据图片。",
                    )
                )
                continue

            item_date = date.fromisoformat(item.date)
            passed = start <= item_date <= end
            findings.append(
                RuleFinding(
                    rule_id="RULE-INVOICE-DATE",
                    passed=passed,
                    risk_type="invoice_date_out_of_trip",
                    risk_level="medium" if not passed else "low",
                    reason=f"{item.item_id} 发票日期 {item.date}，出差期间为 {claim.trip_start} 至 {claim.trip_end}。",
                    expected=f"{claim.trip_start} 至 {claim.trip_end}",
                    actual=item.date,
                    evidence_clause_ids=clause_ids,
                    suggestion="要求补充日期异常说明。" if not passed else "通过发票日期校验。",
                )
            )

        return findings

    def _check_invoice_titles(self, claim: ReimbursementClaim, evidence: List[Evidence]) -> List[RuleFinding]:
        findings = []
        clause_ids = self._evidence_ids_for(evidence, "invoice_title_mismatch")

        for item in claim.items:
            if not item.buyer_name:
                findings.append(
                    RuleFinding(
                        rule_id="RULE-INVOICE-TITLE",
                        passed=False,
                        risk_type="invoice_title_mismatch",
                        risk_level="medium",
                        reason=f"{item.item_id} 缺少发票购买方名称。",
                        expected=claim.company_name,
                        actual="missing",
                        evidence_clause_ids=clause_ids,
                        suggestion="要求补充发票抬头或票据图片。",
                    )
                )
                continue

            passed = item.buyer_name == claim.company_name
            findings.append(
                RuleFinding(
                    rule_id="RULE-INVOICE-TITLE",
                    passed=passed,
                    risk_type="invoice_title_mismatch",
                    risk_level="medium" if not passed else "low",
                    reason=f"{item.item_id} 发票购买方为 {item.buyer_name}，公司名称为 {claim.company_name}。",
                    expected=claim.company_name,
                    actual=item.buyer_name,
                    evidence_clause_ids=clause_ids,
                    suggestion="退回修改发票抬头或补充财务特批。" if not passed else "通过发票抬头校验。",
                )
            )

        return findings

    def _check_supplier_consistency(self, claim: ReimbursementClaim, evidence: List[Evidence]) -> List[RuleFinding]:
        findings = []
        clause_ids = self._evidence_ids_for(evidence, "supplier_name_mismatch")
        for item in claim.items:
            if not item.seller_name or not item.description:
                continue
            if "供应商:" not in item.description:
                continue
            expected_supplier = item.description.split("供应商:", 1)[1].split()[0].strip()
            passed = item.seller_name == expected_supplier
            findings.append(
                RuleFinding(
                    rule_id="RULE-SUPPLIER-CONSISTENCY",
                    passed=passed,
                    risk_type="supplier_name_mismatch",
                    risk_level="medium" if not passed else "low",
                    reason=f"{item.item_id} 发票销售方为 {item.seller_name}，报销说明供应商为 {expected_supplier}。",
                    expected=expected_supplier,
                    actual=item.seller_name,
                    evidence_clause_ids=clause_ids,
                    suggestion="进入人工复核供应商一致性。" if not passed else "通过供应商一致性校验。",
                )
            )
        return findings

    def _check_duplicate_reimbursement(self, claim: ReimbursementClaim, evidence: List[Evidence]) -> List[RuleFinding]:
        duplicate_groups = self.calculator.duplicate_keys(claim.items)
        if not duplicate_groups:
            return []
        findings = []
        clause_ids = self._evidence_ids_for(evidence, "duplicate_reimbursement")
        for key, item_ids in duplicate_groups.items():
            findings.append(
                RuleFinding(
                    rule_id="RULE-DUPLICATE-REIMBURSEMENT",
                    passed=False,
                    risk_type="duplicate_reimbursement",
                    risk_level="high",
                    reason=f"疑似重复报销项目：{', '.join(item_ids)}，重复键={key}。",
                    expected="同一员工、同一日期、同一发票类型、同一金额不得重复报销",
                    actual=", ".join(item_ids),
                    evidence_clause_ids=clause_ids,
                    suggestion="进入人工复核，确认是否重复提交。",
                )
            )
        return findings

    def _check_approval_chain(self, claim: ReimbursementClaim, evidence: List[Evidence]) -> List[RuleFinding]:
        total_amount = self.calculator.total_amount(claim.items)
        missing = []
        if total_amount > 1000 and "department_manager" not in claim.approval_chain:
            missing.append("department_manager")
        if total_amount > 5000 and "finance_director" not in claim.approval_chain:
            missing.append("finance_director")

        passed = not missing
        return [
            RuleFinding(
                rule_id="RULE-APPROVAL-CHAIN",
                passed=passed,
                risk_type="approval_chain_missing",
                risk_level="high" if total_amount > 5000 and missing else "medium" if missing else "low",
                reason=f"报销总金额 {total_amount:.0f} 元，当前审批链：{', '.join(claim.approval_chain) or '无'}。",
                expected="department_manager for >1000 CNY; finance_director for >5000 CNY",
                actual=", ".join(claim.approval_chain) or "missing",
                evidence_clause_ids=self._evidence_ids_for(evidence, "approval_chain_missing"),
                suggestion=f"补全审批节点：{', '.join(missing)}。" if missing else "通过审批链校验。",
            )
        ]

    def _evidence_ids_for(self, evidence: List[Evidence], risk_type: str) -> List[str]:
        return [
            item.clause_id
            for item in evidence
            if item.metadata.get("risk_type") == risk_type
        ][:2]
