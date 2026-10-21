# src/callbacks_registers/failure_a3_callbacks.py

"""
Callbacks das seções A3 abaixo do diagrama (Plano de Ação, Sustentabilidade,
Encerramento) + os campos fixos (Problema, Contenção).

Contrato: tudo vive em `store-fa-secoes` (o dict de seções do domínio). O Salvar do
cabeçalho persiste tudo (ver `_salvar` em failure_analysis_callbacks). A causa raiz
não tem seção própria: é marcada no diagrama (★) e é a **fonte única** do Plano de
Ação — cada causa-raiz vira uma linha (vínculo por `node_id`; BR-AF2-08/14).

O Plano de Ação (seção 4) é renderizado como **linhas de componentes** (não
DataTable): Ação = `Textarea` (quebra linha, colar normal), Responsável = `Dropdown`
de usuários, Prazo = `DatePickerSingle`, Status = `Dropdown`. As linhas são
reconstruídas só quando o CONJUNTO de linhas muda (add/remove de causa-raiz), para o
foco não se perder ao digitar.

Só a aba do diagrama usa estes ids (`fa-sec-*`, `fa-acao-*`).
"""

import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, dcc, html, no_update
from flask_login import current_user

from src.utils import failure_analysis_db as fdb
from src.utils.failure_a3 import (
    ADICIONADA,
    SECOES,
    STATUS_ACAO,
    STATUS_ACAO_PADRAO,
    adicionar_acao,
    alturas_salvas,
    lista_responsaveis,
    remover_acao,
    secoes_alteradas,
    sincronizar_acoes,
)
from src.utils.failure_tree import indexar

# Campos de texto que crescem com o conteúdo e guardam a altura arrastada. A ordem
# é a dos Outputs de `_alturas_textareas` — mexer aqui exige mexer lá.
_TEXTAREAS_ALTURA = (
    "fa-sec-prob-descricao",
    "fa-sec-prob-obs",
    "fa-sec-cont-acoes",
    "fa-sec-licoes",
)

# Campos de texto fixos por seção → caminho no store (secao, campo).
_CAMPOS_FIXOS = {
    "fa-sec-prob-descricao": ("problema", "descricao"),
    "fa-sec-prob-area": ("problema", "area"),
    "fa-sec-prob-equip": ("problema", "equipamento"),
    "fa-sec-prob-subgrupo": ("problema", "subgrupo"),
    "fa-sec-prob-obs": ("problema", "observacoes"),
    "fa-sec-cont-acoes": ("contencao", "acoes"),
    "fa-sec-cont-local": ("contencao", "local"),
    "fa-sec-cont-resp": ("contencao", "responsavel"),
    "fa-sec-cont-inicio": ("contencao", "inicio"),
    # Seção 5 = um campo (Lições Aprendidas). A Seção 6 (assinatura + data) tem
    # callback próprio em failure_analysis_callbacks: a assinatura (`fa-sec-enc-resp`,
    # dropdown restrito ao usuário logado) e a data (`fa-sec-enc-data`, DatePicker com
    # prop `date`, não `value`) não entram aqui.
    "fa-sec-licoes": ("sustainability", "licoes"),
}
_IDS_FIXOS = list(_CAMPOS_FIXOS)

_STATUS_OPTS = [{"label": v, "value": k} for k, v in STATUS_ACAO.items()]


def _hidratar_causa(actions, nos):
    """Rótulo `_causa` de cada ação a partir do título do balão de origem (`node_id`),
    só para exibição. Não é persistido — deriva do diagrama no load (fonte: o nó)."""
    idx = indexar(nos or [])
    out = []
    for a in (actions or []):
        row = dict(a or {})
        no = idx.get(row.get("node_id"))
        row["_causa"] = (no.get("titulo") or "").strip() if no is not None else ""
        out.append(row)
    return out


def _opcoes_responsavel(em_uso=None):
    """Opções do dropdown de responsável de cada ação — usuários da manutenção,
    conforme o perfil do usuário logado (mesmo cadastro do responsável do cabeçalho).

    `em_uso` são os nomes já gravados nas ações. Passá-los mantém no dropdown quem
    saiu do cadastro ou é de outro perfil: sem isso o campo renderiza vazio e o
    próximo Salvar apagaria o responsável em silêncio (ver `garantir_opcao_atual`).
    """
    perfil = str(getattr(current_user, "perfil", "") or "")
    try:
        return fdb.opcoes_responsaveis(perfil, list(em_uso or []))
    except Exception:
        return []


