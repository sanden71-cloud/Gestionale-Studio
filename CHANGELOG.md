# Novità e correzioni (Changelog)

Questo file elenca le novità e i bug risolti per ogni versione. L'app mostra le novità della versione installata in **Utility → Aggiornamenti**.

---

## 1.1.0

- **Gestione licenze**: l'amministratore può creare chiavi licenza univoche con scadenza opzionale (Utility → Amministrazione utenti → Gestione licenze). L'utente inserisce la chiave in Configurazione e vede in sidebar "Licenza scade il …" o "Licenza senza scadenza". Avviso quando la licenza scade entro 30 giorni.
- **Cambio password al primo accesso**: se la password è fornita dall'amministratore o dal recupero, l'utente deve cambiarla al primo accesso. Banner cliccabile che porta alla sezione Cambia password in Utility (visibile a tutti gli utenti).
- **Nome mittente email**: configurabile un nome di fantasia (es. "Software Gestionale AD") al posto dell'indirizzo email nelle email di recupero password.
- **Sync locale ↔ deploy**: con VLEKT_SECRET_KEY, utenti e config sono salvati cifrati (users.enc, config.enc) e si possono committare su Git per sincronizzare locale e deploy.
- **Aggiornamenti (solo online)**: l'utente conferma di aver letto le novità in Utility → Aggiornamenti (nessun download). L'avviso in home scompare dopo la conferma.
- **Sidebar utenti**: per gli utenti non admin viene mostrata "Licenza concessa al Dott. Nome Cognome" con eventuale data di scadenza invece del ruolo.

---

## 1.0.0

- **Database SQLite**: i dati ora sono salvati in SQLite (un file `vlekt.db` per utente) invece che in CSV. Più veloce, più sicuro e con backup/ripristino semplificato.
- **Area Utility riorganizzata**: in cima alla pagina una fila di pulsanti (Backup, Ripristino, Archivi, Statistiche, Integrità, Duplicati, Versione, Aggiornamenti, Amministrazione). Cliccando un pulsante si apre solo quella sezione, senza dover scorrere tutta la pagina.
- **Recupero password**: dalla schermata di login è possibile richiedere il recupero password tramite email (se l’email è impostata dall’amministratore). Configurazione SMTP e licenza gestibili da **Utility → Amministrazione → Configurazione**.
- **Elenco utenti (admin)**: tabella compatta in stile foglio di calcolo (una riga per utente) per trovare rapidamente gli utenti senza scroll.
- **Changelog in italiano**: in **Utility → Aggiornamenti** puoi leggere le novità della versione installata.

---

*Per ogni nuova release, aggiungi qui sopra una sezione `## X.Y.Z` con l’elenco delle novità e delle correzioni.*
