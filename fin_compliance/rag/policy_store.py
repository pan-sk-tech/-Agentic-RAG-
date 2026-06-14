import json
from pathlib import Path
from typing import Iterable, List

from fin_compliance.domain.schemas import PolicyClause


DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "policies"
    / "travel_reimbursement_policy.jsonl"
)


class PolicyStore:
    def __init__(self, policy_path: Path | str = DEFAULT_POLICY_PATH):
        self.policy_path = Path(policy_path)
        self.clauses = self._load_policy_clauses()

    def _load_policy_clauses(self) -> List[PolicyClause]:
        clauses: List[PolicyClause] = []
        with self.policy_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                clauses.append(PolicyClause(**json.loads(line)))
        return clauses

    def all(self) -> List[PolicyClause]:
        return list(self.clauses)

    def by_ids(self, clause_ids: Iterable[str]) -> List[PolicyClause]:
        wanted = set(clause_ids)
        return [clause for clause in self.clauses if clause.clause_id in wanted]

