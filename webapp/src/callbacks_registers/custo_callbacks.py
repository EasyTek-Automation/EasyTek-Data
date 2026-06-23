"""Callbacks da aba 'Custo de Manutencao' — navegacao IDENTICA a indicators-v2.

Regra v2: sempre GRAFICO em cima + CARDS embaixo; tabela so no nivel final.
Fluxo (drill por tempo, contas sempre no eixo):
- Aba: grafico anual (GERAL + todas as contas).
- Clique -> modal nivel 'meses': grade de mini-graficos, 1 por mes (cada = GERAL +
  contas do mes). [analogo ao 'todas as maquinas' do v2]
- Clique num mes -> 'dias': grafico do mes (GERAL+contas) em cima + cards de dia.
- Clique num dia -> 'contas-dia': grafico das contas do dia + cards de conta.
- Clique numa conta -> 'lancamentos': tabela.
Voltar/Fechar em todos os niveis. Mini-graficos usam staticPlot p/ o clique borbulhar
ao Div (mesmo truque do v2).
"""
from __future__ import annotations

import logging
import math

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dash_table, dcc, html, no_update
from dash.dash_table.Format import Format, Group, Scheme, Symbol

try:
    from src.custos import leitura as L
    from src.custos.hierarquia import nome_centro, nome_conta
except ImportError:
    from custos import leitura as L  # type: ignore
    from custos.hierarquia import nome_centro, nome_conta  # type: ignore

logger = logging.getLogger("custos.callbacks")

_AZUL = "#0d6efd"
_VERDE = "#198754"
_VERMELHO = "#dc3545"
_LARANJA = "#fd7e14"
_CINZA = "#6c757d"
_ORCADO_FILL = "#cfe2ff"
_GRID = "rgba(0,0,0,0.06)"
# Cores da marca AMG (mesmas da home — home.py C_SHORT/C_LONG)
_AMG_AZUL = "#005687"      # executado dentro do orçado
_AMG_LARANJA = "#E96D38"   # excedente acima do orçado
_CINZA_ORC = "#dee2e6"        # container do orçado (saldo não usado) — barras das contas
_CINZA_ORC_GERAL = "#c2ccd6"  # idem no GERAL: + escuro p/ não apagar sobre a faixa escura
# Compressão da escala acima de 100%: cada 1% de estouro vale FATOR unidade visual,
# p/ o estouro não esticar o eixo e achatar o container de 100% (ex: 224% → ~143%).
_FATOR_EXC = 0.35
_MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
          "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


# --------------------------------------------------------------------------- #
# Formatacao
# --------------------------------------------------------------------------- #
def _brl(v) -> str:
    if v is None:
        return "—"
    s = f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {s}"


def _brl0(v) -> str:
    if v is None:
        return "—"
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def _brl_abrev(v) -> str:
    """Valor monetário compacto p/ rótulo de barra: 462816 → 'R$ 463k'; 3065639 → 'R$ 3,1M'.

    Abreviação cabe em 16 barras estreitas; valor cheio fica no hover (_hover_rico).
    """
    if v is None:
        return ""
    v = float(v)
    if v == 0:
        return "R$ 0"
    a = abs(v)
    if a >= 1_000_000:
        return "R$ " + f"{v / 1_000_000:.1f}".replace(".", ",") + "M"
    if a >= 1_000:
        return f"R$ {round(v / 1_000):.0f}k"
    return f"R$ {v:.0f}"


def _pct(v) -> str:
    if v is None:
        return "—"
    return f"{v:.1f}".replace(".", ",") + "%"


# --------------------------------------------------------------------------- #
# Filtro por valor (slider duplo) — filtra contas por executado; GERAL fica fixa
# --------------------------------------------------------------------------- #
def _max_conta_exec(rows) -> float:
    """Maior executado entre as contas (exclui GERAL) — teto da escala do slider."""
    return max((r["executado"] or 0 for r in rows if r["code"] != "__GERAL__"), default=0.0)


# piso log do slider (log10(100) = R$100). No piso, o filtro trata como 0 (inclui tudo,
# até contas zeradas). Escala LOG dá controle fino no low-end: dá p/ cortar uma conta de
# R$1k sem levar as de R$50k junto (o problema dos cortes agressivos do slider linear).
_SLIDER_LOG_PISO = 2.0


def _slider_cfg(rows):
    """Config do RangeSlider em escala LOG (R$): (min, max, value, marks, step) em log10(R$).
    A conversão p/ R$ é feita em `_faixa_rs`. Marcas já vêm em R$ (100, 1k, 10k, 100k, 1M…)."""
    teto = _max_conta_exec(rows)
    if teto <= 0:
        m = _SLIDER_LOG_PISO
        return m, m + 1, [m, m + 1], {m: "R$ 0"}, 0.01
    hi = math.ceil(math.log10(teto) * 10) / 10
    lo = _SLIDER_LOG_PISO
    nices = [100, 500, 1e3, 5e3, 1e4, 5e4, 1e5, 5e5, 1e6, 5e6, 1e7, 5e7]
    marks = {round(math.log10(v), 4): _brl_abrev(v) for v in nices if lo <= math.log10(v) <= hi}
    marks[round(hi, 4)] = _brl_abrev(round(teto))
    return lo, round(hi, 4), [lo, round(hi, 4)], marks, 0.01


def _faixa_rs(faixa):
    """Converte a faixa do slider (log10 R$) p/ R$ [lo, hi]. faixa[0] no piso → lo=0 (inclui
    tudo, inclusive contas zeradas). Faixa inválida → None (sem filtro)."""
    if not faixa or len(faixa) != 2:
        return None
    lo = 0 if faixa[0] <= _SLIDER_LOG_PISO + 1e-6 else 10 ** faixa[0]
    return [lo, 10 ** faixa[1]]


