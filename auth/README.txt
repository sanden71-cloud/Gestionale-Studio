VLEKT PRO - Autenticazione e Licenza
====================================

SYNC LOCALE ↔ DEPLOY (utenti e config uguali ovunque):
------------------------------------------------------
Imposta la stessa passphrase in locale e in deploy (es. Streamlit Cloud → Secrets):
  VLEKT_SECRET_KEY = una passphrase segreta (es. "MiaPassphraseSegreta123")

- In locale: aggiungi VLEKT_SECRET_KEY al .command o a ~/.zshrc.
- In deploy: aggiungi VLEKT_SECRET_KEY nei Secrets dell'app.

Con VLEKT_SECRET_KEY attiva:
  • Utenti e config sono salvati cifrati in auth/users.enc e auth/config.enc.
  • Puoi committare e pushare users.enc e config.enc su GitHub: saranno gli stessi in locale e online.
  • Crea/modifica utenti e config in un ambiente, fai commit e push; nell'altro fai pull e riavvia.
- La passphrase non va mai committata: solo nei Secrets / variabili d'ambiente.
- Senza VLEKT_SECRET_KEY: si usano auth/users.json e auth/config.json (ignorati da Git, solo locale).

SVILUPPO LOCALE:
- Imposta VLEKT_DEV=1 (già in Studio_AD.command) per saltare il controllo licenza.
- Primo accesso: utente "admin" / password "Admin123!" — cambiala subito.

LICENZE (admin genera, utente inserisce):
1. Admin: Utility → Amministrazione utenti → Gestione licenze. Genera chiavi con scadenza (data) o senza scadenza.
2. L'admin fornisce la chiave all'utente (es. Dott. Rossi).
3. L'utente inserisce la chiave in Utility → Configurazione → Chiave licenza (o variabile VLEKT_LICENSE_KEY).
4. L'utente vede in sidebar: "Licenza scade il 31/12/2025" o "Licenza senza scadenza".
- Le licenze generate sono salvate in auth/licenses.json (database licenze).
- Formato chiave: VLEKT-{uuid}-{scadenza}-{firma}. Chiavi legacy (>=8 caratteri) ancora valide.

PRODUZIONE (deploy online):
1. Imposta la variabile d'ambiente VLEKT_LICENSE_KEY con la tua chiave (es. su Streamlit Cloud: Secrets).
2. Oppure inserisci la chiave in Utility → Configurazione (Chiave licenza).
   Con sync (VLEKT_SECRET_KEY) la licenza è in config.enc.

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
