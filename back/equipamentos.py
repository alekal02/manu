"""Ciclo de manutenção e relatórios de equipamentos de limpeza urbana."""
import csv
import io
import sqlite3
from collections import defaultdict
from datetime import datetime

from db import get_conn, init_db

# Importações tardias evitam ciclo — funções compartilhadas via services


def _bind():
    from services import (
        LOCAIS_MANUTENCAO_VALIDOS,
        TIPOS_EQUIPAMENTO,
        FASE_OS_PADRAO,
        FASES_OS,
        _fmt_fase,
        _fmt_status,
        _fmt_tipo,
        _row_to_dict,
        listar_ativos,
        normalizar_local,
        normalizar_tipo,
        normalizar_fase,
        validar_fiscal_nao_remove_campo,
        obter_ativo,
        registrar_historico,
    )

    return {
        "LOCAIS_MANUTENCAO_VALIDOS": LOCAIS_MANUTENCAO_VALIDOS,
        "TIPOS_EQUIPAMENTO": TIPOS_EQUIPAMENTO,
        "FASE_OS_PADRAO": FASE_OS_PADRAO,
        "FASES_OS": FASES_OS,
        "_fmt_fase": _fmt_fase,
        "_fmt_status": _fmt_status,
        "_fmt_tipo": _fmt_tipo,
        "_row_to_dict": _row_to_dict,
        "listar_ativos": listar_ativos,
        "normalizar_local": normalizar_local,
        "normalizar_tipo": normalizar_tipo,
        "normalizar_fase": normalizar_fase,
        "validar_fiscal_nao_remove_campo": validar_fiscal_nao_remove_campo,
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
    return _enriquecer_manutencao(s["_row_to_dict"](row), s)


def _enriquecer_manutencao(d, s):
    if not d:
        return d
    fase = s["normalizar_fase"](d.get("fase"))
    d["fase"] = fase
    d["fase_label"] = s["_fmt_fase"](fase)
    return d


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
    return [_enriquecer_manutencao(s["_row_to_dict"](r), s) for r in rows]


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
        d = _enriquecer_manutencao(s["_row_to_dict"](r), s)
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
                 fase, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, NULL, '', 1, ?, ?, ?)
            """,
            (
                int(base_id),
                int(ativo_id),
                os_numero,
                data_abertura,
                observacoes,
                responsavel,
                s["FASE_OS_PADRAO"],
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
            f"OS {os_numero} aberta · Fase {s['_fmt_fase'](s['FASE_OS_PADRAO'])} · {responsavel} · {observacoes[:120]}",
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
    stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    obs_atual = (ativo.get("observacoes") or "").strip()
    linha_enc = f"[{stamp} · ENCERRAMENTO OS {aberta['os_numero']}] {observacoes_enc}"
    obs_final = f"{obs_atual}\n{linha_enc}" if obs_atual else linha_enc

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
            (obs_final, agora, int(ativo_id), int(base_id)),
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


def atualizar_fase_manutencao(
    base_id, ativo_id, fase, observacao="", usuario=None, usuario_nome=None
):
    s = _bind()
    ativo = s["obter_ativo"](base_id, ativo_id)
    if not ativo:
        raise ValueError("Equipamento não encontrado.")

    aberta = obter_manutencao_aberta(base_id, ativo_id)
    if not aberta:
        raise ValueError("Não há OS aberta para alterar a fase.")

    nova_fase = s["normalizar_fase"](fase)
    fase_atual = s["normalizar_fase"](aberta.get("fase"))
    if nova_fase == fase_atual:
        raise ValueError("A OS já está nesta fase.")

    observacao = (observacao or "").strip()
    agora = datetime.now().isoformat(timespec="seconds")
    fase_anterior_label = s["_fmt_fase"](fase_atual)
    fase_nova_label = s["_fmt_fase"](nova_fase)
    detalhes = f"OS {aberta['os_numero']} · {fase_anterior_label} → {fase_nova_label}"
    if observacao:
        detalhes = f"{detalhes} · {observacao[:120]}"

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE manutencoes
            SET fase = ?, atualizado_em = ?
            WHERE id = ? AND base_id = ?
            """,
            (nova_fase, agora, int(aberta["id"]), int(base_id)),
        )

        s["registrar_historico"](
            base_id,
            ativo_id,
            ativo["codigo"],
            ativo["nome"],
            "manutencao_fase",
            usuario or "fiscal",
            usuario_nome or usuario or "fiscal",
            detalhes,
            em_manutencao=True,
            local=ativo.get("local"),
            ordem_servico=aberta["os_numero"],
            conn=conn,
        )

    return aberta["id"]


