# Deploy VLEKT PRO su VPS Linux (Serverplan)

## 1. Preparazione sul tuo computer

- Invia tutti i file del progetto sul server (FTP, SCP, oppure Git se lo usi).

## 2. Sul VPS – installazione

```bash
# Aggiorna il sistema
sudo apt update && sudo apt upgrade -y

# Installa Python 3 e pip
sudo apt install -y python3 python3-pip python3-venv

# Crea cartella per l'app (es. /opt/vlekt)
sudo mkdir -p /opt/vlekt
sudo chown $USER:$USER /opt/vlekt
cd /opt/vlekt

# Copia qui tutti i file del progetto (app2.py, auth_utils.py, auth/, data/, PDF template, ecc.)

# Crea ambiente virtuale
python3 -m venv venv
source venv/bin/activate

# Installa dipendenze
pip install -r requirements.txt

# Rendi eseguibile lo script
chmod +x start.sh
```

## 3. Licenza

Sul server imposta la variabile d'ambiente con la tua chiave:

```bash
export VLEKT_LICENSE_KEY="LA_TUA_CHIAVE_LICENZA"
```

Per usarla in modo persistente, aggiungi al file `~/.bashrc` o al service:

```
export VLEKT_LICENSE_KEY="LA_TUA_CHIAVE_LICENZA"
```

## 4. Primo avvio (test)

```bash
cd /opt/vlekt
source venv/bin/activate
export VLEKT_LICENSE_KEY="tua_chiave"
./start.sh
```

Apri `http://IP_DEL_SERVER:8501` nel browser. Se vedi il login, funziona.

## 5. Avvio automatico con systemd

```bash
# Copia il file di servizio
sudo cp vlekt.service /etc/systemd/system/

# Modifica vlekt.service: sostituisci TUO_USER con il tuo utente Linux, imposta VLEKT_LICENSE_KEY
sudo nano /etc/systemd/system/vlekt.service
# Cambia WorkingDirectory e Environment se necessario

# Abilita e avvia il servizio
sudo systemctl daemon-reload
sudo systemctl enable vlekt
sudo systemctl start vlekt
sudo systemctl status vlekt
```

## 6. Dominio e HTTPS (Nginx + Let's Encrypt)

```bash
# Installa Nginx e Certbot
sudo apt install -y nginx certbot python3-certbot-nginx

# Crea config Nginx
sudo nano /etc/nginx/sites-available/vlekt
```

Inserisci (sostituisci `app.tuodominio.it` con il tuo):

```nginx
server {
    listen 80;
    server_name app.tuodominio.it;
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Attiva il sito
sudo ln -s /etc/nginx/sites-available/vlekt /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Ottieni certificato SSL
sudo certbot --nginx -d app.tuodominio.it
```

## 7. DNS

Nel pannello del dominio (Serverplan) crea un record **A**:
- Nome: `app` (o il sottodominio che preferisci)
- Punta all’IP del tuo VPS

## 8. Primo accesso

- URL: `https://app.tuodominio.it`
- Utente: **admin**
- Password: **Admin123!**
- Cambia subito la password (gestione utenti in fase di estensione).
