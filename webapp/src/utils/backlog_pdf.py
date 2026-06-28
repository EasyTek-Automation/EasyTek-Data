# -*- coding: utf-8 -*-
"""Relatório PDF do Backlog de Manutenção (SDD Backlog).

Gera o PDF do recorte filtrado: cabeçalho (planta/data/filtros/frescor) + KPIs + gráficos
(roscas categoria/disciplina/linha + barras por mês) + Top 10 mais antigas + Ranking de
linhas. Padrão da casa: reportlab platypus + plotly→PNG (kaleido). Devolve bytes.
"""
from __future__ import annotations

import io
import os
from datetime import datetime

import plotly.graph_objects as go
import pytz
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

try:
    from src.utils import backlog_data as bd
except ImportError:
    from utils import backlog_data as bd

NAVY = colors.HexColor("#08137C")
_BRT = pytz.timezone("America/Sao_Paulo")
_COR_CAT = ["#198754", "#dc3545", "#fd7e14", "#6f42c1"]
_COR_DISC = ["#08137C", "#20c997", "#adb5bd"]
_COR_LINHA = ["#08137C", "#0d6efd", "#20c997", "#198754", "#fd7e14",
              "#6f42c1", "#dc3545", "#0dcaf0", "#adb5bd"]
_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_LOGO_AMG = os.path.join(_ASSETS, "LogoAMG.png")      # cabeçalho (cliente)
_LOGO_TEK = os.path.join(_ASSETS, "logo.png")          # rodapé "powered by" (Tekmont)


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("BkTitle", parent=s["Title"], fontSize=17, textColor=NAVY, spaceAfter=2))
    s.add(ParagraphStyle("BkSub", parent=s["Normal"], fontSize=9, textColor=colors.HexColor("#6c757d")))
    s.add(ParagraphStyle("BkH2", parent=s["Heading2"], fontSize=12, textColor=NAVY, spaceBefore=10, spaceAfter=4))
    s.add(ParagraphStyle("BkCell", parent=s["Normal"], fontSize=7.5, leading=9))
    return s


def _png(fig, w=560, h=360):
    return fig.to_image(format="png", width=w, height=h, scale=2)


def _fig_rosca(labels, vals, cores, titulo):
    fig = go.Figure(go.Pie(labels=labels, values=vals, hole=0.55, sort=False,
                           marker=dict(colors=cores, line=dict(color="#fff", width=1)),
                           textinfo="value", textfont=dict(size=12)))
    fig.update_layout(title=dict(text=titulo, x=0.5, font=dict(size=13, color="#08137C")),
                      margin=dict(t=34, b=10, l=6, r=6),
                      annotations=[dict(text=f"<b>{int(sum(vals))}</b>", x=0.5, y=0.5,
                                        showarrow=False, font=dict(size=22, color="#08137C"))],
                      legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center",
                                  font=dict(size=9)))
    return fig


def _fig_barras(labels, vals):
    fig = go.Figure(go.Bar(x=labels, y=vals, marker_color="#08137C"))
    fig.update_layout(title=dict(text="Backlog por mês (data de início)", x=0.5,
                                 font=dict(size=13, color="#08137C")),
                      margin=dict(t=34, b=50, l=10, r=10), plot_bgcolor="white",
                      xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
                      yaxis=dict(gridcolor="#eef0f6"))
    return fig


def _img(png, w, h):
    return Image(io.BytesIO(bytes(png)), width=w, height=h)


