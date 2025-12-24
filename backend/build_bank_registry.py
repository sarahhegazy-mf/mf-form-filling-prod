from __future__ import annotations

import re
from pathlib import Path
import pandas as pd
from pypdf import PdfReader

BANK_FORMS_DIR = Path("assets/bank_forms")
OUT_DIR = Path("backend/registry_store")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAPPING_SEED = Path("config/mappings/field_mapping_seed.csv")


def _pdf_to_text(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for p in reader.pages:
        parts.append(p.extract_text() or "")
    return "\n".join(parts)


def _guess_labels(text: str) -> list[str]:
    labels = set()
    for raw in text.splitlines():
        line = " ".join(raw.strip().split())
        if not line:
            continue

        if ":" in line and len(line) <= 140:
            label = line.split(":", 1)[0].strip()
            if 3 <= len(label) <= 80:
                labels.add(label)

        if re.search(r"_{4,}", raw):
            left = re.split(r"_{4,}", raw)[0].strip()
            left = " ".join(left.split())
            if 3 <= len(left) <= 90:
                labels.add(left)

    blacklist = [
        "signature", "for bank use", "office use", "page", "stamp", "branch",
        "terms and conditions", "declaration", "please tick", "notes"
    ]
    out = []
    for l in labels:
        if any(b in l.lower() for b in blacklist):
            continue
        out.append(l)
    return sorted(out)


def _load_mapping_seed() -> list[tuple[str, str]]:
    if not MAPPING_SEED.exists():
        return []
    df = pd.read_csv(MAPPING_SEED)
    pairs = []
    for _, r in df.iterrows():
        pat = str(r.get("pattern", "")).strip().lower()
        key = str(r.get("canonical_key", "")).strip()
        if pat and key:
            pairs.append((pat, key))
    return pairs


def _map_label(label: str, mapping: list[tuple[str, str]]) -> str:
    ll = label.lower()
    for pat, key in mapping:
        if pat in ll:
            return key
    return ""


def main() -> None:
    if not BANK_FORMS_DIR.exists():
        raise FileNotFoundError(f"{BANK_FORMS_DIR} not found. Put PDFs in assets/bank_forms/")

    mapping = _load_mapping_seed()
    rows = []
    for pdf in sorted(BANK_FORMS_DIR.glob("*.pdf")):
        bank = pdf.stem.replace("_Mortgage_App", "").replace("_", " ").strip()
        text = _pdf_to_text(pdf)
        for label in _guess_labels(text):
            rows.append(
                {
                    "bank": bank,
                    "bank_label": label,
                    "canonical_key": _map_label(label, mapping),
                    "required": True,
                    "section": "",
                }
            )

    df = pd.DataFrame(rows).drop_duplicates()
    out_csv = OUT_DIR / "bank_registry.csv"
    df.to_csv(out_csv, index=False)
    print(f"Saved registry -> {out_csv} ({len(df)} rows)")
    print("Tip: fill 'canonical_key' for unmapped labels, and set required=False for optional fields.")


if __name__ == "__main__":
    main()
