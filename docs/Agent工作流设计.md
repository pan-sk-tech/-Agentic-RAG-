# Agent 工作流设计

当前 LangGraph 节点顺序：

```text
parse_claim
  -> classify_intent
  -> load_memory
  -> plan_audit
  -> route_tools
  -> retrieve_policy
  -> apply_rules
  -> verify_evidence
  -> write_report
  -> score_reward
  -> persist_memory
```

## 关键设计

- `ComplianceState` 保存 claim、intent、plan、tool_calls、evidence、findings、report、reward。
- Planner 生成审核计划，ToolRouter 决定需要调用的工具。
- Retriever 找制度依据，RuleEngine 做确定性判断。
- Verifier 检查未通过风险是否绑定真实 evidence。
- ReportAgent 输出可解释报告。
- Memory 和 data flywheel 记录 trajectory，为后续优化提供数据。
