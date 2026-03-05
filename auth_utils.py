# -*- coding: utf-8 -*-
"""
Modulo autenticazione e gestione utenti per VLEKT PRO.
Gestisce login, utenti, database per utente, protezione copie.
Con VLEKT_SECRET_KEY impostata: utenti e config sono salvati cifrati (users.enc, config.enc)
e possono essere committati su Git per sincronizzare locale ↔ deploy.
"""
from __future__ import annotations
import os
import json
import hashlib
import secrets
import unicodedata
import base64
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
AUTH_DIR = APP_DIR / "auth"
DATA_DIR = APP_DIR / "data"
CONFIG_FILE = AUTH_DIR / "config.json"
CONFIG_ENC = AUTH_DIR / "config.enc"
USERS_ENC = AUTH_DIR / "users.enc"
LICENSES_FILE = AUTH_DIR / "licenses.json"

# Chiave per sincronizzazione sicura locale ↔ deploy (crittografia utenti e config)
SECRET_KEY_ENV = "VLEKT_SECRET_KEY"
# Chiave/licenza per protezione copie (impostare in config o variabile d'ambiente)
LICENSE_ENV = "VLEKT_LICENSE_KEY"


def _sync_key_set() -> bool:
    """True se è impostata la chiave per sync cifrato (utenti e config in .enc)."""
    return bool((os.environ.get(SECRET_KEY_ENV) or "").strip())


def _get_fernet():
    """Restituisce istanza Fernet da VLEKT_SECRET_KEY (passphrase derivata con PBKDF2), o None."""
    key_str = (os.environ.get(SECRET_KEY_ENV) or "").strip()
    if not key_str:
        return None
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        salt = b"vlekt_auth_sync_v1"
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        key_bytes = kdf.derive(key_str.encode("utf-8"))
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)
    except Exception:
        return None


def _get_users_file_path() -> Path:
    """Percorso del file utenti: se sync attivo → users.enc, altrimenti users.json (modulo o cwd)."""
    if _sync_key_set():
        return USERS_ENC
    default = AUTH_DIR / "users.json"
    if default.exists():
        return default
    cwd_auth = Path.cwd() / "auth" / "users.json"
    if cwd_auth.exists():
        return cwd_auth
    return default


def get_users_file_debug_info() -> tuple[str, int]:
    """Per debug: ritorna (percorso_file_utenti, num_utenti)."""
    p = _get_users_file_path()
    data = _load_users()
    return str(p), len(data.get("users", []))


def _ensure_dirs():
    """Crea le cartelle necessarie se non esistono."""
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _hash_password(password: str) -> str:
    """Hash sicuro della password con salt."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${pwd_hash.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """Verifica password contro hash memorizzato."""
    try:
        salt, pwd_hash = stored.split("$")
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return computed.hex() == pwd_hash
    except Exception:
        return False


def _load_users() -> dict:
    """Carica il file utenti (da .enc se sync attivo, altrimenti da .json)."""
    _ensure_dirs()
    if _sync_key_set():
        fernet = _get_fernet()
        if fernet and USERS_ENC.exists():
            try:
                with open(USERS_ENC, "rb") as f:
                    dec = fernet.decrypt(f.read())
                return json.loads(dec.decode("utf-8"))
            except Exception:
                pass
        # Migrazione: se esiste users.json ma non users.enc, cifra e salva .enc
        legacy = AUTH_DIR / "users.json"
        if fernet and legacy.exists():
            try:
                with open(legacy, "r", encoding="utf-8") as f:
                    data = json.load(f)
                raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
                with open(USERS_ENC, "wb") as f:
                    f.write(fernet.encrypt(raw))
                return data
            except Exception:
                pass
        if USERS_ENC.exists():
            return {"users": []}
        # Chiave impostata ma file .enc assente o fernet non disponibile: prova legacy users.json
    users_file = _get_users_file_path()
    if _sync_key_set():
        legacy = AUTH_DIR / "users.json"
        if legacy.exists():
            users_file = legacy
    if not users_file.exists():
        return {"users": []}
    try:
        with open(users_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": []}


def _save_users(data: dict) -> bool:
    """Salva il file utenti (in .enc cifrato se sync attivo, altrimenti in .json)."""
    _ensure_dirs()
    if _sync_key_set():
        fernet = _get_fernet()
        if fernet:
            try:
                raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
                with open(USERS_ENC, "wb") as f:
                    f.write(fernet.encrypt(raw))
                return True
            except Exception:
                return False
    users_file = _get_users_file_path()
    users_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def get_user_data_dir(username: str) -> str:
    """Restituisce il percorso della cartella dati per l'utente."""
    _ensure_dirs()
    # Sanitizza username per usarlo come nome cartella
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in username)
    user_dir = DATA_DIR / safe
    user_dir.mkdir(parents=True, exist_ok=True)
    return str(user_dir)


