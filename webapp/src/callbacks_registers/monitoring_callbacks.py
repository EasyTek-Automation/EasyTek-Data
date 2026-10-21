# -*- coding: utf-8 -*-
"""Callbacks do Monitoramento de Ativos (DS-08).

O fluxo é sempre o mesmo, e é só um:

    url.search → cenário → lista de eventos → projeções → tela

Os controles não pintam nada por conta própria: eles reescrevem a URL, e é a URL que dispara
o repinte. Assim a tela mostrada é sempre a que o endereço descreve — o link é
compartilhável, e o botão "voltar" do navegador funciona sem código nenhum.
"""
from urllib.parse import parse_qs, urlencode

from dash import Input, Output, State, callback_context, html, no_update

from src.components.monitoring import (
    asset_view, capacity, color_style, controls, failure_tables, insight_cards, plant_view,
    status_bar, timeline,
)
from src.pages.maintenance import monitoramento_ativos_ativo as pagina_ativo
from src.utils.monitoring import projection as pj
from src.utils.monitoring.events import Escopo, ativos as ativos_conhecidos
from src.utils.monitoring.scenarios import (
    CENARIO_PADRAO, CENARIOS, cenario as buscar_cenario,
)

ROTA_PLANTA = "/maintenance/monitoramento-ativos"
ROTA_ATIVO = "/maintenance/monitoramento-ativos/ativo"


# O escopo saiu da interface em 2026-08-05 (a tela é de manutenção), mas continua atravessando
# as projeções com um valor só: "ver tudo". Manter o parâmetro custa nada e devolve o filtro à
# tela em uma linha, se um dia a produção voltar a ter eventos aqui.
ESCOPO_FIXO = Escopo.TUDO.value


def parametros(search: str | None) -> tuple[str, str, str | None]:
    """Cenário e ativo pedidos na URL, com o padrão no lugar do ausente."""
    query = parse_qs((search or "").lstrip("?"))
    cenario = buscar_cenario((query.get("cenario") or [None])[0]).chave
    ativo = (query.get("id") or [None])[0]
    return cenario, ESCOPO_FIXO, ativo


def _search(cenario: str, escopo: str, ativo: str | None = None) -> str:
    dados = {}
    if ativo:
        dados["id"] = ativo
    dados["cenario"] = cenario
    return "?" + urlencode(dados)


def eventos_visiveis(cenario: str, escopo: str):
    """A lista de eventos do cenário."""
    return pj.filtrar(buscar_cenario(cenario).resolver(), Escopo(escopo))


