# --- Caricamento e path database (VLEKT PRO) — SQLite (un DB per utente) ---
import os
import sqlite3
import pandas as pd

from config import (
    COLS_PAZ,
    COLS_ALI,
    COLS_DIETA,
    COLS_INTEGR,
    COLS_PRESCR,
    COLS_PROT,
)

SQLITE_DB_NAME = "vlekt.db"
_TABLE_COLS = {
    "pazienti": COLS_PAZ,
    "alimenti": COLS_ALI,
    "diete": COLS_DIETA,
    "integratori": COLS_INTEGR,
    "prescrizioni": COLS_PRESCR,
    "proteine": COLS_PROT,
}
_CSV_FILES = {
    "pazienti": "database_pazienti.csv",
    "alimenti": "database_alimenti.csv",
    "diete": "database_diete.csv",
    "integratori": "database_integratori.csv",
    "prescrizioni": "database_prescrizioni.csv",
    "proteine": "database_proteine.csv",
}


def get_db_paths(user_dir):
    """Restituisce i path del DB SQLite e i nomi tabella. Ogni utente ha il suo file vlekt.db."""
    db_path = os.path.join(user_dir, SQLITE_DB_NAME)
    return {
        "DB_SQLITE": db_path,
        "DB_PAZIENTI": "pazienti",
        "DB_ALIMENTI": "alimenti",
        "DB_DIETE": "diete",
        "DB_INTEGRATORI": "integratori",
        "DB_PRESCRIZIONI": "prescrizioni",
        "DB_PROTEINE": "proteine",
    }


def _ensure_sqlite_schema(conn):
    """Crea le tabelle se non esistono (colonne tutte TEXT per compatibilità)."""
    for table, cols in _TABLE_COLS.items():
        col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({col_defs})')
    conn.commit()


def _migrate_csv_to_sqlite(user_dir, conn):
    """Se esistono ancora CSV nella cartella utente, li importa nel DB e poi li rimuove (opzionale)."""
    for table, cols in _TABLE_COLS.items():
        csv_path = os.path.join(user_dir, _CSV_FILES[table])
        if not os.path.exists(csv_path):
            continue
        try:
            df = pd.read_csv(csv_path, dtype=str)
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            df = df[cols].fillna("")
            df.to_sql(table, conn, if_exists="replace", index=False)
        except Exception:
            pass


def init_user_db(user_dir):
    """Inizializza il database SQLite per un nuovo utente (tabelle vuote). Usato alla creazione account."""
    os.makedirs(user_dir, exist_ok=True)
    paths = get_db_paths(user_dir)
    conn = sqlite3.connect(paths["DB_SQLITE"])
    _ensure_sqlite_schema(conn)
    conn.close()


def load_all_databases(user_dir):
    """Carica tutti i database dall'SQLite dell'utente. Crea il DB e le tabelle se mancano; migra da CSV se presenti."""
    os.makedirs(user_dir, exist_ok=True)
    paths = get_db_paths(user_dir)
    db_path = paths["DB_SQLITE"]
    created = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    _ensure_sqlite_schema(conn)
    if created:
        _migrate_csv_to_sqlite(user_dir, conn)
    conn.close()

    conn = sqlite3.connect(db_path)
    dfs = {}
    for table, cols in _TABLE_COLS.items():
        try:
            df = pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            dfs[table] = df[cols].fillna("")
        except Exception:
            dfs[table] = pd.DataFrame(columns=cols)
    conn.close()

    return (
        dfs["pazienti"],
        dfs["alimenti"],
        dfs["diete"],
        dfs["integratori"],
        dfs["prescrizioni"],
        dfs["proteine"],
        paths,
    )


def load_table(paths, table_key, colonne):
    """Carica una singola tabella (es. per ricaricare prescrizioni/integratori). table_key = "DB_PRESCRIZIONI" etc."""
    table_name = paths[table_key]
    conn = sqlite3.connect(paths["DB_SQLITE"])
    try:
        df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
        for c in colonne:
            if c not in df.columns:
                df[c] = ""
        return df[colonne].fillna("")
    except Exception:
        return pd.DataFrame(columns=colonne)
    finally:
        conn.close()


def save_table(paths, table_key, df):
    """Salva un DataFrame nella tabella SQLite. table_key = "DB_PAZIENTI" etc."""
    table_name = paths[table_key]
    conn = sqlite3.connect(paths["DB_SQLITE"])
    try:
        df = df.astype(str).fillna("")
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()


