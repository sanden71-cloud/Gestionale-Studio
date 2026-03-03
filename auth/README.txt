VLEKT PRO - Autenticazione e Licenza
====================================

SVILUPPO LOCALE:
- Imposta VLEKT_DEV=1 (già in Studio_AD.command) per saltare il controllo licenza.
- Primo accesso: utente "admin" / password "Admin123!" — cambiala subito.

PRODUZIONE (deploy online):
1. Imposta la variabile d'ambiente VLEKT_LICENSE_KEY con la tua chiave (es. su Streamlit Cloud: Secrets).
2. Oppure crea config.json qui con: {"license_key": "LA_TUA_CHIAVE"}

UTENTI:
- I dati di ogni utente sono in data/{username}/
- L'amministratore può attivare/disattivare utenti e crearne di nuovi dall'area Amministrazione.
