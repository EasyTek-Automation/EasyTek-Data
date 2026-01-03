# pages/dashboard.py - Marketing Visual Dashboard
"""
Dashboard de Produção com visual moderno e impactante para marketing.
Inclui gráficos gauge, sunburst, barras com gradiente, e indicadores visuais.
"""

from dash import dcc, html, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np

# ========================================
# PALETA DE CORES MODERNA
# ========================================
COLORS = {
    'primary': '#0d6efd',
    'success': '#20c997',
    'warning': '#ffc107', 
    'danger': '#dc3545',
    'info': '#0dcaf0',
    'purple': '#6f42c1',
    'pink': '#d63384',
    'orange': '#fd7e14',
    'teal': '#20c997',
    'cyan': '#0dcaf0',
    'gradient_start': '#00d4aa',
    'gradient_mid': '#ffd93d',
    'gradient_end': '#ff6b6b',
}

# Gradiente para barra de progresso (verde → amarelo → vermelho)
PROGRESS_GRADIENT = [
    '#00d4aa', '#20e3b2', '#40f2ba', '#5fffc2', '#7fffca',
    '#9fff9f', '#bfff7f', '#dfff5f', '#ffff3f', '#ffdf3f',
    '#ffbf3f', '#ff9f3f', '#ff7f3f', '#ff5f5f', '#ff3f3f'
]

# ========================================
# FUNÇÕES DE CRIAÇÃO DE GRÁFICOS
# ========================================

def create_gauge_chart(value, title, max_val=100, color_ranges=None):
    """Cria um gráfico gauge moderno com gradiente"""
    if color_ranges is None:
        color_ranges = [
            (0, 60, '#ff6b6b'),
            (60, 80, '#ffd93d'),
            (80, 100, '#00d4aa')
        ]
    
    # Converter cores hex para rgba com transparência
    def hex_to_rgba_local(hex_color, alpha=0.25):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f'rgba({r}, {g}, {b}, {alpha})'
    
    # Determinar cor do valor baseado no range
    value_color = '#00d4aa'  # default verde
    for r in color_ranges:
        if r[0] <= value < r[1]:
            value_color = r[2]
            break
    if value >= color_ranges[-1][1]:
        value_color = color_ranges[-1][2]
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        number={'suffix': '%', 'font': {'size': 36, 'family': 'Segoe UI, sans-serif'}},
        delta={'reference': 80, 'increasing': {'color': '#00d4aa'}, 'decreasing': {'color': '#ff6b6b'}},
        title={'text': title, 'font': {'size': 14, 'family': 'Segoe UI, sans-serif'}},
        gauge={
            'axis': {'range': [0, max_val], 'tickwidth': 1, 'tickvals': [0, 20, 40, 60, 80, 100]},
            'bar': {'color': value_color, 'thickness': 0.25},
            'bgcolor': 'rgba(0,0,0,0)',
            'borderwidth': 0,
            'steps': [
                {'range': [r[0], r[1]], 'color': hex_to_rgba_local(r[2])} for r in color_ranges
            ],
        }
    ))
    
    fig.update_layout(
        margin=dict(l=30, r=30, t=60, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=220,
        font={'family': 'Segoe UI, sans-serif'}
    )
    return fig


def create_donut_chart(labels, values, colors, title=""):
    """Cria um gráfico de donut moderno"""
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.65,
        marker=dict(colors=colors, line=dict(color='#fff', width=3)),
        textinfo='percent',
        textposition='outside',
        textfont=dict(size=12, family='Segoe UI, sans-serif'),
        hovertemplate='<b>%{label}</b><br>%{value} unidades<br>%{percent}<extra></extra>'
    )])
    
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=-0.15,
            xanchor='center',
            x=0.5,
            font=dict(size=11)
        ),
        margin=dict(l=20, r=20, t=40, b=60),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=280,
        annotations=[dict(
            text=f'<b>{sum(values)}</b><br><span style="font-size:11px">Total</span>',
            x=0.5, y=0.5,
            font=dict(size=20, family='Segoe UI, sans-serif'),
            showarrow=False
        )]
    )
    return fig


