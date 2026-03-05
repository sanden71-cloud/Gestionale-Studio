# Utility pages for VLEKT PRO - backup, restore, admin, etc. Called from app2 when show_utility is True.

import streamlit as st
import os
import json
import zipfile
from datetime import datetime
import pandas as pd


def render_utility(st, ctx):
    auth = ctx["auth"]
    is_admin = ctx["is_admin"]
    user_dir = ctx["user_dir"]
    paths = ctx["paths"]
    VERSION = ctx["version"]
    app_dir = ctx["app_dir"]
    df_p = ctx["df_p"]
    df_a = ctx["df_a"]
    df_d = ctx["df_d"]
    df_i = ctx["df_i"]
    df_pr = ctx["df_pr"]
    df_prot = ctx["df_prot"]
    read_changelog_for_version = ctx["read_changelog_for_version"]
    read_update_info = ctx["read_update_info"]
    parse_version = ctx["parse_version"]
    read_update_ack = ctx["read_update_ack"]
    write_update_ack = ctx["write_update_ack"]
    data_mod = ctx["data_mod"]

    def _write_update_info(version, download_url):
        try:
            p = os.path.join(ctx["app_dir"], "update_info.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"version": version, "download_url": download_url}, f, indent=2)
            return True
        except Exception:
            return False

    # ── Sottosezione Amministrazione utenti (solo admin) ──
    if auth and is_admin and st.session_state.get("show_admin_section"):
        st.markdown("<h2 style='color:#2c3e50;font-weight:900;'>⚙️ Amministrazione utenti</h2>", unsafe_allow_html=True)
        if st.button("🔙 Torna a Utility", key="btn_back_admin"):
            st.session_state.show_admin_section = False
            st.session_state.admin_reset_user = None
            st.rerun()
        st.markdown("---")

        if 'admin_reset_user' not in st.session_state:
            st.session_state.admin_reset_user = None
        if 'admin_gen_lic_user' not in st.session_state:
            st.session_state.admin_gen_lic_user = None
        if 'set_email_user' not in st.session_state:
            st.session_state.set_email_user = None

        # ── SEZIONE PRINCIPALE: Utenti e licenze (in cima, font leggibili) ──
        st.markdown("### 👥 Utenti e licenze")
        st.markdown("Gestisci utenti, attiva/disattiva accesso, genera licenze, imposta email e password.")
        if os.environ.get("VLEKT_SECRET_KEY", "").strip():
            st.info("🔄 **Sync attivo:** utenti, config e licenze sono salvati cifrati (users.enc, config.enc, licenses.enc). Committali su Git per avere gli stessi dati in locale e online.")
        users = auth.get_all_users()
        _all_lic = auth.get_all_licenses() if users else []

        def _licenze_per_utente(nome_cognome):
            nc = (nome_cognome or "").strip().lower()
            out = []
            for L in reversed(_all_lic):
                n = (L.get("notes") or "").strip().lower()
                if nc and (nc in n or n in nc):
                    out.append(L)
            return out[:3]

        # Allineamento locale ↔ online: hint se sync attivo
        _n_users = len(users)
        if os.environ.get("VLEKT_SECRET_KEY", "").strip():
            st.caption(f"Utenti caricati: **{_n_users}**. Per allineare locale e online: fai commit e push di `users.enc` e `licenses.enc`, poi sul deploy fai pull e riavvia.")

        if not users:
            st.info("Nessun utente. Crea il primo dalla sezione **Crea nuovo utente** qui sotto.")
        else:
            # Tabella tipo Excel: stesse proporzioni per intestazione e ogni riga
            _cols_w = [2.5, 1.3, 2.5, 0.9, 1.0, 2.5, 2.8]
            _h_style = "font-size:14px;font-weight:700;color:#475569;"
            _c_style = "font-size:15px;color:#1e293b;line-height:1.4;"
            _header = st.columns(_cols_w)
            _header[0].markdown(f"<div style='{_h_style}'>Nome</div>", unsafe_allow_html=True)
            _header[1].markdown(f"<div style='{_h_style}'>Username</div>", unsafe_allow_html=True)
            _header[2].markdown(f"<div style='{_h_style}'>Email</div>", unsafe_allow_html=True)
            _header[3].markdown(f"<div style='{_h_style}'>Data</div>", unsafe_allow_html=True)
            _header[4].markdown(f"<div style='{_h_style}'>Stato</div>", unsafe_allow_html=True)
            _header[5].markdown(f"<div style='{_h_style}'>Licenza</div>", unsafe_allow_html=True)
            _header[6].markdown(f"<div style='{_h_style}'>Azioni</div>", unsafe_allow_html=True)

            _last_lic = st.session_state.get("last_generated_license")  # (key, nome_cognome) o None

            for u in users:
                uname = u.get('username', '')
                attivo = u.get('attivo', True)
                is_adm = u.get('is_admin', False)
                user_email = (u.get('email') or '').strip() or "—"
                created = (u.get('created_at') or '')[:10]
                nome_cognome = f"{u.get('cognome', '')} {u.get('nome', '')}".strip() or uname
                stato = "Admin" if is_adm else ("Attivo" if attivo else "Disattivo")
                licenze_u = _licenze_per_utente(nome_cognome) if not is_adm else []
                lic_txt = "—"
                if licenze_u:
                    ult = licenze_u[0]
                    lic_txt = ult.get("expires_at") or "Senza scadenza"
                    if lic_txt != "Senza scadenza":
                        try:
                            lic_txt = lic_txt[-2:] + "/" + lic_txt[5:7] + "/" + lic_txt[:4]
                        except Exception:
                            pass
                r0, r1, r2, r3, r4, r5, r6 = st.columns(_cols_w)
                r0.markdown(f"<div style='{_c_style}'><strong>{nome_cognome}</strong></div>", unsafe_allow_html=True)
                r1.markdown(f"<div style='{_c_style}color:#64748b;'>{uname}</div>", unsafe_allow_html=True)
                r2.markdown(f"<div style='{_c_style}color:#64748b;'>{user_email}</div>", unsafe_allow_html=True)
                r3.markdown(f"<div style='font-size:14px;color:#94a3b8;'>{created}</div>", unsafe_allow_html=True)
                r4.markdown(f"<div style='{_c_style}'>{stato}</div>", unsafe_allow_html=True)
                with r5:
                    if is_adm:
                        st.markdown(f"<div style='{_c_style}color:#94a3b8;'>—</div>", unsafe_allow_html=True)
                    elif _last_lic and (_last_lic[1].strip().lower() == nome_cognome.strip().lower()):
                        _key = _last_lic[0]
                        _ck, _cb = st.columns([3, 1])
                        with _ck:
                            st.code(_key, language=None)
                        with _cb:
                            if st.button("Chiudi", key=f"close_lic_{uname}", use_container_width=True):
                                st.session_state.last_generated_license = None
                                st.rerun()
                    else:
                        _lc, _lb = st.columns([1.2, 1])
                        _lc.markdown(f"<div style='{_c_style}'>{lic_txt}</div>", unsafe_allow_html=True)
                        with _lb:
                            if st.button("Genera", key=f"lic_{uname}", use_container_width=True):
                                st.session_state.admin_gen_lic_user = (uname, nome_cognome)
                                st.rerun()
                with r6:
                    _a, _b, _c = st.columns(3)
                    with _a:
                        if st.button("✉️ Email", key=f"btn_email_{uname}", use_container_width=True):
                            st.session_state.set_email_user = uname
                            st.rerun()
                    with _b:
                        if not is_adm:
                            lab = "Disattiva" if attivo else "Attiva"
                            if st.button(lab, key=f"toggle_{uname}", use_container_width=True):
                                auth.toggle_user_active(uname)
                                st.toast("Stato aggiornato.", icon="✅")
                                st.rerun()
                    with _c:
                        if not is_adm and uname != st.session_state.logged_user:
                            if st.button("🔑 Pwd", key=f"reset_{uname}", use_container_width=True):
                                st.session_state.admin_reset_user = uname
                                st.rerun()
        if not st.session_state.get("last_generated_license") and st.session_state.admin_gen_lic_user:
            _gen_uname, _gen_nome = st.session_state.admin_gen_lic_user
            st.markdown(f"##### 📜 Genera licenza per **{_gen_nome}** (@{_gen_uname})")
            with st.form("form_gen_licenza"):
                lic_perpetua = st.checkbox("Licenza senza scadenza", value=True, key="lic_perpetua")
                lic_scad = st.date_input("Scadenza (usata solo se non perpetua)", key="lic_exp_d")
                _g1, _g2 = st.columns(2)
                with _g1:
                    if st.form_submit_button("Genera licenza"):
                        exp_str = None if lic_perpetua else lic_scad.strftime("%Y-%m-%d")
                        try:
                            new_key = auth.generate_license(expires_at=exp_str, notes=_gen_nome)
                            st.session_state.last_generated_license = (new_key, _gen_nome)
                            st.session_state.admin_gen_lic_user = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore: {e}")
                with _g2:
                    if st.form_submit_button("Annulla"):
                        st.session_state.admin_gen_lic_user = None
                        st.rerun()
        if st.session_state.admin_reset_user:
            st.markdown(f"##### 🔑 Imposta nuova password per **{st.session_state.admin_reset_user}**")
            with st.form("form_reset_pwd"):
                rp1 = st.text_input("Nuova password", type="password")
                rp2 = st.text_input("Ripeti password", type="password")
                rc1, rc2 = st.columns(2)
                if rc1.form_submit_button("Salva"):
                    if rp1 and rp2 and rp1 == rp2 and len(rp1) >= 6:
                        ok, msg = auth.change_password(st.session_state.admin_reset_user, rp1, set_must_change_on_next_login=True)
                        if ok:
                            st.toast(msg, icon="✅")
                            st.session_state.admin_reset_user = None
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.error("Password non valide o non coincidono.")
                if rc2.form_submit_button("Annulla"):
                    st.session_state.admin_reset_user = None
                    st.rerun()
        if st.session_state.get("set_email_user"):
            _who = st.session_state.set_email_user
            _current = next((x.get("email") or "" for x in auth.get_all_users() if (x.get("username") or "").lower() == _who.lower()), "")
            st.markdown(f"##### ✉️ Imposta email per **{_who}** (recupero password)")
            with st.form("form_set_email"):
                _em = st.text_input("Email", value=_current, placeholder="es. utente@email.it", key="input_email_user")
                _c1, _c2 = st.columns(2)
                if _c1.form_submit_button("Salva"):
                    ok_em, msg_em = auth.set_user_email(_who, _em)
                    if ok_em:
                        st.toast(msg_em, icon="✅")
                        st.session_state.set_email_user = None
                        st.rerun()
                    else:
                        st.error(msg_em)
                if _c2.form_submit_button("Annulla"):
                    st.session_state.set_email_user = None
                    st.rerun()
        st.markdown("---")
        st.markdown("### ➕ Crea nuovo utente")
        st.caption("I nuovi utenti restano **disattivati** finché non li attivi dall'elenco sopra (pulsante Attiva). Così abiliti l'accesso online solo quando sei pronto.")
        with st.form("admin_nuovo_utente"):
            cn, cc = st.columns(2)
            with cn:
                nuovo_nome = st.text_input("Nome", placeholder="es. Mario")
            with cc:
                nuovo_cognome = st.text_input("Cognome", placeholder="es. Rossi")
            nu = st.text_input("Username", placeholder="es. mario.rossi")
            nuovo_email = st.text_input("Email (per recupero password)", placeholder="es. mario@email.it")
            np = st.text_input("Password", type="password", placeholder="minimo 6 caratteri")
            np_rip = st.text_input("Ripeti password", type="password")
            attiva_subito = st.checkbox("Attiva utente subito (può accedere dopo la creazione)", value=False)
            if st.form_submit_button("Crea utente"):
                if not nu or not np:
                    st.error("Inserisci username e password.")
                elif np != np_rip:
                    st.error("Le password non coincidono.")
                elif len(np) < 6:
                    st.error("La password deve essere di almeno 6 caratteri.")
                else:
                    ok, msg = auth.create_user(nu, np, is_admin_user=False, nome=nuovo_nome or "", cognome=nuovo_cognome or "", attivo=attiva_subito, email=nuovo_email or "")
                    if ok:
                        data_mod.init_user_db(auth.get_user_data_dir(nu))
                        _toast_msg = msg + (" L'utente è attivo e può accedere. Dovrà cambiare la password al primo accesso." if attiva_subito else " Attivalo dall'elenco quando vuoi abilitarlo.")
                        st.toast(_toast_msg, icon="✅")
                    else:
                        st.error(msg)
                    st.rerun()

        # ── IN FONDO: Configurazione e password (expander per non confondere) ──
        st.markdown("---")
        with st.expander("⚙️ Configurazione (licenza globale e SMTP)", expanded=False):
            st.markdown("Chiave licenza dell'installazione e impostazioni email per il recupero password.")
            _cfg = auth.get_config()
            with st.form("admin_config_form"):
                lic = st.text_input("Chiave licenza", value=_cfg.get("license_key") or "", type="password", placeholder="VLEKT-xxx-xxx (genera dalla tabella utenti sopra)")
                st.markdown("**SMTP (recupero password)**")
                smtp_host = st.text_input("Host SMTP", value=_cfg.get("smtp_host") or "smtp.gmail.com", placeholder="es. smtp.gmail.com")
                smtp_port = st.number_input("Porta SMTP", min_value=1, max_value=65535, value=int(_cfg.get("smtp_port") or 587), step=1)
                smtp_user = st.text_input("Utente SMTP", value=_cfg.get("smtp_user") or "", placeholder="email o username")
                smtp_password = st.text_input("Password SMTP", value="", type="password", placeholder="lascia vuoto per non modificare")
                smtp_use_tls = st.checkbox("Usa TLS", value=bool(_cfg.get("smtp_use_tls", True)))
                from_name = st.text_input("Nome mittente", value=_cfg.get("from_name") or "", placeholder="es. Software Gestionale AD")
                from_email = st.text_input("Indirizzo mittente (From)", value=_cfg.get("from_email") or "", placeholder="es. noreply@tuodominio.it")
                if st.form_submit_button("Salva configurazione"):
                    pwd_final = _cfg.get("smtp_password") or ""
                    if (smtp_password or "").strip():
                        pwd_final = smtp_password
                    data = {
                        "license_key": (lic or "").strip(),
                        "smtp_host": (smtp_host or "").strip(),
                        "smtp_port": smtp_port,
                        "smtp_user": (smtp_user or "").strip(),
                        "smtp_password": pwd_final,
                        "smtp_use_tls": smtp_use_tls,
                        "from_name": (from_name or "").strip(),
                        "from_email": (from_email or "").strip(),
                    }
                    ok_cfg, msg_cfg = auth.save_config(data)
                    if ok_cfg:
                        st.toast(msg_cfg, icon="✅")
                        st.rerun()
                    else:
                        st.error(msg_cfg)
        with st.expander("🔐 Cambia la tua password", expanded=False):
            with st.form("admin_cambia_pwd"):
                pwd_attuale = st.text_input("Password attuale", type="password", autocomplete="current-password")
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
                        ok_ver, _ = auth.verify_login(st.session_state.logged_user, (pwd_attuale or "").strip())
                        if not ok_ver:
                            st.error("Password attuale non corretta.")
                        else:
                            ok, msg = auth.change_password(st.session_state.logged_user, pwd_nuova)
                            if ok:
                                st.toast(msg, icon="✅")
                                st.rerun()
                            else:
                                st.error(msg)
        st.stop()

    st.markdown("<h2 style='color:#2c3e50;font-weight:900;'>🔧 Utility</h2>", unsafe_allow_html=True)
    if st.button("🔙 Chiudi Utility", use_container_width=False):
        st.session_state.show_utility = False
        st.session_state.show_admin_section = False
        st.rerun()

    # Changelog in evidenza: mostra subito le novità della versione corrente
    _changelog_util = read_changelog_for_version(app_dir, VERSION)
    if _changelog_util:
        with st.expander(f"📋 Novità versione {VERSION}", expanded=True):
            st.markdown(_changelog_util)

    # Cambia la tua password: visibile a TUTTI gli utenti (non solo admin)
    _must_change = auth.get_user_must_change_password(st.session_state.logged_user) if auth else False
    with st.expander("🔐 Cambia la tua password", expanded=_must_change):
        with st.form("utility_cambia_pwd"):
            pwd_attuale = st.text_input("Password attuale", type="password", autocomplete="current-password", key="util_pwd_attuale")
            pwd_nuova = st.text_input("Nuova password", type="password", key="util_pwd_nuova")
            pwd_ripeti = st.text_input("Ripeti nuova password", type="password", key="util_pwd_ripeti")
            if st.form_submit_button("Aggiorna password"):
                if not pwd_attuale or not pwd_nuova:
                    st.error("Compila tutti i campi.")
                elif pwd_nuova != pwd_ripeti:
                    st.error("Le password non coincidono.")
                elif len(pwd_nuova) < 6:
                    st.error("La password deve essere di almeno 6 caratteri.")
                else:
                    ok_ver, _ = auth.verify_login(st.session_state.logged_user, (pwd_attuale or "").strip())
                    if not ok_ver:
                        st.error("Password attuale non corretta.")
                    else:
                        ok, msg = auth.change_password(st.session_state.logged_user, pwd_nuova, set_must_change_on_next_login=False)
                        if ok:
                            st.toast(msg, icon="✅")
                            st.rerun()
                        else:
                            st.error(msg)
        if _must_change:
            st.caption("⚠️ Modifica la password per sicurezza: è stata fornita dall'amministratore o dal recupero.")
    st.markdown("---")

    if "utility_tab" not in st.session_state:
        st.session_state.utility_tab = "backup"
    _tabs_list = [
        ("backup", "📦 Backup"),
        ("ripristino", "📤 Ripristino"),
    ]
    if auth:
        _tabs_list.append(("archivi", "📁 Archivi"))
    _tabs_list.extend([
        ("statistiche", "📊 Statistiche"),
        ("integrita", "🔍 Integrità"),
        ("duplicati", "🧹 Duplicati"),
    ])
    if auth and is_admin:
        _tabs_list.extend([("versione", "📌 Versione"), ("amministrazione", "⚙️ Admin")])
    _tabs_list.append(("aggiornamenti", "🔄 Aggiornamenti"))
    _valid_tabs = [t[0] for t in _tabs_list]
    if st.session_state.utility_tab not in _valid_tabs:
        st.session_state.utility_tab = "backup"
    _tab = st.session_state.utility_tab

    # Griglia fissa 2 righe × 5 colonne: pulsanti stesse dimensioni
    _n = 5
    _row1 = _tabs_list[:_n]
    _row2 = _tabs_list[_n:_n * 2]
    _c1 = st.columns(_n)
    for _i, (_key, _label) in enumerate(_row1):
        with _c1[_i]:
            _type = "primary" if _tab == _key else "secondary"
            if st.button(_label, key=f"util_tab_{_key}", use_container_width=True, type=_type):
                st.session_state.utility_tab = _key
                st.rerun()
    _c2 = st.columns(_n)
    for _i, (_key, _label) in enumerate(_row2):
        with _c2[_i]:
            _type = "primary" if _tab == _key else "secondary"
            if st.button(_label, key=f"util_tab_{_key}", use_container_width=True, type=_type):
                st.session_state.utility_tab = _key
                st.rerun()
    st.markdown("---")

    # Backup: un solo file SQLite per utente
    DB_BACKUP_FILE = paths["DB_SQLITE"]
    _udir = user_dir if auth else app_dir
    _archivi_dir = os.path.join(_udir, "archivi") if auth else None

    # ── 1. BACKUP DATABASE ──
    if _tab == "backup":
        st.markdown("#### 📦 Backup database")
        st.markdown("Salva il database (SQLite) in un archivio ZIP con timestamp. Conservalo in un luogo sicuro." + (" Una copia viene salvata anche in **I miei archivi**." if auth else ""))
        if st.button("📥 Crea backup completo", type="primary", key="btn_backup"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_name = f"backup_vlekt_{ts}.zip"
            zip_path = os.path.join(app_dir, zip_name)
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    if os.path.exists(DB_BACKUP_FILE):
                        zf.write(DB_BACKUP_FILE, "vlekt.db")
                with open(zip_path, 'rb') as f:
                    st.session_state.backup_bytes = f.read()
                st.session_state.backup_filename = zip_name
                if _archivi_dir:
                    os.makedirs(_archivi_dir, exist_ok=True)
                    archivi_path = os.path.join(_archivi_dir, zip_name)
                    with open(archivi_path, 'wb') as f:
                        f.write(st.session_state.backup_bytes)
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

    # ── 2. RESTORE DA BACKUP ──
    if _tab == "ripristino":
        st.markdown("#### 📤 Ripristino da backup")
        st.markdown("Carica un file ZIP di backup precedente per sostituire il database attuale. **Attenzione: sovrascrive i dati correnti.**")
        file_restore = st.file_uploader("Carica file ZIP di backup", type=["zip"], key="upload_restore")
        if file_restore:
            if st.button("⚠️ Ripristina database (conferma)", type="primary", key="btn_restore"):
                try:
                    with zipfile.ZipFile(file_restore, 'r') as zf:
                        names = zf.namelist()
                        has_db = any('vlekt.db' in n for n in names)
                        if has_db:
                            for n in names:
                                if 'vlekt.db' in n and not n.startswith('__'):
                                    zf.extract(n, _udir)
                                    _extracted = os.path.join(_udir, n)
                                    _dest = os.path.join(_udir, "vlekt.db")
                                    if os.path.isfile(_extracted):
                                        if _extracted != _dest:
                                            if os.path.exists(_dest):
                                                os.remove(_dest)
                                            os.rename(_extracted, _dest)
                                    break
                        else:
                            for name in names:
                                if name.endswith('.csv'):
                                    zf.extract(name, _udir)
                            _db_path = os.path.join(_udir, "vlekt.db")
                            if os.path.exists(_db_path):
                                os.remove(_db_path)
                    st.success("✅ Backup ripristinato. Ricarica la pagina per vedere i dati aggiornati.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore durante il ripristino: {e}")

    # ── 2b. I MIEI ARCHIVI ──
    if _tab == "archivi" and auth and _archivi_dir:
        st.markdown("#### 📁 I miei archivi")
        st.markdown("Backup salvati nella tua area. Puoi scaricarli o ripristinare da uno di essi.")
        os.makedirs(_archivi_dir, exist_ok=True)
        _archivi_files = sorted([f for f in os.listdir(_archivi_dir) if f.endswith('.zip')], reverse=True)
        if not _archivi_files:
            st.info("Nessun archivio ancora. Crea un backup con il pulsante sopra; una copia verrà salvata qui.")
        else:
            for _ar in _archivi_files:
                _ar_path = os.path.join(_archivi_dir, _ar)
                _col_dl, _col_restore, _ = st.columns([1, 1, 3])
                with _col_dl:
                    with open(_ar_path, 'rb') as _f:
                        st.download_button("⬇️ Scarica", data=_f.read(), file_name=_ar, mime="application/zip", key=f"dl_arch_{_ar}")
                with _col_restore:
                    if st.button("⚠️ Ripristina", key=f"restore_arch_{_ar}"):
                        st.session_state.restore_archivo_path = _ar_path
                        st.rerun()
                st.caption(_ar)
            if st.session_state.get("restore_archivo_path"):
                _path = st.session_state.restore_archivo_path
                st.warning(f"Stai per ripristinare i database da **{os.path.basename(_path)}**. I dati attuali saranno sostituiti.")
                if st.button("✅ Conferma ripristino", type="primary", key="confirm_restore_arch"):
                    try:
                        with zipfile.ZipFile(_path, 'r') as zf:
                            names = zf.namelist()
                            has_db = any('vlekt.db' in n for n in names)
                            if has_db:
                                for n in names:
                                    if 'vlekt.db' in n and not n.startswith('__'):
                                        zf.extract(n, _udir)
                                        _extracted = os.path.join(_udir, n)
                                        _dest = os.path.join(_udir, "vlekt.db")
                                        if os.path.isfile(_extracted) and _extracted != _dest:
                                            if os.path.exists(_dest):
                                                os.remove(_dest)
                                            os.rename(_extracted, _dest)
                                        break
                            else:
                                for name in names:
                                    if name.endswith('.csv'):
                                        zf.extract(name, _udir)
                                _db_path = os.path.join(_udir, "vlekt.db")
                                if os.path.exists(_db_path):
                                    os.remove(_db_path)
                        del st.session_state.restore_archivo_path
                        st.success("Archivio ripristinato. Ricarica la pagina.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                if st.button("❌ Annulla", key="cancel_restore_arch"):
                    del st.session_state.restore_archivo_path
                    st.rerun()

    # ── 3. STATISTICHE ──
    if _tab == "statistiche":
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

    # ── 4. VERIFICA INTEGRITÀ ──
    if _tab == "integrita":
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

    # ── 5. PULIZIA DUPLICATI ──
    if _tab == "duplicati":
        st.markdown("#### 🧹 Pulizia duplicati")
        st.markdown("Rimuove righe duplicate dai database. Per pazienti e diete si mantiene l'ultima occorrenza; per gli altri la prima.")
        if st.button("Esegui pulizia duplicati", type="primary", key="btn_clean_dup"):
            modifiche = []
            n_prima = len(df_p) if not df_p.empty else 0
            df_p_clean = df_p.drop_duplicates(subset=['Codice_Fiscale', 'Data_Visita'], keep='last')
            if len(df_p_clean) < n_prima:
                data_mod.save_table(paths, "DB_PAZIENTI", df_p_clean)
                modifiche.append(f"Pazienti: rimossi {n_prima - len(df_p_clean)} duplicati")
            if not df_a.empty:
                n_prima = len(df_a)
                df_a_clean = df_a.drop_duplicates(subset=['Alimento'], keep='first')
                if len(df_a_clean) < n_prima:
                    data_mod.save_table(paths, "DB_ALIMENTI", df_a_clean)
                    modifiche.append(f"Alimenti: rimossi {n_prima - len(df_a_clean)} duplicati")
            if not df_d.empty:
                n_prima = len(df_d)
                df_d_clean = df_d.drop_duplicates(keep='first')
                if len(df_d_clean) < n_prima:
                    data_mod.save_table(paths, "DB_DIETE", df_d_clean)
                    modifiche.append(f"Diete: rimossi {n_prima - len(df_d_clean)} duplicati")
            if not df_i.empty:
                n_prima = len(df_i)
                df_i_clean = df_i.drop_duplicates(subset=['Nome_Integratore'], keep='first')
                if len(df_i_clean) < n_prima:
                    data_mod.save_table(paths, "DB_INTEGRATORI", df_i_clean)
                    modifiche.append(f"Integratori: rimossi {n_prima - len(df_i_clean)} duplicati")
            if not df_pr.empty:
                n_prima = len(df_pr)
                df_pr_clean = df_pr.drop_duplicates(subset=['Codice_Fiscale', 'Data_Visita', 'Data_Inizio', 'Nome_Integratore'], keep='first')
                if len(df_pr_clean) < n_prima:
                    data_mod.save_table(paths, "DB_PRESCRIZIONI", df_pr_clean)
                    modifiche.append(f"Prescrizioni: rimossi {n_prima - len(df_pr_clean)} duplicati")
            if not df_prot.empty:
                n_prima = len(df_prot)
                df_prot_clean = df_prot.drop_duplicates(subset=['Nome'], keep='first')
                if len(df_prot_clean) < n_prima:
                    data_mod.save_table(paths, "DB_PROTEINE", df_prot_clean)
                    modifiche.append(f"Proteine: rimossi {n_prima - len(df_prot_clean)} duplicati")

            if modifiche:
                for m in modifiche:
                    st.success(f"✅ {m}")
                st.info("Ricarica la pagina per vedere i dati aggiornati.")
                st.rerun()
            else:
                st.success("✅ Nessun duplicato trovato.")

    # ── 6. GESTIONE VERSIONE (solo admin) ──
    if _tab == "versione" and auth and is_admin:
        st.markdown("#### 📌 Gestione versione e aggiornamenti (solo admin)")
        st.markdown("Quando pubblichi una **nuova versione** dell'app (es. dopo aver creato un nuovo installabile): imposta qui il **numero di versione** che gli utenti devono vedere e l'**URL** da cui scaricare l'aggiornamento. Gli utenti vedranno l'avviso in cima alla pagina (o in **Verifica aggiornamenti** sotto) e confermeranno di aver letto le novità (nessun download).")
        _pub_ver, _pub_url = read_update_info(app_dir, VERSION)
        _col_v, _col_u = st.columns(2)
        with _col_v:
            _new_ver = st.text_input("Versione pubblicata", value=_pub_ver or VERSION, key="input_published_version", placeholder="es. 1.0.1")
        with _col_u:
            _new_url = st.text_input("URL download aggiornamento", value=_pub_url, key="input_download_url", placeholder="https://...")
        if st.button("💾 Salva versione e URL", type="primary", key="btn_save_update_info"):
            _v = str(_new_ver).strip() or VERSION
            if _write_update_info(_v, str(_new_url).strip()):
                st.toast("Versione e URL salvati. Gli utenti vedranno l'avviso di aggiornamento.", icon="✅")
                st.rerun()
            else:
                st.error("Impossibile salvare (controlla i permessi della cartella dell'app).")
        st.markdown("---")

    # ── 7. CONTROLLA AGGIORNAMENTI ──
    if _tab == "aggiornamenti":
        st.markdown("#### 🔄 Verifica aggiornamenti")
        _pub_ver, _pub_url = read_update_info(app_dir, VERSION)
        _changelog = read_changelog_for_version(app_dir, VERSION)
        if _changelog:
            with st.expander("📋 Novità in questa versione", expanded=True):
                st.markdown(_changelog)
        if auth and is_admin:
            st.caption("In qualità di **amministratore** gestisci la versione pubblicata nel tab Versione. Gli utenti vedranno l'avviso finché non confermano qui di aver letto le novità.")
        else:
            st.markdown("Qui puoi leggere le novità della versione in uso. Conferma di aver letto per far scomparire l'avviso in home.")
            if parse_version(_pub_ver) > parse_version(read_update_ack(user_dir)):
                if st.button("✅ Confermo, ho letto le novità", type="primary", key="btn_ack_update"):
                    if write_update_ack(user_dir, _pub_ver):
                        st.toast("Avviso aggiornamento rimosso.", icon="✅")
                        st.rerun()
                    else:
                        st.error("Impossibile salvare.")
            else:
                st.info(f"Hai già confermato le novità per la versione **{_pub_ver}**.")

    # ── 8. AMMINISTRAZIONE ──
    if _tab == "amministrazione" and auth and is_admin:
        st.markdown("#### ⚙️ Amministrazione")
        st.caption("Configura **licenza** e **server SMTP** (per il recupero password via email) e gestisci gli utenti.")
        if st.button("👥 Amministrazione utenti (licenza, SMTP, utenti)", type="primary", key="btn_admin_from_utility"):
            st.session_state.show_admin_section = True
            st.rerun()
