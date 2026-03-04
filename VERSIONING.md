# Versionamento e aggiornamenti – VLEKT PRO

## Dove si trova la versione

- **Un solo punto:** nel file `config.py` la variabile **`VERSION`** (es. `"1.0.0"`).
- La versione compare in **navbar** (accanto al logo) e può essere usata nel nome dei file di distribuzione (es. `StudioAD-1.0.0-setup.exe`).

---

## Schema: MAJOR.MINOR.PATCH

| Numero   | Nome   | Quando incrementare |
|----------|--------|----------------------|
| **MAJOR** | 1.0.0 → **2**.0.0 | Cambiamenti che rompono la compatibilità (nuovo formato dati, richiesta reinstallazione, cambio obbligatorio di flusso). |
| **MINOR** | 1.0.0 → 1.**1**.0 | Nuove funzionalità senza rompere le vecchie (nuova schermata, nuovo report, nuovo campo opzionale). |
| **PATCH** | 1.0.0 → 1.0.**1** | Solo correzioni bug, piccoli fix di testi o layout, nessuna nuova feature. |

**Esempi:**
- Aggiunta tab “Statistiche”: **1.0.0 → 1.1.0**
- Fix calcolo BMI: **1.0.0 → 1.0.1**
- Nuovo formato CSV che non è più leggibile dalle versioni vecchie: **1.2.0 → 2.0.0**

---

## Chi definisce il nuovo numero di versione

- **In pratica:** lo definisci **tu** (o chi rilascia l’aggiornamento), in base alle regole sopra.
- **Quando:** prima di dare in mano il nuovo pacchetto agli utenti (chiavetta, link download, ecc.).
- **Dove:** aggiorni **solo** `VERSION` in `config.py`; il resto dell’app legge già da lì (navbar, e in futuro nome installer/changelog se li aggiungi).

Non serve un sistema automatico: ad ogni rilascio decidi se è 1.0.1, 1.1.0 o 2.0.0 e aggiorni quella riga.

---

## Flusso consigliato per un aggiornamento

1. Sviluppi le modifiche in `app2.py` (e negli altri moduli).
2. Prima di “chiudere” la release:
   - Decidi se è **patch** (1.0.0 → 1.0.1), **minor** (1.0.0 → 1.1.0) o **major** (1.0.0 → 2.0.0).
   - Aggiorni **`VERSION`** in `config.py`.
   - Aggiorni **`latest_version.txt`** (stesso numero) e fai push su GitHub, così "Controlla aggiornamenti" in Utility vede la nuova versione.
3. Generi il pacchetto per gli utenti (es. nuovo `.exe` su Windows).
4. Distribuisci (chiavetta, link, ecc.) e comunichi agli utenti: “È disponibile la versione **1.1.0** con …”.

Opzionale: tieni un file **CHANGELOG.md** con l’elenco delle modifiche per versione (es. “1.1.0 – Aggiunta tab Statistiche, fix export PDF”).

---

## Riepilogo

| Cosa | Dove / come |
|------|-------------|
| **Numero di versione** | `config.py` → variabile `VERSION`. |
| **Chi lo cambia** | Tu (o chi rilascia), a mano, a ogni rilascio. |
| **Quando** | Prima di distribuire l’aggiornamento. |
| **Regola** | MAJOR = breaking, MINOR = nuove funzionalità, PATCH = solo bugfix. |
| **Visibilità** | In app nella navbar; in distribuzione nel nome file (es. `StudioAD-1.0.0-setup.exe`). |

### Controlla aggiornamenti (in Utility)

- In **Utility** è presente la sezione "Controlla aggiornamenti".
- Per abilitarla, in `config.py` imposta **`CHECK_UPDATE_URL`** con l’URL che restituisce solo il numero di versione in testo piano (es. `https://tuosito.com/vlekt/latest.txt` che contiene `1.1.0`).
- L’app confronta la versione remota con `VERSION` (MAJOR.MINOR.PATCH): se remota è maggiore, mostra "Disponibile una nuova versione: X.Y.Z".
- Se `CHECK_UPDATE_URL` è vuoto, la sezione mostra un messaggio che spiega come configurarla.

