# callbacks_registers/tempgraph_callback.py

from dash.dependencies import Input, Output
from dateutil.parser import parse
import pandas as pd
import plotly.express as px
import logging
import dash
from dash_bootstrap_templates import ThemeSwitchAIO
from src.config.theme_config import TEMPLATE_THEME_MINTY, TEMPLATE_THEME_DARKLY
from dash.dependencies import Input, Output, State # Adicione State
from dash import dcc # Adicione dcc para usar dcc.send_data_frame


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
logger = logging.getLogger(__name__)

def register_tempgraph_callbacks(app, collection_temp):
    
    # 1. CALLBACK PARA BUSCAR DADOS DE temperatura
    # Ele usa os mesmos gatilhos (filtros de data) do outro gráfico
    @app.callback(
        Output('stored-temp-data', 'data'), # <-- NOVO Output para o novo Store
        [
            Input('interval-component', 'n_intervals'),
            Input('store-start-date', 'data'),
            Input('store-end-date', 'data'),
            Input('store-start-hour', 'data'),
            Input('store-end-hour', 'data'),
        ]
    )
    def fetch_temp_data(n_intervals, start_date, end_date, start_hour, end_hour):
        if not all([start_date, end_date, start_hour, end_hour]):
            raise dash.exceptions.PreventUpdate

        try:
            start_datetime = parse(f"{start_date} {start_hour}")
            end_datetime = parse(f"{end_date} {end_hour}")

            query = {"DateTime": {"$gte": start_datetime, "$lte": end_datetime}}
            # Busca na coleção específica de temperatura
            data = list(collection_temp.find(query).sort("DateTime", 1))

            if not data:
                return {"error": "Sem dados de temperatura para o período."}

            df = pd.DataFrame(data)
            df['DateTime'] = pd.to_datetime(df['DateTime']).dt.strftime('%Y-%m-%d %H:%M:%S')
            df['_id'] = df['_id'].astype(str)

            return df.to_dict('records')

        except Exception as e:
            logger.error(f"Erro ao consultar o MongoDB (temperatura): {e}")
            return {"error": f"Erro: {str(e)}"}

    # 2. CALLBACK PARA ATUALIZAR O GRÁFICO
    # Ele lê os dados do seu próprio Store: 'stored-temp-data'
    @app.callback(
        [Output('temp-graph', 'figure'),
         Output('temp-graph', 'style')],
        [Input('stored-temp-data', 'data'), # <-- Lê do seu próprio Store
         Input('url', 'pathname')],
        [Input(ThemeSwitchAIO.ids.switch("theme"), "value")]
    )
    def update_temp_graph(stored_data, pathname, toggle):
        if toggle is None:
            toggle = True
        template = TEMPLATE_THEME_MINTY if toggle else TEMPLATE_THEME_DARKLY

        visible_style = {'visibility': 'visible', 'height': '450px'}
        error_style = {'visibility': 'visible', 'height': '450px'}

        if not stored_data or "error" in stored_data:
            error_fig = px.line(title=stored_data.get("error", "Sem dados para o período."))
            error_fig.update_layout(template=template)
            return error_fig, error_style

        df = pd.DataFrame(stored_data)

        # Verifica se as colunas de temperatura existem
        required_cols = ['DateTime', 'TempR', 'TempS', 'TempT', 'TempKW']
        if not all(col in df.columns for col in required_cols):
            invalid_data_fig = px.line(title="Erro: Dados de temperatura inválidos.")
            invalid_data_fig.update_layout(template=template)
            return invalid_data_fig, error_style

        # Cria o gráfico de temperatura
        fig = px.line(
            df,
            x='DateTime',
            y=['TempR', 'TempS', 'TempT', 'TempKW'],
            title='Monitoramento de temperatura',
        )
        
        fig.update_layout(
            xaxis_title="Data e Hora",
            yaxis_title="Valor",
            template=template,
            margin=dict(l=40, r=10, t=40, b=40),
            xaxis=dict(tickfont=dict(size=8), nticks=10),
            yaxis=dict(tickfont=dict(size=8)),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9))
        )
        
        return fig, visible_style
    @app.callback(
        Output("download-temp-excel", "data"), # Saída: o componente de download
        Input("btn-export-temp", "n_clicks"),  # Gatilho: clique no botão
        State("stored-temp-data", "data"),     # Entrada de Estado: pega os dados atuais do gráfico
        prevent_initial_call=True # Impede que o callback rode quando o app inicia
    )
    def export_temp_data_to_excel(n_clicks, stored_data):
        # Se não houver dados ou o botão não foi clicado, não faz nada
        if not stored_data or "error" in stored_data:
            raise dash.exceptions.PreventUpdate

        # Converte os dados do Store de volta para um DataFrame
        df_to_export = pd.DataFrame(stored_data)

        # Limpa colunas que não são úteis no Excel, como o _id do MongoDB
        if '_id' in df_to_export.columns:
            df_to_export = df_to_export.drop(columns=['_id'])

        # Usa uma função do Dash para converter o DataFrame para um arquivo Excel em memória
        # e enviá-lo para o componente dcc.Download.
        # O nome do arquivo é definido aqui.
        return dcc.send_data_frame(
            df_to_export.to_excel, "dados_temperatura.xlsx", sheet_name="Dados", index=False
        )

