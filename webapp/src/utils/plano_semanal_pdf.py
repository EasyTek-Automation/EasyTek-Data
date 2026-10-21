# -*- coding: utf-8 -*-
"""Relatório PDF do Planejamento Semanal (SDD relatorio-pdf-semanal).

Emite um PDF **A4 paisagem**, **uma página por técnico** com plano na semana, consumindo o
quadro semanal do hh-management (`hh_data.montar_quadro`) — READ-ONLY, sem recalcular
(fidelidade ao quadro, BR-01). Cada página: cabeçalho (nome/disciplina/semana/frescor) + grade
de 7 colunas (seg→dom) com as ordens do técnico por dia + rodapé de capacidade **por-técnico**
por dia. Padrão da casa: reportlab platypus (como `backlog_pdf.py`). Devolve bytes.

Divisão em duas camadas para testabilidade:
- `montar_paginas(...)` — PURA: recebe o quadro + cadastro + assignments já carregados e devolve
  a lista de páginas (recorte Σ planejado > 1 min, ordem disciplina→técnico, ordens por nº,
  rodapé por-técnico, regra temporal por-dia). Testável sem Mongo.
- `montar_paginas_da_semana(...)` — wrapper que carrega tudo de `hh_data` e delega.
- `gerar_pdf(...)` — renderiza as páginas em PDF paisagem.
"""
from __future__ import annotations

import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

try:
    from src.utils import hh_data
    from src.utils import gantt_db
except ImportError:  # execução fora do pacote src (testes)
    from utils import hh_data
    from utils import gantt_db

NAVY = colors.HexColor("#08137C")
_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_LOGO_TEK = os.path.join(_ASSETS, "logo.png")        # rodapé "powered by" (Tekmont)
_LOGO_AMG = os.path.join(_ASSETS, "LogoAMG.png")     # cabeçalho, à direita do nome (cliente)

DIAS_ABREV = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
LABEL_DISC = {"Mecanica": "Mecânica", "Eletrica": "Elétrica"}
_LIMIAR_MIN = 1   # recorte SP-02.2: técnico entra se Σ planejado da semana > 1 min


# ---- camada de modelo (pura, testável) -----------------------------------------------

def _plan_parcela(o: dict) -> int:
    """Planejado do slot: a parcela (se a ordem foi dividida — BR-13), senão o planejado da ordem."""
    p = o.get("parcela_min")
    if p is not None:
        return int(p)
    return int(o.get("planejado_min") or 0)


def _real_ratear(o: dict) -> float:
    """Realizado atribuível ao slot: rateia o realizado da ordem pela fração planejada da parcela.

    Evita dobrar o realizado quando a ordem é dividida em vários slots (mesmo critério do
    `hh_data.calcular_capacidade`). Ordem inteira num slot → fração 1 → realizado cheio.
    """
    plan_ordem = int(o.get("planejado_min") or 0)
    if plan_ordem <= 0:
        return 0.0
    return (o.get("realizado_min") or 0) * (_plan_parcela(o) / plan_ordem)


def _ordem_view(o: dict, passado: bool) -> dict:
    """Projeção da ordem para a célula do dia (planejado sempre; real/aderência só no passado)."""
    return {
        "ordem": str(o.get("ordem", "")),
        "descricao": (o.get("descricao") or "").strip(),
        "linha": (o.get("linha_nome") or "").strip(),   # Linha (equip.-pai): onde o trabalho ocorre
        "planejado_min": _plan_parcela(o),
        "realizado_min": (o.get("realizado_min") or 0) if passado else None,
        "aderencia": o.get("aderencia") if passado else None,   # aderência ao nível da ordem (BR-13)
    }


