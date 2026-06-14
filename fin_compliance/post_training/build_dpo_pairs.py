import json
from pathlib import Path


class DPOPairBuilder:
    def build(
        self,
        feedback_path: Path | str = "fin_compliance/data_flywheel/feedback.jsonl",
        output_path: Path | str = "fin_compliance/post_training/dpo_pairs.jsonl",
    ) -> str:
        feedback_path = Path(feedback_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not feedback_path.exists():
            output_path.write_text("", encoding="utf-8")
            return str(output_path)
        with feedback_path.open("r", encoding="utf-8") as source, output_path.open("w", encoding="utf-8") as target:
            for line in source:
                record = json.loads(line)
                if record.get("is_correct", True) or not record.get("fixed_answer"):
                    continue
                pair = {
                    "prompt": f"修正报销审核结果：{record.get('claim_id')}",
                    "chosen": record["fixed_answer"],
                    "rejected": record.get("comment", "原答案存在错误"),
                    "error_type": record.get("error_type"),
                }
                target.write(json.dumps(pair, ensure_ascii=False) + "\n")
        return str(output_path)
