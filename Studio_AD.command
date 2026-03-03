#!/bin/zsh
cd -- "$(dirname "$0")"
# VLEKT_DEV=1: sviluppo locale, salta controllo licenza
# In produzione imposta VLEKT_LICENSE_KEY con la tua chiave
export VLEKT_DEV=1
python3 -m streamlit run app2.py