def _filtra_por_exec(rows, faixa):
    """Mantém GERAL sempre; mantém contas com executado em [lo, hi]. faixa inválida → tudo."""
    if not faixa or len(faixa) != 2:
        return rows
    lo, hi = faixa
    return [r for r in rows
            if r["code"] == "__GERAL__" or lo <= (r["executado"] or 0) <= hi]


def _filtra_por_contas(rows, sel):
    """Mantém GERAL sempre; mantém só as contas cujo código está em `sel`. sel None → tudo.

    É o filtro das BARRAS (contas/classes de custo) — não confundir com centro de custo
    (onde o gasto ocorreu). GERAL é o total e nunca some.
    """
    if sel is None:
        return rows
    alvo = set(sel)
    return [r for r in rows if r["code"] == "__GERAL__" or r["code"] in alvo]


def _centro_label(c: str) -> str:
    """Rótulo do filtro: 'código — NOME' quando há descrição; só o código quando não."""
    nome = nome_centro(c)
    return f"{c} — {nome}" if nome != c else c


def _centros_efetivos(selected, ano):
    """Centros a aplicar no filtro de leitura, ou None (= sem filtro → número oficial).

    'Todos selecionados' (ou nenhum) == None: usa o executado reconciliado do resumo
    (BR-12), preservando a reconciliação 46/46. Só recorta dos lançamentos quando há
    um subconjunto de centros marcado.
    """
    if not selected:
        return None
    todos = set(L.fetch_centros_disponiveis(int(ano or 2026)))
    if todos and set(selected) >= todos:
        return None
    return selected


def _nome_mes(mes: str) -> str:
    """'2026-02' -> 'Fev/26'."""
    try:
        y, m = mes.split("-")
        return f"{_MESES[int(m) - 1]}/{y[2:]}"
    except Exception:
        return mes


def _cor_exec(r: dict) -> str:
    if r.get("sem_orcamento"):
        return _LARANJA
    if r.get("estouro"):
        return _VERMELHO
    return _VERDE


# --------------------------------------------------------------------------- #
# Graficos
# --------------------------------------------------------------------------- #
_OVERFLOW_BAND = 45.0  # altura visual FIXA do excedente acima de 100% (0-100% ocupa 100/145≈69%)


def _comp_pct(p, topo=None):
    """Escala do modo pct: abaixo de 100% é linear; o excedente acima de 100% é mapeado em LOG
    numa banda de altura FIXA (`_OVERFLOW_BAND`), independente do máximo. Assim 130% e 4000%
    cabem na mesma faixa e o 0-100% nunca achata. `topo` = maior % da vista (vai ao topo da banda)."""
    if p <= 100:
        return p
    if not topo or topo <= 100:
        return 100 + _OVERFLOW_BAND
    return 100 + _OVERFLOW_BAND * (math.log10(p / 100) / math.log10(topo / 100))


def _nice(v):
    """Arredonda p/ cima a um número 'redondo' (1/1,5/2/3/5/8 × 10ⁿ) — rótulos de tick limpos."""
    if v <= 0:
        return 0
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 1.5, 2, 3, 5, 8, 10):
        if m * mag >= v:
            return int(m * mag)
    return int(10 * mag)


def _fig_vazia(msg="Sem dados", h=380):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper",
                       font={"size": 13, "color": _CINZA}, opacity=0.6)
    fig.update_layout(height=h, plot_bgcolor="rgba(248,250,252,0.6)",
                      paper_bgcolor="rgba(0,0,0,0)", xaxis={"visible": False},
                      yaxis={"visible": False}, margin={"l": 10, "r": 10, "t": 10, "b": 10})
    return fig