def verify_login(username: str, password: str) -> tuple[bool, object]:
    """
    Verifica credenziali. Ritorna (ok, msg_errore).
    Se ok=True, msg_errore è None.
    Se non esiste nessun utente e si tenta login con admin/Admin123!, crea l'admin e riprova (fallback primo accesso).
    """
    data = _load_users()
    users = data.get("users", [])
    username = (username or "").strip().lower()
    password = (password or "").strip()
    # Fallback: se non c'è ancora nessun utente e tentativo admin/Admin123!, crea admin e riprova
    if not users and username == "admin" and password == "Admin123!":
        ensure_admin_exists()
        data = _load_users()
        users = data.get("users", [])
    for u in users:
        if u.get("username", "").lower() == username:
            if not u.get("attivo", True):
                return False, "Utente disattivato. Contatta l'amministratore."
            if _verify_password(password, u.get("password_hash", "")):
                return True, None
            return False, "Password non corretta."
    return False, "Utente non trovato."


def is_admin(username: str) -> bool:
    """Verifica se l'utente è amministratore."""
    data = _load_users()
    username = username.strip().lower()
    for u in data.get("users", []):
        if u.get("username", "").lower() == username:
            return bool(u.get("is_admin", False))
    return False


def get_all_users():
    """Restituisce la lista di tutti gli utenti (per area admin)."""
    data = _load_users()
    return data.get("users", [])


def get_user_info(username: str) -> dict | None:
    """Restituisce il dict utente per username, o None."""
    for u in get_all_users():
        if (u.get("username") or "").lower() == (username or "").lower():
            return u
    return None


def toggle_user_active(username: str) -> bool:
    """Attiva/disattiva un utente. Ritorna True se OK."""
    data = _load_users()
    for u in data["users"]:
        if u.get("username", "").lower() == username:
            u["attivo"] = not u.get("attivo", True)
            return _save_users(data)
    return False


def create_user(username: str, password: str, is_admin_user: bool = False, nome: str = "", cognome: str = "", attivo: bool = False, email: str = "") -> tuple[bool, str]:
    """
    Crea un nuovo utente. Ritorna (ok, msg).
    attivo=False: l'utente non può accedere finché un amministratore non lo attiva da Utility.
    email: opzionale, usato per il recupero password.
    Non permette di creare un secondo admin.
    """
    data = _load_users()
    username_clean = username.strip().lower()
    if not username_clean:
        return False, "Username non valido."
    if len(password) < 6:
        return False, "La password deve essere di almeno 6 caratteri."

    for u in data["users"]:
        if u.get("username", "").lower() == username_clean:
            return False, "Utente già esistente."
        if is_admin_user and u.get("is_admin"):
            return False, "Esiste già un amministratore. Non è possibile creare un secondo admin."

    user_dir = get_user_data_dir(username_clean)
    data["users"].append({
        "username": username_clean,
        "nome": (nome or "").strip(),
        "cognome": (cognome or "").strip(),
        "email": (email or "").strip().lower(),
        "password_hash": _hash_password(password),
        "attivo": attivo,
        "is_admin": is_admin_user,
        "created_at": str(__import__("datetime").datetime.now().isoformat()),
        "must_change_password": True,
    })
    if _save_users(data):
        return True, "Utente creato."
    return False, "Errore durante il salvataggio."


