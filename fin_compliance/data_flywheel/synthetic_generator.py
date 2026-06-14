import json
from pathlib import Path


class SyntheticCaseGenerator:
    def generate(self) -> list[dict]:
        return [
            {
                "case": "普通员工北京出差，住宿费 680 元/晚",
                "label": "不合规",
                "risk_type": ["hotel_fee_over_limit"],
                "reason": "超过一线城市普通员工 600 元/晚标准",
            },
            {
                "case": "员工上海出差 3 晚，总住宿费 1700 元，发票日期均在出差期间",
                "label": "合规",
                "risk_type": [],
                "reason": "未超过 600 元/晚标准",
            },
            {
                "case": "广州出差住宿发票日期晚于出差结束日期，且发票抬头与公司名称不一致",
                "label": "不合规",
                "risk_type": ["invoice_date_out_of_trip", "invoice_title_mismatch"],
                "reason": "日期异常且发票抬头不一致",
            },
            {
                "case": "合同预付款比例 50%，合同未包含验收节点",
                "label": "不合规",
                "risk_type": ["contract_payment_risk"],
                "reason": "预付款超过 30% 且缺少验收节点",
            },
        ]

    def write(self, output_path: Path | str = "fin_compliance/data_flywheel/synthetic_cases.jsonl") -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            for record in self.generate():
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return str(output_path)

