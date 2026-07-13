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
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=22)

    def _set(self, style="", size=10):
        self.set_font(self._family, style=style, size=size)

    def _write_lines(self, text, h=5, style="", size=10):
        self._set(style, size)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, h, _sanitize(text) or "—")

    def _ensure_space(self, needed_mm=24):
        if self.get_y() + needed_mm > self.page_break_trigger:
            self.add_page()

    def header_block(self, titulo, subtitulo):
        self._write_lines("ManuControl", h=8, style="B", size=16)
        self._write_lines(titulo, h=7, style="B", size=13)
        self.set_text_color(80, 80, 80)
        self._write_lines(subtitulo, h=5, size=10)
        self.set_text_color(0, 0, 0)
        self.ln(3)
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-18)
        self._set("", 8)
        self.set_text_color(120, 120, 120)
        self.set_x(self.l_margin)
        self.cell(
            self.epw,
            8,
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            align="C",
        )

    def section_title(self, text):
        self._ensure_space(12)
        self.ln(2)
        self._write_lines(text, h=6, style="B", size=11)
        self.ln(1)

    def stat_line(self, label, value):
        self._write_lines(f"{label}: {value}", h=5, style="B", size=10)

    def tags_line(self, por_acao):
        if not por_acao:
            return
        partes = [
            f"{ACAO_LABEL.get(acao, acao.capitalize())}: {qtd}"
            for acao, qtd in por_acao.items()
        ]
        self._write_lines(" · ".join(partes), h=5, size=9)
        self.ln(1)

    def entry_block(self, hora, acao, codigo, nome, detalhes, meta):
        self._ensure_space(32)

        acao_txt = ACAO_LABEL.get(acao, acao.capitalize())
        self._write_lines(f"{hora}  ·  {acao_txt}", h=5, style="B", size=9)

        titulo = f"{codigo} — {nome}" if codigo and codigo != "—" else (nome or "—")
        self._write_lines(titulo, h=5, style="B", size=10)

        if detalhes:
            self._write_lines(detalhes, h=5, size=9)

        self.set_text_color(100, 100, 100)
        self._write_lines(meta, h=4, size=8)
        self.set_text_color(0, 0, 0)
        self.ln(2)
        self.set_draw_color(230, 230, 230)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)


def gerar_pdf_diario(filial_codigo, filial_nome, diario):
    pdf = RelatorioPDF()
    pdf.add_page()
    data_fmt = _fmt_data_curta(diario["data"])
    pdf.header_block(
        "Relatório diário",
        f"Filial {filial_codigo} — {filial_nome} · {data_fmt}",
    )
    pdf.stat_line("Total de atualizações", str(diario["total"]))
    pdf.tags_line(diario.get("por_acao"))
    pdf.ln(1)

    if not diario["registros"]:
        pdf._write_lines("Nenhuma atualização nesta data.", h=6, size=10)
    else:
        pdf.section_title("Registros do dia")
        for reg in diario["registros"]:
            pdf.entry_block(
                _fmt_hora(reg.get("criado_em")),
                reg.get("acao", ""),
                reg.get("codigo"),
                reg.get("nome"),
                reg.get("detalhes"),
                f"Por {reg.get('usuario_nome', '—')} ({reg.get('usuario', '—')})",
            )

    return bytes(pdf.output())


def gerar_pdf_mensal(filial_codigo, filial_nome, mensal):
    pdf = RelatorioPDF()
    pdf.add_page()
    mes_nome = _nome_mes(mensal["mes"])
    pdf.header_block(
        "Controle mensal",
        f"Filial {filial_codigo} — {filial_nome} · {mes_nome}/{mensal['ano']}",
    )

    pdf.stat_line("Registros no mês", str(mensal["total"]))
    pdf.stat_line("Dias com atividade", str(mensal["dias_com_atividade"]))
    pdf.stat_line("Ativos movimentados", str(mensal["ativos_movimentados"]))

    snap = mensal.get("snapshot") or {}
    pdf.ln(1)
    pdf.section_title("Situação atual da frota")
    pdf.stat_line("Total de ativos", str(snap.get("total_ativos", 0)))
    pdf.stat_line("Operacionais", str(snap.get("operacionais", 0)))
    pdf.stat_line("Em manutenção", str(snap.get("manutencao", 0)))
    pdf.tags_line(mensal.get("por_acao"))

    if mensal.get("por_dia"):
        pdf.section_title("Atividade por dia")
        for dia in mensal["por_dia"]:
            pdf._write_lines(
                f"{_fmt_data_curta(dia['dia'])}: {dia['total']} registro(s)",
                h=5,
                size=9,
            )
        pdf.ln(1)

    if not mensal["registros"]:
        pdf._write_lines("Nenhuma movimentação neste mês.", h=6, size=10)
    else:
        pdf.section_title(f"Histórico do mês ({mensal['total']})")
        for reg in mensal["registros"]:
            pdf.entry_block(
                _fmt_data_hora(reg.get("criado_em")),
                reg.get("acao", ""),
                reg.get("codigo"),
                reg.get("nome"),
                reg.get("detalhes"),
                reg.get("usuario_nome", "—"),
            )

    return bytes(pdf.output())


def gerar_pdf_manutencoes(filial_codigo, filial_nome, rel):
    pdf = RelatorioPDF()
    pdf.add_page()
    pdf.header_block(
        "Relatório de manutenções",
        f"Filial {filial_codigo} — {filial_nome}",
    )
    pdf.stat_line("Equipamentos", str(rel.get("total_equipamentos", 0)))
    pdf.stat_line("Ciclos de manutenção", str(rel.get("total_ciclos", 0)))
    pdf.stat_line(
        "Tempo médio parado (dias)",
        str(rel.get("tempo_medio_geral") if rel.get("tempo_medio_geral") is not None else "—"),
    )
    pdf.stat_line("Em manutenção agora", str(rel.get("em_manutencao_agora", 0)))

    ranking = [r for r in (rel.get("ranking") or []) if r.get("total_manutencoes", 0) > 0]
    if ranking:
        pdf.section_title("Equipamentos com mais manutenções")
        for item in ranking[:20]:
            media = (
                str(item["tempo_medio_dias"])
                if item.get("tempo_medio_dias") is not None
                else "—"
            )
            pdf._write_lines(
                f"{item['codigo']} — {item['nome']} ({item.get('tipo_label', '—')}): "
                f"{item['total_manutencoes']} OS · média {media} dia(s)",
                h=5,
                size=9,
            )
        pdf.ln(1)

    ciclos = rel.get("ciclos") or []
    if ciclos:
        pdf.section_title(f"Ciclos ({len(ciclos)})")
        for c in ciclos[:80]:
            status = "Aberta" if c.get("aberta") else "Encerrada"
            dias = c.get("dias_parado")
            dias_txt = f" · {dias} dia(s)" if dias is not None else ""
            pdf.entry_block(
                _fmt_data_curta(c.get("data_abertura")),
                status,
                c.get("ativo_codigo"),
                c.get("ativo_nome"),
                f"OS {c.get('os_numero')} · {c.get('responsavel', '—')}{dias_txt}",
                (c.get("observacoes_abertura") or "")[:160],
            )
    else:
        pdf._write_lines("Nenhum ciclo de manutenção registrado.", h=6, size=10)

    return bytes(pdf.output())
