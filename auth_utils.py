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
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
AUTH_DIR = APP_DIR / "auth"
DATA_DIR = APP_DIR / "data"
USERS_FILE = AUTH_DIR / "users.json"
CONFIG_FILE = AUTH_DIR / "config.json"

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
    if not USERS_FILE.exists():
        return {"users": []}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": []}


def _save_users(data: dict) -> bool:
    """Salva il file utenti."""
    _ensure_dirs()
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
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
    """
    data = _load_users()
    username = username.strip().lower()
    for u in data.get("users", []):
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


def create_user(username: str, password: str, is_admin_user: bool = False, nome: str = "", cognome: str = "") -> tuple[bool, str]:
    """
    Crea un nuovo utente. Ritorna (ok, msg).
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
        "password_hash": _hash_password(password),
        "attivo": True,
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


def ensure_admin_exists():
    """Crea l'utente admin con password predefinita se non esiste."""
    data = _load_users()
    has_admin = any(u.get("is_admin") for u in data.get("users", []))
    if not has_admin:
        default_pwd = "Admin123!"  # DA CAMBIARE al primo accesso
        data["users"].insert(0, {
            "username": "admin",
            "password_hash": _hash_password(default_pwd),
            "attivo": True,
            "is_admin": True,
            "created_at": str(__import__("datetime").datetime.now().isoformat()),
        })
        _save_users(data)
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