def _fig_barras(rows, com_orcado, titulo, h=380, mini=False, modo="valor"):
    """Barras orçado×executado. `modo`:

    - 'valor' (default): altura = R$; orçado pálido (container) + executado sólido sobreposto.
    - 'pct': altura = realizado (executado÷orçado); escala 0 → maior %; orçado vira a linha
      de referência 100%; conta sem orçado fica cinza no topo (não há % a calcular).

    Em ambos os modos os rótulos de dados (R$ exec/orç + %) e o hover rico são iguais — só a
    altura/escala muda. GERAL ('__GERAL__') destacado. `mini`=True compacta p/ a grade de meses.
    """
    if not rows:
        return _fig_vazia(h=h)
    modo_pct = (modo == "pct")
    codes = [r["code"] for r in rows]
    nomes = [r["label"] for r in rows]   # nome legível da conta/dia
    # eixo X: nome (sem código). Mini esconde rótulos (overview clicável).
    ticks = nomes
    # Destaque do GERAL no medidor (modo pct): como todas as barras agora têm o mesmo peso
    # visual, separamos o GERAL (total) das contas que o compõem por um gap + divisória +
    # faixa de fundo, e o deixamos mais largo. Sem recolorir (mantém azul/cinza/laranja).
    geral_destaque = bool(rows) and rows[0]["code"] == "__GERAL__"
    if geral_destaque:
        # GERAL largo-ish; contas BEM finas e juntas (cluster de componentes). GERAL no eixo
        # primário e contas no secundário (mais altas-proporcionais), em faixas de tom distintas.
        _STEP = 0.42
        xs = [0] + [0.95 + k * _STEP for k in range(len(rows) - 1)]
        larguras = [0.25] + [0.14] * (len(rows) - 1)
    else:
        xs = list(range(len(rows)))
        larguras = 0.62 if modo_pct else None

    # Hover rico (mesmo texto p/ as barras): nome + orçado + executado + %.
    # Vai em `hovertext` de propósito — `customdata` segue carregando só o code (clique de drill).
    def _hover_rico(r):
        # Custo identificado por código + descrição (GERAL não tem código de conta)
        rotulo = r["label"] if r["code"] == "__GERAL__" else f"{r['code']} — {r['label']}"
        linhas = [f"<b>{rotulo}</b>"]
        if r.get("orcado") or 0:
            linhas.append(f"Orçado: {_brl(r['orcado'])}")
        linhas.append(f"Executado: {_brl(r['executado'])}")
        if r.get("sem_orcamento"):
            linhas.append("sem orçamento")
        elif r.get("pct") is not None:
            linhas.append(f"Realizado: {_pct(r['pct'])}")
        return "<br>".join(linhas)

    hovers = [_hover_rico(r) for r in rows]

    def _sem_orc(r):
        return r.get("sem_orcamento") or r.get("pct") is None

    fig = go.Figure()
    if modo_pct:
        # Barra-medidor empilhada: azul = executado dentro do orçado; cinza = saldo do orçado
        # (até 100%); laranja = excedente acima de 100% (comprimido por _comp_pct). Conta sem
        # orçado (÷0) = barra inteira laranja, marcada 's/orç'.
        # Eixo duplo: GERAL no primário (y) e contas no secundário (y2), com ranges diferentes
        # p/ a barra do total parecer ~40% mais alta que as contas no mesmo %.
        contas_idx = list(range(1, len(rows))) if geral_destaque else list(range(len(rows)))
        topo_pct = max((max(rows[i]["pct"], 100) for i in contas_idx
                        if not _sem_orc(rows[i]) and rows[i].get("pct") is not None), default=100)

        def _segs(r):
            if _sem_orc(r):
                return 0.0, 0.0, 100.0
            p = r["pct"] or 0
            # excedente acima de 100% → banda log de altura fixa (não achata o 0-100%)
            return min(p, 100), max(0, 100 - p), max(0, _comp_pct(p, topo_pct) - 100)
        seg = [_segs(r) for r in rows]
        azul_h = [s[0] for s in seg]
        cinza_h = [s[1] for s in seg]
        laranja_h = [s[2] for s in seg]
        bar_top = [a + c + l for a, c, l in seg]

        def _add_medidor(idxs, eixo, legenda, cinza=_CINZA_ORC):
            larg = [larguras[i] for i in idxs] if isinstance(larguras, list) else larguras
            for nome, cor, alt in (("Executado", _AMG_AZUL, azul_h),
                                   ("Orçado", cinza, cinza_h),
                                   ("Excedente", _AMG_LARANJA, laranja_h)):
                fig.add_bar(name=nome, legendgroup=nome, showlegend=legenda, yaxis=eixo,
                            x=[xs[i] for i in idxs], y=[alt[i] for i in idxs], width=larg,
                            marker={"color": cor}, customdata=[codes[i] for i in idxs],
                            hovertext=[hovers[i] for i in idxs],
                            hovertemplate="%{hovertext}<extra></extra>")

        topo_max = _comp_pct(topo_pct, topo_pct)   # = 100 + _OVERFLOW_BAND (teto fixo da banda)
        if geral_destaque:
            _add_medidor([0], "y", False, cinza=_CINZA_ORC_GERAL)  # GERAL → eixo primário
            _add_medidor(contas_idx, "y2", True)                   # contas → eixo secundário
        else:
            _add_medidor(contas_idx, "y", True)
    else:
        # Modo valor (R$) — usado no nível 'contas-dia' (sem orçado diário → sem %). Mantém a
        # família visual: azul AMG (não verde), barras finas e faixa quando há GERAL.
        larg_exec = larguras if larguras is not None else 0.34
        if com_orcado:
            fig.add_bar(name="Orçado", x=xs, y=[r["orcado"] for r in rows],
                        width=(larguras if larguras is not None else 0.66),
                        marker={"color": _ORCADO_FILL, "line": {"color": "#9ec5fe", "width": 1}},
                        customdata=codes, hovertext=hovers,
                        hovertemplate="%{hovertext}<extra></extra>")
        cores = ["#34568b" if r["code"] == "__GERAL__" else _AMG_AZUL for r in rows]
        fig.add_bar(name="Executado", x=xs, y=[r["executado"] for r in rows], width=larg_exec,
                    marker={"color": cores}, customdata=codes, hovertext=hovers,
                    hovertemplate="%{hovertext}<extra></extra>")
        topo_max = max((max(r.get("orcado", 0) or 0, r["executado"] or 0) for r in rows), default=0)
        bar_top = [max(r.get("orcado", 0) or 0, r["executado"] or 0) for r in rows]

    anots = []
    for i, (x, r) in enumerate(zip(xs, rows)):
        orc = r.get("orcado", 0) or 0
        ex = r["executado"] or 0
        topo = bar_top[i]
        # rótulo segue o eixo da sua barra — só há y2 no medidor (pct); valor/contas-dia usa y
        yr = "y2" if (geral_destaque and modo_pct and i != 0) else "y"
        cor_ex = _AMG_AZUL if r["code"] != "__GERAL__" else "#34568b"
        # texto do % (ou s/orç) — comportamento/cor preservado
        if r.get("sem_orcamento"):
            txt_pct, cor_pct = "s/orç", (_AMG_LARANJA if modo_pct else _LARANJA)
        elif r.get("pct") is None:
            txt_pct, cor_pct = "", "#8a929b"
        else:
            txt_pct, cor_pct = _pct(r["pct"]), (_VERMELHO if r.get("estouro") else "#495057")
        if mini:
            # mini (200px): um rótulo só por barra — % quando há, senão R$ abreviado
            t = txt_pct or (_brl_abrev(ex) if ex else "")
            if t:
                anots.append(dict(x=x, y=topo, yref=yr, text=t, showarrow=False, yshift=5,
                                  font={"size": 7, "color": (cor_pct if txt_pct else cor_ex)}))
            continue
        # gráficos grandes: pilha Executado (R$) / Orçado (R$) / % acima da barra
        if ex:
            anots.append(dict(x=x, y=topo, yref=yr, text=_brl_abrev(ex), showarrow=False,
                              yshift=9, font={"size": 9, "color": cor_ex, "weight": "bold"}))
        if orc > 0:
            anots.append(dict(x=x, y=topo, yref=yr, text=_brl_abrev(orc), showarrow=False,
                              yshift=20, font={"size": 8, "color": _CINZA}))
        if txt_pct:
            anots.append(dict(x=x, y=topo, yref=yr, text=txt_pct, showarrow=False, yshift=31,
                              font={"size": 9, "color": cor_pct, "weight": "bold"}))

    def _pct_ticks(ate, topo):
        rs = [t for t in (0, 50, 100) if t <= ate + 1]
        if ate > 100:
            # no máx 4 ticks acima de 100%, log-espaçados e arredondados (não achata o 0-100)
            d = math.log10(ate / 100)
            rs += [v for v in sorted({_nice(100 * 10 ** (d * k / 4)) for k in range(1, 5)}) if v > 100]
        rs = sorted(set(rs))
        return [_comp_pct(t, topo) for t in rs], [f"{t} %" for t in rs]

    yaxis = {"showgrid": not geral_destaque, "gridcolor": _GRID, "zeroline": False,
             "tickfont": {"size": 9 if mini else 10}, "rangemode": "tozero",
             "showticklabels": not mini}
    yaxis2 = None
    if modo_pct and geral_destaque:
        # GERAL no eixo primário com range MENOR → mesma barra parece ~40% mais alta que as
        # contas (que ficam no secundário, range maior). topo_max = teto comprimido das contas.
        r_g = bar_top[0] * 1.18                       # GERAL ocupa ~85% do próprio eixo
        r_c = max(r_g * 1.68, topo_max * 1.10)        # contas ~68% "mais baixas" no mesmo %
        g_top = 100 if bar_top[0] <= 100 else topo_pct
        tvg, ttg = _pct_ticks(g_top, topo_pct)
        tvc, ttc = _pct_ticks(topo_pct, topo_pct)
        yaxis.update({"range": [0, r_g], "tickmode": "array", "tickvals": tvg,
                      "ticktext": ttg, "tickformat": ",.0f"})
        yaxis2 = {"showgrid": False, "zeroline": False, "rangemode": "tozero",
                  "range": [0, r_c], "overlaying": "y", "side": "right",
                  "tickmode": "array", "tickvals": tvc, "ticktext": ttc, "tickformat": ",.0f",
                  "tickfont": {"size": 9 if mini else 10}, "showticklabels": not mini}
    elif modo_pct:
        tv, tt = _pct_ticks(topo_pct, topo_pct)
        yaxis.update({"range": [0, topo_max * 1.18] if (not mini and topo_max > 0) else None,
                      "tickmode": "array", "tickvals": tv, "ticktext": tt, "tickformat": ",.0f"})
    else:
        yaxis.update({"tickprefix": "R$ ", "tickformat": ",.0f",
                      **({"range": [0, topo_max * 1.18]} if (not mini and topo_max > 0) else {})})

    # Destaque do GERAL: duas faixas de fundo — escura no total, clara nos componentes.
    # A própria mudança de tom divide o GERAL das contas (sem precisar de linha).
    shapes = []
    if geral_destaque:
        x_fim = xs[-1] + 0.3
        shapes = [
            dict(type="rect", xref="x", yref="paper", x0=-0.32, x1=0.42, y0=0, y1=1,
                 fillcolor="rgba(0,86,135,0.15)", line={"width": 0}, layer="below"),
            dict(type="rect", xref="x", yref="paper", x0=0.42, x1=x_fim, y0=0, y1=1,
                 fillcolor="rgba(0,86,135,0.07)", line={"width": 0}, layer="below"),
        ]

    fig.update_layout(
        height=h, barmode=("stack" if modo_pct else "overlay"),
        shapes=shapes,
        plot_bgcolor="rgba(248,250,252,0.6)", paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 44, "r": 12, "t": 34 if titulo else 10, "b": 18 if mini else 150},
        title=({"text": titulo, "font": {"size": 13 if not mini else 12, "color": "#343a40"},
                "x": 0, "xanchor": "left", "y": 0.98} if titulo else None),
        # legenda à direita p/ não cobrir a pilha de rótulos da 1ª barra (GERAL).
        # valor: Orçado/Executado. pct: Executado/Orçado/Excedente (explica o medidor).
        showlegend=not mini,
        legend={"orientation": "h", "y": 1.1, "x": 1, "xanchor": "right", "font": {"size": 11}},
        bargap=0.35, annotations=anots,
        xaxis={"tickmode": "array", "tickvals": xs, "ticktext": ticks,
               "showgrid": False, "zeroline": False, "tickfont": {"size": 10},
               "tickangle": -35, "showticklabels": not mini},
        yaxis=yaxis,
        **({"yaxis2": yaxis2} if yaxis2 else {}),
        hoverlabel={"bgcolor": "white", "font_size": 12},
    )
    return fig


