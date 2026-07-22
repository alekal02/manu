# Deploy em produção — ManuControl

Guia para publicar o ManuControl no **servidor da empresa** (Linux ou Windows).

## Pré-requisitos

| Item | Linux | Windows Server |
|------|-------|----------------|
| Python | 3.11 ou 3.12 | 3.11 ou 3.12 |
| Proxy | Nginx (recomendado) | IIS ou Nginx |
| WSGI | Gunicorn | Waitress |
| Disco | Pasta persistente para `manu.db` | Idem |
| HTTPS | Certificado (Let's Encrypt ou interno) | Certificado IIS |

## 1. Preparar o servidor

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx

sudo mkdir -p /opt/manucontrol
sudo mkdir -p /var/lib/manucontrol
sudo chown $USER:$USER /opt/manucontrol /var/lib/manucontrol
```

### Windows Server

1. Instale [Python 3.12](https://www.python.org/downloads/) (marque "Add to PATH")
2. Crie pastas:
   - `D:\apps\manucontrol\app` — código
   - `D:\apps\manucontrol\data` — banco SQLite

## 2. Obter o código

```bash
# Linux
cd /opt/manucontrol
git clone https://github.com/alekal02/manu.git .

# Windows (PowerShell)
cd D:\apps\manucontrol\app
git clone https://github.com/alekal02/manu.git .
```

Ou copie o ZIP do repositório para a pasta de deploy.

## 3. Ambiente virtual e dependências

### Linux

```bash
cd /opt/manucontrol
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r back/requirements-prod.txt
```

### Windows

```powershell
cd D:\apps\manucontrol\app
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r back\requirements-prod.txt
```

## 4. Configurar variáveis de ambiente

Copie o modelo e edite:

```bash
cp .env.example .env
nano .env   # Linux
# notepad .env   # Windows
```

**Exemplo Linux:**

```env
SECRET_KEY=cole-aqui-uma-chave-aleatoria-de-64-caracteres
DATABASE_PATH=/var/lib/manucontrol/manu.db
FLASK_DEBUG=false
```

**Exemplo Windows:**

```env
SECRET_KEY=cole-aqui-uma-chave-aleatoria-de-64-caracteres
DATABASE_PATH=D:\apps\manucontrol\data\manu.db
FLASK_DEBUG=false
```

Gerar `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Importante:** `DATABASE_PATH` deve apontar para uma pasta que **não seja apagada** quando você atualizar o código.

## 5. Inicializar banco e filiais

Execute uma vez após o deploy:

```bash
source venv/bin/activate   # Linux
# ou .\venv\Scripts\Activate.ps1 no Windows

python back/seed.py
```

Na primeira visita ao site, as filiais também são criadas automaticamente se o banco estiver vazio.

**Altere imediatamente** as senhas padrão (`gerente`/`fiscal`/`admin`).

## 6. Subir a aplicação

### Linux — Gunicorn + systemd

Crie o serviço `/etc/systemd/system/manucontrol.service`:

```ini
[Unit]
Description=ManuControl Flask App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/manucontrol
EnvironmentFile=/opt/manucontrol/.env
ExecStart=/opt/manucontrol/venv/bin/gunicorn \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --timeout 120 \
    wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> O Gunicorn carrega `back/app.py` diretamente. Alternativa: `wsgi:application` com `--chdir /opt/manucontrol`.

Ative o serviço:

```bash
sudo systemctl daemon-reload
sudo systemctl enable manucontrol
sudo systemctl start manucontrol
sudo systemctl status manucontrol
```

Logs:

```bash
sudo journalctl -u manucontrol -f
```

### Windows — Waitress

Teste manual:

```powershell
cd D:\apps\manucontrol\app
.\venv\Scripts\Activate.ps1
$env:FLASK_DEBUG="false"
waitress-serve --listen=127.0.0.1:8000 --call wsgi:application
```

Para rodar como serviço, use **NSSM** (Non-Sucking Service Manager):

```powershell
nssm install ManuControl "D:\apps\manucontrol\app\venv\Scripts\waitress-serve.exe"
nssm set ManuControl AppParameters "--listen=127.0.0.1:8000 --call wsgi:application"
nssm set ManuControl AppDirectory "D:\apps\manucontrol\app"
nssm set ManuControl AppEnvironmentExtra "FLASK_DEBUG=false"
nssm start ManuControl
```

## 7. Proxy reverso (HTTPS)

### Nginx (Linux)

Arquivo `/etc/nginx/sites-available/manucontrol`:

```nginx
server {
    listen 80;
    server_name manu.suaempresa.com.br;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    client_max_body_size 10M;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/manucontrol /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Configure HTTPS com Certbot ou certificado interno da empresa.

### IIS (Windows)

1. Instale o módulo **URL Rewrite** e **Application Request Routing**
2. Crie um site apontando para proxy `http://127.0.0.1:8000`
3. Vincule certificado SSL no binding HTTPS

## 8. Atualizar versão (deploy contínuo)

```bash
cd /opt/manucontrol
git pull origin main
source venv/bin/activate
pip install -r back/requirements-prod.txt
sudo systemctl restart manucontrol
```

O banco SQLite em `DATABASE_PATH` **não é sobrescrito** pelo `git pull`.

## 9. Checklist antes de ir ao ar

- [ ] `SECRET_KEY` única e forte no `.env`
- [ ] `FLASK_DEBUG=false`
- [ ] `DATABASE_PATH` em disco persistente
- [ ] Senhas padrão alteradas (gerente, fiscal, admin)
- [ ] Backup automático do `.db` configurado
- [ ] HTTPS ativo
- [ ] Firewall: apenas 80/443 públicos; porta 8000 só localhost
- [ ] Teste login, abertura de OS, exportação PDF

## 10. Solução de problemas

| Problema | Causa provável | Solução |
|----------|----------------|---------|
| Erro 502 Bad Gateway | Gunicorn parado | `systemctl status manucontrol` |
| Banco vazio após deploy | `DATABASE_PATH` errado | Confira `.env` e permissões da pasta |
| PDF não gera | Fonte Arial ausente (Linux) | Instale `fonts-liberation` ou copie fontes em `back/fonts/` |
| Sessão expira / erro estranho | `SECRET_KEY` mudou | Mantenha a mesma chave entre restarts |
| Permissão negada no `.db` | Usuário do serviço | `chown www-data` na pasta de dados |

Fontes no Linux:

```bash
sudo apt install -y fonts-liberation
```

## Portas utilizadas

| Serviço | Porta padrão | Exposto |
|---------|--------------|---------|
| Flask dev | 5000 | Só desenvolvimento |
| Gunicorn/Waitress | 8000 | Apenas localhost |
| Nginx/IIS | 80 / 443 | Público |
