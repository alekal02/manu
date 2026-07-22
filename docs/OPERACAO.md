# Operação — ManuControl

Rotina diária, backup e gestão de usuários no ambiente de produção.

## Perfis de acesso

| Perfil | Login | O que faz |
|--------|-------|-----------|
| **Fiscal** | `/login` → filial + `fiscal` | Check-in diário, cadastra/edita equipamentos, abre e acompanha OS |
| **Gerente** | `/login` → filial + `gerente` | Visualiza dashboard, relatórios PDF/CSV da filial |
| **Admin** | `/admin/login` → `admin` | Gerencia filiais, usuários e histórico global |

### Senhas padrão (primeiro deploy)

| Usuário | Senha |
|---------|-------|
| `gerente` | `1234` |
| `fiscal` | `1234` |
| `admin` | `admin` |

**Altere todas após o go-live.** O fiscal/gerente altera a própria senha em **Perfil**; o admin em **Admin → Perfil**.

## Backup do banco SQLite

Todo o sistema está no arquivo definido em `DATABASE_PATH` (padrão: `back/data/manu.db`).

### Backup manual (Linux)

```bash
#!/bin/bash
DATA=/var/lib/manucontrol/manu.db
DEST=/backup/manucontrol
mkdir -p "$DEST"
cp "$DATA" "$DEST/manu-$(date +%Y%m%d-%H%M).db"
# Mantém últimos 30 dias
find "$DEST" -name "manu-*.db" -mtime +30 -delete
```

Agende no cron (`crontab -e`):

```
0 2 * * * /opt/manucontrol/scripts/backup.sh
```

### Backup manual (Windows)

```powershell
$src = "D:\apps\manucontrol\data\manu.db"
$dest = "D:\backup\manucontrol"
New-Item -ItemType Directory -Force -Path $dest
Copy-Item $src "$dest\manu-$(Get-Date -Format yyyyMMdd-HHmm).db"
```

Use o **Agendador de Tarefas** do Windows para rodar diariamente.

### Restore

1. Pare o serviço (`systemctl stop manucontrol` ou pare o NSSM)
2. Substitua o arquivo `.db` pelo backup
3. Inicie o serviço novamente

```bash
sudo systemctl stop manucontrol
cp /backup/manucontrol/manu-20260722-0200.db /var/lib/manucontrol/manu.db
sudo chown www-data:www-data /var/lib/manucontrol/manu.db
sudo systemctl start manucontrol
```

## Importar equipamentos (CSV)

1. Login como **fiscal** na filial desejada
2. Menu **Edição → Importar lista de ativos**
3. CSV com colunas `nome` e `codigo` (separador `;` ou `,`)

Modelo: `back/data/exemplo_ativos.csv`

Também é possível baixar modelo Excel em **Edição → Baixar modelo**.

## Relatórios exportados

Na tela **Relatórios** (`/relatorios`), o gerente exporta:

| Botão | Conteúdo |
|-------|----------|
| **Manutenções** | Ranking, OS abertas/encerradas, ações do fiscal |
| **Diário — Hoje** | Tudo que o fiscal registrou hoje |
| **Diário — Ontem** | Registros do dia anterior |
| **CSV** | Planilha de ciclos de manutenção |

No **Admin → Histórico**, exporta PDF diário ou mensal por filial.

## Fluxo da ordem de serviço

1. Fiscal marca equipamento **em manutenção** (check-in ou edição)
2. OS aberta com fase inicial (planejamento)
3. Durante a manutenção: altera fase, responsável, local, anotações
4. **Encerrar e voltar para Ativo** quando concluída

Regra: o fiscal **só adiciona** informações — não apaga histórico de observações.

## Administração de filiais e usuários

- **Admin → Filiais:** editar nome/código, desativar base
- **Admin → Usuários:** criar gerente/fiscal por filial, resetar senha, desativar

Ao criar nova filial manualmente no banco, rode `python back/seed.py` ou use o painel admin.

## Monitoramento básico

Verifique periodicamente:

- Serviço ativo (`systemctl status manucontrol`)
- Espaço em disco (backups + banco crescem com o tempo)
- Logs de erro do Gunicorn/Nginx

Tamanho típico do banco: pequeno (MB) para dezenas de filiais com histórico moderado.

## Contatos e suporte interno

Documente internamente:

- Responsável pelo servidor
- URL de produção
- Procedimento de restore testado
- Frequência de backup validada
