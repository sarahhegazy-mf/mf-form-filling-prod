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
      [data-testid="stSidebar"] { min-width: 420px; max-width: 420px; }
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
                            "evidence": v.get("evidence"),
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

        st.success("Extraction complete.")

st.divider()
st.subheader("3) Advisor chat for missing fields")

if not st.session_state.outputs:
    st.info("Run extraction first.")
else:
    bank = st.selectbox("Choose bank to complete", list(st.session_state.outputs.keys()))
    payload = st.session_state.outputs[bank]
    missing = payload.get("missing_fields", [])

    st.write(f"Missing/low-confidence fields: **{len(missing)}**")

    if missing:
        next_field = missing[0]
        st.write(f"Next required field: **{next_field}**")
        val = st.text_input(f"Enter value for: {next_field}", key=f"manual_{bank}_{next_field}")
        if st.button("Save field"):
            st.session_state.manual.setdefault(bank, {})[next_field] = val
            payload["fields"][next_field] = {"value": val, "confidence": 0.99, "evidence": "manual_input"}
            payload["missing_fields"] = [f for f in missing if f != next_field]
            st.session_state.outputs[bank] = payload
            st.success("Saved. Continue to the next missing field.")
            st.rerun()
    else:
        st.success("No missing fields. ✅")

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
