from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


class ReimbursementItem(BaseModel):
    item_id: str
    item_type: str = Field(..., description="hotel, transport, meal, or other")
    amount: float
    currency: str = "CNY"
    city: Optional[str] = None
    date: Optional[str] = None
    nights: int = 1
    invoice_type: Optional[str] = None
    buyer_name: Optional[str] = None
    seller_name: Optional[str] = None
    transport_class: Optional[str] = None
    description: str = ""


class ReimbursementClaim(BaseModel):
    claim_id: str
    employee_name: str
    employee_level: str = "staff"
    department: str
    company_name: str
    trip_city: str
    trip_start: str
    trip_end: str
    approval_chain: List[str] = Field(default_factory=list)
    approval_files: List[str] = Field(default_factory=list)
    attachments: List[str] = Field(default_factory=list)
    items: List[ReimbursementItem]


class PolicyClause(BaseModel):
    clause_id: str
    doc_type: str
    title: str
    text: str
    department: str = "finance"
    effective_date: str
    policy_level: str = "company"
    risk_type: str
    source_page: int = 1
    source_file: str = "unknown"
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    clause_id: str
    title: str
    text: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditIntent(BaseModel):
    task_type: str
    confidence: float = 1.0
    reasons: List[str] = Field(default_factory=list)


class ToolCall(BaseModel):
    tool_name: str
    purpose: str
    status: str = "planned"
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)


class RuleFinding(BaseModel):
    rule_id: str
    passed: bool
    risk_type: str
    risk_level: str
    reason: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    evidence_clause_ids: List[str] = Field(default_factory=list)
    suggestion: str = ""


class AuditReport(BaseModel):
    claim_id: str
    conclusion: str
    risk_level: str
    findings: List[RuleFinding]
    evidence: List[Evidence]
    missing_info: List[str] = Field(default_factory=list)
    markdown: str


class UserProfile(BaseModel):
    user_id: str = "default_user"
    role: str = "finance_reviewer"
    department: str = "finance"
    preferences: Dict[str, Any] = Field(default_factory=dict)


class HistoricalCase(BaseModel):
    claim_id: str
    conclusion: str
    risk_level: str
    risk_types: List[str] = Field(default_factory=list)
    report_path: Optional[str] = None


class RewardScore(BaseModel):
    total_score: float
    components: Dict[str, float]
    penalties: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)


class ComplianceState(TypedDict, total=False):
    claim_path: str
    user_id: str
    claim: ReimbursementClaim
    intent: AuditIntent
    plan: List[str]
    tool_calls: List[ToolCall]
    user_profile: UserProfile
    similar_cases: List[HistoricalCase]
    query: str
    evidence: List[Evidence]
    findings: List[RuleFinding]
    missing_info: List[str]
    report: AuditReport
    report_path: str
    reward: RewardScore