def init_user_data_folder(user_dir: str, files_cols):
    """Inizializza la cartella dati dell'utente con CSV vuoti. files_cols = [(filename, [colonne]), ...]"""
    import pandas as pd
    for fname, cols in files_cols:
        path = Path(user_dir) / fname
        if not path.exists():
            pd.DataFrame(columns=cols).to_csv(path, index=False)


def change_password(username: str, new_password: str, set_must_change_on_next_login: bool = False) -> tuple[bool, str]:
    """Cambia la password di un utente. Se set_must_change_on_next_login=True (admin reset), l'utente dovrà cambiarla al primo accesso."""
    data = _load_users()
    username = username.strip().lower()
    if len(new_password) < 6:
        return False, "La password deve essere di almeno 6 caratteri."
    for u in data["users"]:
        if u.get("username", "").lower() == username:
            u["password_hash"] = _hash_password(new_password)
            u["must_change_password"] = bool(set_must_change_on_next_login)
            return _save_users(data), "Password aggiornata."
    return False, "Utente non trovato."


def get_user_must_change_password(username: str) -> bool:
    """True se l'utente deve cambiare la password al primo accesso (fornita da admin o recupero)."""
    u = get_user_info(username)
    return bool(u and u.get("must_change_password"))


def reset_admin_password_to_default() -> tuple[bool, str]:
    """Reimposta la password dell'utente admin a Admin123!. Consentito solo con VLEKT_DEV=1 (sviluppo)."""
    if os.environ.get("VLEKT_DEV") != "1":
        return False, "Operazione consentita solo in ambiente di sviluppo (VLEKT_DEV=1)."
    data = _load_users()
    for u in data.get("users", []):
        if u.get("is_admin"):
            u["password_hash"] = _hash_password("Admin123!")
            if _save_users(data):
                return True, "Password admin reimpostata a Admin123!. Riprova ad accedere."
            return False, "Impossibile salvare."
    return False, "Utente admin non trovato."


def _normalize_key(s: str) -> str:
    """Normalizza una stringa per il confronto: strip, lowercase, NFKC (evita caratteri invisibili)."""
    if not s:
        return ""
    return unicodedata.normalize("NFKC", str(s).strip().lower())


def find_user_by_email_or_username(key: str):
    """Cerca un utente per email o username. Ritorna il dict utente o None."""
    key_norm = _normalize_key(key)
    if not key_norm:
        return None
    data = _load_users()
    users_list = data.get("users", [])
    if os.environ.get("VLEKT_DEV") == "1":
        _uf = _get_users_file_path()
        print(f"[VLEKT_DEV] Recupero password: file utenti={_uf}, esistente={_uf.exists()}, num_utenti={len(users_list)}")
        for u in users_list:
            print(f"  - username={u.get('username')!r} email={u.get('email')!r}")
    for u in users_list:
        uname = _normalize_key(u.get("username") or "")
        uemail = _normalize_key(u.get("email") or "")
        if uname == key_norm or uemail == key_norm:
            return u
        # Se hanno inserito un'email, prova anche a matchare lo username con la parte prima della @
        if "@" in key_norm and uname == key_norm.split("@")[0]:
            return u
    return None


def _send_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    """
    Invia email tramite SMTP. Config in auth/config.json: smtp_host, smtp_port, smtp_user, smtp_password, smtp_use_tls, from_email.
    Ritorna (ok, messaggio_errore). Se ok=True, messaggio_errore è vuoto.
    """
    to = (to or "").strip()
    if not to or "@" not in to:
        return False, "Indirizzo email non valido."
    cfg = get_config()
    host = (cfg.get("smtp_host") or os.environ.get("VLEKT_SMTP_HOST") or "").strip()
    port = int(cfg.get("smtp_port") or os.environ.get("VLEKT_SMTP_PORT") or 587)
    user = (cfg.get("smtp_user") or os.environ.get("VLEKT_SMTP_USER") or "").strip()
    password = cfg.get("smtp_password") or os.environ.get("VLEKT_SMTP_PASSWORD") or ""
    use_tls = cfg.get("smtp_use_tls", True)
    from_addr = (cfg.get("from_email") or user or "noreply@vlekt.local").strip()
    from_name = (cfg.get("from_name") or "").strip()
    if not host or not user or not password:
        return False, "SMTP non configurato: inserisci host, utente e password in Utility > Configurazione (licenza e SMTP)."
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        if from_name:
            from email.utils import formataddr
            msg["From"] = formataddr((from_name, from_addr))
        else:
            msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(host, port) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to], msg.as_string())
        return True, ""
    except Exception as e:
        err = str(e).strip() or type(e).__name__
        if os.environ.get("VLEKT_DEV") == "1":
            import traceback
            traceback.print_exc()
        return False, err


