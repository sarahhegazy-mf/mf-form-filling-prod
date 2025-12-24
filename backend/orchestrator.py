from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.bank_registry import required_fields_for_bank
from backend.llm import extract_fields_with_genai
from backend.validator import validate


def _clean_required_fields(fields: List[str]) -> List[str]:
    """
    Avoid UI showing 'nan' or empty keys if registry has bad rows.
    """
    out = []
    for f in fields:
        if f is None:
            continue
        s = str(f).strip()
        if not s:
            continue
        if s.lower() == "nan":
            continue
        out.append(s)
    # de-dupe preserve order
    seen = set()
    final = []
    for x in out:
        if x not in seen:
            final.append(x)
            seen.add(x)
    return final


def _batch(items: List[str], size: int) -> List[List[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def process_bank(
    bank_name: str,
    pdf_text: str,
    confidence_threshold: float = 0.6,
    uploaded_pdfs: Optional[List[Tuple[str, bytes]]] = None,
    on_partial_update: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    batch_size: int = 25,
) -> Dict[str, Any]:
    """
    1) Load required fields for bank (canonical_key if available else bank_label)
    2) Extract fields via Gemini multimodal (prompt + attached PDFs)
    3) Validate & flag missing/low-confidence/invalid_format
    4) Return structured payload
    """
    required = _clean_required_fields(required_fields_for_bank(bank_name))
    if not required:
        return {
            "bank": bank_name,
            "fields": {},
            "missing_fields": [],
            "error": "No required fields found for this bank. Check bank_registry.csv.",
        }

    extracted_all: Dict[str, Any] = {}

    for chunk in _batch(required, batch_size):
        extracted = extract_fields_with_genai(
            pdf_text=pdf_text or "",
            field_list=chunk,
            bank_name=bank_name,
            uploaded_pdfs=uploaded_pdfs,
            max_output_tokens=2048,
        )
        # merge
        for k, v in extracted.items():
            extracted_all[k] = v

        # normalize + validate interim so UI can show “missing” correctly
        missing_now, normalized_now = validate(
            extracted=extracted_all,
            required=required,
            confidence_threshold=confidence_threshold,
        )
        if on_partial_update:
            on_partial_update(bank_name, normalized_now)

    missing, normalized = validate(
        extracted=extracted_all,
        required=required,
        confidence_threshold=confidence_threshold,
    )

    return {
        "bank": bank_name,
        "fields": normalized,
        "missing_fields": missing,
        "required_fields": required,
    }
