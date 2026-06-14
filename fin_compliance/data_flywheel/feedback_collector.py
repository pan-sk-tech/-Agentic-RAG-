import json
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_FEEDBACK_PATH = Path("fin_compliance/data_flywheel/feedback.jsonl")


class FeedbackCollector:
    def __init__(self, path: Path | str = DEFAULT_FEEDBACK_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def collect(
        self,
        claim_id: str,
        is_correct: bool,
        comment: str = "",
        error_type: Optional[str] = None,
        fixed_answer: Optional[str] = None,
    ) -> dict:
        record = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "claim_id": claim_id,
            "is_correct": is_correct,
            "comment": comment,
            "error_type": error_type,
            "fixed_answer": fixed_answer,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

