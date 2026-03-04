# --- Caricamento e path database (VLEKT PRO) ---
import os
import pandas as pd

from config import (
    COLS_PAZ,
    COLS_ALI,
    COLS_DIETA,
    COLS_INTEGR,
    COLS_PRESCR,
    COLS_PROT,
)


def get_db_paths(user_dir):
    return {
        "DB_PAZIENTI": os.path.join(user_dir, "database_pazienti.csv"),
        "DB_ALIMENTI": os.path.join(user_dir, "database_alimenti.csv"),
        "DB_DIETE": os.path.join(user_dir, "database_diete.csv"),
        "DB_INTEGRATORI": os.path.join(user_dir, "database_integratori.csv"),
        "DB_PRESCRIZIONI": os.path.join(user_dir, "database_prescrizioni.csv"),
        "DB_PROTEINE": os.path.join(user_dir, "database_proteine.csv"),
    }


def carica_database(file, colonne):
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


def load_all_databases(user_dir):
    paths = get_db_paths(user_dir)
    df_p = carica_database(paths["DB_PAZIENTI"], COLS_PAZ)
    df_a = carica_database(paths["DB_ALIMENTI"], COLS_ALI)
    df_d = carica_database(paths["DB_DIETE"], COLS_DIETA)
    df_i = carica_database(paths["DB_INTEGRATORI"], COLS_INTEGR)
    df_pr = carica_database(paths["DB_PRESCRIZIONI"], COLS_PRESCR)
    df_prot = carica_database(paths["DB_PROTEINE"], COLS_PROT)
    return df_p, df_a, df_d, df_i, df_pr, df_prot, paths


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
