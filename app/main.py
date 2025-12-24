import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import pandas as pd
import streamlit as st

from backend.pdf_text import extract_text_from_uploads
from backend.orchestrator import process_bank
from backend.bank_registry import load_bank_registry

st.set_page_config(page_title="Mortgage AI Form Filler", layout="wide")

# Wider sidebar so bank names show
st.markdown(
    """
    <style>
      [data-testid="stSidebar"] { min-width: 460px; max-width: 460px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Mortgage AI Form Filler")

with st.sidebar:
    st.header("Setup")

    try:
        reg = load_bank_registry()
        banks = sorted(reg["bank"].dropna().unique().tolist())
    except Exception as e:
        st.error(f"Bank registry not found/failed to load: {e}")
        st.info("1) Put bank PDFs in assets/bank_forms/\n2) Run: python backend/build_bank_registry.py")
        st.stop()

    selected_banks = st.multiselect("Select bank(s)", banks, default=banks[:1] if banks else [])
    confidence_threshold = st.slider("Confidence threshold", 0.0, 1.0, 0.6, 0.05)

    st.divider()
    st.subheader("Upload client documents")
    uploads = st.file_uploader(
        "Upload client PDFs (EID, salary cert, bank statements, etc.)",
        type=["pdf"],
        accept_multiple_files=True,
    )

st.divider()

for key, default in {
    "pdf_text": "",
    "doc_names": [],
    "outputs": {},
    "manual": {},
    "chat": [],
    "chat_bank": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

colA, colB = st.columns([1, 1], gap="large")

with colA:
    st.subheader("1) Read PDFs")
    if st.button("Read uploaded PDFs", type="primary", disabled=not uploads):
        file_status = st.empty()
        prog = st.progress(0)

        def on_file(name: str):
            file_status.info(f"Reading: {name}")

        def on_progress(pct: int):
            prog.progress(pct)

        try:
            pdf_text, names = extract_text_from_uploads(uploads, on_file=on_file, on_progress=on_progress)
            st.session_state.pdf_text = pdf_text
            st.session_state.doc_names = names
            st.success(f"Read {len(names)} file(s).")
        except Exception as e:
            st.error(f"Failed to read PDFs: {e}")

    if st.session_state.doc_names:
        st.caption("Files read:")
        st.write(st.session_state.doc_names)

    if st.session_state.pdf_text:
        with st.expander("Preview extracted text (first 4,000 chars)"):
            st.text(st.session_state.pdf_text[:4000])

with colB:
    st.subheader("2) Extract fields per bank (live)")
    live = st.empty()

    if st.button("Extract & Validate", disabled=not (selected_banks and st.session_state.pdf_text)):
        st.session_state.outputs = {}

        for bank in selected_banks:
            st.write(f"### {bank}")
            bank_partial = {"data": {}}

            def on_partial_update(bank_name, partial):
                bank_partial["data"].update(partial)
                df = pd.DataFrame(
                    [
                        {
                            "field": k,
                            "value": v.get("value"),
                            "confidence": v.get("confidence"),
                            "missing": v.get("flags", {}).get("missing") if isinstance(v, dict) else None,
                        }
                        for k, v in bank_partial["data"].items()
                    ]
                )
                live.dataframe(df, use_container_width=True, hide_index=True)

            payload = process_bank(
                bank_name=bank,
                pdf_text=st.session_state.pdf_text,
                confidence_threshold=confidence_threshold,
                on_partial_update=on_partial_update,
            )
            st.session_state.outputs[bank] = payload

        st.success("Extraction complete. Go to the chat below to fill missing fields.")

st.divider()
st.subheader("3) Advisor chat (fill missing fields)")

if not st.session_state.outputs:
    st.info("Run extraction first.")
else:
    bank = st.selectbox("Choose bank", list(st.session_state.outputs.keys()))
    st.session_state.chat_bank = bank

    payload = st.session_state.outputs[bank]
    missing = payload.get("missing_fields", [])
    fields = payload.get("fields", {})

    left, right = st.columns([2, 1], gap="large")

    with right:
        st.caption("Missing / needs review")
        st.write(missing[:50] if missing else ["✅ None"])

    with left:
        for msg in st.session_state.chat:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        def assistant_say(text: str):
            st.session_state.chat.append({"role": "assistant", "content": text})

        def user_say(text: str):
            st.session_state.chat.append({"role": "user", "content": text})

        if st.button("Reset chat"):
            st.session_state.chat = []
            st.rerun()

        if not st.session_state.chat:
            if missing:
                assistant_say(f"For **{bank}**, I’m missing **{missing[0]}**. What is the value?")
            else:
                assistant_say(f"For **{bank}**, everything looks complete. You can export below.")

        user_input = st.chat_input("Type your answer (or 'skip', or 'field: value')")

        if user_input:
            user_say(user_input)

            if not missing:
                assistant_say("No missing fields remaining. You can export below.")
                st.rerun()

            text = user_input.strip()

            if text.lower() == "skip":
                if missing:
                    missing = missing[1:] + missing[:1]
                    payload["missing_fields"] = missing
                    st.session_state.outputs[bank] = payload
                    assistant_say(f"Okay — next: **{missing[0]}**. What is the value?")
                    st.rerun()

            if ":" in text:
                maybe_field, maybe_value = text.split(":", 1)
                f = maybe_field.strip()
                v = maybe_value.strip()
                if f in fields or f in missing:
                    payload["fields"][f] = {
                        "value": v,
                        "confidence": 0.99,
                        "evidence": "manual_input",
                        "flags": {"missing": False, "low_confidence": False, "invalid_format": False},
                    }
                    payload["missing_fields"] = [x for x in missing if x != f]
                    st.session_state.outputs[bank] = payload
                    assistant_say(f"Saved **{f}**. " + (f"Next: **{payload['missing_fields'][0]}**" if payload["missing_fields"] else "All set ✅"))
                    st.rerun()

            if missing:
                f = missing[0]
                payload["fields"][f] = {
                    "value": text,
                    "confidence": 0.99,
                    "evidence": "manual_input",
                    "flags": {"missing": False, "low_confidence": False, "invalid_format": False},
                }
                payload["missing_fields"] = missing[1:]
                st.session_state.outputs[bank] = payload
                if payload["missing_fields"]:
                    assistant_say(f"Saved **{f}**. Next: **{payload['missing_fields'][0]}**. What is the value?")
                else:
                    assistant_say(f"Saved **{f}**. ✅ No missing fields left.")
                st.rerun()

st.divider()
st.subheader("4) Export")

if st.session_state.outputs:
    export_obj = st.session_state.outputs
    st.download_button(
        "Download JSON",
        data=json.dumps(export_obj, indent=2),
        file_name="mortgage_extraction.json",
        mime="application/json",
    )

    rows = []
    for b, pl in export_obj.items():
        for field, v in pl.get("fields", {}).items():
            rows.append(
                {
                    "bank": b,
                    "field": field,
                    "value": v.get("value"),
                    "confidence": v.get("confidence"),
                    "evidence": v.get("evidence"),
                    "missing": v.get("flags", {}).get("missing"),
                    "low_confidence": v.get("flags", {}).get("low_confidence"),
                    "invalid_format": v.get("flags", {}).get("invalid_format"),
                }
            )
    if rows:
        df = pd.DataFrame(rows)
        st.download_button(
            "Download CSV",
            data=df.to_csv(index=False),
            file_name="mortgage_extraction.csv",
            mime="text/csv",
        )
