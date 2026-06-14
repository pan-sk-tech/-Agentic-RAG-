import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fin_compliance.domain.schemas import HistoricalCase


DEFAULT_LOG_PATH = Path("fin_compliance/data_flywheel/audit_logs.jsonl")


class CaseMemory:
    def __init__(self, log_path: Path | str = DEFAULT_LOG_PATH):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: Dict[str, Any]) -> None:
        enriched = {
            "logged_at": datetime.now().isoformat(timespec="seconds"),
            **record,
        }
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(enriched, ensure_ascii=False) + "\n")

    def recent_cases(self, limit: int = 5) -> list[HistoricalCase]:
        if not self.log_path.exists():
            return []
        rows = []
        with self.log_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        cases = []
        for row in rows[-limit:]:
            risk_types = [
                finding.get("risk_type")
                for finding in row.get("findings", [])
                if not finding.get("passed", True)
            ]
            cases.append(
                HistoricalCase(
                    claim_id=row.get("claim_id", "unknown"),
                    conclusion=row.get("conclusion", "unknown"),
                    risk_level=row.get("risk_level", "unknown"),
                    risk_types=[item for item in risk_types if item],
                    report_path=row.get("report_path"),
                )
            )
        return cases

