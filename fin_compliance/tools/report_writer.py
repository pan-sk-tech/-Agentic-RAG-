import json
from pathlib import Path

from fin_compliance.domain.schemas import AuditReport


class ReportWriter:
    def write_markdown(self, report: AuditReport, path: str | Path) -> str:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.markdown, encoding="utf-8")
        return str(path)

    def write_json(self, report: AuditReport, path: str | Path) -> str:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = report.model_dump() if hasattr(report, "model_dump") else report.dict()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

