import json
from pathlib import Path


class HardCaseMiner:
    def __init__(
        self,
        audit_log_path: Path | str = "fin_compliance/data_flywheel/audit_logs.jsonl",
        feedback_path: Path | str = "fin_compliance/data_flywheel/feedback.jsonl",
    ):
        self.audit_log_path = Path(audit_log_path)
        self.feedback_path = Path(feedback_path)

    def mine(self, output_path: Path | str = "fin_compliance/data_flywheel/hard_cases.jsonl") -> list[dict]:
        hard_cases = []
        if self.feedback_path.exists():
            with self.feedback_path.open("r", encoding="utf-8") as file:
                for line in file:
                    record = json.loads(line)
                    if not record.get("is_correct", True):
                        hard_cases.append(record)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            for record in hard_cases:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return hard_cases

