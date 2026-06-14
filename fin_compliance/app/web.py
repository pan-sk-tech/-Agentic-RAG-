import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import streamlit as st

from fin_compliance.agents.workflow import FinanceComplianceWorkflow
from fin_compliance.data_flywheel.feedback_collector import FeedbackCollector
from fin_compliance.data_flywheel.hard_case_miner import HardCaseMiner
from fin_compliance.data_flywheel.synthetic_generator import SyntheticCaseGenerator
from fin_compliance.eval.metrics import average_metrics, evaluate_report
from fin_compliance.eval.run_eval import load_cases
from fin_compliance.parsers.claim_parser import ClaimParser
from fin_compliance.parsers.contract_parser import ContractParser
from fin_compliance.parsers.invoice_ocr import InvoiceOCR
from fin_compliance.parsers.policy_parser import PolicyParser
from fin_compliance.post_training.build_dpo_pairs import DPOPairBuilder
from fin_compliance.post_training.build_sft_data import SFTDataBuilder


ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "fin_compliance" / "data" / "policies"
SAMPLE_DIR = ROOT / "fin_compliance" / "data" / "samples"
UPLOAD_DIR = ROOT / "fin_compliance" / "ui_uploads"
REPORT_DIR = ROOT / "reports"
FLYWHEEL_DIR = ROOT / "fin_compliance" / "data_flywheel"
POST_TRAINING_DIR = ROOT / "fin_compliance" / "post_training"

NAV_ITEMS = [
    "知识库管理",
    "报销审核",
    "合同审核",
    "发票识别",
    "Agent 执行链路",
    "自动化评测",
    "数据飞轮",
    "审核报告记录",
]

DOC_TYPES = {
    "报销制度": "reimbursement_policy",
    "发票制度": "invoice_policy",
    "合同审批制度": "contract_policy",
    "采购制度": "procurement_policy",
    "员工手册": "employee_handbook",
}

RISK_LABELS = {
    "low": "低风险",
    "medium": "中风险",
    "high": "高风险",
}

METRIC_LABELS = {
    "conclusion_accuracy": "结论准确率",
    "rule_accuracy": "规则判断准确率",
    "risk_type_recall": "风险召回率",
    "risk_type_precision": "风险精确率",
    "evidence_recall": "证据召回率",
    "citation_accuracy": "引用准确率",
    "faithfulness": "忠实度",
    "action_success_rate": "工具成功率",
    "hallucination_rate": "幻觉率",
}


