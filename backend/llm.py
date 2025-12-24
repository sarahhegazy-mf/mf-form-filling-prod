from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple, Optional

from google import genai
from google.genai import types


def _extract_json_object(text: str) -> str:
    """
    Pull the first top-level JSON object from model output.
    Handles cases where the model wraps JSON in extra text.
    """
    if not text:
        return ""

    # Common: ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        return fenced.group(1).strip()

    # Otherwise grab first { ... } block
    start = text.find("{")
    if start == -1:
        return ""
    # Find matching end by scanning braces
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1].strip()
    return ""


def _safe_json_load(text: str) -> Dict[str, Any]:
    raw = _extract_json_object(text) or text.strip()
    return json.loads(raw)


def _build_prompt(bank_name: str, field_list: List[str], pdf_text: str) -> str:
    fields = "\n".join([f"- {f}" for f in field_list])
    return f"""
You are a mortgage operations assistant.

TASK:
Extract ONLY the requested fields for bank: "{bank_name}" from the provided DOCUMENTS.

IMPORTANT RULES:
- Return ONLY valid JSON (no markdown, no commentary).
- The JSON keys MUST be exactly the field names provided below (these may be canonical keys like "applicant.full_name" or bank labels).
- If a field is not found, return null for its value.
- Do NOT guess. Do NOT infer missing values.
- For each field return an object with:
  - value: string | number | boolean | null
  - confidence: number between 0 and 1
  - evidence: short direct snippet from the documents that supports the value (or null)

OUTPUT JSON SHAPE:
{{
  "<FIELD>": {{
    "value": ...,
    "confidence": ...,
    "evidence": ...
  }},
  ...
}}

FIELDS:
{fields}

DOCUMENTS (extracted text may be incomplete for scanned PDFs; use the attached PDFs as the source of truth):
{pdf_text}
""".strip()

def extract_fields_with_genai(
    pdf_text: str,
    field_list: List[str],
    bank_name: str,
    uploaded_pdfs: List[Tuple[str, bytes]],
    max_output_tokens: int = 2048,
):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY")

    client = genai.Client(api_key=api_key)

    model = os.getenv("GEMINI_MODEL", "models/gemini-2.5-pro")

    prompt = _build_prompt(bank_name, field_list, pdf_text)

    # Build message parts EXACTLY as Google expects
    parts = [types.Part.from_text(prompt)]

    # Attach each PDF
    for name, data in uploaded_pdfs:
        parts.append(
            types.Part.from_bytes(
                data=data,
                mime_type="application/pdf"
            )
        )

    resp = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            max_output_tokens=max_output_tokens,
        )
    )

    output = resp.text

    try:
        return _safe_json_load(output)
    except Exception:
        raise RuntimeError(f"Invalid JSON from Gemini:\n{output[:2000]}")
