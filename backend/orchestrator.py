from __future__ import annotations

from typing import Any, Dict, Callable, Optional

from backend.bank_registry import required_fields_for_bank
from backend.llm import extract_fields_with_genai
from backend.validator import validate


def process_bank(
    bank_name: str,
    pdf_text: str,
    confidence_threshold: float = 0.6,
    on_partial_update: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    fields = required_fields_for_bank(bank_name)

    extracted = extract_fields_with_genai(
        pdf_text=pdf_text,
        field_list=fields,
        bank_name=bank_name,
        on_partial_update=on_partial_update,
    )

    missing, normalized = validate(
        extracted=extracted,
        required=fields,
        confidence_threshold=confidence_threshold,
    )

    avg_conf = (
        sum(v.get("confidence", 0.0) for v in normalized.values()) / max(1, len(normalized))
    )

    return {
        "bank": bank_name,
        "confidence": round(avg_conf, 2),
        "missing_fields": missing,
        "fields": normalized,
    }
