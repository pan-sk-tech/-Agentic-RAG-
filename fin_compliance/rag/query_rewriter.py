from fin_compliance.domain.policy_metadata import infer_doc_types_from_query


class QueryRewriter:
    def rewrite(self, query: str) -> dict:
        doc_types = infer_doc_types_from_query(query)
        keywords = []
        for keyword in ["北京", "上海", "广州", "深圳", "住宿", "餐饮", "交通", "发票", "审批", "合同", "供应商"]:
            if keyword in query:
                keywords.append(keyword)
        return {
            "original_query": query,
            "rewritten_query": " ".join([query, *keywords, "制度 条款 标准 风险"]),
            "doc_types": doc_types,
            "keywords": keywords,
        }

