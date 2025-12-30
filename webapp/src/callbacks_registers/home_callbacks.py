# src/callbacks_registers/home_callbacks.py

from dash.dependencies import Input, Output
import plotly.graph_objects as go
from dash_bootstrap_templates import ThemeSwitchAIO
from src.config.theme_config import TEMPLATE_THEME_MINTY, TEMPLATE_THEME_DARKLY
import pandas as pd
from datetime import datetime, timedelta

def register_home_callbacks(app):
    """Callbacks para a página home"""
    
    @app.callback(
        Output("graph-home-oee", "figure"),
        Input(ThemeSwitchAIO.ids.switch("theme"), "value")
    )
    def update_home_oee_graph(toggle):
        """Gráfico de OEE simplificado para home"""
        if toggle is None:
            toggle = True
        template = TEMPLATE_THEME_MINTY if toggle else TEMPLATE_THEME_DARKLY
        
        # Dados mockados - substituir por dados reais
        hours = pd.date_range(end=datetime.now(), periods=24, freq='H')
        oee = [75 + (i % 10) * 2 for i in range(24)]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hours,
            y=oee,
            mode='lines',
            name='OEE',
            line=dict(color='#28a745', width=3),
            fill='tozeroy',
            fillcolor='rgba(40, 167, 69, 0.2)'
        ))
        
        fig.update_layout(
            template=template,
            margin=dict(l=40, r=20, t=20, b=40),
            xaxis_title="",
            yaxis_title="OEE (%)",
            showlegend=False,
            hovermode='x unified'
        )
        
        return fig
    
    @app.callback(
        Output("graph-home-energy", "figure"),
        Input(ThemeSwitchAIO.ids.switch("theme"), "value")
    )
    def update_home_energy_graph(toggle):
        """Gráfico de energia simplificado para home"""
        if toggle is None:
            toggle = True
        template = TEMPLATE_THEME_MINTY if toggle else TEMPLATE_THEME_DARKLY
        
        # Dados mockados - substituir por dados reais
        hours = pd.date_range(end=datetime.now(), periods=24, freq='H')
        consumption = [1000 + (i % 6) * 50 for i in range(24)]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=hours,
            y=consumption,
            name='Consumo',
            marker_color='#ffc107'
        ))
        
        fig.update_layout(
            template=template,
            margin=dict(l=40, r=20, t=20, b=40),
            xaxis_title="",
            yaxis_title="Consumo (kWh)",
            showlegend=False,
            hovermode='x unified'
        )
        
        return fig