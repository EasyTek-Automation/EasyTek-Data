# src/callbacks_registers/failure_analysis_callbacks.py

"""
Callbacks da Análise de Paradas: aba de listagem + página do diagrama de Ishikawa.

Divide-se em dois blocos:
- `af-*` — a aba "Análise de Paradas" dentro de /maintenance/analise-de-falhas;
- `fa-*` — a página /maintenance/analise-de-falhas/ishikawa.

Ficam no mesmo módulo porque compartilham o mesmo domínio e o mesmo conjunto de
leitores; os prefixos garantem que nenhum callback da v2 (`v2-`) ou do Pareto
(`af-` de gráfico) seja disparado por engano.

Papéis (BR-AF2-10): ver/criar/editar/concluir exigem perfil manutenção nível ≥ 2
(a própria rota já garante); reabrir uma análise concluída exige nível ≥ 3.
"""

from datetime import datetime

import dash
from dash import ALL, Input, Output, State, dash_table, dcc, html, no_update
import dash_bootstrap_components as dbc
from flask_login import current_user

from src.pages.maintenance.analise_de_falhas import TRANS
from src.utils import failure_analysis_db as fdb
from src.utils.failure_a3 import mesclar_alturas
from src.utils.failure_events import (
    buscar_evento,
    buscar_eventos,
    duracao_na_faixa,
    exibir_todas_as_paradas,
)
from src.utils.failure_tree import (
    MODO_EXPLICATIVO,
    conflitos_de_pai,
    mensagem_com_titulos,
    reconciliar_arvore,
    MODO_MANUAL,
    PLACEHOLDER_CAUSA,
    TIPO_RAIZ,
    criar_etapa,
    criar_no,
    criar_ramificacao,
    distribuir_tempos,
    excluir_no,
    filhos,
    formatar_duracao,
    ids_manuais_em_excesso,
    indexar,
    marcar_causa_raiz,
    marcar_explicativo,
    marcar_tempo_manual,
    pode_reparentar,
    proximo_sort_order,
    reparent_muda_tipo,
    reparentar,
    resetar_tempos,
    sincronizar_tipos,
    tornar_tempo_auto,
    validar_tempos,
)

ROTA_LISTA = "/maintenance/analise-de-falhas"
ROTA_DIAGRAMA = "/maintenance/analise-de-falhas/ishikawa"

NIVEL_EDICAO = 2
# Entregar ao gestor exige nível 2 — é o nível de quem de fato analisa. Aceitar e
# devolver são do gestor (nível 4), único que destrava uma análise entregue.
NIVEL_CONCLUSAO = 2
NIVEL_GESTOR = 4


# ---------------------------------------------------------------------------
# Permissões
# ---------------------------------------------------------------------------