def montar_paginas(quadro: dict, emp_por_id: dict, assignments_por_func: dict,
                   hoje: datetime) -> list[dict]:
    """Constrói a lista de páginas (uma por técnico com Σ planejado > 1 min). Pura, sem I/O.

    Ordem: disciplina (Mecânica→Elétrica) → técnico (alfabético, já vem ordenado do quadro).
    Rodapé por-técnico (RV-04/DS-04): Disponível = jornada do próprio técnico (0 se indisponível
    no dia; None se sem jornada); Programado = Σ parcelas; Executado = Σ realizado rateado (só
    dias passados — DS-05).
    """
    semana = quadro["semana"]
    datas = hh_data.datas_da_semana(semana)
    hoje_d = (hoje.date() if isinstance(hoje, datetime) else hoje)
    paginas: list[dict] = []

    for disc in ("Mecanica", "Eletrica"):
        for tec in quadro["disciplinas"][disc]["tecnicos"]:
            # recorte SP-02.2: soma do planejado (parcelas) da semana > 1 min
            total_plan = sum(_plan_parcela(o) for d in range(7) for o in tec["dias"][d])
            if total_plan <= _LIMIAR_MIN:
                continue

            fid = tec["funcionario_id"]
            emp = emp_por_id.get(fid, {})
            assigns = assignments_por_func.get(fid, [])
            jorn = hh_data.jornada_min(emp)

            dias_model = {}
            for d in range(7):
                data_d = datas[d]
                passado = data_d.date() < hoje_d
                ordens = sorted(tec["dias"][d], key=lambda o: str(o.get("ordem")))

                programado = sum(_plan_parcela(o) for o in ordens)
                if jorn <= 0:
                    disponivel = None
                elif hh_data.indisponivel_no_dia(assigns, data_d):
                    disponivel = 0
                else:
                    disponivel = jorn
                executado = round(sum(_real_ratear(o) for o in ordens)) if passado else None
                pct = (programado / disponivel) if disponivel else None
                ader = (executado / programado) if (passado and programado > 0) else None

                dias_model[d] = {
                    "data": data_d, "passado": passado,
                    "ordens": [_ordem_view(o, passado) for o in ordens],
                    "cap": {"disponivel": disponivel, "programado": programado,
                            "executado": executado, "pct_programado": pct, "aderencia": ader},
                }

            paginas.append({
                "nome": tec["nome"], "disciplina": disc, "turno": tec.get("turno", ""),
                "funcionario_id": fid, "total_planejado_min": total_plan, "dias": dias_model,
            })
    return paginas


def montar_paginas_da_semana(semana: str, hoje: datetime | None = None,
                             silent: bool = True) -> dict | None:
    """Carrega o quadro + cadastro + assignments de `hh_data` e devolve o modelo pronto.

    Retorna {paginas, semana, coletado_em, hoje} ou None se o Mongo cair. `paginas` pode ser
    vazia (nenhum técnico com plano real) → o chamador trata "nada a imprimir" (SP-08.1).
    """
    quadro = hh_data.montar_quadro(semana, silent=silent)
    if quadro is None:
        return None
    funcionarios = hh_data._carregar_funcionarios(silent)
    emp_por_id = {str(f.get("_id")): f for f in funcionarios}
    assignments_por_func = hh_data._assignments_por_func(funcionarios, silent)
    if hoje is None:
        hoje = hh_data._agora_brt()
    paginas = montar_paginas(quadro, emp_por_id, assignments_por_func, hoje)
    # anexa a foto do cadastro (gantt_employees) por técnico — herança do avatar no PDF
    for p in paginas:
        try:
            p["foto_bytes"], p["foto_mime"] = gantt_db.get_employee_photo(p["funcionario_id"])
        except Exception:
            p["foto_bytes"], p["foto_mime"] = None, None
    return {
        "paginas": paginas,
        "semana": semana,
        "coletado_em": quadro.get("coletado_em"),
        "hoje": hoje,
    }


# ---- camada de render (reportlab paisagem) -------------------------------------------

def _styles():
    # Fontes grandes de propósito: o público é técnico no chão de fábrica (leitura à distância).
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("PsTitle", parent=s["Title"], fontSize=22, textColor=NAVY, spaceAfter=2))
    s.add(ParagraphStyle("PsSub", parent=s["Normal"], fontSize=12, textColor=colors.HexColor("#6c757d")))
    s.add(ParagraphStyle("PsColHead", parent=s["Normal"], fontSize=13, textColor=colors.white,
                         alignment=1, fontName="Helvetica-Bold"))
    s.add(ParagraphStyle("PsOrdem", parent=s["Normal"], fontSize=11, leading=13.5))
    s.add(ParagraphStyle("PsCap", parent=s["Normal"], fontSize=10, leading=12.5,
                         textColor=colors.HexColor("#343a40")))
    s.add(ParagraphStyle("PsVazio", parent=s["Normal"], fontSize=11, leading=13,
                         textColor=colors.HexColor("#adb5bd"), alignment=1))
    s.add(ParagraphStyle("PsOrdemNum", parent=s["Normal"], fontSize=12, leading=14,
                         fontName="Helvetica-Bold", textColor=NAVY))
    s.add(ParagraphStyle("PsAder", parent=s["Normal"], fontSize=11, leading=13.5,
                         fontName="Helvetica-Bold", textColor=NAVY))
    return s


