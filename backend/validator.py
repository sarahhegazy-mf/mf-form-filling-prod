from __future__ import annotations

from typing import Dict, Any, Tuple, List


def validate(
    extracted: Dict[str, Any],
    required: List[str],
    confidence_threshold: float = 0.6,
) -> Tuple[List[str], Dict[str, Any]]:
    """Normalize extracted results and return missing/low-confidence fields."""
    normalized: Dict[str, Any] = {}

    for field in required:
        item = extracted.get(field) or {}
        if isinstance(item, dict):
            value = item.get("value", None)
            conf = item.get("confidence", 0.0)
            ev = item.get("evidence", None)
        else:
            value = item
            conf = 0.0
            ev = None

        # Normalize confidence
        try:
            conf = float(conf)
        except Exception:
            conf = 0.0

        normalized[field] = {"value": value, "confidence": conf, "evidence": ev}

    missing = [
        f for f in required
        if normalized[f]["value"] in (None, "", [])
        or normalized[f]["confidence"] < confidence_threshold
    ]

    return missing, normalized
