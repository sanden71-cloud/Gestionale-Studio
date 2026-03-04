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

CONFIGURAZIONE SMTP (recupero password via email):
--------------------------------------------------
Crea o modifica auth/config.json e aggiungi (oltre a license_key se serve):

  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "tua_email@gmail.com",
  "smtp_password": "password_per_app",
  "smtp_use_tls": true,
  "from_email": "tua_email@gmail.com"

- Gmail: usa una "Password per le app" (Account Google > Sicurezza > Verifica in 2 step > Password per le app). Non usare la password normale.
- Outlook/Office365: smtp_host "smtp.office365.com", port 587, smtp_use_tls true.
- Altri provider: cerca "SMTP [nome provider]" per host e porta.

Oppure variabili d'ambiente: VLEKT_SMTP_HOST, VLEKT_SMTP_PORT, VLEKT_SMTP_USER, VLEKT_SMTP_PASSWORD.
Se SMTP non è configurato, il recupero password funziona uguale ma la password temporanea viene mostrata a schermo.
