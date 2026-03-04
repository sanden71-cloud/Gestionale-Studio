# Novità e correzioni (Changelog)

Questo file elenca le novità e i bug risolti per ogni versione. L'app mostra le novità della versione installata in **Utility → Aggiornamenti**.

---

## 1.0.0

- **Database SQLite**: i dati ora sono salvati in SQLite (un file `vlekt.db` per utente) invece che in CSV. Più veloce, più sicuro e con backup/ripristino semplificato.
- **Area Utility riorganizzata**: in cima alla pagina una fila di pulsanti (Backup, Ripristino, Archivi, Statistiche, Integrità, Duplicati, Versione, Aggiornamenti, Amministrazione). Cliccando un pulsante si apre solo quella sezione, senza dover scorrere tutta la pagina.
- **Recupero password**: dalla schermata di login è possibile richiedere il recupero password tramite email (se l’email è impostata dall’amministratore). Configurazione SMTP e licenza gestibili da **Utility → Amministrazione → Configurazione**.
- **Elenco utenti (admin)**: tabella compatta in stile foglio di calcolo (una riga per utente) per trovare rapidamente gli utenti senza scroll.
- **Changelog in italiano**: in **Utility → Aggiornamenti** puoi leggere le novità della versione installata.

---

*Per ogni nuova release, aggiungi qui sopra una sezione `## X.Y.Z` con l’elenco delle novità e delle correzioni.*
