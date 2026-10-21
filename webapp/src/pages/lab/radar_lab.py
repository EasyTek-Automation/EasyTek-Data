"""Radar Lab — playground provisório de gráfico radar totalmente dinâmico.

Rota: /lab/radar (experimental, nível 3).

Diferente do radar da página de Indicadores V1 (`create_performance_radar_chart`,
com 3 eixos e 3 séries fixas), aqui **tudo** é editável em tela: eixos (pontos do
polígono), camadas (séries), valores, cores e opções de exibição.

O estado inteiro vive num `dcc.Store` no navegador — nenhuma leitura ou escrita
em MongoDB. Exportar/importar JSON serve para guardar uma configuração e voltar
nela depois.

As funções deste módulo são puras (estado dentro, estado/figura fora) justamente
para poderem ser testadas sem subir o Dash — ver `webapp/tests/lab/test_radar_lab.py`.
"""

import copy
import json

from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.io as pio


# ==================== CONFIGURAÇÃO PLOTLY ====================
PLOTLY_CONFIG = {
    'displayModeBar': True,
    'displaylogo': False,
    'modeBarButtonsToRemove': [
        'zoom2d', 'pan2d', 'select2d', 'lasso2d',
        'zoomIn2d', 'zoomOut2d', 'resetScale2d',
        'hoverClosestCartesian', 'hoverCompareCartesian',
        'toggleSpikelines'
    ],
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'radar_lab',
        'height': None,
        'width': None,
        'scale': 2
    }
}

# Cores usadas em rodízio quando o usuário adiciona uma camada nova.
PALETA = [
    "#0d6efd", "#fd7e14", "#dc3545", "#198754",
    "#6f42c1", "#20c997", "#ffc107", "#6c757d",
]

ESTILOS_LINHA = [
    {"label": "Sólido", "value": "solid"},
    {"label": "Tracejado", "value": "dash"},
    {"label": "Pontilhado", "value": "dot"},
    {"label": "Traço-ponto", "value": "dashdot"},
]

# Teto do eixo radial quando o modo é "fixo" e o usuário ainda não mexeu.
RANGE_MAX_PADRAO = 150


# ==================== ESTADO ====================

def default_state():
    """Estado inicial do lab: replica o radar da V1 (Meta / Média Geral / Equipamento).

    Serve de ponto de partida conhecido e é para onde o botão "Restaurar padrão" volta.
    """
    eixos = [
        {"id": "ax1", "name": "MTBF", "desc": "Confiabilidade — tempo médio entre falhas"},
        {"id": "ax2", "name": "MTTR", "desc": "Manutenibilidade — tempo médio de reparo"},
        {"id": "ax3", "name": "Taxa de Avaria", "desc": "Disponibilidade — % de tempo parado por avaria"},
    ]
    camadas = [
        _nova_camada("ly1", "Meta", "#dc3545", {"ax1": 100, "ax2": 100, "ax3": 100},
                     dash="dot", opacity=0.10),
        _nova_camada("ly2", "Média Geral", "#fd7e14", {"ax1": 92, "ax2": 85, "ax3": 78},
                     dash="dash", opacity=0.15),
        _nova_camada("ly3", "Equipamento", "#0d6efd", {"ax1": 118, "ax2": 71, "ax3": 104},
                     dash="solid", opacity=0.20, width=3),
    ]
    return {
        "axes": eixos,
        "layers": camadas,
        "opts": {
            "range_mode": "auto",
            "range_max": RANGE_MAX_PADRAO,
            "tick_step": 0,
            "hole": 0.0,
            "legend": True,
            "labels": True,
            "grid": True,
            "title": "Radar Lab",
        },
    }


def _nova_camada(layer_id, name, color, values, dash="solid",
                 opacity=0.18, width=2, fill=True, visible=True):
    """Monta o dicionário de uma camada com todos os campos preenchidos."""
    return {
        "id": layer_id,
        "name": name,
        "color": color,
        "dash": dash,
        "opacity": opacity,
        "width": width,
        "fill": fill,
        "visible": visible,
        "values": dict(values),
    }


