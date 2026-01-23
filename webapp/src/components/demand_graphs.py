"""
Demand Graphs Components
Gráficos de demanda temporal (kW e kVA) para SE03
"""

import dash_bootstrap_components as dbc
from dash import html, dcc
import plotly.graph_objects as go
from src.utils.empty_state import create_empty_state_figure


def create_demand_transversais_layout():
    """
    Layout do gráfico de Demanda Temporal - Transversais

    Exibe:
    - Demanda em kW (barras)
    - Demanda aparente em kVA (área transparente)
    - Equipamentos: MM02, MM04, MM06
    """
    # Gráfico inicial vazio
    fig = create_empty_demand_figure("Transversais")

    return dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-bar-chart-fill me-2"),
            html.Strong("Demanda Máxima Temporal - Transversais"),
            html.Small(" (MM02, MM04, MM06)", className="text-muted ms-2")
        ]),
        dbc.CardBody([
            dcc.Loading(
                id="loading-demand-trans",
                type="default",
                children=dcc.Graph(
                    id='demand-graph-transversais',
                    figure=fig,
                    config={
                        'displayModeBar': True,
                        'displaylogo': False,
                        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                        'doubleClick': 'reset',
                        'responsive': True
                    }
                )
            )
        ])
    ], className="shadow-sm mb-4")


def create_demand_longitudinais_layout():
    """
    Layout do gráfico de Demanda Temporal - Longitudinais

    Exibe:
    - Demanda em kW (barras)
    - Demanda aparente em kVA (área transparente)
    - Equipamentos: MM03, MM05, MM07
    """
    # Gráfico inicial vazio
    fig = create_empty_demand_figure("Longitudinais")

    return dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-bar-chart-fill me-2"),
            html.Strong("Demanda Máxima Temporal - Longitudinais"),
            html.Small(" (MM03, MM05, MM07)", className="text-muted ms-2")
        ]),
        dbc.CardBody([
            dcc.Loading(
                id="loading-demand-long",
                type="default",
                children=dcc.Graph(
                    id='demand-graph-longitudinais',
                    figure=fig,
                    config={
                        'displayModeBar': True,
                        'displaylogo': False,
                        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                        'doubleClick': 'reset',
                        'responsive': True
                    }
                )
            )
        ])
    ], className="shadow-sm mb-4")


def create_empty_demand_figure(grupo_nome, template='minty'):
    """
    Cria figura vazia para o gráfico de demanda usando placeholder visual

    Args:
        grupo_nome (str): Nome do grupo (Transversais ou Longitudinais)
        template (str): Template do tema ('minty' ou 'darkly')

    Returns:
        plotly.graph_objects.Figure: Figura com placeholder visual
    """
    # Define cores baseado no tema
    is_dark = (template == 'darkly')

    if is_dark:
        bg_color = '#2c2c2c'
        text_color = '#e0e0e0'
        subtitle_color = '#a0a0a0'
        border_color = '#404040'
    else:
        bg_color = '#f8f9fa'
        text_color = '#2c3e50'
        subtitle_color = '#6c757d'
        border_color = '#dee2e6'

    # Ícone baseado no grupo
    icon = '⚡' if 'Transversais' in grupo_nome else '🔌'

    fig = go.Figure()

    # Ícone grande
    fig.add_annotation(
        x=0.5,
        y=0.65,
        text=f"<span style='font-size:60px;'>{icon}</span>",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
    )

    # Título
    fig.add_annotation(
        x=0.5,
        y=0.45,
        text=f"<b>Demanda Temporal - {grupo_nome}</b>",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=16, color=text_color)
    )

    # Mensagem
    fig.add_annotation(
        x=0.5,
        y=0.32,
        text="Selecione o período nos filtros acima",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=13, color=subtitle_color)
    )

    # Submensagem
    fig.add_annotation(
        x=0.5,
        y=0.24,
        text="para visualizar a demanda em kW e kVA",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=13, color=subtitle_color)
    )

    fig.update_layout(
        template=template,
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[0, 1]
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[0, 1]
        ),
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        margin=dict(l=20, r=20, t=20, b=20),
        height=350,
        hovermode=False
    )

    return fig


