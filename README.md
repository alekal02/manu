# Controle de Manutenção de Ativos

Aplicação web em Python/Flask para verificar e editar o status de manutenção de ativos (na base ou em terceiros).

## Estrutura do projeto

```
C:\manu\
├── back\                    # Backend (Python / Flask)
│   ├── app.py               # Servidor, rotas, login e API
│   ├── requirements.txt     # Dependências Python
│   └── data\
│       ├── ativos.json      # Dados dos ativos
│       └── usuarios.json    # Usuários e senhas
│
└── front\                   # Frontend (telas e estilo)
    ├── templates\           # Páginas HTML
    │   ├── base.html
    │   ├── login.html
    │   ├── verificacao.html
    │   ├── edicao.html
    │   └── perfil.html
    └── static\
        └── style.css        # Estilos visuais
```

## Perfis de acesso

| Perfil  | Usuário  | Senha  | Permissões                      |
|---------|----------|--------|---------------------------------|
| Gerente | `gerente`| `1234` | Visualizar dashboard            |
| Fiscal  | `fiscal` | `1234` | Visualizar + editar ativos      |

Altere a senha em **Perfil** (clique no nome no topo).

## Como executar

```powershell
cd C:\manu\back
python -m venv ..\venv
..\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Acesse: **http://localhost:5000**

## API

- `GET /api/ativos` — Retorna todos os ativos em JSON (requer login)
