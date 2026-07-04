import csv
import io
import json
import os
import sqlite3
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from db import get_conn, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_ATIVOS = os.path.join(BASE_DIR, "data", "ativos.json")

LOCAIS = {
    "base": "Na base",
    "servico": "Em serviço externo",
    "deslocamento": "Em deslocamento",
    "terceiros": "Em terceiros",
}

LOCAIS_VALIDOS = tuple(LOCAIS.keys())


def _row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    d["id"] = str(d["id"])
    if "base_id" in d:
        d["base_id"] = str(d["base_id"])
    for campo in ("em_manutencao", "ativa", "senha_alterada", "ativo"):
        if campo in d:
            d[campo] = bool(d[campo])
    return d


def contar_bases():
    init_db()
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM bases").fetchone()[0]


def listar_bases(ativas_apenas=True):
    init_db()
    sql = "SELECT * FROM bases"
    if ativas_apenas:
        sql += " WHERE ativa = 1"
    sql += " ORDER BY codigo"
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return [_row_to_dict(r) for r in rows]


def obter_base(base_id):
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM bases WHERE id = ?", (int(base_id),)).fetchone()
    return _row_to_dict(row)


def obter_base_resumo(base_id):
    init_db()
    with get_conn() as conn:
        usuarios = conn.execute(
            "SELECT COUNT(*) FROM usuarios WHERE base_id = ?",
            (int(base_id),),
        ).fetchone()[0]
        ativos = conn.execute(
            "SELECT COUNT(*) FROM ativos WHERE base_id = ?",
            (int(base_id),),
        ).fetchone()[0]
        historico = conn.execute(
            "SELECT COUNT(*) FROM historico_ativos WHERE base_id = ?",
            (int(base_id),),
        ).fetchone()[0]
    return {
        "total_usuarios": usuarios,
        "total_ativos": ativos,
        "total_historico": historico,
    }


def listar_bases_admin():
    bases = listar_bases(ativas_apenas=False)
    for base in bases:
        base.update(obter_base_resumo(base["id"]))
    return bases


def admin_atualizar_base(base_id, nome):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("O nome da filial é obrigatório.")

    base = obter_base(base_id)
    if not base:
        raise ValueError("Filial não encontrada.")

    with get_conn() as conn:
        conn.execute(
            "UPDATE bases SET nome = ? WHERE id = ?",
            (nome, int(base_id)),
        )


def admin_excluir_base(base_id):
    base = obter_base(base_id)
    if not base:
        raise ValueError("Filial não encontrada.")

    if contar_bases() <= 1:
        raise ValueError("Não é possível excluir a única filial do sistema.")

    bid = int(base_id)
    with get_conn() as conn:
        conn.execute("DELETE FROM historico_ativos WHERE base_id = ?", (bid,))
        conn.execute("DELETE FROM ativos WHERE base_id = ?", (bid,))
        conn.execute("DELETE FROM usuarios WHERE base_id = ?", (bid,))
        conn.execute("DELETE FROM bases WHERE id = ?", (bid,))

    return base


def autenticar(base_id, usuario, senha):
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM usuarios
            WHERE base_id = ? AND usuario = ? AND ativo = 1
            """,
            (int(base_id), usuario.strip().lower()),
        ).fetchone()

    if row and check_password_hash(row["senha_hash"], senha):
        user = _row_to_dict(row)
        base = obter_base(base_id)
        user["base_nome"] = base["nome"] if base else ""
        user["base_codigo"] = base["codigo"] if base else ""
        return user
    return None


def obter_usuario(base_id, usuario):
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM usuarios
            WHERE base_id = ? AND usuario = ? AND ativo = 1
            """,
            (int(base_id), usuario),
        ).fetchone()
    return _row_to_dict(row)


