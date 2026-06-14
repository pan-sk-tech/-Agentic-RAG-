import math
import re
from collections import Counter
from typing import Dict, List, Optional

from fin_compliance.domain.schemas import Evidence, PolicyClause
from fin_compliance.rag.policy_store import PolicyStore
from fin_compliance.rag.query_rewriter import QueryRewriter
from fin_compliance.rag.reranker import PolicyReranker


DOMAIN_SYNONYMS = {
    "住宿": ["酒店", "宾馆", "住宿费", "住店"],
    "报销": ["费用", "报账", " reimbursement "],
    "北京": ["一线城市"],
    "上海": ["一线城市"],
    "广州": ["一线城市"],
    "深圳": ["一线城市"],
    "发票": ["票据", "发票抬头", "购买方"],
    "审批": ["审批链", "经理审批", "财务审批"],
}


class HybridPolicyRetriever:
    """Small, dependency-light hybrid retriever for policy clauses.

    It combines keyword/BM25-style scoring, business metadata filters, and a
    deterministic rerank step. This keeps the MVP runnable while leaving a clear
    extension point for dense vectors and cross-encoder rerankers.
    """

    def __init__(self, store: Optional[PolicyStore] = None):
        self.store = store or PolicyStore()
        self.query_rewriter = QueryRewriter()
        self.reranker = PolicyReranker()
        self.clauses = self.store.all()
        self.documents = [self._document_text(clause) for clause in self.clauses]
        self.doc_tokens = [self._tokenize(text) for text in self.documents]
        self.doc_freq = self._build_doc_freq()
        self.avg_doc_len = sum(len(tokens) for tokens in self.doc_tokens) / max(len(self.doc_tokens), 1)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, str]] = None,
    ) -> List[Evidence]:
        rewritten = self.query_rewriter.rewrite(query)
        expanded_query = self._expand_query(rewritten["rewritten_query"])
        query_tokens = self._tokenize(expanded_query)
        scored = []

        for clause, tokens in zip(self.clauses, self.doc_tokens):
            if metadata_filter and not self._metadata_match(clause, metadata_filter):
                continue
            if rewritten["doc_types"] and clause.doc_type not in rewritten["doc_types"]:
                # Keep approval/invoice clauses reachable because cross-policy evidence is common.
                if clause.doc_type not in {"approval_policy", "invoice_policy"}:
                    continue

            bm25 = self._bm25_score(query_tokens, tokens)
            rerank_boost = self._business_rerank_boost(query, clause)
            score = bm25 + rerank_boost
            if score <= 0:
                continue

            scored.append((score, clause))

        scored.sort(key=lambda item: item[0], reverse=True)
        evidence = [
            Evidence(
                clause_id=clause.clause_id,
                title=clause.title,
                text=clause.text,
                score=round(score, 4),
                metadata={
                    "doc_type": clause.doc_type,
                    "risk_type": clause.risk_type,
                    "effective_date": clause.effective_date,
                    "source_page": clause.source_page,
                    "source_file": clause.source_file,
                    "tags": clause.tags,
                    "matched_terms": self._matched_terms(query_tokens, self._tokenize(self._document_text(clause))),
                },
            )
            for score, clause in scored[:top_k]
        ]
        return self.reranker.rerank(query, evidence)[:top_k]

    def _document_text(self, clause: PolicyClause) -> str:
        return " ".join(
            [
                clause.clause_id,
                clause.doc_type,
                clause.title,
                clause.text,
                clause.risk_type,
                " ".join(clause.tags),
            ]
        )

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{1,4}", text)
        char_tokens = [char for char in text if "\u4e00" <= char <= "\u9fff"]
        return tokens + char_tokens

    def _expand_query(self, query: str) -> str:
        expansions = []
        for keyword, synonyms in DOMAIN_SYNONYMS.items():
            if keyword in query:
                expansions.extend(synonyms)
        return " ".join([query, *expansions])

    def _build_doc_freq(self) -> Counter:
        doc_freq = Counter()
        for tokens in self.doc_tokens:
            doc_freq.update(set(tokens))
        return doc_freq

    def _bm25_score(self, query_tokens: List[str], doc_tokens: List[str]) -> float:
        if not query_tokens or not doc_tokens:
            return 0.0

        k1 = 1.5
        b = 0.75
        token_counts = Counter(doc_tokens)
        doc_len = len(doc_tokens)
        total_docs = len(self.doc_tokens)
        score = 0.0

        for token in query_tokens:
            tf = token_counts[token]
            if tf == 0:
                continue
            df = self.doc_freq.get(token, 0)
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1 - b + b * doc_len / max(self.avg_doc_len, 1))
            score += idf * (tf * (k1 + 1) / denom)

        return score

    def _metadata_match(self, clause: PolicyClause, metadata_filter: Dict[str, str]) -> bool:
        for key, expected_value in metadata_filter.items():
            actual = getattr(clause, key, None) or clause.metadata.get(key)
            if actual != expected_value:
                return False
        return True

    def _business_rerank_boost(self, query: str, clause: PolicyClause) -> float:
        boost = 0.0
        if any(word in query for word in ["住宿", "酒店", "住店"]) and clause.risk_type == "hotel_fee_over_limit":
            boost += 2.0
        if "发票" in query and clause.risk_type in {"invoice_date_out_of_trip", "invoice_title_mismatch"}:
            boost += 1.5
        if "审批" in query and clause.risk_type == "approval_chain_missing":
            boost += 1.5
        if "餐饮" in query and clause.risk_type == "meal_fee_over_limit":
            boost += 1.5
        if "合同" in query and clause.risk_type == "contract_payment_risk":
            boost += 1.5
        if "供应商" in query and clause.risk_type == "supplier_name_mismatch":
            boost += 1.5
        if any(city in query for city in ["北京", "上海", "广州", "深圳"]) and "一线城市" in clause.tags:
            boost += 1.0
        return boost

    def _matched_terms(self, query_tokens: List[str], doc_tokens: List[str]) -> List[str]:
        doc_token_set = set(doc_tokens)
        return sorted({token for token in query_tokens if token in doc_token_set})[:20]