def register_monitoring_callbacks(app):
    """Registra os callbacks das duas telas do Monitoramento de Ativos."""

    @app.callback(
        Output(plant_view.ID_ESTADOS, "data"),
        Output(plant_view.ID_CAMADA, "children"),
        Output(plant_view.ID_FS_CENARIO, "children"),
        Output(status_bar.ID_FAIXA_SLOT, "children"),
        Output(plant_view.ID_FEED_SLOT, "children"),
        Output("mon-legenda-slot", "children"),
        Output(controls.ID_CENARIO, "value"),
        Input("url", "search"),
        Input("url", "pathname"),
        prevent_initial_call=False,
    )
    def repintar_planta(search, pathname):
        """Repinta a planta inteira a partir do que a URL descreve."""
        if pathname != ROTA_PLANTA:
            return (no_update,) * 7

        cenario, escopo, _ = parametros(search)
        eventos = eventos_visiveis(cenario, escopo)
        estados = color_style.mapa_de_estados(
            pj.cor_dos_conjuntos(eventos), pj.cor_dos_ativos(eventos)
        )
        return (
            estados,
            plant_view.camada_de_cliques(cenario, escopo),
            buscar_cenario(cenario).rotulo,
            status_bar.faixa_de_situacao(eventos),
            status_bar.painel_de_ocorrencias(eventos, cenario),
            controls.legenda(Escopo(escopo)),
            cenario,
        )

    # O desenho é montado e pintado no navegador: o servidor só diz o que está de que cor.
    app.clientside_callback(
        """
        async function(estados, fonte) {
            const alvo = document.getElementById('mon-canvas');
            if (!alvo || !fonte) { return window.dash_clientside.no_update; }

            if (alvo.dataset.fonte !== fonte) {
                const resposta = await fetch(fonte);
                if (!resposta.ok) { return window.dash_clientside.no_update; }
                alvo.innerHTML = await resposta.text();
                alvo.dataset.fonte = fonte;
            }

            alvo.querySelectorAll('[data-state]').forEach(function (el) {
                el.removeAttribute('data-state');
            });
            alvo.querySelectorAll('[data-mark]').forEach(function (el) {
                el.removeAttribute('data-mark');
            });

            const dados = estados || {};
            const conjuntos = dados.conjuntos || {};
            const ativos = dados.ativos || {};
            Object.keys(conjuntos).forEach(function (chave) {
                alvo.querySelectorAll('[data-conj="' + chave + '"]').forEach(function (el) {
                    el.setAttribute('data-state', conjuntos[chave]);
                });
            });
            Object.keys(ativos).forEach(function (ativo) {
                alvo.querySelectorAll('[data-ativo="' + ativo + '"]').forEach(function (el) {
                    el.setAttribute('data-mark', ativos[ativo]);
                });
            });
            return fonte;
        }
        """,
        Output(plant_view.ID_PINTADO, "data"),
        Input(plant_view.ID_ESTADOS, "data"),
        Input(plant_view.ID_FONTE, "data"),
    )

    @app.callback(
        Output(asset_view.ID_ESTADOS, "data"),
        Output(asset_view.ID_FONTE, "data"),
        Output(asset_view.ID_RECORTE, "data"),
        Output(pagina_ativo.ID_TIMELINE_SLOT, "children"),
        Output(pagina_ativo.ID_CAPACIDADE_SLOT, "children"),
        Output(pagina_ativo.ID_CARDS_SLOT, "children"),
        Output(pagina_ativo.ID_TABELAS_SLOT, "children"),
        Output(pagina_ativo.ID_VOLTAR, "href"),
        Output("mon-legenda-slot", "children", allow_duplicate=True),
        Output(controls.ID_CENARIO, "value", allow_duplicate=True),
        Input(pagina_ativo.ID_CONTEXTO, "data"),
        prevent_initial_call="initial_duplicate",
    )
    def montar_ativo(contexto):
        """Refaz as quatro projeções do ativo a partir do contexto que a página traz.

        O gatilho é o contexto da própria página, e não a URL, de propósito. Pela URL, este
        callback disputava com o roteador: os dois reagem à mesma mudança, e quando a resposta
        chegava antes do layout novo existir, o conteúdo era escrito no documento sem entrar no
        estado do Dash. A página parecia certa até o primeiro clique em qualquer botão — aí o
        Dash redesenhava a partir do estado e os blocos voltavam vazios.

        Com o contexto como gatilho não há corrida: o dado nasce junto com a página, então
        quando o callback roda o destino já existe.
        """
        if not contexto:
            return (no_update,) * 10

        cenario = contexto.get("cenario") or CENARIO_PADRAO
        escopo = ESCOPO_FIXO
        ativo = contexto.get("ativo")
        if ativo not in ativos_conhecidos():
            return (no_update,) * 10

        eventos = eventos_visiveis(cenario, escopo)
        estados = color_style.mapa_de_estados(pj.cor_dos_conjuntos(eventos))
        return (
            estados,
            asset_view.fonte(ativo),
            asset_view.recorte(ativo),
            timeline.grafico(pj.faixas_da_timeline(eventos, ativo)),
            capacity.bloco(pj.curva_de_capacidade(eventos, ativo)),
            insight_cards.faixa(pj.cards(eventos, ativo, escopo=Escopo(escopo))),
            failure_tables.tabelas(pj.falhas_por_conjunto(eventos, ativo)),
            pagina_ativo.link_da_planta(cenario, escopo),
            controls.legenda(Escopo(escopo), com_molduras=False),
            cenario,
        )

    @app.callback(
        Output(pagina_ativo.ID_CONTEXTO, "data", allow_duplicate=True),
        Input(controls.ID_CENARIO, "value"),
        State(pagina_ativo.ID_CONTEXTO, "data"),
        prevent_initial_call=True,
    )
    def cenario_atualiza_o_contexto(cenario, contexto):
        """Trocar o cenário na página do ativo tem de chegar ao contexto.

        O roteador do webapp só reage ao caminho, não à parte de consulta: mudar apenas o
        `?cenario=` **não** remonta a página, e o contexto — que nasce com ela — ficaria com o
        cenário antigo. Este callback fecha esse caminho.

        A guarda de igualdade encerra o ciclo: o `montar_ativo` também escreve no seletor, e
        sem ela os dois ficariam se acordando.
        """
        if not contexto or not cenario or cenario == contexto.get("cenario"):
            return no_update
        return {**contexto, "cenario": cenario}

    # Mesmo mecanismo da planta, com um passo a mais: o croqui recorta o desenho pelo
    # `viewBox` do ativo, em vez de mostrar o grupo inteiro de linhas.
    app.clientside_callback(
        """
        async function(estados, fonte, recorte) {
            const alvo = document.getElementById('mon-asset-canvas');
            if (!alvo || !fonte) { return window.dash_clientside.no_update; }

            if (alvo.dataset.fonte !== fonte) {
                const resposta = await fetch(fonte);
                if (!resposta.ok) { return window.dash_clientside.no_update; }
                alvo.innerHTML = await resposta.text();
                alvo.dataset.fonte = fonte;
            }

            const svg = alvo.querySelector('svg');
            if (svg && recorte) { svg.setAttribute('viewBox', recorte); }

            alvo.querySelectorAll('[data-state]').forEach(function (el) {
                el.removeAttribute('data-state');
            });
            const conjuntos = (estados || {}).conjuntos || {};
            Object.keys(conjuntos).forEach(function (chave) {
                alvo.querySelectorAll('[data-conj="' + chave + '"]').forEach(function (el) {
                    el.setAttribute('data-state', conjuntos[chave]);
                });
            });
            return fonte + '|' + recorte;
        }
        """,
        Output(asset_view.ID_PINTADO, "data"),
        Input(asset_view.ID_ESTADOS, "data"),
        Input(asset_view.ID_FONTE, "data"),
        Input(asset_view.ID_RECORTE, "data"),
    )

    # Tela cheia — quem entra em tela cheia é a **página inteira**, não o quadro do desenho.
    #
    # Enquanto o alvo era o quadro, clicar numa linha derrubava a tela cheia: o roteador
    # reconstrói o layout a cada troca de página, o elemento em tela cheia deixava de existir
    # e o navegador devolvia a janela normal. Pedir a tela cheia de novo na página seguinte
    # não resolve — o navegador recusa, porque o pedido já não vem de um gesto do usuário.
    #
    # Com o documento inteiro como alvo, não há elemento para desaparecer: a tela cheia
    # atravessa a ida para o ativo e a volta para a planta sem nenhum estado guardado. O que
    # some da vista (menu, sidebar, cabeçalho da página) é escondido por CSS sob
    # `html:fullscreen`, que reproduz exatamente o enquadramento de antes.
    app.clientside_callback(
        """
        function(cliques) {
            if (!cliques) { return window.dash_clientside.no_update; }
            const alvo = document.documentElement;
            if (!alvo) { return window.dash_clientside.no_update; }

            if (document.fullscreenElement || document.webkitFullscreenElement) {
                const sair = document.exitFullscreen || document.webkitExitFullscreen;
                if (sair) { sair.call(document); }
            } else {
                const entrar = alvo.requestFullscreen || alvo.webkitRequestFullscreen
                               || alvo.msRequestFullscreen;
                if (entrar) { entrar.call(alvo).catch(function () {}); }
            }
            return cliques;
        }
        """,
        Output(controls.ID_TELA_CHEIA, "n_clicks"),
        Input(controls.ID_TELA_CHEIA, "n_clicks"),
        prevent_initial_call=True,
    )

    # Painel claro × escuro. A troca acontece no navegador (`assets/monitoring_tema.js`), que é
    # quem mantém os dois botões sincronizados e guarda a escolha; aqui só devolvemos o clique
    # ao Dash.
    #
    # Isso não é formalidade: botão com `n_clicks` que ninguém escuta faz o Dash remontar a
    # árvore da rota ao ser clicado, e os blocos da página do ativo — linha do tempo, cards,
    # tabelas — nascem vazios nessa árvore, porque quem os preenche é o `montar_ativo`. Sem
    # este callback, trocar de tema com um ativo aberto esvaziava a página.
    _ALTERNAR_TEMA = """
        function(cliques) {
            if (cliques && window.monTema) { window.monTema.alternar(); }
            return cliques;
        }
    """

    app.clientside_callback(
        _ALTERNAR_TEMA,
        Output(controls.ID_TEMA, "n_clicks"),
        Input(controls.ID_TEMA, "n_clicks"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        _ALTERNAR_TEMA,
        Output(plant_view.ID_TEMA_FS, "n_clicks"),
        Input(plant_view.ID_TEMA_FS, "n_clicks"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(cliques) {
            if (cliques && (document.fullscreenElement || document.webkitFullscreenElement)) {
                const sair = document.exitFullscreen || document.webkitExitFullscreen;
                if (sair) { sair.call(document); }
            }
            return cliques;
        }
        """,
        Output(plant_view.ID_SAIR_FS, "n_clicks"),
        Input(plant_view.ID_SAIR_FS, "n_clicks"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output(controls.ID_CENARIO, "value", allow_duplicate=True),
        Input(plant_view.ID_FS_TROCAR, "n_clicks"),
        State(controls.ID_CENARIO, "value"),
        prevent_initial_call=True,
    )
    def girar_cenario_em_tela_cheia(cliques, atual):
        """Avança para o próximo cenário, em ciclo, sem sair da tela cheia.

        Em tela cheia o dropdown fica fora do que o navegador mostra, e apresentar as quatro
        situações da fábrica exigiria sair e voltar a cada troca. O botão da faixa escreve no
        mesmo dropdown de sempre — daí para a frente o caminho é o de todo controle da tela:
        o dropdown reescreve a URL e a URL repinta.

        Ciclo, e não uma lista: a faixa precisa continuar discreta, e a ordem dos cenários já
        é crescente em severidade (tudo rodando → turno normal → parada programada → avaria).
        Percorrê-la em ordem é justamente o roteiro de quem está apresentando.
        """
        if not cliques:
            return no_update
        chaves = [c.chave for c in CENARIOS]
        try:
            proximo = chaves[(chaves.index(atual) + 1) % len(chaves)]
        except ValueError:
            proximo = chaves[0]
        return proximo

    @app.callback(
        Output("url", "search", allow_duplicate=True),
        Input(controls.ID_CENARIO, "value"),
        State("url", "pathname"),
        State("url", "search"),
        prevent_initial_call=True,
    )
    def controles_reescrevem_a_url(cenario, pathname, search):
        """Mexer no controle só muda o endereço — quem repinta é o callback de cima."""
        if pathname not in (ROTA_PLANTA, ROTA_ATIVO):
            return no_update
        if not callback_context.triggered_id:
            return no_update

        atual_cenario, escopo, ativo = parametros(search)
        cenario = cenario or atual_cenario or CENARIO_PADRAO

        novo = _search(cenario, escopo, ativo if pathname == ROTA_ATIVO else None)
        return no_update if novo == (search or "") else novo
