import json
import re
from pathlib import Path
from typing import Dict


class InvoiceOCR:
    """Deterministic OCR adapter for the MVP.

    For image files, put a sidecar JSON next to the image:
    `invoice.png` -> `invoice.json`. This keeps the workflow runnable without
    native OCR dependencies while preserving the same interface for PaddleOCR or
    Tesseract integration.
    """

    def extract(self, path: str | Path) -> Dict:
        path = Path(path)
        sidecar = path.with_suffix(".json")
        if sidecar.exists():
            return json.loads(sidecar.read_text(encoding="utf-8"))
        if path.suffix.lower() in {".txt", ".ocr"}:
            return self._extract_from_text(path.read_text(encoding="utf-8"))
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
            text = self._extract_text_from_image(path)
            return self._extract_from_text(text)
        raise FileNotFoundError(
            f"No OCR sidecar found for {path}. Provide {sidecar.name}, a .txt OCR result, or install Pillow+pytesseract."
        )

    def _extract_text_from_image(self, path: Path) -> str:
        try:
            from PIL import Image
            import pytesseract
        except ImportError as error:
            raise ImportError(
                "Image OCR requires Pillow and pytesseract. "
                "Install them or provide a sidecar JSON/OCR text file."
            ) from error
        return pytesseract.image_to_string(Image.open(path), lang="chi_sim+eng")

    def _extract_from_text(self, text: str) -> Dict:
        amount_match = re.search(r"(?:金额|价税合计|合计)[:：]?\s*([0-9]+(?:\.[0-9]+)?)", text)
        date_match = re.search(r"(20\d{2}[-/]\d{1,2}[-/]\d{1,2})", text)
        buyer_match = re.search(r"(?:购买方|抬头)[:：]\s*([^\n]+)", text)
        seller_match = re.search(r"(?:销售方|供应商)[:：]\s*([^\n]+)", text)
        return {
            "invoice_type": "住宿发票" if "住宿" in text or "酒店" in text else "普通发票",
            "amount": float(amount_match.group(1)) if amount_match else None,
            "date": date_match.group(1).replace("/", "-") if date_match else None,
            "buyer_name": buyer_match.group(1).strip() if buyer_match else None,
            "seller_name": seller_match.group(1).strip() if seller_match else None,
        }