def _next_id(prefixo, existentes):
    """Gera o próximo id sequencial (`ax4`, `ly7`...) sem repetir os já usados."""
    numeros = []
    for item_id in existentes:
        sufixo = str(item_id)[len(prefixo):]
        if sufixo.isdigit():
            numeros.append(int(sufixo))
    return f"{prefixo}{(max(numeros) + 1) if numeros else 1}"


def normalize_state(state):
    """Devolve uma cópia do estado com todos os campos garantidos.

    Por que existe: o estado é persistido no `localStorage` do navegador. Um estado
    salvo antes de um campo novo existir — ou um JSON importado à mão pelo usuário —
    chegaria incompleto e quebraria a montagem da figura. Aqui tudo que falta ganha
    valor padrão, e todo par (camada, eixo) passa a ter um número.
    """
    if not isinstance(state, dict):
        state = {}
    novo = {"axes": [], "layers": [], "opts": {}}

    for i, eixo in enumerate(state.get("axes") or [], start=1):
        if not isinstance(eixo, dict):
            continue
        novo["axes"].append({
            "id": str(eixo.get("id") or f"ax{i}"),
            "name": str(eixo.get("name") or f"Eixo {i}"),
            "desc": str(eixo.get("desc") or ""),
        })

    ids_eixos = [e["id"] for e in novo["axes"]]

    for i, camada in enumerate(state.get("layers") or [], start=1):
        if not isinstance(camada, dict):
            continue
        valores_origem = camada.get("values") or {}
        valores = {}
        for eixo_id in ids_eixos:
            valores[eixo_id] = _to_float(valores_origem.get(eixo_id), 0.0)
        novo["layers"].append(_nova_camada(
            layer_id=str(camada.get("id") or f"ly{i}"),
            name=str(camada.get("name") or f"Camada {i}"),
            color=str(camada.get("color") or PALETA[(i - 1) % len(PALETA)]),
            values=valores,
            dash=str(camada.get("dash") or "solid"),
            opacity=_to_float(camada.get("opacity"), 0.18),
            width=_to_float(camada.get("width"), 2),
            fill=bool(camada.get("fill", True)),
            visible=bool(camada.get("visible", True)),
        ))

    opts_origem = state.get("opts") or {}
    padrao = default_state()["opts"]
    opts = dict(padrao)
    opts.update({k: v for k, v in opts_origem.items() if k in padrao})
    opts["range_mode"] = "fixed" if opts.get("range_mode") == "fixed" else "auto"
    opts["range_max"] = _to_float(opts.get("range_max"), RANGE_MAX_PADRAO)
    opts["tick_step"] = max(_to_float(opts.get("tick_step"), 0.0), 0.0)
    opts["hole"] = min(max(_to_float(opts.get("hole"), 0.0), 0.0), 0.6)
    for chave in ("legend", "labels", "grid"):
        opts[chave] = bool(opts.get(chave))
    opts["title"] = str(opts.get("title") or "")
    novo["opts"] = opts
    return novo


def _to_float(valor, padrao=0.0):
    """Converte para float aceitando string com vírgula; devolve `padrao` no lixo."""
    if valor is None or valor == "":
        return padrao
    if isinstance(valor, bool):
        return padrao
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return padrao


# ==================== OPERAÇÕES SOBRE O ESTADO ====================

def add_axis(state, name=None, desc=""):
    """Acrescenta um eixo no fim e cria o valor 0 dele em todas as camadas."""
    novo = normalize_state(state)
    eixo_id = _next_id("ax", [e["id"] for e in novo["axes"]])
    novo["axes"].append({
        "id": eixo_id,
        "name": name or f"Eixo {len(novo['axes']) + 1}",
        "desc": desc,
    })
    for camada in novo["layers"]:
        camada["values"][eixo_id] = 0.0
    return novo


def remove_axis(state, axis_id):
    """Remove o eixo e o valor correspondente em todas as camadas."""
    novo = normalize_state(state)
    novo["axes"] = [e for e in novo["axes"] if e["id"] != axis_id]
    for camada in novo["layers"]:
        camada["values"].pop(axis_id, None)
    return novo