def listar_anotacoes_manutencao(base_id, manutencao_id):
    s = _bind()
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM manutencao_anotacoes
            WHERE base_id = ? AND manutencao_id = ?
            ORDER BY criado_em DESC, id DESC
            """,
            (int(base_id), int(manutencao_id)),
        ).fetchall()
    result = []
    for r in rows:
        d = s["_row_to_dict"](r)
        d["manutencao_id"] = str(d["manutencao_id"])
        result.append(d)
    return result


def adicionar_anotacao_manutencao(
    base_id, ativo_id, texto, usuario=None, usuario_nome=None
):
    s = _bind()
    ativo = s["obter_ativo"](base_id, ativo_id)
    if not ativo:
        raise ValueError("Equipamento não encontrado.")

    aberta = obter_manutencao_aberta(base_id, ativo_id)
    if not aberta:
        raise ValueError("Não há OS aberta para registrar anotação.")

    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Informe a observação.")

    agora = datetime.now().isoformat(timespec="seconds")
    stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    autor = (usuario_nome or usuario or "fiscal").strip()
    linha = f"[{stamp} · {autor}] {texto}"
    obs_atual = (ativo.get("observacoes") or "").strip()
    obs_nova = f"{obs_atual}\n{linha}" if obs_atual else linha

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO manutencao_anotacoes
                (base_id, manutencao_id, texto, usuario, usuario_nome, criado_em)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(base_id),
                int(aberta["id"]),
                texto,
                usuario or "fiscal",
                usuario_nome or usuario or "fiscal",
                agora,
            ),
        )
        conn.execute(
            """
            UPDATE manutencoes SET atualizado_em = ? WHERE id = ? AND base_id = ?
            """,
            (agora, int(aberta["id"]), int(base_id)),
        )
        conn.execute(
            """
            UPDATE ativos SET observacoes = ?, atualizado_em = ?
            WHERE id = ? AND base_id = ?
            """,
            (obs_nova, agora, int(ativo_id), int(base_id)),
        )
        s["registrar_historico"](
            base_id,
            ativo_id,
            ativo["codigo"],
            ativo["nome"],
            "manutencao_anotacao",
            usuario or "fiscal",
            usuario_nome or usuario or "fiscal",
            f"OS {aberta['os_numero']} · {texto[:160]}",
            em_manutencao=True,
            local=ativo.get("local"),
            ordem_servico=aberta["os_numero"],
            conn=conn,
        )

    return aberta["id"]


def atualizar_dados_os_aberta(
    base_id, ativo_id, dados, usuario=None, usuario_nome=None
):
    s = _bind()
    ativo = s["obter_ativo"](base_id, ativo_id)
    if not ativo:
        raise ValueError("Equipamento não encontrado.")

    aberta = obter_manutencao_aberta(base_id, ativo_id)
    if not aberta:
        raise ValueError("Não há OS aberta para atualizar.")

    responsavel = (dados.get("responsavel") or "").strip()
    local_raw = dados.get("local")
    local = None
    if local_raw is not None and str(local_raw).strip() != "":
        local = s["normalizar_local"](local_raw)
        if local not in s["LOCAIS_MANUTENCAO_VALIDOS"]:
            raise ValueError("Local de manutenção inválido.")

    s["validar_fiscal_nao_remove_campo"](
        aberta.get("responsavel"), responsavel, "responsável da OS"
    )

    if not responsavel and local is None:
        raise ValueError("Informe ao menos responsável ou local para atualizar.")

    agora = datetime.now().isoformat(timespec="seconds")
    alteracoes = []

    with get_conn() as conn:
        if responsavel and responsavel != (aberta.get("responsavel") or ""):
            conn.execute(
                """
                UPDATE manutencoes
                SET responsavel = ?, atualizado_em = ?
                WHERE id = ? AND base_id = ?
                """,
                (responsavel, agora, int(aberta["id"]), int(base_id)),
            )
            alteracoes.append(
                f"Responsável: '{aberta.get('responsavel') or '—'}' → '{responsavel}'"
            )

        if local is not None and local != (ativo.get("local") or "base"):
            conn.execute(
                """
                UPDATE ativos SET local = ?, atualizado_em = ?
                WHERE id = ? AND base_id = ?
                """,
                (local, agora, int(ativo_id), int(base_id)),
            )
            alteracoes.append(f"Local: '{ativo.get('local') or 'base'}' → '{local}'")

        if not alteracoes:
            raise ValueError("Nenhum dado foi alterado.")

        conn.execute(
            """
            UPDATE manutencoes SET atualizado_em = ? WHERE id = ? AND base_id = ?
            """,
            (agora, int(aberta["id"]), int(base_id)),
        )

        s["registrar_historico"](
            base_id,
            ativo_id,
            ativo["codigo"],
            ativo["nome"],
            "manutencao_atualizacao",
            usuario or "fiscal",
            usuario_nome or usuario or "fiscal",
            f"OS {aberta['os_numero']} · " + " · ".join(alteracoes),
            em_manutencao=True,
            local=local or ativo.get("local"),
            ordem_servico=aberta["os_numero"],
            conn=conn,
        )

    return aberta["id"]


def salvar_acompanhamento_os_aberta(
    base_id, ativo_id, dados, usuario=None, usuario_nome=None
):
    s = _bind()
    ativo = s["obter_ativo"](base_id, ativo_id)
    if not ativo:
        raise ValueError("Equipamento não encontrado.")

    aberta = obter_manutencao_aberta(base_id, ativo_id)
    if not aberta:
        raise ValueError("Não há OS aberta para salvar alterações.")

    texto = (dados.get("texto_anotacao") or "").strip()
    responsavel = (dados.get("responsavel") or "").strip()
    local_raw = dados.get("local")
    fase_raw = dados.get("fase")
    obs_fase = (dados.get("observacao_fase") or "").strip()

    local = None
    if local_raw is not None and str(local_raw).strip() != "":
        local = s["normalizar_local"](local_raw)
        if local not in s["LOCAIS_MANUTENCAO_VALIDOS"]:
            raise ValueError("Local de manutenção inválido.")

    s["validar_fiscal_nao_remove_campo"](
        aberta.get("responsavel"), responsavel, "responsável da OS"
    )

    fase_atual = s["normalizar_fase"](aberta.get("fase"))
    nova_fase = s["normalizar_fase"](fase_raw) if fase_raw else fase_atual

    mudou_responsavel = bool(responsavel) and responsavel != (aberta.get("responsavel") or "")
    mudou_local = local is not None and local != (ativo.get("local") or "base")
    mudou_fase = nova_fase != fase_atual
    tem_anotacao = bool(texto)

    if not any((tem_anotacao, mudou_responsavel, mudou_local, mudou_fase)):
        raise ValueError("Informe ao menos uma alteração para salvar.")

    agora = datetime.now().isoformat(timespec="seconds")
    stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    autor = (usuario_nome or usuario or "fiscal").strip()
    partes = []

    with get_conn() as conn:
        if tem_anotacao:
            linha = f"[{stamp} · {autor}] {texto}"
            obs_atual = (ativo.get("observacoes") or "").strip()
            obs_nova = f"{obs_atual}\n{linha}" if obs_atual else linha
            conn.execute(
                """
                INSERT INTO manutencao_anotacoes
                    (base_id, manutencao_id, texto, usuario, usuario_nome, criado_em)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(base_id),
                    int(aberta["id"]),
                    texto,
                    usuario or "fiscal",
                    usuario_nome or usuario or "fiscal",
                    agora,
                ),
            )
            conn.execute(
                """
                UPDATE ativos SET observacoes = ?, atualizado_em = ?
                WHERE id = ? AND base_id = ?
                """,
                (obs_nova, agora, int(ativo_id), int(base_id)),
            )
            s["registrar_historico"](
                base_id,
                ativo_id,
                ativo["codigo"],
                ativo["nome"],
                "manutencao_anotacao",
                usuario or "fiscal",
                usuario_nome or usuario or "fiscal",
                f"OS {aberta['os_numero']} · {texto[:160]}",
                em_manutencao=True,
                local=ativo.get("local"),
                ordem_servico=aberta["os_numero"],
                conn=conn,
            )
            partes.append("observação")

        if mudou_responsavel:
            conn.execute(
                """
                UPDATE manutencoes
                SET responsavel = ?, atualizado_em = ?
                WHERE id = ? AND base_id = ?
                """,
                (responsavel, agora, int(aberta["id"]), int(base_id)),
            )
            partes.append("responsável")

        if mudou_local:
            conn.execute(
                """
                UPDATE ativos SET local = ?, atualizado_em = ?
                WHERE id = ? AND base_id = ?
                """,
                (local, agora, int(ativo_id), int(base_id)),
            )
            partes.append("local")

        if mudou_fase:
            fase_anterior_label = s["_fmt_fase"](fase_atual)
            fase_nova_label = s["_fmt_fase"](nova_fase)
            detalhes = (
                f"OS {aberta['os_numero']} · {fase_anterior_label} → {fase_nova_label}"
            )
            if obs_fase:
                detalhes = f"{detalhes} · {obs_fase[:120]}"
            conn.execute(
                """
                UPDATE manutencoes
                SET fase = ?, atualizado_em = ?
                WHERE id = ? AND base_id = ?
                """,
                (nova_fase, agora, int(aberta["id"]), int(base_id)),
            )
            s["registrar_historico"](
                base_id,
                ativo_id,
                ativo["codigo"],
                ativo["nome"],
                "manutencao_fase",
                usuario or "fiscal",
                usuario_nome or usuario or "fiscal",
                detalhes,
                em_manutencao=True,
                local=local or ativo.get("local"),
                ordem_servico=aberta["os_numero"],
                conn=conn,
            )
            partes.append("fase")

        if mudou_responsavel or mudou_local:
            alteracoes = []
            if mudou_responsavel:
                alteracoes.append(
                    f"Responsável: '{aberta.get('responsavel') or '—'}' → '{responsavel}'"
                )
            if mudou_local:
                alteracoes.append(
                    f"Local: '{ativo.get('local') or 'base'}' → '{local}'"
                )
            s["registrar_historico"](
                base_id,
                ativo_id,
                ativo["codigo"],
                ativo["nome"],
                "manutencao_atualizacao",
                usuario or "fiscal",
                usuario_nome or usuario or "fiscal",
                f"OS {aberta['os_numero']} · " + " · ".join(alteracoes),
                em_manutencao=True,
                local=local or ativo.get("local"),
                ordem_servico=aberta["os_numero"],
                conn=conn,
            )

        conn.execute(
            """
            UPDATE manutencoes SET atualizado_em = ? WHERE id = ? AND base_id = ?
            """,
            (agora, int(aberta["id"]), int(base_id)),
        )

    return ", ".join(partes)


