# Mortgage Form Filling Copilot (Production)

## One-time setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

mkdir -p .streamlit
cat > .streamlit/secrets.toml <<'TOML'
GEMINI_API_KEY = "YOUR_GEMINI_KEY"
TOML
```

## Build bank registry (run when bank forms change)
Bank PDFs are included under `assets/bank_forms/`.

```bash
python backend/build_bank_registry.py
```

This creates:
- `backend/registry_store/bank_registry.csv`

Review/clean that CSV and commit it.

## Run app
```bash
./venv/bin/streamlit run app/main.py --server.address 0.0.0.0 --server.port 8080
```

Open:
- `http://<EC2_PUBLIC_IP>:8080`
