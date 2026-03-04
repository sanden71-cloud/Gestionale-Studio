# -*- coding: utf-8 -*-
"""
Modulo autenticazione e gestione utenti per VLEKT PRO.
Gestisce login, utenti, database per utente, protezione copie.
"""
from __future__ import annotations
import os
import json
import hashlib
import secrets
import unicodedata
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
AUTH_DIR = APP_DIR / "auth"
DATA_DIR = APP_DIR / "data"
CONFIG_FILE = AUTH_DIR / "config.json"


def _get_users_file_path() -> Path:
    """Percorso del file utenti: prima quello accanto al modulo, poi auth/users.json nella cwd (per avvio da .command)."""
    default = AUTH_DIR / "users.json"
    if default.exists():
        return default
    cwd_auth = Path.cwd() / "auth" / "users.json"
    if cwd_auth.exists():
        return cwd_auth
    return default

# Chiave/licenza per protezione copie (impostare in config.json o variabile d'ambiente)
LICENSE_ENV = "VLEKT_LICENSE_KEY"


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
    """Carica il file utenti."""
    _ensure_dirs()
    users_file = _get_users_file_path()
    if not users_file.exists():
        return {"users": []}
    try:
        with open(users_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": []}


def _save_users(data: dict) -> bool:
    """Salva il file utenti."""
    _ensure_dirs()
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


def change_password(username: str, new_password: str) -> tuple[bool, str]:
    """Cambia la password di un utente."""
    data = _load_users()
    username = username.strip().lower()
    if len(new_password) < 6:
        return False, "La password deve essere di almeno 6 caratteri."
    for u in data["users"]:
        if u.get("username", "").lower() == username:
            u["password_hash"] = _hash_password(new_password)
            return _save_users(data), "Password aggiornata."
    return False, "Utente non trovato."


def reset_admin_password_to_default() -> tuple[bool, str]:
    """Reimposta la password dell'utente admin a Admin123!. Utile in sviluppo se non si ricorda la password."""
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
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    host = (cfg.get("smtp_host") or os.environ.get("VLEKT_SMTP_HOST") or "").strip()
    port = int(cfg.get("smtp_port") or os.environ.get("VLEKT_SMTP_PORT") or 587)
    user = (cfg.get("smtp_user") or os.environ.get("VLEKT_SMTP_USER") or "").strip()
    password = cfg.get("smtp_password") or os.environ.get("VLEKT_SMTP_PASSWORD") or ""
    use_tls = cfg.get("smtp_use_tls", True)
    from_addr = (cfg.get("from_email") or user or "noreply@vlekt.local").strip()
    if not host or not user or not password:
        return False, "SMTP non configurato: inserisci host, utente e password in Utility > Configurazione (licenza e SMTP)."
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
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

Accedi con queste credenziali e cambia subito la password da Utility > Amministrazione (sezione "Cambia la tua password").

Se non hai richiesto tu questo recupero, contatta l'amministratore.
"""
        sent, send_err = _send_email(email_addr, subject, body)
        if sent:
            return True, "Controlla la tua email: ti abbiamo inviato una password temporanea. Accedi e cambiala da Utility.", None
        # Invio fallito: messaggio con motivo e password da mostrare
        msg_base = "Password temporanea generata. Usala per accedere e cambiala da Utility."
        if send_err:
            msg_base = f"L'email non è stata inviata: {send_err}. " + msg_base
        return True, msg_base, temp_pass
    # Nessuna email sull'utente o invio non tentato
    return True, "Password temporanea generata. Usala per accedere e cambiala da Utility.", temp_pass


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


def check_license() -> tuple[bool, str]:
    """
    Verifica la licenza/protezione copie.
    Ritorna (ok, msg). Se ok=False, l'app non dovrebbe funzionare.
    """
    # Controllo 1: variabile d'ambiente
    key = os.environ.get(LICENSE_ENV)
    if key and len(key) >= 8:
        return True, ""

    # Controllo 2: file config nella cartella auth (non in repository)
    _ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("license_key") and len(str(cfg.get("license_key", ""))) >= 8:
                return True, ""
        except Exception:
            pass

    # Controllo 3: VLEKT_DEV=1 = sviluppo locale, salta controllo
    if os.environ.get("VLEKT_DEV") == "1":
        return True, ""

    # Se non c'è licenza valida
    return False, "Software non autorizzato. Contatta LINEADICIOTTO per la licenza."


def get_config() -> dict:
    """Legge auth/config.json. Ritorna un dict con license_key e tutti i campi SMTP (valori vuoti se mancanti)."""
    _ensure_dirs()
    defaults = {
        "license_key": "",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
        "smtp_use_tls": True,
        "from_email": "",
    }
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
    """Salva auth/config.json con i valori forniti. Solo chiavi note (license_key, smtp_*)."""
    _ensure_dirs()
    allowed = {"license_key", "smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_use_tls", "from_email"}
    out = {k: config_dict.get(k) for k in allowed if k in config_dict}
    if "smtp_port" in out and out["smtp_port"] is not None:
        try:
            out["smtp_port"] = int(out["smtp_port"])
        except (TypeError, ValueError):
            out["smtp_port"] = 587
    if "smtp_use_tls" in out:
        out["smtp_use_tls"] = bool(out["smtp_use_tls"])
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        return True, "Configurazione salvata."
    except Exception as e:
        return False, str(e)