def request_password_reset(email_or_username: str) -> tuple[bool, str, str | None]:
    """
    Recupero password: genera una password temporanea, la imposta per l'utente e (se possibile) invia email.
    Ritorna (ok, messaggio_da_mostrare, password_temporanea).
    Se l'email non è configurata o l'invio fallisce, password_temporanea è valorizzata così la si può mostrare a schermo.
    """
    user = find_user_by_email_or_username(email_or_username)
    if not user:
        return False, "Nessun utente trovato. Prova con lo username oppure verifica che l'email sia stata impostata dall'amministratore per il tuo account.", None
    if not user.get("attivo", True):
        return False, "Utente disattivato. Contatta l'amministratore.", None
    temp_pass = secrets.token_urlsafe(10)  # es. 10 caratteri url-safe
    username = user.get("username", "")
    data = _load_users()
    for u in data["users"]:
        if u.get("username", "").lower() == username.lower():
            u["password_hash"] = _hash_password(temp_pass)
            u["must_change_password"] = True
            if not _save_users(data):
                return False, "Errore durante il salvataggio.", None
            break
    email_addr = (user.get("email") or "").strip()
    if email_addr and "@" in email_addr:
        subject = "VLEKT PRO - Recupero password"
        body = f"""Ciao,

È stata richiesta una nuova password per il tuo account VLEKT PRO.

Username: {username}
Password temporanea: {temp_pass}

IMPORTANTE: Cambia la password al primo accesso da Utility > Cambia la tua password (per sicurezza).

Se non hai richiesto tu questo recupero, contatta l'amministratore.
"""
        sent, send_err = _send_email(email_addr, subject, body)
        if sent:
            return True, "Controlla la tua email: ti abbiamo inviato una password temporanea. Accedi e cambia la password al primo accesso da Utility.", None
        # Invio fallito: messaggio con motivo e password da mostrare
        msg_base = "Password temporanea generata. Usala per accedere e cambia la password al primo accesso da Utility."
        if send_err:
            msg_base = f"L'email non è stata inviata: {send_err}. " + msg_base
        return True, msg_base, temp_pass
    # Nessuna email sull'utente o invio non tentato
    return True, "Password temporanea generata. Usala per accedere e cambia la password al primo accesso da Utility.", temp_pass


def set_user_email(username: str, email: str) -> tuple[bool, str]:
    """Imposta o aggiorna l'email di un utente (per recupero password)."""
    data = _load_users()
    username = username.strip().lower()
    email = (email or "").strip().lower()
    for u in data["users"]:
        if u.get("username", "").lower() == username:
            u["email"] = email
            return _save_users(data), "Email aggiornata."
    return False, "Utente non trovato."


def ensure_admin_exists():
    """Crea l'utente admin con password predefinita se non esiste."""
    _ensure_dirs()
    data = _load_users()
    if "users" not in data:
        data["users"] = []
    has_admin = any(u.get("is_admin") for u in data["users"])
    if not has_admin:
        default_pwd = "Admin123!"  # DA CAMBIARE al primo accesso
        data["users"].insert(0, {
            "username": "admin",
            "email": "",
            "password_hash": _hash_password(default_pwd),
            "attivo": True,
            "is_admin": True,
            "created_at": str(__import__("datetime").datetime.now().isoformat()),
        })
        ok = _save_users(data)
        if not ok:
            # Fallback: riprova dopo aver ricreato le cartelle
            _ensure_dirs()
            ok = _save_users(data)
        get_user_data_dir("admin")


