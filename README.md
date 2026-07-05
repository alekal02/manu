# Controle de Manutenção de Ativos

Aplicação web em Python/Flask com **SQLite** para gestão de manutenção de ativos em **múltiplas filiais** — **100% gratuita**, sem servidor de banco externo.

## Por que SQLite?

| Opção | Custo | Para seu caso |
|-------|-------|---------------|
| **SQLite** | Grátis | Ideal — 20 filiais, dados moderados |
| MongoDB Atlas | Grátis (512 MB) | Exige conta e internet |
| PostgreSQL pago | Pago | Desnecessário agora |

O SQLite grava tudo em um arquivo (`back/data/manu.db`). Cada filial continua isolada por `base_id`, sem conflito entre bases.

## Estrutura

```
manu/
├── app.py                 # Ponto de entrada
├── .env.example
├── back/
│   ├── app.py             # Rotas Flask
│   ├── config.py
│   ├── db.py              # SQLite + tabelas
│   ├── services.py        # Regras de negócio
│   ├── seed.py            # Cria 20 filiais
│   └── data/
│       ├── manu.db        # Banco (criado automaticamente)
│       └── exemplo_ativos.csv
└── front/
    ├── templates/
    └── static/
```

## Perfis de acesso

| Perfil  | Usuário   | Permissões |
|---------|-----------|------------|
| Gerente | `gerente` | Visualizar dashboard da filial |
| Fiscal  | `fiscal`  | Visualizar + editar + importar CSV |

Senha inicial em todas as filiais: **1234** (altere em Perfil).

## Como executar

```powershell
cd C:\manu\manu
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r back\requirements.txt
python app.py
```

Na primeira visita ao login, as **20 filiais** são criadas automaticamente.

Acesse: **http://localhost:5000**

## Importar lista de ativos

1. Login como **fiscal** na filial desejada
2. **Edição → Importar lista de ativos**
3. CSV com colunas `nome` e `codigo` (exemplo em `back/data/exemplo_ativos.csv`)

## Publicar na web (sem pagar banco)

Hospede o app em plataformas gratuitas (Render, Railway, PythonAnywhere, etc.) e garanta que o arquivo `manu.db` fique em **disco persistente**:

- Configure `DATABASE_PATH` apontando para uma pasta que não seja apagada a cada deploy
- Faça backup periódico do arquivo `.db`

Cada filial acessa o mesmo link, escolhe sua base no login e vê só seus ativos.

## API

- `GET /api/ativos` — Ativos da filial logada (requer sessão)
