"""Ciclo de manutenção e relatórios de equipamentos de limpeza urbana."""
import csv
import io
import sqlite3
from datetime import datetime

from db import get_conn, init_db

# Importações tardias evitam ciclo — funções compartilhadas via services


def _bind():
    from services import (
        LOCAIS_MANUTENCAO_VALIDOS,
        TIPOS_EQUIPAMENTO,
        _fmt_status,
        _fmt_tipo,
        _row_to_dict,
        listar_ativos,
        normalizar_local,
        normalizar_tipo,
        obter_ativo,
        registrar_historico,
    )

    return {
        "LOCAIS_MANUTENCAO_VALIDOS": LOCAIS_MANUTENCAO_VALIDOS,
        "TIPOS_EQUIPAMENTO": TIPOS_EQUIPAMENTO,
        "_fmt_status": _fmt_status,
        "_fmt_tipo": _fmt_tipo,
        "_row_to_dict": _row_to_dict,
        "listar_ativos": listar_ativos,
        "normalizar_local": normalizar_local,
        "normalizar_tipo": normalizar_tipo,
        "obter_ativo": obter_ativo,
        "registrar_historico": registrar_historico,
    }


def _parse_data(valor, campo="data"):
    valor = (valor or "").strip()
    if not valor:
        raise ValueError(f"Informe a {campo}.")
    try:
        if len(valor) == 10:
            datetime.strptime(valor, "%Y-%m-%d")
            return valor
        dt = datetime.fromisoformat(valor)
        return dt.strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{campo.capitalize()} inválida.") from exc


def _dias_entre(abertura, conclusao):
    try:
        a = datetime.strptime(str(abertura)[:10], "%Y-%m-%d")
        c = datetime.strptime(str(conclusao)[:10], "%Y-%m-%d")
        return max((c - a).days, 0)
    except (ValueError, TypeError):
        return None


def obter_manutencao_aberta(base_id, ativo_id, conn=None):
    s = _bind()
    sql = """
        SELECT * FROM manutencoes
        WHERE base_id = ? AND ativo_id = ? AND aberta = 1
        ORDER BY id DESC LIMIT 1
    """
    params = (int(base_id), int(ativo_id))
    if conn is not None:
        row = conn.execute(sql, params).fetchone()
    else:
        init_db()
        with get_conn() as db:
            row = db.execute(sql, params).fetchone()
    return s["_row_to_dict"](row)


def listar_manutencoes_ativo(base_id, ativo_id):
    s = _bind()
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM manutencoes
            WHERE base_id = ? AND ativo_id = ?
            ORDER BY data_abertura DESC, id DESC
            """,
            (int(base_id), int(ativo_id)),
        ).fetchall()
    return [s["_row_to_dict"](r) for r in rows]


def listar_manutencoes_base(base_id, apenas_abertas=False):
    s = _bind()
    init_db()
    sql = """
        SELECT m.*, a.codigo AS ativo_codigo, a.nome AS ativo_nome, a.tipo AS ativo_tipo
        FROM manutencoes m
        JOIN ativos a ON a.id = m.ativo_id
        WHERE m.base_id = ?
    """
    params = [int(base_id)]
    if apenas_abertas:
        sql += " AND m.aberta = 1"
    sql += " ORDER BY m.data_abertura DESC, m.id DESC"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = s["_row_to_dict"](r)
        d["ativo_codigo"] = r["ativo_codigo"]
        d["ativo_nome"] = r["ativo_nome"]
        d["ativo_tipo"] = r["ativo_tipo"]
        d["tipo_label"] = s["_fmt_tipo"](r["ativo_tipo"])
        d["dias_parado"] = (
            _dias_entre(r["data_abertura"], r["data_conclusao"])
            if r["data_conclusao"]
            else None
        )
        result.append(d)
    return result


def abrir_manutencao(base_id, ativo_id, dados, usuario=None, usuario_nome=None):
    s = _bind()
    ativo = s["obter_ativo"](base_id, ativo_id)
    if not ativo:
        raise ValueError("Equipamento não encontrado.")
    if ativo.get("em_manutencao"):
        raise ValueError("Este equipamento já está em manutenção.")
    if obter_manutencao_aberta(base_id, ativo_id):
        raise ValueError("Já existe uma OS aberta para este equipamento.")

    os_numero = (dados.get("os_numero") or dados.get("ordem_servico") or "").strip()
    if not os_numero:
        raise ValueError("Informe o número da OS.")
    data_abertura = _parse_data(dados.get("data_abertura"), "data de abertura da OS")
    observacoes = (
        dados.get("observacoes") or dados.get("observacoes_abertura") or ""
    ).strip()
    if not observacoes:
        raise ValueError("Informe as observações / motivo da manutenção.")
    responsavel = (dados.get("responsavel") or "").strip()
    if not responsavel:
        responsavel = (usuario_nome or usuario or "").strip()
    if not responsavel:
        raise ValueError("Informe o responsável pela abertura da OS.")

    local = s["normalizar_local"](dados.get("local", "base"))
    if local not in s["LOCAIS_MANUTENCAO_VALIDOS"]:
        local = "base"

    agora = datetime.now().isoformat(timespec="seconds")

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO manutencoes
                (base_id, ativo_id, os_numero, data_abertura, observacoes_abertura,
                 responsavel, data_conclusao, observacoes_encerramento, aberta,
                 criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, NULL, '', 1, ?, ?)
            """,
            (
                int(base_id),
                int(ativo_id),
                os_numero,
                data_abertura,
                observacoes,
                responsavel,
                agora,
                agora,
            ),
        )
        manut_id = str(cur.lastrowid)

        conn.execute(
            """
            UPDATE ativos
            SET em_manutencao = 1, ordem_servico = ?, observacoes = ?,
                local = ?, atualizado_em = ?
            WHERE id = ? AND base_id = ?
            """,
            (os_numero, observacoes, local, agora, int(ativo_id), int(base_id)),
        )

        s["registrar_historico"](
            base_id,
            ativo_id,
            ativo["codigo"],
            ativo["nome"],
            "manutencao_abertura",
            usuario or "fiscal",
            usuario_nome or responsavel,
            f"OS {os_numero} aberta · {responsavel} · {observacoes[:120]}",
            em_manutencao=True,
            local=local,
            ordem_servico=os_numero,
            conn=conn,
        )

    return manut_id