def move_axis(state, axis_id, delta):
    """Move o eixo `delta` posições na lista (a ordem define a geometria do polígono).

    Movimento além das pontas é ignorado — não circula.
    """
    novo = normalize_state(state)
    ids = [e["id"] for e in novo["axes"]]
    if axis_id not in ids:
        return novo
    origem = ids.index(axis_id)
    destino = origem + delta
    if destino < 0 or destino >= len(ids):
        return novo
    novo["axes"].insert(destino, novo["axes"].pop(origem))
    return novo


def update_axis(state, axis_id, campo, valor):
    """Edita `name` ou `desc` de um eixo. Campo desconhecido é ignorado."""
    novo = normalize_state(state)
    if campo not in ("name", "desc"):
        return novo
    for eixo in novo["axes"]:
        if eixo["id"] == axis_id:
            eixo[campo] = "" if valor is None else str(valor)
    return novo


def add_layer(state, name=None):
    """Acrescenta uma camada zerada, com a próxima cor da paleta."""
    novo = normalize_state(state)
    layer_id = _next_id("ly", [c["id"] for c in novo["layers"]])
    cor = PALETA[len(novo["layers"]) % len(PALETA)]
    valores = {eixo["id"]: 0.0 for eixo in novo["axes"]}
    novo["layers"].append(_nova_camada(
        layer_id, name or f"Camada {len(novo['layers']) + 1}", cor, valores))
    return novo


def remove_layer(state, layer_id):
    """Remove a camada inteira (série + valores)."""
    novo = normalize_state(state)
    novo["layers"] = [c for c in novo["layers"] if c["id"] != layer_id]
    return novo


def update_layer(state, layer_id, campo, valor):
    """Edita um atributo de estilo/identificação da camada.

    Campos numéricos e booleanos são convertidos aqui para o estado nunca guardar
    string vinda de `Input`.
    """
    novo = normalize_state(state)
    for camada in novo["layers"]:
        if camada["id"] != layer_id:
            continue
        if campo == "name":
            camada["name"] = "" if valor is None else str(valor)
        elif campo == "color":
            camada["color"] = str(valor or camada["color"])
        elif campo == "dash":
            camada["dash"] = str(valor or "solid")
        elif campo == "opacity":
            camada["opacity"] = min(max(_to_float(valor, camada["opacity"]), 0.0), 1.0)
        elif campo == "width":
            camada["width"] = min(max(_to_float(valor, camada["width"]), 0.5), 12.0)
        elif campo in ("fill", "visible"):
            camada[campo] = bool(valor)
    return novo


def set_values_from_table(state, rows):
    """Aplica no estado os números editados no DataTable de valores.

    Cada linha é um eixo; cada coluna (fora `__axis`) é uma camada. Célula em branco
    ou com texto vira 0 — o radar não tem representação para "vazio".
    """
    novo = normalize_state(state)
    ids_eixos = [e["id"] for e in novo["axes"]]
    por_id = {c["id"]: c for c in novo["layers"]}
    for linha, eixo_id in zip(rows or [], ids_eixos):
        if not isinstance(linha, dict):
            continue
        for chave, valor in linha.items():
            if chave == "__axis":
                continue
            camada = por_id.get(chave)
            if camada is not None:
                camada["values"][eixo_id] = _to_float(valor, 0.0)
    return novo


def set_option(state, campo, valor):
    """Edita uma opção global de exibição (escala, legenda, rótulos, grade, título)."""
    novo = normalize_state(state)
    if campo not in novo["opts"]:
        return novo
    if campo == "range_mode":
        novo["opts"][campo] = "fixed" if valor == "fixed" else "auto"
    elif campo == "range_max":
        novo["opts"][campo] = max(_to_float(valor, RANGE_MAX_PADRAO), 1.0)
    elif campo == "tick_step":
        novo["opts"][campo] = max(_to_float(valor, 0.0), 0.0)
    elif campo == "hole":
        novo["opts"][campo] = min(max(_to_float(valor, 0.0), 0.0), 0.6)
    elif campo == "title":
        novo["opts"][campo] = "" if valor is None else str(valor)
    else:
        novo["opts"][campo] = bool(valor)
    return novo