def _fmt_min(v) -> str:
    """Minutos legíveis: '—' se None; 'Xh MM' se ≥60; senão 'N min'."""
    if v is None:
        return "—"
    v = int(round(v))
    if v >= 60:
        return f"{v // 60}h{v % 60:02d}"
    return f"{v} min"


def _fmt_pct(v) -> str:
    return "—" if v is None else f"{round(100 * v)}%"


def _ordem_cell(o: dict, passado: bool, s, inner_w: float) -> Table:
    """Célula de uma ordem (tabela aninhada): nº (negrito) + descrição, divisória, P/R, aderência.

    Dia futuro/hoje: só a linha `P …` (sem R nem aderência). Divisória = filete entre o bloco
    ordem/descrição e o bloco de tempos.
    """
    cab_html = f"<font size=12><b>{o['ordem']}</b></font><br/>{o['descricao'][:44]}"
    linha = (o.get("linha") or "").strip()
    if linha:   # sublinha cinza "onde": omitida quando a ordem não amarra numa Linha
        cab_html += f"<br/><font size=9 color='#6c757d'>Linha: {linha[:38]}</font>"
    cab = Paragraph(cab_html, s["PsOrdem"])
    rows = [[cab]]
    if passado:
        rows.append([Paragraph(f"P {_fmt_min(o['planejado_min'])} / R {_fmt_min(o['realizado_min'])}",
                               s["PsOrdem"])])
        rows.append([Paragraph(f"Aderência {_fmt_pct(o['aderencia'])}", s["PsAder"])])
    else:
        rows.append([Paragraph(f"P {_fmt_min(o['planejado_min'])}", s["PsOrdem"])])
    t = Table(rows, colWidths=[inner_w])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.6, colors.HexColor("#8a93b5")),   # divisória após ordem/descrição
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _cell_cap(cap: dict, passado: bool, s) -> Paragraph:
    """Rodapé de capacidade da coluna (por-técnico): Disp/Prog e, no passado, Exec/Aderência."""
    txt = (f"Disp {_fmt_min(cap['disponivel'])}<br/>Prog {_fmt_min(cap['programado'])}"
           f" ({_fmt_pct(cap['pct_programado'])})")
    if passado:
        txt += f"<br/>Exec {_fmt_min(cap['executado'])} · Ader {_fmt_pct(cap['aderencia'])}"
    return Paragraph(txt, s["PsCap"])


def _rodape(c, doc):
    """Rodapé em toda página: 'Powered by' + logo Tekmont (centro) + nº da página (paisagem)."""
    c.saveState()
    largura, _ = landscape(A4)
    y = 0.6 * cm
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.HexColor("#9aa0a6"))
    txt = "Powered by"
    tw = c.stringWidth(txt, "Helvetica-Oblique", 7)
    logo_w, logo_h = 1.6 * cm, 0.62 * cm
    total = tw + 0.18 * cm + logo_w
    x0 = (largura - total) / 2.0
    c.drawString(x0, y + 0.14 * cm, txt)
    if os.path.exists(_LOGO_TEK):
        c.drawImage(_LOGO_TEK, x0 + tw + 0.18 * cm, y, width=logo_w, height=logo_h,
                    mask="auto", preserveAspectRatio=True)
    c.setFillColor(colors.HexColor("#adb5bd"))
    c.drawRightString(largura - 1.0 * cm, y + 0.14 * cm, f"Pág. {doc.page}")
    c.restoreState()


