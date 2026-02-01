# callbacks/states_callbacks.py
from dash.dependencies import Input, Output, State
import pandas as pd
import plotly.graph_objects as go
from src.config.theme_config import TEMPLATE_THEME_MINTY
import dash
from dash import dcc
import logging
import time

logger = logging.getLogger(__name__)

def register_states_callbacks(app, collection_graph):

        # CALLBACK 1: ATUALIZAR GRÁFICO E COR DO BOTÃO
        # CALLBACK 1: ATUALIZAR GRÁFICO E COR DO BOTÃO
    @app.callback(
        [
            Output('oee-occupancy-card-graph', 'style'),
            Output('oee-occupancy-graph', 'figure'),
            Output('btn-export-states', 'color')
        ],
        [
            Input('stored-graph-data', 'data')
        ]
    )
    def update_states_graph_and_theme(stored_data):
        # --- LÓGICA DEFENSIVA E PADRONIZADA ---
        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        button_color = "primary"
        # --- FIM DA LÓGICA ---

        visible_style = {"visibility": "visible", "height": "400px"}
        fig = go.Figure()
        fig.update_layout(template=template, title="Processando dados...")
        time.sleep(0.5)

        if not stored_data or "error" in stored_data:
            error_message = stored_data.get("error", "Dados não disponíveis.")
            fig.update_layout(title=error_message)
            return visible_style, fig, button_color

        df = pd.DataFrame(stored_data)
        if 'DateTime' not in df.columns or 'OEE' not in df.columns:
            fig.update_layout(title="Erro: Dados inválidos (colunas ausentes).")
            return visible_style, fig, button_color

        colors = {'good': 'green', 'average': 'yellow', 'bad': 'red'}
        bar_colors = []
        for oee_value in df['OEE']:
            if oee_value >= 0.80:
                bar_colors.append(colors['good'])
            elif 0.50 <= oee_value < 0.80:
                bar_colors.append(colors['average'])
            else:
                bar_colors.append(colors['bad'])
        
        df['altura_fixa'] = 1
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['DateTime'],
            y=df['altura_fixa'],
            marker_color=bar_colors,
            marker_line_width=0,
            customdata=df['OEE'],
            # --- CORREÇÃO DE SINTAXE DEFINITIVA ---
            hovertemplate="""<b>Data</b>: %{x}  
<b>OEE</b>: %{customdata:.2f}%<extra></extra>"""
        ))
        fig.update_layout(
            title='Linha do Tempo de Status de Performance (OEE)',
            xaxis_title='Data e Hora',
            yaxis_title=None,
            yaxis=dict(showticklabels=False, range=[0, 1]),
            xaxis=dict(tickfont=dict(size=8), nticks=20),
            margin=dict(l=20, r=20, t=40, b=40),
            showlegend=False,
            template=template,
            bargap=0
        )
        
        return visible_style, fig, button_color



    # CALLBACK 2: EXPORTAR DADOS DE STATUS PARA EXCEL
    @app.callback(
        Output("download-states-excel", "data"),
        Input("btn-export-states", "n_clicks"),
        State("stored-graph-data", "data"),
        prevent_initial_call=True
    )
    def export_states_data_to_excel(n_clicks, stored_data):
        if not stored_data or "error" in stored_data:
            raise dash.exceptions.PreventUpdate

        df_to_export = pd.DataFrame(stored_data)
        
        if '_id' in df_to_export.columns:
            df_to_export = df_to_export.drop(columns=['_id'])

        return dcc.send_data_frame(
            df_to_export.to_excel, "dados_status_oee.xlsx", sheet_name="Dados", index=False
        )