def _coluna_causa(a, primeira):
    """Primeira coluna da linha: o texto da causa, ou o «↳» das ações seguintes.

    Uma causa raiz pode ter várias ações (responsáveis e prazos diferentes). Só a
    primeira linha mostra o nome da causa; as demais trazem «↳» para deixar claro
    que continuam na mesma causa, sem repetir o texto e poluir a leitura. A ação
    adicionada ganha o 🗑 aqui — a primeira não tem, porque ela nasce do ★ e só sai
    desmarcando a causa (BR-AF2-14).
    """
    if primeira:
        return html.Div(a.get("_causa") or "—", className="small text-muted pt-2")
    filhos = [html.Span("↳", className="small text-muted",
                        title="Outra ação para a mesma causa")]
    if a.get(ADICIONADA):
        filhos.append(
            dbc.Button(html.I(className="bi bi-trash"),
                       id={"type": "fa-acao-del", "aid": a.get("id")},
                       color="link", size="sm",
                       className="text-muted p-0 ms-2 fa-acao-del",
                       title="Remover esta ação"))
    return html.Div(filhos, className="pt-2 d-flex align-items-center")


def _linha_acao(a, resp_opts, alturas=None, primeira=True):
    """Uma linha do Plano de Ação (Seção 4) como componentes de verdade.

    `alturas` traz o tamanho que alguém deixou em cada caixa de "Ação" (mapa
    `{"acao:<id>": px}`, salvo na análise). Sem altura salva a caixa nasce em 38px
    e o JS `fa_textarea_autosize.js` a ajusta ao texto — uma ação de três linhas
    aparece com três linhas, não espremida em uma.

    `primeira` diz se esta é a primeira ação da causa — ver `_coluna_causa`. As
    colunas e larguras são as mesmas de sempre, em qualquer caso.
    """
    aid = a.get("id")
    altura = (alturas or {}).get(f"acao:{aid}")
    estilo_desc = {"width": "100%", "height": f"{altura}px" if altura else "38px",
                   "minHeight": "38px", "fontSize": "0.82rem", "whiteSpace": "pre-wrap"}
    return dbc.Row(
        [
            dbc.Col(_coluna_causa(a, primeira), md=2, xs=12),
            dbc.Col(dcc.Textarea(
                id={"type": "fa-acao-desc", "aid": aid},
                value=a.get("descricao") or "",
                placeholder="Descreva a ação",
                style=estilo_desc), md=4, xs=12),
            # multi: a mesma ação pode ser de mais de um responsável. O valor vem
            # de `lista_responsaveis` porque análise antiga guardou um texto só.
            dbc.Col(dcc.Dropdown(
                id={"type": "fa-acao-resp", "aid": aid},
                options=resp_opts, value=lista_responsaveis(a.get("responsavel")),
                placeholder="Responsáveis", optionHeight=34, multi=True), md=2, xs=12),
            # with_portal: calendário como modal centralizado — não é cortado pelo
            # overflow do accordion nem esmagado pelas colunas estreitas da linha.
            dbc.Col(dcc.DatePickerSingle(
                id={"type": "fa-acao-prazo", "aid": aid},
                date=a.get("prazo"), placeholder="Prazo",
                display_format="DD/MM/YYYY", className="d-block",
                with_portal=True), md=2, xs=12),
            dbc.Col(dcc.Dropdown(
                id={"type": "fa-acao-status", "aid": aid},
                options=_STATUS_OPTS,
                value=a.get("status") if a.get("status") is not None else STATUS_ACAO_PADRAO,
                clearable=False), md=2, xs=12),
        ],
        className="g-2 mb-2 align-items-start",
    )


def _blocos_por_causa(hidratadas, resp_opts, alturas):
    """Agrupa as linhas por causa e põe um «+ ação» ao fim de cada grupo.

    O agrupamento é por `node_id` na ordem em que as linhas chegam — que já vem
    ordenada por `sincronizar_acoes` (ordem dos balões, e dentro da causa a ordem
    de criação). Só a primeira linha de cada causa mostra o nome dela.
    """
    blocos = []
    grupo_atual = None
    for a in hidratadas:
        nid = a.get("node_id")
        primeira = nid != grupo_atual
        if primeira and grupo_atual is not None:
            blocos.append(_botao_add_acao(grupo_atual))
        grupo_atual = nid
        blocos.append(_linha_acao(a, resp_opts, alturas, primeira=primeira))
    if grupo_atual is not None:
        blocos.append(_botao_add_acao(grupo_atual))
    return blocos


