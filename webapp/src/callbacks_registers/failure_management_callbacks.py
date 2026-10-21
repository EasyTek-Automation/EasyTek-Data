"""
Callbacks da aba "Gestão das Análises" (página Análise de Falhas).

Divisão de trabalho, conforme DS-06:

- **carregar** vai ao banco uma vez e guarda o quadro pronto num store;
- **desenhar** monta cartões e gráfico a partir desse store;
- **foco** grava o mês escolhido.

Separar os dois é o que faz clicar num mês ser instantâneo: o foco é um recorte do que
já está na mão, não motivo para consultar o banco de novo.

A conta em si não mora aqui — está em `utils/failure_management.py`, que é puro e
testado. Este módulo só busca, desenha e reage a clique.
"""

import logging
from datetime import datetime, timedelta

import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback_context, html, no_update

from src.pages.maintenance.analise_de_falhas import TRANS
from src.utils.failure_events import buscar_eventos
from src.utils.failure_management import (
    JANELA_REINCIDENCIA_MESES,
    mes_corrente,
    meses_do_periodo,
    montar_quadro,
    somar_meses,
)

logger = logging.getLogger(__name__)

ROTA_DIAGRAMA = "/maintenance/analise-de-falhas/ishikawa"

ACCENT = "#c0392b"
COR_ANALISADAS = "#198754"
COR_PLANO = "#6f42c1"

# Cartões: (id do valor, chave no resumo, chave do "de quanto" ou None).
CARTOES = [
    ("g-val-eleg", "elegiveis", None),
    ("g-val-analisadas", "analisadas", "analisadas_de"),
    ("g-val-fila", "aguardando_aceite", None),
    ("g-val-plano", "com_plano", "com_plano_de"),
    ("g-val-vencidas", "acoes_vencidas", "acoes_em_aberto"),
    ("g-val-voltaram", "falhas_voltaram", None),
]

MESES_CURTOS = {
    "pt": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def _t(lang):
    """Dicionário do idioma atual, caindo no português se vier algo estranho."""
    return TRANS.get(lang or "pt", TRANS["pt"])


# Plural de cada unidade, explícito: derivar com "+ s" erra em "ação" → "açãos" e em
# "mês" → "mêss", e o erro só aparece na tela.
_PLURAL = {"dia": "dias", "mes": "meses", "parada": "paradas",
           "acao": "acoes", "causa": "causas"}


def _un(t, n, nome):
    """A unidade no singular ou no plural, conforme o número.

    "faltam 1 meses" e "1 causas · 1 ações" saltam aos olhos de quem lê a tela todo
    dia — e tiram a credibilidade de um número que está certo.
    """
    chave = f"g_un_{nome}" if abs(n) == 1 else f"g_un_{_PLURAL[nome]}"
    return t.get(chave, "")


def _rotulo_mes(mes, lang):
    """`202606` → `jun/26` — curto porque são 12 no mesmo eixo."""
    nomes = MESES_CURTOS.get(lang or "pt", MESES_CURTOS["pt"])
    return f"{nomes[int(mes[4:]) - 1]}/{mes[2:4]}"


def _hoje():
    """Data de hoje no fuso da fábrica (horário de Brasília).

    O container roda em UTC; sem o ajuste, entre 21h e 0h o quadro pularia para o dia
    seguinte e uma ação com prazo de hoje apareceria vencida.
    """
    return (datetime.utcnow() - timedelta(hours=3)).date()


def _figura_vazia(msg, height=320):
    fig = go.Figure()
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=8, b=8),
                      xaxis={"visible": False}, yaxis={"visible": False},
                      annotations=[{"text": msg, "showarrow": False,
                                    "font": {"size": 13, "color": "#888"}}],
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


