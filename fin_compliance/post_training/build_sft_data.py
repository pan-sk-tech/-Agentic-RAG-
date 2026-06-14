import json
from pathlib import Path


class SFTDataBuilder:
    def build(
        self,
        audit_log_path: Path | str = "fin_compliance/data_flywheel/audit_logs.jsonl",
        output_path: Path | str = "fin_compliance/post_training/sft_data.jsonl",
    ) -> str:
        audit_log_path = Path(audit_log_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not audit_log_path.exists():
            output_path.write_text("", encoding="utf-8")
            return str(output_path)
        with audit_log_path.open("r", encoding="utf-8") as source, output_path.open("w", encoding="utf-8") as target:
            for line in source:
                record = json.loads(line)
                sample = {
                    "instruction": f"审核报销单 {record.get('claim_id')} 是否合规，并给出证据链。",
                    "input": record.get("query", ""),
                    "output": json.dumps(
                        {
                            "conclusion": record.get("conclusion"),
                            "risk_level": record.get("risk_level"),
                            "findings": record.get("findings", []),
                        },
                        ensure_ascii=False,
                    ),
                }
                target.write(json.dumps(sample, ensure_ascii=False) + "\n")
        return str(output_path)