def _license_signing_secret() -> bytes:
    """Segreto per firma HMAC delle licenze (derivato da VLEKT_SECRET_KEY o valore di default)."""
    key_str = (os.environ.get(SECRET_KEY_ENV) or "").strip()
    if key_str:
        return hashlib.sha256(f"vlekt_license_v1_{key_str}".encode()).digest()
    return hashlib.sha256(b"vlekt_license_default_secret").digest()


def _load_licenses() -> dict:
    """Carica auth/licenses.json."""
    _ensure_dirs()
    if not LICENSES_FILE.exists():
        return {"licenses": []}
    try:
        with open(LICENSES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"licenses": []}


def _save_licenses(data: dict) -> bool:
    """Salva auth/licenses.json."""
    _ensure_dirs()
    try:
        with open(LICENSES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def generate_license(expires_at: str | None = None, notes: str = "") -> str:
    """
    Genera una chiave licenza univoca. Se expires_at=None, licenza senza scadenza.
    expires_at formato YYYY-MM-DD. Salva nel database licenze. Ritorna la chiave da dare all'utente.
    """
    import uuid
    from datetime import datetime
    lid = str(uuid.uuid4())
    exp = "NONE"
    exp_date_str = None
    if expires_at and (expires_at or "").strip():
        s = (expires_at or "").strip()
        if len(s) == 10:
            try:
                datetime.strptime(s, "%Y-%m-%d")
                exp = s.replace("-", "")  # YYYYMMDD
                exp_date_str = s
            except ValueError:
                pass
    payload = f"{lid}|{exp}"
    sig = hashlib.pbkdf2_hmac("sha256", payload.encode(), _license_signing_secret(), 10000)[:12]
    key = f"VLEKT-{lid}-{exp}-{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"
    data = _load_licenses()
    data.setdefault("licenses", []).append({
        "key": key,
        "expires_at": exp_date_str,
        "created_at": str(datetime.now().isoformat()),
        "notes": (notes or "").strip(),
    })
    _save_licenses(data)
    return key


def validate_license(key: str) -> tuple[bool, str | None, str]:
    """
    Valida una chiave licenza. Ritorna (ok, expires_at, msg).
    ok=True: licenza valida; expires_at è la data scadenza (YYYY-MM-DD) o None se perpetua; msg descrizione per utente.
    ok=False: msg descrive l'errore.
    """
    from datetime import datetime
    key = (key or "").strip()
    if not key or len(key) < 20:
        return False, None, "Chiave licenza non valida."
    # Formato nuovo: VLEKT-uuid-expires-sig
    if key.startswith("VLEKT-"):
        parts = key.split("-")
        if len(parts) != 4:
            return False, None, "Formato licenza non valido."
        lid, exp, sig_b64 = parts[1], parts[2], parts[3]
        sig_b64_pad = sig_b64 + "=" * (4 - len(sig_b64) % 4) if len(sig_b64) % 4 else sig_b64
        try:
            sig = base64.urlsafe_b64decode(sig_b64_pad)
        except Exception:
            return False, None, "Chiave licenza non valida."
        payload = f"{lid}|{exp}"
        expected = hashlib.pbkdf2_hmac("sha256", payload.encode(), _license_signing_secret(), 10000)[:12]
        if sig != expected:
            return False, None, "Chiave licenza non valida."
        if exp == "NONE":
            return True, None, "Licenza senza scadenza."
        if len(exp) != 8:
            return False, None, "Formato scadenza non valido."
        exp_date = f"{exp[:4]}-{exp[4:6]}-{exp[6:8]}"
        try:
            exp_dt = datetime.strptime(exp_date, "%Y-%m-%d")
        except ValueError:
            return False, None, "Data scadenza non valida."
        if datetime.now().date() > exp_dt.date():
            return False, None, f"Licenza scaduta il {exp_date}."
        return True, exp_date, f"Licenza valida fino al {exp_date}."
    # Legacy: chiave semplice (>= 8 caratteri)
    if len(key) >= 8:
        return True, None, "Licenza valida (formato precedente)."
    return False, None, "Chiave licenza non valida."


def get_license_info() -> tuple[bool, str | None, str]:
    """
    Info sulla licenza attuale (da config o env). Ritorna (ok, expires_at, msg).
    Per mostrare all'utente: "Licenza scade il 31/12/2025" o "Licenza senza scadenza".
    """
    key = (os.environ.get(LICENSE_ENV) or "").strip()
    if not key:
        cfg = get_config()
        key = (cfg.get("license_key") or "").strip()
    if not key:
        return False, None, ""
    ok, expires_at, msg = validate_license(key)
    return ok, expires_at, msg


def get_all_licenses() -> list:
    """Restituisce tutte le licenze generate (per area admin)."""
    data = _load_licenses()
    return data.get("licenses", [])


def check_license() -> tuple[bool, str]:
    """
    Verifica la licenza/protezione copie.
    Ritorna (ok, msg). Se ok=False, l'app non dovrebbe funzionare.
    """
    # Controllo 1: VLEKT_DEV=1 = sviluppo locale, salta controllo
    if os.environ.get("VLEKT_DEV") == "1":
        return True, ""

    # Controllo 2: chiave licenza (da env o config)
    key = (os.environ.get(LICENSE_ENV) or "").strip()
    if not key:
        cfg = get_config()
        key = (cfg.get("license_key") or "").strip()
    if key:
        ok, _, msg = validate_license(key)
        if ok:
            return True, ""
        return False, msg or "Software non autorizzato. Contatta LINEADICIOTTO per la licenza."

    return False, "Software non autorizzato. Contatta LINEADICIOTTO per la licenza."


def get_config() -> dict:
    """Legge config (da config.enc se sync attivo, altrimenti config.json). Ritorna dict con license_key e SMTP."""
    _ensure_dirs()
    defaults = {
        "license_key": "",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
        "smtp_use_tls": True,
        "from_email": "",
        "from_name": "",
    }
    if _sync_key_set():
        fernet = _get_fernet()
        if fernet and CONFIG_ENC.exists():
            try:
                with open(CONFIG_ENC, "rb") as f:
                    dec = fernet.decrypt(f.read())
                cfg = json.loads(dec.decode("utf-8"))
                for k in defaults:
                    if k not in cfg:
                        cfg[k] = defaults[k]
                return cfg
            except Exception:
                pass
        # Migrazione: config.json → config.enc
        if fernet and CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                for k in defaults:
                    if k not in cfg:
                        cfg[k] = defaults[k]
                raw = json.dumps({k: cfg.get(k) for k in defaults}, ensure_ascii=False).encode("utf-8")
                with open(CONFIG_ENC, "wb") as f:
                    f.write(fernet.encrypt(raw))
                return cfg
            except Exception:
                pass
    if not CONFIG_FILE.exists():
        return defaults
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k in defaults:
            if k not in cfg:
                cfg[k] = defaults[k]
        return cfg
    except Exception:
        return defaults


def save_config(config_dict: dict) -> tuple[bool, str]:
    """Salva config (in config.enc cifrato se sync attivo, altrimenti config.json)."""
    _ensure_dirs()
    allowed = {"license_key", "smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_use_tls", "from_email", "from_name"}
    out = {k: config_dict.get(k) for k in allowed if k in config_dict}
    if "smtp_port" in out and out["smtp_port"] is not None:
        try:
            out["smtp_port"] = int(out["smtp_port"])
        except (TypeError, ValueError):
            out["smtp_port"] = 587
    if "smtp_use_tls" in out:
        out["smtp_use_tls"] = bool(out["smtp_use_tls"])
    if _sync_key_set():
        fernet = _get_fernet()
        if fernet:
            try:
                raw = json.dumps(out, ensure_ascii=False).encode("utf-8")
                with open(CONFIG_ENC, "wb") as f:
                    f.write(fernet.encrypt(raw))
                return True, "Configurazione salvata."
            except Exception as e:
                return False, str(e)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        return True, "Configurazione salvata."
    except Exception as e:
        return False, str(e)
