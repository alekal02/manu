import os
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from services import ACAO_LABEL

MESES = [
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]

COR_PRIMARIA = (5, 150, 105)
COR_PRIMARIA_ESC = (4, 120, 87)
COR_ALERTA = (180, 83, 9)
COR_ALERTA_FUNDO = (255, 241, 214)
COR_OK_FUNDO = (232, 245, 233)
COR_TEXTO_SUAVE = (100, 116, 139)
COR_BORDA = (226, 232, 240)


def _font_files():
    win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    regular = win / "arial.ttf"
    bold = win / "arialbd.ttf"
    if regular.is_file():
        return str(regular), str(bold if bold.is_file() else regular)

    local = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"
    if local.is_file():
        bold_local = Path(__file__).parent / "fonts" / "DejaVuSans-Bold.ttf"
        return str(local), str(bold_local if bold_local.is_file() else local)

    return None, None


def _fmt_data_curta(iso_str):
    if not iso_str:
        return "—"
    try:
        if len(iso_str) == 10:
            dt = datetime.strptime(iso_str, "%Y-%m-%d")
        else:
            dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return iso_str


def _fmt_hora(iso_str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%H:%M")
    except ValueError:
        return iso_str


def _fmt_data_hora(iso_str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_str


def _nome_mes(mes):
    try:
        return MESES[int(mes)]
    except (ValueError, IndexError):
        return str(mes)


def _sanitize(text):
    if text is None:
        return ""
    return str(text).replace("\r\n", "\n").replace("\r", "\n").strip()


def _acao_label(acao):
    return ACAO_LABEL.get(acao, (acao or "—").replace("_", " ").capitalize())


def _contar_equipamentos(registros):
    codigos = {r.get("codigo") for r in registros if r.get("codigo")}
    return len(codigos)


def _resumo_por_acao(por_acao):
    return sorted(
        [
            (_acao_label(acao), qtd)
            for acao, qtd in (por_acao or {}).items()
        ],
        key=lambda x: (-x[1], x[0]),
    )


class RelatorioPDF(FPDF):
    def __init__(self):
        super().__init__()
        regular, bold = _font_files()
        if regular:
            self.add_font("Report", "", regular)
            self.add_font("Report", "B", bold)
            self._family = "Report"
        else:
            self._family = "Helvetica"
        self.set_margins(16, 16, 16)
        self.set_auto_page_break(auto=True, margin=20)
        self._titulo_relatorio = ""
        self._subtitulo_relatorio = ""

    def _set(self, style="", size=10):
        self.set_font(self._family, style=style, size=size)

    def _write_lines(self, text, h=5, style="", size=10, color=None):
        if color:
            self.set_text_color(*color)
        self._set(style, size)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, h, _sanitize(text) or "—")
        if color:
            self.set_text_color(0, 0, 0)

    def _ensure_space(self, needed_mm=24):
        if self.get_y() + needed_mm > self.page_break_trigger:
            self.add_page()

    def header(self):
        if self.page_no() == 1:
            return
        self.set_y(10)
        self._set("B", 9)
        self.set_text_color(*COR_PRIMARIA_ESC)
        self.cell(self.epw * 0.65, 5, _sanitize(self._titulo_relatorio)[:70])
        self._set("", 8)
        self.set_text_color(*COR_TEXTO_SUAVE)
        self.cell(self.epw * 0.35, 5, _sanitize(self._subtitulo_relatorio)[:45], align="R")
        self.set_text_color(0, 0, 0)
        self.ln(6)
        self.set_draw_color(*COR_BORDA)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self._set("", 8)
        self.set_text_color(*COR_TEXTO_SUAVE)
        self.cell(
            self.epw / 2,
            5,
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            align="L",
        )
        self.cell(self.epw / 2, 5, f"Página {self.page_no()}", align="R")
        self.set_text_color(0, 0, 0)

    def header_block(self, titulo, subtitulo):
        self._titulo_relatorio = titulo
        self._subtitulo_relatorio = subtitulo

        y0 = self.get_y()
        self.set_fill_color(*COR_PRIMARIA)
        self.rect(self.l_margin, y0, self.epw, 14, style="F")
        self.set_xy(self.l_margin + 4, y0 + 3)
        self._set("B", 14)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, "ManuControl")
        self.set_text_color(0, 0, 0)
        self.set_y(y0 + 18)

        self._write_lines(titulo, h=7, style="B", size=14)
        self._write_lines(subtitulo, h=5, size=10, color=COR_TEXTO_SUAVE)
        self.ln(2)
        self.set_draw_color(*COR_BORDA)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5)

    def resumo_executivo(self, titulo, linhas):
        if not linhas:
            return
        self._ensure_space(16 + len(linhas) * 5)
        y0 = self.get_y()
        self.set_fill_color(248, 250, 252)
        self.set_draw_color(*COR_BORDA)
        self.rect(self.l_margin, y0, self.epw, 8, style="F")
        self.set_xy(self.l_margin + 3, y0 + 2)
        self._set("B", 10)
        self.cell(0, 5, _sanitize(titulo))
        self.set_y(y0 + 10)

        for linha in linhas:
            self._write_lines(f"•  {linha}", h=5, size=9)
        self.ln(3)

    def alerta_box(self, titulo, texto, alerta=True):
        self._ensure_space(22)
        fundo = COR_ALERTA_FUNDO if alerta else COR_OK_FUNDO
        cor_txt = COR_ALERTA if alerta else COR_PRIMARIA_ESC
        y0 = self.get_y()
        self.set_fill_color(*fundo)
        self.set_draw_color(*COR_BORDA)
        self.rect(self.l_margin, y0, self.epw, 7, style="F")
        self.set_xy(self.l_margin + 3, y0 + 1)
        self._set("B", 9)
        self.set_text_color(*cor_txt)
        self.cell(0, 5, _sanitize(titulo))
        self.set_text_color(0, 0, 0)
        self.set_y(y0 + 9)
        self._write_lines(texto, h=5, size=9)
        self.ln(3)

    def section_title(self, text, subtitulo=None):
        self._ensure_space(14)
        self.ln(2)
        y0 = self.get_y()
        self.set_fill_color(*COR_PRIMARIA)
        self.rect(self.l_margin, y0, 3, 7, style="F")
        self.set_xy(self.l_margin + 5, y0)
        self._set("B", 11)
        self.cell(0, 5, _sanitize(text))
        if subtitulo:
            self.set_xy(self.l_margin + 5, y0 + 5)
            self._set("", 8)
            self.set_text_color(*COR_TEXTO_SUAVE)
            self.cell(0, 4, _sanitize(subtitulo))
            self.set_text_color(0, 0, 0)
            self.set_y(y0 + 11)
        else:
            self.set_y(y0 + 9)

    def kpi_cards(self, items):
        self._ensure_space(28)
        n = min(len(items), 4)
        if n == 0:
            return
        gap = 3
        card_w = (self.epw - gap * (n - 1)) / n
        y0 = self.get_y()
        h = 20
        for i, (label, value) in enumerate(items[:4]):
            x = self.l_margin + i * (card_w + gap)
            self.set_xy(x, y0)
            self.set_fill_color(255, 255, 255)
            self.set_draw_color(*COR_BORDA)
            self.rect(x, y0, card_w, h, style="DF")
            self.set_fill_color(*COR_PRIMARIA)
            self.rect(x, y0, card_w, 2, style="F")
            self.set_xy(x + 2, y0 + 5)
            self._set("B", 13)
            self.cell(card_w - 4, 7, _sanitize(str(value)), align="C")
            self.set_xy(x + 2, y0 + 13)
            self._set("", 7)
            self.set_text_color(*COR_TEXTO_SUAVE)
            self.cell(card_w - 4, 5, _sanitize(label), align="C")
            self.set_text_color(0, 0, 0)
        self.set_y(y0 + h + 5)

    def table_row(self, cols, widths, header=False, zebra=False):
        self._ensure_space(8)
        if header:
            self.set_fill_color(*COR_PRIMARIA)
            self.set_text_color(255, 255, 255)
            style = "B"
        elif zebra:
            self.set_fill_color(248, 250, 252)
            self.set_text_color(0, 0, 0)
            style = ""
        else:
            self.set_fill_color(255, 255, 255)
            self.set_text_color(0, 0, 0)
            style = ""
        self._set(style, 8)
        x = self.l_margin
        y = self.get_y()
        row_h = 7
        for col, w in zip(cols, widths):
            self.set_xy(x, y)
            self.cell(
                w,
                row_h,
                _sanitize(col)[:56],
                border=1,
                fill=header or zebra,
                align="L",
            )
            x += w
        self.ln(row_h)

    def acao_resumo_table(self, por_acao):
        linhas = _resumo_por_acao(por_acao)
        if not linhas:
            self._write_lines("Nenhuma movimentação registrada neste período.", h=5, size=9)
            return
        widths = [self.epw * 0.72, self.epw * 0.28]
        self.table_row(["Tipo de ação", "Quantidade"], widths, header=True)
        for i, (label, qtd) in enumerate(linhas):
            self.table_row([label, str(qtd)], widths, zebra=(i % 2 == 0))
        self.ln(2)

    def entry_block(self, hora, acao, codigo, nome, detalhes, meta):
        self._ensure_space(34)
        acao_txt = _acao_label(acao)
        y0 = self.get_y()

        self.set_fill_color(*COR_PRIMARIA)
        self.rect(self.l_margin, y0, 2, 16, style="F")

        self.set_xy(self.l_margin + 5, y0)
        self._set("B", 8)
        self.set_text_color(*COR_PRIMARIA_ESC)
        self.cell(28, 4, _sanitize(hora))
        self._set("B", 9)
        self.cell(0, 4, acao_txt)
        self.set_text_color(0, 0, 0)

        titulo = f"{codigo} — {nome}" if codigo and codigo != "—" else (nome or "—")
        self.set_xy(self.l_margin + 5, y0 + 5)
        self._write_lines(titulo, h=5, style="B", size=10)

        if detalhes:
            self.set_x(self.l_margin + 5)
            self._write_lines(detalhes, h=5, size=9)

        if meta:
            self.set_text_color(*COR_TEXTO_SUAVE)
            self.set_x(self.l_margin + 5)
            self._write_lines(meta, h=4, size=8)
            self.set_text_color(0, 0, 0)

        self.set_y(max(self.get_y(), y0 + 16))
        self.set_draw_color(*COR_BORDA)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def os_ciclo_block(self, ciclo):
        self._ensure_space(44)
        aberta = bool(ciclo.get("aberta"))
        status = "OS ABERTA — requer acompanhamento" if aberta else "OS ENCERRADA"
        fase = ciclo.get("fase_label") or "—"

        fundo = COR_ALERTA_FUNDO if aberta else COR_OK_FUNDO
        cor_txt = COR_ALERTA if aberta else COR_PRIMARIA_ESC
        y0 = self.get_y()
        self.set_fill_color(*fundo)
        self.rect(self.l_margin, y0, self.epw, 8, style="F")
        self.set_xy(self.l_margin + 3, y0 + 1.5)
        self._set("B", 9)
        self.set_text_color(*cor_txt)
        self.cell(0, 5, f"{status}  ·  Fase atual: {fase}")
        self.set_text_color(0, 0, 0)
        self.set_y(y0 + 10)

        codigo = ciclo.get("ativo_codigo") or "—"
        nome = ciclo.get("ativo_nome") or "—"
        tipo = ciclo.get("tipo_label") or "—"
        self._write_lines(f"Equipamento: {codigo} — {nome}", h=5, style="B", size=10)
        self._write_lines(f"Tipo: {tipo}", h=4, size=9, color=COR_TEXTO_SUAVE)

        info = [
            ("Nº da OS", ciclo.get("os_numero") or "—"),
            ("Responsável", ciclo.get("responsavel") or "—"),
            ("Abertura", _fmt_data_curta(ciclo.get("data_abertura"))),
        ]
        if ciclo.get("data_conclusao"):
            info.append(("Conclusão", _fmt_data_curta(ciclo.get("data_conclusao"))))
        if ciclo.get("dias_parado") is not None:
            info.append(("Tempo parado", f"{ciclo.get('dias_parado')} dia(s)"))

        col_w = self.epw / 2
        y_info = self.get_y()
        for i, (rotulo, valor) in enumerate(info):
            col = i % 2
            row = i // 2
            x = self.l_margin + col * col_w
            y = y_info + row * 9
            self.set_xy(x, y)
            self._set("B", 8)
            self.cell(col_w * 0.38, 4, rotulo + ":")
            self._set("", 8)
            self.cell(col_w * 0.62, 4, _sanitize(str(valor))[:40])
        self.set_y(y_info + ((len(info) + 1) // 2) * 9 + 2)

        if ciclo.get("observacoes_abertura"):
            self._write_lines(
                f"Motivo da abertura: {ciclo.get('observacoes_abertura')}",
                h=5,
                size=9,
            )
        if ciclo.get("observacoes_encerramento"):
            self._write_lines(
                f"Observações do encerramento: {ciclo.get('observacoes_encerramento')}",
                h=5,
                size=9,
            )

        anotacoes = ciclo.get("anotacoes") or []
        if anotacoes:
            self._write_lines("Acompanhamento registrado:", h=5, style="B", size=9)
            for an in anotacoes[:8]:
                quando = _fmt_data_hora(an.get("criado_em"))
                quem = an.get("usuario_nome") or an.get("usuario") or "—"
                texto = an.get("texto") or "—"
                self._write_lines(f"  • {quando} — {quem}: {texto}", h=5, size=8)

        self.ln(2)
        self.set_draw_color(*COR_BORDA)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5)


def gerar_pdf_diario(filial_codigo, filial_nome, diario):
    pdf = RelatorioPDF()
    pdf.add_page()
    data_fmt = _fmt_data_curta(diario["data"])
    registros = diario.get("registros") or []
    por_acao = diario.get("por_acao") or {}
    total = diario.get("total", 0)
    equipamentos = _contar_equipamentos(registros)
    os_abertas = por_acao.get("manutencao_abertura", 0)
    os_encerradas = por_acao.get("manutencao_encerramento", 0)

    pdf.header_block(
        "Relatório diário para o gerente",
        f"Filial {filial_codigo} — {filial_nome} · Dia {data_fmt}",
    )

    resumo = []
    if total == 0:
        resumo.append(f"Nenhuma ação do fiscal foi registrada em {data_fmt}.")
    else:
        resumo.append(f"{total} ação(ões) registrada(s) neste dia.")
        resumo.append(f"{equipamentos} equipamento(s) foram atualizados.")
        if os_abertas:
            resumo.append(f"{os_abertas} ordem(ns) de serviço aberta(s).")
        if os_encerradas:
            resumo.append(f"{os_encerradas} ordem(ns) de serviço encerrada(s).")
    pdf.resumo_executivo("Resumo do dia", resumo)

    pdf.kpi_cards(
        [
            ("Ações no dia", total),
            ("Equipamentos", equipamentos),
            ("OS abertas", os_abertas),
            ("OS encerradas", os_encerradas),
        ]
    )

    pdf.section_title("Distribuição por tipo de ação", "O que o fiscal fez ao longo do dia")
    pdf.acao_resumo_table(por_acao)

    if not registros:
        pdf.alerta_box(
            "Sem movimentação",
            "Não há registros para exportar nesta data. Verifique se o fiscal realizou check-ins ou atualizações.",
            alerta=False,
        )
    else:
        pdf.section_title(
            f"Linha do tempo ({total} registro(s))",
            "Ordem cronológica — do mais recente ao mais antigo",
        )
        for reg in registros:
            meta_parts = [f"Responsável: {reg.get('usuario_nome') or reg.get('usuario') or '—'}"]
            if reg.get("ordem_servico"):
                meta_parts.append(f"OS {reg.get('ordem_servico')}")
            if reg.get("local"):
                meta_parts.append(f"Local: {reg.get('local')}")
            if reg.get("em_manutencao") is not None:
                meta_parts.append(
                    "Situação: em manutenção"
                    if reg.get("em_manutencao")
                    else "Situação: operacional"
                )
            pdf.entry_block(
                _fmt_hora(reg.get("criado_em")),
                reg.get("acao", ""),
                reg.get("codigo"),
                reg.get("nome"),
                reg.get("detalhes"),
                "  ·  ".join(meta_parts),
            )

    return bytes(pdf.output())


def gerar_pdf_mensal(filial_codigo, filial_nome, mensal):
    pdf = RelatorioPDF()
    pdf.add_page()
    mes_nome = _nome_mes(mensal["mes"])
    snap = mensal.get("snapshot") or {}
    por_acao = mensal.get("por_acao") or {}
    total = mensal.get("total", 0)

    pdf.header_block(
        "Relatório mensal para o gerente",
        f"Filial {filial_codigo} — {filial_nome} · {mes_nome}/{mensal['ano']}",
    )

    pdf.resumo_executivo(
        "Resumo do mês",
        [
            f"{total} registro(s) de atividade no período.",
            f"{mensal.get('dias_com_atividade', 0)} dia(s) com movimentação do fiscal.",
            f"{mensal.get('ativos_movimentados', 0)} equipamento(s) distintos foram atualizados.",
            (
                f"Situação atual: {snap.get('operacionais', 0)} operacional(is) e "
                f"{snap.get('manutencao', 0)} em manutenção."
            ),
        ],
    )

    pdf.section_title("Indicadores do mês")
    pdf.kpi_cards(
        [
            ("Registros", total),
            ("Dias com atividade", mensal.get("dias_com_atividade", 0)),
            ("Equipamentos mov.", mensal.get("ativos_movimentados", 0)),
            ("Em manutenção", snap.get("manutencao", 0)),
        ]
    )

    pdf.section_title("Situação atual da frota", "Snapshot no momento da exportação")
    pdf.kpi_cards(
        [
            ("Total de ativos", snap.get("total_ativos", 0)),
            ("Operacionais", snap.get("operacionais", 0)),
            ("Em manutenção", snap.get("manutencao", 0)),
            ("Tipos de ação", len(por_acao)),
        ]
    )

    pdf.section_title("Distribuição por tipo de ação")
    pdf.acao_resumo_table(por_acao)

    if mensal.get("por_dia"):
        pdf.section_title("Atividade por dia", "Volume diário de registros do fiscal")
        widths = [pdf.epw * 0.55, pdf.epw * 0.45]
        pdf.table_row(["Data", "Registros"], widths, header=True)
        for i, dia in enumerate(mensal["por_dia"]):
            pdf.table_row(
                [_fmt_data_curta(dia["dia"]), str(dia["total"])],
                widths,
                zebra=(i % 2 == 0),
            )
        pdf.ln(2)

    if not mensal.get("registros"):
        pdf.alerta_box(
            "Sem movimentação",
            "Nenhuma ação foi registrada neste mês para a filial selecionada.",
            alerta=False,
        )
    else:
        pdf.add_page()
        pdf.section_title(
            f"Histórico detalhado ({total})",
            "Registros do mês — do mais recente ao mais antigo",
        )
        dia_atual = None
        for reg in mensal["registros"]:
            dia_reg = _fmt_data_curta(reg.get("criado_em", "")[:10])
            if dia_reg != dia_atual:
                dia_atual = dia_reg
                pdf.section_title(f"Dia {dia_reg}")
            meta_parts = [reg.get("usuario_nome") or reg.get("usuario") or "—"]
            if reg.get("ordem_servico"):
                meta_parts.append(f"OS {reg.get('ordem_servico')}")
            pdf.entry_block(
                _fmt_data_hora(reg.get("criado_em")),
                reg.get("acao", ""),
                reg.get("codigo"),
                reg.get("nome"),
                reg.get("detalhes"),
                "  ·  ".join(meta_parts),
            )

    return bytes(pdf.output())


def gerar_pdf_manutencoes(filial_codigo, filial_nome, rel, atividade=None):
    pdf = RelatorioPDF()
    pdf.add_page()

    media = rel.get("tempo_medio_geral")
    media_txt = str(media) if media is not None else "—"
    ciclos = rel.get("ciclos") or []
    abertas = [c for c in ciclos if c.get("aberta")]
    encerradas = [c for c in ciclos if not c.get("aberta")]
    em_manutencao = rel.get("em_manutencao_agora", 0)

    pdf.header_block(
        "Relatório de manutenções para o gerente",
        f"Filial {filial_codigo} — {filial_nome} · Exportado em {datetime.now().strftime('%d/%m/%Y')}",
    )

    resumo = [
        f"{rel.get('total_equipamentos', 0)} equipamento(s) cadastrados na filial.",
        f"{rel.get('equipamentos_com_manutencao', 0)} já passaram por ordem de serviço.",
        f"{len(abertas)} OS aberta(s) e {len(encerradas)} encerrada(s) no histórico.",
    ]
    if em_manutencao:
        resumo.append(
            f"Atenção: {em_manutencao} equipamento(s) estão parados aguardando manutenção agora."
        )
    if media is not None:
        resumo.append(f"Tempo médio parado (OS encerradas): {media_txt} dia(s).")
    pdf.resumo_executivo("Visão geral para decisão", resumo)

    pdf.kpi_cards(
        [
            ("Equipamentos", rel.get("total_equipamentos", 0)),
            ("Ciclos de OS", rel.get("total_ciclos", 0)),
            ("Tempo médio (dias)", media_txt),
            ("Parados agora", em_manutencao),
        ]
    )

    if abertas:
        pdf.alerta_box(
            f"{len(abertas)} ordem(ns) de serviço aberta(s)",
            "Equipamentos abaixo precisam de acompanhamento até o encerramento da OS.",
        )

    ranking = [r for r in (rel.get("ranking") or []) if r.get("total_manutencoes", 0) > 0]
    if ranking:
        pdf.section_title(
            "Ranking — equipamentos com mais manutenções",
            "Priorize acompanhamento dos que mais geram parada",
        )
        widths = [20, 54, 30, 14, 20, 22]
        pdf.table_row(
            ["Código", "Equipamento", "Tipo", "OS", "Média dias", "Situação"],
            widths,
            header=True,
        )
        for i, item in enumerate(ranking[:25]):
            media_item = (
                str(item["tempo_medio_dias"])
                if item.get("tempo_medio_dias") is not None
                else "—"
            )
            situacao = "Em manutenção" if item.get("em_manutencao") else "Operacional"
            pdf.table_row(
                [
                    item.get("codigo", "—"),
                    item.get("nome", "—"),
                    item.get("tipo_label") or "—",
                    str(item.get("total_manutencoes", 0)),
                    media_item,
                    situacao,
                ],
                widths,
                zebra=(i % 2 == 0),
            )
        pdf.ln(2)

    if abertas:
        pdf.section_title(
            f"Ordens abertas — ação imediata ({len(abertas)})",
            "Equipamentos parados ou em processo de reparo",
        )
        for c in abertas:
            pdf.os_ciclo_block(c)

    if encerradas:
        pdf.section_title(
            f"Ordens encerradas ({len(encerradas)})",
            "Histórico recente — até 60 registros",
        )
        for c in encerradas[:60]:
            pdf.os_ciclo_block(c)

    if not ciclos:
        pdf.alerta_box(
            "Sem histórico de OS",
            "A filial ainda não possui ciclos de manutenção registrados.",
            alerta=False,
        )

    atividade = atividade or []
    if atividade:
        pdf.add_page()
        pdf.section_title(
            f"O que o fiscal registrou ({len(atividade)})",
            "Linha do tempo das ações na filial",
        )
        por_acao_ativ = {}
        for reg in atividade:
            acao = reg.get("acao") or ""
            por_acao_ativ[acao] = por_acao_ativ.get(acao, 0) + 1
        pdf.acao_resumo_table(por_acao_ativ)
        for reg in atividade[:40]:
            meta_parts = [f"Por {reg.get('usuario_nome') or reg.get('usuario') or '—'}"]
            if reg.get("ordem_servico"):
                meta_parts.append(f"OS {reg.get('ordem_servico')}")
            if reg.get("local"):
                meta_parts.append(f"Local: {reg.get('local')}")
            if reg.get("em_manutencao") is not None:
                meta_parts.append(
                    "Em manutenção" if reg.get("em_manutencao") else "Operacional"
                )
            pdf.entry_block(
                _fmt_data_hora(reg.get("criado_em")),
                reg.get("acao", ""),
                reg.get("codigo"),
                reg.get("nome"),
                reg.get("detalhes"),
                "  ·  ".join(meta_parts),
            )

    return bytes(pdf.output())
