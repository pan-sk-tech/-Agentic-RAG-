import json
from pathlib import Path

from fin_compliance.domain.schemas import UserProfile


DEFAULT_USER_MEMORY_PATH = Path("fin_compliance/memory/user_profiles.json")


class UserMemory:
    def __init__(self, path: Path | str = DEFAULT_USER_MEMORY_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                json.dumps(
                    {
                        "default_user": {
                            "user_id": "default_user",
                            "role": "finance_reviewer",
                            "department": "finance",
                            "preferences": {
                                "policy_version": "latest",
                                "report_language": "zh-CN",
                            },
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def get(self, user_id: str = "default_user") -> UserProfile:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        profile = data.get(user_id) or data["default_user"]
        return UserProfile(**profile)

    def update_feedback_preference(self, user_id: str, key: str, value):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        profile = data.setdefault(user_id, data["default_user"].copy())
        profile.setdefault("preferences", {})[key] = value
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
