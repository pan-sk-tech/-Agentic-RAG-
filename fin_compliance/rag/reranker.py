from fin_compliance.domain.schemas import Evidence


class PolicyReranker:
    def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]:
        reranked = []
        for item in evidence:
            score = item.score
            risk_type = item.metadata.get("risk_type", "")
            if "住宿" in query and risk_type == "hotel_fee_over_limit":
                score += 10
            if "餐饮" in query and risk_type == "meal_fee_over_limit":
                score += 10
            if "发票" in query and risk_type in {"invoice_title_mismatch", "invoice_date_out_of_trip"}:
                score += 8
            if "审批" in query and risk_type == "approval_chain_missing":
                score += 8
            if "合同" in query and risk_type == "contract_payment_risk":
                score += 8
            data = item.model_dump() if hasattr(item, "model_dump") else item.dict()
            data["score"] = round(score, 4)
            reranked.append(Evidence(**data))
        return sorted(reranked, key=lambda evidence: evidence.score, reverse=True)