def encerrar_manutencao(base_id, ativo_id, dados, usuario=None, usuario_nome=None):
    s = _bind()
    ativo = s["obter_ativo"](base_id, ativo_id)
    if not ativo:
        raise ValueError("Equipamento não encontrado.")

    aberta = obter_manutencao_aberta(base_id, ativo_id)
    if not aberta:
        raise ValueError("Não há manutenção aberta para este equipamento.")

    data_conclusao = _parse_data(
        dados.get("data_conclusao"), "data de conclusão da manutenção"
    )
    if data_conclusao < str(aberta["data_abertura"])[:10]:
        raise ValueError("A data de conclusão não pode ser anterior à abertura da OS.")

    observacoes_enc = (dados.get("observacoes_encerramento") or "").strip()
    if not observacoes_enc:
        raise ValueError("Informe as observações de encerramento (o que foi feito).")

    agora = datetime.now().isoformat(timespec="seconds")

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE manutencoes
            SET data_conclusao = ?, observacoes_encerramento = ?, aberta = 0,
                atualizado_em = ?
            WHERE id = ? AND base_id = ?
            """,
            (
                data_conclusao,
                observacoes_enc,
                agora,
                int(aberta["id"]),
                int(base_id),
            ),
        )

        conn.execute(
            """
            UPDATE ativos
            SET em_manutencao = 0, ordem_servico = '', observacoes = ?,
                local = 'base', atualizado_em = ?
            WHERE id = ? AND base_id = ?
            """,
            (observacoes_enc, agora, int(ativo_id), int(base_id)),
        )

        s["registrar_historico"](
            base_id,
            ativo_id,
            ativo["codigo"],
            ativo["nome"],
            "manutencao_encerramento",
            usuario or "fiscal",
            usuario_nome or usuario or "fiscal",
            f"OS {aberta['os_numero']} encerrada · {observacoes_enc[:120]}",
            em_manutencao=False,
            local="base",
            ordem_servico=aberta["os_numero"],
            conn=conn,
        )

    return aberta["id"]


def stats_ativo(base_id, ativo_id):
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT os_numero, data_abertura, data_conclusao, aberta
            FROM manutencoes
            WHERE base_id = ? AND ativo_id = ?
            ORDER BY id DESC
            """,
            (int(base_id), int(ativo_id)),
        ).fetchall()

    total = len(rows)
    dias = []
    ultima_os = None
    manut_aberta_obj = None
    for r in rows:
        if ultima_os is None:
            ultima_os = r["os_numero"]
        if r["aberta"]:
            manut_aberta_obj = {
                "os_numero": r["os_numero"],
                "data_abertura": r["data_abertura"],
                "aberta": True,
            }
        elif r["data_conclusao"]:
            d = _dias_entre(r["data_abertura"], r["data_conclusao"])
            if d is not None:
                dias.append(d)

    return {
        "total_manutencoes": total,
        "tempo_medio_dias": round(sum(dias) / len(dias), 1) if dias else None,
        "ultima_os": ultima_os,
        "manutencao_aberta": manut_aberta_obj,
        "ciclos_fechados": len(dias),
    }