def main() -> None:
    _ensure_dirs()
    st.set_page_config(
        page_title="FinCompliance-Agent",
        page_icon="FC",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_style()
    _render_sidebar()
    page = st.session_state.get("page", NAV_ITEMS[1])

    st.markdown('<div class="app-title">FinCompliance-Agent 企业财务合规审核工作台</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">Agentic RAG · Rule Engine · Evidence Chain · Eval · Data Flywheel</div>', unsafe_allow_html=True)

    if page == "知识库管理":
        render_knowledge_page()
    elif page == "报销审核":
        render_reimbursement_page()
    elif page == "合同审核":
        render_contract_page()
    elif page == "发票识别":
        render_invoice_page()
    elif page == "Agent 执行链路":
        render_agent_trace_page()
    elif page == "自动化评测":
        render_eval_page()
    elif page == "数据飞轮":
        render_data_flywheel_page()
    elif page == "审核报告记录":
        render_report_history_page()


def render_knowledge_page() -> None:
    st.header("知识库管理")
    left, right = st.columns([0.95, 1.05])

    with left:
        st.subheader("制度文件入库")
        policy_file = st.file_uploader(
            "上传制度文件",
            type=["pdf", "txt", "md"],
            key="kb_policy_file",
        )
        doc_type_label = st.selectbox("文档类型", list(DOC_TYPES.keys()), key="kb_doc_type")
        effective_date = st.date_input("生效日期", key="kb_effective_date")
        department = st.selectbox("适用部门", ["finance", "sales", "hr", "procurement", "all"], key="kb_department")

        if st.button("导入知识库", type="primary", use_container_width=True):
            if not policy_file:
                st.warning("请先上传制度文件。")
            else:
                try:
                    output_path, clauses = import_policy_file(
                        policy_file=policy_file,
                        doc_type=DOC_TYPES[doc_type_label],
                        doc_type_label=doc_type_label,
                        effective_date=str(effective_date),
                        department=department,
                    )
                    st.session_state["last_policy_import"] = str(output_path)
                    st.success(f"已入库 {len(clauses)} 个条款 chunk。")
                except Exception as exc:  # pragma: no cover - UI guard
                    st.error(f"导入失败：{exc}")

    with right:
        st.subheader("已入库文档")
        rows, chunks = load_policy_inventory()
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.info("暂无制度文件。")

        doc_names = sorted({row["文档名称"] for row in rows})
        if doc_names:
            selected = st.selectbox("查看 chunk", doc_names)
            preview = [
                {
                    "条款": item.get("clause_id"),
                    "标题": item.get("title"),
                    "页码": item.get("source_page"),
                    "风险类型": item.get("risk_type"),
                    "内容": item.get("text", "")[:160],
                }
                for item in chunks
                if _policy_doc_name(item) == selected
            ][:20]
            st.dataframe(preview, hide_index=True, use_container_width=True)


def render_reimbursement_page() -> None:
    st.header("报销审核")
    st.session_state.setdefault("audit_prompt", "帮我审核这笔北京出差报销是否合规。")

    upload_col, result_col = st.columns([0.78, 1.22])
    with upload_col:
        st.subheader("本次审核材料")
        quick_policy = st.file_uploader(
            "上传制度 PDF / TXT / MD",
            type=["pdf", "txt", "md"],
            key="audit_policy_upload",
        )
        claim_file = st.file_uploader(
            "上传报销单 Excel / JSON / CSV",
            type=["xlsx", "xlsm", "json", "csv", "tsv"],
            key="audit_claim_upload",
        )
        invoice_file = st.file_uploader(
            "上传发票图片 / OCR 文本 / JSON",
            type=["png", "jpg", "jpeg", "bmp", "tif", "tiff", "txt", "ocr", "json"],
            key="audit_invoice_upload",
        )
        approval_file = st.file_uploader(
            "上传审批流程文件",
            type=["txt", "json", "md"],
            key="audit_approval_upload",
        )
        st.text_area("用户问题", key="audit_prompt", height=90)
        use_sample = st.checkbox("使用内置北京住宿超标示例", value=claim_file is None)

        if st.button("开始智能审核", type="primary", use_container_width=True):
            try:
                if quick_policy:
                    import_policy_file(
                        policy_file=quick_policy,
                        doc_type="reimbursement_policy",
                        doc_type_label="报销制度",
                        effective_date="2025-01-01",
                        department="finance",
                    )

                claim_path = _resolve_claim_path(claim_file, use_sample)
                invoice_path = save_upload(invoice_file, "invoices") if invoice_file else _sample_invoice_path(use_sample)
                approval_path = save_upload(approval_file, "approvals") if approval_file else _sample_approval_path(use_sample)
                prepared_claim_path = prepare_claim_for_audit(claim_path, invoice_path, approval_path)
                final_state = execute_audit(prepared_claim_path, st.session_state["audit_prompt"])
                st.session_state["last_state"] = final_state
                st.session_state["page"] = "报销审核"
                st.success("审核完成。")
            except Exception as exc:  # pragma: no cover - UI guard
                st.error(f"审核失败：{exc}")

    with result_col:
        final_state = st.session_state.get("last_state")
        if not final_state:
            st.subheader("审核结果")
            st.info("上传材料后点击开始智能审核。未上传时可直接使用内置示例。")
            return
        render_audit_result(final_state)


def render_contract_page() -> None:
    st.header("合同审核")
    contract_file = st.file_uploader("上传合同 / 审批流程文件", type=["txt", "md", "pdf"], key="contract_file")
    use_sample = st.checkbox("使用内置合同风险示例", value=contract_file is None, key="contract_sample")

    if st.button("开始合同风险扫描", type="primary"):
        try:
            path = save_upload(contract_file, "contracts") if contract_file else SAMPLE_DIR / "contract_payment_risk.txt"
            result = ContractParser().parse(path)
            st.session_state["last_contract_result"] = result
            st.success("扫描完成。")
        except Exception as exc:  # pragma: no cover - UI guard
            st.error(f"合同解析失败：{exc}")

    result = st.session_state.get("last_contract_result")
    if result:
        c1, c2, c3 = st.columns(3)
        c1.metric("合同金额", result.get("amount") or "未识别")
        ratio = result.get("prepayment_ratio")
        c2.metric("预付款比例", f"{ratio:.0%}" if ratio is not None else "未识别")
        c3.metric("验收条款", "已包含" if result.get("has_acceptance_clause") else "缺失")

        risk_rows = [
            {"风险点": risk, "建议": _contract_suggestion(risk)}
            for risk in result.get("risk_hints", [])
        ]
        st.subheader("合同风险点")
        if risk_rows:
            st.dataframe(risk_rows, hide_index=True, use_container_width=True)
        else:
            st.success("暂未发现合同付款高风险。")
        with st.expander("合同原文"):
            st.text(result.get("raw_text", "")[:5000])


def render_invoice_page() -> None:
    st.header("发票识别")
    invoice_file = st.file_uploader(
        "上传发票图片 / OCR 文本 / JSON",
        type=["png", "jpg", "jpeg", "bmp", "tif", "tiff", "txt", "ocr", "json"],
        key="invoice_ocr_file",
    )
    use_sample = st.checkbox("使用内置发票 OCR 文本", value=invoice_file is None, key="invoice_sample")

    if st.button("识别发票", type="primary"):
        try:
            path = save_upload(invoice_file, "invoices") if invoice_file else SAMPLE_DIR / "invoice_hotel_680.txt"
            result = InvoiceOCR().extract(path)
            st.session_state["last_invoice_ocr"] = {"path": str(path), "result": result}
            st.success("识别完成。")
        except Exception as exc:  # pragma: no cover - UI guard
            st.error(f"OCR 失败：{exc}")

    payload = st.session_state.get("last_invoice_ocr")
    if payload:
        result = payload["result"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("发票类型", result.get("invoice_type") or "未识别")
        c2.metric("金额", result.get("amount") or "未识别")
        c3.metric("日期", result.get("date") or "未识别")
        c4.metric("购买方", result.get("buyer_name") or "未识别")
        st.json(result)


def render_agent_trace_page() -> None:
    st.header("Agent 执行链路")
    final_state = st.session_state.get("last_state")
    if not final_state:
        final_state = load_latest_audit_record()
        if final_state:
            st.info("当前展示的是最近一次历史审核轨迹。")
    if not final_state:
        st.info("暂无审核轨迹。请先在报销审核页面运行一次审核。")
        return

    rows = build_trace_rows(final_state)
    for index, row in enumerate(rows, start=1):
        st.markdown(
            f"""
            <div class="trace-row">
              <div class="trace-step">Step {index}</div>
              <div class="trace-title">{row['title']}</div>
              <div class="trace-detail">{row['detail']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    tool_calls = _get_state_value(final_state, "tool_calls", [])
    if tool_calls:
        st.subheader("工具调用")
        st.dataframe([_tool_row(item) for item in tool_calls], hide_index=True, use_container_width=True)


def render_eval_page() -> None:
    st.header("自动化评测")
    cases = list(load_cases())
    c1, c2, c3 = st.columns(3)
    c1.metric("测试样本数", len(cases))
    c2.metric("评测集", "test_cases.jsonl")
    c3.metric("报告目录", "reports/eval")

    if st.button("运行评测", type="primary"):
        progress = st.progress(0)
        rows = []
        workflow = FinanceComplianceWorkflow()
        for index, case in enumerate(cases, start=1):
            final_state = workflow.app.invoke(
                {
                    "claim_path": case["claim_path"],
                    "report_path": str(REPORT_DIR / "eval" / f"{case['case_id']}.md"),
                }
            )
            report = final_state["report"]
            metrics = evaluate_report(report, case)
            rows.append({"case_id": case["case_id"], "结论": report.conclusion, **metrics})
            progress.progress(index / max(len(cases), 1))
        st.session_state["eval_rows"] = rows
        st.session_state["eval_avg"] = average_metrics([{k: v for k, v in row.items() if isinstance(v, float)} for row in rows])
        st.success("评测完成。")

    rows = st.session_state.get("eval_rows", [])
    avg = st.session_state.get("eval_avg", {})
    if avg:
        metric_cols = st.columns(4)
        for index, (metric, value) in enumerate(avg.items()):
            metric_cols[index % 4].metric(METRIC_LABELS.get(metric, metric), _fmt_rate(value))

        st.subheader("指标明细")
        st.dataframe(_translate_metric_rows(rows), hide_index=True, use_container_width=True)

        st.subheader("错误类型分布")
        errors = eval_error_distribution(rows)
        if errors:
            st.dataframe(errors, hide_index=True, use_container_width=True)
        else:
            st.success("当前评测集未发现错误样本。")


def render_data_flywheel_page() -> None:
    st.header("数据飞轮")
    audit_logs = read_jsonl(FLYWHEEL_DIR / "audit_logs.jsonl")
    feedback = read_jsonl(FLYWHEEL_DIR / "feedback.jsonl")
    hard_cases = read_jsonl(FLYWHEEL_DIR / "hard_cases.jsonl")
    synthetic = read_jsonl(FLYWHEEL_DIR / "synthetic_cases.jsonl")
    sft_rows = read_jsonl(POST_TRAINING_DIR / "sft_data.jsonl")
    dpo_rows = read_jsonl(POST_TRAINING_DIR / "dpo_pairs.jsonl")

    cols = st.columns(6)
    cols[0].metric("审核轨迹", len(audit_logs))
    cols[1].metric("人工反馈", len(feedback))
    cols[2].metric("Hard Cases", len(hard_cases))
    cols[3].metric("Synthetic", len(synthetic))
    cols[4].metric("SFT 样本", len(sft_rows))
    cols[5].metric("DPO 对", len(dpo_rows))

    action_col, feedback_col = st.columns([0.78, 1.22])
    with action_col:
        st.subheader("飞轮动作")
        if st.button("挖掘 Hard Case", use_container_width=True):
            mined = HardCaseMiner().mine()
            st.success(f"已挖掘 {len(mined)} 条 hard case。")
        if st.button("生成 Synthetic Data", use_container_width=True):
            output = SyntheticCaseGenerator().write()
            st.success(f"已写入 {output}。")
        if st.button("构建 SFT 数据", use_container_width=True):
            output = SFTDataBuilder().build()
            st.success(f"已写入 {output}。")
        if st.button("构建 DPO 偏好对", use_container_width=True):
            output = DPOPairBuilder().build()
            st.success(f"已写入 {output}。")

    with feedback_col:
        st.subheader("人工审核反馈")
        claim_options = [row.get("claim_id", "unknown") for row in audit_logs[-30:]]
        claim_id = st.selectbox("样本 ID", claim_options or ["RC-2026-DEMO"])
        is_correct = st.checkbox("结论正确", value=True)
        error_type = st.selectbox(
            "错误类型",
            ["", "retrieval_miss", "citation_error", "rule_error", "amount_error", "hallucination", "missing_material"],
            disabled=is_correct,
        )
        comment = st.text_area("反馈说明", height=80)
        fixed_answer = st.text_area("修正答案", height=80, disabled=is_correct)
        if st.button("提交反馈", type="primary"):
            record = FeedbackCollector().collect(
                claim_id=claim_id,
                is_correct=is_correct,
                comment=comment,
                error_type=error_type or None,
                fixed_answer=fixed_answer or None,
            )
            st.success(f"已记录反馈：{record['claim_id']}")

    st.subheader("最近审核轨迹")
    st.dataframe([_audit_log_row(row) for row in audit_logs[-20:]][::-1], hide_index=True, use_container_width=True)

    st.subheader("错误样本与反馈闭环")
    feedback_rows = [
        {
            "样本 ID": row.get("claim_id"),
            "是否正确": row.get("is_correct"),
            "错误类型": row.get("error_type") or "-",
            "反馈": row.get("comment") or "-",
            "修正答案": row.get("fixed_answer") or "-",
            "时间": row.get("created_at"),
        }
        for row in feedback[-30:]
    ][::-1]
    st.dataframe(feedback_rows, hide_index=True, use_container_width=True)


def render_report_history_page() -> None:
    st.header("审核报告记录")
    reports = sorted(REPORT_DIR.rglob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not reports:
        st.info("暂无报告。")
        return
    options = {str(path.relative_to(ROOT)): path for path in reports}
    selected_label = st.selectbox("选择报告", list(options.keys()))
    selected_path = options[selected_label]
    markdown = selected_path.read_text(encoding="utf-8")
    st.download_button(
        "下载 Markdown 报告",
        data=markdown,
        file_name=selected_path.name,
        mime="text/markdown",
        use_container_width=True,
    )
    st.markdown(markdown)


def render_audit_result(final_state: dict[str, Any]) -> None:
    report = _get_state_value(final_state, "report")
    reward = _get_state_value(final_state, "reward")
    report_dict = model_to_dict(report)
    findings = report_dict.get("findings", [])
    failed = [item for item in findings if not item.get("passed", True)]
    evidence = report_dict.get("evidence", [])

    st.subheader("审核结果")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("审核结论", report_dict.get("conclusion"))
    c2.metric("风险等级", RISK_LABELS.get(report_dict.get("risk_level"), report_dict.get("risk_level")))
    c3.metric("风险项", len(failed))
    c4.metric("Reward", _reward_value(reward))

    for item in failed or findings:
        st.markdown(
            f"""
            <div class="finding-box">
              <div class="finding-title">{item.get('risk_type', 'risk')}</div>
              <div>{item.get('reason', '')}</div>
              <div class="finding-meta">期望：{item.get('expected') or '-'} | 实际：{item.get('actual') or '-'} | 建议：{item.get('suggestion') or '-'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("制度依据")
    evidence_rows = [
        {
            "条款": item.get("clause_id"),
            "标题": item.get("title"),
            "文件": item.get("metadata", {}).get("source_file"),
            "页码": item.get("metadata", {}).get("source_page"),
            "命中分": round(float(item.get("score", 0)), 4),
            "内容": item.get("text", "")[:140],
        }
        for item in evidence
    ]
    st.dataframe(evidence_rows, hide_index=True, use_container_width=True)

    st.subheader("Markdown 审核报告")
    report_path = Path(_get_state_value(final_state, "report_path", REPORT_DIR / "ui_audit_report.md"))
    markdown = report_dict.get("markdown") or (report_path.read_text(encoding="utf-8") if report_path.exists() else "")
    st.download_button(
        "下载本次报告",
        data=markdown,
        file_name=report_path.name,
        mime="text/markdown",
        use_container_width=True,
    )
    st.markdown(markdown)


def import_policy_file(policy_file, doc_type: str, doc_type_label: str, effective_date: str, department: str):
    saved_path = save_upload(policy_file, "policies")
    parser = PolicyParser()
    clauses = parser.parse(saved_path)
    for clause in clauses:
        clause.doc_type = doc_type
        clause.effective_date = effective_date
        clause.department = department
        clause.metadata.update(
            {
                "doc_name": policy_file.name,
                "doc_type_label": doc_type_label,
                "department": department,
                "status": "已入库",
                "index_status": "已生成",
                "index_type": "MVP BM25 + metadata index",
            }
        )
    output_path = POLICY_DIR / f"ui_{_safe_stem(policy_file.name)}.jsonl"
    parser.write_jsonl(clauses, output_path)
    return output_path, clauses


def prepare_claim_for_audit(claim_path: Path, invoice_path: Path | None, approval_path: Path | None) -> Path:
    claim = ClaimParser().parse(claim_path)
    if invoice_path and str(invoice_path) not in claim.attachments:
        claim.attachments.append(str(invoice_path))
    if approval_path and str(approval_path) not in claim.approval_files:
        claim.approval_files.append(str(approval_path))
    runtime_dir = UPLOAD_DIR / "runtime_claims"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    output_path = runtime_dir / f"{_safe_stem(claim.claim_id)}_prepared.json"
    output_path.write_text(json.dumps(model_to_dict(claim), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def execute_audit(claim_path: Path, prompt: str) -> dict[str, Any]:
    report_path = REPORT_DIR / "ui_audit_report.md"
    workflow = FinanceComplianceWorkflow()
    return workflow.app.invoke(
        {
            "claim_path": str(claim_path),
            "report_path": str(report_path),
            "user_id": "streamlit_user",
            "query": prompt,
        }
    )


def build_trace_rows(state: dict[str, Any]) -> list[dict[str, str]]:
    claim = model_to_dict(_get_state_value(state, "claim", {}))
    intent = model_to_dict(_get_state_value(state, "intent", {}))
    evidence = [model_to_dict(item) for item in _get_state_value(state, "evidence", [])]
    findings = [model_to_dict(item) for item in _get_state_value(state, "findings", [])]
    report = model_to_dict(_get_state_value(state, "report", {}))
    plan = _get_state_value(state, "plan", [])

    hotel_item = next((item for item in claim.get("items", []) if item.get("item_type") == "hotel"), {})
    failed = [item for item in findings if not item.get("passed", True)]
    first_evidence = evidence[0] if evidence else {}

    return [
        {
            "title": "识别任务类型",
            "detail": f"结果：{intent.get('task_type', 'reimbursement_audit')}；置信度：{intent.get('confidence', 1.0)}",
        },
        {
            "title": "解析报销单",
            "detail": (
                f"城市={claim.get('trip_city', '-')}，员工级别={claim.get('employee_level', '-')}，"
                f"住宿费={hotel_item.get('amount', '-')}，审批链={','.join(claim.get('approval_chain', [])) or '-'}"
            ),
        },
        {
            "title": "OCR 识别发票",
            "detail": (
                f"附件数={len(claim.get('attachments', []))}，发票类型={hotel_item.get('invoice_type') or '-'}，"
                f"金额={hotel_item.get('amount', '-')}，日期={hotel_item.get('date') or '-'}"
            ),
        },
        {
            "title": "检索制度",
            "detail": (
                f"命中：{first_evidence.get('metadata', {}).get('source_file', '-')} "
                f"{first_evidence.get('clause_id', '-')}；召回条款数={len(evidence)}"
            ),
        },
        {
            "title": "调用规则引擎",
            "detail": "；".join([f"{item.get('risk_type')}={'通过' if item.get('passed') else '不通过'}" for item in findings]) or "-",
        },
        {
            "title": "Verifier 校验证据",
            "detail": "结论有制度依据，无缺失证据。" if not _get_state_value(state, "missing_info", []) else "存在缺失信息，需要人工补充。",
        },
        {
            "title": "生成审核报告",
            "detail": f"状态：完成；结论={report.get('conclusion', '-')}；风险等级={RISK_LABELS.get(report.get('risk_level'), report.get('risk_level', '-'))}；计划步骤={len(plan)}",
        },
    ]


def load_policy_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chunks = []
    inventory: dict[str, dict[str, Any]] = {}
    for path in sorted(POLICY_DIR.glob("*.jsonl")):
        for record in read_jsonl(path):
            record["_jsonl_file"] = path.name
            chunks.append(record)
            doc_name = _policy_doc_name(record)
            row = inventory.setdefault(
                doc_name,
                {
                    "文档名称": doc_name,
                    "文档类型": record.get("metadata", {}).get("doc_type_label") or record.get("doc_type"),
                    "生效日期": record.get("effective_date"),
                    "适用部门": record.get("department"),
                    "状态": record.get("metadata", {}).get("status", "已入库"),
                    "chunk 数量": 0,
                    "索引状态": record.get("metadata", {}).get("index_status", "已生成"),
                    "索引类型": record.get("metadata", {}).get("index_type", "JSONL policy store"),
                },
            )
            row["chunk 数量"] += 1
    return list(inventory.values()), chunks


def load_latest_audit_record() -> dict[str, Any] | None:
    rows = read_jsonl(FLYWHEEL_DIR / "audit_logs.jsonl")
    if not rows:
        return None
    row = rows[-1]
    return {
        "plan": row.get("plan", []),
        "tool_calls": row.get("tool_calls", []),
        "evidence": row.get("evidence", []),
        "findings": row.get("findings", []),
        "report": {
            "claim_id": row.get("claim_id"),
            "conclusion": row.get("conclusion"),
            "risk_level": row.get("risk_level"),
            "findings": row.get("findings", []),
            "evidence": row.get("evidence", []),
            "markdown": Path(row.get("report_path", "")).read_text(encoding="utf-8")
            if row.get("report_path") and Path(row.get("report_path")).exists()
            else "",
        },
        "report_path": row.get("report_path"),
        "reward": row.get("reward", {}),
    }


def eval_error_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter = Counter()
    for row in rows:
        if row.get("evidence_recall", 1.0) < 1.0:
            counter["检索未命中"] += 1
        if row.get("citation_accuracy", 1.0) < 1.0:
            counter["引用条款错误"] += 1
        if row.get("rule_accuracy", 1.0) < 1.0:
            counter["规则判断错误"] += 1
        if row.get("risk_type_recall", 1.0) < 1.0:
            counter["风险分类错误"] += 1
        if row.get("hallucination_rate", 0.0) > 0.0:
            counter["幻觉输出"] += 1
    return [{"错误类型": key, "数量": value} for key, value in counter.items()]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def save_upload(uploaded_file, folder: str) -> Path:
    if uploaded_file is None:
        raise ValueError("No uploaded file provided.")
    target_dir = UPLOAD_DIR / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / _safe_filename(uploaded_file.name)
    path.write_bytes(uploaded_file.getbuffer())
    return path


def model_to_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, list):
        return [model_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: model_to_dict(item) for key, item in value.items()}
    return value


def _resolve_claim_path(claim_file, use_sample: bool) -> Path:
    if claim_file:
        return save_upload(claim_file, "reimbursements")
    if use_sample:
        return SAMPLE_DIR / "claim_from_excel.xlsx"
    raise ValueError("请上传报销单，或勾选内置示例。")


def _sample_invoice_path(use_sample: bool) -> Path | None:
    return SAMPLE_DIR / "invoice_hotel_680.txt" if use_sample else None


def _sample_approval_path(use_sample: bool) -> Path | None:
    return SAMPLE_DIR / "approval_flow.txt" if use_sample else None


def _policy_doc_name(record: dict[str, Any]) -> str:
    return record.get("metadata", {}).get("doc_name") or record.get("source_file") or record.get("_jsonl_file", "unknown")


def _audit_log_row(row: dict[str, Any]) -> dict[str, Any]:
    reward = row.get("reward", {})
    return {
        "时间": row.get("logged_at"),
        "样本 ID": row.get("claim_id"),
        "结论": row.get("conclusion"),
        "风险等级": RISK_LABELS.get(row.get("risk_level"), row.get("risk_level")),
        "风险类型": ",".join([item.get("risk_type", "") for item in row.get("findings", []) if not item.get("passed", True)]),
        "Reward": reward.get("total_score") if isinstance(reward, dict) else "",
        "报告": row.get("report_path"),
    }


def _tool_row(item: Any) -> dict[str, Any]:
    data = model_to_dict(item)
    return {
        "工具": data.get("tool_name"),
        "目的": data.get("purpose"),
        "状态": data.get("status"),
        "输入": json.dumps(data.get("inputs", {}), ensure_ascii=False),
    }


def _translate_metric_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    translated = []
    for row in rows:
        item = {"case_id": row.get("case_id"), "结论": row.get("结论")}
        for key, value in row.items():
            if key in METRIC_LABELS:
                item[METRIC_LABELS[key]] = _fmt_rate(value)
        translated.append(item)
    return translated


def _contract_suggestion(risk: str) -> str:
    suggestions = {
        "prepayment_over_30_percent": "补充更高层级审批，或将付款拆分到验收节点后。",
        "missing_acceptance_clause": "补充验收标准、验收节点和付款触发条件。",
        "auto_renewal_clause": "补充续约提醒和人工确认流程。",
    }
    return suggestions.get(risk, "进入人工复核。")


def _get_state_value(state: dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _reward_value(reward: Any) -> str:
    data = model_to_dict(reward)
    if isinstance(data, dict) and "total_score" in data:
        return str(data["total_score"])
    return "-"


def _fmt_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", name).strip()
    return cleaned or "uploaded_file"


def _safe_stem(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", Path(name).stem).strip("_") or "policy"


def _ensure_dirs() -> None:
    for path in [POLICY_DIR, SAMPLE_DIR, UPLOAD_DIR, REPORT_DIR, FLYWHEEL_DIR, POST_TRAINING_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### FinCompliance-Agent")
        current = st.session_state.get("page", NAV_ITEMS[1])
        for item in NAV_ITEMS:
            if st.button(item, key=f"nav_{item}", use_container_width=True, type="primary" if item == current else "secondary"):
                st.session_state["page"] = item
                st.rerun()
        st.divider()
        st.caption("MVP + v2 + v3 能力已合并到当前工作台。")


def _inject_style() -> None:
    st.html(
        """
        <style>
        .block-container { padding-top: 7rem; max-width: 1280px; }
        .app-title { font-size: 1.7rem; font-weight: 760; color: #1f2937; line-height: 1.25; margin-top: 1.5rem; }
        .app-subtitle { color: #64748b; margin: 0.25rem 0 1.2rem 0; }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.85rem 0.95rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .finding-box {
            border: 1px solid #f2c36b;
            background: #fff8eb;
            border-radius: 8px;
            padding: 0.85rem 0.95rem;
            margin: 0.65rem 0;
        }
        .finding-title { font-weight: 720; color: #92400e; margin-bottom: 0.25rem; }
        .finding-meta { color: #6b7280; font-size: 0.9rem; margin-top: 0.35rem; }
        .trace-row {
            display: grid;
            grid-template-columns: 88px 180px 1fr;
            gap: 0.75rem;
            align-items: center;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.82rem 0.9rem;
            margin: 0.55rem 0;
            background: #ffffff;
        }
        .trace-step {
            color: #0f766e;
            font-weight: 760;
            font-size: 0.92rem;
        }
        .trace-title { font-weight: 720; color: #111827; }
        .trace-detail { color: #475569; }
        @media (max-width: 760px) {
            .trace-row { grid-template-columns: 1fr; }
        }
        </style>
        """
    )


if __name__ == "__main__":
    main()