# paleta sequencial p/ as fatias da rosca (tons AMG); 'Outros' sempre cinza
_ROSCA_SEQ = ["#005687", "#1f6aa5", "#2f8fc0", "#5b8def", "#7bb0e8", "#9ec5fe",
              "#b9d4f2", "#c9a227", "#e0b84e", "#6c8ea4"]


def _fig_rosca(dados, h=460):
    """Rosca: distribuição do executado do ano por EQUIPAMENTO (centro de custo).

    Cada fatia = um equipamento (nome via de/para `CENTRO_EQUIP`, fallback = código); a
    cauda de centros menores em 'Outros' (cinza). Centro mostra o total. Não dispara drill —
    leitura complementar às barras (que são por conta).
    """
    if not dados:
        return _fig_vazia(h=h)
    labels = [d["equip"] for d in dados]
    values = [d["executado"] for d in dados]
    _CINZAS = {"Outros": "#adb5bd", "Apoio/Admin": "#adb5bd", "Não atribuído": "#ced4da"}
    cores = [_CINZAS.get(lab) or _ROSCA_SEQ[i % len(_ROSCA_SEQ)]
             for i, lab in enumerate(labels)]
    total = sum(values)
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.58, sort=False, direction="clockwise",
        marker={"colors": cores, "line": {"color": "white", "width": 1.5}},
        customdata=[_brl(v) for v in values],
        texttemplate="%{percent:.0%}", textposition="outside",
        textfont={"size": 10},
        hovertemplate="<b>%{label}</b><br>%{customdata} · %{percent}<extra></extra>"))
    fig.update_layout(
        height=h, margin={"l": 8, "r": 8, "t": 34, "b": 8},
        title={"text": "Custo por equipamento (ano)", "x": 0, "xanchor": "left", "y": 0.98,
               "font": {"size": 13, "color": "#343a40"}},
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend={"orientation": "h", "y": -0.05, "x": 0.5, "xanchor": "center",
                "font": {"size": 9}},
        annotations=[dict(text=f"<b>{_brl_abrev(total)}</b><br><span style='font-size:9px'>total</span>",
                          x=0.5, y=0.5, showarrow=False, font={"size": 14, "color": "#34568b"})],
    )
    return fig


