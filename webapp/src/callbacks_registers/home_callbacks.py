# src/callbacks_registers/home_callbacks.py

from dash.dependencies import Input, Output
import plotly.graph_objects as go
from dash_bootstrap_templates import ThemeSwitchAIO
from src.config.theme_config import TEMPLATE_THEME_MINTY, TEMPLATE_THEME_DARKLY
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("home_callbacks")

def register_home_callbacks(app):
    """Callbacks para a página home"""
    
    # ========================================
    # CALLBACK: Gráfico OEE 24h
    # ========================================
    @app.callback(
        [
            Output("graph-home-oee", "figure"),
            Output("graph-home-oee", "style")
        ],
        [
            Input("interval-component", "n_intervals"),
            Input(ThemeSwitchAIO.ids.switch("theme"), "value")
        ]
    )
    def update_home_oee_graph(n_intervals, toggle):
        """
        Gráfico de OEE simplificado para home.
        Retorna figura E style para evitar flash branco.
        """
        if toggle is None:
            toggle = True
        template = TEMPLATE_THEME_MINTY if toggle else TEMPLATE_THEME_DARKLY
        
        # Style visível (gráfico pronto)
        visible_style = {"visibility": "visible", "height": "250px"}
        
        try:
            # ========================================
            # DADOS MOCKADOS (SUBSTITUIR POR DADOS REAIS)
            # ========================================
            # TODO: Buscar dados reais do banco
            hours = pd.date_range(end=datetime.now(), periods=24, freq='H')
            oee_values = [75 + (i % 10) * 2 for i in range(24)]
            
            # ========================================
            # CRIA FIGURA
            # ========================================
            fig = go.Figure()
            
            # Linha de OEE
            fig.add_trace(go.Scatter(
                x=hours,
                y=oee_values,
                mode='lines',
                name='OEE',
                line=dict(color='#28a745', width=3),
                fill='tozeroy',
                fillcolor='rgba(40, 167, 69, 0.2)',
                hovertemplate='<b>%{x|%d/%m %H:%M}</b><br>OEE: %{y:.1f}%<extra></extra>'
            ))
            
            # Linha de meta (85%)
            fig.add_hline(
                y=85, 
                line_dash="dash", 
                line_color="red", 
                opacity=0.5,
                annotation_text="Meta: 85%",
                annotation_position="right"
            )
            
            # Layout
            fig.update_layout(
                template=template,
                margin=dict(l=40, r=20, t=20, b=40),
                xaxis_title="",
                yaxis_title="OEE (%)",
                showlegend=False,
                hovermode='x unified',
                yaxis=dict(range=[0, 100]),  # OEE sempre 0-100%
            )
            
            logger.debug(f"[HOME_OEE] Gráfico gerado com {len(hours)} pontos")
            return fig, visible_style
            
        except Exception as e:
            logger.error(f"[HOME_OEE] Erro ao gerar gráfico: {e}")
            
            # Figura de erro
            error_fig = go.Figure()
            error_fig.add_annotation(
                text=f"Erro ao carregar dados<br>{str(e)}",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14, color="red")
            )
            error_fig.update_layout(
                template=template,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                margin=dict(l=0, r=0, t=0, b=0)
            )
            
            return error_fig, visible_style
    
    # =======================================
    # CALLBACK: Gráfico Energia
    # =======================================
    @app.callback(
        [
            Output("graph-home-energy", "figure"),
            Output("graph-home-energy", "style")
        ],
        [
            Input("interval-component", "n_intervals"),
            Input(ThemeSwitchAIO.ids.switch("theme"), "value")
        ]
    )
    def update_home_energy_graph(n_intervals, toggle):
        """
        Gráfico de energia simplificado para home.
        Retorna figura E style para evitar flash branco.
        """
        if toggle is None:
            toggle = True
        template = TEMPLATE_THEME_MINTY if toggle else TEMPLATE_THEME_DARKLY
        
        # Style visível (gráfico pronto)
        visible_style = {"visibility": "visible", "height": "250px"}
        
        try:
            # ========================================
            # DADOS MOCKADOS (SUBSTITUIR POR DADOS REAIS)
            # ========================================
            # TODO: Buscar dados reais do banco
            hours = pd.date_range(end=datetime.now(), periods=24, freq='H')
            consumption = [1000 + (i % 6) * 50 for i in range(24)]
            
            # ========================================
            # CRIA FIGURA
            # ========================================
            fig = go.Figure()
            
            # Barras de consumo
            fig.add_trace(go.Bar(
                x=hours,
                y=consumption,
                name='Consumo',
                marker_color='#ffc107',
                hovertemplate='<b>%{x|%d/%m %H:%M}</b><br>Consumo: %{y:.0f} kWh<extra></extra>'
            ))
            
            # Linha de média
            avg_consumption = sum(consumption) / len(consumption)
            fig.add_hline(
                y=avg_consumption,
                line_dash="dash",
                line_color="orange",
                opacity=0.5,
                annotation_text=f"Média: {avg_consumption:.0f} kWh",
                annotation_position="right"
            )
            
            # Layout
            fig.update_layout(
                template=template,
                margin=dict(l=40, r=20, t=20, b=40),
                xaxis_title="",
                yaxis_title="Consumo (kWh)",
                showlegend=False,
                hovermode='x unified',
                bargap=0.2,
            )
            
            logger.debug(f"[HOME_ENERGY] Gráfico gerado com {len(hours)} pontos")
            return fig, visible_style
            
        except Exception as e:
            logger.error(f"[HOME_ENERGY] Erro ao gerar gráfico: {e}")
            
            # Figura de erro
            error_fig = go.Figure()
            error_fig.add_annotation(
                text=f"Erro ao carregar dados<br>{str(e)}",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14, color="red")
            )
            error_fig.update_layout(
                template=template,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                margin=dict(l=0, r=0, t=0, b=0)
            )
            
            return error_fig, visible_style
    
    # ========================================
    # CALLBACK: Atualizar valores dos cards
    # ========================================
    @app.callback(
        [
            Output("home-oee-value", "children"),
            Output("home-power-value", "children"),
            Output("home-alarms-count", "children"),
            Output("home-temp-value", "children"),
        ],
        Input("interval-component", "n_intervals")
    )
    def update_home_cards(n_intervals):
        """
        Atualiza valores dos cards de status.
        TODO: Buscar dados reais do banco.
        """
        # Dados mockados - substituir por dados reais
        oee = "85.2%"
        power = "1.245 kW"
        alarms = "3"
        temp = "72.5°C"
        
        return oee, power, alarms, temp