#!/bin/bash
# Avvia VLEKT PRO su VPS
# Assicurati di aver impostato VLEKT_LICENSE_KEY (es. export VLEKT_LICENSE_KEY="tua_chiave")

cd "$(dirname "$0")"

# Opzionale: attiva un virtualenv se lo usi
# source venv/bin/activate

streamlit run app2.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false
