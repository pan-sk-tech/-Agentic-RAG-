from fastapi import FastAPI
from pydantic import BaseModel

from fin_compliance.agents.workflow import FinanceComplianceWorkflow


app = FastAPI(
    title="FinCompliance-Agent",
    version="1.0.0",
    description="Agentic RAG finance compliance audit API.",
)


class AuditRequest(BaseModel):
    claim_path: str
    report_path: str = "reports/api_audit_report.md"
    user_id: str = "default_user"


@app.post("/audit")
def audit(request: AuditRequest):
    workflow = FinanceComplianceWorkflow()
    final_state = workflow.app.invoke(
        {
            "claim_path": request.claim_path,
            "report_path": request.report_path,
            "user_id": request.user_id,
        }
    )
    report = final_state["report"]
    return {
        "claim_id": report.claim_id,
        "conclusion": report.conclusion,
        "risk_level": report.risk_level,
        "report_path": final_state["report_path"],
        "reward": (
            final_state["reward"].model_dump()
            if hasattr(final_state["reward"], "model_dump")
            else final_state["reward"].dict()
        ),
    }