def _graph_click(rows, graph_id, com_orcado, titulo, h=360, modo="valor"):
    """Gráfico grande clicável (clique na barra dispara drill). `modo='pct'` usa o medidor."""
    return dcc.Graph(id=graph_id, figure=_fig_barras(rows, com_orcado, titulo, h=h, modo=modo),
                     config={"displayModeBar": False, "responsive": True},
                     style={"height": f"{h}px", "cursor": "pointer"})


# --------------------------------------------------------------------------- #
# Cards clicáveis (espelha mini-cards do v2)
# --------------------------------------------------------------------------- #
def _mini_graph_card(mes, rows):
    """Card-mini-gráfico de um mês (grade do nível 'meses'). Clicável (staticPlot)."""
    return dbc.Col(
        html.Div(
            dbc.Card(
                [
                    dbc.CardHeader(html.Strong(_nome_mes(mes), style={"fontSize": "0.85rem"}),
                                   className="py-1"),
                    dbc.CardBody(
                        # staticPlot removido p/ liberar o tooltip das barras (hover mostra
                        # orçado/executado/%). O clique no card segue funcionando: o clique
                        # no DOM do gráfico borbulha pro Div pai (n_clicks). doubleClick/drag
                        # desligados p/ não capturar o gesto.
                        dcc.Graph(figure=_fig_barras(rows, True, "", h=200, mini=True, modo="pct"),
                                  config={"displayModeBar": False, "responsive": True,
                                          "doubleClick": False, "scrollZoom": False},
                                  style={"height": "200px", "pointerEvents": "auto"}),
                        className="p-1",
                    ),
                ],
                className="shadow-sm h-100 indicator-v2-card",
            ),
            id={"type": "custo-mes-card", "mes": mes},
            n_clicks=0, style={"cursor": "pointer", "height": "100%"},
        ),
        xs=12, sm=6, md=4, className="mb-3",
    )


def _value_card(titulo, valor_txt, cor, cid, sub=None):
    """Card de valor clicável (dia / conta) — padrão dos mini-cards do v2."""
    body = [html.Div(titulo, className="text-muted small mb-1", style={"fontWeight": "600"}),
            html.Div(valor_txt, style={"fontSize": "1.0rem", "fontWeight": "bold", "color": cor})]
    if sub:
        body.append(html.Div(sub, style={"fontSize": "0.7rem", "color": cor}))
    return dbc.Col(
        html.Div(
            dbc.Card(
                dbc.CardBody(body, className="text-center py-2 d-flex flex-column "
                                             "justify-content-center"),
                className="shadow-sm", style={"borderTop": f"3px solid {cor}", "height": "92px"}),
            id=cid, n_clicks=0, style={"cursor": "pointer", "height": "92px"},
        ),
        xs=6, sm=4, md=3, lg=2, className="mb-2",
    )


def _tabela_lancamentos(docs):
    if not docs:
        return html.Small("Nenhum lançamento neste recorte.", className="text-muted")
    rows = []
    for d in docs:
        dt = d.get("data_lancamento")
        rows.append({
            "data": dt.strftime("%d/%m/%Y") if dt else "",
            "conta": d.get("conta", ""), "centro": d.get("centro_custo", ""),
            "valor": round(d.get("valor") or 0, 2),   # número cru → sort numérico
            "descritor": d.get("descritor", "") or "(sem descrição)",
            "tipo": d.get("tipo_doc", ""), "documento": d.get("no_documento", ""),
        })
    _fmt_brl = Format(group=Group.yes, group_delimiter=".", decimal_delimiter=",",
                      precision=2, scheme=Scheme.fixed, symbol=Symbol.yes, symbol_prefix="R$ ")
    return dash_table.DataTable(
        data=rows,
        columns=[{"name": "Data", "id": "data"}, {"name": "Conta", "id": "conta"},
                 {"name": "Centro", "id": "centro"},
                 {"name": "Valor", "id": "valor", "type": "numeric", "format": _fmt_brl},
                 {"name": "Descrição", "id": "descritor"}, {"name": "Tipo", "id": "tipo"},
                 {"name": "Documento", "id": "documento"}],
        page_size=12, sort_action="native", style_as_list_view=True,
        style_cell={"fontSize": "0.82rem", "padding": "8px 10px", "textAlign": "left",
                    "border": "none", "borderBottom": "1px solid #eef0f3"},
        style_header={"fontWeight": "700", "textTransform": "uppercase", "fontSize": "0.7rem",
                      "letterSpacing": "0.4px", "color": "#6c757d",
                      "backgroundColor": "#fafbfc", "borderBottom": "2px solid #e9ecef"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "rgba(248,250,252,0.6)"},
            {"if": {"column_id": "valor"}, "textAlign": "right", "fontWeight": "600"},
            {"if": {"column_id": "descritor"}, "color": "#495057"}],
        style_table={"overflowX": "auto"},
    )