def _botao_add_acao(node_id):
    """«+ ação» da causa: cria mais uma ação para o mesmo balão de causa raiz."""
    return html.Div(
        dbc.Button([html.I(className="bi bi-plus-lg me-1"), "ação"],
                   id={"type": "fa-acao-add", "nid": node_id},
                   color="link", size="sm",
                   className="text-decoration-none p-0 small",
                   title="Adicionar outra ação para esta causa raiz"),
        className="text-end mb-3 pe-1",
    )


def register_failure_a3_callbacks(app):
    """Registra os callbacks das seções A3."""

    # -- Popular no load -------------------------------------------------

    @app.callback(
        Output("store-fa-secoes", "data"),
        Output("store-fa-secoes-base", "data"),
        [Output(i, "value") for i in _IDS_FIXOS],
        Input("store-fa-analise", "data"),
    )
    def _popular(analise):
        """Semeia o store e os campos de texto fixos da análise carregada.

        Seções 5 (Lições) e 6 (Encerramento) são campos fixos (via `_IDS_FIXOS`). O
        Plano de Ação (seção 4) é montado por `_render_acoes` de `store-fa-secoes.actions`.

        Semeia também `store-fa-secoes-base` — a foto do que veio do banco, contra a
        qual `_marcar_sujo` decide se há alteração não salva. Sai daqui (e não de um
        callback próprio) porque as duas fotos precisam nascer do MESMO valor: se o
        base viesse de outro lugar, qualquer diferença de normalização faria a página
        nascer "com alterações não salvas". Depois do Salvar, `_salvar` recarrega a
        análise e este callback roda de novo — o base acompanha o que foi gravado."""
        if not analise:
            return ({}, {}, *[None] * len(_IDS_FIXOS))

        secoes = {k: analise.get(k) for k in SECOES}
        # Normaliza o Plano de Ação no seed: colapsa duplicatas de `node_id` (corrupção
        # de um race antigo) e descarta órfãos, deixando uma linha por causa-raiz. Torna
        # a auto-cura determinística no load, sem depender da ordem dos callbacks.
        secoes["actions"] = sincronizar_acoes(analise.get("nos") or [], secoes.get("actions"))
        valores = []
        for i in _IDS_FIXOS:
            sec, campo = _CAMPOS_FIXOS[i]
            v = (secoes.get(sec) or {}).get(campo, "")
            valores.append("" if v is None else v)

        return (secoes, secoes, *valores)

    @app.callback(
        [Output(campo, "style") for campo in _TEXTAREAS_ALTURA],
        Input("store-fa-analise", "data"),
    )
    def _alturas_textareas(analise):
        """Restaura a altura que alguém deixou em cada campo de texto da análise.

        A altura fica salva **dentro da análise** (`secoes.alturas`), então todos os
        usuários que a abrirem encontram o mesmo tamanho. Campo sem altura salva não
        recebe `height`: aí o JS `fa_textarea_autosize.js` o ajusta ao texto que
        houver — é o que impede o relato de 8 linhas de voltar espremido em 2.

        A altura salva funciona como piso, não como camisa de força: se o texto
        crescer além dela, o JS aumenta a caixa a partir dali.

        `whiteSpace: pre-wrap` preserva as quebras de linha do texto.
        """
        salvas = alturas_salvas(analise)
        estilos = []
        for campo in _TEXTAREAS_ALTURA:
            estilo = {"whiteSpace": "pre-wrap"}
            px = salvas.get(campo)
            if px:
                estilo["height"] = f"{px}px"
            estilos.append(estilo)
        return estilos

    # -- Campos fixos (seções 1, 2, 6) → store ---------------------------
    # Não marcam `dirty` diretamente (o `_popular` preenche os campos no load e
    # dispararia): quem decide é `_marcar_sujo`, comparando o store com a foto do
    # banco. O Salvar do cabeçalho persiste tudo lendo `store-fa-secoes`.

    @app.callback(
        Output("store-fa-secoes", "data", allow_duplicate=True),
        [Input(i, "value") for i in _IDS_FIXOS],
        State("store-fa-secoes", "data"),
        prevent_initial_call=True,
    )
    def _campos_fixos(*args):
        valores = args[:len(_IDS_FIXOS)]
        store = dict(args[len(_IDS_FIXOS)] or {})
        for i, v in zip(_IDS_FIXOS, valores):
            sec, campo = _CAMPOS_FIXOS[i]
            store.setdefault(sec, {})
            store[sec] = dict(store[sec])
            store[sec][campo] = v
        return store

    @app.callback(
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Input("store-fa-secoes", "data"),
        State("store-fa-secoes-base", "data"),
        State("store-fa-dirty", "data"),
        prevent_initial_call=True,
    )
    def _marcar_sujo(secoes, base, dirty):
        """Liga o aviso de "alterações não salvas" quando o texto das seções muda.

        Em linguagem simples: quem escreve três parágrafos em "Lições Aprendidas" e
        clica em outro item do menu precisa ser avisado antes de perder o texto. Antes
        disto, só mexer no diagrama (criar balão, marcar ★, mover) armava o aviso — as
        seções do A3 escreviam em `store-fa-secoes` e ninguém tocava em
        `store-fa-dirty` (achado VF-06 do QA de 2026-08-05).

        Compara com a foto do banco (`store-fa-secoes-base`) em vez de reagir ao
        evento: o mesmo store é escrito pelo load (`_popular`) e pela reconciliação do
        ★, e reagir a qualquer escrita faria a página nascer suja. Só sobe o dirty —
        limpar é do Salvar e do Descartar.
        """
        if dirty or base is None:
            return no_update           # já avisado, ou store ainda não semeado
        return True if secoes_alteradas(base, secoes) else no_update

    # -- Plano de Ação (seção 4) = derivado das causas-raiz (★) ----------

    def _abrir_secao(atual, item_id):
        """Garante que a seção-alvo do Accordion esteja aberta (always_open = lista)."""
        abertos = list(atual or [])
        if item_id not in abertos:
            abertos.append(item_id)
        return abertos

    @app.callback(
        Output("store-fa-secoes", "data", allow_duplicate=True),
        Output("fa-accordion-secoes", "active_item", allow_duplicate=True),
        Input("store-fa-nos", "data"),
        State("store-fa-secoes", "data"),
        State("fa-accordion-secoes", "active_item"),
        prevent_initial_call=True,
    )
    def _sync_causas_raiz(nos, secoes, ativos):
        """Reconcilia `actions` com as causas-raiz (★) — regra pura `sincronizar_acoes`.

        Uma linha por causa-raiz (vínculo `node_id`), preservando o conteúdo editado;
        linha cujo balão deixa de ser causa-raiz some. Não marca `dirty` (o ★ já marca
        em `_toolbar_ops`). Abre a seção 4 quando entra uma causa nova.

        Guarda contra o race de load: `store-fa-nos` e `store-fa-analise` são setados
        juntos por `_carregar`, mas quem semeia `store-fa-secoes` (com as `actions` do
        banco) é o `_popular`, disparado por `store-fa-analise`. Se este callback rodar
        antes da semeadura, `secoes` chega vazio → `sincronizar_acoes(nos, [])` geraria
        uma linha EM BRANCO (id novo) por causa-raiz, sobrescrevendo o que foi salvo.
        Com store não-semeado, não há o que reconciliar — a reconciliação real roda a
        cada toggle ★ (`_toolbar_ops`), quando `secoes` já está populado."""
        if not secoes:
            return no_update, no_update
        secoes = dict(secoes or {})
        antes = secoes.get("actions") or []
        out = sincronizar_acoes(nos, antes)
        if out == antes:
            return no_update, no_update
        secoes["actions"] = out
        abrir = _abrir_secao(ativos, "sec-acoes") if len(out) > len(antes) else no_update
        return secoes, abrir

    @app.callback(
        Output("fa-acoes-container", "children"),
        Output("store-fa-acoes-ids", "data"),
        Input("store-fa-secoes", "data"),
        State("store-fa-acoes-ids", "data"),
        State("store-fa-nos", "data"),
    )
    def _render_acoes(secoes, ids_prev, nos):
        """Monta as linhas do Plano de Ação a partir de `store-fa-secoes.actions`.

        Só recria quando o CONJUNTO de linhas muda (add/remove de causa-raiz). Editar
        um campo muda o conteúdo do store mas mantém os mesmos ids → devolve
        `no_update` e o Textarea não perde o foco no meio da digitação."""
        actions = (secoes or {}).get("actions") or []
        ids_now = [a.get("id") for a in actions]
        if ids_now == (ids_prev or []):
            return no_update, no_update
        if not actions:
            vazio = html.Div(
                "Nenhuma causa raiz marcada. Marque um balão com ★ no diagrama "
                "para gerar a ação aqui.", className="text-muted small py-2")
            return vazio, ids_now
        hidratadas = _hidratar_causa(actions, nos)
        em_uso = [nome for a in actions for nome in lista_responsaveis(a.get("responsavel"))]
        resp_opts = _opcoes_responsavel(em_uso)
        # As alturas moram no próprio store de seções (`secoes.alturas`), então a
        # linha já nasce no tamanho salvo — sem esperar um segundo callback.
        alturas = alturas_salvas(secoes)
        return _blocos_por_causa(hidratadas, resp_opts, alturas), ids_now

    @app.callback(
        Output("store-fa-secoes", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Input({"type": "fa-acao-add", "nid": ALL}, "n_clicks"),
        State("store-fa-secoes", "data"),
        prevent_initial_call=True,
    )
    def _add_acao(clicks, secoes):
        """«+ ação» → mais uma linha para aquela causa raiz.

        O guard `any(clicks)` não é decoração: estes botões nascem junto com as
        linhas, e `prevent_initial_call` só cobre o load da página — componente
        criado depois dispara o callback na criação, com `n_clicks=None`. Mesma
        armadilha documentada em `_voltar_meses` (failure_analysis_callbacks).
        """
        if not clicks or not any(clicks):
            return no_update, no_update
        alvo = (dash.ctx.triggered_id or {}).get("nid")
        if not alvo:
            return no_update, no_update
        secoes = dict(secoes or {})
        secoes["actions"] = adicionar_acao(secoes.get("actions") or [], alvo)
        return secoes, True

    @app.callback(
        Output("store-fa-secoes", "data", allow_duplicate=True),
        Output("store-fa-dirty", "data", allow_duplicate=True),
        Input({"type": "fa-acao-del", "aid": ALL}, "n_clicks"),
        State("store-fa-secoes", "data"),
        prevent_initial_call=True,
    )
    def _del_acao(clicks, secoes):
        """🗑 → tira uma ação adicionada. A primeira linha da causa não tem o botão,
        e `remover_acao` recusa apagá-la mesmo que o clique chegue de outro jeito."""
        if not clicks or not any(clicks):
            return no_update, no_update
        alvo = (dash.ctx.triggered_id or {}).get("aid")
        if not alvo:
            return no_update, no_update
        atuais = (secoes or {}).get("actions") or []
        novas = remover_acao(atuais, alvo)
        if len(novas) == len(atuais):
            return no_update, no_update      # nada saiu (linha automática)
        secoes = dict(secoes or {})
        secoes["actions"] = novas
        return secoes, True

    @app.callback(
        Output("store-fa-secoes", "data", allow_duplicate=True),
        Input({"type": "fa-acao-desc", "aid": ALL}, "value"),
        Input({"type": "fa-acao-resp", "aid": ALL}, "value"),
        Input({"type": "fa-acao-prazo", "aid": ALL}, "date"),
        Input({"type": "fa-acao-status", "aid": ALL}, "value"),
        State({"type": "fa-acao-desc", "aid": ALL}, "id"),
        State("store-fa-secoes", "data"),
        prevent_initial_call=True,
    )
    def _sync_campos_acao(descs, resps, prazos, stats, ids, secoes):
        """Escreve os campos editados de cada linha de volta em `store-fa-secoes.actions`.

        Casado por `aid` (id do balão-ação); preserva `node_id`. Não recria as linhas
        (o `_render_acoes` devolve no_update quando os ids não mudam)."""
        if not ids:
            return no_update
        secoes = dict(secoes or {})
        por_aid = {a.get("id"): a for a in (secoes.get("actions") or [])}
        novas = []
        for i, d, r, p, s in zip(ids, descs, resps, prazos, stats):
            base = dict(por_aid.get(i.get("aid")) or {"id": i.get("aid")})
            base["descricao"] = d or ""
            # Guarda sempre como lista, mesmo com um nome só — o formato antigo
            # (texto) segue sendo lido por `lista_responsaveis` no load.
            base["responsavel"] = lista_responsaveis(r)
            base["prazo"] = p
            base["status"] = s if s is not None else base.get("status", STATUS_ACAO_PADRAO)
            novas.append({k: v for k, v in base.items() if not k.startswith("_")})
        secoes["actions"] = novas
        return secoes
