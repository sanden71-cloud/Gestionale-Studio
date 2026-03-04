# --- Funzioni di utilità (VLEKT PRO) ---
from datetime import date
from urllib.request import urlopen
from urllib.error import URLError, HTTPError


def to_f(value):
    try:
        if value == "" or value is None or str(value).strip() == "":
            return 0.0
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0


def safe(val, default="-"):
    v = str(val).strip()
    return v if v not in ("", "nan", "None") else default


def calcola_eta(data_nascita_str):
    try:
        g, m, a = map(int, data_nascita_str.split("/"))
        nascita = date(a, m, g)
        oggi = date.today()
        return oggi.year - nascita.year - ((oggi.month, oggi.day) < (nascita.month, nascita.day))
    except Exception:
        return 30


def calcola_eta_anni_mesi(data_nascita_str):
    try:
        g, m, a = map(int, data_nascita_str.split("/"))
        nascita = date(a, m, g)
        oggi = date.today()
        anni = oggi.year - nascita.year - ((oggi.month, oggi.day) < (nascita.month, nascita.day))
        mesi = (oggi.month - nascita.month) + (oggi.day - nascita.day) / 31.0
        if mesi < 0:
            anni -= 1
            mesi += 12
        mesi = int(round(mesi)) % 12
        return anni, mesi
    except Exception:
        return 30, 0


def calcola_info_visite(st_p_ord):
    if st_p_ord is None or st_p_ord.empty:
        return None, 0, 0, 0
    n_visite = len(st_p_ord)
    ultima_str = st_p_ord.iloc[-1]["Data_Visita"]
    try:
        gg, mm, aa = map(int, ultima_str.split("/"))
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
                g, m, a = map(int, str(r["Data_Visita"]).split("/"))
                date_visite.append(date(a, m, g))
            except Exception:
                pass
        date_visite.sort()
        diff_giorni = [(date_visite[i + 1] - date_visite[i]).days for i in range(len(date_visite) - 1)]
        intervallo_medio = int(round(sum(diff_giorni) / len(diff_giorni))) if diff_giorni else 0
    return ultima_str, giorni_da_ultima, n_visite, intervallo_medio


def _norm_data_visita(s):
    try:
        s = str(s).strip()
        if not s or s == "nan":
            return ""
        if "-" in s and "/" not in s:
            parts = s.split("-")
            if len(parts) == 3:
                a, m, g = parts[0], parts[1], parts[2]
                return f"{int(g):02d}/{int(m):02d}/{int(a)}"
        parts = s.split("/")
        if len(parts) == 3:
            g, m, a = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{g:02d}/{m:02d}/{a}"
    except Exception:
        pass
    return str(s).strip()


def calcola_stato_bmi(bmi):
    if bmi < 18.5:
        return "Sottopeso", "#3498db"
    elif bmi < 25.0:
        return "Normopeso", "#2ecc71"
    elif bmi < 30.0:
        return "Sovrappeso", "#f1c40f"
    elif bmi < 35.0:
        return "Obesità 1° Grado", "#e67e22"
    elif bmi < 40.0:
        return "Obesità 2° Grado", "#e74c3c"
    else:
        return "Obesità 3° Grado", "#8e44ad"


def calcola_bmr(peso, altezza, eta, sesso):
    if sesso == "M":
        return (10 * peso) + (6.25 * altezza) - (5 * eta) + 5
    return (10 * peso) + (6.25 * altezza) - (5 * eta) - 161


def _v(d, key, default=0.0):
    if d is None:
        return default
    try:
        if isinstance(d, dict):
            val = d.get(key, default)
        else:
            val = d[key] if key in d.index else default
        r = to_f(val)
        return r if r != 0.0 else default
    except Exception:
        return default


def colora_pasti(row):
    pasto = row["Pasto"]
    if pasto == "Colazione":
        color = "#FFF3CD"
    elif pasto in ("Spuntino Mattina", "Spuntino/Merenda"):
        color = "#FFE6CC"
    elif pasto == "Pranzo":
        color = "#D4EDDA"
    elif pasto == "Merenda":
        color = "#D1ECF1"
    elif pasto == "Cena":
        color = "#E2E3E5"
    elif pasto == "Dopo Cena":
        color = "#E8DAEF"
    else:
        color = "#FFFFFF"
    return [f"background-color: {color}"] * len(row)


def parse_version(ver_str):
    """Converte una stringa versione '1.2.3' in tupla (1, 2, 3). Accetta anche '1.0' -> (1, 0, 0)."""
    if not ver_str or not str(ver_str).strip():
        return (0, 0, 0)
    parts = str(ver_str).strip().split(".")
    out = []
    for i in range(3):
        try:
            out.append(int(parts[i]) if i < len(parts) else 0)
        except (ValueError, IndexError):
            out.append(0)
    return tuple(out)


def check_update_available(current_version, url, timeout_sec=5):
    """
    Controlla se esiste una versione più recente rispetto a current_version.
    url deve restituire solo il numero di versione (es. '1.1.0') in testo piano.
    Ritorna: ('new', '1.1.0') se disponibile aggiornamento, ('current', None) se già aggiornato, ('error', messaggio) in caso di errore.
    """
    if not url or not str(url).strip():
        return "error", "URL non configurato (CHECK_UPDATE_URL in config.py)."
    try:
        with urlopen(str(url).strip(), timeout=timeout_sec) as resp:
            remote = resp.read().decode("utf-8", errors="ignore").strip()
    except HTTPError as e:
        if e.code == 404:
            return "error", (
                "404 Not Found: l’URL non è raggiungibile. Verifica che il repo sia su GitHub, "
                "che il branch in config.py sia corretto (main o master) e che latest_version.txt sia nella root e sia stato caricato (push)."
            )
        return "error", str(e) if str(e) else "Errore di connessione."
    except (URLError, OSError) as e:
        return "error", str(e) if str(e) else "Errore di connessione."
    remote_ver = parse_version(remote)
    current_ver = parse_version(current_version)
    if remote_ver > current_ver:
        return "new", remote
    return "current", None