def register_failure_management_callbacks(app):
    """Registra os callbacks da aba Gestão das Análises."""

    # -- Carregar ---------------------------------------------------------

    @app.callback(
        Output("store-af-gestao-data", "data"),
        Input("tabs-af", "active_tab"),
        Input("btn-af-refresh", "n_clicks"),
        prevent_initial_call=False,
    )
    def _carregar(aba, _n):
        """Busca as paradas e as análises e guarda o quadro pronto.

        Só roda quando a aba está ativa — abrir a página na aba de Paradas não deve
        pagar o custo desta consulta.

        São **duas** buscas de parada: uma com o filtro de gatilho, que é a fila de
        candidatas a análise (BR-02), e outra sem filtro nenhum, porque a falha que
        volta conta em qualquer tamanho (BR-10). A segunda vai até três meses além do
        período, que é a janela de observação da reincidência.
        """
        if aba != "tab-af-gestao":
            return no_update
        try:
            from src.database.connection import get_mongo_connection

            hoje = _hoje()
            meses = meses_do_periodo(hoje)
            inicio = datetime(int(meses[0][:4]), int(meses[0][4:]), 1)
            fim_periodo = somar_meses(meses[-1], 1)
            fim = datetime(int(fim_periodo[:4]), int(fim_periodo[4:]), 1)
            fim_voltas_mes = somar_meses(meses[-1], JANELA_REINCIDENCIA_MESES + 1)
            fim_voltas = datetime(int(fim_voltas_mes[:4]), int(fim_voltas_mes[4:]), 1)

            elegiveis = buscar_eventos(inicio, fim)
            todos = buscar_eventos(inicio, fim_voltas, apenas_acima_do_gatilho=False)
            col = get_mongo_connection("FailureAnalysis")
            analises = list(col.find({})) if col is not None else []
            for a in analises:
                a.pop("_id", None)          # ObjectId não é serializável no store

            quadro = montar_quadro(elegiveis, todos, analises, hoje, meses)
            quadro["erro"] = False
            return quadro
        except Exception as e:                                   # noqa: BLE001
            logger.error("[gestao-analises] falha ao montar o quadro: %s", e)
            return {"erro": True}

    # -- Desenhar ---------------------------------------------------------

    @app.callback(
        [Output(cid, "children") for cid, _, _ in CARTOES],
        [Output(f"{cid}-de", "children") for cid, _, _ in CARTOES],
        Output("g-grafico-meses", "figure"),
        Output("g-foco-texto", "children"),
        Output("g-foco-limpar", "children"),
        Output("g-foco-aviso", "style"),
        Input("store-af-gestao-data", "data"),
        Input("store-af-gestao-mes", "data"),
        Input("store-af-lang", "data"),
    )
    def _desenhar(quadro, mes_foco, lang):
        """Monta cartões e gráfico do que já está no store."""
        t = _t(lang)
        vazios = ["—"] * len(CARTOES)
        sem_de = [""] * len(CARTOES)
        oculto = {"display": "none"}
        if not quadro:
            return (*vazios, *sem_de, _figura_vazia(""), "", t["g_foco_limpar"], oculto)
        if quadro.get("erro"):
            return (*vazios, *sem_de, _figura_vazia(t["g_erro"]), "",
                    t["g_foco_limpar"], oculto)

        por_mes = quadro.get("por_mes") or []
        if mes_foco:
            linhas = [m for m in por_mes if m["mes"] == mes_foco]
            resumo = _resumo_do_mes(quadro, linhas)
        else:
            resumo = quadro.get("cartoes") or {}

        valores, subtitulos = [], []
        for cid, chave, chave_de in CARTOES:
            valores.append(f"{resumo.get(chave, 0)}")
            if chave_de:
                total = resumo.get(chave_de, 0)
                subtitulos.append(f"{t['g_de']} {total}" if total else "")
            elif cid == "g-val-fila":
                # A fila ignora o mês em foco (BR-17) — dizer isso evita a leitura
                # errada de que aquele mês tem 3 esperando aceite.
                subtitulos.append(t["g_fila_todos_meses"] if mes_foco else "")
            else:
                subtitulos.append("")

        fig = _figura(por_mes, quadro.get("mes_corrente"), mes_foco, t, lang)

        if mes_foco:
            texto = f"{t['g_foco']} {_rotulo_mes(mes_foco, lang)} ·"
            estilo = {"display": "block"}
        else:
            texto, estilo = "", oculto

        return (*valores, *subtitulos, fig, texto, t["g_foco_limpar"], estilo)

    def _resumo_do_mes(quadro, linhas):
        """Os números de um mês só — recorte do que já foi calculado."""
        base = dict(quadro.get("cartoes") or {})
        if not linhas:
            return {k: 0 for k in base}
        linha = linhas[0]
        mes = linha["mes"]
        atencao = [i for i in (quadro.get("atencao") or []) if i.get("mes") == mes]
        reinc = [r for r in (quadro.get("reincidencia") or []) if r.get("mes") == mes]
        return {
            "elegiveis": linha["elegiveis"],
            "analisadas": linha["analisadas"],
            "analisadas_de": linha["elegiveis"],
            "aguardando_aceite": base.get("aguardando_aceite", 0),   # fila ignora o foco
            "com_plano": linha["com_plano"],
            "com_plano_de": (linha["analisadas"] + linha["aguardando"]
                             + linha["em_elaboracao"] + linha["devolvidas"]),
            "acoes_vencidas": sum(1 for i in atencao
                                  if "vencida" in (i.get("motivos") or [])),
            "acoes_em_aberto": base.get("acoes_em_aberto", 0),
            "falhas_voltaram": sum(1 for r in reinc if r.get("voltou")),
            "ainda_observando": sum(1 for r in reinc if r.get("ainda_observando")),
            "pendencias": len(atencao),
        }

    def _figura(por_mes, corrente, mes_foco, t, lang):
        """Barras agrupadas: elegíveis × analisadas × com plano de ação.

        O mês corrente sai hachurado — sem isso, todo dia 1º parece uma queda histórica
        de falhas, quando o mês apenas ainda não acabou (BR-12).

        `hoverinfo` fica em `"none"` e **nunca** em `"skip"`: `skip` desliga também o
        clique, e o clique é o que põe o mês em foco.
        """
        if not por_mes:
            return _figura_vazia(t["g_vazio_sem_dado"])

        rotulos = [_rotulo_mes(m["mes"], lang) for m in por_mes]
        series = [
            (t["g_serie_eleg"], [m["elegiveis"] for m in por_mes], ACCENT),
            (t["g_serie_analisadas"], [m["analisadas"] for m in por_mes], COR_ANALISADAS),
            (t["g_serie_plano"], [m["com_plano"] for m in por_mes], COR_PLANO),
        ]
        fig = go.Figure()
        for nome, valores, cor in series:
            fig.add_bar(
                name=nome, x=rotulos, y=valores,
                # A opacidade vai em `marker`, e não solta: `opacity` do traço aceita
                # um número só, e passar lista derruba o callback inteiro.
                marker=dict(
                    color=cor,
                    pattern_shape=["/" if m["mes"] == corrente else "" for m in por_mes],
                    opacity=[1.0 if (not mes_foco or m["mes"] == mes_foco) else 0.3
                             for m in por_mes],
                ),
                customdata=[m["mes"] for m in por_mes],
                hovertemplate=f"<b>%{{x}}</b><br>{nome}: %{{y}}<extra></extra>",
            )
        fig.update_layout(
            barmode="group", height=320, margin=dict(l=8, r=8, t=28, b=8),
            legend=dict(orientation="h", y=1.12, x=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="rgba(128,128,128,0.15)", zeroline=False),
            xaxis=dict(showgrid=False),
        )
        if corrente in [m["mes"] for m in por_mes]:
            fig.add_annotation(x=_rotulo_mes(corrente, lang), y=1.02, yref="paper",
                               text=t["g_mes_andamento"], showarrow=False,
                               font=dict(size=10, color="#888"))
        # Mês sem nenhuma parada carregada recebe a marca "sem dados": barra vazia
        # sozinha não distingue o mês bom do mês que não foi carregado (BR-12), e a
        # diferença entre os dois é comemorar ou investigar.
        for m in por_mes:
            if not m.get("tem_dado"):
                fig.add_annotation(x=_rotulo_mes(m["mes"], lang), y=0, yanchor="bottom",
                                   text=t["g_sem_dado_curto"], showarrow=False,
                                   textangle=-90, xshift=0, yshift=6,
                                   font=dict(size=9, color="#aaa"))
        return fig

    # -- Foco no mês ------------------------------------------------------

    @app.callback(
        Output("store-af-gestao-mes", "data"),
        Input("g-grafico-meses", "clickData"),
        Input("g-foco-limpar", "n_clicks"),
        State("store-af-gestao-mes", "data"),
        prevent_initial_call=True,
    )
    def _foco(clique, _limpar, atual):
        """Clique numa barra põe o mês em foco; clicar no mesmo mês tira o foco."""
        gatilho = (callback_context.triggered[0]["prop_id"] or "").split(".")[0]
        if gatilho == "g-foco-limpar":
            return None
        if not clique or not clique.get("points"):
            return no_update
        mes = clique["points"][0].get("customdata")
        if not mes:
            return no_update
        return None if mes == atual else mes

    # -- Cabeçalho por aba ------------------------------------------------

    @app.callback(
        Output("collapse-af-filters", "style"),
        Output("btn-af-filters", "style"),
        Output("btn-af-sendmail", "style"),
        Output("btn-af-export", "style"),
        Input("tabs-af", "active_tab"),
    )
    def _cabecalho_por_aba(aba):
        """Esconde na aba nova o que pertence ao Pareto.

        Filtros, e-mail e exportar agem sobre os dados do Pareto. Com a aba de gestão
        aberta, eles apareceriam prometendo uma ação que não têm — pior que não existir.
        "Atualizar" e o trocador de idioma ficam: valem para a aba ativa e para a página
        inteira (DS-09).
        """
        esconder = {"display": "none"}
        if aba == "tab-af-gestao":
            return esconder, esconder, esconder, esconder
        return {}, {}, {}, {}

    # -- Tabelas: por responsável e precisa de atenção --------------------

    @app.callback(
        Output("g-tabela-responsaveis", "children"),
        Output("g-lista-atencao", "children"),
        Output("g-aten-filtro-texto", "children"),
        Output("g-aten-limpar", "children"),
        Output("g-aten-filtro", "style"),
        Input("store-af-gestao-data", "data"),
        Input("store-af-gestao-mes", "data"),
        Input("store-af-gestao-pessoa", "data"),
        Input("store-af-lang", "data"),
    )
    def _tabelas(quadro, mes_foco, pessoa, lang):
        """Desenha a tabela por responsável e a lista de pendências."""
        t = _t(lang)
        oculto = {"display": "none"}
        if not quadro or quadro.get("erro"):
            vazio = html.Div(t["g_erro"] if (quadro or {}).get("erro") else "",
                             className="text-muted small py-2")
            return vazio, vazio, "", t["g_aten_limpar"], oculto

        tabela = _tabela_responsaveis(quadro.get("responsaveis") or [], t)
        atencao = [i for i in (quadro.get("atencao") or [])
                   if not mes_foco or i.get("mes") == mes_foco]
        if pessoa:
            atencao = [i for i in atencao
                       if pessoa in (i.get("responsaveis") or [])
                       or (pessoa == t["g_sem_responsavel"] and i.get("tipo") == "acao"
                           and not i.get("responsaveis"))]
        lista = _lista_atencao(atencao, t)

        if pessoa:
            texto = f"{t['g_aten_filtro']} {pessoa} ·"
            estilo = {"display": "block"}
        else:
            texto, estilo = "", oculto
        return tabela, lista, texto, t["g_aten_limpar"], estilo

    def _tabela_responsaveis(linhas, t):
        """Uma linha por pessoa. A nota do rodapé não é enfeite: sem ela, a soma que
        passa do total (ação com dois donos) volta como relato de bug (BR-08)."""
        if not linhas:
            return html.Div(t["g_resp_vazio"], className="text-muted small py-2")

        cabecalho = html.Thead(html.Tr([
            html.Th(t["g_col_pessoa"]), html.Th(t["g_col_acoes"], className="text-end"),
            html.Th(t["g_col_vencidas"], className="text-end"),
            html.Th(t["g_col_em_aberto"], className="text-end"),
            html.Th(t["g_col_feitas"], className="text-end"),
        ]))
        corpo = []
        for linha in linhas:
            venc = linha["vencidas"]
            corpo.append(html.Tr([
                html.Td(linha["pessoa"]),
                html.Td(linha["acoes"], className="text-end"),
                html.Td(html.Strong(venc) if venc else venc,
                        className="text-end" + (" text-danger" if venc else "")),
                html.Td(linha["em_aberto"], className="text-end"),
                html.Td(linha["feitas"], className="text-end"),
            ], id={"type": "g-linha-pessoa", "pessoa": linha["pessoa"]},
                className="g-clicavel"))
        total = html.Tfoot(html.Tr([
            html.Td(html.Strong(t["g_col_total"])),
            html.Td(html.Strong(sum(l["acoes"] for l in linhas)), className="text-end"),
            html.Td(html.Strong(sum(l["vencidas"] for l in linhas)), className="text-end"),
            html.Td(html.Strong(sum(l["em_aberto"] for l in linhas)), className="text-end"),
            html.Td(html.Strong(sum(l["feitas"] for l in linhas)), className="text-end"),
        ]))
        return html.Div([
            dbc.Table([cabecalho, html.Tbody(corpo), total], hover=True, size="sm",
                      className="mb-2 align-middle"),
            html.Div(t["g_resp_nota"], id="af-i18n-g-resp-nota",
                     className="text-muted", style={"fontSize": "0.75rem"}),
        ])

    def _texto_motivos(item, t):
        """Os motivos de uma pendência, em português comum e na mesma linha.

        Uma ação sem dono **e** sem prazo aparece uma vez só, com os dois motivos —
        duas linhas fariam a lista parecer maior que o problema (BR-07).
        """
        partes = []
        for motivo in item.get("motivos") or []:
            if motivo == "vencida":
                atraso = item.get("dias_atraso") or 0
                partes.append(t["g_mot_vencida"].format(n=atraso,
                                                        u=_un(t, atraso, "dia")))
            elif motivo == "sem_responsavel":
                partes.append(t["g_mot_sem_resp"])
            elif motivo == "sem_prazo":
                partes.append(t["g_mot_sem_prazo"])
            elif motivo == "em_elaboracao":
                partes.append(t["g_mot_elaboracao"])
            elif motivo == "devolvida":
                devolucao = (item.get("motivo_devolucao") or "").strip()
                partes.append(f"{t['g_mot_devolvida']} — “{devolucao}”"
                              if devolucao else t["g_mot_devolvida"])
        return " · ".join(partes)

    def _lista_atencao(itens, t, limite=20):
        """Lista de pendências, com o motivo em destaque. Nunca trunca em silêncio."""
        if not itens:
            return html.Div(t["g_aten_vazio"], className="text-muted small py-2")

        linhas = []
        for item in itens[:limite]:
            # Pendência de ação: o título é a ação, e o equipamento vira contexto.
            # Pendência da própria análise não tem descrição — aí o equipamento é o
            # título, e repeti-lo no contexto daria "PRENSA-01 · PRENSA-01 · jul/26".
            equip = item.get("equipamento") or ""
            descricao = (item.get("descricao") or "").strip()
            titulo = descricao or equip
            partes_ctx = [] if descricao == "" else ([equip] if equip else [])
            if item.get("mes"):
                partes_ctx.append(_rotulo_mes(item["mes"], None))
            contexto = " · ".join(partes_ctx)
            donos = ", ".join(item.get("responsaveis") or [])
            grave = "vencida" in (item.get("motivos") or [])
            linhas.append(html.Div([
                html.Div([
                    html.Span(titulo, className="fw-semibold"),
                    html.Span(f" · {contexto}" if contexto else "", className="text-muted"),
                ], style={"fontSize": "0.88rem"}),
                html.Div([
                    html.Span(_texto_motivos(item, t),
                              className="text-danger" if grave else "text-warning"),
                    html.Span(f" · {donos}" if donos else "", className="text-muted"),
                ], style={"fontSize": "0.8rem"}),
            ], id={"type": "g-linha-atencao", "chave": item.get("chave") or ""},
                className="py-2 border-bottom g-clicavel"))

        if len(itens) > limite:
            linhas.append(html.Div(t["g_aten_mais"].format(n=len(itens) - limite),
                                   className="text-muted small pt-2"))
        return html.Div(linhas)

    # -- Filtro por pessoa e navegação ------------------------------------

    @app.callback(
        Output("store-af-gestao-pessoa", "data"),
        Input({"type": "g-linha-pessoa", "pessoa": ALL}, "n_clicks"),
        Input("g-aten-limpar", "n_clicks"),
        State("store-af-gestao-pessoa", "data"),
        prevent_initial_call=True,
    )
    def _filtrar_pessoa(cliques, _limpar, atual):
        """Clicar numa pessoa filtra as pendências para as ações dela.

        O guard `any(cliques)` não é decoração: as linhas nascem junto com a tabela, e
        componente criado depois dispara o callback na criação, com `n_clicks=None`.
        """
        gatilho = callback_context.triggered_id
        if gatilho == "g-aten-limpar":
            return None
        if not cliques or not any(cliques):
            return no_update
        pessoa = (gatilho or {}).get("pessoa")
        if not pessoa:
            return no_update
        return None if pessoa == atual else pessoa

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Output("url", "search", allow_duplicate=True),
        Input({"type": "g-linha-atencao", "chave": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _abrir_analise(cliques):
        """Clique numa pendência abre a análise daquela parada.

        O mês em foco e a pessoa filtrada ficam em store de sessão, então a volta
        devolve a pessoa exatamente onde ela estava — quem tem oito pendências não
        pode reencontrar o caminho oito vezes (SP-08).
        """
        if not cliques or not any(cliques):
            return no_update, no_update
        chave = (callback_context.triggered_id or {}).get("chave")
        if not chave:
            return no_update, no_update
        return ROTA_DIAGRAMA, f"?parada={chave}"

    # -- Fila de aceite e reincidência ------------------------------------

    @app.callback(
        Output("g-bloco-fila", "children"),
        Output("g-bloco-reincidencia", "children"),
        Input("store-af-gestao-data", "data"),
        Input("store-af-gestao-mes", "data"),
        Input("store-af-lang", "data"),
    )
    def _fila_e_reincidencia(quadro, mes_foco, lang):
        """Desenha a fila do gestor e a lista de reincidência."""
        t = _t(lang)
        if not quadro or quadro.get("erro"):
            vazio = html.Div("", className="text-muted small py-2")
            return vazio, vazio
        return (_tabela_fila(quadro.get("fila") or [], t, lang),
                _lista_reincidencia(quadro.get("reincidencia") or [], mes_foco, t, lang))

    def _espera(dias, t):
        """"há 12 dias" / "hoje" — o número é o que faz a fila não envelhecer."""
        if dias is None:
            return "—"
        return (t["g_fila_hoje"] if dias <= 0
            else t["g_fila_dias"].format(n=dias, u=_un(t, dias, "dia")))

    def _tabela_fila(fila, t, lang):
        """A fila do gestor, da que espera há mais tempo para a mais recente (BR-17).

        Linha com mais de 15 dias de espera ganha destaque — é o mesmo que grifar a
        conta mais antiga da pilha, não uma recomendação.
        """
        if not fila:
            return html.Div(t["g_vazio_fila"], className="text-muted small py-2")

        cabecalho = html.Thead(html.Tr([
            html.Th(t["g_fila_col_equip"]), html.Th(t["g_fila_col_mes"]),
            html.Th(t["g_fila_col_falha"]), html.Th(t["g_fila_col_por"]),
            html.Th(t["g_fila_col_espera"]), html.Th(t["g_fila_col_conteudo"]),
        ]))
        corpo = []
        for item in fila:
            dias = item.get("dias_esperando")
            falha = (item.get("falha") or "").strip()
            if len(falha) > 46:
                falha = falha[:43] + "..."
            devolvida = item.get("devolvida_vezes") or 0
            corpo.append(html.Tr([
                html.Td(item.get("equipamento") or "—"),
                html.Td(_rotulo_mes(item["mes"], lang) if item.get("mes") else "—"),
                html.Td([falha,
                         html.Span(" · " + t["g_fila_devolvida"].format(n=devolvida),
                                   className="text-warning") if devolvida else ""]),
                html.Td(item.get("entregue_por") or "—"),
                html.Td(_espera(dias, t),
                        className="text-warning fw-semibold"
                        if (dias or 0) > 15 else ""),
                html.Td(t["g_fila_conteudo"].format(
                    c=item.get("causas") or 0, uc=_un(t, item.get("causas") or 0, "causa"),
                    a=item.get("acoes") or 0, ua=_un(t, item.get("acoes") or 0, "acao"))),
            ], id={"type": "g-linha-atencao", "chave": item.get("chave") or ""},
                className="g-clicavel"))
        return html.Div([
            dbc.Table([cabecalho, html.Tbody(corpo)], hover=True, size="sm",
                      className="mb-2 align-middle"),
            html.Div(t["g_fila_nota"], id="af-i18n-g-fila-nota",
                     className="text-muted", style={"fontSize": "0.75rem"}),
        ])

    def _lista_reincidencia(itens, mes_foco, t, lang):
        """A falha voltou — com tamanho e contexto, nunca só o carimbo (BR-10, BR-11).

        "Ainda observando" é um terceiro estado, e não "não voltou": a análise de julho
        não teve três meses para voltar, e juntar os dois faria a mais recente parecer
        a mais bem-sucedida.
        """
        itens = [i for i in itens if not mes_foco or i.get("mes") == mes_foco]
        if not itens:
            return html.Div(t["g_reinc_vazio"], className="text-muted small py-2")

        # Quem voltou primeiro: é o que exige conversa.
        itens = sorted(itens, key=lambda i: (not i.get("voltou"), i.get("mes") or ""))
        linhas = []
        for item in itens:
            rep = item.get("repeticao") or {}
            dias_rep, vezes = rep.get("dias") or 1, rep.get("vezes") or 1
            repetiu = t["g_reinc_repetiu"].format(
                min=int(rep.get("minutos") or 0),
                d=dias_rep, ud=_un(t, dias_rep, "dia"),
                v=vezes, uv=_un(t, vezes, "parada"))
            if item.get("voltou"):
                meses = ", ".join(_rotulo_mes(m, lang) for m in item.get("meses") or [])
                marca = html.Span(t["g_reinc_voltou"].format(m=meses),
                                  className="text-danger fw-semibold")
                contexto = (t["g_reinc_depois"] if item.get("contexto") == "depois_do_aceite"
                            else t["g_reinc_antes"])
            else:
                faltam = item.get("meses_faltando") or 0
                marca = html.Span(
                    f"{t['g_reinc_observando']} "
                    f"({t['g_reinc_faltam'].format(n=faltam, u=_un(t, faltam, 'mes'))})",
                    className="text-muted")
                contexto = ""
            n_acoes = item.get("acoes") or 0
            acoes = t["g_reinc_acoes"].format(a=n_acoes, ua=_un(t, n_acoes, "acao"),
                                              f=item.get("acoes_feitas") or 0)
            linhas.append(html.Div([
                html.Div([
                    html.Span(item.get("equipamento") or "—", className="fw-semibold"),
                    html.Span(f" · {_rotulo_mes(item['mes'], lang)}" if item.get("mes") else "",
                              className="text-muted"),
                    html.Span(f" · {(item.get('falha') or '')[:60]}", className="text-muted"),
                ], style={"fontSize": "0.88rem"}),
                html.Div([marca,
                          html.Span(f" · {repetiu}", className="text-muted"),
                          html.Span(f" · {contexto}" if contexto else "",
                                    className="text-muted"),
                          html.Span(f" · {acoes}", className="text-muted")],
                         style={"fontSize": "0.8rem"}),
            ], id={"type": "g-linha-atencao", "chave": item.get("chave") or ""},
                className="py-2 border-bottom g-clicavel"))
        return html.Div(linhas)
