# src/pages/maintenance/failure_analysis.py

"""
Página da Análise de Falhas de uma parada (/maintenance/analise-de-falhas/ishikawa).

Recebe a parada por query string (`?parada=LONGI002_202606220911_201`) porque o
router do projeto resolve `ROUTES` por pathname exato — não há parâmetro de rota.
Precedente: `/maintenance/indicators-v2?tab=custo` (index.py).

Escopo: cabeçalho da parada (resumo + dados editáveis) + diagrama de causa e
efeito (Ishikawa) interativo com distribuição de tempo, e as seções A3 abaixo —
Plano de Ação, Lições Aprendidas e Encerramento. Causa Raiz e Solução não têm
seção: a causa raiz é marcada no próprio diagrama (★).

Ids usam prefixo `fa-` para não colidir com os callbacks da página de Pareto
(`af-`) nem com os da indicators-v2 (`v2-`).
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_cytoscape as cyto

from src.utils.failure_a3 import STATUS_ACAO

cyto.load_extra_layouts()  # habilita o layout dagre (LR)

# O diagrama usa dash-cytoscape (lib Python que desenha os nós). Os balões são a
# interface: ao selecionar um balão surge uma TOOLBAR FLUTUANTE ancorada nele
# (+ Irmã, + Ramificação, causa raiz, excluir) — não há painel CRUD lateral.
# Cytoscape renderiza os nós em canvas, então os botões não cabem literalmente
# dentro do nó; a toolbar é posicionada sobre o balão por um pequeno JS.

ACCENT = "#c0392b"        # vermelho — mesma identidade da página de Análise de Falhas
COR_RAIZ = "#2c3e50"
COR_CAUSA_RAIZ = "#e67e22"

LAYOUT_DIAGRAMA = {"name": "dagre", "rankDir": "LR", "nodeSep": 18, "rankSep": 90,
                   "animate": False, "fit": True, "padding": 30}

STYLESHEET = [
    {"selector": "node", "style": {
        "content": "data(label)", "text-wrap": "wrap", "text-max-width": "150px",
        "text-valign": "center", "text-halign": "center", "shape": "round-rectangle",
        "width": "170px", "height": "58px", "background-color": "#ffffff",
        "border-width": 2, "border-color": ACCENT, "color": "#212529",
        "font-size": "11px", "padding": "6px"}},
    {"selector": '[tipo = "ROOT"]', "style": {
        "background-color": COR_RAIZ, "border-color": COR_RAIZ, "color": "#ffffff",
        "font-weight": "bold", "width": "200px", "height": "70px"}},
    {"selector": '[tipo = "STEP"]', "style": {"border-color": ACCENT}},
    {"selector": '[tipo = "CAUSE"]', "style": {"border-color": "#adb5bd"}},
    {"selector": "[?is_root_cause]", "style": {
        "border-color": COR_CAUSA_RAIZ, "border-width": 4, "background-color": "#fff6ec"}},
    {"selector": "node:selected", "style": {"border-color": "#0d6efd", "border-width": 4}},
    # Balão explicativo (não leva tempo) → tracejado e apagado.
    {"selector": "[?explicativo]", "style": {
        "border-style": "dashed", "border-color": "#adb5bd",
        "background-color": "#f8f9fa", "color": "#6c757d"}},
    # Tempo inconsistente (estouro/divergência do grupo) → vermelho.
    {"selector": "[?tempo_erro]", "style": {
        "border-color": "#dc3545", "border-width": 4, "background-color": "#fdecec"}},
    {"selector": "edge", "style": {
        "curve-style": "taxi", "taxi-direction": "horizontal",
        "target-arrow-shape": "triangle", "line-color": "#adb5bd",
        "target-arrow-color": "#adb5bd", "width": 2}},
]




def _resumo_item(icone, label, value_id):
    """Uma linha do resumo read-only da parada (ícone · rótulo · valor).

    O valor é um `html.Span` (não input) — o dado vem da parada e não se edita;
    fica como lista limpa, sem caixas de texto mortas ocupando espaço.
    """
    return html.Div([
        html.I(className=f"bi {icone} me-2 text-secondary"),
        html.Span(label, className="text-muted small"),
        html.Span("—", id=value_id, className="fw-semibold small ms-auto text-end"),
    ], className="d-flex align-items-center py-2 border-bottom")


def _edit_field(label, componente):
    """Campo editável empilhado (rótulo em cima, componente embaixo)."""
    return html.Div(
        [html.Label(label, className="form-label small fw-semibold mb-1"), componente],
        className="mb-3",
    )


def _titulo_secao(numero, texto):
    """Título de seção do accordion: badge numerado (laranja da marca) + texto.

    Deixa claro que a linha é um cabeçalho expansível — antes o número vinha solto
    no texto ("1. Problema") e, colapsado, tudo se misturava. O badge é um elemento
    real (não `::before`), então segue a cor da marca do cliente definida no CSS."""
    return html.Span([
        html.Span(str(numero), className="fa-sec-num"),
        html.Span(texto, className="fa-sec-txt"),
    ], className="fa-sec-titulo")


def _titulo_secao_icone(icone, texto):
    """Título de seção com badge de ÍCONE (não número). Usado pela seção de Fotos,
    para não renumerar as seções 1–6 já validadas (premissa de preservação)."""
    return html.Span([
        html.Span(html.I(className=f"bi {icone}"), className="fa-sec-num"),
        html.Span(texto, className="fa-sec-txt"),
    ], className="fa-sec-titulo")


def _secao_fotos():
    """Seção "Fotos da ocorrência" — accordion próprio (SDD analise-falhas-fotos).

    Galeria geral por análise: área de upload (dirigida pelo JS fa_photos_upload),
    grade de miniaturas (render por callback a partir do Mongo) e lightbox (JS). O id
    da análise vai num `<div>` oculto (`fa-fotos-aid`) para o JS montar as URLs."""
    corpo = html.Div([
        # id da análise para o JS (upload/serve) — preenchido no load.
        html.Div(id="fa-fotos-aid", style={"display": "none"}),
        # Área de upload: o botão aciona um <input type=file> que o JS
        # (fa_photos_upload) cria dinamicamente — o Dash não tem input nativo de
        # arquivo. A área é ocultada por callback quando não se pode subir.
        html.Div([
            dbc.Button([html.I(className="bi bi-plus-lg me-1"), "Adicionar fotos"],
                       id="fa-fotos-btn", color="primary", outline=True, size="sm"),
            html.Small(id="fa-fotos-contador", className="text-muted ms-2"),
        ], id="fa-fotos-upload-area", className="mb-2 d-flex align-items-center flex-wrap gap-1"),
        html.Div(id="fa-fotos-alerta", className="mb-2"),
        html.Div(id="fa-fotos-grid", className="fa-fotos-grid"),
        # Referência discreta: onde as fotos ficam no file server + id da análise
        # (para localizar a pasta no \\file-server quando precisar).
        html.Small(id="fa-fotos-ref", className="text-muted d-block mt-2",
                   style={"fontSize": "0.72rem"}),
    ])
    return dbc.Accordion([
        dbc.AccordionItem(corpo, title=_titulo_secao_icone("bi-camera", "Fotos da ocorrência"),
                          item_id="sec-fotos"),
    ], id="fa-accordion-fotos", always_open=True, className="mb-3 fa-a3-accordion",
       start_collapsed=True)


def _controles_diagrama():
    """Controles do diagrama novo: marcar causa raiz e a dica de uso.

    O Excalidraw não tem botão dentro do balão (a barrinha do diagrama antigo), então
    marcar a causa raiz passa a ser: seleciona o balão, clica no botão. O botão fica
    desabilitado enquanto nada estiver selecionado — clique que não faz nada é pior
    que botão apagado.
    """
    return html.Div([
        html.Div(
            "Desenhe os balões e ligue-os com setas: a seta vai do balão de cima "
            "para o de baixo. Dê duplo clique para escrever dentro do balão.",
            className="text-muted", style={"fontSize": "0.75rem"},
        ),
        html.Div([
            dbc.Button([html.I(className="bi bi-star me-1"), "Causa raiz (★)"],
                       id="fa-btn-causa-raiz", size="sm", color="warning",
                       outline=True, disabled=True,
                       title="Marca o balão selecionado como causa raiz — "
                             "gera a linha no Plano de Ação (seção 4)"),
            html.Small(id="fa-causa-raiz-dica", className="text-muted ms-2",
                       children="selecione um balão no diagrama"),
        ], className="d-flex align-items-center"),
    ], className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2")


def _versao_diagrama():
    """Botões v2.0 / v3.0 para alternar entre o diagrama antigo e o novo, como no
    Indicadores. Só o diagrama troca — o resto da página é o mesmo nas duas.

    Os dois diagramas leem e gravam os mesmos balões (`store-fa-nos`), então trocar
    não converte nada. A troca é só mostrar um e esconder o outro, feita no navegador
    por `fa_diagrama_versao.js`, que também lembra a escolha de cada pessoa e recusa
    a troca enquanto houver alteração não salva.
    """
    return html.Div([
        html.Small(id="fa-diag-versao-aviso", className="text-danger me-2"),
        html.Small("Versão do diagrama", className="text-muted me-2"),
        dbc.ButtonGroup([
            dbc.Button("v2.0", id="fa-btn-diag-v2", color="primary", size="sm",
                       outline=True, title="Diagrama anterior (com tempos em cada balão)"),
            dbc.Button("v3.0", id="fa-btn-diag-v3", color="primary", size="sm",
                       outline=False, title="Diagrama novo (desenho livre)"),
        ]),
    ], className="d-flex justify-content-end align-items-center mb-2")


def _canvas_diagrama():
    """O quadro de desenho (Excalidraw), num iframe servido pelos assets.

    O iframe isola o React do Excalidraw do React do Dash e, se a página remontar,
    o próprio quadro repete o aviso de "estou pronto" até receber os balões de volta
    — foi o que resolveu o diagrama nascer vazio depois de um recarregamento.
    """
    return html.Div([
        html.Iframe(
            id="fa-frame", src="/assets/fa_excalidraw.html",
            style={"width": "100%", "height": "75vh", "border": "0", "display": "block"},
        ),
        # Destino obrigatório do callback da ponte (clientside precisa de um Output).
        dcc.Store(id="fa-ponte-sink"),
        # Destino do clientside que agenda a imagem do diagrama para o slide (IM-AF3-08).
        dcc.Store(id="fa-diagrama-imagem-sink"),
        # Balões com mais de uma seta chegando. O desenho é livre, mas a análise
        # precisa ser uma árvore: o Salvar consulta isto e avisa em vez de gravar torto.
        dcc.Store(id="store-fa-conflitos", data=[]),
    ], style={"position": "relative"})


def _cabecalho():
    """Cabeçalho split: resumo da parada (read-only, à esquerda) + dados editáveis
    do A3 (à direita). O resumo é uma lista limpa; a edição fica isolada do outro
    lado. Área/Subgrupo e o Título ficam ocultos por ora (o Título aparece no topo;
    Área/Subgrupo o usuário decide depois) — mantidos no DOM só para os callbacks."""
    resumo = html.Div([
        html.Div("Resumo da parada", className="text-uppercase text-muted fw-bold mb-2",
                 style={"fontSize": "0.72rem", "letterSpacing": "0.04em"}),
        _resumo_item("bi-calendar-event", "Data da ocorrência", "fa-parada-data"),
        _resumo_item("bi-play-circle", "Hora de início", "fa-parada-inicio"),
        _resumo_item("bi-stop-circle", "Hora de término", "fa-parada-fim"),
        _resumo_item("bi-hourglass-split", "Duração total", "fa-parada-duracao"),
        _resumo_item("bi-gear-wide-connected", "Equipamento", "fa-parada-equip"),
        _resumo_item("bi-exclamation-triangle", "Causa cadastrada", "fa-parada-causa"),
        # Composição diária da parada mensal (drill "1 grande vs várias pequenas").
        # Vazio quando a falha ocorreu num único dia.
        html.Div(id="fa-por-dia", className="mt-3"),
    ])

    edicao = html.Div([
        html.Div("Dados da análise", className="text-uppercase text-muted fw-bold mb-2",
                 style={"fontSize": "0.72rem", "letterSpacing": "0.04em"}),
        _edit_field("Nome", dbc.Input(id="fa-nome", size="sm",
                    placeholder="Como você quer se referir a esta parada")),
        # Responsável vem da collection `usuarios` — mesmo padrão do workflow.
        _edit_field("Responsável", html.Div([
            dcc.Dropdown(id="fa-responsavel", placeholder="Selecione o responsável",
                         clearable=False, searchable=True),
            html.Small(id="fa-responsavel-help", className="text-muted d-block"),
        ])),
        # Participantes = multi-select dos mesmos usuários (não mais texto livre).
        _edit_field("Participantes", dcc.Dropdown(
            id="fa-participantes", multi=True, searchable=True,
            placeholder="Selecione os participantes")),
    ])

    return dbc.Card(
        [
            dbc.CardHeader(
                html.Div([
                    html.Div([
                        html.Strong(id="fa-titulo-exibicao", style={"fontSize": "1.05rem"}),
                        html.Div(id="fa-subtitulo", className="text-muted",
                                 style={"fontSize": "0.8rem"}),
                    ]),
                    html.Div(id="fa-status-badge"),
                ], className="d-flex justify-content-between align-items-center flex-wrap gap-2"),
                className="py-2",
            ),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(resumo, md=5, xs=12, className="border-end pe-md-4 mb-3 mb-md-0"),
                    dbc.Col(edicao, md=7, xs=12, className="ps-md-4"),
                ], className="g-0"),
                # `titulo` é read-only (derivado da parada) e fica oculto — só
                # alimenta o callback de exibição. Área/Subgrupo saíram daqui: são
                # editados na Seção 1 do A3 (`fa-sec-prob-area`/`-subgrupo`).
                html.Div([
                    dbc.Input(id="fa-titulo", disabled=True),
                ], style={"display": "none"}),
            ]),
        ],
        className="shadow-sm mb-3",
        style={"borderTop": f"4px solid {ACCENT}"},
    )


def _txt(id_, label, placeholder="", area=False, md=4):
    """Campo de texto de seção A3, ligado por id `fa-sec-<secao>-<campo>`."""
    comp = (dbc.Textarea(id=id_, rows=2, className="form-control-sm")
            if area else dbc.Input(id=id_, size="sm"))
    if placeholder:
        comp.placeholder = placeholder
    return dbc.Col([html.Label(label, className="form-label small fw-semibold mb-1"), comp],
                   md=md, xs=12)


def _secoes_problema_contencao():
    """Seções 1 e 2 (Problema, Contenção) — vêm ANTES do diagrama (ordem do A3,
    conforme o modelo em planilha). Campos da seção 1 alinhados ao modelo:
    Descrição · Onde (Área/Equip/Subgrupo) · Observações. O antigo campo
    "Desenho / foto / evidência" saiu da tela (v3): as fotos têm galeria própria e o
    texto já gravado continua no banco."""
    sec1 = dbc.Row([
        _txt("fa-sec-prob-descricao", "Descrição do problema", area=True, md=12),
        dbc.Col(html.Div("Onde:", className="fw-semibold mt-1"), md=12),
        _txt("fa-sec-prob-area", "Área"),
        _txt("fa-sec-prob-equip", "Equipamento"),
        _txt("fa-sec-prob-subgrupo", "Subgrupo"),
        _txt("fa-sec-prob-obs", "Observações do primeiro atendimento", area=True, md=12),
    ], className="g-2")

    sec2 = dbc.Row([
        _txt("fa-sec-cont-acoes",
             "Ações realizadas para conter o problema (antes da causa raiz / reparo)",
             area=True, md=12),
        _txt("fa-sec-cont-local", "Onde a ação de contenção foi realizada"),
        _txt("fa-sec-cont-resp", "Responsável"),
        _txt("fa-sec-cont-inicio", "Data de início da contenção"),
    ], className="g-2")

    return dbc.Accordion([
        dbc.AccordionItem(sec1, title=_titulo_secao(1, "Esclareça o Problema"),
                          item_id="sec-problema"),
        dbc.AccordionItem(sec2, title=_titulo_secao(2, "Ação de Contenção"),
                          item_id="sec-contencao"),
    ], id="fa-accordion-topo", always_open=True, className="mb-3 fa-a3-accordion",
       active_item=["sec-problema"])


def _secoes_a3():
    """Seções 4–6 do A3 (Plano de Ação, Lições Aprendidas, Encerramento), exibidas
    ABAIXO do diagrama (Accordion). Causa raiz e Solução foram removidas — não
    existem no modelo de A3 em uso (vinham da aba oculta da planilha)."""
    # Seção 4 = linhas de componentes (NÃO DataTable): Ação=Textarea (larga, quebra
    # linha, colar normal), Responsável=Dropdown de usuários, Prazo=DatePicker. As
    # linhas são renderizadas por `_render_acoes` a partir de `store-fa-secoes.actions`
    # (derivado das causas-raiz ★). `store-fa-acoes-ids` guarda o conjunto de ids
    # renderizado, para não recriar as linhas (perder foco) quando só o conteúdo muda.
    cab_cols = dbc.Row([
        dbc.Col(html.Small("Causa (balão)", className="fw-semibold text-muted"), md=2),
        dbc.Col(html.Small("Ação", className="fw-semibold text-muted"), md=4),
        dbc.Col(html.Small("Responsável", className="fw-semibold text-muted"), md=2),
        dbc.Col(html.Small("Prazo", className="fw-semibold text-muted"), md=2),
        dbc.Col(html.Small("Status", className="fw-semibold text-muted"), md=2),
    ], className="g-2 d-none d-md-flex mb-1")

    sec7 = html.Div([
        cab_cols,
        html.Div(id="fa-acoes-container"),
        dcc.Store(id="store-fa-acoes-ids"),
        html.Div([
            html.Small("As linhas vêm das causas-raiz marcadas com ★ no diagrama. "
                       "Marque um balão como causa raiz para gerar a ação aqui; "
                       "desmarque para removê-la.", className="text-muted"),
        ], className="mt-2"),
        html.Div([html.Small(f"Status: {' · '.join(f'{k}={v}' for k, v in STATUS_ACAO.items())}",
                             className="text-muted")], className="mt-1"),
    ])

    # Seção 5 = um campo só (A3 oficial: "8. Lições Aprendidas").
    sec8 = dbc.Row([
        _txt("fa-sec-licoes", "Lições aprendidas", area=True, md=12),
    ], className="g-2")

    # Seção 6 = enxuta (A3 oficial: "9. Ass. Final do Responsável / Data").
    # Assinatura = dropdown restrito ao PRÓPRIO usuário (não digitação livre); as
    # opções/valor vêm do callback `_assinatura` (o usuário logado). Concluir exige
    # nível 3 (validado no botão + em `_concluir`).
    sec9 = dbc.Row([
        dbc.Col([
            html.Label("Assinatura final do responsável",
                       className="form-label small fw-semibold mb-1"),
            dcc.Dropdown(id="fa-sec-enc-resp", options=[], clearable=False,
                         placeholder="Você (usuário logado)"),
            html.Small("Só o próprio usuário assina · Concluir exige nível 3.",
                       className="text-muted"),
        ], md=8, xs=12),
        dbc.Col([
            html.Label("Data", className="form-label small fw-semibold mb-1"),
            # with_portal: o calendário abre como modal centralizado (não é cortado
            # pelo overflow do accordion nem pela borda inferior da tela — esta é a
            # última seção).
            dcc.DatePickerSingle(id="fa-sec-enc-data", placeholder="Data",
                                 display_format="DD/MM/YYYY", className="d-block",
                                 with_portal=True),
        ], md=4, xs=12),
    ], className="g-2")

    def item(titulo, corpo, item_id):
        return dbc.AccordionItem(corpo, title=titulo, item_id=item_id)

    return dbc.Accordion([
        item(_titulo_secao(4, "Plano de Ação"), sec7, "sec-acoes"),
        item(_titulo_secao(5, "Lições Aprendidas"), sec8, "sec-sustentabilidade"),
        item(_titulo_secao(6, "Encerramento"), sec9, "sec-encerramento"),
    ], id="fa-accordion-secoes", always_open=True, className="mb-3 fa-a3-accordion",
       start_collapsed=True)


def layout(parada: str = None):
    """Layout da página. `parada` é a chave do evento, vinda da query string.

    O carregamento real acontece no callback disparado por `store-fa-chave` — o
    layout só precisa carregar a chave para dentro da página.
    """
    return dbc.Container(
        [
            dcc.Store(id="store-fa-chave", data=parada),
            dcc.Store(id="store-fa-analise"),      # cabeçalho + versão + status
            dcc.Store(id="store-fa-nos"),          # árvore corrente (draft, não salva)
            dcc.Store(id="store-fa-nos-original"), # snapshot para o Descartar
            dcc.Store(id="store-fa-selecionado"),  # id do balão selecionado
            dcc.Store(id="store-fa-dirty", data=False),
            # Foto das seções do A3 como vieram do banco. Serve de referência para
            # saber se o que está na tela já foi salvo — é o que arma o aviso de
            # saída quando alguém só digita texto, sem tocar no diagrama.
            dcc.Store(id="store-fa-secoes-base"),
            # Download do .pptx de um slide só ("Exportar esta análise", S5).
            dcc.Download(id="download-fa-slide"),
            # Fotos: lista atual (do Mongo) + gatilho de recarga que o JS bumpa após
            # upload/exclusão (SDD analise-falhas-fotos).
            dcc.Store(id="store-fa-fotos"),
            dcc.Store(id="store-fa-fotos-refresh"),
            # Altura (px) de cada campo de texto do A3 depois que o usuário arrasta a
            # alça de redimensionar — mapa `{id_do_campo: px}`. Um JS
            # (fa_textarea_autosize.js) escreve aqui; o Salvar persiste em
            # `secoes.alturas` e o load restaura. Como fica dentro da análise, o
            # tamanho vale para todos os usuários que a abrirem. Os campos também
            # crescem sozinhos com o texto — a altura salva é só um piso.
            dcc.Store(id="store-fa-alturas"),
            # id do balão recém-criado → clientside abre o editor de texto nele.
            dcc.Store(id="store-fa-editar-novo"),
            html.Div(id="fa-editar-novo-sink", style={"display": "none"}),
            # Alvo neutro do callback client-side (beforeunload).
            html.Div(id="fa-beforeunload", style={"display": "none"}),

            dbc.Toast(id="fa-toast", header="Análise de Falhas", is_open=False,
                      dismissable=True, duration=5000, icon="info",
                      style={"position": "fixed", "top": "90px", "right": "20px",
                             "width": "380px", "zIndex": 1060}),

            # Linha do título — TRAVADA no topo (sticky) para efeito paralaxe: o
            # conteúdo rola por baixo. Salvar/Descartar vivem aqui (Descartar só
            # aparece com alterações; Salvar pisca discreto quando há pendência).
            html.Div(
                dbc.Row([
                    dbc.Col([
                        dbc.Button([html.I(className="bi bi-arrow-left me-1"), "Voltar às paradas"],
                                   id="fa-btn-voltar", color="link", size="sm", className="ps-0"),
                        html.H3([html.I(className="bi bi-diagram-3 me-2", style={"color": ACCENT}),
                                 "Análise de Falha"], className="mb-0"),
                    ], xs=12, md=6),
                    dbc.Col(
                        # Botão isolado, FORA do ButtonGroup já entregue (preservação de
                        # UI): leva esta análise sozinha para um .pptx de um slide (S5).
                        [dbc.Button([html.I(className="bi bi-file-earmark-slides me-1"),
                                     html.Span("Exportar esta análise")],
                                    id="fa-btn-exportar-slide", color="dark",
                                    outline=True, size="sm", className="me-2"),
                         dbc.ButtonGroup([
                            dbc.Button([html.I(className="bi bi-x-lg me-1"), "Descartar"],
                                       id="fa-btn-descartar", color="secondary", outline=True,
                                       size="sm", style={"display": "none"}),
                            dbc.Button([html.I(className="bi bi-save me-1"), "Salvar alterações"],
                                       id="fa-btn-salvar", color="primary", size="sm"),
                            # "Entregar ao gestor" era "Concluir". O nome mudou porque
                            # o significado mudou: a análise trava e vai para a fila de
                            # alguém — não acabou, falta o aceite.
                            dbc.Button([html.I(className="bi bi-send me-1"),
                                        "Entregar ao gestor"],
                                       id="fa-btn-concluir", color="success", outline=True,
                                       size="sm"),
                            # Só o gestor (nível 4) vê estes dois. Botão que a pessoa
                            # não pode usar não aparece, em vez de aparecer desabilitado
                            # sem explicação.
                            dbc.Button([html.I(className="bi bi-check2-circle me-1"),
                                        "Aceitar"],
                                       id="fa-btn-aceitar", color="success", size="sm",
                                       style={"display": "none"}),
                            dbc.Button([html.I(className="bi bi-arrow-counterclockwise me-1"),
                                        "Devolver"],
                                       id="fa-btn-devolver", color="warning", outline=True,
                                       size="sm", style={"display": "none"}),
                         ])],
                        xs=12, md=6,
                        className="d-flex align-items-end justify-content-md-end mt-3 mt-md-0",
                    ),
                ], className="mb-0 align-items-end"),
                id="fa-topbar",
                style={"position": "sticky", "top": 0, "zIndex": 1030,
                       "background": "var(--bs-body-bg)", "padding": "0.6rem 0",
                       "marginBottom": "1rem", "boxShadow": "0 3px 6px rgba(0,0,0,0.08)"},
            ),

            html.Div(id="fa-alerta-permissao"),
            # Faixa de estado: quem abre uma análise travada e não consegue digitar
            # acha que é defeito. Aqui ela diz o estado e desde quando.
            html.Div(id="fa-faixa-estado"),
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Devolver a análise")),
                dbc.ModalBody([
                    html.P("A análise volta a ser editável por quem a fez, com o motivo "
                           "à mostra.", className="text-muted small"),
                    dbc.Label("Motivo da devolução"),
                    dbc.Textarea(id="fa-devolver-motivo", rows=3,
                                 placeholder="Ex.: a causa raiz aponta o operador, não o "
                                             "equipamento — refazer o diagrama pela falha "
                                             "mecânica."),
                    html.Div(id="fa-devolver-aviso", className="small text-danger mt-1"),
                ]),
                dbc.ModalFooter([
                    dbc.Button("Cancelar", id="fa-devolver-cancelar", color="secondary",
                               outline=True, size="sm"),
                    # Nasce desabilitado: devolução sem motivo obriga quem recebe a
                    # adivinhar (BR-15).
                    dbc.Button("Devolver", id="fa-devolver-confirmar", color="warning",
                               size="sm", disabled=True),
                ]),
            ], id="fa-modal-devolver", is_open=False, centered=True),
            _cabecalho(),

            # ── 1-2. Problema e Ação de Contenção (vêm ANTES do diagrama — ordem A3) ──
            _secoes_problema_contencao(),

            # ── Fotos da ocorrência (galeria) — accordion próprio após a Seção 1 ──
            _secao_fotos(),

            # ── 3. Diagrama de Causa e Efeito — item de accordion (colapsável) ──
            dbc.Accordion([
                dbc.AccordionItem([
                    # ── Troca de versão do diagrama (v2.0 Cytoscape / v3.0 Excalidraw) ──
                    _versao_diagrama(),

                    # ── Diagrama NOVO (Excalidraw): desenho livre ──
                    html.Div([
                        _controles_diagrama(),
                        _canvas_diagrama(),
                    ], id="fa-diagrama-v3"),

                    # ── Diagrama ANTIGO (dash-cytoscape): OCULTO, não removido ──
                    # Os 22 ids daqui de dentro (fa-diagrama, fa-switch-tempos,
                    # fa-tb-*, fa-inline-*, fa-tempo-*) são Input/State de callbacks
                    # que continuam registrados. Remover qualquer um deixa o Input
                    # órfão e o dash-renderer **aborta o ciclo inteiro** — na prática,
                    # "a tela pisca Updating e nada acontece". Por isso o bloco sai da
                    # vista, mas continua no DOM. A remoção definitiva (callbacks
                    # antes dos componentes) é passo próprio, depois de o Excalidraw
                    # estar estável em produção.
                    html.Div([
                    # Controles do diagrama (antes ficavam no CardHeader).
                    html.Div([
                        html.Div("Edite pelos balões: dê duplo clique no texto; use "
                                 "+ Irmã / + Ramif. no próprio balão.",
                                 className="text-muted", style={"fontSize": "0.75rem"}),
                        html.Div([
                            dbc.Checklist(
                                id="fa-switch-tempos",
                                options=[{"label": "Exibir tempos", "value": "sim"}],
                                value=["sim"], switch=True, className="small mb-0",
                            ),
                            dbc.Button([html.I(className="bi bi-arrow-counterclockwise me-1"),
                                        "Recalcular tempos"],
                                       id="fa-btn-reset-tempos", color="link", size="sm",
                                       className="p-0 ms-3 small",
                                       title="Limpa os tempos manuais — tudo volta ao rateio automático"),
                        ], className="d-flex align-items-center"),
                    ], className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2"),
                    html.Div(id="fa-alerta-tempo", className="mb-2"),
                    # Wrapper posicionado: a toolbar do balão flutua sobre o canvas.
                    html.Div([
                        cyto.Cytoscape(
                            id="fa-diagrama",
                            elements=[],
                            layout=LAYOUT_DIAGRAMA,
                            stylesheet=STYLESHEET,
                            style={"width": "100%", "height": "75vh"},
                            minZoom=0.2, maxZoom=2.5,
                            boxSelectionEnabled=False,
                            autoungrabify=False,       # permite arrastar balões
                            # Zoom só com Shift+scroll: desliga a roda nativa e o
                            # JS (fa_node_toolbar.js) reaplica o zoom só com Shift.
                            # Scroll normal continua rolando a página.
                            userZoomingEnabled=False,
                        ),
                        # Toolbar do balão — aparece no HOVER do balão (não precisa
                        # clicar). São botões Dash de verdade; operações em Python.
                        html.Div(
                            [dbc.ButtonGroup([
                                # + cria um bloco no mesmo nível (irmão);
                                # ++ cria um bloco filho (ramificação).
                                dbc.Button("+", id="fa-tb-irma", size="sm",
                                           color="primary",
                                           title="Adicionar bloco no mesmo nível (irmão)"),
                                dbc.Button("++", id="fa-tb-ramif", size="sm",
                                           color="primary", outline=True,
                                           title="Adicionar bloco filho (ramificação)"),
                                dbc.Button("✎", id="fa-tb-editar", size="sm",
                                           color="secondary", outline=True, title="Editar texto"),
                                # ★ causa raiz: marcar gera automaticamente a linha no
                                # Plano de Ação (seção 4). É a ÚNICA fonte da seção 4.
                                dbc.Button("★", id="fa-tb-raiz", size="sm",
                                           color="warning", outline=True,
                                           title="Causa raiz — gera a linha no Plano de Ação (seção 4)"),
                                dbc.Button("⏱", id="fa-tb-tempo", size="sm",
                                           color="secondary", outline=True,
                                           title="Editar o tempo deste balão"),
                                dbc.Button("🗑", id="fa-tb-excluir", size="sm",
                                           color="danger", outline=True, title="Excluir"),
                            ], size="sm"),
                             # Controle novo isolado (fora do ButtonGroup já validado):
                             # marca/desmarca o balão como explicativo — não leva tempo.
                             dbc.Button("∅", id="fa-tb-explicativo", size="sm",
                                        color="secondary", outline=True, className="ms-1",
                                        title="Marcar/desmarcar como explicativo (não leva tempo)"),
                             # Reparent pela hierarquia (isolados, fora do ButtonGroup):
                             # « sobe o balão um nível (vira irmão do pai); » o rebaixa
                             # (vira filho do irmão logo acima). O tipo STEP/CAUSE e o
                             # rateio de tempo são recalculados automaticamente.
                             dbc.Button("«", id="fa-tb-promover", size="sm",
                                        color="info", outline=True, className="ms-1",
                                        title="Subir um nível (virar irmão do pai)"),
                             dbc.Button("»", id="fa-tb-rebaixar", size="sm",
                                        color="info", outline=True,
                                        title="Descer um nível (virar filho do irmão acima)")],
                            id="fa-node-toolbar",
                            # Fundo sólido de card: sem isso os botões (outline, com
                            # vãos) deixam o balão de cima vazar por trás e a toolbar
                            # fica ilegível. Opaco + borda + sombra = painel destacado.
                            style={"position": "absolute", "display": "none", "zIndex": 30,
                                   "top": 0, "left": 0, "padding": "3px",
                                   "background": "var(--bs-body-bg)", "borderRadius": "7px",
                                   "border": "1px solid rgba(0,0,0,0.12)",
                                   "boxShadow": "0 3px 10px rgba(0,0,0,0.28)"},
                        ),
                        # Editor de texto inline: o próprio texto do balão vira input.
                        # O input é transparente/sem borda e é dimensionado/posicionado
                        # pelo JS para casar com o nó (fonte, tamanho, lugar); o label
                        # do canvas fica coberto pelo fundo opaco do editor (o JS o
                        # posiciona por cima). Sem botão OK visível — confirma por
                        # Enter ou ao clicar fora.
                        html.Div(
                            [
                                dbc.Textarea(
                                    id="fa-inline-text",
                                    style={"width": "100%", "height": "100%",
                                           "resize": "none", "overflow": "hidden",
                                           "textAlign": "center", "border": "none",
                                           "outline": "none", "boxShadow": "none",
                                           "background": "transparent", "padding": "6px",
                                           "color": "#212529", "lineHeight": "1.15",
                                           "fontFamily": "inherit"},
                                ),
                                dbc.Button("OK", id="fa-inline-ok",
                                           style={"display": "none"}),
                            ],
                            id="fa-inline-editor",
                            style={"position": "absolute", "display": "none", "zIndex": 21,
                                   "top": 0, "left": 0, "width": "170px", "height": "58px"},
                        ),
                        # Editor de tempo do balão (abre no ⏱): digita minutos →
                        # fixa como manual; "auto" tira o pino. Posicionado pelo JS.
                        html.Div(
                            dbc.InputGroup([
                                dbc.Input(id="fa-tempo-input", type="number", min=0,
                                          size="sm", placeholder="min"),
                                dbc.Button("OK", id="fa-tempo-ok", size="sm", color="primary"),
                                dbc.Button([html.I(className="bi bi-arrow-repeat me-1"), "Auto"],
                                           id="fa-tempo-auto", size="sm", color="secondary",
                                           title="Voltar ao automático (tira o pino deste balão)"),
                            ], size="sm"),
                            id="fa-tempo-editor",
                            # Fundo sólido de card (igual à toolbar): sem isso o
                            # editor flutua transparente sobre os balões e fica ruim.
                            style={"position": "absolute", "display": "none", "zIndex": 30,
                                   "top": 0, "left": 0, "width": "230px", "padding": "3px",
                                   "background": "var(--bs-body-bg)", "borderRadius": "7px",
                                   "border": "1px solid rgba(0,0,0,0.12)",
                                   "boxShadow": "0 3px 10px rgba(0,0,0,0.28)"},
                        ),
                        # Aviso estilo mapa: aparece ao rolar SEM Shift sobre o
                        # diagrama; some 3,5s depois de parar (JS em fa_node_toolbar.js).
                        html.Div(
                            [html.I(className="bi bi-mouse me-2"),
                             "Segure Shift e role para dar zoom in/out"],
                            id="fa-zoom-hint",
                            style={"position": "absolute", "top": "12px", "right": "12px",
                                   "zIndex": 25, "display": "none", "opacity": "0",
                                   "transition": "opacity 0.3s ease", "pointerEvents": "none",
                                   "background": "rgba(33,37,41,0.55)", "color": "#fff",
                                   "padding": "12px 22px", "borderRadius": "8px",
                                   "fontSize": "1.05rem", "boxShadow": "0 2px 10px rgba(0,0,0,0.25)"},
                        ),
                    ], style={"position": "relative"}),
                    ], id="fa-diagrama-legado", style={"display": "none"}),
                ], title=_titulo_secao(3, "Diagrama de Causa e Efeito"),
                   item_id="sec-diagrama"),
            ], id="fa-accordion-diagrama", always_open=True,
               active_item=["sec-diagrama"], className="mb-3 fa-a3-accordion"),

            # ── Seções A3 abaixo do diagrama (Plano de Ação, Sustentab., Encerr.) ──
            dcc.Store(id="store-fa-secoes"),
            _secoes_a3(),

            # Lightbox das fotos (overlay) — o JS (fa_photos_lightbox) preenche/abre.
            html.Div(id="fa-fotos-lightbox", className="fa-lightbox",
                     style={"display": "none"}),

        ],
        fluid=True,
        className="p-4 fa-page",
    )