def state_from_json(texto, fallback=None):
    """Lê o JSON colado pelo usuário. Texto inválido devolve `fallback` intacto.

    Nunca levanta: o objetivo é o usuário colar qualquer coisa e, no pior caso,
    o radar continuar como estava.
    """
    try:
        carregado = json.loads(texto or "")
    except (TypeError, ValueError):
        return copy.deepcopy(fallback) if fallback is not None else None
    if not isinstance(carregado, dict):
        return copy.deepcopy(fallback) if fallback is not None else None
    return normalize_state(carregado)


def state_to_json(state):
    """Serializa o estado normalizado, pronto para o botão de exportar."""
    return json.dumps(normalize_state(state), indent=2, ensure_ascii=False)


# ==================== FIGURA ====================

def _rgba(hex_color, alpha):
    """Converte `#rrggbb` em `rgba(...)` para usar como preenchimento translúcido."""
    cor = (hex_color or "#0d6efd").lstrip("#")
    if len(cor) == 3:
        cor = "".join(c * 2 for c in cor)
    try:
        r, g, b = (int(cor[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        r, g, b = 13, 110, 253
    return f"rgba({r}, {g}, {b}, {alpha})"


def _template_registrado(nome):
    """Devolve o template só se ele estiver registrado no Plotly, senão `None`.

    Os temas `minty`/`darkly` só existem depois que `app.py` roda
    `load_figure_template`. Fora do app (testes, scripts) passar o nome cru
    levantaria `ValueError` — aqui a figura simplesmente sai com o tema default,
    já que as cores que importam são definidas explicitamente logo abaixo.
    """
    return nome if nome in pio.templates else None


def build_figure(state, template="minty", height=520):
    """Monta o radar a partir do estado.

    Cada camada visível vira um `Scatterpolar` fechado (o primeiro ponto é repetido
    no fim, senão o polígono aparece aberto). Com menos de 3 eixos o desenho degenera
    em linha/ponto — é permitido de propósito, faz parte do playground.
    """
    is_dark = (template == "darkly")
    bg_color = "#2c2c2c" if is_dark else "#ffffff"
    grid_color = "#495057" if is_dark else "#dee2e6"
    fg_color = "#e9ecef" if is_dark else "#212529"

    state = normalize_state(state)
    eixos = state["axes"]
    opts = state["opts"]

    fig = go.Figure()

    if not eixos:
        fig.update_layout(
            template=_template_registrado(template), height=height,
            margin=dict(l=30, r=30, t=50, b=30),
            paper_bgcolor="rgba(0,0,0,0)",
            annotations=[dict(
                text="Sem eixos — adicione ao menos um ponto no painel à esquerda.",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False, font=dict(size=14, color=fg_color), opacity=0.6,
            )],
        )
        return fig

    categorias = [e["name"] or e["id"] for e in eixos]
    descricoes = [e["desc"] for e in eixos]
    theta = categorias + [categorias[0]]
    custom = [[d] for d in descricoes + [descricoes[0]]]

    maior = 0.0
    for camada in state["layers"]:
        if not camada["visible"]:
            continue
        valores = [camada["values"].get(e["id"], 0.0) for e in eixos]
        maior = max([maior] + valores)
        fig.add_trace(go.Scatterpolar(
            r=valores + [valores[0]],
            theta=theta,
            customdata=custom,
            fill="toself" if camada["fill"] else "none",
            fillcolor=_rgba(camada["color"], camada["opacity"]),
            line=dict(color=camada["color"], width=camada["width"], dash=camada["dash"]),
            name=camada["name"] or camada["id"],
            hovertemplate=(
                f"<b>{camada['name'] or camada['id']}</b><br>"
                "%{theta}: %{r:.2f}"
                "<br><i>%{customdata[0]}</i><extra></extra>"
            ),
        ))

    if opts["range_mode"] == "fixed":
        teto = opts["range_max"]
    else:
        teto = maior * 1.1 if maior > 0 else 1.0

    fig.update_layout(
        template=_template_registrado(template),
        height=height,
        title=dict(text=opts["title"], x=0.5, font=dict(size=15, color=fg_color)),
        polar=dict(
            bgcolor=bg_color,
            # Buraco no centro: em escala curta (0–2 da auditoria) o zero fincado
            # no ponto central some — vários eixos zerados viram um ponto só. Com o
            # buraco cada zero vira um vértice visível. Custo: exagera a diferença
            # entre 0 e 1 aos olhos, por isso o teto é 0,6 e o padrão é 0.
            hole=opts["hole"],
            radialaxis=dict(
                visible=opts["grid"],
                range=[0, teto],
                # Escala discreta (ex.: nota 0/1/2 de auditoria) não pode mostrar
                # meio ponto: com tick_step o usuário fixa o intervalo dos traços.
                dtick=opts["tick_step"] or None,
                gridcolor=grid_color,
                showticklabels=opts["grid"],
                tickfont=dict(size=10, color=fg_color),
            ),
            angularaxis=dict(
                gridcolor=grid_color,
                showticklabels=opts["labels"],
                tickfont=dict(size=11, color=fg_color),
            ),
        ),
        showlegend=opts["legend"],
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5,
                    font=dict(size=11)),
        margin=dict(l=50, r=50, t=50 if opts["title"] else 30, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ==================== TABELA DE VALORES ====================

def table_columns(state):
    """Colunas do DataTable: primeira é o nome do eixo (fixa), uma por camada depois."""
    state = normalize_state(state)
    colunas = [{"name": "Eixo", "id": "__axis", "editable": False}]
    for camada in state["layers"]:
        colunas.append({
            "name": camada["name"] or camada["id"],
            "id": camada["id"],
            "type": "numeric",
            "editable": True,
        })
    return colunas


def table_data(state):
    """Linhas do DataTable — uma por eixo, na mesma ordem do polígono."""
    state = normalize_state(state)
    linhas = []
    for eixo in state["axes"]:
        linha = {"__axis": eixo["name"] or eixo["id"]}
        for camada in state["layers"]:
            linha[camada["id"]] = camada["values"].get(eixo["id"], 0.0)
        linhas.append(linha)
    return linhas


# ==================== PAINÉIS (renderizados pelos callbacks) ====================

def render_axes_panel(state):
    """Lista editável de eixos: nome, descrição, subir/descer e remover."""
    state = normalize_state(state)
    if not state["axes"]:
        return html.Small("Nenhum eixo. Clique em “+ Eixo”.", className="text-muted")

    linhas = []
    for i, eixo in enumerate(state["axes"]):
        linhas.append(html.Div([
            dbc.Row([
                dbc.Col(dbc.Input(
                    id={"type": "rl-axis-name", "index": eixo["id"]},
                    value=eixo["name"], debounce=True, size="sm",
                    placeholder="Nome do ponto",
                ), width=7),
                dbc.Col(dbc.ButtonGroup([
                    dbc.Button("↑", id={"type": "rl-axis-up", "index": eixo["id"]},
                               size="sm", color="light", disabled=(i == 0), title="Subir"),
                    dbc.Button("↓", id={"type": "rl-axis-down", "index": eixo["id"]},
                               size="sm", color="light",
                               disabled=(i == len(state["axes"]) - 1), title="Descer"),
                    dbc.Button("✕", id={"type": "rl-axis-del", "index": eixo["id"]},
                               size="sm", color="light", title="Remover ponto"),
                ], size="sm"), width=5, className="text-end"),
            ], className="g-1"),
            dbc.Input(
                id={"type": "rl-axis-desc", "index": eixo["id"]},
                value=eixo["desc"], debounce=True, size="sm",
                placeholder="Descrição (aparece no hover)",
                className="mt-1",
            ),
        ], className="mb-2 pb-2 border-bottom"))
    return html.Div(linhas)


def render_layers_panel(state):
    """Lista editável de camadas: nome, cor, estilo, espessura, opacidade e flags."""
    state = normalize_state(state)
    if not state["layers"]:
        return html.Small("Nenhuma camada. Clique em “+ Camada”.", className="text-muted")

    cartoes = []
    for camada in state["layers"]:
        cartoes.append(dbc.Card(dbc.CardBody([
            dbc.Row([
                dbc.Col(dbc.Input(
                    id={"type": "rl-layer-name", "index": camada["id"]},
                    value=camada["name"], debounce=True, size="sm",
                    placeholder="Nome da camada",
                ), width=8),
                dbc.Col(dbc.Input(
                    id={"type": "rl-layer-color", "index": camada["id"]},
                    type="color", value=camada["color"],
                    style={"height": "31px", "padding": "2px"},
                ), width=2),
                dbc.Col(dbc.Button(
                    "✕", id={"type": "rl-layer-del", "index": camada["id"]},
                    size="sm", color="light", title="Remover camada",
                ), width=2, className="text-end"),
            ], className="g-1"),
            dbc.Row([
                dbc.Col([
                    html.Small("Linha", className="text-muted"),
                    dbc.Select(
                        id={"type": "rl-layer-dash", "index": camada["id"]},
                        options=ESTILOS_LINHA, value=camada["dash"], size="sm",
                    ),
                ], width=5),
                dbc.Col([
                    html.Small("Espessura", className="text-muted"),
                    dbc.Input(
                        id={"type": "rl-layer-width", "index": camada["id"]},
                        type="number", min=0.5, max=12, step=0.5,
                        value=camada["width"], debounce=True, size="sm",
                    ),
                ], width=3),
                dbc.Col([
                    html.Small("Opacidade", className="text-muted"),
                    dbc.Input(
                        id={"type": "rl-layer-opacity", "index": camada["id"]},
                        type="number", min=0, max=1, step=0.05,
                        value=camada["opacity"], debounce=True, size="sm",
                    ),
                ], width=4),
            ], className="g-1 mt-1"),
            dbc.Row([
                dbc.Col(dbc.Switch(
                    id={"type": "rl-layer-fill", "index": camada["id"]},
                    label="Preencher", value=camada["fill"], className="mb-0",
                ), width=6),
                dbc.Col(dbc.Switch(
                    id={"type": "rl-layer-vis", "index": camada["id"]},
                    label="Visível", value=camada["visible"], className="mb-0",
                ), width=6),
            ], className="g-1 mt-1"),
        ], className="p-2"), className="mb-2 shadow-sm"))
    return html.Div(cartoes)


def render_values_table(state):
    """Tabela de valores (eixos × camadas) montada a partir do estado.

    Vale o mesmo motivo do painel de exibição: a tabela é editável, então
    `data` já é Input do callback que escreve o estado. Devolver `data` a
    partir do store fecharia um ciclo de dependência — que o Dash 3 recusa,
    derrubando os callbacks e deixando importar/restaurar sem efeito na tela.
    """
    return dash_table.DataTable(
        id="rl-values-table",
        columns=table_columns(state),
        data=table_data(state),
        editable=True,
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "center", "padding": "6px",
                    "fontFamily": "inherit", "fontSize": "0.85rem"},
        style_cell_conditional=[{"if": {"column_id": "__axis"},
                                 "textAlign": "left", "fontWeight": "600"}],
        style_header={"fontWeight": "700"},
    )


def render_options_panel(state):
    """Controles de exibição montados a partir do estado.

    Por que é um painel renderizado e não campos fixos: escrever de volta em
    `value` a partir do store fecha um ciclo de dependência (store → value →
    store) que o Dash 3 recusa, e aí "Restaurar padrão" e "Importar JSON"
    param de chegar ao gráfico. Renderizando o card inteiro — como já é feito
    com eixos e camadas — o estado continua sendo a única fonte da verdade.
    """
    opts = normalize_state(state)["opts"]
    return [
        dbc.Input(id="rl-title", value=opts["title"], size="sm",
                  debounce=True, placeholder="Título do gráfico", className="mb-2"),
        html.Small("Escala do eixo radial", className="text-muted"),
        dbc.RadioItems(
            id="rl-range-mode",
            options=[{"label": "Automática", "value": "auto"},
                     {"label": "Fixa", "value": "fixed"}],
            value=opts["range_mode"], inline=True, className="mb-2",
        ),
        dbc.Input(id="rl-range-max", type="number", min=1, step=10,
                  value=opts["range_max"], debounce=True, size="sm",
                  placeholder="Máximo", className="mb-2"),
        html.Small("Intervalo dos traços (0 = automático)", className="text-muted"),
        dbc.Input(id="rl-tick-step", type="number", min=0, step=0.5,
                  value=opts["tick_step"], debounce=True, size="sm", className="mb-2"),
        html.Small("Buraco no centro (0 = zero no ponto central)", className="text-muted"),
        dbc.Input(id="rl-hole", type="number", min=0, max=0.6, step=0.05,
                  value=opts["hole"], debounce=True, size="sm", className="mb-2"),
        dbc.Switch(id="rl-opt-legend", label="Legenda", value=opts["legend"]),
        dbc.Switch(id="rl-opt-labels", label="Rótulos dos pontos", value=opts["labels"]),
        dbc.Switch(id="rl-opt-grid", label="Grade e escala", value=opts["grid"]),
    ]


# ==================== LAYOUT ====================

def layout():
    """Página do Radar Lab (rota provisória `/lab/radar`)."""
    estado = default_state()

    painel_controles = html.Div([
        dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-diagram-3 me-2"),
                html.Strong("Pontos do radar"),
                dbc.Button("+ Eixo", id="rl-add-axis", size="sm",
                           color="primary", className="float-end"),
            ]),
            dbc.CardBody(id="rl-axes-panel", children=render_axes_panel(estado),
                         style={"maxHeight": "420px", "overflowY": "auto"}),
        ], className="shadow-sm mb-3"),

        dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-layers me-2"),
                html.Strong("Camadas"),
                dbc.Button("+ Camada", id="rl-add-layer", size="sm",
                           color="primary", className="float-end"),
            ]),
            dbc.CardBody(id="rl-layers-panel", children=render_layers_panel(estado),
                         style={"maxHeight": "620px", "overflowY": "auto"}),
        ], className="shadow-sm mb-3"),

        dbc.Card([
            dbc.CardHeader([html.I(className="bi bi-sliders me-2"), html.Strong("Exibição")]),
            dbc.CardBody(id="rl-opts-panel", children=render_options_panel(estado)),
        ], className="shadow-sm mb-3"),

        dbc.Card([
            dbc.CardHeader([html.I(className="bi bi-save me-2"), html.Strong("Salvar / Carregar")]),
            dbc.CardBody([
                dbc.Button([html.I(className="bi bi-download me-1"), "Exportar JSON"],
                           id="rl-export", size="sm", color="secondary", className="me-2"),
                dbc.Button([html.I(className="bi bi-arrow-counterclockwise me-1"),
                            "Restaurar padrão"],
                           id="rl-reset", size="sm", color="light"),
                html.Hr(),
                dbc.Textarea(id="rl-import-text", rows=4, className="mb-2",
                             placeholder="Cole aqui um JSON exportado e clique em Importar"),
                dbc.Button("Importar JSON", id="rl-import-apply", size="sm", color="secondary"),
                html.Div(id="rl-import-msg", className="mt-2"),
            ]),
        ], className="shadow-sm"),
    ])

    painel_grafico = html.Div([
        dbc.Card([
            dbc.CardHeader([html.I(className="bi bi-pentagon me-2"), html.Strong("Radar")]),
            dbc.CardBody(dcc.Graph(id="rl-graph", config=PLOTLY_CONFIG,
                                   figure=build_figure(estado))),
        ], className="shadow-sm mb-3"),

        dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-table me-2"),
                html.Strong("Valores"),
                html.Small(" — linhas são os pontos, colunas são as camadas",
                           className="text-muted ms-2"),
            ]),
            dbc.CardBody(id="rl-table-panel", children=render_values_table(estado)),
        ], className="shadow-sm"),
    ])

    return html.Div([
        dcc.Store(id="rl-store", data=estado, storage_type="local"),
        dcc.Download(id="rl-download"),

        dbc.Row([
            dbc.Col([
                html.H4([html.I(className="bi bi-pentagon me-2"), "Radar Lab"],
                        className="mb-1"),
                html.Small(
                    "Playground de radar dinâmico — eixos, camadas e valores editáveis. "
                    "Nada é gravado no banco: o estado fica no seu navegador.",
                    className="text-muted",
                ),
            ], width=9),
            dbc.Col(dbc.Badge("Rota provisória", color="warning", className="float-end"),
                    width=3),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(painel_controles, md=4, lg=4),
            dbc.Col(painel_grafico, md=8, lg=8),
        ]),
    ], className="p-3")
