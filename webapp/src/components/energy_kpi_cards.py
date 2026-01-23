"""
Energy KPI Cards Components
Cards de indicadores para a página de energia SE03
"""

import dash_bootstrap_components as dbc
from dash import html, dcc
import plotly.graph_objects as go


def create_fp_card():
    """
    Card de Fator de Potência Médio (MM01)

    Exibe:
    - Valor do FP médio (0-1)
    - Badge de qualidade (Bom/Regular/Ruim)
    - Opções de período (1h, 8h, 24h)
    """
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className="bi bi-lightning-charge-fill me-2",
                       style={"fontSize": "1.5rem", "color": "#6c757d"}),
                html.H6("Fator de Potência Médio",
                       className="text-muted mb-0 d-inline")
            ], className="mb-3"),

            # RadioItems para selecionar período
            dbc.RadioItems(
                id="fp-period-radio",
                options=[
                    {"label": "1h", "value": 1},
                    {"label": "8h", "value": 8},
                    {"label": "24h", "value": 24}
                ],
                value=24,
                inline=True,
                className="mb-3"
            ),

            html.H3(id="fp-value", children="--", className="mb-2"),
            dbc.Badge(
                id="fp-badge",
                children="Calculando...",
                color="secondary",
                className="mt-1"
            ),
            html.Small(id="fp-period-label", children="Últimas 24 horas", className="text-muted mt-2 d-block")
        ], className="d-flex flex-column justify-content-center h-100")
    ], className="shadow-sm h-100 w-100")


def create_desbalanco_card():
    """
    Card de Desbalanceamento de Fases por Equipamento

    Exibe:
    - Desbalanceamento de cada multimedidor (MM02 a MM07)
    - Badge de status para cada um (OK/Atenção/Crítico)
    """
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className="bi bi-diagram-3-fill me-2",
                       style={"fontSize": "1.5rem", "color": "#6c757d"}),
                html.H6("Desbalanceamento de Fases",
                       className="text-muted mb-0 d-inline")
            ], className="mb-3"),

            # Conteúdo dinâmico com lista de equipamentos
            html.Div(id="desbalanco-content", children=[
                html.Small("Carregando...", className="text-muted")
            ]),

            html.Small("Últimas 24 horas", className="text-muted mt-2 d-block")
        ], className="d-flex flex-column justify-content-center h-100")
    ], className="shadow-sm h-100 w-100")


def create_consumo_medio_card():
    """
    Card de Consumo Médio (Transversais + Longitudinais)

    Exibe:
    - Consumo médio Transversais (kW)
    - Consumo médio Longitudinais (kW)
    - Total médio (kW)
    """
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className="bi bi-speedometer2 me-2",
                       style={"fontSize": "1.5rem", "color": "#6c757d"}),
                html.H6("Consumo Médio",
                       className="text-muted mb-0 d-inline")
            ], className="mb-3"),
            html.Div(id="consumo-medio-content", children=[
                html.Div([
                    html.Small("Transversais:", className="text-muted me-2"),
                    html.Span("-- kW", className="fw-bold")
                ], className="mb-1"),
                html.Div([
                    html.Small("Longitudinais:", className="text-muted me-2"),
                    html.Span("-- kW", className="fw-bold")
                ], className="mb-2"),
                html.Hr(className="my-2"),
                html.Div([
                    html.Small("Total:", className="text-muted me-2"),
                    html.H5("-- kW", className="mb-0 d-inline")
                ])
            ]),
            html.Small("Período selecionado", className="text-muted mt-2 d-block")
        ], className="d-flex flex-column justify-content-center h-100")
    ], className="shadow-sm h-100 w-100")


def create_donut_chart_card():
    """
    Card com Gráfico de Rosca (Donut Chart)

    Exibe distribuição de consumo:
    - Transversais (%)
    - Longitudinais (%)
    - Total no centro (kWh)
    """
    # Gráfico inicial vazio
    fig = go.Figure(data=[go.Pie(
        labels=['Transversais', 'Longitudinais'],
        values=[1, 1],  # Valores placeholder
        hole=.65,
        marker=dict(colors=['#2E86AB', '#F77F00']),
        textinfo='percent',
        textposition='inside',
        hovertemplate='<b>%{label}</b><br>%{value:.1f} kWh<br>%{percent}<extra></extra>'
    )])

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5
        ),
        height=250,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        annotations=[dict(
            text='--<br>kWh',
            x=0.5, y=0.5,
            font=dict(size=20, color='#6c757d'),
            showarrow=False
        )]
    )

    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className="bi bi-pie-chart-fill me-2",
                       style={"fontSize": "1.5rem", "color": "#6c757d"}),
                html.H6("Distribuição de Consumo",
                       className="text-muted mb-0 d-inline")
            ], className="mb-2"),
            dcc.Graph(
                id='donut-chart',
                figure=fig,
                config={'displayModeBar': False},
                style={'height': '280px'}
            ),
            html.Small("Período selecionado", className="text-muted d-block text-center")
        ], className="d-flex flex-column justify-content-center h-100")
    ], className="shadow-sm h-100 w-100")


# Helper functions para criar badges
def get_fp_badge(fp_value):
    """
    Retorna badge apropriado baseado no valor do FP

    Args:
        fp_value (float): Valor do fator de potência (0-1)

    Returns:
        tuple: (text, color)
    """
    if fp_value is None or fp_value == 0:
        return ("Sem dados", "secondary")
    elif fp_value >= 0.92:
        return ("Bom ✓", "success")
    elif fp_value >= 0.85:
        return ("Regular", "warning")
    else:
        return ("Ruim", "danger")


def get_desbalanco_badge(desbal_percent):
    """
    Retorna badge apropriado baseado no desbalanceamento

    Args:
        desbal_percent (float): Percentual de desbalanceamento

    Returns:
        tuple: (text, color)
    """
    if desbal_percent is None:
        return ("Sem dados", "secondary")
    elif desbal_percent < 5:
        return ("OK ✓", "success")
    elif desbal_percent < 10:
        return ("Atenção", "warning")
    else:
        return ("Crítico", "danger")