def carica_database(path_or_paths, colonne, table_key=None):
    """
    Compatibilità: se riceve (paths, table_key) carica da SQLite.
    Usato dove si faceva carica_database(DB_PRESCRIZIONI, COLS_PRESCR): ora serve passare paths e "DB_PRESCRIZIONI".
    """
    if table_key is not None:
        return load_table(path_or_paths, table_key, colonne)
    # Fallback: path come primo arg (legacy)
    if isinstance(path_or_paths, dict):
        return load_table(path_or_paths, "DB_PAZIENTI", colonne)
    file = path_or_paths
    if not os.path.exists(file):
        pd.DataFrame(columns=colonne).to_csv(file, index=False)
    try:
        df = pd.read_csv(file, dtype=str)
        for c in colonne:
            if c not in df.columns:
                df[c] = ""
        return df[colonne].fillna("")
    except Exception:
        return pd.DataFrame(columns=colonne)


def parse_prestashop_csv(file_path):
    import csv
    import re
    from html.parser import HTMLParser

    class TableParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows = []
            self.cur = []
            self.in_cell = False

        def handle_starttag(self, tag, attrs):
            if tag in ("td", "th"):
                self.in_cell = True
                self.cur.append("")

        def handle_endtag(self, tag):
            if tag in ("td", "th"):
                self.in_cell = False
            if tag == "tr" and self.cur:
                self.rows.append([x.strip().replace("\xa0", " ") for x in self.cur])
                self.cur = []

        def handle_data(self, data):
            if self.in_cell and self.cur:
                self.cur[-1] += data

    def estrai_nutrizionali(desc_html):
        if not desc_html or "<table" not in desc_html:
            return {}
        pos = 0
        tbl_html = None
        while True:
            start = desc_html.find("<table", pos)
            if start < 0:
                break
            end = desc_html.find("</table>", start) + len("</table>")
            blocco = desc_html[start:end]
            if "energia" in blocco.lower() or "kcal" in blocco.lower() or "valori nutrizionali" in blocco.lower():
                tbl_html = blocco
                break
            pos = end
        if not tbl_html:
            return {}
        p = TableParser()
        try:
            p.feed(tbl_html)
        except Exception:
            return {}
        vals = {}
        for row in p.rows:
            if len(row) < 3:
                continue
            label = (row[0] or "").lower()
            col3 = row[2]
            if "energia" in label:
                m = re.search(r"(\d+)\s*[kK]cal", col3)
                vals["Kcal"] = m.group(1) if m else ""
            elif "grassi" in label:
                m = re.search(r"([\d,]+)\s*g", col3)
                vals["Grassi"] = m.group(1).replace(",", ".") if m else ""
            elif "carboidrati" in label:
                m = re.search(r"([\d,]+)\s*g", col3)
                vals["Carbo_Netti"] = m.group(1).replace(",", ".") if m else ""
            elif "proteine" in label:
                m = re.search(r"([\d,]+)\s*g", col3)
                vals["Prot"] = m.group(1).replace(",", ".") if m else ""
        return vals

    def estrai_porzioni(nome):
        m = re.search(r"(\d+)\s*(?:porzioni|barrette|bustine?|pezzi)", nome or "", re.I)
        return m.group(1) if m else ""

    def pulisci_nome(nome):
        if not nome:
            return ""
        n = re.sub(r"\s*[•·]\s*LINEAPROTEICA\s*$", "", nome, flags=re.I)
        return n.strip()

    risultato = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            r = csv.reader(f, delimiter=";", quotechar='"')
            headers = next(r, [])
            idx_nome = idx_desc = -1
            for i, h in enumerate(headers):
                hc = str(h).strip().lower()
                if hc == "nome":
                    idx_nome = i
                elif idx_nome < 0 and "nome" in hc:
                    idx_nome = i
                if "descrizione" in hc and "html" in hc and "breve" not in hc:
                    idx_desc = i
            if idx_nome < 0:
                idx_nome = 6
            if idx_desc < 0:
                idx_desc = 8
            seen = set()
            for row in r:
                if len(row) <= max(idx_nome, idx_desc):
                    continue
                nome_raw = row[idx_nome].strip()
                nome = pulisci_nome(nome_raw)
                if not nome or nome in seen:
                    continue
                seen.add(nome)
                nutr = estrai_nutrizionali(row[idx_desc] if idx_desc < len(row) else "")
                porz = estrai_porzioni(nome_raw) or estrai_porzioni(row[idx_desc] if idx_desc < len(row) else "")
                kc, cb, pt, gr = nutr.get("Kcal", ""), nutr.get("Carbo_Netti", ""), nutr.get("Prot", ""), nutr.get("Grassi", "")
                if not (kc or cb or pt or gr):
                    continue
                risultato.append({
                    "Alimento": nome,
                    "Kcal": kc,
                    "Carbo_Netti": cb,
                    "Prot": pt,
                    "Grassi": gr,
                    "Porzioni_Confezione": porz,
                })
    except Exception:
        raise
    return risultato
