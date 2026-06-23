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
_CINZA_ORC = "#dee2e6"     # container do orçado (saldo não usado)
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


def _slider_cfg(rows):
    """(min, max, value, marks, step) do RangeSlider a partir do teto de executado.

    min=0; max arredondado p/ um número redondo (1/2/2,5/5×10ⁿ); value=faixa cheia;
    marcas em 0/25/50/75/100% (R$ abreviado). Vista sem contas → escala trivial.
    """
    teto = _max_conta_exec(rows)
    if teto <= 0:
        return 0, 1, [0, 1], {0: "R$ 0", 1: "R$ 1"}, 1
    mag = 10 ** math.floor(math.log10(teto))
    topo = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= teto)
    marks = {int(round(topo * f)): _brl_abrev(round(topo * f))
             for f in (0, 0.25, 0.5, 0.75, 1.0)}
    step = max(1, round(topo / 100))
    return 0, int(topo), [0, int(topo)], marks, step


def _filtra_por_exec(rows, faixa):
    """Mantém GERAL sempre; mantém contas com executado em [lo, hi]. faixa inválida → tudo."""
    if not faixa or len(faixa) != 2:
        return rows
    lo, hi = faixa
    return [r for r in rows
            if r["code"] == "__GERAL__" or lo <= (r["executado"] or 0) <= hi]


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
def _comp_pct(p):
    """Escala comprimida do modo pct: abaixo de 100% é linear; o estouro acima de 100%
    vale `_FATOR_EXC` por ponto (ex.: 224% → 100 + 124·0,35 ≈ 143%). Mantém o container
    de 100% (cinza) expressivo mesmo com contas muito estouradas."""
    return p if p <= 100 else 100 + (p - 100) * _FATOR_EXC


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
    geral_destaque = (not mini and modo_pct and rows and rows[0]["code"] == "__GERAL__")
    if geral_destaque:
        # GERAL e contas estreitos; contas mais juntas (cluster de componentes). O total e
        # os componentes ficam em faixas de cor distintas (escura no GERAL, clara nas contas).
        _STEP = 0.5
        xs = [0] + [1.0 + k * _STEP for k in range(len(rows) - 1)]
        larguras = [0.5] + [0.32] * (len(rows) - 1)
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
        # Barra-medidor empilhada (sem linha de 100% — o cinza/laranja já dá a referência):
        #   azul AMG  = executado dentro do orçado (0→100%)
        #   cinza     = saldo do orçado não usado (até 100%)
        #   laranja AMG = excedente acima de 100% (escala comprimida via _comp_pct)
        # Conta sem orçado = divisão por zero (% infinito) → gasto 100% fora do orçado:
        # barra inteira laranja (excedente puro), marcada 's/orç'.
        azul_h, cinza_h, laranja_h, cinza_cor = [], [], [], []
        for r in rows:
            if _sem_orc(r):
                azul_h.append(0); cinza_h.append(0); laranja_h.append(100)
                cinza_cor.append(_CINZA_ORC)
                continue
            p = r["pct"] or 0
            azul_h.append(min(p, 100))
            cinza_h.append(max(0, 100 - p))
            laranja_h.append(max(0, (p - 100) * _FATOR_EXC))
            cinza_cor.append(_CINZA_ORC)
        fig.add_bar(name="Executado", x=xs, y=azul_h, width=larguras,
                    marker={"color": _AMG_AZUL}, customdata=codes, hovertext=hovers,
                    hovertemplate="%{hovertext}<extra></extra>")
        fig.add_bar(name="Orçado", x=xs, y=cinza_h, width=larguras,
                    marker={"color": cinza_cor}, customdata=codes, hovertext=hovers,
                    hovertemplate="%{hovertext}<extra></extra>")
        fig.add_bar(name="Excedente", x=xs, y=laranja_h, width=larguras,
                    marker={"color": _AMG_LARANJA}, customdata=codes, hovertext=hovers,
                    hovertemplate="%{hovertext}<extra></extra>")
        topo_pct = max((max(r["pct"], 100) for r in rows
                        if not _sem_orc(r) and r.get("pct") is not None), default=100)
        topo_max = _comp_pct(topo_pct)
        bar_top = [a + c + l for a, c, l in zip(azul_h, cinza_h, laranja_h)]
    else:
        if com_orcado:
            fig.add_bar(name="Orçado", x=xs, y=[r["orcado"] for r in rows], width=0.66,
                        marker={"color": _ORCADO_FILL, "line": {"color": "#9ec5fe", "width": 1}},
                        customdata=codes, hovertext=hovers,
                        hovertemplate="%{hovertext}<extra></extra>")
        # GERAL com cor própria (cinza-azulado) p/ destacar do resto
        cores = ["#34568b" if r["code"] == "__GERAL__" else _cor_exec(r) for r in rows]
        fig.add_bar(name="Executado", x=xs, y=[r["executado"] for r in rows], width=0.34,
                    marker={"color": cores}, customdata=codes, hovertext=hovers,
                    hovertemplate="%{hovertext}<extra></extra>")
        topo_max = max((max(r.get("orcado", 0) or 0, r["executado"] or 0) for r in rows), default=0)
        bar_top = [max(r.get("orcado", 0) or 0, r["executado"] or 0) for r in rows]

    anots = []
    if not mini:
        for i, (x, r) in enumerate(zip(xs, rows)):
            orc = r.get("orcado", 0) or 0
            ex = r["executado"] or 0
            topo = bar_top[i]
            cor_ex = _AMG_AZUL if modo_pct else ("#34568b" if r["code"] == "__GERAL__" else _cor_exec(r))
            # Rótulos de dados empilhados ACIMA da barra. De baixo p/ cima: Executado, Orçado, %.
            if ex:
                anots.append(dict(x=x, y=topo, text=_brl_abrev(ex), showarrow=False, yshift=9,
                                  font={"size": 9, "color": cor_ex, "weight": "bold"}))
            if orc > 0:
                anots.append(dict(x=x, y=topo, text=_brl_abrev(orc), showarrow=False, yshift=20,
                                  font={"size": 8, "color": _CINZA}))
            if r.get("sem_orcamento"):
                txt, cor = "s/orç", (_AMG_LARANJA if modo_pct else _LARANJA)
            elif r.get("pct") is None:
                txt, cor = "", "#8a929b"
            else:
                txt, cor = _pct(r["pct"]), (_VERMELHO if r.get("estouro") else "#495057")
            if txt:
                anots.append(dict(x=x, y=topo, text=txt, showarrow=False, yshift=31,
                                  font={"size": 9, "color": cor, "weight": "bold"}))

    yaxis = {"showgrid": True, "gridcolor": _GRID, "zeroline": False,
             "tickfont": {"size": 9 if mini else 10}, "rangemode": "tozero",
             "showticklabels": not mini,
             # headroom p/ os rótulos empilhados acima da barra mais alta (só nos grandes)
             **({"range": [0, topo_max * 1.18]} if (not mini and topo_max > 0) else {})}
    if modo_pct:
        # ticks reais (0,50,100,150,...) posicionados na escala comprimida
        reais = sorted(set(list(range(0, int(topo_pct) + 51, 50)) + [100]))
        reais = [t for t in reais if t <= topo_pct + 1]
        yaxis.update({"tickmode": "array",
                      "tickvals": [_comp_pct(t) for t in reais],
                      "ticktext": [f"{t} %" for t in reais],
                      "tickformat": ",.0f"})
    else:
        yaxis.update({"tickprefix": "R$ ", "tickformat": ",.0f"})

    # Destaque do GERAL: duas faixas de fundo — escura no total, clara nos componentes.
    # A própria mudança de tom divide o GERAL das contas (sem precisar de linha).
    shapes = []
    if geral_destaque:
        x_fim = xs[-1] + 0.3
        shapes = [
            dict(type="rect", xref="x", yref="paper", x0=-0.4, x1=0.5, y0=0, y1=1,
                 fillcolor="rgba(0,86,135,0.11)", line={"width": 0}, layer="below"),
            dict(type="rect", xref="x", yref="paper", x0=0.5, x1=x_fim, y0=0, y1=1,
                 fillcolor="rgba(0,86,135,0.035)", line={"width": 0}, layer="below"),
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
        hoverlabel={"bgcolor": "white", "font_size": 12},
    )
    return fig


