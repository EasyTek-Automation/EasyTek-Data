# callbacks/oeegraph_callback.py
from dash.dependencies import Input, Output, State
from dateutil.parser import parse
import pandas as pd
import plotly.express as px
import logging
import dash
from dash import dcc # Importar dcc para send_data_frame
from src.config.theme_config import TEMPLATE_THEME_MINTY

# A importação de 'time' e 'filtrar_dados_mongo' não são usadas aqui, podem ser removidas se não forem necessárias em outro lugar.
# import time
# from src.metrics import filtrar_dados_mongo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)
logger = logging.getLogger(__name__)

def register_oeegraph_callbacks(app, collection_graph):
    
    # CALLBACK 1: BUSCAR DADOS (sem alterações)
    @app.callback(
        Output('stored-graph-data', 'data'),
        [
            Input('interval-component', 'n_intervals'),
            Input('store-start-date', 'data'),
            Input('store-end-date', 'data'),
            Input('store-start-hour', 'data'),
            Input('store-end-hour', 'data'),
        ]
    )
    def fetch_graph_data(n_intervals, start_date, end_date, start_hour, end_hour):
        if not all([start_date, end_date, start_hour, end_hour]):
            raise dash.exceptions.PreventUpdate
        try:
            start_datetime = parse(f"{start_date} {start_hour}")
            end_datetime = parse(f"{end_date} {end_hour}")
            query = {"DateTime": {"$gte": start_datetime, "$lte": end_datetime}}
            data = list(collection_graph.find(query).sort("DateTime", 1))
            if not data:
                return {"error": "Sem dados disponíveis para o intervalo selecionado."}
            df = pd.DataFrame(data)
            df['DateTime'] = pd.to_datetime(df['DateTime']).dt.strftime('%Y-%m-%d %H:%M:%S')
            df['_id'] = df['_id'].astype(str)
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Erro ao consultar o MongoDB (gráfico): {e}")
            return {"error": f"Erro: {str(e)}"}

    # CALLBACK 2: ATUALIZAR GRÁFICO E COR DO BOTÃO (versão corrigida e padronizada)
    @app.callback(
        [
            Output('oee-graph', 'figure'),
            Output('oee-graph', 'style'),
            Output('btn-export-oee', 'color')
        ],
        [
            Input('stored-graph-data', 'data'),
            Input('url', 'pathname')
        ]
    )
    def update_oee_graph_and_theme(stored_data, pathname):
        # --- LÓGICA DEFENSIVA E PADRONIZADA ---
        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        button_color = "primary"
        # --- FIM DA LÓGICA ---

        visible_style = {'visibility': 'visible', 'height': '450px'}
        error_style = {'visibility': 'visible', 'height': '450px'}

        if not stored_data or "error" in stored_data:
            error_fig = px.line(title=stored_data.get("error", "Sem dados para o período."))
            error_fig.update_layout(template=template)
            return error_fig, error_style, button_color

        df = pd.DataFrame(stored_data)
        if 'DateTime' not in df.columns:
            invalid_data_fig = px.line(title="Erro: Dados inválidos para gráfico.")
            invalid_data_fig.update_layout(template=template)
            return invalid_data_fig, error_style, button_color

        fig = px.line(
            df,
            x='DateTime',
            y=['OEE', 'Desemp', 'Quali', 'Disp'],
            title='Indicadores ao Longo do Tempo',
        )
        
        fig.update_layout(
            xaxis_title="Data e Hora",
            yaxis_title="Indicadores (%)",
            template=template,
            margin=dict(l=40, r=10, t=40, b=40),
            xaxis=dict(tickfont=dict(size=8), nticks=10),
            yaxis=dict(tickfont=dict(size=8)),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9))
        )
        
        return fig, visible_style, button_color


    # CALLBACK 3: EXPORTAR DADOS PARA EXCEL (sem alterações)
    @app.callback(
        Output("download-oee-excel", "data"),
        Input("btn-export-oee", "n_clicks"),
        State("stored-graph-data", "data"),
        prevent_initial_call=True
    )
    def export_oee_data_to_excel(n_clicks, stored_data):
        if not stored_data or "error" in stored_data:
            raise dash.exceptions.PreventUpdate

        df_to_export = pd.DataFrame(stored_data)
        
        if '_id' in df_to_export.columns:
            df_to_export = df_to_export.drop(columns=['_id'])

        return dcc.send_data_frame(
            df_to_export.to_excel, "dados_oee.xlsx", sheet_name="Dados", index=False
        )
