import re
from pathlib import Path
from typing import Dict, List


class ContractParser:
    def parse(self, path: str | Path) -> Dict:
        text = self._extract_text(Path(path))
        return {
            "amount": self._extract_amount(text),
            "prepayment_ratio": self._extract_prepayment_ratio(text),
            "has_acceptance_clause": "验收" in text,
            "risk_hints": self.extract_risk_hints(text),
            "raw_text": text,
        }

    def _extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8")
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError as error:
                raise ImportError("Install pypdf to parse PDF contracts: pip install pypdf") from error
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        raise ValueError(f"Unsupported contract file type: {path.suffix}")

    def extract_risk_hints(self, text: str) -> List[str]:
        risks = []
        ratio = self._extract_prepayment_ratio(text)
        if ratio is not None and ratio > 0.3:
            risks.append("prepayment_over_30_percent")
        if "验收" not in text:
            risks.append("missing_acceptance_clause")
        if "自动续约" in text:
            risks.append("auto_renewal_clause")
        return risks

    def _extract_amount(self, text: str):
        match = re.search(r"金额[:：]?\s*([0-9]+(?:\.[0-9]+)?)", text)
        return float(match.group(1)) if match else None

    def _extract_prepayment_ratio(self, text: str):
        match = re.search(r"预付款(?:比例)?[:：]?\s*([0-9]+)%", text)
        if match:
            return float(match.group(1)) / 100
        return None
