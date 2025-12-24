from __future__ import annotations

from typing import Dict, Any, Tuple, List
import re
from datetime import datetime


def _is_email(x: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", x))


def _is_phone(x: str) -> bool:
    return bool(re.match(r"^[+0-9][0-9\s\-]{6,}$", x))


def _is_emirates_id(x: str) -> bool:
    return bool(re.match(r"^784\-\d{4}\-\d{7}\-\d$", x.strip()))


def _is_date(x: str) -> bool:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            datetime.strptime(x.strip(), fmt)
            return True
        except Exception:
            continue
    return False


def validate(
    extracted: Dict[str, Any],
    required: List[str],
    confidence_threshold: float = 0.6,
) -> Tuple[List[str], Dict[str, Any]]:
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

        try:
            conf = float(conf)
        except Exception:
            conf = 0.0

        flags = {
            "missing": value in (None, "", []),
            "low_confidence": conf < confidence_threshold,
            "invalid_format": False,
        }

        if isinstance(value, str) and value.strip():
            lname = field.lower()
            if "email" in lname:
                flags["invalid_format"] = not _is_email(value)
            elif "mobile" in lname or "phone" in lname:
                flags["invalid_format"] = not _is_phone(value)
            elif "emirates" in lname or "eid" in lname:
                flags["invalid_format"] = not _is_emirates_id(value)
            elif "date" in lname or "dob" in lname:
                flags["invalid_format"] = not _is_date(value)

        normalized[field] = {"value": value, "confidence": conf, "evidence": ev, "flags": flags}

    missing = [
        f for f in required
        if normalized[f]["flags"]["missing"]
        or normalized[f]["flags"]["low_confidence"]
        or normalized[f]["flags"]["invalid_format"]
    ]

    return missing, normalized