def atualizar_senha(base_id, usuario, nova_senha):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE usuarios
            SET senha_hash = ?, senha_alterada = 1
            WHERE base_id = ? AND usuario = ?
            """,
            (generate_password_hash(nova_senha), int(base_id), usuario),
        )


def listar_ativos(base_id):
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ativos WHERE base_id = ? ORDER BY codigo",
            (int(base_id),),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def obter_ativo(base_id, ativo_id):
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ativos WHERE id = ? AND base_id = ?",
            (int(ativo_id), int(base_id)),
        ).fetchone()
    return _row_to_dict(row)


def _fmt_status(em_manutencao):
    return "Em manutenção" if em_manutencao else "Operacional"


def _fmt_local(local):
    return LOCAIS.get(local, local or "Na base")


def normalizar_local(local):
    valor = (local or "base").strip().lower()
    return valor if valor in LOCAIS_VALIDOS else "base"


def registrar_historico(
    base_id,
    ativo_id,
    codigo,
    nome,
    acao,
    usuario,
    usuario_nome,
    detalhes,
    em_manutencao=None,
    local=None,
    ordem_servico=None,
):
    agora = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO historico_ativos
                (base_id, ativo_id, codigo, nome, acao, usuario, usuario_nome,
                 detalhes, em_manutencao, local, ordem_servico, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(base_id),
                int(ativo_id) if ativo_id else None,
                codigo,
                nome,
                acao,
                usuario,
                usuario_nome or usuario,
                detalhes,
                int(em_manutencao) if em_manutencao is not None else None,
                local,
                ordem_servico or "",
                agora,
            ),
        )


def _detalhes_edicao(antigo, novo):
    mudancas = []
    if bool(antigo["em_manutencao"]) != bool(novo["em_manutencao"]):
        mudancas.append(
            f"Status: {_fmt_status(antigo['em_manutencao'])} → {_fmt_status(novo['em_manutencao'])}"
        )
    if antigo.get("local") != novo.get("local"):
        mudancas.append(
            f"Local: {_fmt_local(antigo.get('local', 'base'))} → {_fmt_local(novo.get('local', 'base'))}"
        )
    if (antigo.get("ordem_servico") or "") != (novo.get("ordem_servico") or ""):
        mudancas.append(
            f"OS: '{antigo.get('ordem_servico') or '—'}' → '{novo.get('ordem_servico') or '—'}'"
        )
    if (antigo.get("observacoes") or "") != (novo.get("observacoes") or ""):
        mudancas.append("Observações atualizadas")
    if antigo.get("nome") != novo.get("nome"):
        mudancas.append(f"Nome: '{antigo['nome']}' → '{novo['nome']}'")
    if antigo.get("codigo") != novo.get("codigo"):
        mudancas.append(f"Código: '{antigo['codigo']}' → '{novo['codigo']}'")
    return " · ".join(mudancas) if mudancas else "Registro atualizado"


def salvar_ativo(base_id, ativo_id, dados, usuario=None, usuario_nome=None):
    antigo = obter_ativo(base_id, ativo_id)
    if not antigo:
        return

    nome = (dados.get("nome") or antigo["nome"]).strip()
    codigo = (dados.get("codigo") or antigo["codigo"]).strip()
    if not nome or not codigo:
        raise ValueError("Nome e código são obrigatórios.")

    novo = {
        "nome": nome,
        "codigo": codigo,
        "em_manutencao": bool(dados["em_manutencao"]),
        "local": normalizar_local(dados.get("local", "base")),
        "ordem_servico": dados["ordem_servico"],
        "observacoes": dados["observacoes"],
    }
    agora = datetime.now().isoformat(timespec="seconds")

    try:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE ativos
                SET nome = ?, codigo = ?, em_manutencao = ?, local = ?, ordem_servico = ?,
                    observacoes = ?, atualizado_em = ?
                WHERE id = ? AND base_id = ?
                """,
                (
                    novo["nome"],
                    novo["codigo"],
                    int(novo["em_manutencao"]),
                    novo["local"],
                    novo["ordem_servico"],
                    novo["observacoes"],
                    agora,
                    int(ativo_id),
                    int(base_id),
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Já existe um ativo com este código nesta filial.") from exc

    if usuario:
        registrar_historico(
            base_id,
            ativo_id,
            novo["codigo"],
            novo["nome"],
            "edicao",
            usuario,
            usuario_nome,
            _detalhes_edicao(antigo, novo),
            em_manutencao=novo["em_manutencao"],
            local=novo["local"],
            ordem_servico=novo["ordem_servico"],
        )


def excluir_ativo(base_id, ativo_id, usuario=None, usuario_nome=None):
    antigo = obter_ativo(base_id, ativo_id)
    if not antigo:
        return False

    with get_conn() as conn:
        conn.execute(
            "DELETE FROM ativos WHERE id = ? AND base_id = ?",
            (int(ativo_id), int(base_id)),
        )

    if usuario:
        registrar_historico(
            base_id,
            None,
            antigo["codigo"],
            antigo["nome"],
            "exclusao",
            usuario,
            usuario_nome,
            f"Ativo excluído · {antigo['codigo']} — {antigo['nome']}",
            em_manutencao=antigo["em_manutencao"],
            local=antigo.get("local"),
            ordem_servico=antigo.get("ordem_servico", ""),
        )

    return True


def criar_ativo(base_id, dados, usuario=None, usuario_nome=None):
    agora = datetime.now().isoformat(timespec="seconds")
    try:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO ativos
                    (base_id, nome, codigo, local, em_manutencao,
                     ordem_servico, observacoes, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(base_id),
                    dados["nome"],
                    dados["codigo"],
                    normalizar_local(dados.get("local", "base")),
                    int(dados.get("em_manutencao", False)),
                    dados.get("ordem_servico", ""),
                    dados.get("observacoes", ""),
                    agora,
                ),
            )
            novo_id = str(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise ValueError("Já existe um ativo com este código nesta filial.") from exc

    if usuario:
        registrar_historico(
            base_id,
            novo_id,
            dados["codigo"],
            dados["nome"],
            "criacao",
            usuario,
            usuario_nome,
            f"Ativo cadastrado · {_fmt_status(dados.get('em_manutencao', False))} · {_fmt_local(dados.get('local', 'base'))}",
            em_manutencao=dados.get("em_manutencao", False),
            local=dados.get("local", "base"),
            ordem_servico=dados.get("ordem_servico", ""),
        )
    return novo_id


def importar_ativos_csv(base_id, conteudo_bytes, substituir=False, usuario=None, usuario_nome=None):
    texto = conteudo_bytes.decode("utf-8-sig")
    leitor = csv.DictReader(io.StringIO(texto))

    if not leitor.fieldnames:
        raise ValueError("Arquivo CSV vazio ou sem cabeçalho.")

    campos = {c.strip().lower() for c in leitor.fieldnames}
    if "codigo" not in campos or "nome" not in campos:
        raise ValueError("O CSV deve conter as colunas: nome, codigo")

    linhas = []
    codigos_vistos = set()
    for i, row in enumerate(leitor, start=2):
        nome = (row.get("nome") or row.get("Nome") or "").strip()
        codigo = (row.get("codigo") or row.get("Codigo") or row.get("Código") or "").strip()
        if not nome and not codigo:
            continue
        if not nome or not codigo:
            raise ValueError(f"Linha {i}: nome e codigo são obrigatórios.")
        codigo_upper = codigo.upper()
        if codigo_upper in codigos_vistos:
            raise ValueError(f"Linha {i}: código duplicado no arquivo ({codigo}).")
        codigos_vistos.add(codigo_upper)
        linhas.append({"nome": nome, "codigo": codigo})

    if not linhas:
        raise ValueError("Nenhum ativo válido encontrado no arquivo.")

    agora = datetime.now().isoformat(timespec="seconds")
    inseridos = 0
    atualizados = 0
    base_int = int(base_id)

    with get_conn() as conn:
        if substituir:
            removidos = conn.execute(
                "SELECT COUNT(*) FROM ativos WHERE base_id = ?", (base_int,)
            ).fetchone()[0]
            conn.execute("DELETE FROM ativos WHERE base_id = ?", (base_int,))
            if usuario and removidos:
                registrar_historico(
                    base_id,
                    None,
                    "—",
                    "Importação CSV",
                    "importacao",
                    usuario,
                    usuario_nome,
                    f"Lista substituída — {removidos} ativo(s) removido(s) antes da importação",
                )

        for item in linhas:
            existente = conn.execute(
                "SELECT id, nome FROM ativos WHERE base_id = ? AND codigo = ?",
                (base_int, item["codigo"]),
            ).fetchone()

            if existente:
                conn.execute(
                    """
                    UPDATE ativos SET nome = ?, atualizado_em = ?
                    WHERE id = ?
                    """,
                    (item["nome"], agora, existente["id"]),
                )
                atualizados += 1
                if usuario:
                    registrar_historico(
                        base_id,
                        existente["id"],
                        item["codigo"],
                        item["nome"],
                        "importacao",
                        usuario,
                        usuario_nome,
                        f"Nome atualizado via CSV (era: {existente['nome']})",
                    )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO ativos
                        (base_id, nome, codigo, local, em_manutencao,
                         ordem_servico, observacoes, atualizado_em)
                    VALUES (?, ?, ?, 'base', 0, '', '', ?)
                    """,
                    (base_int, item["nome"], item["codigo"], agora),
                )
                inseridos += 1
                if usuario:
                    registrar_historico(
                        base_id,
                        cur.lastrowid,
                        item["codigo"],
                        item["nome"],
                        "importacao",
                        usuario,
                        usuario_nome,
                        "Ativo incluído via importação CSV",
                        em_manutencao=False,
                        local="base",
                    )

    if usuario and not substituir:
        pass  # registros individuais já gravados acima

    return {"inseridos": inseridos, "atualizados": atualizados, "total": len(linhas)}


def seed_bases(qtd=20):
    init_db()
    if contar_bases() > 0:
        return {"criadas": 0, "mensagem": "Bases já existem no banco."}

    senha_padrao = generate_password_hash("1234")
    bases_criadas = 0
    usuarios_criados = 0

    with get_conn() as conn:
        for i in range(1, qtd + 1):
            codigo = f"{i:02d}"
            cur = conn.execute(
                "INSERT INTO bases (codigo, nome, ativa) VALUES (?, ?, 1)",
                (codigo, f"Filial {codigo}"),
            )
            base_id = cur.lastrowid
            bases_criadas += 1

            for usuario, nome, nivel in [
                ("gerente", f"Gerente Filial {codigo}", "gerente"),
                ("fiscal", f"Fiscal Filial {codigo}", "fiscal"),
            ]:
                conn.execute(
                    """
                    INSERT INTO usuarios
                        (base_id, usuario, senha_hash, nome, nivel, senha_alterada, ativo)
                    VALUES (?, ?, ?, ?, ?, 0, 1)
                    """,
                    (base_id, usuario, senha_padrao, nome, nivel),
                )
                usuarios_criados += 1

    return {
        "criadas": bases_criadas,
        "usuarios": usuarios_criados,
        "mensagem": f"{bases_criadas} filiais criadas com gerente e fiscal cada.",
    }


def migrar_json_legacy(base_codigo="01"):
    init_db()
    with get_conn() as conn:
        base = conn.execute(
            "SELECT id FROM bases WHERE codigo = ?", (base_codigo,)
        ).fetchone()

    if not base:
        raise ValueError(f"Filial {base_codigo} não encontrada. Execute o seed primeiro.")

    base_id = base["id"]
    agora = datetime.now().isoformat(timespec="seconds")

    if os.path.exists(LEGACY_ATIVOS):
        with open(LEGACY_ATIVOS, "r", encoding="utf-8") as f:
            ativos = json.load(f)

        with get_conn() as conn:
            for a in ativos:
                conn.execute(
                    """
                    INSERT INTO ativos
                        (base_id, nome, codigo, local, em_manutencao,
                         ordem_servico, observacoes, atualizado_em)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(base_id, codigo) DO UPDATE SET
                        nome = excluded.nome,
                        local = excluded.local,
                        em_manutencao = excluded.em_manutencao,
                        ordem_servico = excluded.ordem_servico,
                        observacoes = excluded.observacoes,
                        atualizado_em = excluded.atualizado_em
                    """,
                    (
                        base_id,
                        a["nome"],
                        a["codigo"],
                        a.get("local", "base"),
                        int(a.get("em_manutencao", False)),
                        a.get("ordem_servico", ""),
                        a.get("observacoes", ""),
                        a.get("atualizado_em", agora),
                    ),
                )

    return {"base": base_codigo, "mensagem": "Migração concluída."}


# --- Relatórios ---


def _historico_dict(row):
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("ativo_id"):
        d["ativo_id"] = str(d["ativo_id"])
    if d.get("em_manutencao") is not None:
        d["em_manutencao"] = bool(d["em_manutencao"])
    return d


ACAO_LABEL = {
    "criacao": "Cadastro",
    "edicao": "Edição",
    "importacao": "Importação CSV",
    "exclusao": "Exclusão",
}


def relatorio_diario(base_id, data_ref=None):
    init_db()
    if not data_ref:
        data_ref = datetime.now().strftime("%Y-%m-%d")

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM historico_ativos
            WHERE base_id = ? AND date(criado_em) = date(?)
            ORDER BY criado_em DESC
            """,
            (int(base_id), data_ref),
        ).fetchall()

    registros = [_historico_dict(r) for r in rows]
    por_acao = {}
    for r in registros:
        por_acao[r["acao"]] = por_acao.get(r["acao"], 0) + 1

    return {
        "data": data_ref,
        "registros": registros,
        "total": len(registros),
        "por_acao": por_acao,
    }