def listar_ativos_com_stats(base_id):
    s = _bind()
    ativos = s["listar_ativos"](base_id)
    for a in ativos:
        a["stats"] = stats_ativo(base_id, a["id"])
        a["tipo_label"] = s["_fmt_tipo"](a.get("tipo"))
        a["status_label"] = s["_fmt_status"](a.get("em_manutencao"))
    return ativos


def equipamento_detalhe(base_id, ativo_id):
    s = _bind()
    ativo = s["obter_ativo"](base_id, ativo_id)
    if not ativo:
        return None
    ativo["tipo_label"] = s["_fmt_tipo"](ativo.get("tipo"))
    ativo["status_label"] = s["_fmt_status"](ativo.get("em_manutencao"))
    ativo["stats"] = stats_ativo(base_id, ativo_id)
    ativo["manutencoes"] = listar_manutencoes_ativo(base_id, ativo_id)
    ativo["manutencao_aberta"] = obter_manutencao_aberta(base_id, ativo_id)
    return ativo


def relatorio_manutencoes(base_id):
    s = _bind()
    init_db()
    ativos = s["listar_ativos"](base_id)
    ranking = []
    todos_dias = []

    with get_conn() as conn:
        for a in ativos:
            rows = conn.execute(
                """
                SELECT os_numero, data_abertura, data_conclusao, aberta
                FROM manutencoes
                WHERE base_id = ? AND ativo_id = ?
                """,
                (int(base_id), int(a["id"])),
            ).fetchall()
            dias = []
            abertas = 0
            for r in rows:
                if r["aberta"]:
                    abertas += 1
                elif r["data_conclusao"]:
                    d = _dias_entre(r["data_abertura"], r["data_conclusao"])
                    if d is not None:
                        dias.append(d)
                        todos_dias.append(d)
            ranking.append(
                {
                    "id": a["id"],
                    "codigo": a["codigo"],
                    "nome": a["nome"],
                    "tipo": a.get("tipo") or "",
                    "tipo_label": s["_fmt_tipo"](a.get("tipo")),
                    "total_manutencoes": len(rows),
                    "abertas": abertas,
                    "tempo_medio_dias": round(sum(dias) / len(dias), 1) if dias else None,
                    "em_manutencao": a.get("em_manutencao"),
                }
            )

        ciclos = conn.execute(
            """
            SELECT m.*, a.codigo AS ativo_codigo, a.nome AS ativo_nome, a.tipo AS ativo_tipo
            FROM manutencoes m
            JOIN ativos a ON a.id = m.ativo_id
            WHERE m.base_id = ?
            ORDER BY m.data_abertura DESC, m.id DESC
            """,
            (int(base_id),),
        ).fetchall()

    ranking.sort(key=lambda x: (-x["total_manutencoes"], x["codigo"]))
    ciclos_list = []
    for r in ciclos:
        d = s["_row_to_dict"](r)
        d["ativo_codigo"] = r["ativo_codigo"]
        d["ativo_nome"] = r["ativo_nome"]
        d["ativo_tipo"] = r["ativo_tipo"]
        d["tipo_label"] = s["_fmt_tipo"](r["ativo_tipo"])
        d["dias_parado"] = (
            _dias_entre(r["data_abertura"], r["data_conclusao"])
            if r["data_conclusao"]
            else None
        )
        ciclos_list.append(d)

    return {
        "ranking": ranking,
        "ciclos": ciclos_list,
        "total_ciclos": len(ciclos_list),
        "tempo_medio_geral": (
            round(sum(todos_dias) / len(todos_dias), 1) if todos_dias else None
        ),
        "equipamentos_com_manutencao": sum(
            1 for r in ranking if r["total_manutencoes"] > 0
        ),
        "em_manutencao_agora": sum(1 for a in ativos if a.get("em_manutencao")),
        "total_equipamentos": len(ativos),
    }


def export_csv_manutencoes(base_id):
    rel = relatorio_manutencoes(base_id)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        [
            "codigo",
            "nome",
            "tipo",
            "os_numero",
            "data_abertura",
            "responsavel",
            "observacoes_abertura",
            "data_conclusao",
            "observacoes_encerramento",
            "status",
            "dias_parado",
        ]
    )
    for c in rel["ciclos"]:
        writer.writerow(
            [
                c.get("ativo_codigo", ""),
                c.get("ativo_nome", ""),
                c.get("tipo_label", ""),
                c.get("os_numero", ""),
                c.get("data_abertura", ""),
                c.get("responsavel", ""),
                c.get("observacoes_abertura", ""),
                c.get("data_conclusao") or "",
                c.get("observacoes_encerramento", ""),
                "Aberta" if c.get("aberta") else "Encerrada",
                c.get("dias_parado") if c.get("dias_parado") is not None else "",
            ]
        )
    return buf.getvalue()
