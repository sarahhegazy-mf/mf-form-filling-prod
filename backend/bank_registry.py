from __future__ import annotations

from pathlib import Path
import pandas as pd

REGISTRY_PATH = Path("backend/registry_store/bank_registry.csv")


def load_bank_registry() -> pd.DataFrame:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(
            f"{REGISTRY_PATH} not found. Run: python backend/build_bank_registry.py"
        )
    df = pd.read_csv(REGISTRY_PATH)
    # Normalize required column to bool
    if "required" in df.columns:
        df["required"] = df["required"].astype(str).str.lower().isin(["true", "1", "yes", "y"])
    return df


def required_fields_for_bank(bank: str) -> list[str]:
    df = load_bank_registry()
    if "bank" not in df.columns or "field" not in df.columns:
        raise ValueError("bank_registry.csv must include columns: bank, field, required")
    sub = df[df["bank"] == bank]
    if "required" in sub.columns:
        sub = sub[sub["required"] == True]
    return sub["field"].dropna().astype(str).tolist()