def relatorio_mensal(base_id, ano, mes):
    init_db()
    mes_str = f"{int(mes):02d}"
    ano_str = str(int(ano))

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM historico_ativos
            WHERE base_id = ?
              AND strftime('%Y', criado_em) = ?
              AND strftime('%m', criado_em) = ?
            ORDER BY criado_em DESC
            """,
            (int(base_id), ano_str, mes_str),
        ).fetchall()

        por_dia_rows = conn.execute(
            """
            SELECT date(criado_em) AS dia, COUNT(*) AS total
            FROM historico_ativos
            WHERE base_id = ?
              AND strftime('%Y', criado_em) = ?
              AND strftime('%m', criado_em) = ?
            GROUP BY date(criado_em)
            ORDER BY dia DESC
            """,
            (int(base_id), ano_str, mes_str),
        ).fetchall()

    registros = [_historico_dict(r) for r in rows]
    por_acao = {}
    ativos_alterados = set()
    for r in registros:
        por_acao[r["acao"]] = por_acao.get(r["acao"], 0) + 1
        if r.get("codigo") and r["codigo"] != "—":
            ativos_alterados.add(r["codigo"])

    ativos = listar_ativos(base_id)
    em_manutencao = sum(1 for a in ativos if a.get("em_manutencao"))

    por_dia = [{"dia": row["dia"], "total": row["total"]} for row in por_dia_rows]

    return {
        "ano": int(ano),
        "mes": int(mes),
        "registros": registros,
        "total": len(registros),
        "por_acao": por_acao,
        "por_dia": por_dia,
        "dias_com_atividade": len(por_dia),
        "ativos_movimentados": len(ativos_alterados),
        "snapshot": {
            "total_ativos": len(ativos),
            "operacionais": len(ativos) - em_manutencao,
            "manutencao": em_manutencao,
        },
    }


# --- Admin ---


def autenticar_admin(usuario, senha):
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM admins
            WHERE usuario = ? AND ativo = 1
            """,
            (usuario.strip().lower(),),
        ).fetchone()

    if row and check_password_hash(row["senha_hash"], senha):
        d = dict(row)
        d["id"] = str(d["id"])
        d["ativo"] = bool(d["ativo"])
        return d
    return None