def _graph_click(rows, graph_id, com_orcado, titulo, h=360):
    """Gráfico grande clicável (clique na barra dispara drill)."""
    return dcc.Graph(id=graph_id, figure=_fig_barras(rows, com_orcado, titulo, h=h),
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
                        dcc.Graph(figure=_fig_barras(rows, True, "", h=200, mini=True),
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
            dbc.Card(dbc.CardBody(body, className="text-center py-2"),
                     className="shadow-sm h-100", style={"borderTop": f"3px solid {cor}"}),
            id=cid, n_clicks=0, style={"cursor": "pointer"},
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
            "valor": _brl(d.get("valor")),
            "descritor": d.get("descritor", "") or "(sem descrição)",
            "tipo": d.get("tipo_doc", ""), "documento": d.get("no_documento", ""),
        })
    return dash_table.DataTable(
        data=rows,
        columns=[{"name": "Data", "id": "data"}, {"name": "Conta", "id": "conta"},
                 {"name": "Centro", "id": "centro"}, {"name": "Valor", "id": "valor"},
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

    @app.callback(
        Output("custo-centro-filter", "options"),
        Output("custo-centro-filter", "value"),
        Input("custo-init", "n_intervals"),
        State("store-custo-ano", "data"),
        State("store-custo-centros", "data"),
    )
    def _popular_centros(_n, ano, salvos):
        centros = L.fetch_centros_disponiveis(int(ano or 2026))
        options = [{"label": _centro_label(c), "value": c} for c in centros]
        # Padrão: todos os centros marcados. Respeita um filtro salvo na sessão
        # (subconjunto escolhido antes); só cai no "todos" na 1ª visita / sessão limpa.
        value = salvos if salvos else centros
        return options, value

    @app.callback(
        Output("store-custo-centros", "data"),
        Input("custo-centro-filter", "value"),
        prevent_initial_call=True,
    )
    def _set_centros(value):
        return value or []

    @app.callback(
        Output("store-custo-ano", "data"),
        Input("custo-ano-select", "value"),
        prevent_initial_call=True,
    )
    def _set_ano(value):
        return value

    # Gráfico de entrada (anual) + selo + tarja
    # Escala do slider do anual — ajusta mín/máx/marcas ao dado e reseta p/ faixa cheia
    @app.callback(
        Output("custo-slider-geral", "min"),
        Output("custo-slider-geral", "max"),
        Output("custo-slider-geral", "value"),
        Output("custo-slider-geral", "marks"),
        Output("custo-slider-geral", "step"),
        Input("store-custo-centros", "data"),
        Input("store-custo-ano", "data"),
        Input("custo-init", "n_intervals"),
    )
    def _slider_geral_range(centros, ano, _n):
        ano = int(ano or 2026)
        centros = _centros_efetivos(centros, ano)
        return _slider_cfg(L.fetch_contas_geral(ano, None, centros))

    @app.callback(
        Output("custo-graph-entry", "figure"),
        Output("custo-seed-selo", "children"),
        Output("custo-reconc-banner", "children"),
        Input("store-custo-centros", "data"),
        Input("store-custo-ano", "data"),
        Input("custo-init", "n_intervals"),
        Input("custo-slider-geral", "value"),
    )
    def _render_entry(centros, ano, _n, faixa):
        ano = int(ano or 2026)
        centros = _centros_efetivos(centros, ano)
        # Mudança de dado (ano/centros/init) renderiza cheio; o reset do slider re-renderiza
        # logo em seguida (já com a faixa nova). Só o arrasto do slider aplica filtro — evita
        # filtrar com faixa obsoleta de outro ano.
        if ctx.triggered_id != "custo-slider-geral":
            faixa = None
        rows = _filtra_por_exec(L.fetch_contas_geral(ano, None, centros), faixa)
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
        State("store-custo-centros", "data"),
        State("store-custo-ano", "data"),
        prevent_initial_call=True,
    )
    def _slider_modal_range(level, mes, dia, centros, ano):
        ano = int(ano or 2026)
        centros = _centros_efetivos(centros, ano)
        oculto = {"display": "none"}
        if level == "meses":
            # teto = maior conta entre todos os meses (mesmo limiar aplicado a cada mini)
            allrows = []
            for m in L.meses_com_dados(ano):
                allrows += L.fetch_contas_geral(ano, m, centros)
            rows = allrows
        elif level == "dias" and mes:
            rows = L.fetch_contas_geral(ano, mes, centros)
        elif level == "contas-dia" and dia:
            rows = L.fetch_contas_no_dia(ano, dia, centros)
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
        State("store-custo-centros", "data"),
        State("store-custo-ano", "data"),
        prevent_initial_call=True,
    )
    def _render_modal(level, mes, dia, conta, faixa, centros, ano):
        if not level or level == "planta":
            return None, "", None, {"display": "none"}
        ano = int(ano or 2026)
        centros = _centros_efetivos(centros, ano)
        ano_lbl = f"{ano}"
        # Só o arrasto do slider aplica filtro; navegação de nível renderiza cheio (o reset
        # do slider re-renderiza com a faixa nova) — evita filtrar com faixa de outro nível.
        if ctx.triggered_id != "custo-slider-modal":
            faixa = None

        # NÍVEL 1 — meses (grade de mini-gráficos, 1 por mês)
        if level == "meses":
            meses = L.meses_com_dados(ano)
            cards = [_mini_graph_card(m, _filtra_por_exec(L.fetch_contas_geral(ano, m, centros), faixa))
                     for m in meses]
            content = html.Div([
                html.H6("Clique num mês para ver os dias:", className="v2-section-h6 text-muted"),
                dbc.Row(cards, className="g-3"),
            ])
            return content, "Custo — meses (orçado × executado)", _crumb(ano_lbl), {}

        # NÍVEL 2 — dias (gráfico do mês + cards de dia)
        if level == "dias" and mes:
            # filtro vale só p/ as barras de conta; os cards de DIA são outra dimensão (total/dia)
            rows = _filtra_por_exec(L.fetch_contas_geral(ano, mes, centros), faixa)
            dias = L.fetch_dias_total_mes(ano, mes, centros)
            cards = [_value_card(d["label"], _brl0(d["executado"]), _AZUL,
                                 {"type": "custo-dia-card", "dia": d["code"]}) for d in dias]
            content = html.Div([
                _graph_click(rows, {"type": "custo-bar", "nivel": "mes-contas"}, True,
                             f"{_nome_mes(mes)} — orçado × executado por conta"),
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
            rows = _filtra_por_exec(L.fetch_contas_no_dia(ano, dia, centros), faixa)
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
                docs = L.fetch_lancamentos_no_dia(ano, dia, conta=conta, centros=centros)
                escopo = f"{dia[-2:]}/{_nome_mes(mes)}"
                crumb = _crumb(ano_lbl, _nome_mes(mes), f"Dia {dia[-2:]}", nome)
            else:
                docs = L.fetch_lancamentos(ano, conta=conta, mes=mes, centros=centros)
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
