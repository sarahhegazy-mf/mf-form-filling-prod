from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Callable, Optional, Tuple

import streamlit as st
from google import genai

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
MAX_DOC_CHARS = int(os.getenv("GEMINI_MAX_DOC_CHARS", "20000"))
MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "8192"))
FIELD_BATCH_SIZE = int(os.getenv("GEMINI_FIELD_BATCH_SIZE", "12"))


def _get_client() -> genai.Client:
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing. Add it to .streamlit/secrets.toml")
    return genai.Client(api_key=api_key)


def _trim_docs(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= MAX_DOC_CHARS:
        return text
    head = text[: int(MAX_DOC_CHARS * 0.75)]
    tail = text[-int(MAX_DOC_CHARS * 0.25) :]
    return head + "\n\n--- TRUNCATED ---\n\n" + tail


def _extract_json_object(raw: str) -> str:
    raw = (raw or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]
    # Remove trailing commas before } or ]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return raw.strip()


def _parse_json(raw: str) -> Dict[str, Any]:
    candidate = _extract_json_object(raw)
    return json.loads(candidate)


def _call_model(
    client: genai.Client,
    bank_name: str,
    pdf_text: str,
    fields: List[str],
) -> Dict[str, Any]:
    docs = _trim_docs(pdf_text)

    prompt = f"""You are a mortgage operations assistant.

Extract ONLY the requested fields for bank: "{bank_name}" from the DOCUMENTS.

Return ONLY valid JSON (no markdown, no explanations).
The JSON must be a single object where keys EXACTLY match the provided field names.

For each field value, return an object:
- "value": string | number | null
- "confidence": number between 0 and 1
- "evidence": a short snippet from the documents, or null

Rules:
- Do not invent values.
- If missing, use null and confidence 0.
- Numbers must be numeric (no commas, no currency symbols).
- Do not include trailing commas.

FIELDS:
{json.dumps(fields, ensure_ascii=False, indent=2)}

DOCUMENTS:
{docs}
""".strip()

    resp = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=prompt,
        config={
            "temperature": 0,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "response_mime_type": "application/json",
        },
    )

    raw = (resp.text or "").strip()
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini did not return a JSON object.")
    return parsed


def _split_in_half(items: List[str]) -> Tuple[List[str], List[str]]:
    mid = max(1, len(items) // 2)
    return items[:mid], items[mid:]


def extract_fields_with_genai(
    pdf_text: str,
    field_list: List[str],
    bank_name: str,
    on_partial_update: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Extract fields using Gemini with safe batching.

    - Requests fields in batches to avoid truncation/invalid JSON
    - If a batch fails, recursively splits into smaller batches
    - Calls on_partial_update(bank_name, partial_dict) after each successful batch
    """
    client = _get_client()

    # Deduplicate while preserving order
    seen = set()
    fields = []
    for f in field_list:
        if f not in seen:
            fields.append(f)
            seen.add(f)

    results: Dict[str, Any] = {}

    def run_batch(batch: List[str]) -> Dict[str, Any]:
        try:
            out = _call_model(client, bank_name, pdf_text, batch)
            return out
        except Exception:
            if len(batch) <= 1:
                # soft-fail single field
                f = batch[0]
                return {f: {"value": None, "confidence": 0.0, "evidence": None}}
            left, right = _split_in_half(batch)
            out = {}
            out.update(run_batch(left))
            out.update(run_batch(right))
            return out

    for i in range(0, len(fields), max(1, FIELD_BATCH_SIZE)):
        batch = fields[i : i + FIELD_BATCH_SIZE]
        partial = run_batch(batch)
        results.update(partial)
        if on_partial_update:
            on_partial_update(bank_name, partial)

    return results
