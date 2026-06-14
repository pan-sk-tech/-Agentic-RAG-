import json
import re
from pathlib import Path
from typing import Iterable, List

from fin_compliance.domain.schemas import PolicyClause


class PolicyParser:
    """Parse policy PDF/text files into structured policy clauses.

    PDF parsing uses optional `pypdf`. Text and Markdown files work without
    extra dependencies, which keeps the demo runnable on a clean machine.
    """

    def parse(self, path: str | Path, output_path: str | Path | None = None) -> List[PolicyClause]:
        path = Path(path)
        text = self._extract_text(path)
        clauses = self._extract_clauses(text, source_file=path.name)
        if output_path:
            self.write_jsonl(clauses, output_path)
        return clauses

    def write_jsonl(self, clauses: Iterable[PolicyClause], output_path: str | Path) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            for clause in clauses:
                data = clause.model_dump() if hasattr(clause, "model_dump") else clause.dict()
                file.write(json.dumps(data, ensure_ascii=False) + "\n")
        return str(output_path)

    def _extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8")
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError as error:
                raise ImportError("Install pypdf to parse PDF policies: pip install pypdf") from error
            reader = PdfReader(str(path))
            pages = []
            for index, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                pages.append(f"\n[PAGE {index}]\n{page_text}")
            return "\n".join(pages)
        raise ValueError(f"Unsupported policy file type: {path.suffix}")

    def _extract_clauses(self, text: str, source_file: str) -> List[PolicyClause]:
        chunks = self._split_into_clause_chunks(text)
        return [
            self._chunk_to_clause(index=index, chunk=chunk, source_file=source_file)
            for index, chunk in enumerate(chunks, start=1)
        ]

    def _split_into_clause_chunks(self, text: str) -> List[str]:
        matches = list(re.finditer(r"(?m)^\s*(?:第\s*)?\d+(?:\.\d+)+\s*(?:条|、|\.|：|:)?", text))
        if matches:
            chunks = []
            for index, match in enumerate(matches):
                start = match.start()
                end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                chunk = text[start:end].strip()
                if chunk:
                    chunks.append(chunk)
            return chunks

        pattern = re.compile(r"(?=(?:第\s*)?\d+(?:\.\d+)+\s*(?:条|、|\.|：|:))")
        parts = [part.strip() for part in pattern.split(text) if part.strip()]
        if len(parts) <= 1:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return ["\n".join(lines[index:index + 4]) for index in range(0, len(lines), 4)]
        return parts

    def _chunk_to_clause(self, index: int, chunk: str, source_file: str) -> PolicyClause:
        clause_id = self._extract_clause_id(chunk, index)
        title = self._extract_title(chunk, clause_id)
        risk_type = self._infer_risk_type(chunk)
        doc_type = self._infer_doc_type(chunk)
        source_page = self._extract_page(chunk) or index
        tags = self._infer_tags(chunk)
        return PolicyClause(
            clause_id=clause_id,
            doc_type=doc_type,
            title=title,
            text=self._clean_text(chunk),
            department="finance",
            effective_date="2025-01-01",
            policy_level="company",
            risk_type=risk_type,
            source_page=source_page,
            source_file=source_file,
            tags=tags,
        )

    def _extract_clause_id(self, chunk: str, index: int) -> str:
        match = re.search(r"(\d+(?:\.\d+)+)", chunk)
        return f"TRAVEL-{match.group(1)}" if match else f"POLICY-{index:03d}"

    def _extract_title(self, chunk: str, clause_id: str) -> str:
        first_line = chunk.strip().splitlines()[0]
        first_line = re.sub(r"\s+", " ", first_line)
        return first_line[:60] if first_line else clause_id

    def _extract_page(self, chunk: str):
        match = re.search(r"\[PAGE\s+(\d+)\]", chunk)
        return int(match.group(1)) if match else None

    def _clean_text(self, chunk: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"\[PAGE\s+\d+\]", "", chunk)).strip()

    def _infer_doc_type(self, text: str) -> str:
        if "合同" in text or "付款" in text:
            return "contract_policy"
        if "审批" in text:
            return "approval_policy"
        if "发票" in text or "抬头" in text:
            return "invoice_policy"
        return "reimbursement_policy"

    def _infer_risk_type(self, text: str) -> str:
        rules = [
            ("住宿", "hotel_fee_over_limit"),
            ("餐饮", "meal_fee_over_limit"),
            ("日期", "invoice_date_out_of_trip"),
            ("抬头", "invoice_title_mismatch"),
            ("审批", "approval_chain_missing"),
            ("交通", "transport_policy_violation"),
            ("重复", "duplicate_reimbursement"),
            ("供应商", "supplier_name_mismatch"),
            ("合同", "contract_payment_risk"),
        ]
        for keyword, risk_type in rules:
            if keyword in text:
                return risk_type
        return "missing_material"

    def _infer_tags(self, text: str) -> List[str]:
        candidates = ["差旅", "住宿", "北京", "一线城市", "餐饮", "发票", "审批", "交通", "合同", "供应商"]
        return [tag for tag in candidates if tag in text]
