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

    if "required" in df.columns:
        df["required"] = df["required"].astype(str).str.lower().isin(["true", "1", "yes", "y"])

    for col in ["bank", "bank_label"]:
        if col not in df.columns:
            raise ValueError("bank_registry.csv must include at least: bank, bank_label")
    if "canonical_key" not in df.columns:
        df["canonical_key"] = ""
    if "section" not in df.columns:
        df["section"] = ""

    return df


def required_fields_for_bank(bank: str) -> list[str]:
    df = load_bank_registry()
    sub = df[df["bank"] == bank]
    if "required" in sub.columns:
        sub = sub[sub["required"] == True]

    keys = []
    for _, r in sub.iterrows():
        ck = str(r.get("canonical_key", "")).strip()
        lbl = str(r.get("bank_label", "")).strip()
        keys.append(ck if ck else lbl)
    return [k for k in keys if k]
