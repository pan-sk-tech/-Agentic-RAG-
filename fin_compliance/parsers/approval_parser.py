import json
from pathlib import Path
from typing import List


class ApprovalParser:
    ROLE_MAP = {
        "员工提交": "employee_submit",
        "提交": "employee_submit",
        "直属经理": "department_manager",
        "部门经理": "department_manager",
        "部门负责人": "department_manager",
        "财务负责人": "finance_director",
        "财务总监": "finance_director",
    }

    def parse(self, path: str | Path) -> List[str]:
        path = Path(path)
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(item) for item in data]
            return [str(item) for item in data.get("approval_chain", [])]
        text = path.read_text(encoding="utf-8")
        chain = []
        for keyword, role in self.ROLE_MAP.items():
            if keyword in text and role not in chain:
                chain.append(role)
        return chain