def _crumb(*partes):
    itens = []
    for i, p in enumerate(partes):
        if i:
            itens.append(html.Span(" › ", className="mx-1 text-muted"))
        itens.append(html.Span(p, className="text-primary fw-semibold"))
    return itens


# --------------------------------------------------------------------------- #
# Registro
# --------------------------------------------------------------------------- #
def register_custo_callbacks(app):
    """Registra todos os callbacks da aba de custo."""

    # Popula o filtro de CONTAS (as barras). Repopula ao trocar o ano.
    @app.callback(
        Output("custo-conta-filter", "options"),
        Output("custo-conta-filter", "value"),
        Input("custo-init", "n_intervals"),
        Input("store-custo-ano", "data"),
        State("store-custo-contas-sel", "data"),
    )
    def _popular_contas(_n, ano, salvos):
        rows = L.fetch_contas_geral(int(ano or 2026), None, None)
        contas = [r for r in rows if r["code"] != "__GERAL__"]
        options = [{"label": f'{r["code"]} — {r["label"]}', "value": r["code"]} for r in contas]
        codes = [r["code"] for r in contas]
        # Padrão: todas marcadas. Respeita seleção salva na sessão se ainda válida.
        value = [c for c in (salvos or []) if c in codes] or codes
        return options, value

    @app.callback(
        Output("store-custo-contas-sel", "data"),
        Input("custo-conta-filter", "value"),
        prevent_initial_call=True,
    )
    def _set_contas(value):
        return value or []

    @app.callback(
        Output("store-custo-ano", "data"),
        Input("custo-ano-select", "value"),
        prevent_initial_call=True,
    )
    def _set_ano(value):
        return value

    # Colapsar/expandir a lista de contas (paredão de chips fica escondido)
    @app.callback(
        Output("custo-contas-collapse", "is_open"),
        Input("custo-contas-toggle", "n_clicks"),
        State("custo-contas-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def _toggle_contas(_n, aberto):
        return not aberto

    # Rótulo do botão: quantas contas selecionadas + chevron (sobe/desce)
    @app.callback(
        Output("custo-contas-toggle", "children"),
        Input("custo-conta-filter", "value"),
        Input("custo-contas-collapse", "is_open"),
        State("custo-conta-filter", "options"),
    )
    def _label_contas(value, aberto, options):
        total = len(options or [])
        n = len(value or [])
        if total and n >= total:
            txt = f"Todas as contas ({total})"
        elif n == 0:
            txt = "Nenhuma conta"
        else:
            txt = f"{n} de {total} contas"
        chev = "bi-chevron-up" if aberto else "bi-chevron-down"
        return [html.Span(txt), html.I(className=f"bi {chev} ms-2")]

    # Gráfico de entrada (anual) + selo + tarja
    # Escala do slider do anual — ajusta mín/máx/marcas ao dado e reseta p/ faixa cheia
    @app.callback(
        Output("custo-slider-geral", "min"),
        Output("custo-slider-geral", "max"),
        Output("custo-slider-geral", "value"),
        Output("custo-slider-geral", "marks"),
        Output("custo-slider-geral", "step"),
        Input("store-custo-ano", "data"),
        Input("custo-init", "n_intervals"),
    )
    def _slider_geral_range(ano, _n):
        # escala do slider baseada em TODAS as contas (não no recorte do filtro) — estável
        return _slider_cfg(L.fetch_contas_geral(int(ano or 2026), None, None))

    # Rosca: distribuição do executado por equipamento (independe do filtro de conta)
    @app.callback(
        Output("custo-graph-rosca", "figure"),
        Input("store-custo-ano", "data"),
        Input("custo-init", "n_intervals"),
    )
    def _render_rosca(ano, _n):
        return _fig_rosca(L.fetch_por_equipamento(int(ano or 2026), None))

    @app.callback(
        Output("custo-graph-entry", "figure"),
        Output("custo-seed-selo", "children"),
        Output("custo-reconc-banner", "children"),
        Input("store-custo-contas-sel", "data"),
        Input("store-custo-ano", "data"),
        Input("custo-init", "n_intervals"),
        Input("custo-slider-geral", "value"),
    )
    def _render_entry(contas_sel, ano, _n, faixa):
        ano = int(ano or 2026)
        # Só o arrasto do slider aplica o filtro de valor; outras mudanças renderizam cheio.
        if ctx.triggered_id != "custo-slider-geral":
            faixa = None
        rows = L.fetch_contas_geral(ano, None, None)   # todos os centros (sem escopo de centro)
        rows = _filtra_por_contas(rows, contas_sel or None)   # filtro das BARRAS (contas)
        rows = _filtra_por_exec(rows, _faixa_rs(faixa))
        # Anual usa a vista por % realizado (altura = executado÷orçado) — evita barras
        # minúsculas de contas de baixo R$. Modal segue em R$ (modo padrão).
        fig = _fig_barras(rows, True, "", h=460, modo="pct")
        rc = L.reconciliacao(ano)
        banner = None
        if rc.get("por_mes") and not rc["bate"]:
            banner = dbc.Alert(
                [html.I(className="bi bi-exclamation-triangle me-2"),
                 f"Esta coleta não fechou com o SAP (diferença {_brl(rc['diff'])}). "
                 "Confira antes de decidir."], color="warning", className="py-2 mb-0")
        selo = None
        if L.fonte_dos_dados(ano) == "csv":
            selo = dbc.Badge([html.I(className="bi bi-info-circle me-1"),
                              "dados de exemplo (seed)"], color="secondary")
        return fig, selo, banner

    # Controle do modal (espelha control_modal da v2)
    @app.callback(
        Output("modal-custo", "is_open"),
        Output("store-custo-level", "data"),
        Output("store-custo-mes", "data"),
        Output("store-custo-dia", "data"),
        Output("store-custo-conta", "data"),
        Output("modal-custo-content", "children", allow_duplicate=True),
        Output("modal-custo-title", "children", allow_duplicate=True),
        Output("modal-custo-breadcrumb", "children", allow_duplicate=True),
        Input("custo-entry-wrap", "n_clicks"),
        Input({"type": "custo-mes-card", "mes": ALL}, "n_clicks"),
        Input({"type": "custo-dia-card", "dia": ALL}, "n_clicks"),
        Input({"type": "custo-conta-card", "conta": ALL}, "n_clicks"),
        Input({"type": "custo-bar", "nivel": ALL}, "clickData"),
        Input("btn-custo-back", "n_clicks"),
        Input("btn-custo-close", "n_clicks"),
        State("store-custo-level", "data"),
        State("store-custo-mes", "data"),
        State("store-custo-dia", "data"),
        State("store-custo-conta", "data"),
        prevent_initial_call=True,
    )
    def _control_modal(*args):
        trig = ctx.triggered_id
        level, mes, dia, conta = args[-4], args[-3], args[-2], args[-1]
        CLEAR = (None, "", None)
        # NOOP precisa ser no-op DE VERDADE: não tocar content/title/breadcrumb. Antes era
        # (no_update,)*5 + CLEAR, que ZERAVA o conteúdo. Isso quebrava quando o slider do modal
        # reconstrói os cards: o set ALL (cards/barras) muda → este callback dispara sem clique
        # real → caía em NOOP e apagava o que o _render_modal acabara de pintar.
        NOOP = (no_update,) * 8

        if trig == "btn-custo-close":
            return (False, "planta", None, None, None) + CLEAR
        if trig == "btn-custo-back":
            if level == "lancamentos":
                return (True, "contas-dia" if dia else "dias", mes, dia, None) + CLEAR
            if level == "contas-dia":
                return (True, "dias", mes, None, None) + CLEAR
            if level == "dias":
                return (True, "meses", None, None, None) + CLEAR
            if level == "meses":
                return (False, "planta", None, None, None) + CLEAR
            return NOOP

        # Clique no gráfico de entrada (área inteira clicável) → abre nível meses
        if trig == "custo-entry-wrap":
            tr = dash.callback_context.triggered
            if not tr or not tr[0].get("value"):
                return NOOP
            return (True, "meses", None, None, None) + CLEAR

        if isinstance(trig, dict):
            t = trig.get("type")
            _val = (dash.callback_context.triggered or [{}])[0].get("value")
            if t in ("custo-mes-card", "custo-dia-card", "custo-conta-card") and not _val:
                return NOOP
            if t == "custo-mes-card":
                return (True, "dias", trig["mes"], None, None) + CLEAR
            if t == "custo-dia-card":
                return (True, "contas-dia", mes, trig["dia"], None) + CLEAR
            if t == "custo-conta-card":
                return (True, "lancamentos", mes, dia, trig["conta"]) + CLEAR
            if t == "custo-bar":
                tr = dash.callback_context.triggered
                if not tr or tr[0].get("value") is None:
                    return NOOP
                code = tr[0]["value"]["points"][0].get("customdata")
                if code is None or code == "__GERAL__":
                    return NOOP
                niv = trig.get("nivel")
                if niv == "mes-contas":      # conta clicada no gráfico do mês
                    return (True, "lancamentos", mes, None, code) + CLEAR
                if niv == "dia-contas":      # conta clicada no gráfico do dia
                    return (True, "lancamentos", mes, dia, code) + CLEAR
        return NOOP

    # Escala + visibilidade do slider do modal — ajusta ao dado do nível e reseta faixa.
    # Escondido nos níveis sem barras (lançamentos / planta).
    @app.callback(
        Output("custo-slider-modal", "min"),
        Output("custo-slider-modal", "max"),
        Output("custo-slider-modal", "value"),
        Output("custo-slider-modal", "marks"),
        Output("custo-slider-modal", "step"),
        Output("custo-slider-modal-wrap", "style"),
        Input("store-custo-level", "data"),
        Input("store-custo-mes", "data"),
        Input("store-custo-dia", "data"),
        State("store-custo-ano", "data"),
        prevent_initial_call=True,
    )
    def _slider_modal_range(level, mes, dia, ano):
        ano = int(ano or 2026)
        oculto = {"display": "none"}
        if level == "meses":
            # teto = maior conta entre todos os meses (mesmo limiar aplicado a cada mini)
            allrows = []
            for m in L.meses_com_dados(ano):
                allrows += L.fetch_contas_geral(ano, m, None)
            rows = allrows
        elif level == "dias" and mes:
            rows = L.fetch_contas_geral(ano, mes, None)
        elif level == "contas-dia" and dia:
            rows = L.fetch_contas_no_dia(ano, dia, None)
        else:  # lançamentos / planta — sem barras, esconde o slider
            return 0, 1, [0, 1], {}, 1, oculto
        mn, mx, val, marks, step = _slider_cfg(rows)
        return mn, mx, val, marks, step, {"display": "block"}

    # Render do conteúdo do modal por nível (espelha render_modal da v2)
    @app.callback(
        Output("modal-custo-content", "children", allow_duplicate=True),
        Output("modal-custo-title", "children", allow_duplicate=True),
        Output("modal-custo-breadcrumb", "children", allow_duplicate=True),
        Output("btn-custo-back", "style"),
        Input("store-custo-level", "data"),
        Input("store-custo-mes", "data"),
        Input("store-custo-dia", "data"),
        Input("store-custo-conta", "data"),
        Input("custo-slider-modal", "value"),
        State("store-custo-contas-sel", "data"),
        State("store-custo-ano", "data"),
        prevent_initial_call=True,
    )
    def _render_modal(level, mes, dia, conta, faixa, contas_sel, ano):
        if not level or level == "planta":
            return None, "", None, {"display": "none"}
        ano = int(ano or 2026)
        sel = contas_sel or None
        ano_lbl = f"{ano}"
        # Só o arrasto do slider aplica filtro; navegação de nível renderiza cheio (o reset
        # do slider re-renderiza com a faixa nova) — evita filtrar com faixa de outro nível.
        if ctx.triggered_id != "custo-slider-modal":
            faixa = None

        def _prep(rows):  # filtro de contas (barras) + filtro de valor
            return _filtra_por_exec(_filtra_por_contas(rows, sel), _faixa_rs(faixa))

        # NÍVEL 1 — meses (grade de mini-gráficos, 1 por mês)
        if level == "meses":
            meses = L.meses_com_dados(ano)
            cards = [_mini_graph_card(m, _prep(L.fetch_contas_geral(ano, m, None)))
                     for m in meses]
            content = html.Div([
                html.H6("Clique num mês para ver os dias:", className="v2-section-h6 text-muted"),
                dbc.Row(cards, className="g-3"),
            ])
            return content, "Custo — meses (realizado, % do orçado)", _crumb(ano_lbl), {}

        # NÍVEL 2 — dias (gráfico do mês + cards de dia)
        if level == "dias" and mes:
            # filtro vale só p/ as barras de conta; os cards de DIA são outra dimensão (total/dia)
            rows = _prep(L.fetch_contas_geral(ano, mes, None))
            dias = L.fetch_dias_total_mes(ano, mes, None)
            cards = [_value_card(d["label"], _brl0(d["executado"]), _AZUL,
                                 {"type": "custo-dia-card", "dia": d["code"]}) for d in dias]
            content = html.Div([
                _graph_click(rows, {"type": "custo-bar", "nivel": "mes-contas"}, True,
                             f"{_nome_mes(mes)} — realizado por conta (% do orçado)",
                             modo="pct"),
                html.Hr(),
                html.H6("Clique num dia (card) para ver as contas do dia, ou numa barra "
                        "de conta para os lançamentos:", className="v2-section-h6 text-muted"),
                dbc.Row(cards, className="g-2"),
            ])
            return (content, f"Custo — {_nome_mes(mes)}",
                    _crumb(ano_lbl, _nome_mes(mes)), {})

        # NÍVEL 3 — contas do dia (gráfico das contas do dia + cards de conta)
        if level == "contas-dia" and dia:
            # aqui barras e cards são a MESMA dimensão (conta) → filtra os dois p/ casar
            rows = _prep(L.fetch_contas_no_dia(ano, dia, None))
            cards = [_value_card(r["label"], _brl0(r["executado"]), _AZUL,
                                 {"type": "custo-conta-card", "conta": r["code"]})
                     for r in rows if r["code"] != "__GERAL__"]
            content = html.Div([
                _graph_click(rows, {"type": "custo-bar", "nivel": "dia-contas"}, False,
                             f"{dia[-2:]}/{_nome_mes(mes)} — executado por conta"),
                html.Hr(),
                html.H6("Clique numa conta (card ou barra) para ver os lançamentos:",
                        className="v2-section-h6 text-muted"),
                dbc.Row(cards, className="g-2"),
            ])
            return (content, f"Custo — {dia[-2:]}/{_nome_mes(mes)} — contas do dia",
                    _crumb(ano_lbl, _nome_mes(mes), f"Dia {dia[-2:]}"), {})

        # NÍVEL 4 — lançamentos (tabela)
        if level == "lancamentos" and conta:
            nome = nome_conta(conta)
            if dia:
                docs = L.fetch_lancamentos_no_dia(ano, dia, conta=conta, centros=None)
                escopo = f"{dia[-2:]}/{_nome_mes(mes)}"
                crumb = _crumb(ano_lbl, _nome_mes(mes), f"Dia {dia[-2:]}", nome)
            else:
                docs = L.fetch_lancamentos(ano, conta=conta, mes=mes, centros=None)
                escopo = _nome_mes(mes)
                crumb = _crumb(ano_lbl, _nome_mes(mes), nome)
            content = html.Div([
                html.H6(f"Lançamentos — {nome} ({conta}), {escopo}",
                        className="v2-section-h6 text-muted"),
                _tabela_lancamentos(docs),
            ])
            return content, f"Custo — {nome} — {escopo}", crumb, {}

        return None, "", None, {"display": "none"}

    # Botão "Rodar agora"
    @app.callback(
        Output("custo-rodar-feedback", "children"),
        Input("btn-custo-rodar-agora", "n_clicks"),
        prevent_initial_call=True,
    )
    def _rodar_agora(_n):
        try:
            from src.sap_scheduler.mongo_helpers import get_db
            from src.custos.sap_jobs import enqueue_ambos, _LABEL
        except ImportError:
            from sap_scheduler.mongo_helpers import get_db  # type: ignore
            from custos.sap_jobs import enqueue_ambos, _LABEL  # type: ignore
        db = get_db()
        if db is None:
            return dbc.Alert("Banco indisponível — não foi possível enfileirar.",
                             color="danger", dismissable=True, className="py-2")
        res = enqueue_ambos(db)
        msg_map = {"inserido": "enfileirada", "ja_em_andamento": "já em andamento",
                   "dedup": "já enfileirada neste minuto", "erro": "falhou"}
        linhas = [f"{_LABEL.get(t, t)}: {msg_map.get(s, s)}" for t, s in res.items()]
        cor = "success" if any(s == "inserido" for s in res.values()) else "info"
        return dbc.Alert(
            [html.Div("Coletas SAP solicitadas:", className="fw-bold"),
             html.Ul([html.Li(x) for x in linhas], className="mb-1"),
             html.Small("A execução roda no coletor do cliente (transporte diferido); "
                        "enquanto isso, os dados vêm da carga de exemplo (seed).",
                        className="text-muted")],
            color=cor, dismissable=True, className="py-2")