def create_horizontal_bar_chart(categories, values, title=""):
    """Cria um gráfico de barras horizontais com gradiente de cores"""
    # Normalizar valores para determinar cores
    max_val = max(values)
    colors = []
    for v in values:
        ratio = v / max_val
        if ratio >= 0.8:
            colors.append('#00d4aa')
        elif ratio >= 0.6:
            colors.append('#20c997')
        elif ratio >= 0.4:
            colors.append('#ffd93d')
        elif ratio >= 0.2:
            colors.append('#fd7e14')
        else:
            colors.append('#ff6b6b')
    
    fig = go.Figure(go.Bar(
        x=values,
        y=categories,
        orientation='h',
        marker=dict(
            color=colors,
            line=dict(color='rgba(0,0,0,0.1)', width=1),
            cornerradius=6
        ),
        text=[f'{v:,.0f}' for v in values],
        textposition='outside',
        textfont=dict(size=12, family='Segoe UI, sans-serif'),
        hovertemplate='<b>%{y}</b><br>Valor: %{x:,.0f}<extra></extra>'
    ))
    
    fig.update_layout(
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.15)',
            zeroline=False,
            showticklabels=True,
            tickfont=dict(size=10)
        ),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(size=12, family='Segoe UI, sans-serif')
        ),
        margin=dict(l=10, r=60, t=30, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=280,
        bargap=0.3
    )
    return fig


def create_vertical_bar_comparison(categories, series1, series2, name1="Atual", name2="Meta"):
    """Cria gráfico de barras verticais comparativo"""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=categories,
        y=series1,
        name=name1,
        marker=dict(color='#0d6efd', cornerradius=4),
        text=[f'{v:.1f}%' for v in series1],
        textposition='outside',
        textfont=dict(size=10)
    ))
    
    fig.add_trace(go.Bar(
        x=categories,
        y=series2,
        name=name2,
        marker=dict(color='#dee2e6', cornerradius=4),
        text=[f'{v:.1f}%' for v in series2],
        textposition='outside',
        textfont=dict(size=10)
    ))
    
    fig.update_layout(
        barmode='group',
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=11, family='Segoe UI, sans-serif')
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.15)',
            zeroline=False,
            range=[0, 110]
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        margin=dict(l=40, r=20, t=50, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=300,
        bargap=0.2,
        bargroupgap=0.1
    )
    return fig


def create_sunburst_chart(data_labels, data_parents, data_values, title=""):
    """Cria um gráfico sunburst para hierarquia de dados"""
    colors = [
        '#0d6efd', '#20c997', '#fd7e14', '#6c757d',
        '#0d6efd', '#198754', '#0dcaf0',
        '#ffc107', '#dc3545', '#6f42c1'
    ]
    
    fig = go.Figure(go.Sunburst(
        labels=data_labels,
        parents=data_parents,
        values=data_values,
        branchvalues="total",
        marker=dict(
            colors=colors[:len(data_labels)],
            line=dict(color='#fff', width=2)
        ),
        textfont=dict(size=12, family='Segoe UI, sans-serif'),
        insidetextorientation='radial',
        hovertemplate='<b>%{label}</b><br>Consumo: %{value:,.0f} kWh<extra></extra>'
    ))
    
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        height=350
    )
    return fig


def create_area_chart_gradient(hours, values, title=""):
    """Cria gráfico de área com gradiente suave"""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=hours,
        y=values,
        mode='lines',
        fill='tozeroy',
        line=dict(color='#0d6efd', width=3, shape='spline'),
        fillcolor='rgba(13, 110, 253, 0.15)',
        hovertemplate='<b>%{x}h</b><br>Consumo: %{y:,.0f} kWh<extra></extra>'
    ))
    
    # Linha de média
    avg = np.mean(values)
    fig.add_hline(
        y=avg, 
        line_dash="dash", 
        line_color="#6c757d",
        annotation_text=f"Média: {avg:,.0f} kWh",
        annotation_position="top right",
        annotation_font=dict(size=10, color='#6c757d')
    )
    
    fig.update_layout(
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=10),
            title=None
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.15)',
            zeroline=False,
            tickfont=dict(size=10),
            title=None
        ),
        margin=dict(l=50, r=20, t=20, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=250,
        hovermode='x unified'
    )
    return fig