def create_error_demand_figure(error_message, grupo_nome, template='minty'):
    """
    Cria figura de erro para o gráfico de demanda

    Args:
        error_message (str): Mensagem de erro a ser exibida
        grupo_nome (str): Nome do grupo (Transversais ou Longitudinais)
        template (str): Template do tema ('minty' ou 'darkly')

    Returns:
        plotly.graph_objects.Figure: Figura com mensagem de erro
    """
    # Define cores baseado no tema
    is_dark = (template == 'darkly')

    if is_dark:
        bg_color = '#2c2c2c'
        text_color = '#e0e0e0'
        error_color = '#ff6b6b'
        border_color = '#404040'
    else:
        bg_color = '#f8f9fa'
        text_color = '#2c3e50'
        error_color = '#e74c3c'
        border_color = '#dee2e6'

    fig = go.Figure()

    # Ícone de erro
    fig.add_annotation(
        x=0.5,
        y=0.65,
        text="<span style='font-size:60px;'>⚠️</span>",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
    )

    # Título
    fig.add_annotation(
        x=0.5,
        y=0.48,
        text=f"<b>Demanda {grupo_nome}</b>",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=16, color=text_color)
    )

    # Mensagem de erro
    fig.add_annotation(
        x=0.5,
        y=0.32,
        text=error_message,
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=13, color=error_color),
        bgcolor=border_color,
        borderpad=10,
        borderwidth=1,
        bordercolor=error_color,
        opacity=0.9
    )

    # Dica
    fig.add_annotation(
        x=0.5,
        y=0.18,
        text="Ajuste os filtros de período e tente novamente",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=11, color=text_color),
    )

    fig.update_layout(
        template=template,
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[0, 1]
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[0, 1]
        ),
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        margin=dict(l=20, r=20, t=20, b=20),
        height=350,
        hovermode=False
    )

    return fig


def create_demand_figure(timestamps, kw_values, kva_values, grupo_nome, template='minty'):
    """
    Cria gráfico de demanda com dados reais

    Args:
        timestamps (list): Lista de timestamps
        kw_values (list): Valores de demanda em kW
        kva_values (list): Valores de demanda aparente em kVA
        grupo_nome (str): Nome do grupo (Transversais ou Longitudinais)
        template (str): Template do tema ('minty' ou 'darkly')

    Returns:
        plotly.graph_objects.Figure: Figura com dados
    """
    fig = go.Figure()

    # Barras de kW
    fig.add_trace(go.Bar(
        x=timestamps,
        y=kw_values,
        name='Demanda (kW)',
        marker=dict(
            color='#2E86AB',
            line=dict(color='#1A5276', width=1)
        ),
        hovertemplate='<b>%{x}</b><br>Demanda: %{y:.2f} kW<extra></extra>'
    ))

    # Área transparente de kVA
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=kva_values,
        name='Demanda Aparente (kVA)',
        fill='tozeroy',
        fillcolor='rgba(247, 127, 0, 0.3)',
        line=dict(color='rgba(247, 127, 0, 0.8)', width=2),
        yaxis='y2',
        hovertemplate='<b>%{x}</b><br>Demanda Aparente: %{y:.2f} kVA<extra></extra>'
    ))

    # Layout
    fig.update_layout(
        template=template,
        title=dict(
            text=f"Demanda Temporal - {grupo_nome}",
            x=0.5,
            xanchor='center',
            font=dict(size=16)
        ),
        xaxis=dict(
            title="Data/Hora",
            showgrid=True,
            tickformat='%d/%m %H:%M'
        ),
        yaxis=dict(
            title="Demanda (kW)",
            side='left',
            showgrid=True,
            title_font=dict(color='#2E86AB'),
            tickfont=dict(color='#2E86AB'),
            rangemode='tozero'
        ),
        yaxis2=dict(
            title="Demanda Aparente (kVA)",
            side='right',
            overlaying='y',
            showgrid=False,
            title_font=dict(color='#F77F00'),
            tickfont=dict(color='#F77F00'),
            rangemode='tozero'
        ),
        hovermode='x unified',
        height=350,
        margin=dict(t=50, b=50, l=60, r=60),
        font=dict(size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        showlegend=True
    )

    return fig