def _tabela(dados, col_w, header=True):
    cmds = [
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1),
         [colors.whitesmoke, colors.HexColor("#f8f9fa")]),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#adb5bd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), NAVY),
                 ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                 ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    else:  # tabela de pares label/valor (KPIs): colunas de rótulo em navy-bold
        cmds += [("TEXTCOLOR", (0, 0), (0, -1), NAVY), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                 ("TEXTCOLOR", (2, 0), (2, -1), NAVY), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold")]
    t = Table(dados, colWidths=col_w, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(cmds))
    return t


def _rodape(c, doc):
    """Rodapé em toda página: 'Powered by' + logo Tekmont (centro) + nº da página."""
    c.saveState()
    largura, _ = A4
    y = 0.78 * cm
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(colors.HexColor("#9aa0a6"))
    txt = "Powered by"
    tw = c.stringWidth(txt, "Helvetica-Oblique", 7.5)
    logo_w, logo_h = 1.7 * cm, 0.70 * cm
    total = tw + 0.18 * cm + logo_w
    x0 = (largura - total) / 2.0
    c.drawString(x0, y + 0.16 * cm, txt)
    if os.path.exists(_LOGO_TEK):
        c.drawImage(_LOGO_TEK, x0 + tw + 0.18 * cm, y, width=logo_w, height=logo_h,
                    mask="auto", preserveAspectRatio=True)
    c.setFillColor(colors.HexColor("#adb5bd"))
    c.drawRightString(largura - 1.4 * cm, y + 0.16 * cm, f"Pág. {doc.page}")
    c.restoreState()


def gerar_pdf(ordens: list, filtros_desc: str, frescor: str, hoje: datetime | None = None) -> bytes:
    """Monta o PDF do recorte (lista de ordens já filtrada/enriquecida). Devolve bytes."""
    if hoje is None:
        hoje = bd.hoje_brt()
    s = _styles()
    el = []

    # 1. Cabeçalho
    agora = datetime.now(tz=pytz.UTC).astimezone(_BRT)
    cab = [[
        _img(open(_LOGO_AMG, "rb").read(), 2.7 * cm, 1.52 * cm) if os.path.exists(_LOGO_AMG) else "",
        Paragraph("Relatório de Backlog de Manutenção — Planta BR02<br/>"
                  f"<font size=8 color='#6c757d'>Gerado em {agora.strftime('%d/%m/%Y %H:%M')} · "
                  f"{frescor}</font>", s["BkTitle"]),
    ]]
    tc = Table(cab, colWidths=[3.6 * cm, 13.4 * cm])
    tc.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    el += [tc, Spacer(1, 4), Paragraph(f"<b>Recorte:</b> {filtros_desc}", s["BkSub"]), Spacer(1, 8)]

    # 2. KPIs
    ins = bd.insights(ordens, hoje)
    lab_c, val_c = bd.dados_rosca_categoria(ordens)
    lab_d, val_d = bd.dados_rosca_disciplina(ordens)
    kpis = [
        ["Total pendentes", str(ins.get("total", 0)),
         "Não classificadas", f"{ins.get('nc_pct', 0)}% ({ins.get('nc_n', 0)})"],
        [f"Preventiva", str(val_c[0]), "Mecânica", str(val_d[0])],
        [f"Corretiva", str(val_c[1]), "Elétrica", str(val_d[1])],
        [f"Melhoria / Matrizes", f"{val_c[2]} / {val_c[3]}", "Não classificado", str(val_d[2])],
        ["Mais antiga", f"{ins.get('mais_antiga_dias','—')} d (OS {ins.get('mais_antiga_ordem','—')})",
         "Idade média / mediana", f"{ins.get('idade_media','—')} / {ins.get('idade_mediana','—')} d"],
        ["Abertas últimos 30 d", str(ins.get("inflow_30", "—")),
         "Corretivas / preventiva", str(ins.get("razao_cp", "—"))],
    ]
    el += [Paragraph("Resumo executivo", s["BkH2"]),
           _tabela(kpis, [4.2 * cm, 4.3 * cm, 4.2 * cm, 4.3 * cm], header=False),
           Spacer(1, 8)]

    # 3. Gráficos
    rc = _img(_png(_fig_rosca(["Preventiva", "Corretiva", "Melhoria", "Matrizes"], val_c, _COR_CAT,
                              "Por categoria")), 8.2 * cm, 5.3 * cm)
    rd = _img(_png(_fig_rosca(["Mecânica", "Elétrica", "Não classif."], val_d, _COR_DISC,
                              "Por disciplina")), 8.2 * cm, 5.3 * cm)
    lab_l, val_l = bd.dados_rosca_linha(ordens, topn=8)
    rl = _img(_png(_fig_rosca(lab_l, val_l, _COR_LINHA, "Por linha (equipamento-pai)"), 700, 380),
              8.2 * cm, 5.3 * cm)
    labm, valm = bd.dados_barras_mes(ordens)
    bar = _img(_png(_fig_barras(labm, valm), 700, 360), 8.2 * cm, 5.3 * cm)
    gtab = Table([[rc, rd], [rl, bar]], colWidths=[8.5 * cm, 8.5 * cm])
    gtab.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    el += [Paragraph("Gráficos", s["BkH2"]), gtab, Spacer(1, 8)]

    # 4. Top 10 mais antigas
    idades = []
    for o in ordens:
        di = o.get("data_inicio")
        if isinstance(di, datetime):
            d = (hoje - di).days
            if d >= 0:
                idades.append((d, o))
    idades.sort(key=lambda x: x[0], reverse=True)
    cab_top = ["Dias", "OS", "Descrição", "Categoria", "Linha", "Início"]
    rows_top = [cab_top]
    for d, o in idades[:10]:
        di = o.get("data_inicio")
        rows_top.append([
            str(d), o.get("ordem", ""),
            Paragraph((o.get("descricao", "") or "")[:48], s["BkCell"]),
            o.get("categoria", ""),
            Paragraph((o.get("_linha_nome", "") or "")[:26], s["BkCell"]),
            di.strftime("%d/%m/%Y") if isinstance(di, datetime) else "",
        ])
    el += [Paragraph("Top 10 ordens mais antigas", s["BkH2"]),
           _tabela(rows_top, [1.2 * cm, 2 * cm, 6 * cm, 2.4 * cm, 4 * cm, 2 * cm])]

    # 5. Ranking de linhas
    cont = {}
    for o in ordens:
        nome = o.get("_linha_nome") or "(sem linha)"
        c = cont.setdefault(nome, [0, 0])
        c[0] += 1
        if o.get("disciplina") == "NaoClassificado":
            c[1] += 1
    rank = sorted(cont.items(), key=lambda kv: kv[1][0], reverse=True)
    cab_rk = ["Linha", "Ordens", "Não classif.", "% não classif."]
    rows_rk = [cab_rk]
    for nome, (tot, nc) in rank[:15]:
        rows_rk.append([Paragraph(nome[:42], s["BkCell"]), str(tot), str(nc),
                        f"{round(100*nc/tot)}%" if tot else "0%"])
    el += [Spacer(1, 8), Paragraph("Ranking de linhas (por nº de ordens)", s["BkH2"]),
           _tabela(rows_rk, [9 * cm, 2.6 * cm, 2.8 * cm, 2.6 * cm])]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.7 * cm,
                            title="Backlog de Manutenção — BR02")
    doc.build(el, onFirstPage=_rodape, onLaterPages=_rodape)
    return buf.getvalue()