def obter_admin(admin_id):
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM admins WHERE id = ?", (int(admin_id),)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["id"] = str(d["id"])
    d["ativo"] = bool(d["ativo"])
    return d


def listar_todos_usuarios(base_id=None):
    init_db()
    sql = """
        SELECT u.*, b.codigo AS base_codigo, b.nome AS base_nome
        FROM usuarios u
        JOIN bases b ON b.id = u.base_id
    """
    params = []
    if base_id:
        sql += " WHERE u.base_id = ?"
        params.append(int(base_id))
    sql += " ORDER BY b.codigo, u.nivel, u.usuario"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    result = []
    for row in rows:
        d = _row_to_dict(row)
        d["base_codigo"] = row["base_codigo"]
        d["base_nome"] = row["base_nome"]
        result.append(d)
    return result


def obter_usuario_por_id(user_id):
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.*, b.codigo AS base_codigo, b.nome AS base_nome
            FROM usuarios u
            JOIN bases b ON b.id = u.base_id
            WHERE u.id = ?
            """,
            (int(user_id),),
        ).fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    d["base_codigo"] = row["base_codigo"]
    d["base_nome"] = row["base_nome"]
    return d


def admin_resetar_senha(user_id, nova_senha):
    if len(nova_senha) < 4:
        raise ValueError("A senha deve ter pelo menos 4 caracteres.")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE usuarios
            SET senha_hash = ?, senha_alterada = 0
            WHERE id = ?
            """,
            (generate_password_hash(nova_senha), int(user_id)),
        )


