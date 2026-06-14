# FinCompliance-Agent

企业财务合规智能审核工作台。项目面向差旅报销、发票、审批流程和合同付款审核，使用 LangGraph 编排 Agent 工作流，结合 RAG 检索、规则引擎、证据链校验、自动化评测和数据飞轮，完成从材料上传到审核报告生成的闭环。

## 核心能力

| 模块 | 能力 |
| --- | --- |
| 知识库管理 | 上传制度 PDF/TXT/MD，解析为带 metadata 的条款库 |
| 报销审核 | 解析 Excel/JSON/CSV 报销单，结合发票和审批流程完成合规判断 |
| 发票识别 | 支持 OCR 文本、sidecar JSON 和图片 OCR adapter |
| 合同审核 | 识别预付款比例、验收条款、自动续约等付款风险 |
| Agent 工作流 | LangGraph 编排 parser、planner、retriever、rule engine、verifier、report agent |
| RAG 检索 | query rewrite、BM25-style retrieval、metadata、业务 rerank、citation evidence |
| 规则引擎 | 住宿超标、餐饮超标、发票日期、发票抬头、审批链、重复报销、交通标准 |
| 自动化评测 | 结论准确率、风险召回率、证据召回率、引用准确率、幻觉率 |
| 数据飞轮 | audit trajectory、人工反馈、hard case、synthetic data、SFT/DPO 数据构建 |

## 快速启动

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

启动网站：

```powershell
.\run_ui.ps1
```

或手动启动：

```powershell
.\venv\Scripts\python.exe -m streamlit run run_web.py --server.port 8501
```

浏览器访问：

```text
http://localhost:8501
```

## 命令行验证

```powershell
python fin_compliance_cli.py audit --claim fin_compliance/data/samples/claim_from_excel.xlsx --out reports/ui_audit_report.md
python fin_compliance_cli.py eval
python fin_compliance_cli.py ocr fin_compliance/data/samples/invoice_hotel_680.txt
python fin_compliance_cli.py synthetic
python fin_compliance_cli.py hard-cases
python fin_compliance_cli.py build-sft
python fin_compliance_cli.py build-dpo
```

## API 服务

```powershell
python run_api.py
```

接口文档：

```text
http://localhost:8010/docs
```

## 项目结构

```text
FinCompliance-Agent/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── run_web.py
├── run_api.py
├── run_ui.ps1
├── configs/
├── docs/
├── fin_compliance/
│   ├── app/
│   ├── agents/
│   ├── domain/
│   ├── parsers/
│   ├── rag/
│   ├── tools/
│   ├── memory/
│   ├── eval/
│   ├── data_flywheel/
│   ├── post_training/
│   └── data/
├── reports/
├── tests/
├── archive/          # 本地旧版本归档，默认不提交
└── local_runtime/    # 本地运行数据，默认不提交
```

## 演示流程

1. 进入网站首页。
2. 在“知识库管理”上传制度文件并入库。
3. 在“报销审核”上传报销单、发票和审批流程。
4. 点击“开始智能审核”。
5. 查看审核结论、风险原因、制度依据和 Markdown 报告。
6. 切到“Agent 执行链路”查看完整 trajectory。
7. 切到“自动化评测”运行指标评估。
8. 切到“数据飞轮”提交反馈并生成 hard case / SFT / DPO 数据。

## 设计原则

- LLM 不直接黑箱判断财务合规，金额、日期、审批链等确定性逻辑由规则引擎完成。
- RAG 负责找制度依据，Verifier 负责检查风险结论是否绑定真实条款。
- 每次审核都记录执行轨迹，用于评测、错误分析和后续数据飞轮优化。
