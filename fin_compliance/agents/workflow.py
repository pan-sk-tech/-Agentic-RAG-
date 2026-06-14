import json
from pathlib import Path
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from fin_compliance.agents.intent_classifier import IntentClassifier
from fin_compliance.agents.planner import AuditPlanner
from fin_compliance.agents.report_agent import ReportAgent
from fin_compliance.agents.tool_router import ToolRouter
from fin_compliance.agents.verifier import EvidenceVerifier
from fin_compliance.domain.schemas import ComplianceState, ReimbursementClaim
from fin_compliance.memory.case_memory import CaseMemory
from fin_compliance.memory.user_memory import UserMemory
from fin_compliance.parsers.approval_parser import ApprovalParser
from fin_compliance.parsers.claim_parser import ClaimParser
from fin_compliance.parsers.invoice_ocr import InvoiceOCR
from fin_compliance.post_training.reward_scorer import RewardScorer
from fin_compliance.rag.hybrid_retriever import HybridPolicyRetriever
from fin_compliance.tools.rule_engine import RuleEngine
from fin_compliance.tools.report_writer import ReportWriter


class FinanceComplianceWorkflow:
    def __init__(self):
        self.claim_parser = ClaimParser()
        self.approval_parser = ApprovalParser()
        self.invoice_ocr = InvoiceOCR()
        self.intent_classifier = IntentClassifier()
        self.planner = AuditPlanner()
        self.tool_router = ToolRouter()
        self.retriever = HybridPolicyRetriever()
        self.rule_engine = RuleEngine()
        self.verifier = EvidenceVerifier()
        self.report_agent = ReportAgent()
        self.report_writer = ReportWriter()
        self.memory = CaseMemory()
        self.user_memory = UserMemory()
        self.reward_scorer = RewardScorer()
        self.app = self._compile()

    def _compile(self):
        workflow = StateGraph(ComplianceState)
        workflow.add_node("parse_claim", self.parse_claim)
        workflow.add_node("classify_intent", self.classify_intent)
        workflow.add_node("load_memory", self.load_memory)
        workflow.add_node("plan_audit", self.plan_audit)
        workflow.add_node("route_tools", self.route_tools)
        workflow.add_node("retrieve_policy", self.retrieve_policy)
        workflow.add_node("apply_rules", self.apply_rules)
        workflow.add_node("verify_evidence", self.verify_evidence)
        workflow.add_node("write_report", self.write_report)
        workflow.add_node("score_reward", self.score_reward)
        workflow.add_node("persist_memory", self.persist_memory)

        workflow.set_entry_point("parse_claim")
        workflow.add_edge("parse_claim", "classify_intent")
        workflow.add_edge("classify_intent", "load_memory")
        workflow.add_edge("load_memory", "plan_audit")
        workflow.add_edge("plan_audit", "route_tools")
        workflow.add_edge("route_tools", "retrieve_policy")
        workflow.add_edge("retrieve_policy", "apply_rules")
        workflow.add_edge("apply_rules", "verify_evidence")
        workflow.add_edge("verify_evidence", "write_report")
        workflow.add_edge("write_report", "score_reward")
        workflow.add_edge("score_reward", "persist_memory")
        workflow.add_edge("persist_memory", END)
        return workflow.compile()

    def parse_claim(self, state: ComplianceState) -> ComplianceState:
        claim = self.claim_parser.parse(state["claim_path"])
        self._enrich_claim_with_approvals(claim)
        self._enrich_claim_with_attachments(claim)
        return {"claim": claim}

    def classify_intent(self, state: ComplianceState) -> ComplianceState:
        return {"intent": self.intent_classifier.classify(state["claim"])}

    def load_memory(self, state: ComplianceState) -> ComplianceState:
        user_id = state.get("user_id", "default_user")
        return {
            "user_profile": self.user_memory.get(user_id),
            "similar_cases": self.memory.recent_cases(limit=3),
        }

    def plan_audit(self, state: ComplianceState) -> ComplianceState:
        claim = state["claim"]
        return {"plan": self.planner.plan(claim, state.get("intent"))}

    def route_tools(self, state: ComplianceState) -> ComplianceState:
        return {"tool_calls": self.tool_router.route(state["claim"], state["intent"])}

    def retrieve_policy(self, state: ComplianceState) -> ComplianceState:
        claim = state["claim"]
        query = self._build_policy_query(claim)
        evidence = self.retriever.retrieve(query, top_k=8)
        return {"query": query, "evidence": evidence}

    def apply_rules(self, state: ComplianceState) -> ComplianceState:
        findings = self.rule_engine.audit(state["claim"], state["evidence"])
        return {"findings": findings}

    def verify_evidence(self, state: ComplianceState) -> ComplianceState:
        missing_info = self.verifier.verify(state["findings"], state["evidence"])
        return {"missing_info": missing_info}

    def write_report(self, state: ComplianceState) -> ComplianceState:
        report = self.report_agent.write(
            claim=state["claim"],
            findings=state["findings"],
            evidence=state["evidence"],
            missing_info=state.get("missing_info", []),
            plan=state.get("plan", []),
            tool_calls=state.get("tool_calls", []),
        )
        report_path = Path(state.get("report_path") or f"reports/{report.claim_id}.md")
        self.report_writer.write_markdown(report, report_path)
        self.report_writer.write_json(report, report_path.with_suffix(".json"))
        return {"report": report, "report_path": str(report_path)}

    def score_reward(self, state: ComplianceState) -> ComplianceState:
        return {"reward": self.reward_scorer.score(state["report"])}

    def persist_memory(self, state: ComplianceState) -> ComplianceState:
        report = state["report"]
        self.memory.append(
            {
                "claim_id": report.claim_id,
                "intent": self._dump_model(state["intent"]),
                "query": state.get("query"),
                "plan": state.get("plan"),
                "tool_calls": [self._dump_model(item) for item in state.get("tool_calls", [])],
                "user_profile": self._dump_model(state["user_profile"]),
                "similar_cases": [self._dump_model(item) for item in state.get("similar_cases", [])],
                "conclusion": report.conclusion,
                "risk_level": report.risk_level,
                "findings": [self._dump_model(item) for item in report.findings],
                "evidence": [self._dump_model(item) for item in report.evidence],
                "reward": self._dump_model(state["reward"]),
                "report_path": state.get("report_path"),
            }
        )
        return state

    def _build_policy_query(self, claim: ReimbursementClaim) -> str:
        item_text = " ".join(
            [
                f"{item.item_type} {item.amount} {item.city or claim.trip_city} {item.date or ''} "
                f"{item.invoice_type or ''} {item.buyer_name or ''} {item.seller_name or ''} {item.description}"
                for item in claim.items
            ]
        )
        return (
            f"{claim.employee_level} {claim.department} {claim.trip_city} 出差报销审核 "
            f"{claim.trip_start} {claim.trip_end} 审批 {' '.join(claim.approval_chain)} {item_text}"
        )

    def _dump_model(self, model: Any) -> Dict[str, Any]:
        if hasattr(model, "model_dump"):
            return model.model_dump()
        return model.dict()

    def _enrich_claim_with_approvals(self, claim: ReimbursementClaim) -> None:
        for approval_file in claim.approval_files:
            parsed_roles = self.approval_parser.parse(approval_file)
            for role in parsed_roles:
                if role not in claim.approval_chain:
                    claim.approval_chain.append(role)

    def _enrich_claim_with_attachments(self, claim: ReimbursementClaim) -> None:
        if not claim.attachments or not claim.items:
            return
        for index, attachment in enumerate(claim.attachments):
            ocr_data = self.invoice_ocr.extract(attachment)
            item = claim.items[min(index, len(claim.items) - 1)]
            if ocr_data.get("amount") and not item.amount:
                item.amount = float(ocr_data["amount"])
            if ocr_data.get("date") and not item.date:
                item.date = ocr_data["date"]
            if ocr_data.get("invoice_type") and not item.invoice_type:
                item.invoice_type = ocr_data["invoice_type"]
            if ocr_data.get("buyer_name") and not item.buyer_name:
                item.buyer_name = ocr_data["buyer_name"]
            if ocr_data.get("seller_name") and not item.seller_name:
                item.seller_name = ocr_data["seller_name"]