def _nivel_usuario() -> int:
    """Nível do usuário logado; 0 quando anônimo (não deveria chegar aqui)."""
    try:
        return int(getattr(current_user, "level", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _username() -> str:
    """Login do usuário corrente, para os campos de auditoria."""
    return str(getattr(current_user, "username", "") or "")


def _pode_editar(analise: dict | None) -> bool:
    """Editar exige nível ≥ 2 e análise aberta — concluída é somente leitura."""
    if not analise:
        return False
    # Entregue OU aceita = travada. Nem quem fez, nem o gestor, nem administrador
    # editam: o gestor precisa julgar o que foi entregue, e o que foi aceito precisa
    # continuar sendo o que ele aceitou (BR-16).
    from src.utils.failure_a3 import analise_travada

    if analise_travada(analise):
        return False
    return _nivel_usuario() >= NIVEL_EDICAO


def _lista_participantes(valor) -> list:
    """Normaliza `participantes` para lista (o campo virou multi-select).

    Retrocompat: análises antigas gravaram os participantes como texto livre
    separado por vírgula. Converte string → lista; lista já vem pronta.
    """
    if isinstance(valor, list):
        return [str(p).strip() for p in valor if str(p).strip()]
    if isinstance(valor, str) and valor.strip():
        return [p.strip() for p in valor.split(",") if p.strip()]
    return []


# ---------------------------------------------------------------------------
# Aba "Análise de Paradas" — listagem
# ---------------------------------------------------------------------------

_COLUNAS = [
    ("dt", "col_mes"),
    ("equip", "col_equip"),
    ("causa", "col_cause"),
    ("duracao", "col_duracao"),
    ("dias", "col_dias"),
    ("apont", "col_apont"),
    ("gatilho", "col_gatilho"),
    ("analise", "col_analise"),
    ("abrir", "col_abrir"),
]


def _linha(evento: dict, status_analise: str | None, tr: dict) -> dict:
    """Converte um evento de falha numa linha da tabela."""
    from src.utils.failure_events import nome_equipamento

    causa = (evento.get("rotulo") or "").strip()
    if not causa:
        causa = tr["sem_causa"]
    else:
        causa = f"{evento.get('causa')} — {causa}"

    rotulo_analise = {
        fdb.STATUS_ABERTA: tr["an_aberta"],
        fdb.STATUS_CONCLUIDA: tr["an_concluida"],
    }.get(status_analise, tr["an_nenhuma"])

    return {
        "chave": evento["chave"],  # fora de `columns`: não renderiza, mas identifica a linha
        # Parada MENSAL: a coluna mostra o mês (YYYY-MM). ISO e não MM/AAAA porque o
        # sort nativo do DataTable compara a string crua — só em ISO a ordem
        # alfabética coincide com a cronológica.
        "dt": (evento.get("mes") or evento["inicio"]).strftime("%Y-%m"),
        "equip": nome_equipamento(evento.get("equipamento") or ""),
        "causa": causa,
        "duracao": formatar_duracao(evento.get("duracao_min")),
        # Nº de dias com avaria no mês e nº de apontamentos: dizem se a duração é
        # uma parada grande ou a soma de várias pequenas ao longo do mês.
        "dias": evento.get("n_dias") or 1,
        "apont": evento.get("n_apontamentos") or 0,
        # Explica por que a linha está aqui (ou por que outra não está).
        # `buscar_eventos` anota `gatilho_min` nos dois modos do filtro.
        "gatilho": formatar_duracao(evento.get("gatilho_min")),
        "analise": rotulo_analise,
        "abrir": tr["btn_abrir"],
    }


_MESES = {
    "pt": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
           "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
    "es": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
           "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
}


def _estado_vazio(msg, icone, cor="muted"):
    """Placeholder de carregando / vazio / erro, no mesmo tom das demais páginas."""
    return html.Div(
        [
            html.I(className=f"bi bi-{icone}", style={"fontSize": "2rem", "opacity": "0.5"}),
            html.P(msg, className=f"text-{cor} mt-2 mb-0"),
        ],
        className="text-center py-5",
    )


def _grid_meses(eventos, ano, status_map, tr, lang):
    """Grade de 12 cards (um por mês do ano). Abrir um card lista as paradas do mês.

    Replica o visual dos mini-cards de mês da indicators-v2 (dbc.Card em Col
    xs=6/sm=4/md=3/lg=2, clicável por pattern-matching). O número é o total de
    paradas do mês; abaixo, quantas ainda estão sem análise."""
    meses = _MESES.get(lang, _MESES["pt"])
    por_mes = {m: {"n": 0, "com_analise": 0} for m in range(1, 13)}
    for e in eventos:
        mes = e.get("mes")
        if not mes or mes.year != ano:
            continue
        slot = por_mes[mes.month]
        slot["n"] += 1
        if status_map.get(e["chave"]):
            slot["com_analise"] += 1

    cols = []
    for m in range(1, 13):
        n = por_mes[m]["n"]
        pendentes = n - por_mes[m]["com_analise"]
        clicavel = n > 0
        style_card = {} if clicavel else {"opacity": 0.5}
        cor_valor = "#c0392b" if clicavel else "#adb5bd"
        if not clicavel:
            rodape = html.Small(" ", className="d-block mt-1")
        elif pendentes > 0:
            rodape = html.Small(f"{pendentes} {tr.get('card_pendentes', 'sem análise')}",
                                className="text-warning d-block mt-1")
        else:
            rodape = html.Small(tr.get("card_analisado", "tudo analisado"),
                                className="text-success d-block mt-1")
        corpo = dbc.CardBody(
            [
                html.Div(meses[m - 1], className="text-muted small mb-1"),
                html.Div(str(n), style={"fontSize": "1.6rem", "fontWeight": "bold",
                                        "color": cor_valor, "lineHeight": "1.1"}),
                html.Div(tr.get("card_paradas", "paradas"), className="text-muted",
                         style={"fontSize": "0.72rem"}),
                rodape,
            ],
            className="text-center py-3",
        )
        card = html.Div(dbc.Card(corpo, className="shadow-sm h-100", style=style_card),
                        n_clicks=0, style={"cursor": "pointer" if clicavel else "default"})
        if clicavel:
            card.id = {"type": "af-month", "month": m}
        cols.append(dbc.Col(card, xs=6, sm=4, md=3, lg=2, className="mb-3"))

    return html.Div([
        html.H6(f"{tr.get('meses_ano', 'Ano')} {ano}",
                className="text-muted fw-semibold mb-3"),
        dbc.Row(cols, className="g-2"),
    ])


def _botao_slides(ano, mes, tr):
    """Botão "Exportar slides do mês" do cabeçalho da lista de um mês (S4.1).

    Fica isolado, no canto oposto ao "Voltar aos meses" — a grade dos 12 cards não
    muda (premissa de preservação de UI). Desabilita quando o mês não tem nenhuma
    análise, com o aviso ao lado, em vez de baixar um arquivo só com a capa.

    A contagem vem das **análises** no banco, não das paradas da tela: a análise órfã
    (parada que saiu da agregação) não aparece na lista mas entra no material.
    """
    n = fdb.contar_analises_do_mes(f"{ano:04d}{mes:02d}")
    botao = dbc.Button(
        [html.I(className="bi bi-file-earmark-slides me-1"),
         html.Span(tr.get("slides_btn", "Exportar slides do mês"))],
        id="af-btn-slides", size="sm", color="dark", outline=True,
        disabled=n == 0,
    )
    if n:
        return botao
    return html.Div([
        html.Small(tr.get("slides_vazio", "Nenhuma análise neste mês — nada a exportar."),
                   className="text-muted me-2"),
        botao,
    ], className="d-flex align-items-center")


def _tabela_dt(linhas, page_size, view, tr):
    """A DataTable de paradas (lista de um mês). Mesma configuração de sempre."""
    view = view or {}
    try:
        tamanho = max(1, int(page_size or 20))
    except (TypeError, ValueError):
        tamanho = 20
    return dash_table.DataTable(
        id="af-paradas-table",
        data=linhas,
        columns=[{"name": tr[k], "id": cid} for cid, k in _COLUNAS],
        page_size=tamanho,
        page_current=view.get("page_current", 0),
        sort_action="native",
        sort_by=view.get("sort_by") or [{"column_id": "dt", "direction": "desc"}],
        style_as_list_view=True,
        style_table={"overflowX": "auto"},
        style_cell={"fontSize": "0.82rem", "padding": "8px",
                    "textAlign": "left", "fontFamily": "inherit"},
        style_header={"fontWeight": "600", "backgroundColor": "rgba(0,0,0,0.03)"},
        style_cell_conditional=[
            {"if": {"column_id": "causa"}, "minWidth": "260px", "maxWidth": "420px",
             "whiteSpace": "normal", "height": "auto"},
            {"if": {"column_id": "abrir"}, "textAlign": "center", "width": "150px"},
            {"if": {"column_id": "duracao"}, "width": "110px"},
        ],
        style_data_conditional=[
            {"if": {"column_id": "abrir"},
             "color": "#0d6efd", "cursor": "pointer", "fontWeight": "600"},
        ],
        css=[{"selector": ".dash-spreadsheet td.focused", "rule": "outline: none;"}],
    )


def register_failure_analysis_callbacks(app):
    """Registra os callbacks da aba de paradas e da página do diagrama."""

    # -- Listagem --------------------------------------------------------

    @app.callback(
        Output("af-paradas-container", "children"),
        Input("store-af-filters", "data"),
        Input("store-af-lang", "data"),
        Input("af-paradas-page-size", "value"),
        Input("store-af-paradas-mes", "data"),
        State("store-af-paradas-view", "data"),
    )
    def _render_paradas(filtros, lang, page_size, mes, view):
        """Aba Análise de Paradas: grade dos 12 meses do ano; abrir um mês lista
        as paradas daquele mês.

        Reusa `store-af-filters` — os filtros valem para as três abas. `mes`
        (`store-af-paradas-mes`) decide grade × lista. Restaura página/ordenação
        de `store-af-paradas-view` na lista (caso 20).
        """
        tr = TRANS.get(lang or "pt", TRANS["pt"])
        if not filtros:
            return _estado_vazio(tr["loading"], "hourglass-split")

        from src.callbacks_registers.analise_falhas_callbacks import _resolve_window

        # Só esta aba respeita o gatilho — Pareto e Dados seguem com tudo (BR-01).
        todas = exibir_todas_as_paradas(filtros)
        try:
            inicio, fim = _resolve_window(filtros)
            eventos = buscar_eventos(
                inicio, fim,
                breakdown_codes=filtros.get("codes"),
                equipamentos=filtros.get("equip"),
                apenas_acima_do_gatilho=not todas,
            )
        except Exception as e:
            print(f"[failure_analysis] falha ao listar paradas: {e}")
            return _estado_vazio(tr["paradas_erro"], "exclamation-triangle", cor="danger")

        # Faixa de duração — aqui a linha é um evento agregado (soma do mês), então
        # a faixa é avaliada sobre a duração do evento, não de cada apontamento.
        eventos = [e for e in eventos
                   if duracao_na_faixa(e.get("duracao_min"), filtros.get("duracao"))]

        ano = inicio.year
        status = fdb.chaves_com_analise([e["chave"] for e in eventos])

        # GRADE dos meses (nível 1): um card por mês do ano.
        if not mes:
            return _grid_meses(eventos, ano, status, tr, lang or "pt")

        # LISTA de um mês (nível 2): paradas daquele mês + voltar.
        meses = _MESES.get(lang or "pt", _MESES["pt"])
        eventos_mes = [e for e in eventos
                       if e.get("mes") and e["mes"].month == mes and e["mes"].year == ano]
        cabecalho = html.Div([
            html.Div([
                dbc.Button(
                    [html.I(className="bi bi-arrow-left me-1"),
                     tr.get("voltar_meses", "Voltar aos meses")],
                    id="af-paradas-voltar", size="sm", color="link",
                    className="px-0 text-decoration-none",
                ),
                _botao_slides(ano, mes, tr),
            ], className="d-flex justify-content-between align-items-center"),
            html.H6(f"{meses[mes - 1]} {ano} · {len(eventos_mes)} "
                    f"{tr.get('card_paradas', 'paradas')}",
                    className="mt-1 mb-3 fw-semibold"),
        ])
        if not eventos_mes:
            vazio = tr["paradas_vazio"] if todas else tr["paradas_vazio_gatilho"]
            return html.Div([cabecalho, _estado_vazio(vazio, "inbox")])
        linhas = [_linha(e, status.get(e["chave"]), tr) for e in eventos_mes]
        return html.Div([cabecalho, _tabela_dt(linhas, page_size, view, tr)])

    @app.callback(
        Output("store-af-paradas-mes", "data"),
        Input({"type": "af-month", "month": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _abrir_mes(clicks):
        """Card de mês clicado → guarda o mês (dispara a lista daquele mês)."""
        if not clicks or not any(clicks):
            return no_update
        alvo = dash.ctx.triggered_id
        return (alvo or {}).get("month")

    @app.callback(
        Output("store-af-paradas-mes", "data", allow_duplicate=True),
        Input("af-paradas-voltar", "n_clicks"),
        prevent_initial_call=True,
    )
    def _voltar_meses(n):
        """"Voltar aos meses" → limpa o mês, volta pra grade.

        O guard `not n` não é decorativo: o botão nasce junto com a lista do mês, e
        `prevent_initial_call` só cobre o load da página — componente criado depois
        dispara o callback na criação, com `n_clicks=None`. Sem o guard, abrir um mês
        zerava `store-af-paradas-mes` no mesmo instante em que ele foi preenchido (a
        lista continuava na tela, mas o store ficava `null` — e quem lesse o store
        depois, como o botão de exportar slides, não sabia qual mês estava aberto).
        Mesmo idioma do guard de `_abrir_mes`.
        """
        if not n:
            return no_update
        return None

    @app.callback(
        Output("download-af-slides", "data"),
        Output("af-slides-toast", "is_open"),
        Output("af-slides-toast", "children"),
        Input("af-btn-slides", "n_clicks"),
        State("store-af-paradas-mes", "data"),
        State("store-af-filters", "data"),
        State("store-af-lang", "data"),
        # Só o rótulo entra no `running` — **não** o `disabled`. Motivo: este callback
        # também dispara quando o botão é criado (abrir um mês), e o valor "off" do
        # running seria aplicado aí, reabilitando o botão de um mês sem análise nenhuma.
        # Quem manda no `disabled` é o servidor, em `_botao_slides`.
        running=[
            (Output("af-btn-slides", "children"),
             [dbc.Spinner(size="sm", spinner_class_name="me-1"),
              html.Span(TRANS["pt"]["slides_gerando"])],
             [html.I(className="bi bi-file-earmark-slides me-1"),
              html.Span(TRANS["pt"]["slides_btn"])]),
        ],
        prevent_initial_call=True,
    )
    def _exportar_slides(n, mes, filtros, lang):
        """Gera o material mensal em PowerPoint do mês aberto e devolve o download (S4).

        O ano vem da mesma janela que a listagem usa (`_resolve_window`), para o arquivo
        casar com o que está na tela. Falha na geração não pode derrubar a página: vira
        toast e o botão volta ao normal.
        """
        tr = TRANS.get(lang or "pt", TRANS["pt"])
        if not n or not mes:
            return no_update, no_update, no_update

        from src.callbacks_registers.analise_falhas_callbacks import _resolve_window
        from src.utils.failure_slides_pptx import gerar_mes

        try:
            inicio, _fim = _resolve_window(filtros or {})
            dados, nome = gerar_mes(inicio.year, int(mes))
        except Exception as e:  # noqa: BLE001
            print(f"[failure_analysis] falha ao gerar slides de {mes}: {e}")
            return no_update, True, tr.get("slides_erro",
                                           "Não foi possível gerar os slides do mês.")
        return (
            dcc.send_bytes(
                dados, nome,
                type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            False,
            no_update,
        )

    @app.callback(
        Output("store-af-paradas-view", "data"),
        Input("af-paradas-table", "page_current"),
        Input("af-paradas-table", "sort_by"),
        Input("af-paradas-page-size", "value"),
        prevent_initial_call=True,
    )
    def _guardar_view(page_current, sort_by, page_size):
        """Guarda página/ordenação/tamanho para restaurar ao voltar do diagrama (caso 20)."""
        return {
            "page_current": page_current or 0,
            "sort_by": sort_by,
            "page_size": page_size,
        }

    @app.callback(
        Output("af-paradas-page-size", "value"),
        Input("url", "pathname"),
        State("store-af-paradas-view", "data"),
    )
    def _hidratar_page_size(pathname, view):
        """Restaura o tamanho de página escolhido ao reentrar na listagem."""
        if pathname != ROTA_LISTA or not view or not view.get("page_size"):
            return no_update
        return view["page_size"]

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Output("url", "search", allow_duplicate=True),
        Input("af-paradas-table", "active_cell"),
        State("af-paradas-table", "derived_viewport_data"),
        prevent_initial_call=True,
    )
    def _abrir_diagrama(active_cell, dados_visiveis):
        """Clique em "Abrir diagrama" navega para a análise daquela parada.

        Usa `active_cell` em vez de link markdown para navegar pelo roteador do
        Dash, sem recarregar a página inteira. Não limpa `active_cell` de volta:
        Output e Input no mesmo prop seria dependência circular — e a tabela é
        recriada ao voltar, então a seleção já nasce limpa.
        """
        if not active_cell or active_cell.get("column_id") != "abrir":
            return no_update, no_update
        try:
            linha = (dados_visiveis or [])[active_cell["row"]]
        except (IndexError, KeyError, TypeError):
            return no_update, no_update
        chave = linha.get("chave")
        if not chave:
            return no_update, no_update
        return ROTA_DIAGRAMA, f"?parada={chave}"

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Output("url", "search", allow_duplicate=True),
        Input("fa-btn-voltar", "n_clicks"),
        prevent_initial_call=True,
    )
    def _voltar(n):
        """Volta à listagem. A view (página/ordenação) vem do store de sessão."""
        if not n:
            return no_update, no_update
        return ROTA_LISTA, ""

    @app.callback(
        Output("download-fa-slide", "data"),
        Output("fa-toast", "is_open", allow_duplicate=True),
        Output("fa-toast", "children", allow_duplicate=True),
        Output("fa-toast", "icon", allow_duplicate=True),
        Input("fa-btn-exportar-slide", "n_clicks"),
        State("store-fa-chave", "data"),
        # Só o rótulo no `running` — nunca o `disabled`. Este callback também dispara
        # quando o botão é criado (o valor "off" seria aplicado aí). Mesma armadilha
        # documentada no botão de exportar o mês.
        running=[
            (Output("fa-btn-exportar-slide", "children"),
             [dbc.Spinner(size="sm", spinner_class_name="me-1"), html.Span("Gerando…")],
             [html.I(className="bi bi-file-earmark-slides me-1"),
              html.Span("Exportar esta análise")]),
        ],
        prevent_initial_call=True,
    )
    def _exportar_slide(n, chave):
        """Baixa esta análise sozinha num `.pptx` de um slide (S5).

        Relê a análise do banco em vez de usar o store da tela: o arquivo reflete o que
        está **salvo**. Edição ainda não salva não entra no slide — assim o que foi para
        a reunião é o mesmo que está registrado no sistema.
        """
        if not n or not chave:
            return no_update, no_update, no_update, no_update

        from src.utils.failure_slides_pptx import gerar_analise

        analise = fdb.carregar_analise(chave)
        if not analise:
            return (no_update, True,
                    "Não foi possível carregar esta análise para exportar.", "danger")
        try:
            dados, nome = gerar_analise(analise)
        except Exception as e:  # noqa: BLE001
            print(f"[failure_analysis] falha ao exportar slide de {chave}: {e}")
            return no_update, True, "Não foi possível gerar o slide desta análise.", "danger"
        return (
            dcc.send_bytes(
                dados, nome,
                type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            no_update, no_update, no_update,
        )

    # -- Página do diagrama ----------------------------------------------

    @app.callback(
        Output("store-fa-analise", "data"),
        Output("store-fa-nos", "data"),
        Output("store-fa-nos-original", "data"),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Output("fa-toast", "is_open", allow_duplicate=True),
        Output("fa-toast", "children", allow_duplicate=True),
        Output("fa-toast", "icon", allow_duplicate=True),
        Input("store-fa-chave", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def _carregar(chave):
        """Carrega a parada e a análise, criando-a na primeira abertura (casos 2 a 5).

        `obter_ou_criar_analise` é idempotente: reabrir a página não duplica a
        análise nem recria os nós iniciais. `sincronizar_tipos` é a ponte de
        retrocompat: análises antigas só tinham ROOT/CAUSE — os filhos diretos do
        ROOT viram STEP no load. O snapshot original alimenta o Descartar.
        """
        if not chave:
            return None, None, None, False, True, "Parada não informada na URL.", "danger"

        evento = buscar_evento(chave)
        if not evento:
            return (None, None, None, False, True,
                    "Parada não encontrada. Ela pode ter saído do período importado do ZPP.",
                    "danger")

        if _nivel_usuario() < NIVEL_EDICAO:
            # Sem permissão de criar: mostra a análise se já existir, senão avisa.
            analise = fdb.carregar_analise(chave)
            if not analise:
                return (None, None, None, False, True,
                        "Você não tem permissão para criar uma análise para esta parada.",
                        "warning")
            nos = sincronizar_tipos(analise.get("nos") or [])
            return analise, nos, nos, False, False, "", "info"

        analise, criada = fdb.obter_ou_criar_analise(evento, _username())
        if not analise:
            return (None, None, None, False, True,
                    "Não foi possível carregar a análise. Verifique a conexão com o banco.",
                    "danger")

        nos = sincronizar_tipos(analise.get("nos") or [])
        msg = "Análise criada a partir dos dados da parada." if criada else ""
        return analise, nos, nos, False, bool(criada), msg, "success"

    @app.callback(
        Output("fa-titulo-exibicao", "children"),
        Output("fa-subtitulo", "children"),
        Output("fa-status-badge", "children"),
        Output("fa-parada-data", "children"),
        Output("fa-parada-inicio", "children"),
        Output("fa-parada-fim", "children"),
        Output("fa-parada-duracao", "children"),
        Output("fa-parada-equip", "children"),
        Output("fa-parada-causa", "children"),
        Output("fa-titulo", "value"),
        Output("fa-nome", "value"),
        Output("fa-responsavel", "value"),
        Output("fa-participantes", "value"),
        Input("store-fa-analise", "data"),
    )
    def _render_cabecalho(analise):
        """Preenche o cabeçalho com o snapshot da parada + campos do A3."""
        if not analise:
            # 13 saídas nesta ordem: 3 do cabeçalho (título/subtítulo/badge) + 6 do
            # resumo (data..causa) + 4 editáveis (titulo, nome, responsável,
            # PARTICIPANTES). Participantes é multi-select → vazio é [], não "".
            # (Área/Subgrupo saíram do cabeçalho — são editados só na Seção 1 do A3.)
            return ("—", "", None) + ("",) * 9 + ([],)

        p = analise.get("parada") or {}
        inicio = _dt(p.get("inicio"))
        fim = _dt(p.get("fim"))

        concluida = analise.get("status") == fdb.STATUS_CONCLUIDA
        badge = dbc.Badge(
            "Concluída" if concluida else "Em andamento",
            color="success" if concluida else "warning",
            className="ms-2", pill=True,
        )

        ordens = ", ".join(str(o) for o in (p.get("ordens") or []))
        n_dias = p.get("n_dias") or 1
        dias_txt = f" em {n_dias} dia(s) do mês" if n_dias and n_dias > 1 else ""
        sub = (f"{p.get('n_apontamentos', 0)} apontamento(s) do ZPP{dias_txt}"
               + (f" · ordem(ns) {ordens}" if ordens else ""))

        # No topo mostra o Nome quando o usuário deu um; senão, o título fixo.
        return (
            (analise.get("nome") or "").strip() or analise.get("titulo") or "—",
            sub,
            badge,
            inicio.strftime("%d/%m/%Y") if inicio else "—",
            inicio.strftime("%H:%M") if inicio else "—",
            fim.strftime("%H:%M") if fim else "—",
            formatar_duracao(p.get("duracao_min")),
            p.get("equipamento_nome") or p.get("equipamento") or "—",
            p.get("causa") or "—",
            analise.get("titulo") or "",
            analise.get("nome") or "",
            analise.get("responsavel") or "",
            _lista_participantes(analise.get("participantes")),
        )

    @app.callback(
        Output("fa-por-dia", "children"),
        Input("store-fa-analise", "data"),
    )
    def _render_por_dia(analise):
        """Composição diária da parada mensal (drill "1 grande vs várias pequenas").

        Barras proporcionais por dia. Fica vazio quando a falha foi num único dia —
        aí não há o que decompor."""
        por_dia = ((analise or {}).get("parada") or {}).get("por_dia") or []
        if len(por_dia) <= 1:
            return ""  # dia único: nada a decompor
        maxd = max((d.get("duracao_min") or 0) for d in por_dia) or 1
        linhas = []
        for d in por_dia:
            dur = d.get("duracao_min") or 0
            iso = str(d.get("dia") or "")
            rotulo = f"{iso[8:10]}/{iso[5:7]}" if len(iso) >= 10 else iso  # DD/MM
            linhas.append(html.Div([
                html.Span(rotulo, className="text-muted",
                          style={"width": "44px", "flex": "0 0 44px", "fontSize": "0.75rem"}),
                html.Div(
                    html.Div(style={"width": f"{dur / maxd * 100:.0f}%", "height": "100%",
                                    "backgroundColor": "#c0392b", "borderRadius": "3px",
                                    "minWidth": "2px"}),
                    style={"flex": "1", "backgroundColor": "rgba(0,0,0,0.05)",
                           "height": "14px", "borderRadius": "3px", "margin": "0 8px"},
                ),
                html.Span(formatar_duracao(dur), className="text-muted",
                          style={"width": "64px", "flex": "0 0 64px", "textAlign": "right",
                                 "fontSize": "0.75rem"}),
            ], className="d-flex align-items-center mb-1"))
        return html.Div([
            html.Div(f"Composição no mês · {len(por_dia)} dias",
                     className="text-uppercase text-muted fw-bold mb-2",
                     style={"fontSize": "0.72rem", "letterSpacing": "0.04em"}),
            *linhas,
        ])

    @app.callback(
        Output("fa-responsavel", "options"),
        Output("fa-responsavel-help", "children"),
        Output("fa-participantes", "options"),
        Input("store-fa-analise", "data"),
    )
    def _popular_responsaveis(analise):
        """Popula os selects de responsável e participantes com os usuários do banco.

        Segue a regra já usada no workflow: admin atribui a qualquer usuário; os
        demais, só a usuários do próprio perfil. O responsável já gravado é
        mantido na lista mesmo que não esteja mais entre os usuários ativos.
        Participantes usa a mesma lista de usuários (multi-select); qualquer nome
        já gravado que não esteja mais na lista é preservado como opção.
        """
        perfil = str(getattr(current_user, "perfil", "") or "")
        atual = (analise or {}).get("responsavel")
        opcoes = fdb.opcoes_responsaveis(perfil, atual)

        # Opções dos participantes = mesmos usuários, garantindo os já gravados.
        part_opcoes = list(opcoes)
        for p in _lista_participantes((analise or {}).get("participantes")):
            part_opcoes = fdb.garantir_opcao_atual(part_opcoes, p)

        if not opcoes:
            return [], "Nenhum usuário disponível para atribuição.", part_opcoes
        ajuda = ("Você pode atribuir para qualquer usuário (admin)."
                 if perfil == "admin"
                 else f"Usuários do departamento {perfil}.")
        return opcoes, ajuda, part_opcoes

    @app.callback(
        Output("fa-alerta-permissao", "children"),
        Output("fa-faixa-estado", "children"),
        Output("fa-btn-salvar", "disabled"),
        Output("fa-btn-concluir", "disabled"),
        Output("fa-btn-aceitar", "style"),
        Output("fa-btn-devolver", "style"),
        Input("store-fa-analise", "data"),
    )
    def _aplicar_permissoes(analise):
        """Trava a interface conforme papel e estado da análise (BR-15, BR-16).

        Botão que a pessoa não pode usar **não aparece** — em vez de aparecer
        desabilitado sem explicação. A recusa de verdade mora no servidor; esconder é
        conforto, não bloqueio.
        """
        from src.utils.failure_a3 import (
            ESTADO_ABERTA, ESTADO_ACEITA, ESTADO_DEVOLVIDA, ESTADO_ENTREGUE,
            estado_analise, passagens,
        )

        oculto = {"display": "none"}
        if not analise:
            return None, None, True, True, oculto, oculto

        estado = estado_analise(analise)
        nivel = _nivel_usuario()
        gestor = nivel >= NIVEL_GESTOR
        editavel = _pode_editar(analise)
        pode_entregar_ui = editavel and nivel >= NIVEL_CONCLUSAO

        alerta = None
        if estado == ESTADO_ABERTA and nivel < NIVEL_EDICAO:
            alerta = dbc.Alert(
                [html.I(className="bi bi-eye me-2"), "Você tem acesso somente de leitura."],
                color="info", className="py-2 small")

        faixa = _faixa_de_estado(estado, analise, passagens(analise), gestor)

        mostrar_gestor = {} if (gestor and estado in (ESTADO_ENTREGUE, ESTADO_ACEITA)) else oculto
        # Aceitar só faz sentido no que ainda não foi aceito; devolver serve para os
        # dois — é o único jeito de destravar.
        botao_aceitar = mostrar_gestor if estado == ESTADO_ENTREGUE else oculto
        return (alerta, faixa, not editavel, not pode_entregar_ui,
                botao_aceitar, mostrar_gestor)

    def _quando(valor):
        """Data de uma passagem, para leitura humana. Aceita texto ou data."""
        if isinstance(valor, str):
            valor = valor[:10]
            try:
                d = datetime.strptime(valor, "%Y-%m-%d")
            except ValueError:
                return valor
        elif isinstance(valor, datetime):
            d = valor
        else:
            return ""
        return d.strftime("%d/%m/%Y")

    def _faixa_de_estado(estado, analise, hist, gestor):
        """A faixa que diz em que pé está a análise e desde quando (SP-10)."""
        from src.utils.failure_a3 import ESTADO_ACEITA, ESTADO_DEVOLVIDA, ESTADO_ENTREGUE

        if estado == ESTADO_ENTREGUE:
            entrega = next((p for p in reversed(hist) if p.get("acao") == "entregue"), {})
            quem = entrega.get("por") or analise.get("concluido_por") or "—"
            quando = _quando(entrega.get("em") or analise.get("data_conclusao_analise"))
            texto = f"Entregue por {quem}" + (f" em {quando}" if quando else "")
            texto += " · aguardando aceite do gestor"
            if not gestor:
                texto += ". Para corrigir, peça a devolução."
            return dbc.Alert([html.I(className="bi bi-hourglass-split me-2"), texto],
                             color="info", className="py-2 small mb-2")

        if estado == ESTADO_ACEITA:
            aceite = (analise.get("aceite") or {})
            quem = aceite.get("aceito_por") or "—"
            quando = _quando(aceite.get("aceito_em"))
            entregou = next((p.get("por") for p in reversed(hist)
                             if p.get("acao") == "entregue"), None)
            # Entregue e aceita pela mesma pessoa não é proibido (a planta tem dois
            # gestores), mas fica à mostra: transparência resolve o que a proibição
            # só emperraria (BR-15).
            rotulo = (f"Entregue e aceita por {quem}" if entregou == quem
                      else f"Aceita por {quem}")
            texto = rotulo + (f" em {quando}" if quando else "")
            if not gestor:
                texto += ". Para corrigir, peça a devolução."
            return dbc.Alert([html.I(className="bi bi-lock me-2"), texto],
                             color="secondary", className="py-2 small mb-2")

        if estado == ESTADO_DEVOLVIDA:
            ultima = hist[-1] if hist else {}
            quem = ultima.get("por") or "—"
            quando = _quando(ultima.get("em"))
            motivo = (ultima.get("motivo") or "").strip()
            devolucoes = sum(1 for p in hist if p.get("acao") == "devolvida")
            corpo = [html.I(className="bi bi-arrow-counterclockwise me-2"),
                     f"Devolvida por {quem}" + (f" em {quando}" if quando else "")]
            if motivo:
                corpo.append(html.Span(f" — “{motivo}”", className="fst-italic"))
            if devolucoes > 1:
                corpo.append(html.Span(f" · devolvida {devolucoes}×", className="ms-1"))
            return dbc.Alert(corpo, color="warning", className="py-2 small mb-2")

        return None

    # -- Encerramento (Seção 6): assinatura (só o próprio usuário) + data ----

    @app.callback(
        Output("fa-sec-enc-resp", "options"),
        Output("fa-sec-enc-resp", "value"),
        Output("fa-sec-enc-data", "date"),
        Input("store-fa-analise", "data"),
    )
    def _encerramento_load(analise):
        """A assinatura final é **restrita ao usuário logado** (não digitação livre):
        análise aberta → única opção é você; concluída → mostra quem assinou. A data é
        um DatePicker, semeado da análise carregada."""
        if not analise:
            return [], None, None
        key = _username()
        closing = analise.get("closing") or {}
        data = closing.get("data")
        if analise.get("status") == fdb.STATUS_CONCLUIDA:
            assinou = closing.get("responsavel") or key
            return [{"label": assinou, "value": assinou}], assinou, data
        return ([{"label": key, "value": key}] if key else []), (key or None), data

    @app.callback(
        Output("store-fa-secoes", "data", allow_duplicate=True),
        Input("fa-sec-enc-resp", "value"),
        Input("fa-sec-enc-data", "date"),
        State("store-fa-secoes", "data"),
        prevent_initial_call=True,
    )
    def _encerramento_store(assinatura, data, secoes):
        """Grava assinatura (usuário logado) + data em `closing`."""
        secoes = dict(secoes or {})
        closing = dict(secoes.get("closing") or {})
        closing["responsavel"] = assinatura or ""
        closing["data"] = data
        secoes["closing"] = closing
        return secoes

    # -- Diagrama --------------------------------------------------------

    @app.callback(
        Output("fa-diagrama", "elements"),
        Output("fa-alerta-tempo", "children"),
        Input("store-fa-nos", "data"),
        Input("fa-switch-tempos", "value"),
        State("store-fa-analise", "data"),
    )
    def _render_diagrama(nos, mostrar_tempos, analise):
        """Monta os elementos do cytoscape a partir da árvore corrente.

        Com "Exibir tempos" on, TODOS os balões (menos o ROOT) mostram a duração;
        os manuais levam um 🔒. Balões em grupo com tempo inconsistente
        (estouro/divergência) ficam marcados (`tempo_erro`) para destaque vermelho.
        """
        if not nos:
            return [], None

        total = ((analise or {}).get("parada") or {}).get("duracao_min") or 0
        exibir = "sim" in (mostrar_tempos or [])
        ids_erro = set(ids_manuais_em_excesso(nos, total))

        elementos = []
        for n in nos:
            rotulo = (n.get("titulo") or "").strip()
            tipo = n.get("tipo")
            if not rotulo and tipo != TIPO_RAIZ:
                rotulo = PLACEHOLDER_CAUSA
            explicativo = n.get("duration_mode") == MODO_EXPLICATIVO
            if exibir and tipo == TIPO_RAIZ:
                rotulo = f"{rotulo}\nΣ {formatar_duracao(total)}"
            elif exibir and explicativo:
                rotulo = f"{rotulo}\n— sem tempo"
            elif exibir:
                marca = " 🔒" if n.get("duration_mode") == MODO_MANUAL else ""
                rotulo = f"{rotulo}\n⏱ {formatar_duracao(n.get('duration_min'))}{marca}"
            elementos.append({"data": {
                "id": n["id"], "label": rotulo, "tipo": tipo,
                "is_root_cause": bool(n.get("is_root_cause")),
                "explicativo": explicativo,
                "tempo_erro": n["id"] in ids_erro,
            }})
        for n in nos:
            if n.get("parent_id"):
                elementos.append({"data": {"source": n["parent_id"], "target": n["id"]}})

        ok, msg = validar_tempos(nos, total)
        alerta = None if ok else dbc.Alert(
            [html.I(className="bi bi-exclamation-triangle me-2"), msg],
            color="danger", className="py-2 small mb-0",
        )
        return elementos, alerta

    # -- Painel da etapa selecionada -------------------------------------

    @app.callback(
        Output("store-fa-selecionado", "data"),
        Input("fa-diagrama", "tapNodeData"),
    )
    def _selecionar(node_data):
        """Guarda o nó clicado no diagrama."""
        return (node_data or {}).get("id")

    # -- Toolbar do balão selecionado -----------------------------------

    @app.callback(
        Output("store-fa-nos", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Output("store-fa-selecionado", "data", allow_duplicate=True),
        Output("fa-toast", "is_open", allow_duplicate=True),
        Output("fa-toast", "children", allow_duplicate=True),
        Output("fa-toast", "icon", allow_duplicate=True),
        Output("store-fa-editar-novo", "data"),
        Input("fa-tb-irma", "n_clicks"),
        Input("fa-tb-ramif", "n_clicks"),
        Input("fa-tb-raiz", "n_clicks"),
        Input("fa-tb-excluir", "n_clicks"),
        Input("fa-tb-promover", "n_clicks"),
        Input("fa-tb-rebaixar", "n_clicks"),
        State("store-fa-selecionado", "data"),
        State("store-fa-nos", "data"),
        State("store-fa-analise", "data"),
        # Só para contar, no aviso do ★, quantas ações a causa perde ao ser
        # desmarcada — uma causa pode ter várias (BR-AF2-14).
        State("store-fa-secoes", "data"),
        prevent_initial_call=True,
    )
    def _toolbar_ops(n_irma, n_ramif, n_raiz, n_excl, n_prom, n_reb, sel, nos, analise,
                     secoes):
        """Operações do balão selecionado, disparadas pela toolbar flutuante.

        + Irmã cria um balão irmão (STEP se o pai for o ROOT, senão CAUSE);
        + Ramif. cria um filho CAUSE; ★ marca/desmarca a causa raiz; 🗑 exclui a
        ramificação; « sobe o balão um nível (vira irmão do pai) e » o rebaixa
        (vira filho do irmão logo acima). Toda mudança estrutural ressincroniza
        tipos e redistribui o tempo (só STEP rateia) e marca a página como não
        salva. A causa raiz marcada (★) vincula-se às ações do Plano de Ação por
        `node_id`; não há mais seção/tabela de causa raiz separada.
        """
        if not sel or not nos:
            return (no_update,) * 7
        if not _pode_editar(analise):
            return (no_update, no_update, no_update, True,
                    "Você não pode editar esta análise.", "warning", no_update)

        gatilho = (dash.callback_context.triggered[0]["prop_id"] or "").split(".")[0]
        nos = [dict(n) for n in nos]
        idx = indexar(nos)
        no = idx.get(sel)
        if not no:
            return (no_update,) * 7

        analysis_id = (analise or {}).get("id")
        total = ((analise or {}).get("parada") or {}).get("duracao_min") or 0
        novo_sel = no_update
        abrir = no_update   # id do balão novo → o clientside abre o editor de texto nele
        msg = ""

        if gatilho == "fa-tb-irma":
            if no.get("tipo") == TIPO_RAIZ:
                novo = criar_etapa(analysis_id, sel, "", sort_order=proximo_sort_order(nos, sel))
            else:
                pai = no.get("parent_id")
                novo = criar_no(analysis_id, pai, "", tipo=no.get("tipo"),
                                sort_order=proximo_sort_order(nos, pai))
            nos.append(novo)
            novo_sel = abrir = novo["id"]
            msg = "Balão irmão criado."

        elif gatilho == "fa-tb-ramif":
            novo = criar_ramificacao(analysis_id, sel, "",
                                     sort_order=proximo_sort_order(nos, sel))
            nos.append(novo)
            novo_sel = abrir = novo["id"]
            msg = "Ramificação criada."

        elif gatilho == "fa-tb-raiz":
            if no.get("tipo") == TIPO_RAIZ:
                return (no_update,) * 7
            marcado = not no.get("is_root_cause")
            # Desmarcar apaga TODAS as ações daquela causa, não só uma — desde que
            # a causa pode ter várias. Dizer quantas evita a perda silenciosa.
            perdidas = 0
            if not marcado:
                perdidas = sum(1 for a in ((secoes or {}).get("actions") or [])
                               if a.get("node_id") == sel)
            nos = marcar_causa_raiz(nos, sel, marcado)
            if marcado:
                msg = "Causa raiz marcada."
            elif perdidas > 1:
                msg = f"Causa raiz desmarcada — as {perdidas} ações dela saíram do plano."
            elif perdidas == 1:
                msg = "Causa raiz desmarcada — a ação dela saiu do plano."
            else:
                msg = "Causa raiz desmarcada."

        elif gatilho == "fa-tb-excluir":
            if no.get("tipo") == TIPO_RAIZ:
                return (no_update, no_update, no_update, True,
                        "O evento de parada não pode ser excluído.", "warning", no_update)
            nos = excluir_no(nos, sel, promover_filhos=False)
            novo_sel = None
            msg = "Balão excluído."

        elif gatilho == "fa-tb-promover":
            # « sobe um nível: o balão vira irmão do próprio pai (novo pai = avô).
            if no.get("tipo") == TIPO_RAIZ:
                return (no_update,) * 7
            avo = (idx.get(no.get("parent_id")) or {}).get("parent_id")
            ok, motivo = pode_reparentar(nos, sel, avo)
            if not ok:
                return (no_update, no_update, no_update, True,
                        f"Não dá para subir este balão: {motivo}", "warning", no_update)
            mudou_tipo = reparent_muda_tipo(nos, sel, avo)
            nos = reparentar(nos, sel, avo)
            msg = "Balão subiu um nível."
            if mudou_tipo:
                msg += " O tipo mudou — o rateio de tempo foi recalculado."

        elif gatilho == "fa-tb-rebaixar":
            # » desce um nível: o balão vira filho do irmão logo acima dele.
            if no.get("tipo") == TIPO_RAIZ:
                return (no_update,) * 7
            irmaos = filhos(nos, no.get("parent_id"))
            pos = next((i for i, irm in enumerate(irmaos) if irm["id"] == sel), 0)
            if pos == 0:
                return (no_update, no_update, no_update, True,
                        "Não há balão acima no mesmo nível para receber este.",
                        "warning", no_update)
            anterior = irmaos[pos - 1]["id"]
            ok, motivo = pode_reparentar(nos, sel, anterior)
            if not ok:
                return (no_update, no_update, no_update, True,
                        f"Não dá para descer este balão: {motivo}", "warning", no_update)
            mudou_tipo = reparent_muda_tipo(nos, sel, anterior)
            nos = reparentar(nos, sel, anterior)
            msg = "Balão desceu um nível."
            if mudou_tipo:
                msg += " O tipo mudou — o rateio de tempo foi recalculado."

        nos = sincronizar_tipos(nos)
        return distribuir_tempos(nos, total), True, novo_sel, True, msg, "success", abrir

    # -- Edição inline do texto do balão --------------------------------

    @app.callback(
        Output("fa-inline-editor", "style", allow_duplicate=True),
        Output("fa-inline-text", "value"),
        Input("fa-tb-editar", "n_clicks"),
        State("store-fa-selecionado", "data"),
        State("store-fa-nos", "data"),
        State("fa-inline-editor", "style"),
        prevent_initial_call=True,
    )
    def _abrir_editor_inline(n, sel, nos, style):
        """Mostra o editor inline com o texto do balão selecionado."""
        if not sel or not nos:
            return no_update, no_update
        no = indexar(nos).get(sel)
        if not no or no.get("tipo") == TIPO_RAIZ:
            return no_update, no_update
        st = dict(style or {})
        st["display"] = "block"
        # Vazio → mostra o placeholder ("Descreva a causa") como texto já
        # selecionado (o JS dá select()), igual a editar a forma no PowerPoint.
        return st, no.get("titulo") or PLACEHOLDER_CAUSA

    @app.callback(
        Output("store-fa-nos", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Output("fa-inline-editor", "style", allow_duplicate=True),
        Input("fa-inline-ok", "n_clicks"),
        Input("fa-inline-text", "n_submit"),
        State("fa-inline-text", "value"),
        State("store-fa-selecionado", "data"),
        State("store-fa-nos", "data"),
        State("store-fa-analise", "data"),
        State("fa-inline-editor", "style"),
        prevent_initial_call=True,
    )
    def _aplicar_texto_inline(n, n_submit, texto, sel, nos, analise, style):
        """Grava o texto editado no balão e esconde o editor. Dispara pelo botão OK
        ou por Enter no campo de texto (`n_submit`)."""
        st = dict(style or {})
        st["display"] = "none"
        if not sel or not nos or not _pode_editar(analise):
            return no_update, no_update, st
        nos = [dict(x) for x in nos]
        for x in nos:
            if x["id"] == sel:
                x["titulo"] = texto or ""
        return nos, True, st

    # -- Edição do tempo do balão (⏱) -----------------------------------

    def _total(analise):
        return ((analise or {}).get("parada") or {}).get("duracao_min") or 0

    @app.callback(
        Output("fa-tempo-editor", "style", allow_duplicate=True),
        Output("fa-tempo-input", "value"),
        Input("fa-tb-tempo", "n_clicks"),
        State("store-fa-selecionado", "data"),
        State("store-fa-nos", "data"),
        State("fa-tempo-editor", "style"),
        prevent_initial_call=True,
    )
    def _abrir_tempo_editor(n, sel, nos, style):
        """Abre o editor de tempo preenchido com o valor atual do balão.

        Vale para qualquer balão (folha ou container): fixá-lo (MANUAL) o torna um
        competidor de valor fixo; os irmãos AUTO reabsorvem a sobra do pai."""
        if not sel or not nos:
            return no_update, no_update
        no = indexar(nos).get(sel)
        if not no or no.get("tipo") == TIPO_RAIZ:
            return no_update, no_update  # o ROOT é a duração da parada, não se edita
        st = dict(style or {})
        st["display"] = "block"
        return st, int(round(float(no.get("duration_min") or 0)))

    @app.callback(
        Output("store-fa-nos", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Output("fa-tempo-editor", "style", allow_duplicate=True),
        Input("fa-tempo-ok", "n_clicks"),
        Input("fa-tempo-input", "n_submit"),
        State("fa-tempo-input", "value"),
        State("store-fa-selecionado", "data"),
        State("store-fa-nos", "data"),
        State("store-fa-analise", "data"),
        State("fa-tempo-editor", "style"),
        prevent_initial_call=True,
    )
    def _aplicar_tempo(n1, n2, minutos, sel, nos, analise, style):
        """Fixa o tempo do balão (MANUAL) e redistribui irmãos + descendentes."""
        st = dict(style or {})
        st["display"] = "none"
        if not sel or not nos or not _pode_editar(analise):
            return no_update, no_update, st
        nos2 = marcar_tempo_manual(nos, sel, minutos)
        nos2 = distribuir_tempos(nos2, _total(analise))
        return nos2, True, st

    @app.callback(
        Output("store-fa-nos", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Output("fa-tempo-editor", "style", allow_duplicate=True),
        Input("fa-tempo-auto", "n_clicks"),
        State("store-fa-selecionado", "data"),
        State("store-fa-nos", "data"),
        State("store-fa-analise", "data"),
        State("fa-tempo-editor", "style"),
        prevent_initial_call=True,
    )
    def _tempo_auto(n, sel, nos, analise, style):
        """Tira o pino manual do balão — volta ao rateio automático do grupo."""
        st = dict(style or {})
        st["display"] = "none"
        if not n or not sel or not nos or not _pode_editar(analise):
            return no_update, no_update, st
        nos2 = distribuir_tempos(tornar_tempo_auto(nos, sel), _total(analise))
        return nos2, True, st

    @app.callback(
        Output("store-fa-nos", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Input("fa-tb-explicativo", "n_clicks"),
        State("store-fa-selecionado", "data"),
        State("store-fa-nos", "data"),
        State("store-fa-analise", "data"),
        prevent_initial_call=True,
    )
    def _toggle_explicativo(n, sel, nos, analise):
        """Marca/desmarca o balão como explicativo (não leva tempo) e redistribui.

        Um balão explicativo é transparente: sai da conta de tempo e deixa a sobra
        do pai passar para os filhos dele. Desmarcar volta ao rateio automático."""
        if not n or not sel or not nos or not _pode_editar(analise):
            return no_update, no_update
        no = indexar(nos).get(sel)
        if not no or no.get("tipo") == TIPO_RAIZ:
            return no_update, no_update
        virar = no.get("duration_mode") != MODO_EXPLICATIVO  # toggle
        nos2 = distribuir_tempos(marcar_explicativo(nos, sel, virar), _total(analise))
        return nos2, True

    @app.callback(
        Output("store-fa-nos", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Output("fa-toast", "is_open", allow_duplicate=True),
        Output("fa-toast", "children", allow_duplicate=True),
        Output("fa-toast", "icon", allow_duplicate=True),
        Input("fa-btn-reset-tempos", "n_clicks"),
        State("store-fa-nos", "data"),
        State("store-fa-analise", "data"),
        prevent_initial_call=True,
    )
    def _reset_tempos(n, nos, analise):
        """Limpa todos os pinos manuais — a árvore inteira volta ao automático."""
        if not n or not nos or not _pode_editar(analise):
            return (no_update,) * 5
        nos2 = distribuir_tempos(resetar_tempos(nos), _total(analise))
        return nos2, True, True, "Tempos recalculados no automático.", "info"

    # -- Persistência ----------------------------------------------------

    @app.callback(
        Output("store-fa-analise", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Output("store-fa-nos-original", "data", allow_duplicate=True),
        Output("fa-toast", "is_open", allow_duplicate=True),
        Output("fa-toast", "children", allow_duplicate=True),
        Output("fa-toast", "icon", allow_duplicate=True),
        Input("fa-btn-salvar", "n_clicks"),
        State("store-fa-nos", "data"),
        State("store-fa-analise", "data"),
        State("fa-nome", "value"),
        State("fa-responsavel", "value"),
        State("fa-participantes", "value"),
        State("store-fa-secoes", "data"),
        State("store-fa-alturas", "data"),
        State("store-fa-conflitos", "data"),
        prevent_initial_call=True,
    )
    def _salvar(n1, nos, analise, nome, responsavel, participantes, secoes, alturas,
                conflitos):
        """Salva cabeçalho e árvore (Seção 14.3). Recarrega para trazer a nova versão.

        Salva em três escritas condicionadas à versão (concorrência otimista,
        Seção 17). Ao salvar, o snapshot original vira o estado salvo — Descartar
        depois volta para o que acabou de ser gravado.
        """
        if not n1 or not analise:
            return (no_update,) * 6
        if not _pode_editar(analise):
            return no_update, no_update, no_update, True, "Você não pode editar esta análise.", "warning"

        analysis_id = analise["id"]
        versao = analise.get("versao", 1)

        # O desenho é livre; a cobrança é aqui. Dois pais no mesmo balão o banco nem
        # enxerga (o modelo guarda um `parent_id` só), então quem avisa é o desenho.
        avisos = conflitos_de_pai(conflitos, nos or [])
        if avisos:
            return no_update, no_update, no_update, True, " ".join(avisos), "warning"

        # O balão recém-desenhado chega sem id definitivo e sem saber a que análise
        # pertence — e um só desses derruba a gravação da árvore inteira.
        nos = reconciliar_arvore(nos or [], analysis_id)

        # `titulo` não vai aqui: é imutável e a whitelist de CAMPOS_EDITAVEIS o
        # descartaria de qualquer forma. `tipo_analise`, `area` e `subgrupo` saíram
        # do cabeçalho — não são mais editáveis por aqui (área/subgrupo são editados
        # na Seção 1 do A3, em `secoes.problema`). Os valores legados de topo no DB
        # são preservados por não serem reescritos.
        ok, msg = fdb.atualizar_campos(analysis_id, versao, {
            "nome": nome or "",
            "responsavel": responsavel or "",
            "participantes": _lista_participantes(participantes),
        }, _username())
        if not ok:
            return no_update, no_update, no_update, True, msg, "danger"

        total = (analise.get("parada") or {}).get("duracao_min") or 0
        ok, msg = fdb.salvar_arvore(analysis_id, versao + 1, nos, total, _username())
        if not ok:
            # Conflito de versão (outro usuário salvou) cai aqui com a msg própria.
            # As mensagens de estrutura falam em id de nó; na tela, o balão é
            # reconhecido pelo texto que a pessoa escreveu nele.
            return no_update, no_update, no_update, True, mensagem_com_titulos(msg, nos), "danger"

        # Seções A3 (terceira escrita — a versão já subiu 2x pelas anteriores).
        # Dobra as alturas que o usuário arrastou nos campos de texto (px) dentro de
        # `secoes.alturas`: como ficam na análise, o tamanho confortável é restaurado
        # para TODOS que a abrirem depois.
        if alturas:
            secoes = mesclar_alturas(secoes, alturas)
        if secoes:
            ok, msg = fdb.salvar_secoes(analysis_id, versao + 2, secoes, _username())
            if not ok:
                return no_update, no_update, no_update, True, msg, "danger"

        atualizada = fdb.carregar_analise(analise["parada_chave"])
        salvos = sincronizar_tipos((atualizada or {}).get("nos") or nos or [])
        return atualizada or no_update, False, salvos, True, "Alterações salvas.", "success"

    # -- Barra de alterações não salvas + Descartar (Seção 14) ----------

    @app.callback(
        Output("fa-btn-salvar", "className"),
        Output("fa-btn-descartar", "style"),
        Input("store-fa-dirty", "data"),
    )
    def _indicador_dirty(dirty):
        """Com alterações não salvas: 'Salvar alterações' pisca discreto e o botão
        Descartar aparece na linha do título. Sem pendência, ambos somem."""
        if dirty:
            return "fa-dirty-blink", {"display": "inline-block"}
        return "", {"display": "none"}

    @app.callback(
        Output("store-fa-nos", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Output("store-fa-selecionado", "data", allow_duplicate=True),
        Output("fa-toast", "is_open", allow_duplicate=True),
        Output("fa-toast", "children", allow_duplicate=True),
        Output("fa-toast", "icon", allow_duplicate=True),
        Input("fa-btn-descartar", "n_clicks"),
        State("store-fa-nos-original", "data"),
        prevent_initial_call=True,
    )
    def _descartar(n, original):
        """Restaura o último estado persistido e limpa o dirty (Seção 14.4)."""
        if not n:
            return (no_update,) * 6
        return (original or []), False, None, True, "Alterações descartadas.", "info"

    @app.callback(
        Output("store-fa-analise", "data", allow_duplicate=True),
        Output("fa-toast", "is_open", allow_duplicate=True),
        Output("fa-toast", "children", allow_duplicate=True),
        Output("fa-toast", "icon", allow_duplicate=True),
        Input("fa-btn-concluir", "n_clicks"),
        State("store-fa-nos", "data"),
        State("store-fa-analise", "data"),
        State("store-fa-secoes", "data"),
        prevent_initial_call=True,
    )
    def _concluir(n, nos, analise, secoes):
        """Entrega a análise ao gestor. Exige nível 2 e os requisitos da BR-14 — e a
        mensagem de recusa lista o que falta, item a item."""
        if not n or not analise:
            return (no_update,) * 4
        if not _pode_editar(analise):
            return no_update, True, "Esta análise não está aberta para edição.", "warning"
        if _nivel_usuario() < NIVEL_CONCLUSAO:
            return no_update, True, "Entregar a análise exige nível 2.", "warning"

        total = (analise.get("parada") or {}).get("duracao_min") or 0
        ok, msg = fdb.entregar_analise(analise["id"], analise.get("versao", 1),
                                       nos or [], (secoes or {}).get("actions") or [],
                                       total, _username())
        if not ok:
            return no_update, True, msg, "danger"
        return fdb.carregar_analise(analise["parada_chave"]) or no_update, True, msg, "success"

    # -- Aceite do gestor (nível 4) ---------------------------------------

    @app.callback(
        Output("store-fa-analise", "data", allow_duplicate=True),
        Output("fa-toast", "is_open", allow_duplicate=True),
        Output("fa-toast", "children", allow_duplicate=True),
        Output("fa-toast", "icon", allow_duplicate=True),
        Input("fa-btn-aceitar", "n_clicks"),
        State("store-fa-analise", "data"),
        prevent_initial_call=True,
    )
    def _aceitar(n, analise):
        """O gestor aceita a análise entregue — a partir daqui ela conta no quadro."""
        if not n or not analise:
            return (no_update,) * 4
        if _nivel_usuario() < NIVEL_GESTOR:
            return no_update, True, "Aceitar a análise exige nível 4.", "warning"
        ok, msg = fdb.aceitar_analise(analise["id"], _username())
        if not ok:
            return no_update, True, msg, "danger"
        return fdb.carregar_analise(analise["parada_chave"]) or no_update, True, msg, "success"

    @app.callback(
        Output("fa-modal-devolver", "is_open"),
        Output("fa-devolver-motivo", "value"),
        Input("fa-btn-devolver", "n_clicks"),
        Input("fa-devolver-cancelar", "n_clicks"),
        Input("fa-devolver-confirmar", "n_clicks"),
        prevent_initial_call=True,
    )
    def _modal_devolver(abrir, cancelar, confirmar):
        """Abre e fecha a caixa do motivo, limpando o texto ao abrir."""
        gatilho = (dash.ctx.triggered_id or "")
        if gatilho == "fa-btn-devolver":
            return True, ""
        return False, no_update

    @app.callback(
        Output("fa-devolver-confirmar", "disabled"),
        Input("fa-devolver-motivo", "value"),
    )
    def _exige_motivo(motivo):
        """Sem motivo escrito, não dá para confirmar a devolução (BR-15).

        Devolução sem motivo obriga quem recebe a adivinhar, e adivinhação vira
        retrabalho às cegas.
        """
        return not (motivo or "").strip()

    @app.callback(
        Output("store-fa-analise", "data", allow_duplicate=True),
        Output("fa-toast", "is_open", allow_duplicate=True),
        Output("fa-toast", "children", allow_duplicate=True),
        Output("fa-toast", "icon", allow_duplicate=True),
        Input("fa-devolver-confirmar", "n_clicks"),
        State("fa-devolver-motivo", "value"),
        State("store-fa-analise", "data"),
        prevent_initial_call=True,
    )
    def _devolver(n, motivo, analise):
        """Devolve a análise a quem a fez, com o motivo à mostra.

        É o único jeito de destravar: o "Reabrir" de antes saiu da tela.
        """
        if not n or not analise:
            return (no_update,) * 4
        if _nivel_usuario() < NIVEL_GESTOR:
            return no_update, True, "Devolver a análise exige nível 4.", "warning"
        ok, msg = fdb.devolver_analise(analise["id"], _username(), motivo or "")
        if not ok:
            return no_update, True, msg, "danger"
        return fdb.carregar_analise(analise["parada_chave"]) or no_update, True, msg, "success"

    app.clientside_callback(
        # Aviso do navegador ao sair com alterações não salvas. Precisa ser
        # client-side: só o browser controla o beforeunload.
        # `e.returnValue = ''` é obrigatório no Chrome para o diálogo aparecer
        # (só `preventDefault`/`return` não basta). `window.__faDirty` é lido pelo
        # guard de navegação in-app (fa_node_toolbar.js), que cobre o menu SPA —
        # onde o beforeunload NÃO dispara (não há unload da página).
        """
        function(dirty) {
            window.__faDirty = !!dirty;
            window.onbeforeunload = dirty
                ? function(e) { e.preventDefault(); e.returnValue = ''; return ''; }
                : null;
            // Trap de histórico para os botões Voltar/Avançar do navegador (popstate,
            // que não dispara beforeunload em SPA). Ao ficar dirty, empilha um estado
            // no MESMO url; o Back cai nele e o listener de popstate (fa_node_toolbar.js)
            // pede confirmação em vez de descartar. Armado uma vez por página.
            if (dirty && !window.__faTrapArmed) {
                window.__faTrapArmed = true;
                try { history.pushState({faTrap: 1}, '', location.href); } catch (e2) {}
            }
            return '';
        }
        """,
        # Escreve num alvo neutro: devolver para `store-fa-dirty.data` — o próprio
        # Input — seria dependência circular e o Dash recusa registrar.
        Output("fa-beforeunload", "children"),
        Input("store-fa-dirty", "data"),
    )

    # Balão recém-criado → abre o editor de texto já selecionado (estilo PowerPoint).
    # Espera o nó aparecer no cytoscape (após o re-render + layout dagre) e então
    # dispara o clique no ✎ — que abre o editor (Python, lê o nó selecionado) e o
    # posiciona/foca/seleciona (JS). O balão nasce vazio → mostra "Descreva a causa".
    app.clientside_callback(
        """
        function(nid) {
            if (!nid) { return ""; }
            // Trava a seleção JÁ: enquanto o balão novo não é editado, passar o
            // mouse por cima de outro balão não pode roubar o foco (senão o editor
            // abre/salva no balão errado). O mouseover respeita `cy._faLockSel`.
            var el0 = document.getElementById('fa-diagrama');
            var cy0 = el0 && el0._cyreg && el0._cyreg.cy;
            if (cy0) { cy0._faLockSel = true; }
            var tries = 0;
            var iv = setInterval(function () {
                var el = document.getElementById('fa-diagrama');
                var cy = el && el._cyreg && el._cyreg.cy;
                if (cy) { cy._faLockSel = true; }
                var node = cy ? cy.getElementById(nid) : null;
                if (node && node.length) {
                    clearInterval(iv);
                    cy._faActive = node;
                    var btn = document.getElementById('fa-tb-editar');
                    if (btn) { setTimeout(function () { btn.click(); }, 130); }
                    // Editor aberto → a própria visibilidade dele trava o hover;
                    // libera a trava de seleção para o uso normal.
                    setTimeout(function () { if (cy) cy._faLockSel = false; }, 1200);
                }
                if (++tries > 40) { clearInterval(iv); if (cy) cy._faLockSel = false; }
            }, 80);
            return "";
        }
        """,
        Output("fa-editar-novo-sink", "children"),
        Input("store-fa-editar-novo", "data"),
        prevent_initial_call=True,
    )

    # -- Diagrama novo (Excalidraw) --------------------------------------
    #
    # A ponte liga o quadro de desenho (que roda num iframe) ao resto da página.
    # O `store-fa-nos` continua sendo a fonte da verdade: o quadro lê dele para
    # desenhar e escreve nele quando o usuário termina uma edição. Nada mais da
    # página muda — Plano de Ação, seções, export e salvar seguem lendo o mesmo
    # store que liam com o diagrama antigo.
    #
    # Três mensagens vêm do quadro:
    #   ready  — "montei": a página responde mandando os balões (repetida a cada
    #            500 ms até chegar dado, senão um recarregamento lento perde o
    #            aviso e o diagrama nasce vazio)
    #   select — o balão selecionado mudou  -> store-fa-selecionado
    #   edit   — o usuário editou           -> store-fa-nos + store-fa-dirty
    #
    # A escrita usa `set_props` em vez de um callback com Output nesses stores:
    # `store-fa-selecionado` já tem dono (o callback do diagrama antigo), e dois
    # donos declarados para o mesmo store é confusão garantida.
    app.clientside_callback(
        """
        function(nos) {
            window._faNos = nos || [];
            var sp = function (id, valor) {
                window.dash_clientside.set_props(id, {data: valor});
            };
            if (!window._faPonte) {
                window._faPonte = true;
                window.addEventListener('message', function (e) {
                    var d = e.data || {};
                    if (d.type === 'ready') {
                        window._faPronto = true;
                        var f = document.getElementById('fa-frame');
                        if (f && f.contentWindow) {
                            f.contentWindow.postMessage(
                                {cmd: 'render', nos: window._faNos}, '*');
                        }
                    } else if (d.type === 'select') {
                        sp('store-fa-selecionado', d.faId);
                    } else if (d.type === 'edit') {
                        sp('store-fa-nos', d.nos);
                        sp('store-fa-conflitos', d.conflitos || []);
                        // Mexeu no desenho = alteração não salva: o botão Salvar
                        // pisca e sair da página passa a avisar. O _salvar limpa.
                        sp('store-fa-dirty', true);
                    }
                });
            }
            var atual = JSON.stringify(window._faNos);
            var f = document.getElementById('fa-frame');
            if (f && f.contentWindow && window._faPronto && atual !== window._faUltimo) {
                // Só reenvia quando mudou de verdade: sem isso, a edição volta do
                // servidor e o quadro se redesenha inteiro a cada tecla.
                window._faUltimo = atual;
                f.contentWindow.postMessage({cmd: 'render', nos: window._faNos}, '*');
            }
            return '';
        }
        """,
        Output("fa-ponte-sink", "data"),
        Input("store-fa-nos", "data"),
    )

    # Imagem do diagrama para o slide (IM-AF3-08): a cada análise carregada ou salva,
    # `fa_diagrama_imagem.js` confere se a imagem guardada está em dia e, se não, pede
    # o SVG ao quadro e envia. Em segundo plano — não segura nem atrapalha o Salvar.
    app.clientside_callback(
        """
        function(analise) {
            if (analise && analise.id && window.faDiagramaImagem) {
                window.faDiagramaImagem.agendar(analise.id, analise.versao);
            }
            return '';
        }
        """,
        Output("fa-diagrama-imagem-sink", "data"),
        Input("store-fa-analise", "data"),
    )

    @app.callback(
        Output("fa-btn-causa-raiz", "disabled"),
        Output("fa-btn-causa-raiz", "children"),
        Output("fa-causa-raiz-dica", "children"),
        Input("store-fa-selecionado", "data"),
        # `store-fa-nos` também é Input, e não State: depois de marcar a causa raiz,
        # quem muda é a árvore, não a seleção. Como State, o botão continuaria
        # dizendo "Causa raiz (★)" num balão que acabou de virar causa raiz.
        Input("store-fa-nos", "data"),
    )
    def _estado_botao_causa_raiz(selecionado, nos):
        """Liga o botão quando há balão selecionado e diz o que ele vai fazer.

        O rótulo alterna: num balão comum o botão marca a causa raiz; num balão que
        já é causa raiz, ele desmarca. Sem isso, o mesmo botão faria coisas opostas
        sem avisar qual.
        """
        no = next((n for n in (nos or []) if n.get("id") == selecionado), None)
        if not no:
            return True, [html.I(className="bi bi-star me-1"), "Causa raiz (★)"], \
                "selecione um balão no diagrama"
        if no.get("tipo") == TIPO_RAIZ:
            return True, [html.I(className="bi bi-star me-1"), "Causa raiz (★)"], \
                "o balão da parada não pode ser causa raiz"
        titulo = (no.get("titulo") or "").strip() or "balão sem texto"
        if no.get("is_root_cause"):
            return False, [html.I(className="bi bi-star-fill me-1"), "Tirar causa raiz"], \
                f"“{titulo}” está marcado como causa raiz"
        return False, [html.I(className="bi bi-star me-1"), "Causa raiz (★)"], \
            f"marcar “{titulo}” como causa raiz"

    @app.callback(
        Output("store-fa-nos", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Input("fa-btn-causa-raiz", "n_clicks"),
        State("store-fa-selecionado", "data"),
        State("store-fa-nos", "data"),
        State("store-fa-analise", "data"),
        prevent_initial_call=True,
    )
    def _alternar_causa_raiz(n, selecionado, nos, analise):
        """Marca/desmarca a causa raiz do balão selecionado.

        Escrever em `store-fa-nos` é o bastante: o callback que mantém o Plano de
        Ação ouve esse store e cria (ou remove) a linha da causa sozinho — o mesmo
        caminho do diagrama antigo.
        """
        if not n or not selecionado or not nos:
            return no_update, no_update
        if not _pode_editar(analise):
            return no_update, no_update
        no = next((x for x in nos if x.get("id") == selecionado), None)
        if not no or no.get("tipo") == TIPO_RAIZ:
            return no_update, no_update
        return marcar_causa_raiz(nos, selecionado, not no.get("is_root_cause")), True


def _dt(valor):
    """Normaliza datetime que pode voltar do dcc.Store como string ISO."""
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(valor.replace("Z", "+00:00").split("+")[0])
        except ValueError:
            return None
    return None
