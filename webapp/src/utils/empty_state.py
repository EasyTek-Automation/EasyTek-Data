# utils/empty_state.py
"""
Componente reutilizável para exibir placeholders visuais 
quando não há dados selecionados nos gráficos.
"""

import plotly.graph_objects as go
from src.config.theme_config import TEMPLATE_THEME_MINTY, TEMPLATE_THEME_DARKLY


def create_empty_state_figure(graph_type, template):
    """
    Cria uma figura Plotly com placeholder visual para estado vazio.
    
    Args:
        graph_type (str): Tipo do gráfico ('consumption', 'voltage', 'current')
        template (str): Template do tema (TEMPLATE_THEME_MINTY ou TEMPLATE_THEME_DARKLY)
    
    Returns:
        go.Figure: Figura Plotly com o placeholder
    """
    
    # Configurações por tipo de gráfico
    configs = {
        'consumption': {
            'icon': '📊',
            'title': 'Aguardando Seleção de Equipamentos',
            'message': 'Selecione equipamentos nos grupos',
            'submessage': 'para visualizar a comparação de consumo',
            'color': '#1f77b4'
        },
        'voltage': {
            'icon': '⚡',
            'title': 'Aguardando Seleção de Equipamentos',
            'message': 'Selecione equipamentos para monitorar',
            'submessage': 'a tensão em tempo real',
            'color': '#ff7f0e'
        },
        'current': {
            'icon': '🔌',
            'title': 'Aguardando Seleção de Equipamentos',
            'message': 'Selecione equipamentos para monitorar',
            'submessage': 'a corrente em tempo real',
            'color': '#2ca02c'
        }
    }
    
    config = configs.get(graph_type, configs['consumption'])
    
    # Define cores baseado no tema
    is_dark = (template == TEMPLATE_THEME_DARKLY)
    
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
    
    # Cria figura vazia
    fig = go.Figure()
    
    # Adiciona anotação com o ícone (grande)
    fig.add_annotation(
        x=0.5,
        y=0.65,
        text=f"<span style='font-size:80px;'>{config['icon']}</span>",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
    )
    
    # Adiciona título
    fig.add_annotation(
        x=0.5,
        y=0.45,
        text=f"<b>{config['title']}</b>",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=18, color=text_color)
    )
    
    # Adiciona mensagem principal
    fig.add_annotation(
        x=0.5,
        y=0.35,
        text=config['message'],
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=14, color=subtitle_color)
    )
    
    # Adiciona submensagem
    fig.add_annotation(
        x=0.5,
        y=0.28,
        text=config['submessage'],
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=14, color=subtitle_color)
    )
    
    # Adiciona dica visual (seta)
    fig.add_annotation(
        x=0.5,
        y=0.18,
        text="↓ Use os dropdowns na barra lateral",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=12, color=subtitle_color, family="monospace"),
        bgcolor=border_color,
        borderpad=8,
        borderwidth=1,
        bordercolor=border_color,
        opacity=0.8
    )
    
    # Layout da figura
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
        height=450,
        hovermode=False
    )
    
    return fig


def create_error_state_figure(error_message, template):
    """
    Cria uma figura Plotly para exibir mensagens de erro de forma amigável.
    
    Args:
        error_message (str): Mensagem de erro a ser exibida
        template (str): Template do tema
    
    Returns:
        go.Figure: Figura Plotly com a mensagem de erro
    """
    
    # Define cores baseado no tema
    is_dark = (template == TEMPLATE_THEME_DARKLY)
    
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
        text="<span style='font-size:80px;'>⚠️</span>",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
    )
    
    # Título de erro
    fig.add_annotation(
        x=0.5,
        y=0.45,
        text="<b>Ops! Algo deu errado</b>",
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=18, color=error_color)
    )
    
    # Mensagem de erro (truncada se muito longa)
    truncated_message = error_message[:100] + "..." if len(error_message) > 100 else error_message
    
    fig.add_annotation(
        x=0.5,
        y=0.32,
        text=truncated_message,
        showarrow=False,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        font=dict(size=12, color=text_color),
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
        text="Verifique os filtros e tente novamente",
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
        height=450,
        hovermode=False
    )
    
    return fig