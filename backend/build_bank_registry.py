from __future__ import annotations

import re
from pathlib import Path
import pandas as pd
from pypdf import PdfReader

BANK_FORMS_DIR = Path("assets/bank_forms")
OUT_DIR = Path("backend/registry_store")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _pdf_to_text(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for p in reader.pages:
        parts.append(p.extract_text() or "")
    return "\n".join(parts)


def _guess_fields(text: str) -> list[str]:
    """Heuristically propose form fields from a bank form PDF.

    This is a bootstrapper. In production, review the CSV and clean field names.
    """
    fields = set()

    for raw in text.splitlines():
        line = " ".join(raw.strip().split())
        if not line:
            continue

        # Label: ______
        if ":" in line and len(line) <= 120:
            label = line.split(":", 1)[0].strip()
            if 3 <= len(label) <= 70:
                fields.add(label)

        # Underscore runs like "Employer Name _______"
        if re.search(r"_{4,}", raw):
            left = re.split(r"_{4,}", raw)[0].strip()
            left = " ".join(left.split())
            if 3 <= len(left) <= 80:
                fields.add(left)

        # Checkbox style prompts
        if re.search(r"\[\s*\]|\(\s*\)", raw):
            cleaned = re.sub(r"\[\s*\]|\(\s*\)", "", line).strip()
            if 3 <= len(cleaned) <= 80:
                fields.add(cleaned)

    # Remove obvious junk
    blacklist = [
        "signature", "for bank use", "office use", "page", "date:", "stamp", "branch",
        "terms and conditions", "declaration"
    ]
    out = []
    for f in fields:
        fl = f.lower()
        if any(b in fl for b in blacklist):
            continue
        out.append(f)

    return sorted(out)


def main() -> None:
    if not BANK_FORMS_DIR.exists():
        raise FileNotFoundError(f"{BANK_FORMS_DIR} not found. Put PDFs in assets/bank_forms/")

    rows = []
    for pdf in sorted(BANK_FORMS_DIR.glob("*.pdf")):
        bank = pdf.stem.replace("_Mortgage_App", "").replace("_", " ").strip()
        text = _pdf_to_text(pdf)
        for field in _guess_fields(text):
            rows.append({"bank": bank, "field": field, "required": True})

    df = pd.DataFrame(rows).drop_duplicates()
    out_csv = OUT_DIR / "bank_registry.csv"
    df.to_csv(out_csv, index=False)
    print(f"Saved registry -> {out_csv} ({len(df)} rows)")
    print(df.groupby("bank")["field"].count().sort_values(ascending=False))


if __name__ == "__main__":
    main()
