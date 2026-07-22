# ManuControl

Sistema web para **controle de manutenção de equipamentos** em múltiplas filiais. Desenvolvido em **Python/Flask** com banco **SQLite** (sem custo de servidor de banco).

## Funcionalidades

- Dashboard por filial com equipamentos operacionais e em manutenção
- Check-in diário e cadastro/edição de equipamentos (fiscal)
- Ordens de serviço (OS) com fases: planejamento, diagnóstico, execução, divergência de estoque, aguardando peças, aguardando terceiros
- Acompanhamento de OS aberta (anotações, responsável, local, fase)
- Relatórios PDF/CSV (manutenções, diário hoje/ontem)
- Painel administrativo (filiais, usuários, histórico fiscal)

## Estrutura do projeto

```
manu-main/
├── app.py                      # Entrada desenvolvimento
├── wsgi.py                     # Entrada produção (Gunicorn/Waitress)
├── .env.example                # Modelo de variáveis de ambiente
├── README.md
├── docs/
│   ├── DEPLOY.md               # Deploy no servidor da empresa
│   ├── OPERACAO.md             # Backup, usuários, rotina
│   └── DESENVOLVIMENTO.md      # Setup para devs
├── back/
│   ├── app.py                  # Rotas Flask
│   ├── config.py               # Configuração (SECRET_KEY, DATABASE_PATH)
│   ├── db.py                   # SQLite + migrações
│   ├── services.py             # Regras de negócio
│   ├── equipamentos.py         # OS, relatórios, importação
│   ├── pdf_reports.py          # Geração de PDF
│   ├── requirements.txt
│   ├── requirements-prod.txt   # Gunicorn + Waitress
│   ├── seed.py                 # Cria filiais iniciais
│   └── data/
│       └── exemplo_ativos.csv
└── front/
    ├── templates/
    └── static/
```

## Início rápido (desenvolvimento)

```powershell
cd C:\Projeto\manu-main
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r back\requirements.txt
copy .env.example .env
python app.py
```

Acesse: **http://localhost:5000**

Na primeira execução, o sistema cria automaticamente **20 filiais** de exemplo.

### Credenciais padrão (altere após o primeiro acesso)

| Perfil   | Onde entrar        | Usuário  | Senha  |
|----------|--------------------|----------|--------|
| Gerente  | `/login`           | `gerente`| `1234` |
| Fiscal   | `/login`           | `fiscal` | `1234` |
| Admin    | `/admin/login`     | `admin`  | `admin`|

Escolha a **filial** no login (ex.: código `01`).

## Produção

Consulte o guia completo: **[docs/DEPLOY.md](docs/DEPLOY.md)**

Resumo:

1. Copie `.env.example` → `.env` e defina `SECRET_KEY` e `DATABASE_PATH`
2. Instale dependências: `pip install -r back/requirements-prod.txt`
3. Suba com **Gunicorn** (Linux) ou **Waitress** (Windows)
4. Coloque **Nginx** ou **IIS** como proxy reverso (HTTPS recomendado)
5. Configure **backup diário** do arquivo `.db`

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [docs/DEPLOY.md](docs/DEPLOY.md) | Instalação no servidor Linux/Windows, systemd, Nginx, IIS |
| [docs/OPERACAO.md](docs/OPERACAO.md) | Backup, restore, usuários, importação CSV |
| [docs/DESENVOLVIMENTO.md](docs/DESENVOLVIMENTO.md) | Ambiente local, estrutura do código |

## API

- `GET /api/ativos` — Lista ativos da filial logada (requer sessão)

## Licença

Uso interno — projeto da empresa.
