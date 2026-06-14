import json
from pathlib import Path

from fin_compliance.agents.workflow import FinanceComplianceWorkflow
from fin_compliance.eval.metrics import average_metrics, evaluate_report


DEFAULT_CASE_PATH = Path("fin_compliance/eval/test_cases.jsonl")


def load_cases(path: Path = DEFAULT_CASE_PATH):
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                yield json.loads(line)


def main():
    workflow = FinanceComplianceWorkflow()
    rows = []

    for case in load_cases():
        final_state = workflow.app.invoke(
            {
                "claim_path": case["claim_path"],
                "report_path": f"reports/eval/{case['case_id']}.md",
            }
        )
        report = final_state["report"]
        metrics = evaluate_report(report, case)
        rows.append(metrics)
        print(f"{case['case_id']} {report.conclusion} {metrics}")

    print("Average metrics:")
    print(json.dumps(average_metrics(rows), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

