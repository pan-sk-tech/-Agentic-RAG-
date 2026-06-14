import argparse

from fin_compliance.agents.workflow import FinanceComplianceWorkflow


def main():
    parser = argparse.ArgumentParser(description="Run the FinCompliance-Agent MVP.")
    parser.add_argument(
        "--claim",
        default="fin_compliance/data/samples/claim_beijing_hotel_over_limit.json",
        help="Path to a reimbursement claim JSON file.",
    )
    parser.add_argument(
        "--out",
        default="reports/fin_compliance_report.md",
        help="Path to write the Markdown audit report.",
    )
    args = parser.parse_args()

    workflow = FinanceComplianceWorkflow()
    final_state = workflow.app.invoke(
        {
            "claim_path": args.claim,
            "report_path": args.out,
        }
    )
    report = final_state["report"]
    reward = final_state["reward"]

    print("FinCompliance-Agent finished.")
    print(f"Conclusion: {report.conclusion}")
    print(f"Risk level: {report.risk_level}")
    print(f"Reward: {reward.total_score}")
    print(f"Report: {final_state['report_path']}")


if __name__ == "__main__":
    main()
