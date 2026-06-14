import argparse

from fin_compliance.agents.workflow import FinanceComplianceWorkflow
from fin_compliance.data_flywheel.feedback_collector import FeedbackCollector
from fin_compliance.data_flywheel.hard_case_miner import HardCaseMiner
from fin_compliance.data_flywheel.synthetic_generator import SyntheticCaseGenerator
from fin_compliance.eval.run_eval import main as run_eval_main
from fin_compliance.parsers.invoice_ocr import InvoiceOCR
from fin_compliance.parsers.policy_parser import PolicyParser
from fin_compliance.post_training.build_dpo_pairs import DPOPairBuilder
from fin_compliance.post_training.build_sft_data import SFTDataBuilder


def run_audit(args):
    workflow = FinanceComplianceWorkflow()
    final_state = workflow.app.invoke(
        {
            "claim_path": args.claim,
            "report_path": args.out,
            "user_id": args.user_id,
        }
    )
    report = final_state["report"]
    reward = final_state["reward"]
    print(f"Conclusion: {report.conclusion}")
    print(f"Risk level: {report.risk_level}")
    print(f"Reward: {reward.total_score}")
    print(f"Report: {final_state['report_path']}")


def run_synthetic(args):
    path = SyntheticCaseGenerator().write(args.out)
    print(f"Synthetic cases written to {path}")


def run_feedback(args):
    record = FeedbackCollector().collect(
        claim_id=args.claim_id,
        is_correct=not args.incorrect,
        comment=args.comment,
        error_type=args.error_type,
        fixed_answer=args.fixed_answer,
    )
    print(record)


def run_hard_cases(args):
    cases = HardCaseMiner().mine(args.out)
    print(f"Hard cases: {len(cases)} -> {args.out}")


def run_sft(args):
    print(SFTDataBuilder().build(output_path=args.out))


def run_dpo(args):
    print(DPOPairBuilder().build(output_path=args.out))


def run_ocr(args):
    print(InvoiceOCR().extract(args.path))


def run_build_policy(args):
    clauses = PolicyParser().parse(args.input, args.out)
    print(f"Parsed policy clauses: {len(clauses)} -> {args.out}")


def main():
    parser = argparse.ArgumentParser(description="FinCompliance-Agent command line tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit")
    audit.add_argument("--claim", default="fin_compliance/data/samples/claim_beijing_hotel_over_limit.json")
    audit.add_argument("--out", default="reports/fin_compliance_report.md")
    audit.add_argument("--user-id", default="default_user")
    audit.set_defaults(func=run_audit)

    eval_cmd = subparsers.add_parser("eval")
    eval_cmd.set_defaults(func=lambda args: run_eval_main())

    synthetic = subparsers.add_parser("synthetic")
    synthetic.add_argument("--out", default="fin_compliance/data_flywheel/synthetic_cases.jsonl")
    synthetic.set_defaults(func=run_synthetic)

    feedback = subparsers.add_parser("feedback")
    feedback.add_argument("--claim-id", required=True)
    feedback.add_argument("--incorrect", action="store_true")
    feedback.add_argument("--comment", default="")
    feedback.add_argument("--error-type", default=None)
    feedback.add_argument("--fixed-answer", default=None)
    feedback.set_defaults(func=run_feedback)

    hard_cases = subparsers.add_parser("hard-cases")
    hard_cases.add_argument("--out", default="fin_compliance/data_flywheel/hard_cases.jsonl")
    hard_cases.set_defaults(func=run_hard_cases)

    sft = subparsers.add_parser("build-sft")
    sft.add_argument("--out", default="fin_compliance/post_training/sft_data.jsonl")
    sft.set_defaults(func=run_sft)

    dpo = subparsers.add_parser("build-dpo")
    dpo.add_argument("--out", default="fin_compliance/post_training/dpo_pairs.jsonl")
    dpo.set_defaults(func=run_dpo)

    ocr = subparsers.add_parser("ocr")
    ocr.add_argument("path")
    ocr.set_defaults(func=run_ocr)

    policy = subparsers.add_parser("build-policy")
    policy.add_argument("--input", required=True)
    policy.add_argument("--out", default="fin_compliance/data/policies/parsed_policy.jsonl")
    policy.set_defaults(func=run_build_policy)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