def create_progress_bar_visual():
    """Cria uma representação visual de barra de progresso com gradiente"""
    # Dados simulados de progresso
    progress = 78.5
    
    return html.Div([
        # Label
        html.Div([
            html.Span("Meta Mensal de Produção", className="fw-semibold"),
            html.Span(f"{progress}%", className="fw-bold text-primary ms-auto")
        ], className="d-flex justify-content-between mb-2"),
        
        # Barra de progresso com gradiente
        html.Div([
            html.Div(
                style={
                    "width": f"{progress}%",
                    "height": "24px",
                    "background": "linear-gradient(90deg, #00d4aa 0%, #20c997 25%, #ffd93d 50%, #fd7e14 75%, #ff6b6b 100%)",
                    "backgroundSize": f"{100/progress*100}% 100%",
                    "borderRadius": "12px",
                    "transition": "width 1s ease-in-out",
                    "boxShadow": "0 2px 8px rgba(0, 212, 170, 0.3)"
                }
            )
        ], style={
            "width": "100%",
            "height": "24px",
            "backgroundColor": "var(--bs-secondary-bg)",
            "borderRadius": "12px",
            "overflow": "hidden"
        }),
        
        # Marcadores
        html.Div([
            html.Span("0%", className="text-muted", style={"fontSize": "10px"}),
            html.Span("50%", className="text-muted", style={"fontSize": "10px"}),
            html.Span("100%", className="text-muted", style={"fontSize": "10px"})
        ], className="d-flex justify-content-between mt-1")
    ], className="mb-3")


def hex_to_rgba(hex_color, alpha=0.2):
    """Converte cor hex para rgba"""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f'rgba({r}, {g}, {b}, {alpha})'


def create_mini_sparkline(values, color='#0d6efd'):
    """Cria mini gráfico sparkline para cards"""
    fig = go.Figure()
    
    # Converter hex para rgba para o fillcolor
    fill_color = hex_to_rgba(color, 0.2) if color.startswith('#') else color.replace(')', ', 0.2)').replace('rgb', 'rgba')
    
    fig.add_trace(go.Scatter(
        y=values,
        mode='lines',
        fill='tozeroy',
        line=dict(color=color, width=2, shape='spline', smoothing=1.3),
        fillcolor=fill_color
    ))
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=50,
        autosize=False,
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False)
    )
    return fig


# ========================================
# DADOS SIMULADOS
# ========================================

# Dados para gráficos
oee_atual = 85.7
disponibilidade = 92.3
performance = 88.1
qualidade = 97.2

# Dados para donut - Distribuição de Paradas
paradas_labels = ['Manutenção', 'Setup', 'Aguardando Material', 'Outros']
paradas_values = [45, 28, 18, 9]
paradas_colors = ['#0d6efd', '#6f42c1', '#fd7e14', '#6c757d']

# Dados para barras horizontais - Produção por Linha
linhas = ['Linha A', 'Linha B', 'Linha C', 'Linha D', 'Linha E']
producao_linhas = [2450, 2180, 1950, 1720, 1580]

# Dados para comparativo
turnos = ['1º Turno', '2º Turno', '3º Turno']
oee_turnos = [87.5, 84.2, 82.1]
metas_turnos = [85, 85, 85]

# Dados para sunburst - Hierarquia de Consumo (apenas folhas têm valores)
sunburst_labels = [
    "Fábrica", 
    "Produção", "Utilidades", "Administrativo",
    "Linha A", "Linha B", "Linha C",
    "Compressores", "HVAC", "Iluminação"
]
sunburst_parents = [
    "",
    "Fábrica", "Fábrica", "Fábrica",
    "Produção", "Produção", "Produção",
    "Utilidades", "Utilidades", "Utilidades"
]
# Valores: só os nós folha têm valores, os pais são calculados automaticamente
sunburst_values = [680, 450, 180, 50, 180, 150, 120, 80, 60, 40]

# Dados para área - Consumo por hora
horas = list(range(0, 24))
consumo_hora = [
    320, 310, 305, 300, 295, 310, 450, 680, 850, 920,
    980, 1050, 1020, 980, 950, 920, 890, 750, 620, 520,
    450, 400, 380, 350
]