def admin_toggle_usuario(user_id, ativo):
    with get_conn() as conn:
        conn.execute(
            "UPDATE usuarios SET ativo = ? WHERE id = ?",
            (int(ativo), int(user_id)),
        )


def admin_atualizar_usuario(user_id, nome, nivel):
    if nivel not in ("gerente", "fiscal"):
        raise ValueError("Nível inválido. Use gerente ou fiscal.")
    if not nome.strip():
        raise ValueError("Nome é obrigatório.")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE usuarios SET nome = ?, nivel = ?
            WHERE id = ?
            """,
            (nome.strip(), nivel, int(user_id)),
        )


def admin_criar_usuario(base_id, usuario, nome, nivel, senha):
    usuario = usuario.strip().lower()
    if not usuario or not nome.strip():
        raise ValueError("Usuário e nome são obrigatórios.")
    if nivel not in ("gerente", "fiscal"):
        raise ValueError("Nível inválido. Use gerente ou fiscal.")
    if len(senha) < 4:
        raise ValueError("A senha deve ter pelo menos 4 caracteres.")
    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO usuarios
                    (base_id, usuario, senha_hash, nome, nivel, senha_alterada, ativo)
                VALUES (?, ?, ?, ?, ?, 0, 1)
                """,
                (
                    int(base_id),
                    usuario,
                    generate_password_hash(senha),
                    nome.strip(),
                    nivel,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Já existe este usuário nesta filial.") from exc


def admin_alterar_senha_admin(admin_id, senha_atual, nova_senha):
    admin = obter_admin(admin_id)
    if not admin or not check_password_hash(admin["senha_hash"], senha_atual):
        raise ValueError("Senha atual incorreta.")
    if len(nova_senha) < 4:
        raise ValueError("A nova senha deve ter pelo menos 4 caracteres.")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE admins SET senha_hash = ? WHERE id = ?
            """,
            (generate_password_hash(nova_senha), int(admin_id)),
        )
