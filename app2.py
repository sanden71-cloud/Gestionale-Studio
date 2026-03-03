import streamlit as st
import pandas as pd
import numpy as np
import os
import time
import base64
from datetime import date, datetime
import zipfile
from fpdf import FPDF
import matplotlib.pyplot as plt
import io
import subprocess
import sys

# Installa pypdf e reportlab se non presenti
def _ensure_pkg(pkg, import_name=None):
    import_name = import_name or pkg
    try:
        __import__(import_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

_ensure_pkg("pypdf")
_ensure_pkg("reportlab")

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4

try:
    from streamlit_searchbox import st_searchbox
except ImportError:
    st_searchbox = None

# --- 1. CONFIGURAZIONE E SETUP ---
try:
    from codicefiscale import codicefiscale
except ImportError:
    st.error("Errore: Libreria mancante. Installa con: pip3 install codicefiscale")

st.set_page_config(page_title="VLEKT PRO - Gestionale Nutrizionale Integrato", layout="wide", page_icon="🥑")

# --- FUNZIONI MEDICO-MATEMATICHE ---
def to_f(value):
    try:
        if value == "" or value is None or str(value).strip() == "": return 0.0
        return float(str(value).replace(',', '.'))
    except: return 0.0

def calcola_eta(data_nascita_str):
    try:
        g, m, a = map(int, data_nascita_str.split('/'))
        nascita = date(a, m, g)
        oggi = date.today()
        return oggi.year - nascita.year - ((oggi.month, oggi.day) < (nascita.month, nascita.day))
    except:
        return 30

def calcola_eta_anni_mesi(data_nascita_str):
    """Restituisce (anni, mesi) per visualizzazione tipo '43 anni e 10 mesi'."""
    try:
        g, m, a = map(int, data_nascita_str.split('/'))
        nascita = date(a, m, g)
        oggi = date.today()
        anni = oggi.year - nascita.year - ((oggi.month, oggi.day) < (nascita.month, nascita.day))
        mesi = (oggi.month - nascita.month) + (oggi.day - nascita.day) / 31.0
        if mesi < 0:
            anni -= 1
            mesi += 12
        mesi = int(round(mesi)) % 12
        return anni, mesi
    except:
        return 30, 0

def calcola_info_visite(st_p_ord):
    """Da DataFrame visite ordinate per data: ultima_data, giorni_da_ultima, n_visite, intervallo_medio_giorni."""
    if st_p_ord is None or st_p_ord.empty:
        return None, 0, 0, 0
    n_visite = len(st_p_ord)
    ultima_str = st_p_ord.iloc[-1]['Data_Visita']
    try:
        gg, mm, aa = map(int, ultima_str.split('/'))
        ultima_data = date(aa, mm, gg)
        giorni_da_ultima = (date.today() - ultima_data).days
    except Exception:
        ultima_data = None
        giorni_da_ultima = 0
    intervallo_medio = 0
    if n_visite >= 2:
        date_visite = []
        for _, r in st_p_ord.iterrows():
            try:
                g, m, a = map(int, str(r['Data_Visita']).split('/'))
                date_visite.append(date(a, m, g))
            except Exception:
                pass
        date_visite.sort()
        diff_giorni = [(date_visite[i+1] - date_visite[i]).days for i in range(len(date_visite)-1)]
        intervallo_medio = int(round(sum(diff_giorni) / len(diff_giorni))) if diff_giorni else 0
    return ultima_str, giorni_da_ultima, n_visite, intervallo_medio

def calcola_stato_bmi(bmi):
    if bmi < 18.5: return "Sottopeso", "#3498db" 
    elif bmi < 25.0: return "Normopeso", "#2ecc71" 
    elif bmi < 30.0: return "Sovrappeso", "#f1c40f" 
    elif bmi < 35.0: return "Obesità 1° Grado", "#e67e22" 
    elif bmi < 40.0: return "Obesità 2° Grado", "#e74c3c" 
    else: return "Obesità 3° Grado", "#8e44ad" 

def calcola_bmr(peso, altezza, eta, sesso):
    if sesso == 'M': return (10 * peso) + (6.25 * altezza) - (5 * eta) + 5
    else: return (10 * peso) + (6.25 * altezza) - (5 * eta) - 161

# --- 1.5 INIEZIONE CSS PER GRAFICA A "SCHEDE" (GARANTITA AL 100%) ---
st.markdown("""
<style>
    /* Sfondo grigio chiaro per far risaltare il bianco delle schede */
    .stApp { background-color: #f4f7f6; }

    /* Pulsanti primary: colore pastello professionale al posto del rosso */
    button[kind="primary"] {
        background-color: #5b8fb9 !important;
        color: white !important;
        border: none !important;
    }
    button[kind="primary"]:hover {
        background-color: #4a7da3 !important;
        color: white !important;
        border-color: #4a7da3 !important;
    }

    /* Stile personalizzato per le Card HTML */
    .card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        border: 1px solid #e0e6ed;
        height: 100%;
    }
    .card-header-blue {
        color: #2c3e50;
        font-size: 18px;
        font-weight: 800;
        border-bottom: 3px solid #3498db;
        padding-bottom: 8px;
        margin-bottom: 15px;
        margin-top: 0;
    }
    .card-header-green {
        color: #2c3e50;
        font-size: 18px;
        font-weight: 800;
        border-bottom: 3px solid #2ecc71;
        padding-bottom: 8px;
        margin-bottom: 15px;
        margin-top: 0;
    }
    .card-text {
        font-size: 15px;
        color: #34495e;
        margin: 6px 0;
    }
    .highlight-red {
        color: #e74c3c;
        font-weight: 800;
        font-size: 17px;
    }
    /* Card header generico (senza colore specifico) */
    .card-header {
        color: #2c3e50;
        font-size: 18px;
        font-weight: 800;
        border-bottom: 3px solid #95a5a6;
        padding-bottom: 8px;
        margin-bottom: 15px;
        margin-top: 0;
    }
    /* Box evidenziato dentro le card */
    .highlight-box {
        background-color: #f0f4f8;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 15px;
        font-weight: 700;
        color: #2c3e50;
        margin-bottom: 8px;
    }
    /* Badge colorato per stato BMI */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 700;
        color: #ffffff;
    }

    /* Pulsanti in colonne — dimensioni e layout uniformi (tutti i button + download) */
    div[data-testid="column"] button,
    div[data-testid="column"] a[download] {
        min-height: 40px !important;
        height: 40px !important;
        max-height: 40px !important;
        padding: 8px 14px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: nowrap !important;
        flex-direction: row !important;
        box-sizing: border-box !important;
    }
    /* Sidebar: pulsante "apri paziente" piccolo e discreto (no blu) */
    div[data-testid="stSidebar"] div[data-testid="column"] button[kind="secondary"] {
        min-height: 28px !important;
        height: 28px !important;
        padding: 2px 6px !important;
        font-size: 13px !important;
        background: #f0f4f8 !important;
        color: #374151 !important;
        border: 1px solid #d1d5db !important;
    }
    div[data-testid="stSidebar"] div[data-testid="column"] button[kind="secondary"]:hover {
        background: #e0e7ef !important;
        border-color: #3498db !important;
        color: #3498db !important;
    }

    /* Titoli sezione sidebar — leggibilità */
    div[data-testid="stSidebar"] .sidebar-section {
        color: #2c3e50 !important;
        font-size: 14px !important;
        font-weight: 700 !important;
        margin: 12px 0 8px 0 !important;
        letter-spacing: 0.3px !important;
    }

    /* Pulsante Crea Nuovo Paziente — evidenziato (target via anchor) */
    div[data-testid="stSidebar"] div:has(.crea-paziente-anchor) + div button,
    div[data-testid="stSidebar"] div:has(.crea-paziente-anchor) ~ div:first-of-type button {
        background: linear-gradient(135deg, #10b981 0%, #059669 50%, #047857 100%) !important;
        color: white !important;
        font-weight: 800 !important;
        font-size: 14px !important;
        padding: 14px 20px !important;
        border-radius: 12px !important;
        border: none !important;
        box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4) !important;
        transition: all 0.2s ease !important;
        letter-spacing: 0.5px !important;
    }
    div[data-testid="stSidebar"] div:has(.crea-paziente-anchor) + div button:hover,
    div[data-testid="stSidebar"] div:has(.crea-paziente-anchor) ~ div:first-of-type button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.5) !important;
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
    }

    /* --- Header bar stile Nutriverso (scuro, breadcrumb + CTA) --- */
    .vlekt-navbar {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
        color: #f1f5f9;
        padding: 12px 20px;
        margin: -1rem -1rem 1rem -1rem;
        border-bottom: 1px solid #334155;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
        font-family: inherit;
    }
    .vlekt-navbar-left { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
    .vlekt-navbar-logo {
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 0.5px;
        color: #fff;
    }
    .vlekt-navbar-logo span { color: #38bdf8; }
    .vlekt-breadcrumb {
        font-size: 13px;
        color: #94a3b8;
        font-weight: 500;
    }
    .vlekt-breadcrumb a { color: #94a3b8; text-decoration: none; }
    .vlekt-breadcrumb a:hover { color: #38bdf8; }
    .vlekt-navbar-btn {
        display: inline-block;
        background: #2563eb !important;
        color: white !important;
        padding: 8px 16px !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        text-decoration: none !important;
        border: none !important;
        box-shadow: 0 2px 6px rgba(37, 99, 235, 0.4);
    }
    .vlekt-navbar-btn:hover { background: #1d4ed8 !important; color: white !important; }

    /* Tab orizzontali stile Nutriverso (sotto header paziente) */
    .vlekt-tabs-wrap {
        display: flex;
        gap: 0;
        border-bottom: 2px solid #e2e8f0;
        margin-bottom: 16px;
        font-size: 13px;
        font-weight: 600;
    }
    .vlekt-tab {
        padding: 10px 18px;
        color: #64748b;
        cursor: pointer;
        border-bottom: 3px solid transparent;
        margin-bottom: -2px;
    }
    .vlekt-tab.active { color: #2563eb; border-bottom-color: #2563eb; }
    .vlekt-tab:hover:not(.active) { color: #1e293b; }

    /* Radio orizzontale come tab (Cruscotto / Piani / Integratori) */
    div[data-testid="stRadio"] > div {
        gap: 0 !important;
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 0;
        margin-bottom: 12px;
    }
    div[data-testid="stRadio"] label {
        padding: 10px 18px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        color: #64748b !important;
        border-radius: 0 !important;
        border-bottom: 3px solid transparent !important;
        margin-bottom: -2px !important;
    }
    div[data-testid="stRadio"] label:hover { color: #1e293b !important; }
    div[data-testid="stRadio"] label[data-checked="true"],
    div[data-testid="stRadio"] label:has(input:checked) {
        color: #2563eb !important;
        border-bottom-color: #2563eb !important;
    }
    /* Barra nome paziente sotto breadcrumb */
    .vlekt-patient-name-bar {
        font-size: 14px;
        color: #475569;
        font-weight: 600;
        margin: -8px 0 12px 0;
        padding: 6px 0;
        border-bottom: 1px solid #f1f5f9;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER SPONSOR (LINEADICIOTTO) ---
st.markdown("""
<div style="text-align: center; padding: 10px; background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); border-radius: 8px; margin-bottom: 15px; border: 1px solid #e0e6ed; box-shadow: 0 2px 8px rgba(0,0,0,0.02);">
    <p style="color: #7f8c8d; margin: 0; font-weight: 600; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;">Software Nutrizionale in comodato d'uso da <span style="color: #2c3e50; font-weight: 900; font-size: 14px; letter-spacing: 1px; margin-left: 5px;">LINEADICIOTTO</span></p>
    <a href="https://www.lineadiciotto.it" target="_blank" style="color: #3498db; text-decoration: none; font-weight: 600; font-size: 12px;">🌐 www.lineadiciotto.it</a>
</div>
""", unsafe_allow_html=True)

# --- AUTENTICAZIONE E LICENZA ---
try:
    import auth_utils as _auth
except ImportError:
    _auth = None

if _auth:
    ok_lic, msg_lic = _auth.check_license()
    if not ok_lic:
        st.error(f"🔒 {msg_lic}")
        st.stop()
    _auth.ensure_admin_exists()

    if 'logged_user' not in st.session_state:
        st.session_state.logged_user = None
    if 'show_admin' not in st.session_state:
        st.session_state.show_admin = False

    # Sviluppo locale: auto-login admin (VLEKT_DEV=1) — anche dopo refresh pagina
    if st.session_state.logged_user is None and os.environ.get("VLEKT_DEV") == "1":
        st.session_state.logged_user = "admin"
        st.session_state.show_admin = False

    if st.session_state.logged_user is None:
        st.markdown("### 🔐 Accesso")
        with st.form("login_form"):
            u = st.text_input("Utente", placeholder="username")
            p = st.text_input("Password", type="password", placeholder="password")
            if st.form_submit_button("Accedi"):
                if u and p and _auth:
                    ok, err = _auth.verify_login(u, p)
                    if ok:
                        st.session_state.logged_user = u.strip().lower()
                        st.session_state.show_admin = False
                        st.rerun()
                    else:
                        st.error(err)
                else:
                    st.warning("Inserisci utente e password.")
        st.caption("Primo accesso: utente **admin** / password **Admin123!** — cambiala subito.")
        st.stop()

    _logged = st.session_state.logged_user
    _user_dir = _auth.get_user_data_dir(_logged)
    _is_admin = _auth.is_admin(_logged)
else:
    _user_dir = os.path.dirname(os.path.abspath(__file__))
    _is_admin = False

# --- 2. COSTANTI E DATABASE ---
DB_PAZIENTI = os.path.join(_user_dir, 'database_pazienti.csv')
DB_ALIMENTI = os.path.join(_user_dir, 'database_alimenti.csv')
DB_DIETE = os.path.join(_user_dir, 'database_diete.csv')
DB_INTEGRATORI = os.path.join(_user_dir, 'database_integratori.csv')
DB_PRESCRIZIONI = os.path.join(_user_dir, 'database_prescrizioni.csv')
DB_PROTEINE = os.path.join(_user_dir, 'database_proteine.csv')

# Migrazione: se admin e data/admin vuoto ma esistono CSV nella root app, copiali
if _auth and _is_admin and _user_dir != os.path.dirname(os.path.abspath(__file__)):
    _app_dir = os.path.dirname(os.path.abspath(__file__))
    _root_csv = os.path.join(_app_dir, 'database_pazienti.csv')
    if os.path.exists(_root_csv) and not os.path.exists(DB_PAZIENTI):
        import shutil
        for _fn in ['database_pazienti.csv', 'database_alimenti.csv', 'database_diete.csv',
                    'database_integratori.csv', 'database_prescrizioni.csv', 'database_proteine.csv']:
            _src = os.path.join(_app_dir, _fn)
            _dst = os.path.join(_user_dir, _fn)
            if os.path.exists(_src):
                shutil.copy2(_src, _dst)

LISTA_PASTI_UOMO   = ['Colazione', 'Spuntino Mattina', 'Pranzo', 'Merenda', 'Cena', 'Dopo Cena']
LISTA_PASTI_DONNA  = ['Colazione', 'Spuntino/Merenda', 'Pranzo', 'Cena']
LISTA_PASTI        = LISTA_PASTI_UOMO  # default per compatibilità ordinamento
ORDINE_PASTI       = {p: i for i, p in enumerate(LISTA_PASTI_UOMO + ['Spuntino/Merenda'])}

# Definizione Colonne
COLS_PAZ = [
    'Data_Visita', 'Nome', 'Cognome', 'Codice_Fiscale', 'Data_Nascita', 
    'Luogo_Nascita', 'Indirizzo', 'Sesso', 'Cellulare', 'Email', 'Altezza', 'Peso', 'BMI', 
    'Addome', 'Fianchi', 'Torace', 'Polso', 
    'Analisi_Cliniche', 'Farmaci', 'Note', 'LAF', 'Peso_Target',
    # Circonferenze
    'Circ_Polso_Dx', 'Circ_Polso_Sx',
    'Circ_Avambraccio_Dx', 'Circ_Avambraccio_Sx',
    'Circ_Braccio_Dx', 'Circ_Braccio_Sx',
    'Circ_Spalle', 'Circ_Torace_Ant', 'Circ_Vita', 'Circ_Addome_Ant', 'Circ_Fianchi_Ant',
    'Circ_Coscia_Prox_Dx', 'Circ_Coscia_Prox_Sx',
    'Circ_Coscia_Med_Dx', 'Circ_Coscia_Med_Sx',
    'Circ_Coscia_Dist_Dx', 'Circ_Coscia_Dist_Sx',
    'Circ_Polpaccio_Dx', 'Circ_Polpaccio_Sx',
    'Circ_Caviglia_Dx', 'Circ_Caviglia_Sx',
    # Pliche
    'Plica_Avambraccio', 'Plica_Bicipitale', 'Plica_Tricipitale', 'Plica_Ascellare',
    'Plica_Pettorale', 'Plica_Sottoscapolare', 'Plica_Addominale', 'Plica_Soprailiaca',
    'Plica_Coscia_Med', 'Plica_Soprapatellare', 'Plica_Polpaccio_Med', 'Plica_Sopraspinale',
    # Diametri ossei
    'Diam_Polso', 'Diam_Gomito', 'Diam_Biacromiale',
    'Diam_Toracico', 'Diam_Bicrestale', 'Diam_Addominale_Sag',
    'Diam_Bitrocanterio', 'Diam_Ginocchio', 'Diam_Caviglia',
    # Note antropometria
    'Note_Antropometria',
]
COLS_ALI = ['Alimento', 'Kcal', 'Carbo_Netti', 'Prot', 'Grassi', 'Porzioni_Confezione']
COLS_DIETA = ['Codice_Fiscale', 'Data_Visita', 'Step', 'Giorni', 'Pasto', 'Alimento', 'Quantita', 'Kcal_Tot', 'Carbo_Tot', 'Prot_Tot', 'Grassi_Tot']
COLS_INTEGR = ['Nome_Integratore', 'Categoria', 'Descrizione']
COLS_PRESCR = ['Codice_Fiscale', 'Data_Visita', 'Data_Inizio', 'Nome_Integratore', 'Posologia', 'Note_Prescrizione']
COLS_PROT = ['Nome', 'Categoria', 'Grammi_Porzione', 'Kcal', 'Prot', 'Grassi', 'Carbo_Netti', 'Note']

# --- COSTANTI GLOBALI ---
lista_laf = ["1.2 - Sedentario", "1.375 - Leggermente Attivo", "1.55 - Moderatamente Attivo", "1.725 - Molto Attivo", "1.9 - Estremamente Attivo"]

def carica_database(file, colonne):
    if not os.path.exists(file):
        pd.DataFrame(columns=colonne).to_csv(file, index=False)
    try:
        df = pd.read_csv(file, dtype=str)
        for c in colonne:
            if c not in df.columns: df[c] = ""
        return df[colonne].fillna("")
    except:
        return pd.DataFrame(columns=colonne)

df_p = carica_database(DB_PAZIENTI, COLS_PAZ)
df_a = carica_database(DB_ALIMENTI, COLS_ALI)
df_d = carica_database(DB_DIETE, COLS_DIETA)
df_i = carica_database(DB_INTEGRATORI, COLS_INTEGR)
df_pr = carica_database(DB_PRESCRIZIONI, COLS_PRESCR)
df_prot = carica_database(DB_PROTEINE, COLS_PROT)


def parse_prestashop_csv(file_path):
    """
    Legge un CSV export PrestaShop (articoli) e estrae i dati nutrizionali
    dalla tabella HTML nella colonna Descrizione.
    Ritorna lista di dict con chiavi COLS_ALI.
    """
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
            if tag in ('td', 'th'):
                self.in_cell = True
                self.cur.append('')
        def handle_endtag(self, tag):
            if tag in ('td', 'th'):
                self.in_cell = False
            if tag == 'tr' and self.cur:
                self.rows.append([x.strip().replace('\xa0', ' ') for x in self.cur])
                self.cur = []
        def handle_data(self, data):
            if self.in_cell and self.cur:
                self.cur[-1] += data

    def estrai_nutrizionali(desc_html):
        """Estrae Kcal, Carbo, Prot, Grassi dalla tabella nutrizionale HTML."""
        if not desc_html or '<table' not in desc_html:
            return {}
        # Cerca la tabella che contiene "Energia" o "Kcal" (non sempre è la prima; a volte c'è tabella ingredienti prima)
        pos = 0
        tbl_html = None
        while True:
            start = desc_html.find('<table', pos)
            if start < 0:
                break
            end = desc_html.find('</table>', start) + len('</table>')
            blocco = desc_html[start:end]
            if 'energia' in blocco.lower() or 'kcal' in blocco.lower() or 'valori nutrizionali' in blocco.lower():
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
            label = (row[0] or '').lower()
            col3 = row[2]  # valori per porzione
            if 'energia' in label:
                m = re.search(r'(\d+)\s*[kK]cal', col3)
                vals['Kcal'] = m.group(1) if m else ''
            elif 'grassi' in label:
                m = re.search(r'([\d,]+)\s*g', col3)
                vals['Grassi'] = (m.group(1).replace(',', '.') if m else '')
            elif 'carboidrati' in label:
                m = re.search(r'([\d,]+)\s*g', col3)
                vals['Carbo_Netti'] = (m.group(1).replace(',', '.') if m else '')
            elif 'proteine' in label:
                m = re.search(r'([\d,]+)\s*g', col3)
                vals['Prot'] = (m.group(1).replace(',', '.') if m else '')
        return vals

    def estrai_porzioni(nome):
        """Estrae numero porzioni da nome (es. 'Confezione 5 porzioni' -> 5)."""
        m = re.search(r'(\d+)\s*(?:porzioni|barrette|bustine?|pezzi)', nome or '', re.I)
        return m.group(1) if m else ''

    def pulisci_nome(nome):
        """Rimuove suffissi come •LINEAPROTEICA dalla fine."""
        if not nome:
            return ''
        n = re.sub(r'\s*[•·]\s*LINEAPROTEICA\s*$', '', nome, flags=re.I)
        return n.strip()

    risultato = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            r = csv.reader(f, delimiter=';', quotechar='"')
            headers = next(r, [])
            # Indici colonne PrestaShop tipici (Nome=7, Descrizione HTML=9)
            idx_nome = idx_desc = -1
            for i, h in enumerate(headers):
                hc = str(h).strip().lower()
                if hc == 'nome':
                    idx_nome = i
                elif idx_nome < 0 and 'nome' in hc:
                    idx_nome = i
                if 'descrizione' in hc and 'html' in hc and 'breve' not in hc:
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
                nutr = estrai_nutrizionali(row[idx_desc] if idx_desc < len(row) else '')
                porz = estrai_porzioni(nome_raw) or estrai_porzioni(row[idx_desc] if idx_desc < len(row) else '')
                # Escludi prodotti senza valori nutrizionali (integratori, servizi, ecc.)
                kc, cb, pt, gr = nutr.get('Kcal', ''), nutr.get('Carbo_Netti', ''), nutr.get('Prot', ''), nutr.get('Grassi', '')
                if not (kc or cb or pt or gr):
                    continue
                risultato.append({
                    'Alimento': nome,
                    'Kcal': kc,
                    'Carbo_Netti': cb,
                    'Prot': pt,
                    'Grassi': gr,
                    'Porzioni_Confezione': porz
                })
    except Exception as e:
        raise e
    return risultato


# --- 3. FUNZIONI PDF ---

# Percorsi template piani dieta (da copiare nella stessa cartella dell'app)
PDF_PIANI = {
    ('F', 1): 'Donna_4_pasti_Fase_1_Step_1.pdf',
    ('F', 2): 'Donna_3_pasti_Fase_1_Step_2.pdf',
    ('M', 1): 'Uomo_5_pasti_Fase_1_Step_1.pdf',
    ('M', 2): 'Uomo_4_Pasti_Fase_1_Step_2.pdf',
}

# Coordinate zona nome per ogni template
# y_rl = coordinata Y in ReportLab (origine in basso) = 842 - top_pdfplumber
# Il testo originale è ~18pt, usiamo 13pt per non sovrastare il layout
PDF_NOME_CFG = {
    ('F', 1): {'x': 54, 'y_cover_top': 131, 'y_cover_bot': 150},  # top=131, bottom=149
    ('F', 2): {'x': 54, 'y_cover_top': 138, 'y_cover_bot': 158},  # top=138, bottom=156
    ('M', 1): {'x': 54, 'y_cover_top': 129, 'y_cover_bot': 149},  # top=129, bottom=147
    ('M', 2): {'x': 54, 'y_cover_top': 137, 'y_cover_bot': 160},  # top=137, bottom=159
}

def genera_piano_dieta_pdf(sesso, step, cognome, nome, data_visita):
    """
    Prende il PDF template corretto (per sesso e step),
    sovrappone il nome del paziente e restituisce i bytes del PDF.
    Se il template dello step non esiste, usa quello dello step 1 come fallback.
    """
    key = (sesso, step)
    template_name = PDF_PIANI.get(key)
    if not template_name:
        return None

    app_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(app_dir, template_name)
    if not os.path.exists(template_path):
        # Fallback: usa template step 1 se step 2 non presente (es. Uomo_4_Pasti non ancora aggiunto)
        fallback_key = (sesso, 1)
        template_name = PDF_PIANI.get(fallback_key)
        if not template_name:
            return None
        template_path = os.path.join(app_dir, template_name)
        if not os.path.exists(template_path):
            return None
        key = fallback_key

    cfg = PDF_NOME_CFG.get(key) or PDF_NOME_CFG.get((sesso, 1))
    PAGE_H = 842.0

    # Converti coordinate pdfplumber (y dall'alto) → ReportLab (y dal basso)
    rl_bottom = PAGE_H - cfg['y_cover_bot']  # bordo inferiore del rettangolo
    rl_top    = PAGE_H - cfg['y_cover_top']  # bordo superiore del rettangolo
    rect_h    = rl_top - rl_bottom
    # Centro verticale del rettangolo, con baseline testo leggermente sotto il centro
    text_y = rl_bottom + (rect_h - 13) / 2  # 13 = font size

    # Crea overlay
    packet = io.BytesIO()
    c = rl_canvas.Canvas(packet, pagesize=A4)

    # Rettangolo bianco per coprire nome generico (tutta la larghezza utile)
    c.setFillColorRGB(1, 1, 1)
    c.rect(cfg['x'], rl_bottom - 2, 490, rect_h + 4, fill=1, stroke=0)

    # Nuovo nome con stesso stile: font 13pt, bold
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 13)
    data_fmt = data_visita if data_visita else date.today().strftime('%d/%m/%Y')
    c.drawString(cfg['x'] + 5, text_y, f"Spett.: {cognome} {nome}   {data_fmt}")

    c.save()
    packet.seek(0)

    # Merge overlay sulla prima pagina del template
    overlay  = PdfReader(packet)
    template = PdfReader(template_path)
    writer   = PdfWriter()

    for i, page in enumerate(template.pages):
        if i == 0:
            page.merge_page(overlay.pages[0])
        writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.read()

def genera_pdf_overview(p_info, storico):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 15, "RIEPILOGO CLINICO PAZIENTE", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, f"Paziente: {p_info['Nome']} {p_info['Cognome']}", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, f"Codice Fiscale: {p_info['Codice_Fiscale']} | Data Nascita: {p_info['Data_Nascita']}", ln=True)
    pdf.ln(5)

    if not storico.empty:
        ultima_v = storico.iloc[-1]
        peso_u = to_f(ultima_v['Peso'])
        altezza_u = to_f(ultima_v['Altezza'])
        bmi_u = to_f(ultima_v['BMI'])
        
        eta = calcola_eta(p_info['Data_Nascita'])
        bmr = calcola_bmr(peso_u, altezza_u, eta, p_info['Sesso'])
        laf_str = str(ultima_v.get('LAF', '1.2 - Sedentario'))
        laf_num = float(laf_str.split(' - ')[0]) if laf_str and laf_str != 'nan' else 1.2
        tdee = bmr * laf_num
        peso_target_str = str(ultima_v.get('Peso_Target', ''))
        peso_target = to_f(peso_target_str) if peso_target_str and peso_target_str != 'nan' else round(22.5 * ((altezza_u/100)**2), 1)
        delta_peso = peso_u - peso_target
        
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, " STATO ATTUALE E OBIETTIVO PONDERALE", ln=True, fill=True)
        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 8, f"Data Ultima Visita: {ultima_v['Data_Visita']}", ln=True)
        pdf.cell(0, 8, f"Peso Attuale: {peso_u} kg | Altezza: {altezza_u} cm | BMI: {bmi_u}", ln=True)
        pdf.cell(0, 8, f"Metabolismo Basale (BMR): {int(bmr)} Kcal | Fabbisogno (TDEE): {int(tdee)} Kcal", ln=True)
        pdf.ln(2)
        pdf.set_font("Arial", 'B', 11)
        delta_label = f"Da perdere: {round(delta_peso, 1)} kg" if delta_peso > 0 else f"Da guadagnare: {round(abs(delta_peso), 1)} kg"
        pdf.cell(0, 8, f"Obiettivo Ponderale: {peso_target} kg ({delta_label})", ln=True)
        pdf.ln(5)

        # --- GRAFICO 1: BARRA BMI COLORATA ---
        if altezza_u > 0:
            h_m = altezza_u / 100
            t1 = 18.5 * (h_m**2); t2 = 25.0 * (h_m**2)
            t3 = 30.0 * (h_m**2); t4 = 35.0 * (h_m**2); t5 = 40.0 * (h_m**2)
            min_w = 30.0; max_w = max(160.0, peso_u + 20.0)
            
            fig, ax = plt.subplots(figsize=(7, 1.8))
            ax.set_xlim(min_w, max_w); ax.set_ylim(0, 1)
            ax.set_yticks([])
            
            segmenti = [
                (min_w, t1, '#3498db', 'Sottopeso'),
                (t1, t2, '#2ecc71', 'Normopeso'),
                (t2, t3, '#f1c40f', 'Sovrappeso'),
                (t3, t4, '#e67e22', 'Ob. Lieve'),
                (t4, t5, '#e74c3c', 'Ob. Mod.'),
                (t5, max_w, '#8e44ad', 'Ob. Grave'),
            ]
            for (x0, x1, col, lbl) in segmenti:
                ax.barh(0, x1 - x0, left=x0, height=0.5, color=col, align='edge')
                ax.text((x0 + x1) / 2, 0.62, lbl, ha='center', va='bottom', fontsize=6.5, color='#555')

            # Indicatore peso attuale
            ax.axvline(peso_u, color='#111827', linewidth=2.5, zorder=5)
            ax.text(peso_u, -0.18, f'Attuale\n{peso_u} kg', ha='center', va='top', fontsize=7.5, fontweight='bold', color='#111827')

            # Indicatore peso target
            ax.axvline(peso_target, color='#2c3e50', linewidth=1.8, linestyle='--', zorder=5)
            ax.text(peso_target, 1.05, f'Target: {peso_target} kg', ha='center', va='bottom', fontsize=7.5, fontweight='bold', color='#2c3e50')

            ax.set_xlabel("Peso (kg)", fontsize=8)
            plt.tight_layout(pad=1.2)
            buf_bmi = io.BytesIO()
            plt.savefig(buf_bmi, format='png', dpi=150, bbox_inches='tight')
            buf_bmi.seek(0); plt.close()

            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, " GRAFICO OBIETTIVO PONDERALE E RANGE BMI", ln=True, fill=True)
            pdf.ln(3)
            pdf.image(buf_bmi, x=15, w=180)
            pdf.ln(5)

        if len(storico) >= 2:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, " EVOLUZIONE DEL PESO", ln=True, fill=True)
            pdf.ln(5)
            plt.figure(figsize=(7, 3.5))
            st_ord = storico.copy()
            st_ord['DT'] = pd.to_datetime(st_ord['Data_Visita'], format='%d/%m/%Y', errors='coerce')
            st_ord = st_ord.dropna(subset=['DT']).sort_values('DT')
            plt.plot(st_ord['Data_Visita'], st_ord['Peso'].astype(float), marker='o', color='#3498db', linewidth=2)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            pdf.image(buf, x=15, w=180)
            plt.close()
            
    return bytes(pdf.output())

def genera_pdf_visita_paziente(p_info, visita, storico):
    """
    Report completo da consegnare al paziente:
    - Intestazione studio / dati paziente
    - Dettagli visita (peso, BMI, metabolismo, obiettivo)
    - Grafico andamento peso (se piu visite)
    - Barra BMI colorata
    - Misure antropometriche della visita (solo campi con dati)
    - Grafico andamenti antropometrici (solo misure con piu di 1 rilevazione)
    - Analisi cliniche / farmaci / note
    """
    def safe(val, default="-"):
        v = str(val).strip()
        return v if v not in ('', 'nan', 'None') else default

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── COLORI TEMA ──
    C_BLU   = (52, 152, 219)
    C_VERDE = (46, 204, 113)
    C_SCURO = (44, 62, 80)
    C_GRIGIO= (240, 244, 248)

    def section_header(title, r=52, g=152, b=219):
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 9, f"  {title}", ln=True, fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    def kv(label, value, w_label=60):
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(w_label, 7, label + ":", ln=False)
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 7, str(value), ln=True)

    # ══════════════════════════════════════════════
    # PAGINA 1 - DATI PAZIENTE + VISITA + GRAFICI
    # ══════════════════════════════════════════════
    pdf.add_page()

    # Intestazione studio
    pdf.set_fill_color(*C_SCURO)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 14, "  REPORT VISITA NUTRIZIONALE - VLEKT PRO", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Dati anagrafici paziente
    section_header("DATI PAZIENTE", *C_SCURO)
    pdf.set_fill_color(*C_GRIGIO)
    pdf.rect(10, pdf.get_y(), 190, 26, 'F')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, f"  {p_info['Cognome']} {p_info['Nome']}", ln=True)
    pdf.set_font("Arial", '', 10)
    eta_p = calcola_eta(p_info['Data_Nascita'])
    pdf.cell(95, 6, f"  Nato/a il: {safe(p_info['Data_Nascita'])}  (eta': {eta_p} anni)", ln=False)
    pdf.cell(0,  6, f"C.F.: {safe(p_info['Codice_Fiscale'])}", ln=True)
    pdf.cell(95, 6, f"  Sesso: {'Uomo' if str(p_info.get('Sesso','')).upper()=='M' else 'Donna'}", ln=False)
    pdf.cell(0,  6, f"Cellulare: {safe(p_info.get('Cellulare',''))}", ln=True)
    pdf.ln(5)

    # Dati visita
    data_vis = safe(visita['Data_Visita'])
    peso_v   = to_f(visita['Peso'])
    alt_v    = to_f(visita['Altezza'])
    bmi_v    = to_f(visita['BMI'])
    laf_str  = safe(visita.get('LAF', '1.2'), '1.2')
    laf_num  = float(laf_str.split(' - ')[0]) if ' - ' in laf_str else to_f(laf_str) or 1.2
    bmr_v    = calcola_bmr(peso_v, alt_v, eta_p, p_info.get('Sesso','M'))
    tdee_v   = bmr_v * laf_num
    pt_str   = safe(visita.get('Peso_Target',''))
    peso_target = to_f(pt_str) if pt_str != '-' else round(22.5*((alt_v/100)**2), 1)
    delta_v  = round(peso_v - peso_target, 1)
    stato_t, stato_c_hex = calcola_stato_bmi(bmi_v)

    section_header(f"VISITA DEL {data_vis}", *C_BLU)
    # Griglia dati visita 2 colonne
    col_w = 95
    rows_vis = [
        ("Peso",           f"{peso_v} kg",       "Altezza",     f"{alt_v} cm"),
        ("BMI",            f"{bmi_v}  ({stato_t})", "Peso Target", f"{peso_target} kg"),
        ("Metabolismo Bas..", f"{int(bmr_v)} kcal", "Fabbisogno (TDEE)", f"{int(tdee_v)} kcal"),
        ("Attivita' fisica", laf_str,              "Da perdere/guadagnare", f"{'-' if delta_v<=0 else '+'}{abs(delta_v)} kg"),
    ]
    for (l1, v1, l2, v2) in rows_vis:
        pdf.set_font("Arial", 'B', 9); pdf.cell(30, 6, l1+":", ln=False)
        pdf.set_font("Arial", '', 9);  pdf.cell(col_w-30, 6, v1, ln=False)
        pdf.set_font("Arial", 'B', 9); pdf.cell(35, 6, l2+":", ln=False)
        pdf.set_font("Arial", '', 9);  pdf.cell(0, 6, v2, ln=True)
    pdf.ln(4)

    # ── BARRA BMI ──
    if alt_v > 0:
        h_m = alt_v / 100
        t1=18.5*(h_m**2); t2=25.0*(h_m**2); t3=30.0*(h_m**2); t4=35.0*(h_m**2); t5=40.0*(h_m**2)
        min_w=30.0; max_w=max(160.0, peso_v+20.0)
        fig, ax = plt.subplots(figsize=(7, 1.6))
        ax.set_xlim(min_w, max_w); ax.set_ylim(0,1); ax.set_yticks([])
        for (x0,x1,col,lbl) in [
            (min_w,t1,'#3498db','Sottopeso'),(t1,t2,'#2ecc71','Normopeso'),
            (t2,t3,'#f1c40f','Sovrappeso'),(t3,t4,'#e67e22','Ob.Lieve'),
            (t4,t5,'#e74c3c','Ob.Mod.'),(t5,max_w,'#8e44ad','Ob.Grave')]:
            ax.barh(0, x1-x0, left=x0, height=0.5, color=col, align='edge')
            ax.text((x0+x1)/2, 0.62, lbl, ha='center', va='bottom', fontsize=6.5, color='#555')
        ax.axvline(peso_v, color='#111827', linewidth=2.5, zorder=5)
        ax.text(peso_v, -0.18, f'Attuale\n{peso_v} kg', ha='center', va='top', fontsize=7, fontweight='bold', color='#111827')
        ax.axvline(peso_target, color='#2c3e50', linewidth=1.8, linestyle='--', zorder=5)
        ax.text(peso_target, 1.08, f'Target: {peso_target} kg', ha='center', va='bottom', fontsize=7, fontweight='bold', color='#2c3e50')
        ax.set_xlabel("Peso (kg)", fontsize=8)
        plt.tight_layout(pad=1.0)
        buf_bmi = io.BytesIO(); plt.savefig(buf_bmi, format='png', dpi=150, bbox_inches='tight'); buf_bmi.seek(0); plt.close()
        section_header("POSIZIONE BMI E OBIETTIVO PONDERALE", *C_BLU)
        pdf.image(buf_bmi, x=12, w=186)
        pdf.ln(4)

    # ── ANDAMENTO PESO ──
    st_ord = storico.copy()
    st_ord['DT'] = pd.to_datetime(st_ord['Data_Visita'], format='%d/%m/%Y', errors='coerce')
    st_ord = st_ord.dropna(subset=['DT']).sort_values('DT')
    if len(st_ord) >= 2:
        section_header("ANDAMENTO DEL PESO NEL TEMPO", *C_BLU)
        pesi = st_ord['Peso'].apply(to_f).tolist()
        date_lbl = st_ord['Data_Visita'].tolist()
        fig2, ax2 = plt.subplots(figsize=(7, 2.8))
        ax2.plot(range(len(date_lbl)), pesi, marker='o', color='#3498db', linewidth=2, markersize=6)
        if peso_target > 0:
            ax2.axhline(peso_target, color='#2ecc71', linewidth=1.5, linestyle='--', label=f'Target {peso_target} kg')
            ax2.legend(fontsize=8)
        for i, (p, d) in enumerate(zip(pesi, date_lbl)):
            ax2.annotate(f"{p} kg", (i, p), textcoords="offset points", xytext=(0, 8), ha='center', fontsize=7.5)
        ax2.set_xticks(range(len(date_lbl))); ax2.set_xticklabels(date_lbl, rotation=30, ha='right', fontsize=8)
        ax2.set_ylabel("Peso (kg)", fontsize=8); ax2.grid(True, alpha=0.3)
        plt.tight_layout()
        buf2 = io.BytesIO(); plt.savefig(buf2, format='png', dpi=150, bbox_inches='tight'); buf2.seek(0); plt.close()
        pdf.image(buf2, x=12, w=186)
        pdf.ln(3)

    # ══════════════════════════════════════════════
    # PAGINA 2 - ANTROPOMETRIA + GRAFICI ANDAMENTI
    # ══════════════════════════════════════════════
    # Raccoglie campi antropometrici con valore > 0 nella visita corrente
    CIRC_LABELS = {
        'Circ_Polso_Dx':'Polso Dx','Circ_Polso_Sx':'Polso Sx',
        'Circ_Avambraccio_Dx':'Avambraccio Dx','Circ_Avambraccio_Sx':'Avambraccio Sx',
        'Circ_Braccio_Dx':'Braccio Dx','Circ_Braccio_Sx':'Braccio Sx',
        'Circ_Spalle':'Spalle','Circ_Torace_Ant':'Torace',
        'Circ_Vita':'Vita','Circ_Addome_Ant':'Addome','Circ_Fianchi_Ant':'Fianchi',
        'Circ_Coscia_Prox_Dx':'Coscia Prox Dx','Circ_Coscia_Prox_Sx':'Coscia Prox Sx',
        'Circ_Coscia_Med_Dx':'Coscia Med Dx','Circ_Coscia_Med_Sx':'Coscia Med Sx',
        'Circ_Coscia_Dist_Dx':'Coscia Dist Dx','Circ_Coscia_Dist_Sx':'Coscia Dist Sx',
        'Circ_Polpaccio_Dx':'Polpaccio Dx','Circ_Polpaccio_Sx':'Polpaccio Sx',
        'Circ_Caviglia_Dx':'Caviglia Dx','Circ_Caviglia_Sx':'Caviglia Sx',
    }
    PLICHE_LABELS = {
        'Plica_Avambraccio':'Avambraccio','Plica_Bicipitale':'Bicipitale',
        'Plica_Tricipitale':'Tricipitale','Plica_Ascellare':'Ascellare',
        'Plica_Pettorale':'Pettorale/Toracica','Plica_Sottoscapolare':'Sottoscapolare',
        'Plica_Addominale':'Addominale','Plica_Soprailiaca':'Soprailiaca',
        'Plica_Coscia_Med':'Mediana coscia','Plica_Soprapatellare':'Soprapatellare',
        'Plica_Polpaccio_Med':'Mediana polpaccio','Plica_Sopraspinale':'Sopraspinale',
    }
    DIAM_LABELS = {
        'Diam_Polso':'Polso','Diam_Gomito':'Gomito','Diam_Biacromiale':'Biacromiale',
        'Diam_Toracico':'Toracico','Diam_Bicrestale':'Bicrestale',
        'Diam_Addominale_Sag':'Addominale sag.','Diam_Bitrocanterio':'Bitrocanterico',
        'Diam_Ginocchio':'Ginocchio','Diam_Caviglia':'Caviglia',
    }

    circ_dati  = {k: to_f(visita.get(k,0)) for k,_ in CIRC_LABELS.items() if to_f(visita.get(k,0)) > 0}
    pliche_dati= {k: to_f(visita.get(k,0)) for k,_ in PLICHE_LABELS.items() if to_f(visita.get(k,0)) > 0}
    diam_dati  = {k: to_f(visita.get(k,0)) for k,_ in DIAM_LABELS.items() if to_f(visita.get(k,0)) > 0}

    has_antro = circ_dati or pliche_dati or diam_dati

    if has_antro:
        pdf.add_page()
        pdf.set_fill_color(*C_SCURO)
        pdf.set_text_color(255,255,255)
        pdf.set_font("Arial",'B',14)
        pdf.cell(0,12,f"  MISURE ANTROPOMETRICHE - {data_vis}", ln=True, fill=True)
        pdf.set_text_color(0,0,0)
        pdf.ln(3)

        def tabella_antro(title, dati, labels_dict, unita):
            if not dati: return
            section_header(f"{title} ({unita})", *C_BLU)
            items = list(dati.items())
            # 3 colonne per riga
            for i in range(0, len(items), 3):
                gruppo = items[i:i+3]
                cols_w = [63, 63, 64]
                for j, (k, v) in enumerate(gruppo):
                    lbl = labels_dict[k]
                    pdf.set_fill_color(245,248,252)
                    pdf.rect(10 + sum(cols_w[:j]), pdf.get_y(), cols_w[j]-2, 12, 'F')
                    pdf.set_font("Arial",'',8); pdf.set_xy(11 + sum(cols_w[:j]), pdf.get_y())
                    pdf.cell(cols_w[j]-4, 5, lbl, ln=False)
                pdf.ln(5)
                for j, (k, v) in enumerate(gruppo):
                    pdf.set_font("Arial",'B',11); pdf.set_xy(11 + sum(cols_w[:j]), pdf.get_y())
                    pdf.cell(cols_w[j]-4, 7, f"{v:.1f} {unita}", ln=False)
                pdf.ln(8)
            pdf.ln(2)

        tabella_antro("CIRCONFERENZE", circ_dati, CIRC_LABELS, "cm")
        tabella_antro("PLICHE CUTANEE", pliche_dati, PLICHE_LABELS, "mm")
        tabella_antro("DIAMETRI OSSEI", diam_dati, DIAM_LABELS, "cm")

    # ── GRAFICI ANDAMENTI ANTROPOMETRICI (solo misure con ≥2 rilevazioni) ──
    TUTTE_MISURE = {}
    TUTTE_MISURE.update(CIRC_LABELS)
    TUTTE_MISURE.update(PLICHE_LABELS)
    TUTTE_MISURE.update(DIAM_LABELS)

    grafici_antro = []
    for col, lbl in TUTTE_MISURE.items():
        if col not in st_ord.columns: continue
        serie = st_ord[['Data_Visita', col]].copy()
        serie[col] = serie[col].apply(to_f)
        serie = serie[serie[col] > 0]
        if len(serie) >= 2:
            grafici_antro.append((col, lbl, serie))

    if grafici_antro:
        pdf.add_page()
        pdf.set_fill_color(*C_SCURO)
        pdf.set_text_color(255,255,255)
        pdf.set_font("Arial",'B',14)
        pdf.cell(0,12,"  ANDAMENTI ANTROPOMETRICI NEL TEMPO", ln=True, fill=True)
        pdf.set_text_color(0,0,0)
        pdf.ln(4)

        # 2 grafici per riga
        grafici_per_riga = 2
        graph_w = 90; graph_h = 45
        for idx_g in range(0, len(grafici_antro), grafici_per_riga):
            gruppo_g = grafici_antro[idx_g:idx_g+grafici_per_riga]
            y_start = pdf.get_y()
            if y_start + graph_h + 10 > 270:
                pdf.add_page(); y_start = pdf.get_y()
            fig_g, axes = plt.subplots(1, len(gruppo_g), figsize=(4.5*len(gruppo_g), 1.8))
            if len(gruppo_g) == 1: axes = [axes]
            for ax_g, (col_g, lbl_g, serie_g) in zip(axes, gruppo_g):
                vals_g = serie_g[col_g].tolist()
                dlbls  = serie_g['Data_Visita'].tolist()
                colore = '#3498db' if col_g in CIRC_LABELS else ('#e74c3c' if col_g in PLICHE_LABELS else '#27ae60')
                ax_g.plot(range(len(vals_g)), vals_g, marker='o', color=colore, linewidth=1.8, markersize=5)
                for xi, (vi, di) in enumerate(zip(vals_g, dlbls)):
                    ax_g.annotate(f"{vi:.1f}", (xi, vi), textcoords="offset points", xytext=(0,5), ha='center', fontsize=6.5)
                ax_g.set_title(lbl_g, fontsize=8, fontweight='bold', pad=4)
                ax_g.set_xticks(range(len(dlbls))); ax_g.set_xticklabels(dlbls, rotation=30, ha='right', fontsize=6)
                ax_g.grid(True, alpha=0.25); ax_g.tick_params(axis='y', labelsize=6.5)
            plt.tight_layout(pad=0.8)
            buf_g = io.BytesIO(); plt.savefig(buf_g, format='png', dpi=150, bbox_inches='tight'); buf_g.seek(0); plt.close()
            pdf.image(buf_g, x=10, y=y_start, w=190)
            pdf.set_y(y_start + graph_h + 6)

    # ══════════════════════════════════════════════
    # ULTIMA SEZIONE - NOTE / ANALISI / FARMACI
    # ══════════════════════════════════════════════
    analisi_s = safe(visita.get('Analisi_Cliniche',''))
    farmaci_s = safe(visita.get('Farmaci',''))
    note_s    = safe(visita.get('Note',''))
    note_antro_s = safe(visita.get('Note_Antropometria',''))

    has_note = any(x != '-' for x in [analisi_s, farmaci_s, note_s, note_antro_s])
    if has_note:
        if pdf.get_y() > 220: pdf.add_page()
        else: pdf.ln(4)
        section_header("NOTE CLINICHE E ANNOTAZIONI", 231, 76, 60)
        for titolo, valore in [
            ("Analisi Cliniche", analisi_s),
            ("Farmaci Assunti",  farmaci_s),
            ("Note Visita",      note_s),
            ("Note Antropometria", note_antro_s),
        ]:
            if valore != '-':
                pdf.set_font("Arial",'B',10); pdf.cell(0,6, f"{titolo}:", ln=True)
                pdf.set_font("Arial",'',9);   pdf.multi_cell(0,5, valore)
                pdf.ln(2)

    # ── PIE' DI PAGINA ──
    pdf.set_y(-15)
    pdf.set_font("Arial",'I',7)
    pdf.set_text_color(150,150,150)
    pdf.cell(0, 5, f"Report generato il {date.today().strftime('%d/%m/%Y')} - VLEKT PRO | lineadiciotto.it", align='C')

    return bytes(pdf.output())


def _html_btn_stampa(pdf_bytes, btn_label="🖨️ Stampa"):
    """Genera HTML per pulsante Stampa che apre il PDF in nuova finestra e attiva la stampa."""
    b64 = base64.b64encode(pdf_bytes).decode()
    return f'''<!DOCTYPE html><html><head><style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ height: 40px; min-height: 40px; overflow: hidden; }}
    .btn-wrap {{ width: 100%; height: 40px; display: flex; align-items: center; }}
    .btn-stampa-pdf {{
        width: 100%;
        min-height: 40px;
        height: 40px;
        max-height: 40px;
        padding: 8px 14px;
        font-size: 14px;
        font-weight: 600;
        border-radius: 8px;
        border: none;
        background: #5b8fb9 !important;
        color: white !important;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        white-space: nowrap;
        box-sizing: border-box;
    }}
    .btn-stampa-pdf:hover {{ background: #4a7da3 !important; }}
    </style></head><body>
    <div class="btn-wrap"><button onclick="_doPrint()" class="btn-stampa-pdf">{btn_label}</button></div>
    <script>
    function _doPrint() {{
        var w = window.open('', '_blank');
        w.document.write('<html><body style="margin:0"><iframe src="data:application/pdf;base64,{b64}" style="width:100%;height:99vh;border:none"></iframe></body></html>');
        w.document.close();
        w.focus();
        setTimeout(function() {{ w.print(); }}, 500);
    }}
    </script></body></html>'''


def genera_pdf_privacy(p_info):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "CONSENSO AL TRATTAMENTO DEI DATI PERSONALI (GDPR)", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, "Ai sensi dell'art. 13 del Regolamento UE 2016/679", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", '', 11)
    indirizzo_txt = p_info.get('Indirizzo', '')
    if not indirizzo_txt: indirizzo_txt = "________________________"
    
    testo_anagrafica = (
        f"Il/La sottoscritto/a {p_info['Nome']} {p_info['Cognome']}, "
        f"nato/a a {p_info['Luogo_Nascita']} il {p_info['Data_Nascita']}, "
        f"residente in {indirizzo_txt}, "
        f"Codice Fiscale: {p_info['Codice_Fiscale']}."
    )
    pdf.multi_cell(0, 8, testo_anagrafica)
    pdf.ln(5)
    
    testo_legale = (
        "DICHIARA\n\n"
        "Di aver ricevuto e letto attentamente l'informativa sul trattamento dei dati personali in conformita' "
        "al Regolamento UE 2016/679 (GDPR). Pertanto, prestando il proprio consenso libero e consapevole:\n\n"
        "1. ACCONSENTE al trattamento dei propri dati personali e particolari (dati relativi allo stato di salute, "
        "esami clinici, parametri antropometrici, ecc.) per l'esecuzione della prestazione professionale dietetica e nutrizionale.\n\n"
        "2. ACCONSENTE alla comunicazione dei suddetti dati a soggetti terzi esclusivamente laddove tale comunicazione "
        "sia strettamente necessaria per finalita' cliniche o adempimenti fiscali/legali.\n\n"
        "Il sottoscritto e' consapevole che il conferimento dei dati relativi alla salute e' indispensabile "
        "per l'erogazione del piano VLEKT, e che un eventuale rifiuto comporterebbe l'impossibilita' di procedere."
    )
    pdf.multi_cell(0, 6, testo_legale)
    pdf.ln(20)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, f"Luogo e Data: _________________________", ln=True)
    pdf.ln(10)
    pdf.cell(0, 8, f"Firma del Paziente: __________________________________________", ln=True)
    return bytes(pdf.output())

def genera_pdf_prescrizione(p_info, prescrizioni_df, data_visita):
    pdf = FPDF()
    pdf.add_page()

    # --- Titolo ---
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 12, "CONSIGLIO PRESCRITTIVO INTEGRATORI", ln=True, align='C')
    pdf.set_draw_color(52, 152, 219)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # --- Dati paziente ---
    pdf.set_fill_color(240, 244, 248)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 9, " DATI PAZIENTE", ln=True, fill=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(95, 7, f"Paziente: {p_info.get('Nome','')} {p_info.get('Cognome','')}", ln=False)
    pdf.cell(0, 7, f"Codice Fiscale: {p_info.get('Codice_Fiscale','')}", ln=True)
    pdf.cell(95, 7, f"Data di Nascita: {p_info.get('Data_Nascita','')}", ln=False)
    pdf.cell(0, 7, f"Data Visita: {data_visita}", ln=True)
    pdf.ln(6)

    # --- Tabella integratori ---
    pdf.set_fill_color(52, 152, 219)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(10, 9, "#", 1, 0, 'C', fill=True)
    pdf.cell(30, 9, "Data Inizio", 1, 0, 'C', fill=True)
    pdf.cell(65, 9, "Integratore", 1, 0, 'C', fill=True)
    pdf.cell(85, 9, "Posologia", 1, 1, 'C', fill=True)
    pdf.set_text_color(0, 0, 0)

    fill = False
    for idx, row in prescrizioni_df.iterrows():
        pdf.set_fill_color(240, 248, 255) if fill else pdf.set_fill_color(255, 255, 255)
        num = str(prescrizioni_df.index.get_loc(idx) + 1)
        posologia_txt = str(row.get('Posologia', ''))
        # salva posizione iniziale riga
        y_start = pdf.get_y()
        x_start = pdf.get_x()
        # calcola altezza necessaria per la posologia
        char_per_line = 42
        lines_needed = max(1, -(-len(posologia_txt) // char_per_line))  # ceiling division
        row_h = max(8, 7 * lines_needed)
        pdf.set_font("Arial", '', 9)
        pdf.cell(10, row_h, num, 1, 0, 'C', fill=fill)
        pdf.cell(30, row_h, str(row.get('Data_Inizio', '')), 1, 0, 'C', fill=fill)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(65, row_h, str(row.get('Nome_Integratore', '')), 1, 0, 'L', fill=fill)
        # posologia con wrap
        pdf.set_font("Arial", '', 9)
        x_pos = pdf.get_x()
        pdf.multi_cell(85, 7, posologia_txt, 1, 'L', fill=fill)
        # riposiziona dopo la riga
        pdf.set_xy(x_start, y_start + row_h)
        fill = not fill

    # --- Note aggiuntive ---
    note_valide = prescrizioni_df['Note_Prescrizione'].dropna()
    note_valide = note_valide[note_valide.str.strip() != ""]
    if not note_valide.empty:
        pdf.ln(8)
        pdf.set_fill_color(255, 249, 219)
        pdf.set_draw_color(230, 180, 0)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, " NOTE AGGIUNTIVE", ln=True, fill=True)
        pdf.set_font("Arial", '', 10)
        pdf.set_draw_color(0, 0, 0)
        for nota in note_valide.values:
            pdf.multi_cell(0, 6, f"• {nota}")

    return bytes(pdf.output())

def genera_pdf_report(p_info, storico, dieta, scorte_df=None, data_visita="N/D"):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 15, "REPORT CLINICO E PIANO NUTRIZIONALE VLEKT", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, f"Paziente: {p_info['Nome']} {p_info['Cognome']} - Visita del: {data_visita}", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, f"Codice Fiscale: {p_info['Codice_Fiscale']} | Nascita: {p_info['Data_Nascita']}", ln=True)
    pdf.cell(0, 5, f"Cellulare: {p_info.get('Cellulare', 'N/D')} | Email: {p_info.get('Email', 'N/D')}", ln=True)
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 12)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, " PARAMETRI ANTROPOMETRICI", ln=True, fill=True)
    pdf.set_font("Arial", '', 11)
    
    v_info = storico[storico['Data_Visita'] == data_visita]
    if not v_info.empty:
        v_info = v_info.iloc[0]
        pdf.cell(0, 8, f"Peso: {v_info['Peso']}kg | BMI: {v_info['BMI']} | Altezza: {v_info['Altezza']}cm", ln=True)
        pdf.cell(0, 8, f"Addome: {v_info['Addome']}cm | Fianchi: {v_info['Fianchi']}cm | Torace: {v_info['Torace']}cm", ln=True)
    else:
        pdf.cell(0, 8, f"Peso: {p_info['Peso']}kg | BMI: {p_info['BMI']} | Altezza: {p_info['Altezza']}cm", ln=True)
    pdf.ln(5)

    if not dieta.empty:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, " PIANO ALIMENTARE VLEKT ASSEGNATO", ln=True, fill=True)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(35, 8, "Pasto", 1); pdf.cell(50, 8, "Alimento", 1); pdf.cell(15, 8, "Qt.", 1)
        pdf.cell(18, 8, "Kcal", 1); pdf.cell(18, 8, "Grassi", 1); pdf.cell(18, 8, "Prot", 1); pdf.cell(18, 8, "Carbo", 1); pdf.ln()
        
        pdf.set_font("Arial", '', 8)
        d_ord = dieta.copy()
        d_ord['sort'] = d_ord['Pasto'].map(ORDINE_PASTI)
        # Recupera valori unitari dal db alimenti
        d_ord = d_ord.merge(df_a[['Alimento','Kcal','Carbo_Netti','Prot','Grassi']], on='Alimento', how='left')
        for _, r in d_ord.sort_values('sort').iterrows():
            kcal_u = to_f(r.get('Kcal', r['Kcal_Tot']))
            grassi_u = to_f(r.get('Grassi', r['Grassi_Tot']))
            prot_u = to_f(r.get('Prot', r['Prot_Tot']))
            carbo_u = to_f(r.get('Carbo_Netti', r['Carbo_Tot']))
            # Rimuove emoji e caratteri non-ASCII per compatibilità font PDF
            nome_pdf = str(r['Alimento']).replace('🥩 ', '[P] ').replace('•', '-').encode('latin-1', errors='ignore').decode('latin-1')
            pdf.cell(35, 8, str(r['Pasto']), 1); pdf.cell(50, 8, nome_pdf, 1); pdf.cell(15, 8, str(r['Quantita']), 1)
            pdf.cell(18, 8, f"{kcal_u:.1f}", 1); pdf.cell(18, 8, f"{grassi_u:.1f}", 1)
            pdf.cell(18, 8, f"{prot_u:.1f}", 1); pdf.cell(18, 8, f"{carbo_u:.1f}", 1); pdf.ln()

    if scorte_df is not None and not scorte_df.empty:
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(220, 240, 220)
        pdf.cell(0, 10, f" FABBISOGNO ESATTO E PRODOTTI DA ACQUISTARE", ln=True, fill=True)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(95, 8, "Pasto Sostitutivo", 1); pdf.cell(20, 8, "Pz/Scatola", 1)
        pdf.cell(55, 8, "Scatole da Acquistare", 1); pdf.ln()
        
        pdf.set_font("Arial", '', 9)
        for _, row_s in scorte_df.iterrows():
            ali_pdf = str(row_s['Alimento']).replace('🥩 ', '[P] ').replace('•', '-').encode('latin-1', errors='ignore').decode('latin-1')
            pdf.cell(95, 8, ali_pdf, 1)
            pdf.cell(20, 8, str(row_s['Porzioni_Confezione']), 1, 0, 'C')
            pdf.cell(55, 8, str(row_s['Confezioni_Necessarie']), 1, 0, 'C')
            pdf.ln()

    if len(storico) >= 2:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "EVOLUZIONE DEL PESO NEL TEMPO", ln=True, align='C')
        plt.figure(figsize=(6, 3))
        st_ord = storico.copy()
        st_ord['DT'] = pd.to_datetime(st_ord['Data_Visita'], format='%d/%m/%Y', errors='coerce')
        st_ord = st_ord.dropna(subset=['DT']).sort_values('DT')
        plt.plot(st_ord['Data_Visita'], st_ord['Peso'].astype(float), marker='o', color='gold', linewidth=2)
        plt.grid(True, alpha=0.3)
        buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=150); buf.seek(0)
        pdf.image(buf, x=15, y=30, w=180); plt.close()

    return bytes(pdf.output())

def colora_pasti(row):
    pasto = row['Pasto']
    if pasto == 'Colazione': color = '#FFF3CD'
    elif pasto in ('Spuntino Mattina', 'Spuntino/Merenda'): color = '#FFE6CC'
    elif pasto == 'Pranzo': color = '#D4EDDA'
    elif pasto == 'Merenda': color = '#D1ECF1'
    elif pasto == 'Cena': color = '#E2E3E5'
    elif pasto == 'Dopo Cena': color = '#E8DAEF'
    else: color = '#FFFFFF'
    return [f'background-color: {color}'] * len(row)


# --- FUNZIONE FORM ANTROPOMETRICO ---
def _v(d, key, default=0.0):
    """Legge un valore da un dict/Series, restituisce default se assente/nan."""
    if d is None: return default
    try:
        if isinstance(d, dict):
            val = d.get(key, default)
        else:
            val = d[key] if key in d.index else default
        r = to_f(val)
        return r if r != 0.0 else default
    except:
        return default

def form_antropometria(prefix, d_form=None):
    """Sezione espandibile con tutti i campi antropometrici. Restituisce dict."""
    vals = {}
    # CSS per nascondere i bottoni +/- dei number_input
    st.markdown("""
    <style>
    button[data-testid="stNumberInputStepDown"],
    button[data-testid="stNumberInputStepUp"] { display: none !important; }
    </style>""", unsafe_allow_html=True)

    with st.expander("📐 Antropometria dettagliata (Circonferenze, Pliche, Diametri)", expanded=False):
        st.markdown("""<div style="background:#f0f4f8;border-left:4px solid #6366f1;border-radius:6px;
             padding:8px 14px;margin-bottom:12px;font-size:12px;color:#4338ca;font-weight:600;">
            📏 Dati facoltativi — compilare quelli disponibili. Le differenze destra/sinistra sono calcolate in tempo reale.
        </div>""", unsafe_allow_html=True)

        # ── CIRCONFERENZE ──
        st.markdown("##### 📏 Circonferenze (cm)")
        st.markdown("<div style='display:flex;gap:4px;font-size:11px;color:#6b7280;margin-bottom:4px;'><span style='width:40%;'>Segmento</span><span style='width:25%;text-align:center;'>Destro/a</span><span style='width:25%;text-align:center;'>Sinistro/a</span><span style='width:10%;text-align:center;'>Diff.</span></div>", unsafe_allow_html=True)

        for lbl, kdx, ksx in [
            ("Polso",              "Circ_Polso_Dx",       "Circ_Polso_Sx"),
            ("Avambraccio",        "Circ_Avambraccio_Dx", "Circ_Avambraccio_Sx"),
            ("Braccio",            "Circ_Braccio_Dx",     "Circ_Braccio_Sx"),
            ("Coscia prossimale",  "Circ_Coscia_Prox_Dx", "Circ_Coscia_Prox_Sx"),
            ("Coscia mediana",     "Circ_Coscia_Med_Dx",  "Circ_Coscia_Med_Sx"),
            ("Coscia distale",     "Circ_Coscia_Dist_Dx", "Circ_Coscia_Dist_Sx"),
            ("Polpaccio",          "Circ_Polpaccio_Dx",   "Circ_Polpaccio_Sx"),
            ("Caviglia",           "Circ_Caviglia_Dx",    "Circ_Caviglia_Sx"),
        ]:
            c1, c2, c3, c4 = st.columns([2, 1, 1, 0.6])
            c1.markdown(f"<div style='padding-top:28px;font-size:13px;font-weight:600;color:#374151;'>{lbl}</div>", unsafe_allow_html=True)
            k1 = f"{prefix}_{kdx}"
            k2 = f"{prefix}_{ksx}"
            vals[kdx] = c2.number_input("dx", value=_v(d_form, kdx), key=k1, label_visibility="collapsed", format="%.1f")
            vals[ksx] = c3.number_input("sx", value=_v(d_form, ksx), key=k2, label_visibility="collapsed", format="%.1f")
            diff = abs(vals[kdx] - vals[ksx])
            diff_color = "#e74c3c" if diff > 2 else "#2ecc71" if diff == 0 else "#f39c12"
            c4.markdown(f"<div style='padding-top:28px;font-size:13px;font-weight:800;color:{diff_color};text-align:center;'>{diff:.1f}</div>", unsafe_allow_html=True)

        # Misure singole
        cs1, cs2, cs3, cs4, cs5 = st.columns(5)
        vals["Circ_Spalle"]      = cs1.number_input("Spalle",  value=_v(d_form,"Circ_Spalle"),      key=f"{prefix}_Circ_Spalle",      format="%.1f")
        vals["Circ_Torace_Ant"]  = cs2.number_input("Torace",  value=_v(d_form,"Circ_Torace_Ant"),  key=f"{prefix}_Circ_Torace_Ant",  format="%.1f")
        vals["Circ_Vita"]        = cs3.number_input("Vita",    value=_v(d_form,"Circ_Vita"),        key=f"{prefix}_Circ_Vita",        format="%.1f")
        vals["Circ_Addome_Ant"]  = cs4.number_input("Addome",  value=_v(d_form,"Circ_Addome_Ant"),  key=f"{prefix}_Circ_Addome_Ant",  format="%.1f")
        vals["Circ_Fianchi_Ant"] = cs5.number_input("Fianchi", value=_v(d_form,"Circ_Fianchi_Ant"), key=f"{prefix}_Circ_Fianchi_Ant", format="%.1f")

        st.markdown("---")

        # ── PLICHE ──
        st.markdown("##### 📌 Pliche (mm)")
        pliche_list = [
            ("Avambraccio","Plica_Avambraccio"), ("Bicipitale","Plica_Bicipitale"),
            ("Tricipitale","Plica_Tricipitale"),  ("Ascellare","Plica_Ascellare"),
            ("Pettorale/Torac.","Plica_Pettorale"), ("Sottoscapolare","Plica_Sottoscapolare"),
            ("Addominale","Plica_Addominale"),    ("Soprailiaca","Plica_Soprailiaca"),
            ("Mediana coscia","Plica_Coscia_Med"), ("Soprapatellare","Plica_Soprapatellare"),
            ("Med. polpaccio","Plica_Polpaccio_Med"), ("Sopraspinale","Plica_Sopraspinale"),
        ]
        for row_start in range(0, len(pliche_list), 4):
            cols = st.columns(4)
            for ci, (lbl, key) in enumerate(pliche_list[row_start:row_start+4]):
                vals[key] = cols[ci].number_input(lbl, value=_v(d_form, key), key=f"{prefix}_{key}", format="%.1f")

        st.markdown("---")

        # ── DIAMETRI OSSEI ──
        st.markdown("##### 🦴 Diametri ossei (cm)")
        diam_list = [
            ("Polso","Diam_Polso"), ("Gomito","Diam_Gomito"), ("Biacromiale","Diam_Biacromiale"),
            ("Toracico","Diam_Toracico"), ("Bicrestale","Diam_Bicrestale"), ("Addominale sag.","Diam_Addominale_Sag"),
            ("Bitrocanterico","Diam_Bitrocanterio"), ("Ginocchio","Diam_Ginocchio"), ("Caviglia","Diam_Caviglia"),
        ]
        for row_start in range(0, len(diam_list), 3):
            cols = st.columns(3)
            for ci, (lbl, key) in enumerate(diam_list[row_start:row_start+3]):
                vals[key] = cols[ci].number_input(lbl, value=_v(d_form, key), key=f"{prefix}_{key}", format="%.1f")

        note_antro_val = ""
        if d_form is not None:
            try: note_antro_val = str(d_form.get("Note_Antropometria", "") or "").replace("nan", "")
            except: note_antro_val = ""
        vals["Note_Antropometria"] = st.text_area("Note antropometria", value=note_antro_val, key=f"{prefix}_Note_Antro", height=70)

    return vals

# --- 4. SESSION STATE ---
if 'p_attivo' not in st.session_state: st.session_state.p_attivo = None
if 'm_modulo' not in st.session_state: st.session_state.m_modulo = False
if 'idx_mod' not in st.session_state: st.session_state.idx_mod = None
if 'edit_food_idx' not in st.session_state: st.session_state.edit_food_idx = None
if 'edit_anagrafica' not in st.session_state: st.session_state.edit_anagrafica = False
if 'confirm_delete_paz' not in st.session_state: st.session_state.confirm_delete_paz = False
if 'prescr_nome_input' not in st.session_state: st.session_state.prescr_nome_input = ""
if 'visita_idx_sel' not in st.session_state: st.session_state.visita_idx_sel = None
if 'show_db_alimenti' not in st.session_state: st.session_state.show_db_alimenti = False
if 'show_db_integratori' not in st.session_state: st.session_state.show_db_integratori = False
if 'show_db_proteine' not in st.session_state: st.session_state.show_db_proteine = False
if 'show_utility' not in st.session_state: st.session_state.show_utility = False

# --- 5. SIDEBAR ---
with st.sidebar:
    # Blocco Utente
    if _auth:
        st.caption(f"👤 {st.session_state.logged_user}")
        if st.button("🚪 Esci", use_container_width=True, key="btn_logout"):
            st.session_state.logged_user = None
            st.session_state.show_admin = False
            st.session_state.p_attivo = None
            st.session_state.m_modulo = False
            st.session_state.show_utility = False
            st.rerun()
        if _is_admin:
            if st.button("⚙️ Amministrazione", use_container_width=True, key="btn_admin"):
                st.session_state.show_admin = True
                st.session_state.p_attivo = None
                st.session_state.show_db_alimenti = False
                st.session_state.show_db_integratori = False
                st.session_state.show_db_proteine = False
                st.session_state.show_utility = False
                st.rerun()
        st.markdown("---")

    # Blocco Paziente — selezione unificata con filtro
    st.markdown("<p class='sidebar-section'>👤 Paziente</p>", unsafe_allow_html=True)
    search = st.text_input("Filtra (cognome o CF)", placeholder="Cerca...").strip()
    if not df_p.empty:
        df_p_unique = df_p.drop_duplicates('Codice_Fiscale').sort_values('Cognome')
        # Filtra in base alla ricerca
        if search:
            mask = (df_p_unique['Cognome'].str.contains(search, case=False, na=False) |
                    df_p_unique['Nome'].str.contains(search, case=False, na=False) |
                    df_p_unique['Codice_Fiscale'].str.contains(search, case=False, na=False))
            df_filt = df_p_unique[mask]
        else:
            df_filt = df_p_unique
        # Lista opzioni filtrata (max 80 per leggibilità)
        mappa = {"-- Scegli Paziente --": "-- Scegli Paziente --"}
        for _, row in df_filt.head(80).iterrows():
            mappa[row['Codice_Fiscale']] = f"{row['Cognome']} {row['Nome']}"
        cf_list = list(mappa.keys())

        def on_change_paziente():
            cf = st.session_state._sb_lista_pazienti
            if cf and cf != "-- Scegli Paziente --":
                match = df_p[df_p['Codice_Fiscale'] == cf]
                if not match.empty:
                    st.session_state.p_attivo = match.iloc[-1].to_dict()
                    st.session_state.m_modulo = False
                    st.session_state.idx_mod = None
                    st.session_state.edit_anagrafica = False
                    st.session_state.confirm_delete_paz = False
                    st.session_state.visita_idx_sel = None
                    st.session_state.show_db_alimenti = False
                    st.session_state.show_db_integratori = False
                    st.session_state.show_db_proteine = False
                    st.session_state.show_utility = False
                    st.session_state._pending_rerun = True
            else:
                st.session_state.p_attivo = None
                st.session_state._pending_rerun = True

        st.selectbox(
            "Seleziona paziente:",
            cf_list,
            format_func=lambda x: mappa[x],
            key="_sb_lista_pazienti",
            on_change=on_change_paziente
        )
    else:
        st.caption("Nessun paziente. Crea il primo.")

    st.markdown('<div class="crea-paziente-anchor" style="margin:4px 0;"></div>', unsafe_allow_html=True)
    if st.button("➕ Crea nuovo paziente", use_container_width=True, type="primary", key="btn_crea_nuovo_paziente"):
        st.session_state.p_attivo = None
        st.session_state.m_modulo = True
        st.session_state.idx_mod = None
        st.session_state.edit_anagrafica = False
        st.session_state.show_db_alimenti = False
        st.session_state.show_db_integratori = False
        st.session_state.show_db_proteine = False
        st.rerun()

    st.markdown("---")
    st.markdown("<p class='sidebar-section'>📋 Gestione Database</p>", unsafe_allow_html=True)
    if st.button("🍱 Alimenti VLEKT", use_container_width=True):
        st.session_state.show_db_alimenti = True
        st.session_state.show_db_integratori = False
        st.session_state.show_db_proteine = False
        st.session_state.show_utility = False
        st.session_state.p_attivo = None
        st.session_state.m_modulo = False
        st.session_state.edit_food_idx = None
        st.rerun()
    if st.button("💊 Integratori", use_container_width=True):
        st.session_state.show_db_integratori = True
        st.session_state.show_db_alimenti = False
        st.session_state.show_db_proteine = False
        st.session_state.show_utility = False
        st.session_state.p_attivo = None
        st.session_state.m_modulo = False
        st.session_state.edit_integr_idx = None
        st.rerun()
    if st.button("🥩 Proteine Naturali", use_container_width=True):
        st.session_state.show_db_proteine = True
        st.session_state.show_db_alimenti = False
        st.session_state.show_db_integratori = False
        st.session_state.show_utility = False
        st.session_state.p_attivo = None
        st.session_state.m_modulo = False
        st.rerun()

    st.markdown("---")
    st.markdown("<p class='sidebar-section'>🔧 Utility</p>", unsafe_allow_html=True)
    if st.button("🛠️ Backup, Restore, Statistiche", use_container_width=True):
        st.session_state.show_utility = True
        st.session_state.show_db_alimenti = False
        st.session_state.show_db_integratori = False
        st.session_state.show_db_proteine = False
        st.session_state.p_attivo = None
        st.session_state.m_modulo = False
        st.rerun()

    # Rerun dopo selezione paziente (st.rerun() in callback è no-op, si usa flag)
    if st.session_state.get('_pending_rerun'):
        del st.session_state._pending_rerun
        st.rerun()

# --- 5b. AREA AMMINISTRAZIONE ---
if _auth and st.session_state.get('show_admin'):
    st.markdown("<h2 style='color:#2c3e50;font-weight:900;'>⚙️ Amministrazione utenti</h2>", unsafe_allow_html=True)
    if st.button("🔙 Torna all'app", key="btn_back_admin"):
        st.session_state.show_admin = False
        st.session_state.admin_reset_user = None
        st.rerun()
    st.markdown("---")

    if 'admin_reset_user' not in st.session_state:
        st.session_state.admin_reset_user = None

    # ── SEZIONE 1: Cambia la tua password (admin) ──
    with st.expander("🔐 Cambia la tua password", expanded=False):
        with st.form("admin_cambia_pwd"):
            pwd_attuale = st.text_input("Password attuale", type="password")
            pwd_nuova = st.text_input("Nuova password", type="password")
            pwd_ripeti = st.text_input("Ripeti nuova password", type="password")
            if st.form_submit_button("Aggiorna password"):
                if not pwd_attuale or not pwd_nuova:
                    st.error("Compila tutti i campi.")
                elif pwd_nuova != pwd_ripeti:
                    st.error("Le password non coincidono.")
                elif len(pwd_nuova) < 6:
                    st.error("La password deve essere di almeno 6 caratteri.")
                else:
                    ok_ver, _ = _auth.verify_login(st.session_state.logged_user, pwd_attuale)
                    if not ok_ver:
                        st.error("Password attuale non corretta.")
                    else:
                        ok, msg = _auth.change_password(st.session_state.logged_user, pwd_nuova)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    st.markdown("---")

    # ── SEZIONE 2: Lista utenti ──
    st.markdown("#### 👥 Utenti registrati")
    users = _auth.get_all_users()
    if not users:
        st.info("Nessun utente. Crea il primo dalla sezione qui sotto.")
    else:
        for u in users:
            uname = u.get('username', '')
            attivo = u.get('attivo', True)
            is_adm = u.get('is_admin', False)
            created = u.get('created_at', '')[:10] if u.get('created_at') else '—'
            stato = "🟢 Attivo" if attivo else "🔴 Disattivato"
            badge = "`admin`" if is_adm else ""
            with st.container():
                c1, c2, c3 = st.columns([2, 1.5, 1])
                with c1:
                    nome_cognome = f"{u.get('cognome', '')} {u.get('nome', '')}".strip() or uname
                    st.markdown(f"**{nome_cognome}** {badge}")
                    st.caption(f"@{uname} — Creato: {created}")
                with c2:
                    if not is_adm:
                        label_toggle = "Disattiva" if attivo else "Attiva"
                        if st.button(label_toggle, key=f"toggle_{uname}"):
                            _auth.toggle_user_active(uname)
                            st.rerun()
                with c3:
                    if uname != st.session_state.logged_user and not is_adm:
                        if st.button("Reset pwd", key=f"reset_{uname}"):
                            st.session_state.admin_reset_user = uname
                            st.rerun()
                st.markdown("---")

    # Modal: reset password (altro utente)
    if st.session_state.admin_reset_user:
        st.markdown(f"##### 🔑 Imposta nuova password per **{st.session_state.admin_reset_user}**")
        with st.form("form_reset_pwd"):
            rp1 = st.text_input("Nuova password", type="password")
            rp2 = st.text_input("Ripeti password", type="password")
            rc1, rc2 = st.columns(2)
            if rc1.form_submit_button("Salva"):
                if rp1 and rp2 and rp1 == rp2 and len(rp1) >= 6:
                    ok, msg = _auth.change_password(st.session_state.admin_reset_user, rp1)
                    if ok:
                        st.success(msg)
                        st.session_state.admin_reset_user = None
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("Password non valide o non coincidono.")
            if rc2.form_submit_button("Annulla"):
                st.session_state.admin_reset_user = None
                st.rerun()

    st.markdown("---")

    # ── SEZIONE 3: Nuovo utente ──
    st.markdown("#### ➕ Crea nuovo utente")
    with st.form("admin_nuovo_utente"):
        cn, cc = st.columns(2)
        with cn:
            nuovo_nome = st.text_input("Nome", placeholder="es. Mario")
        with cc:
            nuovo_cognome = st.text_input("Cognome", placeholder="es. Rossi")
        nu = st.text_input("Username", placeholder="es. mario.rossi")
        np = st.text_input("Password", type="password", placeholder="minimo 6 caratteri")
        np_rip = st.text_input("Ripeti password", type="password")
        if st.form_submit_button("Crea utente"):
            if not nu or not np:
                st.error("Inserisci username e password.")
            elif np != np_rip:
                st.error("Le password non coincidono.")
            elif len(np) < 6:
                st.error("La password deve essere di almeno 6 caratteri.")
            else:
                ok, msg = _auth.create_user(nu, np, is_admin_user=False, nome=nuovo_nome or "", cognome=nuovo_cognome or "")
                if ok:
                    _auth.init_user_data_folder(_auth.get_user_data_dir(nu), [
                        ('database_pazienti.csv', COLS_PAZ),
                        ('database_alimenti.csv', COLS_ALI),
                        ('database_diete.csv', COLS_DIETA),
                        ('database_integratori.csv', COLS_INTEGR),
                        ('database_prescrizioni.csv', COLS_PRESCR),
                        ('database_proteine.csv', COLS_PROT),
                    ])
                    st.success(msg)
                else:
                    st.error(msg)
                st.rerun()

    st.stop()


def _render_navbar():
    """Barra superiore stile Nutriverso: logo + breadcrumb. Mostrata solo in area principale (non login, non admin)."""
    p_r = st.session_state.p_attivo
    show_utility = st.session_state.get("show_utility", False)
    show_db_a = st.session_state.get("show_db_alimenti", False)
    show_db_i = st.session_state.get("show_db_integratori", False)
    show_db_p = st.session_state.get("show_db_proteine", False)

    if show_utility:
        bread = "Pazienti &gt; Utility"
    elif show_db_a:
        bread = "Database &gt; Alimenti VLEKT"
    elif show_db_i:
        bread = "Database &gt; Integratori"
    elif show_db_p:
        bread = "Database &gt; Proteine naturali"
    elif p_r:
        nome = f"{p_r.get('Cognome', '')} {p_r.get('Nome', '')}".strip() or "Paziente"
        bread = f"Pazienti &gt; <span style='color:#f1f5f9;'>{nome}</span>"
    else:
        bread = "Pazienti &gt; Panoramica"

    html = f"""
    <div class="vlekt-navbar">
        <div class="vlekt-navbar-left">
            <span class="vlekt-navbar-logo">VLEKT <span>PRO</span></span>
            <span class="vlekt-breadcrumb">{bread}</span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# --- 6. INTERFACCIA PRINCIPALE ---
p_r = st.session_state.p_attivo
idx_mod = st.session_state.idx_mod
# Protezione: se idx_mod non è più valido (visita eliminata), lo azzeriamo
if idx_mod is not None and (idx_mod >= len(df_p) or idx_mod not in df_p.index):
    st.session_state.idx_mod = None
    idx_mod = None
d_form = df_p.iloc[idx_mod] if idx_mod is not None else p_r

# Navbar stile Nutriverso (logo + breadcrumb) — sopra tutto il contenuto principale
_render_navbar()

# CTA principale (Nuova visita / Crea paziente) a destra sotto la navbar — solo su home e scheda paziente
_show_nav_cta = not st.session_state.get("show_utility") and not st.session_state.get("show_db_alimenti") and not st.session_state.get("show_db_integratori") and not st.session_state.get("show_db_proteine")
if _show_nav_cta:
    _nav_cta_col1, _nav_cta_col2 = st.columns([5, 1])
    with _nav_cta_col2:
        if p_r is not None:
            if st.button("Nuova visita", type="primary", key="navbar_nuova_visita", use_container_width=True):
                st.session_state.m_modulo = True
                st.session_state.idx_mod = None
                st.rerun()
        else:
            if st.button("Crea paziente", type="primary", key="navbar_crea_paziente", use_container_width=True):
                st.session_state.p_attivo = None
                st.session_state.m_modulo = True
                st.session_state.idx_mod = None
                st.session_state.edit_anagrafica = False
                st.rerun()

# Inizializza session state integratori se mancanti
if 'edit_integr_idx' not in st.session_state: st.session_state.edit_integr_idx = None
if 'confirm_del_integr' not in st.session_state: st.session_state.confirm_del_integr = None
if 'confirm_del_visita' not in st.session_state: st.session_state.confirm_del_visita = False
if 'confirm_del_pasto' not in st.session_state: st.session_state.confirm_del_pasto = None
if 'confirm_del_piano' not in st.session_state: st.session_state.confirm_del_piano = False
if 'confirm_del_prescr' not in st.session_state: st.session_state.confirm_del_prescr = None

def chiudi_db():
    st.session_state.show_db_alimenti = False
    st.session_state.show_db_integratori = False
    st.session_state.show_db_proteine = False
    st.session_state.show_utility = False
    st.session_state.edit_food_idx = None
    st.session_state.edit_integr_idx = None
    st.session_state.confirm_del_integr = None

# ══════════════════════════════════════════════════════
# PAGINA UTILITY
# ══════════════════════════════════════════════════════
if st.session_state.show_utility:
    st.markdown("<h2 style='color:#2c3e50;font-weight:900;'>🔧 Utility</h2>", unsafe_allow_html=True)

    if st.button("🔙 Chiudi Utility", use_container_width=False):
        st.session_state.show_utility = False
        st.rerun()

    st.markdown("---")

    # Lista file database
    DB_FILES = [
        (DB_PAZIENTI, "Pazienti e visite"),
        (DB_ALIMENTI, "Alimenti VLEKT"),
        (DB_DIETE, "Piani dietetici"),
        (DB_INTEGRATORI, "Integratori"),
        (DB_PRESCRIZIONI, "Prescrizioni"),
        (DB_PROTEINE, "Proteine naturali"),
    ]
    app_dir = os.path.dirname(os.path.abspath(__file__))

    # ── 1. BACKUP DATABASE ──
    st.markdown("#### 📦 Backup database")
    st.markdown("Salva tutti i file CSV in un archivio ZIP con timestamp. Conservalo in un luogo sicuro.")
    if st.button("📥 Crea backup completo", type="primary", key="btn_backup"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"backup_vlekt_{ts}.zip"
        zip_path = os.path.join(app_dir, zip_name)
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for db_file, _ in DB_FILES:
                    fp = os.path.join(app_dir, db_file)
                    if os.path.exists(fp):
                        zf.write(fp, db_file)
            with open(zip_path, 'rb') as f:
                st.session_state.backup_bytes = f.read()
            st.session_state.backup_filename = zip_name
            os.remove(zip_path)
            st.rerun()
        except Exception as e:
            st.error(f"Errore durante il backup: {e}")

    if 'backup_bytes' in st.session_state and st.session_state.backup_bytes:
        st.download_button(
            "⬇️ Scarica backup",
            data=st.session_state.backup_bytes,
            file_name=st.session_state.get('backup_filename', 'backup_vlekt.zip'),
            mime="application/zip",
            key="dl_backup"
        )
        if st.button("🗑️ Annulla download", key="btn_clear_backup"):
            del st.session_state.backup_bytes
            if 'backup_filename' in st.session_state:
                del st.session_state.backup_filename
            st.rerun()

    st.markdown("---")

    # ── 2. RESTORE DA BACKUP ──
    st.markdown("#### 📤 Ripristino da backup")
    st.markdown("Carica un file ZIP di backup precedente per sostituire i database attuali. **Attenzione: sovrascrive i dati correnti.**")
    file_restore = st.file_uploader("Carica file ZIP di backup", type=["zip"], key="upload_restore")
    if file_restore:
        if st.button("⚠️ Ripristina database (conferma)", type="primary", key="btn_restore"):
            try:
                with zipfile.ZipFile(file_restore, 'r') as zf:
                    for name in zf.namelist():
                        if name.endswith('.csv'):
                            zf.extract(name, app_dir)
                st.success("✅ Backup ripristinato. Ricarica la pagina per vedere i dati aggiornati.")
                st.rerun()
            except Exception as e:
                st.error(f"Errore durante il ripristino: {e}")

    st.markdown("---")

    # ── 3. STATISTICHE ──
    st.markdown("#### 📊 Statistiche database")
    n_paz = len(df_p.drop_duplicates('Codice_Fiscale')) if not df_p.empty else 0
    n_visite = len(df_p)
    n_alimenti = len(df_a)
    n_diete_righe = len(df_d)
    n_integr = len(df_i)
    n_prescriz = len(df_pr)
    n_prot = len(df_prot)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👤 Pazienti unici", n_paz)
        st.metric("📋 Visite totali", n_visite)
    with col2:
        st.metric("🍱 Alimenti VLEKT", n_alimenti)
        st.metric("📅 Righe piani dieta", n_diete_righe)
    with col3:
        st.metric("💊 Integratori", n_integr)
        st.metric("📝 Prescrizioni", n_prescriz)
    st.metric("🥩 Proteine naturali", n_prot)

    st.markdown("---")

    # ── 4. VERIFICA INTEGRITÀ ──
    st.markdown("#### 🔍 Verifica integrità")
    st.markdown("Controlla riferimenti orfani (diete o prescrizioni senza paziente corrispondente).")
    if st.button("Esegui verifica", key="btn_verify"):
        cf_pazienti = set(df_p['Codice_Fiscale'].astype(str).str.strip().unique()) if not df_p.empty else set()
        orfani_d = df_d[~df_d['Codice_Fiscale'].astype(str).str.strip().isin(cf_pazienti)] if not df_d.empty else pd.DataFrame()
        orfani_pr = df_pr[~df_pr['Codice_Fiscale'].astype(str).str.strip().isin(cf_pazienti)] if not df_pr.empty else pd.DataFrame()
        if orfani_d.empty and orfani_pr.empty:
            st.success("✅ Nessun riferimento orfano trovato.")
        else:
            if not orfani_d.empty:
                st.warning(f"⚠️ **{len(orfani_d)}** righe di dieta riferite a CF non presenti nei pazienti.")
            if not orfani_pr.empty:
                st.warning(f"⚠️ **{len(orfani_pr)}** prescrizioni riferite a CF non presenti nei pazienti.")

    st.markdown("---")

    # ── 5. PULIZIA DUPLICATI ──
    st.markdown("#### 🧹 Pulizia duplicati")
    st.markdown("Rimuove righe duplicate dai database. Per pazienti e diete si mantiene l’ultima occorrenza; per gli altri la prima.")
    if st.button("Esegui pulizia duplicati", type="primary", key="btn_clean_dup"):
        modifiche = []
        # Pazienti: stesso CF + stessa Data_Visita → tiene l'ultima
        if not df_p.empty:
            n_prima = len(df_p)
            df_p_clean = df_p.drop_duplicates(subset=['Codice_Fiscale', 'Data_Visita'], keep='last')
            if len(df_p_clean) < n_prima:
                df_p_clean.to_csv(DB_PAZIENTI, index=False)
                modifiche.append(f"Pazienti: rimossi {n_prima - len(df_p_clean)} duplicati")
        # Alimenti: stesso nome → tiene la prima
        if not df_a.empty:
            n_prima = len(df_a)
            df_a_clean = df_a.drop_duplicates(subset=['Alimento'], keep='first')
            if len(df_a_clean) < n_prima:
                df_a_clean.to_csv(DB_ALIMENTI, index=False)
                modifiche.append(f"Alimenti: rimossi {n_prima - len(df_a_clean)} duplicati")
        # Diete: righe identiche → tiene la prima
        if not df_d.empty:
            n_prima = len(df_d)
            df_d_clean = df_d.drop_duplicates(keep='first')
            if len(df_d_clean) < n_prima:
                df_d_clean.to_csv(DB_DIETE, index=False)
                modifiche.append(f"Diete: rimossi {n_prima - len(df_d_clean)} duplicati")
        # Integratori: stesso nome → tiene la prima
        if not df_i.empty:
            n_prima = len(df_i)
            df_i_clean = df_i.drop_duplicates(subset=['Nome_Integratore'], keep='first')
            if len(df_i_clean) < n_prima:
                df_i_clean.to_csv(DB_INTEGRATORI, index=False)
                modifiche.append(f"Integratori: rimossi {n_prima - len(df_i_clean)} duplicati")
        # Prescrizioni: stesso CF + Data_Visita + Data_Inizio + Nome → tiene la prima
        if not df_pr.empty:
            n_prima = len(df_pr)
            df_pr_clean = df_pr.drop_duplicates(subset=['Codice_Fiscale', 'Data_Visita', 'Data_Inizio', 'Nome_Integratore'], keep='first')
            if len(df_pr_clean) < n_prima:
                df_pr_clean.to_csv(DB_PRESCRIZIONI, index=False)
                modifiche.append(f"Prescrizioni: rimossi {n_prima - len(df_pr_clean)} duplicati")
        # Proteine: stesso Nome → tiene la prima
        if not df_prot.empty:
            n_prima = len(df_prot)
            df_prot_clean = df_prot.drop_duplicates(subset=['Nome'], keep='first')
            if len(df_prot_clean) < n_prima:
                df_prot_clean.to_csv(DB_PROTEINE, index=False)
                modifiche.append(f"Proteine: rimossi {n_prima - len(df_prot_clean)} duplicati")

        if modifiche:
            for m in modifiche:
                st.success(f"✅ {m}")
            st.info("Ricarica la pagina per vedere i dati aggiornati.")
            st.rerun()
        else:
            st.success("✅ Nessun duplicato trovato.")

# ══════════════════════════════════════════════════════
# PAGINA DB ALIMENTI
# ══════════════════════════════════════════════════════
if st.session_state.show_db_alimenti:
    st.markdown("<h2 style='color:#2c3e50;font-weight:900;'>🍱 DB Alimenti VLEKT</h2>", unsafe_allow_html=True)

    col_chiudi, col_svuota, _ = st.columns([1, 1, 4])
    with col_chiudi:
        if st.button("🔙 Chiudi DB Alimenti", use_container_width=True):
            chiudi_db()
            st.rerun()
    with col_svuota:
        if 'confirm_svuota_alimenti' not in st.session_state:
            st.session_state.confirm_svuota_alimenti = False
        if st.session_state.confirm_svuota_alimenti:
            if st.button("⚠️ Confermi? Cancella TUTTI", key="btn_si_svuota_ali", use_container_width=True, type="primary"):
                pd.DataFrame(columns=COLS_ALI).to_csv(DB_ALIMENTI, index=False)
                st.session_state.confirm_svuota_alimenti = False
                st.success("✅ Database alimenti svuotato.")
                st.rerun()
            if st.button("❌ Annulla", key="btn_no_svuota_ali", use_container_width=True):
                st.session_state.confirm_svuota_alimenti = False
                st.rerun()
        elif st.button("🗑️ Cancella tutti i prodotti", key="btn_svuota_ali", use_container_width=True, help="Svuota il database per evitare duplicati prima di un nuovo import"):
            st.session_state.confirm_svuota_alimenti = True
            st.rerun()

    st.markdown("---")

    # --- FORM MODIFICA ALIMENTO ---
    if st.session_state.edit_food_idx is not None and st.session_state.edit_food_idx in df_a.index:
        idx_e = st.session_state.edit_food_idx
        r_e = df_a.loc[idx_e]
        st.markdown(f"<div class='card'><h4 class='card-header-blue'>✏️ Modifica Prodotto: {r_e['Alimento']}</h4></div>", unsafe_allow_html=True)
        with st.form("f_edit_food"):
            ne_a = st.text_input("Nome Alimento", r_e['Alimento'])
            c1, c2 = st.columns(2)
            vke_a = c1.text_input("Kcal/unità", r_e['Kcal'])
            vce_a = c2.text_input("Carbo Netti/unità", r_e['Carbo_Netti'])
            c3, c4 = st.columns(2)
            vpe_a = c3.text_input("Proteine/unità", r_e['Prot'])
            vge_a = c4.text_input("Grassi/unità", r_e['Grassi'])
            v_porz_e = st.text_input("Porzioni in 1 Confezione", r_e.get('Porzioni_Confezione', ''))
            cs, ca = st.columns(2)
            if cs.form_submit_button("💾 Salva Modifiche", use_container_width=True, type="primary"):
                df_a.loc[idx_e, ['Alimento','Kcal','Carbo_Netti','Prot','Grassi','Porzioni_Confezione']] = [ne_a, vke_a, vce_a, vpe_a, vge_a, v_porz_e]
                df_a.to_csv(DB_ALIMENTI, index=False)
                st.session_state.edit_food_idx = None
                st.success(f"✅ '{ne_a}' aggiornato!")
                st.rerun()
            if ca.form_submit_button("❌ Annulla", use_container_width=True):
                st.session_state.edit_food_idx = None
                st.rerun()

    else:
        # --- FORM AGGIUNTA ---
        with st.expander("✨ Aggiungi Nuovo Prodotto", expanded=df_a.empty):
            with st.form("add_food_form", clear_on_submit=True):
                n_a = st.text_input("Nome Alimento (es. Barretta Proteica)")
                c1, c2 = st.columns(2)
                vk_a = c1.text_input("Kcal/unità")
                vc_a = c2.text_input("Carbo Netti/unità")
                c3, c4 = st.columns(2)
                vp_a = c3.text_input("Proteine/unità")
                vg_a = c4.text_input("Grassi/unità")
                v_porz = st.text_input("Porzioni in 1 Confezione (es. 5)")
                if st.form_submit_button("💾 Salva nel Database", use_container_width=True, type="primary"):
                    if n_a:
                        pd.concat([df_a, pd.DataFrame([[n_a, vk_a, vc_a, vp_a, vg_a, v_porz]], columns=COLS_ALI)]).to_csv(DB_ALIMENTI, index=False)
                        st.success(f"✅ '{n_a}' aggiunto!")
                        st.rerun()
                    else:
                        st.error("Il nome del prodotto è obbligatorio.")

        # --- IMPORT DA CSV PRESTASHOP (lineadiciotto.it) ---
        with st.expander("📥 Importa da CSV PrestaShop (lineadiciotto.it)"):
            st.caption("Carica un file CSV esportato da PrestaShop (articoli). I valori nutrizionali saranno estratti automaticamente dalle tabelle nelle descrizioni HTML.")
            uploaded = st.file_uploader("Seleziona CSV export articoli", type=["csv"], key="upload_prestashop")
            if uploaded is not None:
                try:
                    # Salva temporaneamente per parse_prestashop_csv
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp:
                        tmp.write(uploaded.getvalue())
                        tmp_path = tmp.name
                    try:
                        prodotti = parse_prestashop_csv(tmp_path)
                    finally:
                        os.unlink(tmp_path)
                    if prodotti:
                        esistenti = set(df_a['Alimento'].str.strip().str.lower())
                        nuovi = [p for p in prodotti if p['Alimento'].strip().lower() not in esistenti]
                        sovrascrivi = st.checkbox("Sovrascrivi prodotti già presenti (aggiorna dati nutrizionali)", value=False, key="sovr_ali")
                        if st.button("💾 Importa nel Database", key="btn_import_prestashop", type="primary"):
                            if sovrascrivi:
                                for p in prodotti:
                                    mask = df_a['Alimento'].astype(str).str.strip().str.lower() == str(p['Alimento']).strip().lower()
                                    if mask.any():
                                        idx = df_a.index[mask][0]
                                        df_a.loc[idx, ['Kcal','Carbo_Netti','Prot','Grassi','Porzioni_Confezione']] = [
                                            p['Kcal'], p['Carbo_Netti'], p['Prot'], p['Grassi'], p['Porzioni_Confezione']]
                                    else:
                                        df_a = pd.concat([df_a, pd.DataFrame([p])], ignore_index=True)
                            else:
                                df_a = pd.concat([df_a, pd.DataFrame(nuovi)], ignore_index=True)
                            df_a = df_a[COLS_ALI]
                            df_a.to_csv(DB_ALIMENTI, index=False)
                            st.success(f"✅ Importati {len(nuovi) if not sovrascrivi else len(prodotti)} prodotti.")
                            st.rerun()
                        st.info(f"Trovati {len(prodotti)} prodotti. {len(nuovi)} nuovi, {len(prodotti)-len(nuovi)} già presenti.")
                    else:
                        st.warning("Nessun prodotto con tabella nutrizionale trovato nel CSV.")
                except Exception as e:
                    st.error(f"Errore durante l'import: {e}")

        # --- LISTA ALIMENTI ---
        if not df_a.empty:
            st.markdown("---")
            n_ali = len(df_a)
            st.markdown(f"<h4 style='color:#1f2937;margin-bottom:12px;'>📋 Prodotti nel Database <span style='font-size:13px;color:#7f8c8d;font-weight:400;'>({n_ali} prodotti)</span></h4>", unsafe_allow_html=True)

            # Intestazione tabella
            ha0, ha1, ha2, ha3, ha4, ha5, ha6, ha7 = st.columns([2.5, 1, 1, 1, 1, 1.2, 0.8, 0.8])
            ha0.markdown("**Prodotto**"); ha1.markdown("**Kcal**"); ha2.markdown("**Carbo**")
            ha3.markdown("**Prot**"); ha4.markdown("**Grassi**"); ha5.markdown("**Pz/Conf**")
            ha6.markdown(""); ha7.markdown("")
            st.markdown("<hr style='margin:4px 0 8px 0;'>", unsafe_allow_html=True)

            df_a_sorted = df_a.sort_values('Alimento').reset_index()
            if 'confirm_del_ali' not in st.session_state: st.session_state.confirm_del_ali = None

            for _, row_a in df_a_sorted.iterrows():
                real_idx_a = row_a['index']
                if st.session_state.confirm_del_ali == real_idx_a:
                    st.warning(f"⚠️ Eliminare **{row_a['Alimento']}**? L'azione è irreversibile.")
                    cda1, cda2 = st.columns(2)
                    if cda1.button("✅ Sì, elimina", key=f"conf_si_ali_{real_idx_a}", use_container_width=True, type="primary"):
                        df_a.drop(real_idx_a).to_csv(DB_ALIMENTI, index=False)
                        st.session_state.confirm_del_ali = None
                        st.rerun()
                    if cda2.button("❌ Annulla", key=f"conf_no_ali_{real_idx_a}", use_container_width=True):
                        st.session_state.confirm_del_ali = None
                        st.rerun()
                else:
                    ra0, ra1, ra2, ra3, ra4, ra5, ra6, ra7 = st.columns([2.5, 1, 1, 1, 1, 1.2, 0.8, 0.8])
                    ra0.markdown(f"**{row_a['Alimento']}**")
                    ra1.caption(str(row_a['Kcal']))
                    ra2.caption(str(row_a['Carbo_Netti']))
                    ra3.caption(str(row_a['Prot']))
                    ra4.caption(str(row_a['Grassi']))
                    ra5.caption(str(row_a.get('Porzioni_Confezione', '—')))
                    if ra6.button("✏️", key=f"mod_ali_{real_idx_a}", help="Modifica", use_container_width=True):
                        st.session_state.edit_food_idx = real_idx_a
                        st.rerun()
                    if ra7.button("🗑️", key=f"del_ali_{real_idx_a}", help="Elimina", use_container_width=True):
                        st.session_state.confirm_del_ali = real_idx_a
                        st.rerun()

    st.markdown("---")
    if st.button("🔙 Chiudi DB Alimenti", key="chiudi_ali_bottom", use_container_width=True, type="primary"):
        chiudi_db()
        st.rerun()

# ══════════════════════════════════════════════════════
# PAGINA DB INTEGRATORI
# ══════════════════════════════════════════════════════
elif st.session_state.show_db_integratori:
    st.markdown("<h2 style='color:#2c3e50;font-weight:900;'>💊 DB Integratori</h2>", unsafe_allow_html=True)

    if st.button("🔙 Chiudi DB Integratori", use_container_width=False):
        chiudi_db()
        st.rerun()

    st.markdown("---")

    # --- FORM MODIFICA INTEGRATORE ---
    if st.session_state.edit_integr_idx is not None and st.session_state.edit_integr_idx in df_i.index:
        idx_ei = st.session_state.edit_integr_idx
        r_ei = df_i.loc[idx_ei]
        st.markdown(f"<div class='card'><h4 class='card-header-blue'>✏️ Modifica: {r_ei['Nome_Integratore']}</h4></div>", unsafe_allow_html=True)
        with st.form("edit_integr_form"):
            ei_nome = st.text_input("Nome Integratore", value=r_ei['Nome_Integratore'])
            ei_cat  = st.text_input("Categoria", value=r_ei['Categoria'])
            ei_desc = st.text_area("Descrizione / Note", value=r_ei['Descrizione'], height=100)
            cs, cc = st.columns(2)
            if cs.form_submit_button("💾 Salva Modifiche", use_container_width=True, type="primary"):
                df_i.loc[idx_ei, ['Nome_Integratore','Categoria','Descrizione']] = [ei_nome, ei_cat, ei_desc]
                df_i.to_csv(DB_INTEGRATORI, index=False)
                st.session_state.edit_integr_idx = None
                st.success(f"✅ '{ei_nome}' aggiornato!")
                st.rerun()
            if cc.form_submit_button("❌ Annulla", use_container_width=True):
                st.session_state.edit_integr_idx = None
                st.rerun()

    else:
        # --- FORM AGGIUNTA ---
        with st.expander("✨ Aggiungi Nuovo Integratore", expanded=df_i.empty):
            with st.form("add_integr_form", clear_on_submit=True):
                ni_nome = st.text_input("Nome Integratore (es. Omega 3)")
                ni_cat  = st.text_input("Categoria (es. Vitamine, Minerali...)")
                ni_desc = st.text_area("Descrizione / Note", height=80)
                if st.form_submit_button("💾 Salva nel Database", use_container_width=True, type="primary"):
                    if ni_nome:
                        pd.concat([df_i, pd.DataFrame([[ni_nome, ni_cat, ni_desc]], columns=COLS_INTEGR)]).to_csv(DB_INTEGRATORI, index=False)
                        st.success(f"✅ '{ni_nome}' aggiunto!")
                        st.rerun()
                    else:
                        st.error("Il nome è obbligatorio.")

        # --- LISTA INTEGRATORI CON NAVIGAZIONE A-Z ---
        if not df_i.empty:
            st.markdown("---")
            n_integr = len(df_i)
            st.markdown(f"<h4 style='color:#1f2937;margin-bottom:8px;'>📋 Integratori nel Database <span style='font-size:13px;color:#7f8c8d;font-weight:400;'>({n_integr} prodotti)</span></h4>", unsafe_allow_html=True)

            df_i_sorted = df_i.sort_values('Nome_Integratore').reset_index()

            # Calcola quali lettere hanno almeno un integratore
            lettere_presenti = sorted(set(
                str(row['Nome_Integratore'])[0].upper()
                for _, row in df_i_sorted.iterrows()
                if str(row['Nome_Integratore']).strip() not in ('', 'nan')
            ))

            # Session state per lettera selezionata
            if 'integr_lettera' not in st.session_state:
                st.session_state.integr_lettera = lettere_presenti[0] if lettere_presenti else 'A'
            # Se la lettera salvata non è più presente, resetta
            if st.session_state.integr_lettera not in lettere_presenti and lettere_presenti:
                st.session_state.integr_lettera = lettere_presenti[0]

            lettera_sel = st.session_state.integr_lettera

            # --- TASTIERA ALFABETICA ---
            st.markdown("<div style='margin-bottom:8px;'>", unsafe_allow_html=True)
            tutte_lettere = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            # Mostra 13 lettere per riga
            for riga_az in range(0, len(tutte_lettere), 13):
                gruppo_az = tutte_lettere[riga_az:riga_az + 13]
                cols_az = st.columns(len(gruppo_az))
                for ci, lettera in enumerate(gruppo_az):
                    ha_integr = lettera in lettere_presenti
                    is_sel_az = (lettera == lettera_sel)
                    if ha_integr:
                        # Lettera attiva: colorata, cliccabile
                        btn_style = "primary" if is_sel_az else "secondary"
                        if cols_az[ci].button(lettera, key=f"az_{lettera}", use_container_width=True, type=btn_style):
                            st.session_state.integr_lettera = lettera
                            st.session_state.confirm_del_integr = None
                            st.rerun()
                    else:
                        # Lettera senza integratori: grigia, disabilitata
                        cols_az[ci].markdown(
                            f"<div style='text-align:center;padding:6px 0;color:#d1d5db;font-size:14px;font-weight:600;'>{lettera}</div>",
                            unsafe_allow_html=True
                        )
            st.markdown("</div>", unsafe_allow_html=True)

            # --- INTEGRATORI DELLA LETTERA SELEZIONATA ---
            df_lettera = df_i_sorted[df_i_sorted['Nome_Integratore'].str.upper().str.startswith(lettera_sel)]
            n_lettera = len(df_lettera)

            st.markdown(f"""
            <div style="background:#eef6ff;border-left:5px solid #3498db;border-radius:6px;
                 padding:8px 16px;margin:8px 0 12px 0;">
                <span style="font-size:22px;font-weight:900;color:#3498db;">{lettera_sel}</span>
                <span style="font-size:13px;color:#6b7280;margin-left:8px;">{n_lettera} integratore/i</span>
            </div>""", unsafe_allow_html=True)

            if df_lettera.empty:
                st.info(f"Nessun integratore con la lettera **{lettera_sel}**.")
            else:
                for _, row_i in df_lettera.iterrows():
                    real_idx = row_i['index']
                    is_confirming = (st.session_state.confirm_del_integr == real_idx)
                    border_color = "#e74c3c" if is_confirming else "#3498db"
                    bg_color = "#fff5f5" if is_confirming else "#ffffff"

                    st.markdown(f"""
                    <div style="background:{bg_color};border:1px solid #e0e6ed;border-left:5px solid {border_color};
                         border-radius:8px;padding:14px 18px;margin-bottom:4px;">
                        <div style="font-size:16px;font-weight:800;color:#2c3e50;margin-bottom:4px;">
                            💊 {row_i['Nome_Integratore']}
                        </div>
                        <div style="font-size:12px;font-weight:600;color:#3498db;margin-bottom:4px;">
                            🏷️ {row_i['Categoria'] if str(row_i['Categoria']).strip() not in ('','nan') else 'Categoria non specificata'}
                        </div>
                        <div style="font-size:12px;color:#6b7280;">
                            📝 {row_i['Descrizione'] if str(row_i['Descrizione']).strip() not in ('','nan') else 'Nessuna descrizione'}
                        </div>
                    </div>""", unsafe_allow_html=True)

                    if is_confirming:
                        st.error(f"⚠️ Eliminare definitivamente **{row_i['Nome_Integratore']}**?")
                        cd1, cd2 = st.columns(2)
                        if cd1.button("✅ Sì, elimina", key=f"conf_si_{real_idx}", use_container_width=True, type="primary"):
                            df_i.drop(real_idx).to_csv(DB_INTEGRATORI, index=False)
                            st.session_state.confirm_del_integr = None
                            st.rerun()
                        if cd2.button("❌ Annulla", key=f"conf_no_{real_idx}", use_container_width=True):
                            st.session_state.confirm_del_integr = None
                            st.rerun()
                    else:
                        cb1, cb2, cb3 = st.columns([4, 1, 1])
                        if cb2.button("✏️ Modifica", key=f"mod_integr_{real_idx}", use_container_width=True):
                            st.session_state.edit_integr_idx = real_idx
                            st.session_state.confirm_del_integr = None
                            st.rerun()
                        if cb3.button("🗑️ Elimina", key=f"del_integr_{real_idx}", use_container_width=True):
                            st.session_state.confirm_del_integr = real_idx
                            st.rerun()
                    st.markdown("<div style='margin-bottom:2px;'></div>", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🔙 Chiudi DB Integratori", key="chiudi_integr_bottom", use_container_width=True, type="primary"):
        chiudi_db()
        st.rerun()

elif st.session_state.show_db_proteine:
    st.markdown("<h2 style='color:#2c3e50;font-weight:900;'>🥩 DB Alimenti Proteici Naturali</h2>", unsafe_allow_html=True)

    if st.button("🔙 Chiudi DB Proteine", use_container_width=False):
        chiudi_db()
        st.rerun()

    st.markdown("---")

    # --- SESSION STATE ---
    if 'edit_prot_idx' not in st.session_state: st.session_state.edit_prot_idx = None
    if 'confirm_del_prot' not in st.session_state: st.session_state.confirm_del_prot = None

    # --- FORM MODIFICA ---
    if st.session_state.edit_prot_idx is not None and st.session_state.edit_prot_idx in df_prot.index:
        idx_ep = st.session_state.edit_prot_idx
        r_ep = df_prot.loc[idx_ep]
        st.markdown(f"<div class='card'><h4 class='card-header-blue'>✏️ Modifica: {r_ep['Nome']}</h4></div>", unsafe_allow_html=True)
        with st.form("edit_prot_form"):
            ep_nome = st.text_input("Nome Alimento", value=r_ep['Nome'])
            ep_cat  = st.text_input("Categoria (es. Carne, Pesce, Uova...)", value=r_ep['Categoria'])
            c1p, c2p, c3p, c4p = st.columns(4)
            ep_g    = c1p.text_input("Grammi Porzione", value=r_ep['Grammi_Porzione'])
            ep_kcal = c2p.text_input("Kcal", value=r_ep['Kcal'])
            ep_prot = c3p.text_input("Prot (g)", value=r_ep['Prot'])
            ep_gras = c4p.text_input("Grassi (g)", value=r_ep['Grassi'])
            ep_carb = st.text_input("Carbo Netti (g)", value=r_ep['Carbo_Netti'])
            ep_note = st.text_area("Note", value=r_ep['Note'], height=70)
            cs, cc = st.columns(2)
            if cs.form_submit_button("💾 Salva Modifiche", use_container_width=True, type="primary"):
                df_prot.loc[idx_ep] = [ep_nome, ep_cat, ep_g, ep_kcal, ep_prot, ep_gras, ep_carb, ep_note]
                df_prot.to_csv(DB_PROTEINE, index=False)
                st.session_state.edit_prot_idx = None
                st.success(f"✅ '{ep_nome}' aggiornato!")
                st.rerun()
            if cc.form_submit_button("❌ Annulla", use_container_width=True):
                st.session_state.edit_prot_idx = None
                st.rerun()
    else:
        # --- FORM AGGIUNTA ---
        with st.expander("✨ Aggiungi Nuovo Alimento Proteico", expanded=df_prot.empty):
            with st.form("add_prot_form", clear_on_submit=True):
                np_nome = st.text_input("Nome Alimento (es. Petto di Pollo)")
                np_cat  = st.text_input("Categoria (es. Carne, Pesce, Uova, Legumi...)")
                c1n, c2n, c3n, c4n = st.columns(4)
                np_g    = c1n.text_input("Grammi Porzione", value="100")
                np_kcal = c2n.text_input("Kcal", value="0")
                np_prot = c3n.text_input("Prot (g)", value="0")
                np_gras = c4n.text_input("Grassi (g)", value="0")
                np_carb = st.text_input("Carbo Netti (g)", value="0")
                np_note = st.text_area("Note (es. cottura consigliata, varianti...)", height=70)
                if st.form_submit_button("💾 Salva nel Database", use_container_width=True, type="primary"):
                    if np_nome:
                        pd.concat([df_prot, pd.DataFrame([[np_nome, np_cat, np_g, np_kcal, np_prot, np_gras, np_carb, np_note]], columns=COLS_PROT)]).to_csv(DB_PROTEINE, index=False)
                        st.success(f"✅ '{np_nome}' aggiunto!")
                        st.rerun()
                    else:
                        st.error("Il nome è obbligatorio.")

        # --- LISTA ---
        if not df_prot.empty:
            st.markdown("---")
            df_prot_sorted = df_prot.sort_values('Nome').reset_index()

            # Filtro per categoria
            categorie = ['Tutte'] + sorted(df_prot['Categoria'].dropna().unique().tolist())
            cat_sel = st.selectbox("🔎 Filtra per Categoria", categorie, key="prot_cat_filter")

            df_prot_vis = df_prot_sorted if cat_sel == 'Tutte' else df_prot_sorted[df_prot_sorted['Categoria'] == cat_sel]

            n_prot = len(df_prot_vis)
            st.markdown(f"<h4 style='color:#1f2937;margin-bottom:8px;'>📋 Alimenti nel Database <span style='font-size:13px;color:#7f8c8d;font-weight:400;'>({n_prot} prodotti)</span></h4>", unsafe_allow_html=True)

            # Intestazione
            hc0, hc1, hc2, hc3, hc4, hc5, hc6, hc7 = st.columns([2.5, 1.5, 0.8, 0.8, 0.8, 0.8, 0.7, 0.7])
            hc0.markdown("**Nome**"); hc1.markdown("**Categoria**"); hc2.markdown("**g/pz**")
            hc3.markdown("**Kcal**"); hc4.markdown("**Prot**"); hc5.markdown("**Grassi**"); hc6.markdown(""); hc7.markdown("")
            st.markdown("<hr style='margin:4px 0 8px 0;'>", unsafe_allow_html=True)

            for _, row_p in df_prot_vis.iterrows():
                real_idx_p = row_p['index']
                if st.session_state.confirm_del_prot == real_idx_p:
                    st.warning(f"⚠️ Eliminare **{row_p['Nome']}**? L'azione è irreversibile.")
                    cdp1, cdp2 = st.columns(2)
                    if cdp1.button("✅ Sì, elimina", key=f"conf_si_prot_{real_idx_p}", use_container_width=True, type="primary"):
                        df_prot.drop(real_idx_p).to_csv(DB_PROTEINE, index=False)
                        st.session_state.confirm_del_prot = None
                        st.rerun()
                    if cdp2.button("❌ Annulla", key=f"conf_no_prot_{real_idx_p}", use_container_width=True):
                        st.session_state.confirm_del_prot = None
                        st.rerun()
                else:
                    pc0, pc1, pc2, pc3, pc4, pc5, pc6, pc7 = st.columns([2.5, 1.5, 0.8, 0.8, 0.8, 0.8, 0.7, 0.7])
                    pc0.markdown(f"**{row_p['Nome']}**")
                    pc1.caption(str(row_p['Categoria']))
                    pc2.caption(str(row_p['Grammi_Porzione']))
                    pc3.caption(str(row_p['Kcal']))
                    pc4.caption(str(row_p['Prot']))
                    pc5.caption(str(row_p['Grassi']))
                    if pc6.button("✏️", key=f"mod_prot_{real_idx_p}", use_container_width=True):
                        st.session_state.edit_prot_idx = real_idx_p
                        st.rerun()
                    if pc7.button("🗑️", key=f"del_prot_{real_idx_p}", use_container_width=True):
                        st.session_state.confirm_del_prot = real_idx_p
                        st.rerun()
        else:
            st.info("🥩 Nessun alimento proteico nel database. Aggiungine uno con il form sopra.")

    st.markdown("---")
    if st.button("🔙 Chiudi DB Proteine", key="chiudi_prot_bottom", use_container_width=True, type="primary"):
        chiudi_db()
        st.rerun()


elif p_r is not None:
    _nome_paz = f"{p_r.get('Cognome', '')} {p_r.get('Nome', '')}".strip()
    st.markdown(f"<div class='vlekt-patient-name-bar'>👤 {_nome_paz}</div>", unsafe_allow_html=True)

    tab_labels = ["📋 Cruscotto Visite", "🥑 Piani Alimentari VLEKT", "💊 Integratori & Prescrizioni"]
    if st.session_state.get('switch_to_prescrizioni'):
        st.session_state.paziente_tab_radio = tab_labels[2]
        st.session_state.switch_to_prescrizioni = False
    paziente_tab = st.radio("", tab_labels, horizontal=True, key="paziente_tab_radio", label_visibility="collapsed")

    cf_attivo = str(p_r.get('Codice_Fiscale','')).strip()
    st_p = df_p[df_p['Codice_Fiscale'].fillna('').astype(str).str.strip() == cf_attivo].copy()
    date_visite_disponibili = []
    if not st_p.empty:
        st_p_ord = st_p.copy()
        st_p_ord['DT_sort'] = pd.to_datetime(st_p_ord['Data_Visita'], format='%d/%m/%Y', errors='coerce')
        st_p_ord = st_p_ord.sort_values('DT_sort', ascending=True)
        date_visite_disponibili = st_p_ord['Data_Visita'].tolist()

    if paziente_tab == tab_labels[0]:
        if not st_p.empty:

            # Visita selezionata (default: ultima)
            indici_visite = list(st_p_ord.index[::-1])
            if st.session_state.visita_idx_sel not in indici_visite:
                st.session_state.visita_idx_sel = indici_visite[0]
            idx_sel = st.session_state.visita_idx_sel
            rv_sel  = st_p_ord.loc[idx_sel]

            # ── CARD DATI GENERALI + INFO VISITE (stile Nutriverso) ──
            eta_anni, eta_mesi = calcola_eta_anni_mesi(p_r.get('Data_Nascita', '01/01/1990'))
            sesso_label = "Femmina" if str(p_r.get('Sesso', '')).strip().upper() == 'F' else "Maschio"
            ultima_visita_str, giorni_da_ultima, n_visite_tot, intervallo_medio = calcola_info_visite(st_p_ord)

            col_dati_gen, col_info_vis = st.columns(2)
            with col_dati_gen:
                st.markdown("""
                <div class="card" style="margin-bottom: 16px;">
                    <h4 class="card-header-blue">Dati generali</h4>
                    <div class="card-text">Sesso: """ + sesso_label + """</div>
                    <div class="card-text">Età: """ + f"{eta_anni} anni e {eta_mesi} mesi" + """</div>
                </div>""", unsafe_allow_html=True)
                if st.button("Modifica anagrafica paziente", key="btn_mod_anag_card", use_container_width=True):
                    st.session_state.edit_anagrafica = True
                    st.rerun()
            with col_info_vis:
                st.markdown(f"""
                <div class="card" style="margin-bottom: 16px;">
                    <h4 class="card-header-green">Info visite</h4>
                    <div class="card-text">Ultima visita: <b>{ultima_visita_str}</b></div>
                    <div class="card-text">Giorni dall'ultima visita: <b>{giorni_da_ultima} giorni</b></div>
                    <div class="card-text">Numero visite totali: <b>{n_visite_tot}</b></div>
                    <div class="card-text">Intervallo medio visite: <b>{intervallo_medio} giorni</b></div>
                </div>""", unsafe_allow_html=True)

            # ── LAYOUT: colonna sinistra = lista visite | destra = dettaglio/form ──
            col_lista, col_det = st.columns([1, 2.4])

            with col_lista:
                st.markdown("<div style='font-size:12px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px;'>Storico visite</div>", unsafe_allow_html=True)

                # Raggruppa visite per mese (più recente prima)
                mesi_it = ['','Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
                           'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']
                
                from collections import OrderedDict
                gruppi = OrderedDict()
                for i, rv in st_p_ord.iloc[::-1].iterrows():
                    try:
                        parts = rv['Data_Visita'].split('/')
                        mese_num = int(parts[1]); anno = parts[2]
                        chiave = f"{anno}-{mese_num:02d}"
                        label_mese = f"{mesi_it[mese_num]} {anno}"
                    except:
                        chiave = 'altro'; label_mese = 'Altro'
                    if chiave not in gruppi:
                        gruppi[chiave] = {'label': label_mese, 'visite': []}
                    gruppi[chiave]['visite'].append((i, rv))

                # Mese selezionato = quello che contiene la visita attiva
                mese_visita_sel = None
                for chiave, g in gruppi.items():
                    if any(i == idx_sel for i, _ in g['visite']):
                        mese_visita_sel = chiave
                        break

                for chiave, g in gruppi.items():
                    is_mese_attivo = (chiave == mese_visita_sel)
                    n = len(g['visite'])
                    with st.expander(f"📅 {g['label']}  ({n})", expanded=is_mese_attivo):
                        for i, rv in g['visite']:
                            is_sel = (i == idx_sel)
                            bmi_v = to_f(rv['BMI'])
                            _, bmi_c = calcola_stato_bmi(bmi_v) if bmi_v > 0 else ('', '#9ca3af')

                            if is_sel:
                                st.markdown(f"""
                                <div style="background:#eef6ff;border:2px solid #3b82f6;border-radius:8px;
                                     padding:10px 13px;margin-bottom:4px;">
                                    <div style="font-size:13px;font-weight:800;color:#1d4ed8;">📌 {rv['Data_Visita']}</div>
                                    <div style="display:flex;gap:10px;margin-top:3px;">
                                        <span style="font-size:11px;color:#6b7280;">⚖️ {rv['Peso']} kg</span>
                                        <span style="font-size:11px;font-weight:700;color:{bmi_c};">BMI {rv['BMI']}</span>
                                    </div>
                                </div>""", unsafe_allow_html=True)
                            else:
                                label = f"**{rv['Data_Visita']}**\n⚖️ {rv['Peso']} kg  •  BMI {rv['BMI']}"
                                if st.button(label, key=f"sel_visita_{i}", use_container_width=True):
                                    st.session_state.visita_idx_sel = i
                                    st.session_state.m_modulo = False
                                    st.session_state.idx_mod = None
                                    st.rerun()

                st.markdown("<hr style='margin:12px 0;border-color:#e5e7eb;'>", unsafe_allow_html=True)
                if not st.session_state.m_modulo:
                    if st.button("➕ Nuova Visita", use_container_width=True, type="primary"):
                        st.session_state.m_modulo = True
                        st.session_state.idx_mod = None
                        st.rerun()
                else:
                    st.markdown("<div style='background:#dbeafe;border-radius:6px;padding:8px 10px;font-size:12px;color:#1d4ed8;font-weight:600;text-align:center;'>✏️ Form visita aperto →</div>", unsafe_allow_html=True)

            with col_det:
                # ── FORM NUOVA/MODIFICA VISITA (ha priorità visiva) ──
                if st.session_state.m_modulo or idx_mod is not None:
                    titolo_v = "📝 Modifica Visita" if idx_mod is not None else "➕ Nuova Visita"
                    st.markdown(f"""<div style="background:#eff6ff;border:2px solid #3b82f6;border-radius:10px;
                        padding:16px 20px;margin-bottom:16px;">
                        <div style="font-size:15px;font-weight:800;color:#1d4ed8;">{titolo_v}</div>
                    </div>""", unsafe_allow_html=True)

                    # Per nuova visita: usa solo i dati stabili (altezza, LAF, peso target)
                    # Per modifica: usa tutti i dati della visita selezionata
                    is_nuova_visita = (idx_mod is None)
                    df_base = d_form  # dati da usare come base

                    with st.form(f"form_visita_{idx_mod}"):
                        cvg, cvm, cva = st.columns(3)
                        g_l = [str(i).zfill(2) for i in range(1, 32)]; m_l = [str(i).zfill(2) for i in range(1, 13)]; a_l = [str(i) for i in range(2020, 2051)]
                        dv_g, dv_m, dv_a = str(date.today().day).zfill(2), str(date.today().month).zfill(2), str(date.today().year)
                        if idx_mod is not None:
                            try: p_dv = d_form['Data_Visita'].split('/'); dv_g, dv_m, dv_a = p_dv[0], p_dv[1], p_dv[2]
                            except: pass
                        s_dg = cvg.selectbox("Giorno", g_l, index=g_l.index(dv_g) if dv_g in g_l else 0)
                        s_dm = cvm.selectbox("Mese", m_l, index=m_l.index(dv_m) if dv_m in m_l else 0)
                        s_da = cva.selectbox("Anno", a_l, index=a_l.index(dv_a) if dv_a in a_l else 0)
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            # Altezza: sempre pre-popolata (dato stabile)
                            altezza_v = st.number_input("Altezza (cm)", value=int(to_f(df_base['Altezza'])) if df_base is not None and str(df_base['Altezza'])!="" else 170)
                            # Peso: pre-popolato solo in modifica, vuoto (0) in nuova visita
                            peso_default = to_f(df_base['Peso']) if (not is_nuova_visita and df_base is not None and str(df_base['Peso'])!="") else 0.0
                            peso_v = st.number_input("Peso (kg)", value=peso_default)

                        with c2:
                            sugg_target = round(22.5 * ((altezza_v/100)**2), 1) if altezza_v > 0 else 70.0
                            # Peso target e LAF: sempre pre-popolati (obiettivi stabili)
                            val_pt = to_f(df_base.get('Peso_Target')) if df_base is not None and str(df_base.get('Peso_Target')) != 'nan' and str(df_base.get('Peso_Target')) != "" else sugg_target
                            s_pt = st.number_input("Peso Obiettivo / Target (kg)", value=float(val_pt))
                            val_laf = str(df_base.get('LAF', lista_laf[0])) if df_base is not None and str(df_base.get('LAF')) != 'nan' and str(df_base.get('LAF')) != "" else lista_laf[0]
                            idx_laf = lista_laf.index(val_laf) if val_laf in lista_laf else 0
                            s_laf = st.selectbox("Livello Attività Fisica (LAF)", lista_laf, index=idx_laf)

                        # Antropometria: pre-popolata solo in modifica, azzerata in nuova visita
                        antro_v = form_antropometria("mv", None if is_nuova_visita else df_base)

                        # Ricava i campi legacy dall'antropometria dettagliata
                        addome_v  = antro_v.get('Circ_Addome_Ant', 0.0)
                        fianchi_v = antro_v.get('Circ_Fianchi_Ant', 0.0)
                        torace_v  = antro_v.get('Circ_Torace_Ant', 0.0)
                        polso_v   = antro_v.get('Circ_Polso_Dx', 0.0)

                        # Analisi, farmaci, note: pre-popolati solo in modifica
                        analisi_v = st.text_area("Analisi Cliniche", value=str(df_base['Analisi_Cliniche']) if (not is_nuova_visita and df_base is not None and str(df_base['Analisi_Cliniche']) not in ('', 'nan')) else "")
                        farmaci_v = st.text_area("Farmaci Assunti",  value=str(df_base['Farmaci'])         if (not is_nuova_visita and df_base is not None and str(df_base['Farmaci'])         not in ('', 'nan')) else "")
                        note_v    = st.text_area("Note Visita",      value=str(df_base['Note'])            if (not is_nuova_visita and df_base is not None and str(df_base['Note'])            not in ('', 'nan')) else "")

                        col_sv, col_ann = st.columns(2)
                        salva_btn = col_sv.form_submit_button("💾 SALVA VISITA", type="primary", use_container_width=True)
                        annulla_btn = col_ann.form_submit_button("🚪 ANNULLA", use_container_width=True)

                        if annulla_btn:
                            st.session_state.m_modulo = False
                            st.session_state.idx_mod = None
                            st.rerun()
                        
                        if salva_btn:
                            bmi_v = round(peso_v / ((altezza_v/100)**2), 2) if altezza_v > 0 else 0.0
                            riga = [
                                f"{s_dg}/{s_dm}/{s_da}", p_r['Nome'], p_r['Cognome'], p_r['Codice_Fiscale'], p_r['Data_Nascita'], 
                                p_r['Luogo_Nascita'], p_r.get('Indirizzo',''), p_r['Sesso'], p_r.get('Cellulare',''), p_r.get('Email',''), altezza_v, peso_v, bmi_v, 
                                addome_v, fianchi_v, torace_v, polso_v, analisi_v, farmaci_v, note_v, s_laf, s_pt,
                                # Circonferenze
                                antro_v.get('Circ_Polso_Dx', 0.0), antro_v.get('Circ_Polso_Sx', 0.0),
                                antro_v.get('Circ_Avambraccio_Dx', 0.0), antro_v.get('Circ_Avambraccio_Sx', 0.0),
                                antro_v.get('Circ_Braccio_Dx', 0.0), antro_v.get('Circ_Braccio_Sx', 0.0),
                                antro_v.get('Circ_Spalle', 0.0), antro_v.get('Circ_Torace_Ant', 0.0),
                                antro_v.get('Circ_Vita', 0.0), antro_v.get('Circ_Addome_Ant', 0.0),
                                antro_v.get('Circ_Fianchi_Ant', 0.0),
                                antro_v.get('Circ_Coscia_Prox_Dx', 0.0), antro_v.get('Circ_Coscia_Prox_Sx', 0.0),
                                antro_v.get('Circ_Coscia_Med_Dx', 0.0), antro_v.get('Circ_Coscia_Med_Sx', 0.0),
                                antro_v.get('Circ_Coscia_Dist_Dx', 0.0), antro_v.get('Circ_Coscia_Dist_Sx', 0.0),
                                antro_v.get('Circ_Polpaccio_Dx', 0.0), antro_v.get('Circ_Polpaccio_Sx', 0.0),
                                antro_v.get('Circ_Caviglia_Dx', 0.0), antro_v.get('Circ_Caviglia_Sx', 0.0),
                                # Pliche
                                antro_v.get('Plica_Avambraccio', 0.0), antro_v.get('Plica_Bicipitale', 0.0),
                                antro_v.get('Plica_Tricipitale', 0.0), antro_v.get('Plica_Ascellare', 0.0),
                                antro_v.get('Plica_Pettorale', 0.0), antro_v.get('Plica_Sottoscapolare', 0.0),
                                antro_v.get('Plica_Addominale', 0.0), antro_v.get('Plica_Soprailiaca', 0.0),
                                antro_v.get('Plica_Coscia_Med', 0.0), antro_v.get('Plica_Soprapatellare', 0.0),
                                antro_v.get('Plica_Polpaccio_Med', 0.0), antro_v.get('Plica_Sopraspinale', 0.0),
                                # Diametri ossei
                                antro_v.get('Diam_Polso', 0.0), antro_v.get('Diam_Gomito', 0.0),
                                antro_v.get('Diam_Biacromiale', 0.0), antro_v.get('Diam_Toracico', 0.0),
                                antro_v.get('Diam_Bicrestale', 0.0), antro_v.get('Diam_Addominale_Sag', 0.0),
                                antro_v.get('Diam_Bitrocanterio', 0.0), antro_v.get('Diam_Ginocchio', 0.0),
                                antro_v.get('Diam_Caviglia', 0.0),
                                # Note antropometria
                                antro_v.get('Note_Antropometria', ""),
                            ]
                            
                            if idx_mod is not None:
                                df_p.iloc[idx_mod] = riga
                                st.session_state.idx_mod = None
                                st.session_state.m_modulo = False
                            else: 
                                df_p = pd.concat([df_p, pd.DataFrame([riga], columns=COLS_PAZ)], ignore_index=True)
                                new_idx = df_p.index[-1]
                                st.session_state.visita_idx_sel = new_idx
                                st.session_state.m_modulo = False
                                st.session_state.idx_mod = None
                                
                            df_p.to_csv(DB_PAZIENTI, index=False)
                            st.rerun()

                else:
                    # ── DETTAGLIO VISITA SELEZIONATA ──
                    stato_t_s, stato_c_s = calcola_stato_bmi(to_f(rv_sel['BMI']))
                    peso_u    = to_f(rv_sel['Peso'])
                    altezza_u = to_f(rv_sel['Altezza'])
                    bmi_u     = to_f(rv_sel['BMI'])
                    eta   = calcola_eta(p_r['Data_Nascita'])
                    bmr   = calcola_bmr(peso_u, altezza_u, eta, p_r['Sesso'])
                    laf_str = str(rv_sel.get('LAF', lista_laf[0]))
                    laf_num = float(laf_str.split(' - ')[0]) if laf_str and laf_str not in ('', 'nan') else 1.2
                    tdee  = bmr * laf_num

                    st.markdown(f"""
                    <div class="card" style="margin-bottom: 16px;">
                        <h4 class="card-header-blue">Parametri principali della visita del {rv_sel['Data_Visita']}</h4>
                        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:12px;">
                            <div style="background:#f8fafc;border-radius:8px;padding:10px 12px;border:1px solid #e5e7eb;">
                                <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">Peso</div>
                                <div style="font-size:20px;font-weight:800;color:#111827;">{peso_u} <span style="font-size:12px;font-weight:400;">kg</span></div>
                            </div>
                            <div style="background:#f8fafc;border-radius:8px;padding:10px 12px;border:1px solid #e5e7eb;">
                                <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">BMI</div>
                                <div style="font-size:20px;font-weight:800;color:{stato_c_s};">{bmi_u}</div>
                                <div style="font-size:11px;color:{stato_c_s};">{stato_t_s}</div>
                            </div>
                            <div style="background:#f8fafc;border-radius:8px;padding:10px 12px;border:1px solid #e5e7eb;">
                                <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">Altezza</div>
                                <div style="font-size:20px;font-weight:800;color:#111827;">{altezza_u} <span style="font-size:12px;font-weight:400;">cm</span></div>
                            </div>
                        </div>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">
                            <div style="background:#fff8f0;border-radius:8px;padding:8px 12px;border:1px solid #fed7aa;">
                                <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">BMR</div>
                                <div style="font-size:15px;font-weight:700;color:#ea580c;">{int(bmr)} <span style="font-size:11px;font-weight:400;">kcal</span></div>
                            </div>
                            <div style="background:#f0fdf4;border-radius:8px;padding:8px 12px;border:1px solid #bbf7d0;">
                                <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">TDEE</div>
                                <div style="font-size:15px;font-weight:700;color:#16a34a;">{int(tdee)} <span style="font-size:11px;font-weight:400;">kcal</span></div>
                            </div>
                        </div>
                        <div style="display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:#6b7280;border-top:1px solid #f1f5f9;padding-top:10px;">
                            <span>Addome: <b>{rv_sel['Addome']} cm</b></span>
                            <span>Fianchi: <b>{rv_sel['Fianchi']} cm</b></span>
                            <span>Torace: <b>{rv_sel['Torace']} cm</b></span>
                            <span>Polso: <b>{rv_sel['Polso']} cm</b></span>
                            <span>LAF: <b>{laf_str.split(' - ')[0] if ' - ' in laf_str else laf_str}</b></span>
                        </div>
                    </div>""", unsafe_allow_html=True)

                    # ── CARD VARIAZIONI PESO (se almeno 2 visite) ──
                    if len(st_p_ord) >= 2:
                        peso_prima = to_f(st_p_ord.iloc[0]['Peso'])
                        peso_ultima = to_f(st_p_ord.iloc[-1]['Peso'])
                        try:
                            pos_cur = st_p_ord.index.tolist().index(idx_sel)
                            peso_visita_prec = to_f(st_p_ord.iloc[pos_cur - 1]['Peso']) if pos_cur > 0 else peso_u
                        except (ValueError, KeyError):
                            peso_visita_prec = peso_u
                        delta_tot_kg = round(peso_ultima - peso_prima, 1)
                        delta_tot_pct = round((delta_tot_kg / peso_prima * 100), 1) if peso_prima > 0 else 0
                        delta_prec_kg = round(peso_u - peso_visita_prec, 1)
                        delta_prec_pct = round((delta_prec_kg / peso_visita_prec * 100), 1) if peso_visita_prec > 0 else 0
                        try:
                            data_prima = st_p_ord.iloc[0]['Data_Visita'].split('/')
                            data_ultima = st_p_ord.iloc[-1]['Data_Visita'].split('/')
                            d1 = date(int(data_prima[2]), int(data_prima[1]), int(data_prima[0]))
                            d2 = date(int(data_ultima[2]), int(data_ultima[1]), int(data_ultima[0]))
                            mesi_tot = max(1, (d2 - d1).days / 30.0)
                            media_mensile_kg = round((peso_ultima - peso_prima) / mesi_tot, 1)
                            media_mensile_pct = round(delta_tot_pct / mesi_tot, 1) if mesi_tot else 0
                        except Exception:
                            media_mensile_kg = 0
                            media_mensile_pct = 0
                        col_neg = "#16a34a" if delta_tot_kg <= 0 else "#dc2626"
                        st.markdown(f"""
                        <div class="card" style="margin-bottom: 16px;">
                            <h4 class="card-header-green">Variazioni peso</h4>
                            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;">
                                <div><span style="color:#64748b;">Totale:</span> <b style="color:{col_neg};">{delta_tot_kg:+.1f} kg</b> ({delta_tot_pct:+.1f}%)</div>
                                <div><span style="color:#64748b;">Dalla visita precedente:</span> <b style="color:{col_neg};">{delta_prec_kg:+.1f} kg</b> ({delta_prec_pct:+.1f}%)</div>
                                <div><span style="color:#64748b;">Media mensile:</span> <b>{media_mensile_kg:+.1f} kg</b> ({media_mensile_pct:+.1f}%)</div>
                            </div>
                        </div>""", unsafe_allow_html=True)

                    # Note/Farmaci/Analisi
                    analisi_val = str(rv_sel.get('Analisi_Cliniche', '')).strip()
                    farmaci_val = str(rv_sel.get('Farmaci', '')).strip()
                    note_val    = str(rv_sel.get('Note', '')).strip()
                    extra_html  = ''
                    if analisi_val and analisi_val != 'nan':
                        extra_html += f'<div style="margin-bottom:6px;font-size:12px;color:#6b7280;"><b>🔬 Analisi:</b> {analisi_val}</div>'
                    if farmaci_val and farmaci_val != 'nan':
                        extra_html += f'<div style="margin-bottom:6px;font-size:12px;color:#6b7280;"><b>💊 Farmaci:</b> {farmaci_val}</div>'
                    if note_val and note_val != 'nan':
                        extra_html += f'<div style="margin-bottom:6px;font-size:12px;color:#6b7280;"><b>📝 Note:</b> {note_val}</div>'
                    if extra_html:
                        st.markdown(f'<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 14px;margin-bottom:12px;">{extra_html}</div>', unsafe_allow_html=True)

                    # ── GRAFICO BMI ──
                    h_m = altezza_u / 100
                    peso_target_str = str(rv_sel.get('Peso_Target', ''))
                    peso_target = to_f(peso_target_str) if peso_target_str and peso_target_str != 'nan' else round(22.5*(h_m**2), 1)
                    if h_m > 0:
                        min_w = 30.0; max_w = max(160.0, peso_u + 20.0); range_w = max(max_w - min_w, 1.0)
                        t1=18.5*(h_m**2); t2=25.0*(h_m**2); t3=30.0*(h_m**2); t4=35.0*(h_m**2); t5=40.0*(h_m**2)
                        p1=max(0,(t1-min_w)/range_w*100); p2=max(0,(t2-t1)/range_w*100); p3=max(0,(t3-t2)/range_w*100)
                        p4=max(0,(t4-t3)/range_w*100); p5=max(0,(t5-t4)/range_w*100); p6=max(0,(max_w-t5)/range_w*100)
                        pa=max(0,min(100,(peso_u-min_w)/range_w*100)); pt=max(0,min(100,(peso_target-min_w)/range_w*100))
                        delta_kg = round(peso_u - peso_target, 1)
                        delta_label = f"Da perdere: <b>{delta_kg} kg</b>" if delta_kg > 0 else f"Da guadagnare: <b>{abs(delta_kg)} kg</b>"
                        delta_color = "#e74c3c" if delta_kg > 0 else "#2ecc71"
                        st.markdown(f"""<div class='card' style='margin:0 0 14px 0;'><div class='card-header'>Obiettivo ponderale e Range BMI</div>
                        <div style='display:flex;justify-content:space-between;font-size:13px;color:#4b5563;margin-bottom:5px;'>
                        <span>Target: <b>{peso_target} kg</b> | <span style='color:{delta_color};'>{delta_label}</span></span>
                        <span>Range normale: <b>{round(t1,1)} – {round(t2,1)} kg</b></span></div>
                        <div style='position:relative;height:40px;width:100%;border-radius:6px;display:flex;overflow:hidden;margin-top:35px;margin-bottom:25px;'>
                        <div style='width:{p1}%;background:#3498db;'></div><div style='width:{p2}%;background:#2ecc71;'></div>
                        <div style='width:{p3}%;background:#f1c40f;'></div><div style='width:{p4}%;background:#e67e22;'></div>
                        <div style='width:{p5}%;background:#e74c3c;'></div><div style='width:{p6}%;background:#8e44ad;'></div>
                        <div style='position:absolute;left:{pt}%;top:-5px;bottom:-5px;width:2px;background:#2c3e50;z-index:10;'></div>
                        <div style='position:absolute;left:calc({pt}% - 7px);top:-14px;width:14px;height:14px;background:#fff;border:3px solid #2c3e50;border-radius:50%;z-index:10;'></div>
                        <div style='position:absolute;left:calc({pt}% - 22px);top:-35px;font-size:10px;font-weight:bold;background:#f3f4f6;color:#374151;padding:2px 6px;border-radius:4px;border:1px solid #d1d5db;'>Target</div>
                        <div style='position:absolute;left:{pa}%;top:-5px;bottom:-5px;width:2px;background:#111827;z-index:10;'></div>
                        <div style='position:absolute;left:calc({pa}% - 7px);top:-14px;width:14px;height:14px;background:#111827;border-radius:50%;z-index:10;border:2px solid white;'></div>
                        <div style='position:absolute;left:calc({pa}% - 30px);top:-35px;font-size:11px;font-weight:bold;background:#111827;color:white;padding:3px 8px;border-radius:4px;'>Attuale: {peso_u} kg</div>
                        </div>
                        <div style='display:flex;justify-content:center;gap:12px;font-size:11px;color:#6b7280;flex-wrap:wrap;'>
                        <span><div style='width:12px;height:12px;background:#3498db;border-radius:2px;display:inline-block;'></div> Sottopeso</span>
                        <span><div style='width:12px;height:12px;background:#2ecc71;border-radius:2px;display:inline-block;'></div> Normopeso</span>
                        <span><div style='width:12px;height:12px;background:#f1c40f;border-radius:2px;display:inline-block;'></div> Sovrappeso</span>
                        <span><div style='width:12px;height:12px;background:#e67e22;border-radius:2px;display:inline-block;'></div> Ob. Lieve</span>
                        <span><div style='width:12px;height:12px;background:#e74c3c;border-radius:2px;display:inline-block;'></div> Ob. Mod.</span>
                        <span><div style='width:12px;height:12px;background:#8e44ad;border-radius:2px;display:inline-block;'></div> Ob. Grave</span>
                        </div></div>""", unsafe_allow_html=True)

                    # ── TASTI OPERATIVI ──
                    ba, bb, bc, bc2, bd, be = st.columns(6)
                    if ba.button("✏️ Modifica", use_container_width=True, type="primary"):
                        st.session_state.idx_mod = idx_sel; st.rerun()
                    if bb.button("🗑️ Elimina", use_container_width=True, type="primary"):
                        if len(st_p_ord) <= 1:
                            st.error("⚠️ Unica visita: usa 'Elimina Paziente'.")
                        else:
                            st.session_state.confirm_del_visita = True; st.rerun()
                    if bc.button("👤 Anagrafica", use_container_width=True, type="primary"):
                        st.session_state.edit_anagrafica = True; st.rerun()
                    if bc2.button("💊 Prescrizione", use_container_width=True, type="primary"):
                        st.session_state.switch_to_prescrizioni = True
                        st.rerun()
                    pdf_privacy = genera_pdf_privacy(p_r)
                    bd.download_button("🖨️ Privacy", pdf_privacy, f"Privacy_{p_r['Cognome']}.pdf", "application/pdf", use_container_width=True, type="primary")
                    pdf_overview = genera_pdf_overview(p_r, st_p_ord)
                    be.download_button("📊 Riepilogo", pdf_overview, f"Riepilogo_{p_r['Cognome']}.pdf", "application/pdf", use_container_width=True, type="primary")

                    # ── REPORT VISITA DA CONSEGNARE AL PAZIENTE ──
                    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
                    pdf_visita = genera_pdf_visita_paziente(p_r, rv_sel, st_p_ord)
                    data_fn = str(rv_sel['Data_Visita']).replace('/', '-')
                    rp1, rp2 = st.columns(2)
                    with rp1:
                        st.download_button(
                            label="📋 Scarica Report Visita",
                            data=pdf_visita,
                            file_name=f"Report_{p_r['Cognome']}_{p_r['Nome']}_{data_fn}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            type="primary",
                            key="dl_report_visita"
                        )
                    with rp2:
                        st.components.v1.html(_html_btn_stampa(pdf_visita, "🖨️ Stampa Report"), height=40)

                    if st.session_state.confirm_del_visita:
                        st.warning(f"⚠️ Sei sicuro di voler eliminare la visita del **{rv_sel['Data_Visita']}**?")
                        cv1, cv2 = st.columns(2)
                        if cv1.button("✅ Sì, elimina visita", key="conf_si_visita", use_container_width=True, type="primary"):
                            cf_vis = str(p_r['Codice_Fiscale']).strip()
                            data_vis = str(rv_sel['Data_Visita']).strip()
                            df_p.drop(idx_sel).to_csv(DB_PAZIENTI, index=False)
                            # Cascade: rimuovi diete e prescrizioni associate a questa visita
                            mask_d = (df_d['Codice_Fiscale'].astype(str).str.strip() == cf_vis) & (df_d['Data_Visita'].astype(str).str.strip() == data_vis)
                            mask_pr = (df_pr['Codice_Fiscale'].astype(str).str.strip() == cf_vis) & (df_pr['Data_Visita'].astype(str).str.strip() == data_vis)
                            if mask_d.any():
                                df_d[~mask_d].to_csv(DB_DIETE, index=False)
                            if mask_pr.any():
                                df_pr[~mask_pr].to_csv(DB_PRESCRIZIONI, index=False)
                            st.session_state.confirm_del_visita = False
                            st.session_state.visita_idx_sel = None
                            st.rerun()
                        if cv2.button("❌ Annulla", key="conf_no_visita", use_container_width=True):
                            st.session_state.confirm_del_visita = False; st.rerun()

                    st.markdown("<br>", unsafe_allow_html=True)
                    # ── ELIMINA PAZIENTE ──
                    if not st.session_state.confirm_delete_paz:
                        if st.button("🗑️ Elimina Paziente", use_container_width=True):
                            st.session_state.confirm_delete_paz = True; st.rerun()
                    else:
                        st.error(f"⚠️ Stai per eliminare **{p_r['Nome']} {p_r['Cognome']}** e tutte le sue visite. Azione irreversibile.")
                        cd1, cd2 = st.columns(2)
                        if cd1.button("✅ SÌ, ELIMINA DEFINITIVAMENTE", use_container_width=True, type="primary"):
                            cf_paz = p_r['Codice_Fiscale']
                            df_p[df_p['Codice_Fiscale'] != cf_paz].to_csv(DB_PAZIENTI, index=False)
                            df_d[df_d['Codice_Fiscale'] != cf_paz].to_csv(DB_DIETE, index=False)
                            df_pr[df_pr['Codice_Fiscale'] != cf_paz].to_csv(DB_PRESCRIZIONI, index=False)
                            st.session_state.p_attivo = None; st.session_state.idx_mod = None
                            st.session_state.m_modulo = False; st.session_state.confirm_delete_paz = False
                            st.session_state.visita_idx_sel = None; st.rerun()
                        if cd2.button("❌ Annulla elimina paz.", use_container_width=True):
                            st.session_state.confirm_delete_paz = False; st.rerun()

        else:
            st.info("Nessuna visita registrata. Clicca su 'Nuova Visita'.")
            if st.button("➕ REGISTRA PRIMA VISITA", type="primary"):
                st.session_state.m_modulo = True; st.rerun()

        # ── MODIFICA ANAGRAFICA ──
        if st.session_state.edit_anagrafica:
            st.markdown("<div class='card'><h4 class='card-header'>🛠️ Modifica Dati Anagrafici</h4></div>", unsafe_allow_html=True)
            with st.form("form_anagrafica"):
                ca1, ca2 = st.columns(2)
                with ca1:
                    e_nome = st.text_input("Nome", p_r['Nome'])
                    e_cognome = st.text_input("Cognome", p_r['Cognome'])
                    e_cf = st.text_input("Codice Fiscale", p_r['Codice_Fiscale']).upper()
                    e_sesso = st.selectbox("Sesso", ["M", "F"], index=0 if str(p_r.get('Sesso', '')).strip().upper() == 'M' else 1)
                    e_indirizzo = st.text_input("Indirizzo di Residenza", p_r.get('Indirizzo', ''))
                with ca2:
                    e_cell = st.text_input("Cellulare", p_r.get('Cellulare', ''))
                    e_email = st.text_input("Email", p_r.get('Email', ''))
                    e_nascita = st.text_input("Data di Nascita (GG/MM/AAAA)", p_r['Data_Nascita'])
                    e_luogo = st.text_input("Comune di Nascita", p_r['Luogo_Nascita'])
                
                cs_a, cc_a = st.columns(2)
                if cs_a.form_submit_button("💾 Salva Modifiche", use_container_width=True):
                    mask = df_p['Codice_Fiscale'] == p_r['Codice_Fiscale']
                    df_p.loc[mask, 'Nome'] = e_nome; df_p.loc[mask, 'Cognome'] = e_cognome
                    df_p.loc[mask, 'Codice_Fiscale'] = e_cf; df_p.loc[mask, 'Sesso'] = e_sesso
                    df_p.loc[mask, 'Indirizzo'] = e_indirizzo; df_p.loc[mask, 'Cellulare'] = e_cell
                    df_p.loc[mask, 'Email'] = e_email; df_p.loc[mask, 'Data_Nascita'] = e_nascita
                    df_p.loc[mask, 'Luogo_Nascita'] = e_luogo
                    df_p.to_csv(DB_PAZIENTI, index=False)
                    if e_cf != p_r['Codice_Fiscale']:
                        df_d.loc[df_d['Codice_Fiscale'] == p_r['Codice_Fiscale'], 'Codice_Fiscale'] = e_cf
                        df_d.to_csv(DB_DIETE, index=False)
                        df_pr.loc[df_pr['Codice_Fiscale'] == p_r['Codice_Fiscale'], 'Codice_Fiscale'] = e_cf
                        df_pr.to_csv(DB_PRESCRIZIONI, index=False)
                    st.session_state.edit_anagrafica = False
                    st.session_state.p_attivo = df_p[df_p['Codice_Fiscale'] == e_cf].iloc[0].to_dict()
                    st.rerun()
                if cc_a.form_submit_button("🚪 Chiudi Anagrafica", use_container_width=True):
                    st.session_state.edit_anagrafica = False
                    st.rerun()

  # --- fine tab1 ---

    elif paziente_tab == tab_labels[1]:
        if not st_p.empty:
            # ── SELEZIONE VISITA ─────────────────────────────────────────
            visite_tab2 = list(st_p_ord.iloc[::-1].iterrows())
            labels_tab2 = [f"🗓️ {rv['Data_Visita']}  —  ⚖️ {rv['Peso']} kg" for (_, rv) in visite_tab2]
            date_tab2   = [rv['Data_Visita'] for (_, rv) in visite_tab2]

            st.markdown("<div class='card' style='margin-bottom:12px;'><h4 class='card-header-blue'>🗓️ Seleziona Visita di Riferimento</h4></div>", unsafe_allow_html=True)
            scelta_tab2 = st.selectbox(
                "Visita:", range(len(labels_tab2)),
                format_func=lambda x: labels_tab2[x],
                index=0, key="selectbox_tab2", label_visibility="collapsed"
            )
            visita_selezionata = date_tab2[scelta_tab2]
            rv_tab2 = visite_tab2[scelta_tab2][1]
            stato_t2, stato_c2 = calcola_stato_bmi(to_f(rv_tab2['BMI']))
            sesso_paz = str(p_r.get('Sesso', 'M')).strip().upper()

            st.markdown(f"""
            <div style="background:#f0fff4;border:1px solid #e0e6ed;border-left:5px solid #2ecc71;
                 border-radius:8px;padding:10px 16px;margin:4px 0 14px 0;font-size:13px;color:#374151;">
                ✅ <b>Visita del {rv_tab2['Data_Visita']}</b> &nbsp;|&nbsp;
                ⚖️ Peso: <b>{rv_tab2['Peso']} kg</b> &nbsp;|&nbsp;
                📊 BMI: <b style="color:{stato_c2};">{rv_tab2['BMI']} — {stato_t2}</b> &nbsp;|&nbsp;
                {'👨 Uomo' if sesso_paz == 'M' else '👩 Donna'}
            </div>""", unsafe_allow_html=True)

            # ── SELEZIONE PIANO (GIORNI) ──────────────────────────────────
            pasti_giorno = 5 if sesso_paz == 'M' else 4
            st.markdown(f"""
            <div style="background:#f8fafc;border:1px solid #e0e6ed;border-radius:10px;padding:16px 20px;margin-bottom:16px;">
                <div style="font-size:15px;font-weight:800;color:#2c3e50;margin-bottom:4px;">
                    📋 Scegli la durata del Piano VLEKT
                </div>
                <div style="font-size:13px;color:#6b7280;margin-bottom:12px;">
                    {'👨 Uomo → 5 pasti/giorno' if sesso_paz == 'M' else '👩 Donna → 4 pasti/giorno'} &nbsp;|&nbsp;
                    Componi 1 giorno tipo: il sistema moltiplica automaticamente per i giorni scelti
                </div>
            </div>""", unsafe_allow_html=True)

            # ── SELEZIONE PIANO (GIORNI) ──────────────────────────────────
            if 'piano_giorni' not in st.session_state: st.session_state.piano_giorni = None
            if 'piano_step' not in st.session_state: st.session_state.piano_step = None

            # Configurazione in base al sesso dell'anagrafica
            if sesso_paz == 'M':
                emoji_sesso   = '👨'
                label_sesso   = 'Uomo'
                pasti_step1   = 5
                pasti_step2   = 4
            else:
                emoji_sesso   = '👩'
                label_sesso   = 'Donna'
                pasti_step1   = 4
                pasti_step2   = 3

            st.markdown(f"""
            <div style="background:#f8fafc;border:1px solid #e0e6ed;border-radius:10px;padding:16px 20px;margin-bottom:16px;">
                <div style="font-size:15px;font-weight:800;color:#2c3e50;margin-bottom:2px;">
                    📋 Scegli il Piano VLEKT — {emoji_sesso} {label_sesso}
                </div>
                <div style="font-size:12px;color:#6b7280;">
                    Due livelli disponibili: <b>Step 1</b> ({pasti_step1} pasti/giorno) e <b>Step 2</b> ({pasti_step2} pasti/giorno).
                    Seleziona durata e step, poi componi 1 giorno tipo.
                </div>
            </div>""", unsafe_allow_html=True)

            def btn_piano(col, giorni, step, pasti_g, key):
                pasti_tot = pasti_g * giorni
                sel = (st.session_state.piano_giorni == giorni and st.session_state.piano_step == step)
                bg     = "#2c3e50" if sel else "#ffffff"
                color  = "#ffffff" if sel else "#2c3e50"
                border = "#2c3e50" if sel else "#dee2e6"
                col.markdown(f"""
                <div style="background:{bg};border:2px solid {border};border-radius:10px;
                     padding:14px 6px;text-align:center;margin-bottom:4px;">
                    <div style="font-size:22px;font-weight:900;color:{'#f39c12' if sel else '#3498db'};">{giorni}</div>
                    <div style="font-size:10px;font-weight:700;color:{color};">giorni</div>
                    <div style="font-size:11px;font-weight:600;color:{'#aed6f1' if sel else '#7f8c8d'};margin-top:4px;">
                        {pasti_g}×{giorni} = {pasti_tot}
                    </div>
                    <div style="font-size:13px;font-weight:900;color:{'#f39c12' if sel else '#e74c3c'};margin-top:2px;">
                        {pasti_tot} pasti
                    </div>
                </div>""", unsafe_allow_html=True)
                label_btn = "✅ Sel." if sel else "Seleziona"
                if col.button(label_btn, key=key, use_container_width=True, type="primary" if sel else "secondary"):
                    st.session_state.piano_giorni = giorni
                    st.session_state.piano_step   = step
                    st.rerun()

            # ── STEP 1 ──
            st.markdown(f"""
            <div style="background:#eaf4fb;border-left:4px solid #3498db;border-radius:6px;
                 padding:8px 14px;margin:8px 0 6px 0;">
                <span style="font-size:14px;font-weight:800;color:#2c3e50;">
                    {emoji_sesso} Step 1
                </span>
                <span style="font-size:13px;color:#5d6d7e;margin-left:8px;">
                    — {pasti_step1} pasti al giorno &nbsp;|&nbsp; Calcolo: <b>{pasti_step1} × giorni</b>
                </span>
                <div style="font-size:11px;color:#3498db;margin-top:3px;font-style:italic;">
                    ({pasti_step1} pasti sostitutivi al giorno)
                </div>
            </div>""", unsafe_allow_html=True)
            cs1, cs2, cs3, cs4 = st.columns([2.5, 1, 1, 1])
            cs1.markdown(f"<div style='padding:12px 0;font-size:12px;color:#6b7280;'><b>{pasti_step1} pasti</b>/giorno</div>", unsafe_allow_html=True)
            btn_piano(cs2, 15, 1, pasti_step1, f"s1_15")
            btn_piano(cs3, 20, 1, pasti_step1, f"s1_20")
            btn_piano(cs4, 30, 1, pasti_step1, f"s1_30")

            st.markdown("<div style='margin:10px 0 0 0;'></div>", unsafe_allow_html=True)

            # ── STEP 2 ──
            st.markdown(f"""
            <div style="background:#eafaf1;border-left:4px solid #27ae60;border-radius:6px;
                 padding:8px 14px;margin:8px 0 6px 0;">
                <span style="font-size:14px;font-weight:800;color:#2c3e50;">
                    {emoji_sesso} Step 2
                </span>
                <span style="font-size:13px;color:#5d6d7e;margin-left:8px;">
                    — {pasti_step2} pasti al giorno &nbsp;|&nbsp; Calcolo: <b>{pasti_step2} × giorni</b>
                </span>
                <div style="font-size:11px;color:#27ae60;margin-top:3px;font-style:italic;">
                    ({pasti_step2} pasti sostitutivi + 1 pasto di proteine naturali a scelta tra Pranzo e Cena)
                </div>
            </div>""", unsafe_allow_html=True)
            cs21, cs22, cs23, cs24 = st.columns([2.5, 1, 1, 1])
            cs21.markdown(f"<div style='padding:12px 0;font-size:12px;color:#6b7280;'><b>{pasti_step2} pasti</b>/giorno</div>", unsafe_allow_html=True)
            btn_piano(cs22, 15, 2, pasti_step2, f"s2_15")
            btn_piano(cs23, 20, 2, pasti_step2, f"s2_20")
            btn_piano(cs24, 30, 2, pasti_step2, f"s2_30")

            # ── BANNER PIANO SELEZIONATO ──
            giorni_sel = st.session_state.piano_giorni
            step_sel   = st.session_state.piano_step

            if giorni_sel is None or step_sel is None:
                st.markdown("<br>", unsafe_allow_html=True)
                st.info(f"👆 Seleziona uno Step e la durata per procedere con l'inserimento dei pasti.")
                st.stop()

            pasti_g_sel   = pasti_step1 if step_sel == 1 else pasti_step2
            pasti_tot_sel = pasti_g_sel * giorni_sel

            st.markdown(f"""
            <div style="background:#2c3e50;border-radius:10px;padding:14px 20px;margin:14px 0 0 0;">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                    <div>
                        <div style="font-size:11px;color:#95a5a6;font-weight:600;text-transform:uppercase;">Piano Selezionato</div>
                        <div style="font-size:18px;font-weight:900;color:#ffffff;">
                            {emoji_sesso} {label_sesso} — Step {step_sel} — {giorni_sel} giorni
                        </div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:11px;color:#95a5a6;">Pasti/giorno</div>
                        <div style="font-size:24px;font-weight:900;color:#f39c12;">{pasti_g_sel}</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:11px;color:#95a5a6;">Formula</div>
                        <div style="font-size:16px;font-weight:800;color:#aed6f1;">{pasti_g_sel} × {giorni_sel}</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:11px;color:#95a5a6;">Totale Pasti</div>
                        <div style="font-size:28px;font-weight:900;color:#2ecc71;">{pasti_tot_sel}</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

            st.markdown("---")


            # ── COMPOSIZIONE GIORNO TIPO ──────────────────────────────────
            c_add, c_res = st.columns([0.35, 0.65])

            with c_add:
                st.markdown(f"<div class='card'><h4 class='card-header-blue'>🏗️ Componi 1 Giorno Tipo — Step {step_sel} ({pasti_g_sel} pasti)</h4></div>", unsafe_allow_html=True)
                st.markdown("<div style='margin-top: -60px; padding: 0 15px;'>", unsafe_allow_html=True)

                # Pasti disponibili in base a sesso e step
                lista_pasti_attiva = LISTA_PASTI_DONNA if sesso_paz == 'F' else LISTA_PASTI_UOMO
                pasti_disponibili = list(lista_pasti_attiva[:pasti_g_sel])

                # Step 2 → aggiungi Cena come pasto proteico extra se non è già presente
                if step_sel == 2:
                    if sesso_paz == 'F' and 'Cena' not in pasti_disponibili:
                        pasti_disponibili.append('Cena')
                    if sesso_paz == 'M' and 'Cena' not in pasti_disponibili:
                        pasti_disponibili.append('Cena')

                pasto_sel = st.selectbox("Momento del Pasto", pasti_disponibili)

                # Step 2: Pranzo e Cena sono pasti proteici (per entrambi i sessi)
                is_pasto_proteico = step_sel == 2 and pasto_sel in ['Pranzo', 'Cena']

                if is_pasto_proteico:
                    st.markdown(f"""
                    <div style="background:#fff8e1;border-left:4px solid #f39c12;border-radius:6px;
                         padding:8px 12px;margin:8px 0;">
                        <span style="font-size:13px;font-weight:800;color:#d35400;">
                            🥩 Step 2 — Pasto Proteico ({pasto_sel})
                        </span>
                        <div style="font-size:11px;color:#7f8c8d;margin-top:2px;">
                            Puoi inserire un prodotto VLEKT oppure una proteina naturale
                        </div>
                    </div>""", unsafe_allow_html=True)

                    tipo_pasto = st.radio(
                        "Tipo di inserimento",
                        ["🍱 Prodotto VLEKT", "🥩 Proteina Naturale"],
                        horizontal=True,
                        key=f"tipo_ins_{pasto_sel}"
                    )
                else:
                    tipo_pasto = "🍱 Prodotto VLEKT"

                # ── INSERIMENTO PROTEINA NATURALE ──
                if tipo_pasto == "🥩 Proteina Naturale":
                    if not df_prot.empty:
                        categorie_prot = ['Tutte'] + sorted(df_prot['Categoria'].dropna().unique().tolist())
                        cat_prot_sel = st.selectbox("Categoria", categorie_prot, key="cat_prot_sel_piano")
                        df_prot_filtrata = df_prot if cat_prot_sel == 'Tutte' else df_prot[df_prot['Categoria'] == cat_prot_sel]
                        nomi_prot = df_prot_filtrata['Nome'].sort_values().unique()
                        prot_sel = st.selectbox("Seleziona Proteina", nomi_prot, key="prot_sel_piano")
                        prot_info = df_prot[df_prot['Nome'] == prot_sel].iloc[0]

                        grammi_std = to_f(prot_info['Grammi_Porzione']) or 100
                        grammi_ins = st.number_input("Grammi da inserire", min_value=10, value=int(grammi_std), step=10, key="grammi_prot_ins")

                        fattore = grammi_ins / grammi_std if grammi_std > 0 else 1
                        kcal_p  = round(to_f(prot_info['Kcal']) * fattore, 1)
                        prot_p  = round(to_f(prot_info['Prot']) * fattore, 1)
                        gras_p  = round(to_f(prot_info['Grassi']) * fattore, 1)
                        carb_p  = round(to_f(prot_info['Carbo_Netti']) * fattore, 1)

                        st.markdown(f"""
                        <div style="background:#f0fff4;border:1px solid #2ecc71;border-radius:6px;
                             padding:8px 12px;font-size:12px;color:#1a7a40;margin:6px 0;">
                            <b>{grammi_ins}g di {prot_sel}</b> →
                            Kcal: <b>{kcal_p}</b> | Prot: <b>{prot_p}g</b> |
                            Grassi: <b>{gras_p}g</b> | Carbo: <b>{carb_p}g</b>
                            {'<br>📝 ' + str(prot_info['Note']) if str(prot_info.get('Note','')).strip() not in ('','nan') else ''}
                        </div>""", unsafe_allow_html=True)

                        if st.button("➕ Inserisci Proteina nel Piano", use_container_width=True, type="primary"):
                            nome_voce = f"🥩 {prot_sel} ({grammi_ins}g)"
                            n_d = [
                                p_r['Codice_Fiscale'], visita_selezionata, step_sel, giorni_sel, pasto_sel, nome_voce, 1,
                                kcal_p, carb_p, prot_p, gras_p
                            ]
                            pd.concat([df_d, pd.DataFrame([n_d], columns=COLS_DIETA)]).to_csv(DB_DIETE, index=False)
                            st.rerun()
                    else:
                        st.warning("⚠️ Nessuna proteina nel database. Aggiungile dal menu **🥩 DB Proteine Naturali** in sidebar.")

                # ── INSERIMENTO PRODOTTO VLEKT ──
                else:
                    if not df_a.empty:
                        prodotti_ordinati = df_a['Alimento'].sort_values().unique()
                        ali_sel = st.selectbox("Seleziona Prodotto", prodotti_ordinati)
                        b_info = df_a[df_a['Alimento'] == ali_sel].iloc[0]
                        porzioni_box = str(b_info.get('Porzioni_Confezione', '1'))

                        col_q, col_p = st.columns(2)
                        quant = col_q.number_input("N. Scatole al giorno", min_value=1, value=1, step=1)
                        col_p.text_input("Pz. in 1 Scatola", value=porzioni_box, disabled=True)
                        porz_num = to_f(porzioni_box) if to_f(porzioni_box) > 0 else 1
                        giorni_coperti = int(quant * porz_num)
                        st.caption(f"📦 {quant} scatola/e × {int(porz_num)} pz = **{giorni_coperti} giorni di copertura**")

                        if st.button("➕ Inserisci nel Piano", use_container_width=True, type="primary"):
                            n_d = [
                                p_r['Codice_Fiscale'], visita_selezionata, step_sel, giorni_sel, pasto_sel, ali_sel, quant,
                                to_f(b_info['Kcal'])*quant, to_f(b_info['Carbo_Netti'])*quant,
                                to_f(b_info['Prot'])*quant, to_f(b_info['Grassi'])*quant
                            ]
                            pd.concat([df_d, pd.DataFrame([n_d], columns=COLS_DIETA)]).to_csv(DB_DIETE, index=False)
                            st.rerun()
                    else:
                        st.warning("Il database alimenti è vuoto.")
                st.markdown("</div>", unsafe_allow_html=True)

            with c_res:
                st.markdown("<div class='card'><h4 class='card-header-blue'>📊 Analisi Giorno Tipo</h4></div>", unsafe_allow_html=True)
                st.markdown("<div style='margin-top: -60px; padding: 0 15px;'>", unsafe_allow_html=True)

                # Carica tutto il piano della visita
                # Carica righe della visita selezionata
                dieta_tutta = df_d[
                    (df_d['Codice_Fiscale'] == p_r['Codice_Fiscale']) &
                    (df_d['Data_Visita'] == visita_selezionata)
                ].copy()

                # Filtra per Step + Giorni — match esatto
                dieta_p = dieta_tutta[
                    (dieta_tutta['Step'].astype(str).str.strip() == str(step_sel)) &
                    (dieta_tutta['Giorni'].astype(str).str.strip() == str(giorni_sel))
                ].copy()

                # ── SEMPRE: Riepilogo card pasti con semaforo ──
                st.markdown("##### 🍽️ Riepilogo Pasti Giornalieri")

                lista_pasti_attiva = LISTA_PASTI_DONNA if sesso_paz == 'F' else LISTA_PASTI_UOMO
                # Step 2: aggiungi Cena se non presente
                lista_pasti_vis = list(lista_pasti_attiva[:pasti_g_sel])
                if step_sel == 2 and 'Cena' not in lista_pasti_vis:
                    lista_pasti_vis.append('Cena')

                emoji_pasti  = {'Colazione':'☀️','Spuntino Mattina':'🍎','Spuntino/Merenda':'🍎','Pranzo':'🥗','Merenda':'🍊','Cena':'🌙','Dopo Cena':'🌛'}
                colori_pasti = {'Colazione':'#FFF3CD','Spuntino Mattina':'#FFE6CC','Spuntino/Merenda':'#FFE6CC','Pranzo':'#D4EDDA','Merenda':'#D1ECF1','Cena':'#E2E3E5','Dopo Cena':'#E8DAEF'}
                colori_border= {'Colazione':'#f39c12','Spuntino Mattina':'#e67e22','Spuntino/Merenda':'#e67e22','Pranzo':'#27ae60','Merenda':'#17a2b8','Cena':'#6c757d','Dopo Cena':'#8e44ad'}

                if not dieta_p.empty:
                    dieta_p_ext2 = dieta_p.copy()
                    dieta_p_ext2 = dieta_p_ext2.merge(df_a[['Alimento','Porzioni_Confezione']], on='Alimento', how='left')
                    dieta_p_ext2['Porzioni_Confezione'] = dieta_p_ext2['Porzioni_Confezione'].fillna(1).apply(to_f)
                    dieta_p_ext2.loc[dieta_p_ext2['Porzioni_Confezione'] <= 0, 'Porzioni_Confezione'] = 1.0
                    dieta_p_ext2['Giorni_Coperti'] = dieta_p_ext2['Quantita'].apply(to_f) * dieta_p_ext2['Porzioni_Confezione']
                    dieta_p_dedup2 = dieta_p_ext2.drop_duplicates(subset=['Pasto','Alimento'])
                    # I prodotti dello stesso pasto sono ALTERNATIVI (si alternano nei giorni)
                    # → giorni coperti dal pasto = SOMMA dei giorni coperti da ogni prodotto
                    giorni_tot_pasto = dieta_p_dedup2.groupby('Pasto')['Giorni_Coperti'].sum()
                    n_prodotti_pasto = dieta_p_dedup2.groupby('Pasto')['Alimento'].count()
                    # Kcal media/giorno per pasto = somma kcal di tutte le porzioni / giorni coperti dal pasto
                    # Proteine naturali: kcal intere (si mangiano ogni giorno)
                    giorni_piano_card = giorni_sel if giorni_sel else 15
                    def kcal_gg_riga(r):
                        if str(r['Alimento']).startswith('🥩'):
                            return to_f(r['Kcal_Tot'])  # kcal intere ogni giorno
                        # Kcal totali del prodotto = Kcal_Tot × Porzioni_Confezione
                        # diviso per i giorni totali del pasto (calcolato dopo il groupby)
                        return to_f(r['Kcal_Tot']) * r['Porzioni_Confezione']
                    dieta_p_dedup2['Kcal_tot_pasto'] = dieta_p_dedup2.apply(kcal_gg_riga, axis=1)
                    kcal_sum_pasto = dieta_p_dedup2.groupby('Pasto')['Kcal_tot_pasto'].sum()
                    # kcal/gg = somma_kcal_porzioni / giorni_coperti_pasto
                    kcal_pasti = {}
                    for pasto_k in kcal_sum_pasto.index:
                        gg_p = giorni_tot_pasto.get(pasto_k, giorni_piano_card)
                        # se è solo proteine naturali nel pasto, kcal_sum è già la kcal/gg
                        righe_k = dieta_p_dedup2[dieta_p_dedup2['Pasto'] == pasto_k]
                        solo_nat = righe_k['Alimento'].str.startswith('🥩', na=False).all()
                        if solo_nat:
                            kcal_pasti[pasto_k] = float(kcal_sum_pasto[pasto_k])
                        else:
                            kcal_nat_k  = righe_k.loc[righe_k['Alimento'].str.startswith('🥩', na=False), 'Kcal_Tot'].apply(to_f).sum()
                            kcal_vlekt_k = righe_k.loc[~righe_k['Alimento'].str.startswith('🥩', na=False), 'Kcal_tot_pasto'].sum()
                            gg_vlekt_k = righe_k.loc[~righe_k['Alimento'].str.startswith('🥩', na=False), 'Giorni_Coperti'].sum()
                            kcal_pasti[pasto_k] = kcal_nat_k + (kcal_vlekt_k / gg_vlekt_k if gg_vlekt_k > 0 else 0)
                    kcal_pasti = pd.Series(kcal_pasti)
                else:
                    dieta_p_dedup2   = pd.DataFrame(columns=['Pasto','Alimento','Giorni_Coperti'])
                    giorni_tot_pasto = pd.Series(dtype=float)
                    n_prodotti_pasto = pd.Series(dtype=int)
                    kcal_pasti       = pd.Series(dtype=float)

                target = giorni_sel if giorni_sel else 15
                cols_pasti = st.columns(len(lista_pasti_vis))
                for ci, pasto in enumerate(lista_pasti_vis):
                    giorni_pasto = int(giorni_tot_pasto.get(pasto, 0))
                    tot_kc  = float(kcal_pasti.get(pasto, 0))
                    n_ali   = int(n_prodotti_pasto.get(pasto, 0))
                    bg      = colori_pasti.get(pasto, '#f8f9fa')
                    border  = colori_border.get(pasto, '#adb5bd')
                    emoji   = emoji_pasti.get(pasto, '🍽️')

                    righe_pasto = dieta_p_dedup2[dieta_p_dedup2['Pasto'] == pasto] if not dieta_p_dedup2.empty else pd.DataFrame()
                    dettaglio_righe = ""
                    for _, r in righe_pasto.iterrows():
                        nome_breve = str(r['Alimento'])[:18].replace("'", "&#39;").replace('"', '&quot;')
                        gg = int(r['Giorni_Coperti'])
                        dettaglio_righe += f"<div style='font-size:9px;color:#444;margin-top:2px;text-align:left;padding:0 6px;'>{nome_breve}: <b>{gg}gg</b></div>"

                    # Semaforo: se c'è almeno una proteina naturale nel pasto → copre tutti i giorni selezionati
                    ha_proteina = not righe_pasto.empty and righe_pasto['Alimento'].str.startswith('🥩').any()
                    coperti = target if ha_proteina else giorni_pasto
                    pct_sem = min(coperti / target, 1.0) if target > 0 else 0
                    if pct_sem >= 1.0:
                        sem_col = "#2ecc71"; sem_dot = "🟢"; sem_txt = "Completo"
                    elif pct_sem > 0:
                        sem_col = "#f39c12"; sem_dot = "🟡"; sem_txt = f"{coperti}/{target} gg"
                    else:
                        sem_col = "#e74c3c"; sem_dot = "🔴"; sem_txt = f"0/{target} gg"
                    barra_sem   = int(pct_sem * 100)
                    mancanti_sem = max(0, target - coperti)

                    html_card = (
                        f'<div style="background:{bg};border:1px solid #e0e6ed;border-top:4px solid {border};border-radius:8px;padding:10px 8px;text-align:center;margin-bottom:6px;">'
                        f'<div style="font-size:18px;">{emoji}</div>'
                        f'<div style="font-size:10px;font-weight:800;color:#2c3e50;margin-top:2px;">{pasto}</div>'
                        f'<div style="font-size:22px;font-weight:900;color:{border};margin:4px 0;">{giorni_pasto if n_ali > 0 else chr(8212)}</div>'
                        f'<div style="font-size:10px;color:#6b7280;margin-bottom:4px;">giorni totali</div>'
                        + dettaglio_righe
                        + (f'<div style="font-size:11px;font-weight:600;color:#374151;margin-top:5px;">{tot_kc:.0f} kcal/gg</div>' if n_ali > 0 else '')
                        + f'<div style="margin-top:8px;padding-top:6px;border-top:1px solid #e0e6ed;">'
                        f'<div style="background:#e9ecef;border-radius:6px;height:6px;margin-bottom:4px;overflow:hidden;">'
                        f'<div style="background:{sem_col};width:{barra_sem}%;height:100%;border-radius:6px;"></div>'
                        f'</div>'
                        f'<div style="font-size:10px;font-weight:800;color:{sem_col};">{sem_dot} {sem_txt}</div>'
                        + (f'<div style="font-size:9px;color:{sem_col};margin-top:2px;">mancano {mancanti_sem} gg</div>' if mancanti_sem > 0 else '')
                        + '</div></div>'
                    )
                    cols_pasti[ci].markdown(html_card, unsafe_allow_html=True)

                if not dieta_p.empty:
                    dieta_p['sort'] = dieta_p['Pasto'].map(ORDINE_PASTI)
                    dieta_p = dieta_p.sort_values('sort')

                    # ── LOGICA MACRO PER GIORNO TIPO ──────────────────────────────
                    # PRODOTTI VLEKT (scatole con porzioni):
                    #   Porzioni totali = Quantita × Porzioni_Confezione
                    #   Media kcal/gg   = (Kcal_Tot × Porzioni_Confezione) / giorni_sel
                    #
                    # PROTEINE NATURALI (🥩): si mangiano OGNI giorno → kcal intere, nessuna divisione
                    #   Kcal/gg = Kcal_Tot (già salvato come kcal del pasto, Quantita=1)
                    dieta_p_kcal = dieta_p.copy()
                    dieta_p_kcal = dieta_p_kcal.merge(df_a[['Alimento','Porzioni_Confezione']].drop_duplicates('Alimento'), on='Alimento', how='left')
                    dieta_p_kcal['Porzioni_Confezione'] = dieta_p_kcal['Porzioni_Confezione'].fillna(1).apply(to_f)
                    dieta_p_kcal.loc[dieta_p_kcal['Porzioni_Confezione'] <= 0, 'Porzioni_Confezione'] = 1.0
                    for col in ['Kcal_Tot','Prot_Tot','Grassi_Tot','Carbo_Tot']:
                        dieta_p_kcal[col] = dieta_p_kcal[col].apply(to_f)
                    giorni_piano = giorni_sel if giorni_sel else 15
                    giorni_piano_div = max(1, int(to_f(giorni_piano)))
                    mask_nat = dieta_p_kcal['Alimento'].str.startswith('🥩', na=False)
                    # Proteine naturali: kcal intere ogni giorno
                    kcal_nat   = dieta_p_kcal.loc[mask_nat, 'Kcal_Tot'].sum()
                    prot_nat   = dieta_p_kcal.loc[mask_nat, 'Prot_Tot'].sum()
                    grassi_nat = dieta_p_kcal.loc[mask_nat, 'Grassi_Tot'].sum()
                    carbo_nat  = dieta_p_kcal.loc[mask_nat, 'Carbo_Tot'].sum()
                    # Prodotti VLEKT: media su giorni_piano (evita divisione per zero)
                    kcal_vlekt   = (dieta_p_kcal.loc[~mask_nat, 'Kcal_Tot']  * dieta_p_kcal.loc[~mask_nat, 'Porzioni_Confezione']).sum() / giorni_piano_div
                    prot_vlekt   = (dieta_p_kcal.loc[~mask_nat, 'Prot_Tot']   * dieta_p_kcal.loc[~mask_nat, 'Porzioni_Confezione']).sum() / giorni_piano_div
                    grassi_vlekt = (dieta_p_kcal.loc[~mask_nat, 'Grassi_Tot'] * dieta_p_kcal.loc[~mask_nat, 'Porzioni_Confezione']).sum() / giorni_piano_div
                    carbo_vlekt  = (dieta_p_kcal.loc[~mask_nat, 'Carbo_Tot']  * dieta_p_kcal.loc[~mask_nat, 'Porzioni_Confezione']).sum() / giorni_piano_div
                    kcal_giorno   = kcal_nat   + kcal_vlekt
                    prot_giorno   = prot_nat   + prot_vlekt
                    grassi_giorno = grassi_nat + grassi_vlekt
                    carbo_giorno  = carbo_nat  + carbo_vlekt
                    pasti_inseriti = dieta_p['Pasto'].nunique()
                    pasti_target_giorno = len(lista_pasti_vis)  # include Cena proteica per step 2
                    colore_prog = "#2ecc71" if pasti_inseriti >= pasti_target_giorno else "#e67e22"

                    st.markdown(f"""
                    <div style="background:#f8fafc;border:1px solid #e0e6ed;border-radius:8px;padding:12px 16px;margin-bottom:10px;">
                        <div style="font-size:13px;font-weight:700;color:#2c3e50;margin-bottom:8px;">📅 Giorno tipo — Macronutrienti per 1 giorno</div>
                        <div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:8px;">
                            <div style="text-align:center;"><div style="font-size:20px;font-weight:900;color:#e74c3c;">{kcal_giorno:.0f}</div><div style="font-size:10px;color:#6b7280;">Kcal/giorno</div></div>
                            <div style="text-align:center;"><div style="font-size:20px;font-weight:900;color:#3498db;">{prot_giorno:.1f}g</div><div style="font-size:10px;color:#6b7280;">Proteine</div></div>
                            <div style="text-align:center;"><div style="font-size:20px;font-weight:900;color:#f39c12;">{grassi_giorno:.1f}g</div><div style="font-size:10px;color:#6b7280;">Grassi</div></div>
                            <div style="text-align:center;"><div style="font-size:20px;font-weight:900;color:#27ae60;">{carbo_giorno:.1f}g</div><div style="font-size:10px;color:#6b7280;">Carbo Netti</div></div>
                        </div>
                        <div style="font-size:12px;color:{colore_prog};font-weight:700;">
                            🍽️ Pasti inseriti: {pasti_inseriti} / {pasti_target_giorno}
                            {'✅ Giorno completo!' if pasti_inseriti >= pasti_target_giorno else f' — mancano {pasti_target_giorno - pasti_inseriti} pasti'}
                        </div>
                    </div>""", unsafe_allow_html=True)

                    st.markdown("<br>", unsafe_allow_html=True)
                    # Tabella: mostra pezzi totali (Quantita × Porzioni_Confezione) e macro per singolo pezzo
                    df_visual = dieta_p[['Pasto','Alimento','Quantita','Grassi_Tot','Prot_Tot','Carbo_Tot','Kcal_Tot']].copy()
                    df_visual = df_visual.merge(df_a[['Alimento','Porzioni_Confezione']].drop_duplicates('Alimento'), on='Alimento', how='left')
                    df_visual['Porzioni_Confezione'] = df_visual['Porzioni_Confezione'].fillna(1).apply(to_f)
                    df_visual.loc[df_visual['Porzioni_Confezione'] <= 0, 'Porzioni_Confezione'] = 1.0
                    # Per proteine naturali (🥩): Porzioni = 1, Quantita rimane 1
                    mask_nat_vis = df_visual['Alimento'].str.startswith('🥩', na=False)
                    df_visual.loc[mask_nat_vis, 'Porzioni_Confezione'] = 1.0
                    # Pezzi totali = Quantita × Porzioni_Confezione
                    df_visual['Pezzi'] = (df_visual['Quantita'].apply(to_f) * df_visual['Porzioni_Confezione']).apply(lambda x: int(round(x)))
                    # Macro per singolo pezzo = X_Tot / Quantita (Kcal_Tot = Kcal_per_pezzo × Quantita_scatole)
                    qt_safe = df_visual['Quantita'].apply(to_f).clip(lower=1)
                    for col_tot, col_new in [('Kcal_Tot','Kcal'), ('Grassi_Tot','Grassi'), ('Prot_Tot','Prot'), ('Carbo_Tot','Carbo')]:
                        df_visual[col_new] = (df_visual[col_tot].apply(to_f) / qt_safe).round(1)
                    df_visual = df_visual.rename(columns={'Pezzi': 'Quantita_show'})
                    df_visual['Quantita'] = df_visual['Quantita_show']
                    df_visual = df_visual[['Pasto','Alimento','Quantita','Grassi','Prot','Carbo','Kcal']]
                    st.dataframe(
                        df_visual.style.apply(colora_pasti, axis=1).format({'Grassi':'{:.1f}','Prot':'{:.1f}','Carbo':'{:.1f}','Kcal':'{:.1f}'}),
                        use_container_width=True, hide_index=True
                    )

                    st.markdown("##### 📝 Correzione Singoli Pasti")
                    for id_d, r_d in dieta_p.iterrows():
                        is_proteina = str(r_d['Alimento']).startswith('🥩')
                        qt_attuale = int(to_f(r_d['Quantita'])) if not is_proteina else None

                        if st.session_state.confirm_del_pasto == id_d:
                            st.warning(f"⚠️ Eliminare **{r_d['Alimento']}** ({r_d['Pasto']})? L'azione è irreversibile.")
                            cp1, cp2 = st.columns(2)
                            if cp1.button("✅ Sì, elimina", key=f"conf_si_pasto_{id_d}", use_container_width=True, type="primary"):
                                df_d.drop(id_d).to_csv(DB_DIETE, index=False)
                                st.session_state.confirm_del_pasto = None
                                st.rerun()
                            if cp2.button("❌ Annulla", key=f"conf_no_pasto_{id_d}", use_container_width=True):
                                st.session_state.confirm_del_pasto = None
                                st.rerun()
                        else:
                            if is_proteina:
                                # Proteina naturale: solo nome + cestino (quantità sempre 1, non modificabile)
                                ctx, cdl = st.columns([0.85, 0.15])
                                ctx.write(f"**{r_d['Pasto']}**: {r_d['Alimento']}")
                                if cdl.button("🗑️", key=f"deli_{id_d}", use_container_width=True):
                                    st.session_state.confirm_del_pasto = id_d
                                    st.rerun()
                            else:
                                # Prodotto VLEKT: tasti - / + per cambiare numero scatole
                                c_label, c_minus, c_qt, c_plus, c_del = st.columns([3.5, 0.5, 0.5, 0.5, 0.5])
                                c_label.markdown(f"**{r_d['Pasto']}**: {r_d['Alimento']}")
                                c_qt.markdown(f"<div style='text-align:center;font-weight:800;font-size:16px;padding-top:4px;'>{qt_attuale}</div>", unsafe_allow_html=True)

                                if c_minus.button("➖", key=f"minus_{id_d}", use_container_width=True):
                                    if qt_attuale > 1:
                                        nuova_qt = qt_attuale - 1
                                        # Ricalcola i totali (macro per scatola = X_Tot / qt_attuale)
                                        kcal_u = to_f(r_d['Kcal_Tot']) / qt_attuale
                                        carbo_u = to_f(r_d['Carbo_Tot']) / qt_attuale
                                        prot_u  = to_f(r_d['Prot_Tot'])  / qt_attuale
                                        gras_u  = to_f(r_d['Grassi_Tot'])/ qt_attuale
                                        df_d.loc[id_d, 'Quantita']   = nuova_qt
                                        df_d.loc[id_d, 'Kcal_Tot']   = round(kcal_u  * nuova_qt, 2)
                                        df_d.loc[id_d, 'Carbo_Tot']  = round(carbo_u * nuova_qt, 2)
                                        df_d.loc[id_d, 'Prot_Tot']   = round(prot_u  * nuova_qt, 2)
                                        df_d.loc[id_d, 'Grassi_Tot'] = round(gras_u  * nuova_qt, 2)
                                        df_d.to_csv(DB_DIETE, index=False)
                                        st.rerun()
                                    else:
                                        st.session_state.confirm_del_pasto = id_d
                                        st.rerun()

                                if c_plus.button("➕", key=f"plus_{id_d}", use_container_width=True):
                                    nuova_qt = qt_attuale + 1
                                    kcal_u = to_f(r_d['Kcal_Tot']) / qt_attuale
                                    carbo_u = to_f(r_d['Carbo_Tot']) / qt_attuale
                                    prot_u  = to_f(r_d['Prot_Tot'])  / qt_attuale
                                    gras_u  = to_f(r_d['Grassi_Tot'])/ qt_attuale
                                    df_d.loc[id_d, 'Quantita']   = nuova_qt
                                    df_d.loc[id_d, 'Kcal_Tot']   = round(kcal_u  * nuova_qt, 2)
                                    df_d.loc[id_d, 'Carbo_Tot']  = round(carbo_u * nuova_qt, 2)
                                    df_d.loc[id_d, 'Prot_Tot']   = round(prot_u  * nuova_qt, 2)
                                    df_d.loc[id_d, 'Grassi_Tot'] = round(gras_u  * nuova_qt, 2)
                                    df_d.to_csv(DB_DIETE, index=False)
                                    st.rerun()

                                if c_del.button("🗑️", key=f"deli_{id_d}", use_container_width=True):
                                    st.session_state.confirm_del_pasto = id_d
                                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

                if not dieta_p.empty:
                    st.markdown("<div style='margin-top: -60px; padding: 0 15px;'>", unsafe_allow_html=True)

                    dieta_p['Quantita'] = dieta_p['Quantita'].apply(to_f)
                    dieta_p['Alimento'] = dieta_p['Alimento'].str.strip()
                    # Esclude le proteine naturali (alimenti freschi, non hanno scatole da acquistare)
                    dieta_p_vlekt = dieta_p[~dieta_p['Alimento'].str.startswith('🥩')]
                    # Rimuove duplicati per stesso pasto+alimento, poi somma i pezzi tra pasti diversi
                    dieta_p_dedup_scorte = dieta_p_vlekt.drop_duplicates(subset=['Pasto', 'Alimento'])
                    scorte = dieta_p_dedup_scorte.groupby('Alimento')['Quantita'].sum().reset_index()
                    if 'Porzioni_Confezione' not in df_a.columns: df_a['Porzioni_Confezione'] = "1"
                    # Deduplicare df_a per evitare righe doppie con stesso nome alimento che causano moltiplicazione
                    df_a_dedup = df_a.copy()
                    df_a_dedup['Alimento'] = df_a_dedup['Alimento'].str.strip()
                    df_a_dedup = df_a_dedup.drop_duplicates(subset=['Alimento'], keep='first')
                    scorte = scorte.merge(df_a_dedup[['Alimento','Porzioni_Confezione']], on='Alimento', how='left')
                    scorte['Porzioni_Confezione'] = scorte['Porzioni_Confezione'].fillna(1).apply(to_f)
                    scorte.loc[scorte['Porzioni_Confezione'] <= 0, 'Porzioni_Confezione'] = 1.0

                    # Scatole da acquistare = ceil(Quantita_giornaliera / Pezzi_per_scatola)
                    scorte['Confezioni_Necessarie'] = scorte.apply(
                        lambda r: int(np.ceil(r['Quantita'] / r['Porzioni_Confezione'])) if r['Porzioni_Confezione'] > 0 else int(r['Quantita'])
                    , axis=1)

                    scorte_disp = scorte[['Alimento','Porzioni_Confezione','Confezioni_Necessarie']].copy()
                    scorte_disp.columns = ['Pasto Sostitutivo', 'Pz/Scatola', 'Scatole da Acquistare']
                    st.dataframe(scorte_disp, use_container_width=True, hide_index=True)

                    pdf_bytes = genera_pdf_report(p_r, st_p, dieta_p, scorte, data_visita=visita_selezionata)
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    scorte = pd.DataFrame()
                    pdf_bytes = None

                # ── ELIMINA PIANO e PDF — sempre visibili se esiste almeno un dato per questa visita ──
                if not dieta_tutta.empty:
                    col_del, col_pdf = st.columns(2)
                    if not st.session_state.confirm_del_piano:
                        if col_del.button("🗑️ ELIMINA INTERO PIANO", use_container_width=True):
                            st.session_state.confirm_del_piano = True
                            st.rerun()
                    else:
                        st.warning(f"⚠️ Sei sicuro di voler eliminare il piano **Step {step_sel} — {giorni_sel} giorni** della visita del {visita_selezionata}?")
                        cpi1, cpi2 = st.columns(2)
                        if cpi1.button("✅ Sì, elimina piano", key="conf_si_piano", use_container_width=True, type="primary"):
                            mask_keep = ~(
                                (df_d['Codice_Fiscale'] == p_r['Codice_Fiscale']) &
                                (df_d['Data_Visita'] == visita_selezionata) &
                                (df_d['Step'].astype(str).str.strip() == str(step_sel)) &
                                (df_d['Giorni'].astype(str).str.strip() == str(giorni_sel))
                            )
                            df_d[mask_keep].to_csv(DB_DIETE, index=False)
                            st.session_state.confirm_del_piano = False
                            st.rerun()
                        if cpi2.button("❌ Annulla", key="conf_no_piano", use_container_width=True):
                            st.session_state.confirm_del_piano = False
                            st.rerun()

                    if pdf_bytes:
                        col_pdf.download_button("📥 SCARICA REPORT E LISTA SPESA (PDF)", pdf_bytes, f"VLEKT_{p_r['Cognome']}_{visita_selezionata.replace('/','-')}.pdf", "application/pdf", use_container_width=True)

                # ── PIANO DIETA GIORNALIERO ──
                sesso_paz = p_r.get('Sesso', 'M')
                piano_bytes = genera_piano_dieta_pdf(
                    sesso_paz, step_sel,
                    p_r.get('Cognome', ''), p_r.get('Nome', ''),
                    visita_selezionata
                )
                if piano_bytes:
                    label_piano = f"📋 PIANO DIETA {'DONNA' if sesso_paz == 'F' else 'UOMO'} STEP {step_sel}"
                    st.download_button(
                        label_piano, piano_bytes,
                        f"PianoDieta_{p_r.get('Cognome','')}_{visita_selezionata.replace('/','-')}_Step{step_sel}.pdf",
                        "application/pdf",
                        use_container_width=True
                    )
                else:
                    app_dir = os.path.dirname(os.path.abspath(__file__))
                    template_name = PDF_PIANI.get((sesso_paz, step_sel), '')
                    st.warning(f"⚠️ Template PDF non trovato: `{template_name}` — copialo nella stessa cartella dell'app.")
        else:
            st.warning("⚠️ Devi registrare almeno una visita prima di poter assegnare un piano alimentare.")

    elif paziente_tab == tab_labels[2]:
        st.subheader("💊 Integratori e Prescrizioni")
        _n_visite = len(date_visite_disponibili) if date_visite_disponibili else 0
        if _n_visite == 0:
            st.warning("Devi registrare almeno una visita prima di prescrivere gli integratori.")
            st.info("👉 Vai nel tab **Cruscotto Visite** e clicca **Nuova Visita** per registrare la prima visita.")
        else:
            visita_corrente = st_p_ord.iloc[-1]['Data_Visita']
            # Normalizza date per selectbox
            date_visite_str = [str(d) for d in date_visite_disponibili]
            idx_default_pr = max(0, len(date_visite_str) - 1)
            visita_prescr = st.selectbox(
                "Visita di riferimento:",
                date_visite_str,
                index=idx_default_pr,
                key="sel_visita_prescr"
            )

            df_pr_fresh = carica_database(DB_PRESCRIZIONI, COLS_PRESCR)
            prescr_visita = df_pr_fresh[
                (df_pr_fresh['Codice_Fiscale'].astype(str).str.strip() == str(p_r['Codice_Fiscale']).strip()) &
                (df_pr_fresh['Data_Visita'].astype(str) == str(visita_prescr))
            ].copy()

            st.markdown("---")
            col_sx, col_dx = st.columns([0.45, 0.55])

            with col_sx:
                st.markdown("<div class='card'><h4 class='card-header-blue'>➕ Aggiungi Integratore</h4></div>", unsafe_allow_html=True)
                lista_integr = df_i['Nome_Integratore'].dropna().astype(str).str.strip().unique()
                lista_integr = sorted([x for x in lista_integr if x and x.lower() != 'nan'])

                with st.form("form_prescr_add", clear_on_submit=True):
                    opt_default = "-- Seleziona dal database --"
                    opts = [opt_default] + lista_integr if lista_integr else [opt_default]
                    scelto = st.selectbox(
                        "Integratore dal database:",
                        opts,
                        key="prescr_sel_db"
                    )
                    nome_custom = st.text_input("Oppure scrivi un nuovo integratore:", placeholder="es. Omega 3, Vitamina D...", key="prescr_nome_custom")
                    nome_da_usare = nome_custom.strip() if nome_custom.strip() else (scelto if scelto != opt_default else "")
                    if nome_da_usare:
                        st.caption(f"✅ Da prescrivere: **{nome_da_usare}**")

                    pr_categoria = st.text_input("Categoria (opzionale)", placeholder="es. Vitamine, Omega...", key="prescr_cat")
                    st.markdown("**Data Inizio**")
                    g_pr = [f"{i:02d}" for i in range(1, 32)]
                    m_pr = ["01","02","03","04","05","06","07","08","09","10","11","12"]
                    a_pr = [str(a) for a in range(date.today().year, date.today().year + 3)]
                    pc1, pc2, pc3 = st.columns(3)
                    g_pi = pc1.selectbox("G", g_pr, key="pr_g", label_visibility="collapsed", index=date.today().day - 1)
                    m_pi = pc2.selectbox("M", m_pr, key="pr_m", label_visibility="collapsed", index=date.today().month - 1)
                    a_pi = pc3.selectbox("A", a_pr, key="pr_a", label_visibility="collapsed")
                    data_inizio_pr = f"{g_pi}/{m_pi}/{a_pi}"
                    pr_posologia = st.text_area("Posologia", placeholder="es. 1 cps a colazione per 30 giorni", height=80, key="prescr_pos")
                    pr_note = st.text_input("Note aggiuntive (opzionale)", key="prescr_note")

                    if st.form_submit_button("💾 Aggiungi alla prescrizione", use_container_width=True, type="primary"):
                        if nome_da_usare:
                            df_i_fresh = carica_database(DB_INTEGRATORI, COLS_INTEGR)
                            if nome_da_usare not in df_i_fresh['Nome_Integratore'].astype(str).values:
                                pd.concat([
                                    df_i_fresh,
                                    pd.DataFrame([[nome_da_usare, pr_categoria or "", ""]], columns=COLS_INTEGR)
                                ], ignore_index=True).to_csv(DB_INTEGRATORI, index=False)
                                st.toast(f"💊 '{nome_da_usare}' aggiunto al DB integratori", icon="✅")
                            nuova_riga = pd.DataFrame([[
                                p_r['Codice_Fiscale'], visita_prescr, data_inizio_pr,
                                nome_da_usare, pr_posologia or "", pr_note or ""
                            ]], columns=COLS_PRESCR)
                            df_pr_new = carica_database(DB_PRESCRIZIONI, COLS_PRESCR)
                            pd.concat([df_pr_new, nuova_riga], ignore_index=True).to_csv(DB_PRESCRIZIONI, index=False)
                            st.success(f"✅ **{nome_da_usare}** aggiunto alla prescrizione.")
                            st.rerun()
                        else:
                            st.error("Seleziona un integratore dal menu o scrivine uno nuovo.")

            with col_dx:
                st.markdown(f"<div class='card'><h4 class='card-header-blue'>💊 Prescrizione — Visita del {visita_prescr}</h4></div>", unsafe_allow_html=True)
                if prescr_visita.empty:
                    st.info("Nessun integratore prescritto per questa visita. Aggiungine uno dal form a sinistra.")
                else:
                    for idx_pr, row_pr in prescr_visita.iterrows():
                        with st.container():
                            if st.session_state.confirm_del_prescr == idx_pr:
                                st.warning(f"⚠️ Eliminare **{row_pr['Nome_Integratore']}** dalla prescrizione?")
                                cpr1, cpr2 = st.columns(2)
                                if cpr1.button("✅ Sì, elimina", key=f"conf_si_prescr_{idx_pr}", use_container_width=True, type="primary"):
                                    df_pr_upd = carica_database(DB_PRESCRIZIONI, COLS_PRESCR)
                                    df_pr_upd.drop(idx_pr, errors='ignore').to_csv(DB_PRESCRIZIONI, index=False)
                                    st.session_state.confirm_del_prescr = None
                                    st.rerun()
                                if cpr2.button("❌ Annulla", key=f"conf_no_prescr_{idx_pr}", use_container_width=True):
                                    st.session_state.confirm_del_prescr = None
                                    st.rerun()
                            else:
                                st.markdown(f"""
                                <div style='background:#f8fafc; border-left:4px solid #3498db; border-radius:6px; padding:10px 14px; margin-bottom:10px;'>
                                    <span style='font-size:15px; font-weight:800; color:#2c3e50;'>💊 {row_pr['Nome_Integratore']}</span>
                                    <span style='font-size:11px; color:#7f8c8d; margin-left:10px;'>🗓️ Dal {row_pr['Data_Inizio']}</span>
                                    <div style='font-size:13px; color:#34495e; margin-top:5px;'>{row_pr['Posologia']}</div>
                                    {'<div style="font-size:11px; color:#95a5a6; margin-top:3px;">📝 ' + str(row_pr['Note_Prescrizione']) + '</div>' if str(row_pr.get('Note_Prescrizione','')).strip() not in ('', 'nan') else ''}
                                </div>
                                """, unsafe_allow_html=True)
                                if st.button("🗑️ Rimuovi", key=f"del_pr_{idx_pr}", use_container_width=False):
                                    st.session_state.confirm_del_prescr = idx_pr
                                    st.rerun()

                st.markdown("---")
                st.markdown("**🖨️ Stampa prescrizione per il paziente**")
                if not prescr_visita.empty:
                    pdf_prescr = genera_pdf_prescrizione(p_r, prescr_visita, visita_prescr)
                    pr1, pr2 = st.columns(2)
                    with pr1:
                        st.download_button(
                            "📄 Scarica PDF Prescrizione",
                            pdf_prescr,
                            f"Prescrizione_{p_r['Cognome']}_{str(visita_prescr).replace('/','-')}.pdf",
                            "application/pdf",
                            use_container_width=True,
                            type="primary",
                            key="btn_pdf_prescr"
                        )
                    with pr2:
                        st.components.v1.html(_html_btn_stampa(pdf_prescr, "🖨️ Stampa"), height=40)
                else:
                    st.caption("Aggiungi almeno un integratore per generare il PDF.")
elif st.session_state.m_modulo:
        st.markdown("<div class='card'><h4 class='card-header-blue'>👤 Registrazione Nuovo Paziente</h4></div>", unsafe_allow_html=True)

        # --- SEZIONE ANAGRAFICA (fuori dal form per aggiornamento CF in tempo reale) ---
        st.markdown("##### 👤 Dati Anagrafici")
        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome", key="np_nome")
            cognome = st.text_input("Cognome", key="np_cognome")

            # Data di nascita con selettori
            st.markdown("**Data di Nascita**")
            g_np = [f"{i:02d}" for i in range(1, 32)]
            m_np = ["01","02","03","04","05","06","07","08","09","10","11","12"]
            a_np = [str(a) for a in range(date.today().year - 100, date.today().year + 1)][::-1]
            cnp1, cnp2, cnp3 = st.columns(3)
            g_nasc = cnp1.selectbox("Giorno", g_np, key="np_g", label_visibility="collapsed")
            m_nasc = cnp2.selectbox("Mese", m_np, key="np_m", label_visibility="collapsed")
            a_nasc = cnp3.selectbox("Anno", a_np, key="np_a", label_visibility="collapsed")
            nascita = f"{g_nasc}/{m_nasc}/{a_nasc}"
            st.caption(f"📅 Data selezionata: **{nascita}**")

            luogo = st.text_input("Comune di Nascita", key="np_luogo")
            sesso = st.selectbox("Sesso", ["M", "F"], key="np_sesso")

        with c2:
            # Calcolo CF automatico in tempo reale
            cf_calcolato = ""
            if nome and cognome and luogo and nascita:
                try:
                    cf_calcolato = codicefiscale.encode(
                        lastname=cognome, firstname=nome,
                        gender=sesso, birthdate=nascita, birthplace=luogo
                    )
                except Exception:
                    cf_calcolato = ""

            st.markdown("**Codice Fiscale** (calcolato automaticamente)")
            st.text_input(
                "Codice Fiscale",
                value=cf_calcolato,
                disabled=True,
                key="np_cf_display",
                label_visibility="collapsed",
                help="Compilato automaticamente da Nome, Cognome, Nascita e Comune"
            )
            if cf_calcolato:
                st.caption(f"✅ CF generato: **{cf_calcolato}**")
            else:
                st.caption("⏳ Compila Nome, Cognome, Comune e Data per generare il CF")

            # Override manuale opzionale
            cf_override = st.text_input("Sovrascrittura manuale CF (opzionale)", key="np_cf_override", placeholder="Lascia vuoto per usare quello calcolato").upper()
            cf_in = cf_override if cf_override else cf_calcolato

            indirizzo_val = st.text_input("Indirizzo", key="np_indirizzo")
            cell_val = st.text_input("Cellulare", key="np_cell")
            email_val = st.text_input("Email", key="np_email")

        st.markdown("---")

        with st.form("nuovo_paziente_form"):
            cc1, cc2 = st.columns(2)
            with cc1:
                altezza = st.number_input("Altezza (cm)", min_value=0, value=170)
                peso = st.number_input("Peso attuale (kg)", min_value=0.0, value=None, placeholder="es. 75.5", format="%.1f")
                s_laf = st.selectbox("Livello Attività Fisica (LAF)", lista_laf)
            with cc2:
                addome = st.number_input("Circ. Addome (cm)", value=0.0)
                fianchi = st.number_input("Circ. Fianchi (cm)", value=0.0)
                torace = st.number_input("Circ. Torace (cm)", value=0.0)
                polso = st.number_input("Circ. Polso (cm)", value=0.0)
                s_pt = st.number_input("Peso Target (Obiettivo kg)", value=65.0)

            # ── SEZIONE ANTROPOMETRIA ──
            st.markdown("---")
            antro_np = form_antropometria("np")

            analisi = st.text_area("Analisi Cliniche")
            farmaci = st.text_area("Farmaci")
            note = st.text_area("Note iniziali")

            col_save, col_cancel = st.columns(2)
            submit = col_save.form_submit_button("💾 CREA PAZIENTE E SALVA VISITA", use_container_width=True, type="primary")
            cancel = col_cancel.form_submit_button("❌ ANNULLA", use_container_width=True)

            if submit:
                # Recupera i valori anagrafica dallo session_state
                nome_s = st.session_state.get("np_nome", "")
                cognome_s = st.session_state.get("np_cognome", "")
                luogo_s = st.session_state.get("np_luogo", "")
                sesso_s = st.session_state.get("np_sesso", "M")
                g_s = st.session_state.get("np_g", "01")
                m_s = st.session_state.get("np_m", "01")
                a_s = st.session_state.get("np_a", "1990")
                nascita_s = f"{g_s}/{m_s}/{a_s}"
                cf_ov_s = st.session_state.get("np_cf_override", "").upper()
                indirizzo_s = st.session_state.get("np_indirizzo", "")
                cell_s = st.session_state.get("np_cell", "")
                email_s = st.session_state.get("np_email", "")

                if not cf_ov_s:
                    try:
                        cf_ov_s = codicefiscale.encode(
                            lastname=cognome_s, firstname=nome_s,
                            gender=sesso_s, birthdate=nascita_s, birthplace=luogo_s
                        )
                    except Exception:
                        cf_ov_s = "ERRORE_CF"

                if cf_ov_s == "ERRORE_CF":
                    st.error("Impossibile calcolare il Codice Fiscale. Verifica Nome, Cognome, Data di nascita (GG/MM/AAAA) e Comune di nascita.")
                elif nome_s and cognome_s and nascita_s:
                    peso_val = float(peso) if peso is not None else 0.0
                    bmi = round(peso_val / ((altezza/100)**2), 2) if altezza > 0 and peso_val > 0 else 0.0
                    riga = [
                        f"{date.today().day:02d}/{date.today().month:02d}/{date.today().year}",
                        nome_s, cognome_s, cf_ov_s, nascita_s, luogo_s, indirizzo_s, sesso_s,
                        cell_s, email_s, altezza, peso_val, bmi, addome, fianchi,
                        torace, polso, analisi, farmaci, note, s_laf, s_pt,
                        antro_np.get('Circ_Polso_Dx', 0.0), antro_np.get('Circ_Polso_Sx', 0.0),
                        antro_np.get('Circ_Avambraccio_Dx', 0.0), antro_np.get('Circ_Avambraccio_Sx', 0.0),
                        antro_np.get('Circ_Braccio_Dx', 0.0), antro_np.get('Circ_Braccio_Sx', 0.0),
                        antro_np.get('Circ_Spalle', 0.0), antro_np.get('Circ_Torace_Ant', 0.0),
                        antro_np.get('Circ_Vita', 0.0), antro_np.get('Circ_Addome_Ant', 0.0),
                        antro_np.get('Circ_Fianchi_Ant', 0.0),
                        antro_np.get('Circ_Coscia_Prox_Dx', 0.0), antro_np.get('Circ_Coscia_Prox_Sx', 0.0),
                        antro_np.get('Circ_Coscia_Med_Dx', 0.0), antro_np.get('Circ_Coscia_Med_Sx', 0.0),
                        antro_np.get('Circ_Coscia_Dist_Dx', 0.0), antro_np.get('Circ_Coscia_Dist_Sx', 0.0),
                        antro_np.get('Circ_Polpaccio_Dx', 0.0), antro_np.get('Circ_Polpaccio_Sx', 0.0),
                        antro_np.get('Circ_Caviglia_Dx', 0.0), antro_np.get('Circ_Caviglia_Sx', 0.0),
                        antro_np.get('Plica_Avambraccio', 0.0), antro_np.get('Plica_Bicipitale', 0.0),
                        antro_np.get('Plica_Tricipitale', 0.0), antro_np.get('Plica_Ascellare', 0.0),
                        antro_np.get('Plica_Pettorale', 0.0), antro_np.get('Plica_Sottoscapolare', 0.0),
                        antro_np.get('Plica_Addominale', 0.0), antro_np.get('Plica_Soprailiaca', 0.0),
                        antro_np.get('Plica_Coscia_Med', 0.0), antro_np.get('Plica_Soprapatellare', 0.0),
                        antro_np.get('Plica_Polpaccio_Med', 0.0), antro_np.get('Plica_Sopraspinale', 0.0),
                        antro_np.get('Diam_Polso', 0.0), antro_np.get('Diam_Gomito', 0.0),
                        antro_np.get('Diam_Biacromiale', 0.0), antro_np.get('Diam_Toracico', 0.0),
                        antro_np.get('Diam_Bicrestale', 0.0), antro_np.get('Diam_Addominale_Sag', 0.0),
                        antro_np.get('Diam_Bitrocanterio', 0.0), antro_np.get('Diam_Ginocchio', 0.0),
                        antro_np.get('Diam_Caviglia', 0.0),
                        antro_np.get('Note_Antropometria', ""),
                    ]
                    new_row = pd.DataFrame([riga], columns=COLS_PAZ)
                    df_p = pd.concat([df_p, new_row], ignore_index=True)
                    df_p.to_csv(DB_PAZIENTI, index=False)
                    st.session_state.p_attivo = df_p.iloc[-1].to_dict()
                    st.success("Paziente creato con successo!")
                    st.rerun()
                else:
                    st.error("Nome, Cognome e Data di Nascita sono obbligatori!")

            if cancel:
                st.session_state.m_modulo = False
                st.rerun()

# CASO 3: SCHERMATA HOME (non mostrata quando si è in Utility)
else:
    if not st.session_state.show_utility:
        st.markdown("""
        <div class="card" style="margin-bottom: 20px;">
        <div style="text-align:center; padding: 20px 0 12px 0;">
            <div style="font-size:32px; margin-bottom:6px;">👨‍⚕️</div>
            <div style="font-size:22px; font-weight:900; color:#1a2332; letter-spacing:-0.5px;">Gestione Studio Nutrizionale</div>
            <div style="font-size:12px; color:#64748b; margin-top:4px; font-weight:500;">VLEKT PRO — Pazienti recenti</div>
        </div>
        </div>
        """, unsafe_allow_html=True)

    if not st.session_state.show_utility:
        if not df_p.empty:
            st.markdown("<div class='card' style='padding: 18px 20px;'>", unsafe_allow_html=True)
            display_df = df_p.drop_duplicates('Codice_Fiscale', keep='last').copy()
            if 'Data_Visita' in display_df.columns:
                display_df['DT_sort'] = pd.to_datetime(display_df['Data_Visita'], format='%d/%m/%Y', errors='coerce')
                display_df = display_df.sort_values('DT_sort', ascending=False).drop(columns=['DT_sort'])

            # Proporzioni colonne — fisse e usate sia per header che per righe
            COL_W = [0.25, 2.6, 1.3, 0.8, 0.7]

            # ── INTESTAZIONE ──
            h_btn, h_nome, h_data, h_peso, h_bmi = st.columns(COL_W)
            h_btn.markdown("")
            h_nome.markdown("<span style='font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.6px;'>Paziente</span>", unsafe_allow_html=True)
            h_data.markdown("<span style='font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.6px;'>Ultima visita</span>", unsafe_allow_html=True)
            h_peso.markdown("<span style='font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.6px;'>Peso</span>", unsafe_allow_html=True)
            h_bmi.markdown("<span style='font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.6px;'>BMI</span>", unsafe_allow_html=True)
            st.markdown("<hr style='margin:4px 0 6px 0; border-color:#e5e7eb;'>", unsafe_allow_html=True)

            # ── RIGHE PAZIENTI ──
            for i, row in display_df.head(15).iterrows():
                bmi_val = to_f(row.get('BMI', 0))
                bmi_label, bmi_color = calcola_stato_bmi(bmi_val) if bmi_val > 0 else ('—', '#9ca3af')

                c_btn, c_nome, c_data, c_peso, c_bmi = st.columns(COL_W)

                if c_btn.button("↗", key=f"open_home_{i}",
                                help=f"Apri {row.get('Cognome','')} {row.get('Nome','')}",
                                use_container_width=True):
                    match = df_p[df_p['Codice_Fiscale'] == row['Codice_Fiscale']]
                    if not match.empty:
                        st.session_state.p_attivo = match.iloc[-1].to_dict()
                        st.session_state.m_modulo = False
                        st.session_state.idx_mod = None
                        st.session_state.edit_anagrafica = False
                        st.session_state.confirm_delete_paz = False
                        st.session_state.show_db_alimenti = False
                        st.session_state.show_db_integratori = False
                        st.session_state.show_db_proteine = False
                        st.rerun()

                c_nome.markdown(
                    f"<div style='line-height:1.3; padding:4px 0;'>"
                    f"<div style='font-size:14px;font-weight:700;color:#111827;'>{row.get('Cognome','')} {row.get('Nome','')}</div>"
                    f"<div style='font-size:10px;color:#b0b8c4;margin-top:1px;'>{row.get('Codice_Fiscale','')}</div>"
                    f"</div>", unsafe_allow_html=True)

                c_data.markdown(
                    f"<div style='padding:4px 0;font-size:13px;color:#6b7280;'>{row.get('Data_Visita','—')}</div>",
                    unsafe_allow_html=True)

                c_peso.markdown(
                    f"<div style='padding:4px 0;font-size:13px;font-weight:600;color:#374151;'>"
                    f"{row.get('Peso','—')} <span style='font-size:11px;font-weight:400;color:#9ca3af;'>kg</span></div>",
                    unsafe_allow_html=True)

                c_bmi.markdown(
                    f"<div style='padding:4px 0;'>"
                    f"<span style='font-size:13px;font-weight:800;color:{bmi_color};'>{row.get('BMI','—')}</span>"
                    f"<div style='font-size:9px;color:{bmi_color};opacity:0.8;'>{bmi_label}</div>"
                    f"</div>", unsafe_allow_html=True)

                st.markdown("<div style='border-bottom:1px solid #f3f4f6; margin-bottom:2px;'></div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("👈 Nessun paziente nel database. Utilizza la barra laterale per crearne uno nuovo.")