def _pagina_tecnico(pag: dict, semana: str, coletado_em, s) -> list:
    """Flowables de uma página de técnico: cabeçalho + grade 7 colunas + rodapé de capacidade."""
    datas = hh_data.datas_da_semana(semana)
    ini, fim = datas[0], datas[6]
    frescor = (f"dados de até {coletado_em.strftime('%d/%m %H:%M')}"
               if isinstance(coletado_em, datetime) else "aguardando primeira coleta")
    largura = landscape(A4)[0] - 2 * cm      # menos margens (~1 cm cada lado)
    col_w = largura / 7.0
    inner_w = col_w - 12                      # largura útil da tabela aninhada (menos padding da célula)

    # cabeçalho: foto do funcionário (cadastro) à esquerda do nome; sem foto → só o nome
    nome_par = Paragraph(
        f"{pag['nome']} — {LABEL_DISC.get(pag['disciplina'], pag['disciplina'])}"
        f" · Turno {pag.get('turno') or '—'}<br/>"
        f"<font size=12 color='#6c757d'>Semana {semana} "
        f"({ini.strftime('%d/%m')}–{fim.strftime('%d/%m/%Y')}) · {frescor}</font>",
        s["PsTitle"])
    foto = pag.get("foto_bytes")
    avatar = None
    if foto:
        try:
            avatar = Image(io.BytesIO(bytes(foto)), width=2.66 * cm, height=2.66 * cm)
        except Exception:
            avatar = None

    # logo do cliente (AMG) à direita do nome; some com graça se o arquivo faltar.
    # dimensão +70% sobre o padrão backlog_pdf (2,7×1,52) → 4,59×2,584cm.
    logo_amg = None
    if os.path.exists(_LOGO_AMG):
        try:
            logo_amg = Image(_LOGO_AMG, width=4.59 * cm, height=2.584 * cm)
        except Exception:
            logo_amg = None

    # cabeçalho = [avatar? | nome (flex) | logo AMG?] numa linha; nome absorve a folga
    cells, widths = [], []
    if avatar is not None:
        cells.append(avatar)
        widths.append(3.0 * cm)
    logo_w = 4.9 * cm if logo_amg is not None else 0   # coluna cabe o logo +70% + folga
    cells.append(nome_par)
    widths.append(largura - sum(widths) - logo_w)
    if logo_amg is not None:
        cells.append(logo_amg)
        widths.append(logo_w)
    cab = Table([cells], colWidths=widths)
    estilo_cab = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]
    if logo_amg is not None:
        estilo_cab.append(("ALIGN", (-1, 0), (-1, 0), "RIGHT"))   # logo AMG encostado à direita
    cab.setStyle(TableStyle(estilo_cab))

    # cabeçalho das colunas (dias)
    col_head = [Paragraph(f"{DIAS_ABREV[d]} {datas[d].strftime('%d/%m')}", s["PsColHead"])
                for d in range(7)]

    # corpo = grade (índice da ordem × dia): cada LINHA é uma "faixa de ordem" cruzando os 7
    # dias → a zebra é da linha inteira (não interna por coluna). Dia com menos ordens deixa
    # células vazias na faixa.
    max_ord = max((len(pag["dias"][d]["ordens"]) for d in range(7)), default=0)
    max_ord = max(max_ord, 1)
    body_rows = []
    for r in range(max_ord):
        row = []
        for d in range(7):
            ordens = pag["dias"][d]["ordens"]
            row.append(_ordem_cell(ordens[r], pag["dias"][d]["passado"], s, inner_w)
                       if r < len(ordens) else "")
        body_rows.append(row)

    footer = [_cell_cap(pag["dias"][d]["cap"], pag["dias"][d]["passado"], s) for d in range(7)]

    grid = Table([col_head] + body_rows + [footer], colWidths=[col_w] * 7, repeatRows=1)
    last = len(body_rows) + 1     # índice da linha de rodapé (0 = header)
    grid.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),                          # header dias
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        # zebra da LINHA INTEIRA (faixas de ordem, linhas 1..penúltima)
        ("ROWBACKGROUNDS", (0, 1), (-1, last - 1), [colors.white, colors.HexColor("#e3e7f2")]),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#adb5bd")),
        ("BACKGROUND", (0, last), (-1, last), colors.HexColor("#eef0f6")),   # rodapé capacidade
        ("LINEABOVE", (0, last), (-1, last), 0.8, NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return [cab, Spacer(1, 6), grid]


def gerar_pdf(paginas: list[dict], semana: str, coletado_em=None, hoje=None) -> bytes:
    """Renderiza o PDF A4 paisagem: uma página por técnico (BR-06: quebra por técnico). Devolve bytes.

    `paginas` = saída de `montar_paginas`. Se vazia, gera uma folha "Nada a imprimir" (o chamador
    normalmente evita chamar nesse caso — SP-08.1).
    """
    s = _styles()
    story: list = []
    if not paginas:
        story.append(Paragraph(f"Nada a imprimir na semana {semana}.", s["PsTitle"]))
    else:
        for i, pag in enumerate(paginas):
            if i > 0:
                story.append(PageBreak())
            story += _pagina_tecnico(pag, semana, coletado_em, s)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1 * cm, rightMargin=1 * cm,
                            topMargin=1 * cm, bottomMargin=1.2 * cm,
                            title=f"Plano semanal — {semana}")
    doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
    return buf.getvalue()