# Sparklines com mais oscilação
spark_oee = [78, 82, 75, 88, 80, 92, 85, 79, 90, 84, 88, 86]
spark_energy = [500, 1500, 400, 2100, 500,3000 , 1100, 1380, 1250, 1450, 1300, 1380]
spark_quality = [95, 98, 94, 97, 96, 99, 95, 98, 96, 97, 98, 97]


# ========================================
# LAYOUT DO DASHBOARD
# ========================================

layout = dbc.Container([
    
    # ========================================
    # HEADER
    # ========================================
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H2([
                    html.I(className="bi bi-speedometer2 me-3", style={"color": "#0d6efd"}),
                    "Dashboard de Produção"
                ], className="mb-1", style={"fontWeight": "700"}),
                html.P(
                    f"Visão consolidada • Atualizado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
                    className="text-muted mb-0",
                    style={"fontSize": "0.9rem"}
                )
            ])
        ], width=8),
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button([
                    html.I(className="bi bi-arrow-clockwise me-2"),
                    "Atualizar"
                ], color="primary", size="sm", outline=True, id="btn-refresh-dashboard"),
                dbc.Button([
                    html.I(className="bi bi-download me-2"),
                    "Exportar"
                ], color="secondary", size="sm", outline=True),
            ], className="float-end")
        ], width=4, className="text-end d-flex align-items-center justify-content-end")
    ], className="mb-4 pt-3"),
    
    # ========================================
    # KPI CARDS COM SPARKLINES
    # ========================================
    dbc.Row([
        # Card OEE
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.I(className="bi bi-gear-wide-connected", 
                                   style={"fontSize": "1.5rem", "color": "#0d6efd"})
                        ], className="rounded-circle p-2", 
                           style={"backgroundColor": "rgba(13, 110, 253, 0.1)"}),
                        html.Div([
                            html.Span("OEE Geral", className="text-muted", style={"fontSize": "0.85rem"}),
                            html.H3(f"{oee_atual}%", className="mb-0 fw-bold")
                        ], className="ms-3")
                    ], className="d-flex align-items-center mb-2"),
                    html.Div([
                        dcc.Graph(
                            figure=create_mini_sparkline(spark_oee, '#0d6efd'), 
                            config={'displayModeBar': False, 'staticPlot': True},
                            style={'height': '50px'}
                        )
                    ], style={'height': '50px', 'overflow': 'hidden'}),
                    html.Small([
                        html.I(className="bi bi-arrow-up text-success me-1"),
                        html.Span("+2.3% vs ontem", className="text-success")
                    ])
                ])
            ], className="shadow-sm h-100 border-0")
        ], md=3, className="mb-3"),
        
        # Card Energia
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.I(className="bi bi-lightning-charge", 
                                   style={"fontSize": "1.5rem", "color": "#fd7e14"})
                        ], className="rounded-circle p-2", 
                           style={"backgroundColor": "rgba(253, 126, 20, 0.1)"}),
                        html.Div([
                            html.Span("Consumo Atual", className="text-muted", style={"fontSize": "0.85rem"}),
                            html.H3("1.380 kW", className="mb-0 fw-bold")
                        ], className="ms-3")
                    ], className="d-flex align-items-center mb-2"),
                    html.Div([
                        dcc.Graph(
                            figure=create_mini_sparkline(spark_energy, '#fd7e14'), 
                            config={'displayModeBar': False, 'staticPlot': True},
                            style={'height': '50px'}
                        )
                    ], style={'height': '50px', 'overflow': 'hidden'}),
                    html.Small([
                        html.I(className="bi bi-arrow-up text-danger me-1"),
                        html.Span("+5.1% vs média", className="text-danger")
                    ])
                ])
            ], className="shadow-sm h-100 border-0")
        ], md=3, className="mb-3"),
        
        # Card Qualidade
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.I(className="bi bi-patch-check", 
                                   style={"fontSize": "1.5rem", "color": "#20c997"})
                        ], className="rounded-circle p-2", 
                           style={"backgroundColor": "rgba(32, 201, 151, 0.1)"}),
                        html.Div([
                            html.Span("Qualidade", className="text-muted", style={"fontSize": "0.85rem"}),
                            html.H3(f"{qualidade}%", className="mb-0 fw-bold")
                        ], className="ms-3")
                    ], className="d-flex align-items-center mb-2"),
                    html.Div([
                        dcc.Graph(
                            figure=create_mini_sparkline(spark_quality, '#20c997'), 
                            config={'displayModeBar': False, 'staticPlot': True},
                            style={'height': '50px'}
                        )
                    ], style={'height': '50px', 'overflow': 'hidden'}),
                    html.Small([
                        html.I(className="bi bi-arrow-up text-success me-1"),
                        html.Span("+0.5% vs meta", className="text-success")
                    ])
                ])
            ], className="shadow-sm h-100 border-0")
        ], md=3, className="mb-3"),
        
        # Card Alarmes
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.I(className="bi bi-bell", 
                                   style={"fontSize": "1.5rem", "color": "#dc3545"})
                        ], className="rounded-circle p-2", 
                           style={"backgroundColor": "rgba(220, 53, 69, 0.1)"}),
                        html.Div([
                            html.Span("Alarmes Ativos", className="text-muted", style={"fontSize": "0.85rem"}),
                            html.H3("3", className="mb-0 fw-bold", style={"color": "#dc3545"})
                        ], className="ms-3")
                    ], className="d-flex align-items-center mb-3"),
                    html.Div([
                        dbc.Badge("2 Críticos", color="danger", className="me-2"),
                        dbc.Badge("1 Aviso", color="warning")
                    ]),
                    html.Div(className="mt-2"),
                    dbc.Button("Ver Alarmes →", href="/maintenance/alarms", 
                               size="sm", color="outline-danger", className="w-100 mt-2")
                ])
            ], className="shadow-sm h-100 border-0")
        ], md=3, className="mb-3"),
    ]),
    
    # ========================================
    # BARRA DE PROGRESSO META
    # ========================================
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    create_progress_bar_visual()
                ])
            ], className="shadow-sm border-0")
        ])
    ], className="mb-4"),
    
    # ========================================
    # GAUGES DE OEE
    # ========================================
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-speedometer me-2"),
                    html.Span("Indicadores OEE", className="fw-semibold")
                ], className="bg-transparent border-bottom"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dcc.Graph(
                                figure=create_gauge_chart(disponibilidade, "Disponibilidade"),
                                config={'displayModeBar': False}
                            )
                        ], md=4),
                        dbc.Col([
                            dcc.Graph(
                                figure=create_gauge_chart(performance, "Performance"),
                                config={'displayModeBar': False}
                            )
                        ], md=4),
                        dbc.Col([
                            dcc.Graph(
                                figure=create_gauge_chart(qualidade, "Qualidade"),
                                config={'displayModeBar': False}
                            )
                        ], md=4),
                    ])
                ])
            ], className="shadow-sm border-0")
        ])
    ], className="mb-4"),
    
    # ========================================
    # GRÁFICOS PRINCIPAIS - LINHA 1
    # ========================================
    dbc.Row([
        # Donut - Distribuição de Paradas
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-pie-chart me-2"),
                    html.Span("Distribuição de Paradas", className="fw-semibold")
                ], className="bg-transparent border-bottom"),
                dbc.CardBody([
                    dcc.Graph(
                        figure=create_donut_chart(paradas_labels, paradas_values, paradas_colors),
                        config={'displayModeBar': False}
                    )
                ])
            ], className="shadow-sm border-0 h-100")
        ], md=4, className="mb-4"),
        
        # Barras Horizontais - Produção por Linha
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-bar-chart-horizontal me-2"),
                    html.Span("Produção por Linha (unidades)", className="fw-semibold")
                ], className="bg-transparent border-bottom"),
                dbc.CardBody([
                    dcc.Graph(
                        figure=create_horizontal_bar_chart(linhas, producao_linhas),
                        config={'displayModeBar': False}
                    )
                ])
            ], className="shadow-sm border-0 h-100")
        ], md=4, className="mb-4"),
        
        # Barras Comparativas - OEE por Turno
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-bar-chart me-2"),
                    html.Span("OEE por Turno vs Meta", className="fw-semibold")
                ], className="bg-transparent border-bottom"),
                dbc.CardBody([
                    dcc.Graph(
                        figure=create_vertical_bar_comparison(turnos, oee_turnos, metas_turnos),
                        config={'displayModeBar': False}
                    )
                ])
            ], className="shadow-sm border-0 h-100")
        ], md=4, className="mb-4"),
    ]),
    
    # ========================================
    # GRÁFICOS PRINCIPAIS - LINHA 2
    # ========================================
    dbc.Row([
        # Sunburst - Hierarquia de Consumo
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-diagram-3 me-2"),
                    html.Span("Distribuição de Consumo Energético", className="fw-semibold")
                ], className="bg-transparent border-bottom"),
                dbc.CardBody([
                    dcc.Graph(
                        figure=create_sunburst_chart(sunburst_labels, sunburst_parents, sunburst_values),
                        config={'displayModeBar': False}
                    )
                ])
            ], className="shadow-sm border-0 h-100")
        ], md=5, className="mb-4"),
        
        # Área - Consumo por Hora
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-graph-up me-2"),
                    html.Span("Consumo Energético por Hora (kWh)", className="fw-semibold")
                ], className="bg-transparent border-bottom"),
                dbc.CardBody([
                    dcc.Graph(
                        figure=create_area_chart_gradient(horas, consumo_hora),
                        config={'displayModeBar': False}
                    )
                ])
            ], className="shadow-sm border-0 h-100")
        ], md=7, className="mb-4"),
    ]),
    
    # ========================================
    # TABELA DE RESUMO
    # ========================================
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.Div([
                        html.Div([
                            html.I(className="bi bi-table me-2"),
                            html.Span("Resumo de Produção por Turno", className="fw-semibold")
                        ]),
                        dbc.Badge("Hoje", color="primary", className="ms-auto")
                    ], className="d-flex align-items-center justify-content-between")
                ], className="bg-transparent border-bottom"),
                dbc.CardBody([
                    dbc.Table([
                        html.Thead([
                            html.Tr([
                                html.Th("Turno", style={"width": "15%"}),
                                html.Th("Produção", className="text-center"),
                                html.Th("OEE", className="text-center"),
                                html.Th("Disponib.", className="text-center"),
                                html.Th("Performance", className="text-center"),
                                html.Th("Qualidade", className="text-center"),
                                html.Th("Status", className="text-center"),
                            ], className="")
                        ]),
                        html.Tbody([
                            html.Tr([
                                html.Td([html.I(className="bi bi-sun me-2"), "1º Turno"]),
                                html.Td("2.450 un", className="text-center fw-semibold"),
                                html.Td([
                                    dbc.Badge("87.5%", color="success")
                                ], className="text-center"),
                                html.Td("94.2%", className="text-center"),
                                html.Td("90.1%", className="text-center"),
                                html.Td("97.8%", className="text-center"),
                                html.Td([
                                    html.I(className="bi bi-check-circle-fill text-success")
                                ], className="text-center")
                            ]),
                            html.Tr([
                                html.Td([html.I(className="bi bi-cloud-sun me-2"), "2º Turno"]),
                                html.Td("2.180 un", className="text-center fw-semibold"),
                                html.Td([
                                    dbc.Badge("84.2%", color="warning")
                                ], className="text-center"),
                                html.Td("91.5%", className="text-center"),
                                html.Td("87.8%", className="text-center"),
                                html.Td("96.9%", className="text-center"),
                                html.Td([
                                    html.I(className="bi bi-exclamation-circle-fill text-warning")
                                ], className="text-center")
                            ]),
                            html.Tr([
                                html.Td([html.I(className="bi bi-moon me-2"), "3º Turno"]),
                                html.Td("1.950 un", className="text-center fw-semibold"),
                                html.Td([
                                    dbc.Badge("82.1%", color="warning")
                                ], className="text-center"),
                                html.Td("89.8%", className="text-center"),
                                html.Td("86.2%", className="text-center"),
                                html.Td("97.1%", className="text-center"),
                                html.Td([
                                    html.I(className="bi bi-exclamation-circle-fill text-warning")
                                ], className="text-center")
                            ]),
                        ])
                    ], bordered=True, hover=True, responsive=True, className="mb-0")
                ])
            ], className="shadow-sm border-0")
        ])
    ], className="mb-4"),
    
], fluid=True, className="p-3", style={"minHeight": "100vh"})