def _stats_from_manut_rows(rows, s):
    total = len(rows)
    dias = []
    ultima_os = None
    manut_aberta_obj = None
    for r in rows:
        if ultima_os is None:
            ultima_os = r["os_numero"]
        if r["aberta"]:
            fase = s["normalizar_fase"](r["fase"] if "fase" in r.keys() else None)
            manut_aberta_obj = {
                "id": str(r["id"]),
                "os_numero": r["os_numero"],
                "data_abertura": r["data_abertura"],
                "aberta": True,
                "fase": fase,
                "fase_label": s["_fmt_fase"](fase),
                "responsavel": r["responsavel"],
                "observacoes_abertura": r["observacoes_abertura"],
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


def _anotacoes_por_manutencoes(base_id, manutencao_ids, s, conn):
    if not manutencao_ids:
        return {}
    placeholders = ",".join("?" * len(manutencao_ids))
    rows = conn.execute(
        f"""
        SELECT * FROM manutencao_anotacoes
        WHERE base_id = ? AND manutencao_id IN ({placeholders})
        ORDER BY criado_em DESC, id DESC
        """,
        [int(base_id), *manutencao_ids],
    ).fetchall()
    por_id = defaultdict(list)
    for r in rows:
        d = s["_row_to_dict"](r)
        d["manutencao_id"] = str(d["manutencao_id"])
        por_id[str(r["manutencao_id"])].append(d)
    return por_id


def stats_ativo(base_id, ativo_id):
    s = _bind()
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, os_numero, data_abertura, data_conclusao, aberta, fase,
                   responsavel, observacoes_abertura
            FROM manutencoes
            WHERE base_id = ? AND ativo_id = ?
            ORDER BY id DESC
            """,
            (int(base_id), int(ativo_id)),
        ).fetchall()
    return _stats_from_manut_rows(rows, s)


def listar_ativos_com_stats(base_id):
    s = _bind()
    init_db()
    base_int = int(base_id)
    with get_conn() as conn:
        ativo_rows = conn.execute(
            "SELECT * FROM ativos WHERE base_id = ? ORDER BY codigo",
            (base_int,),
        ).fetchall()
        manut_rows = conn.execute(
            """
            SELECT id, ativo_id, os_numero, data_abertura, data_conclusao, aberta, fase,
                   responsavel, observacoes_abertura
            FROM manutencoes
            WHERE base_id = ?
            ORDER BY ativo_id, id DESC
            """,
            (base_int,),
        ).fetchall()

    por_ativo = defaultdict(list)
    for row in manut_rows:
        por_ativo[row["ativo_id"]].append(row)

    ativos = []
    for row in ativo_rows:
        a = s["_row_to_dict"](row)
        a["stats"] = _stats_from_manut_rows(por_ativo.get(int(row["id"]), []), s)
        a["tipo_label"] = s["_fmt_tipo"](a.get("tipo"))
        a["status_label"] = s["_fmt_status"](a.get("em_manutencao"))
        if a.get("em_manutencao") and a["stats"].get("manutencao_aberta"):
            aberta = a["stats"]["manutencao_aberta"]
            a["manutencao_aberta"] = aberta
            a["fase_os"] = aberta.get("fase", s["FASE_OS_PADRAO"])
            a["fase_os_label"] = aberta.get(
                "fase_label", s["_fmt_fase"](a["fase_os"])
            )
        ativos.append(a)
    return ativos


def equipamento_detalhe(base_id, ativo_id):
    s = _bind()
    init_db()
    base_int = int(base_id)
    ativo_int = int(ativo_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ativos WHERE id = ? AND base_id = ?",
            (ativo_int, base_int),
        ).fetchone()
        if not row:
            return None

        ativo = s["_row_to_dict"](row)
        manut_rows = conn.execute(
            """
            SELECT * FROM manutencoes
            WHERE base_id = ? AND ativo_id = ?
            ORDER BY data_abertura DESC, id DESC
            """,
            (base_int, ativo_int),
        ).fetchall()

        manutencoes = [_enriquecer_manutencao(s["_row_to_dict"](r), s) for r in manut_rows]
        stats = _stats_from_manut_rows(manut_rows, s)
        manut_ids = [int(m["id"]) for m in manutencoes]
        anot_map = _anotacoes_por_manutencoes(base_int, manut_ids, s, conn)
        for m in manutencoes:
            m["anotacoes"] = anot_map.get(m["id"], [])

        aberta = next((m for m in manutencoes if m.get("aberta")), None)

        from services import listar_historico_ativo

        historico_fiscal = listar_historico_ativo(base_int, ativo_int, conn=conn)

    ativo["tipo_label"] = s["_fmt_tipo"](ativo.get("tipo"))
    ativo["status_label"] = s["_fmt_status"](ativo.get("em_manutencao"))
    ativo["stats"] = stats
    ativo["manutencoes"] = manutencoes
    ativo["manutencao_aberta"] = aberta
    ativo["historico_fiscal"] = historico_fiscal
    return ativo


def relatorio_manutencoes(base_id):
    s = _bind()
    init_db()
    base_int = int(base_id)
    ranking = []
    todos_dias = []

    with get_conn() as conn:
        ativo_rows = conn.execute(
            "SELECT * FROM ativos WHERE base_id = ? ORDER BY codigo",
            (base_int,),
        ).fetchall()
        ciclos = conn.execute(
            """
            SELECT m.*, a.codigo AS ativo_codigo, a.nome AS ativo_nome, a.tipo AS ativo_tipo
            FROM manutencoes m
            JOIN ativos a ON a.id = m.ativo_id
            WHERE m.base_id = ?
            ORDER BY m.data_abertura DESC, m.id DESC
            """,
            (base_int,),
        ).fetchall()

    stats_map = defaultdict(lambda: {"total": 0, "abertas": 0, "dias": []})
    for r in ciclos:
        aid = r["ativo_id"]
        stats_map[aid]["total"] += 1
        if r["aberta"]:
            stats_map[aid]["abertas"] += 1
        elif r["data_conclusao"]:
            d = _dias_entre(r["data_abertura"], r["data_conclusao"])
            if d is not None:
                stats_map[aid]["dias"].append(d)
                todos_dias.append(d)

    ativos = [s["_row_to_dict"](r) for r in ativo_rows]
    for a in ativos:
        st = stats_map.get(int(a["id"]), {"total": 0, "abertas": 0, "dias": []})
        dias = st["dias"]
        ranking.append(
            {
                "id": a["id"],
                "codigo": a["codigo"],
                "nome": a["nome"],
                "tipo": a.get("tipo") or "",
                "tipo_label": s["_fmt_tipo"](a.get("tipo")),
                "total_manutencoes": st["total"],
                "abertas": st["abertas"],
                "tempo_medio_dias": round(sum(dias) / len(dias), 1) if dias else None,
                "em_manutencao": a.get("em_manutencao"),
            }
        )

    ranking.sort(key=lambda x: (-x["total_manutencoes"], x["codigo"]))
    ciclos_list = []
    manut_ids = [r["id"] for r in ciclos]
    with get_conn() as conn:
        anot_map = _anotacoes_por_manutencoes(base_int, manut_ids, s, conn)
    for r in ciclos:
        d = _enriquecer_manutencao(s["_row_to_dict"](r), s)
        d["ativo_codigo"] = r["ativo_codigo"]
        d["ativo_nome"] = r["ativo_nome"]
        d["ativo_tipo"] = r["ativo_tipo"]
        d["ativo_id"] = str(r["ativo_id"])
        d["tipo_label"] = s["_fmt_tipo"](r["ativo_tipo"])
        if r["data_conclusao"]:
            d["dias_parado"] = _dias_entre(r["data_abertura"], r["data_conclusao"])
        elif r["aberta"]:
            d["dias_parado"] = _dias_entre(r["data_abertura"], datetime.now().strftime("%Y-%m-%d"))
        else:
            d["dias_parado"] = None
        d["anotacoes"] = anot_map.get(str(r["id"]), [])
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
            "fase",
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
                c.get("fase_label", ""),
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
