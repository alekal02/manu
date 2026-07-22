# Desenvolvimento — ManuControl

Guia para quem vai manter ou evoluir o código.

## Requisitos

- Python 3.11+
- Windows, Linux ou macOS

## Setup local

```powershell
git clone https://github.com/alekal02/manu.git
cd manu
py -3 -m venv venv
.\venv\Scripts\Activate.ps1          # Linux: source venv/bin/activate
pip install -r back/requirements.txt
copy .env.example .env               # Linux: cp .env.example .env
python app.py
```

Abre em **http://localhost:5000** com `FLASK_DEBUG=true` (padrão).

## Estrutura do backend

| Arquivo | Responsabilidade |
|---------|------------------|
| `back/app.py` | Rotas Flask, autenticação, renderização |
| `back/services.py` | Regras de negócio, histórico fiscal, relatórios diário/mensal |
| `back/equipamentos.py` | CRUD ativos, OS, import CSV, relatório manutenções |
| `back/db.py` | Schema SQLite, migrações leves, seed admin |
| `back/pdf_reports.py` | PDFs (diário, mensal, manutenções) |
| `back/config.py` | `SECRET_KEY`, `DATABASE_PATH` via env |

## Frontend

Templates Jinja2 em `front/templates/`, CSS/JS em `front/static/`.

Layout base: `front/templates/base.html`  
Admin: `front/templates/admin/base.html`

## Banco de dados

SQLite em `DATABASE_PATH`. Tabelas principais:

- `bases` — filiais
- `usuarios` — gerente/fiscal por filial
- `admins` — administradores globais
- `ativos` — equipamentos
- `manutencoes` — ciclos de OS
- `manutencao_anotacoes` — acompanhamento da OS
- `historico_ativos` — auditoria / timeline fiscal

Migrações são aplicadas em `init_db()` ao subir o app (colunas e índices novos).

## Seed e dados de teste

```bash
python back/seed.py              # 20 filiais
python back/seed.py --migrar-json  # migra JSON legado (se existir)
```

## Rotas principais

| Rota | Acesso |
|------|--------|
| `/` | Dashboard filial |
| `/login` | Login gerente/fiscal |
| `/relatorios` | Relatórios (gerente) |
| `/relatorios/pdf?tipo=diario&offset=-1` | PDF diário ontem |
| `/admin/login` | Admin global |
| `/admin/historico` | Histórico por filial |
| `/api/ativos` | JSON (sessão) |

## Testar PDF localmente

```python
# no diretório back/, com venv ativo
from equipamentos import relatorio_manutencoes
from services import relatorio_diario, relatorio_atividade_fiscal
from pdf_reports import gerar_pdf_manutencoes
rel = relatorio_manutencoes(1)
pdf = gerar_pdf_manutencoes("01", "Filial", rel, relatorio_atividade_fiscal(1))
open("teste.pdf", "wb").write(pdf)
```

## Dependências

`back/requirements.txt` — dev  
`back/requirements-prod.txt` — inclui Gunicorn e Waitress

## Boas práticas antes de deploy

1. Nunca commitar `.env` ou `*.db`
2. Testar exportação PDF no SO alvo (fontes)
3. `FLASK_DEBUG=false` em produção
4. `SECRET_KEY` forte e estável

## Atualizar dependências

```bash
pip install --upgrade pip
pip install -r back/requirements.txt
pip freeze  # revisar antes de fixar novas versões
```
