from docx import Document as Docx
from pypdf import PdfReader


def extract_text(path: str) -> tuple[str, bool]:
    low = path.lower()
    if low.endswith(".docx"):
        return "\n".join(p.text for p in Docx(path).paragraphs), False
    if low.endswith(".txt"):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(), False
    if low.endswith(".pdf"):
        try:
            text = "\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
        except Exception:
            return "", True
        return (text, False) if len(text.strip()) >= 50 else ("", True)
    return "", True
