# callbacks/msgtable_callback.py
from dash.dependencies import Input, Output, State # NOVO: Importar State
from dateutil.parser import parse
import pandas as pd
import plotly.express as px
import logging
import dash
from datetime import datetime, timedelta
from src.config.theme_config import TEMPLATE_THEME_MINTY
import time

from src.metrics import filtrar_dados_mongo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)
logger = logging.getLogger(__name__)


def register_msgtable_callbacks(app, collection_table):
    # Callback 1: fetch_table_data (este permanece EXATAMENTE como está)
    @app.callback(
            Output('stored-table-data', 'data'),
            [
            Input('interval-component', 'n_intervals'),
            Input('store-start-date', 'data'),
            Input('store-end-date', 'data'),
            Input('store-start-hour', 'data'),
            Input('store-end-hour', 'data'),
            Input('url', 'pathname')
        ]
    )
    def fetch_table_data(n_intervals, store_start_date, store_end_date, store_start_hour, store_end_hour, pathname):
        # Adiciona logs para rastreamento dos valores recebidos
        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        # Não executar este callback em páginas que têm seus próprios filtros/callbacks
        if pathname in ["/maintenance/indicators"]:
            raise dash.exceptions.PreventUpdate

        logger.info(f"Pathname atual: {pathname}")
        logger.info(f"Valores recebidos (Store): Start Date: {store_start_date}, End Date: {store_end_date}, Start Hour: {store_start_hour}, End Hour: {store_end_hour}")
        
        # Identificar se a condição está disparando
        if pathname == "/reports-print" and not all([store_start_date, store_end_date, store_start_hour, store_end_hour]):
            logger.info("Filtros estavam vazios em /reports-print. Aplicando valores padrão.")
            
            # Configura valores padrão
            end_datetime = datetime.now()
            start_datetime = end_datetime - timedelta(days=7)  # Default: últimos 7 dias
            store_start_date = start_datetime.strftime("%Y-%m-%d")
            store_end_date = end_datetime.strftime("%Y-%m-%d")
            store_start_hour = "00:00"
            store_end_hour = "23:59"
        
        elif not all([store_start_date, store_end_date, store_start_hour, store_end_hour]):
            # Log para rastrear se este `PreventUpdate` está sendo chamado
            logger.info("Filtros ainda vazios fora de /reports-print. Avoiding update.")
            raise dash.exceptions.PreventUpdate
        
        # Log de filtros validados antes de fazer a query para MongoDB
        logger.info(f"Realizando query com os valores: Start Date: {store_start_date}, End Date: {store_end_date}, Start Hour: {store_start_hour}, End Hour: {store_end_hour}")
        
        try:
            start_datetime = parse(f"{store_start_date} {store_start_hour}")
            end_datetime = parse(f"{store_end_date} {store_end_hour}")

            query = {"date_time": {"$gte": start_datetime, "$lte": end_datetime}}
            data = list(collection_table.find(query).sort("date_time", 1))

            if not data:
                logger.info("Nenhum dado encontrado para os filtros aplicados.")
                return {"error": "Sem dados disponíveis para o intervalo selecionado."}

            # Processa dados
            df = pd.DataFrame(data)
            df['date_time'] = pd.to_datetime(df['date_time']).dt.strftime('%d/%m/%Y %H:%M:%S')
            df['_id'] = df['_id'].astype(str)

            return df.to_dict('records')

        except Exception as e:
            logger.error(f"Erro ao consultar o MongoDB (tabela): {e}")
            return {"error": f"Erro: {str(e)}"}


    # Callback 2: update_table (ALTERAR ESTE BLOCO!)
    @app.callback(
        [
            # 1. Adicionar o Output para o estilo do container
            Output("messagestable-cards-layout", "style"),
            # 2. Manter os Outputs existentes da tabela
            Output("data-table", "data"),
            Output("data-table", "columns"),
            Output("data-table", "style_data"),
            Output("data-table", "style_header"),
            Output("data-table", "style_cell")
        ],
        [
            Input("stored-table-data", "data")
        ]
    )
    def update_table(stored_data):
        if toggle is None:
            toggle = True
        # Estilo para tornar o container visível
        visible_style = {"visibility": "visible", "min-height": "400px"}

        # ... (sua lógica de template e definição de estilos dark/light permanece a mesma) ...
        dark_theme_style_data = {"backgroundColor": "#2B2B2B", "color": "white", "border": "1px solid #444"}
        light_theme_style_data = {"backgroundColor": "white", "color": "black", "border": "1px solid #ddd"}
        dark_theme_style_header = {"backgroundColor": "#1A1A1A", "color": "white", "fontWeight": "bold", "textAlign": "center", "border": "1px solid #444"}
        light_theme_style_header = {"backgroundColor": "lightgrey", "color": "black", "fontWeight": "bold", "textAlign": "center", "border": "1px solid #ddd"}
        dark_theme_style_cell = {'backgroundColor': '#2B2B2B', 'color': 'white', 'textAlign': 'left', 'padding': '8px', 'whiteSpace': 'normal', 'height': 'auto', 'lineHeight': '15px', 'overflow': 'hidden', 'textOverflow': 'ellipsis', 'background-color': 'transparent !important'}
        light_theme_style_cell = {'backgroundColor': 'white', 'color': 'black', 'textAlign': 'left', 'padding': '8px', 'whiteSpace': 'normal', 'height': 'auto', 'lineHeight': '15px', 'overflow': 'hidden', 'textOverflow': 'ellipsis', 'background-color': 'transparent !important'}

        style_data = light_theme_style_data if toggle else dark_theme_style_data
        style_header = light_theme_style_header if toggle else dark_theme_style_header
        style_cell = light_theme_style_cell if toggle else dark_theme_style_cell

        # Adicionando um pequeno delay para garantir que o loading apareça
        time.sleep(0.5)

        if not stored_data or "error" in stored_data:
            # 3. Retornar o estilo visível mesmo em caso de erro
            return visible_style, [], [{"name": "Info", "id": "Info"}], style_data, style_header, style_cell

        df = pd.DataFrame(stored_data)

        expected_columns = ['qualMaquinaDesc', 'categoriaFalhaDesc', 'descricaoFalhaDesc', 'date_time']
        if not set(expected_columns).issubset(df.columns):
            # 3. Retornar o estilo visível mesmo em caso de erro
            return visible_style, [], [{"name": "Erro de Coluna", "id": "Erro"}], style_data, style_header, style_cell

        df = df.sort_values(by="date_time", ascending=False) # Geralmente o mais recente vem primeiro

        columns_to_display = ['qualMaquinaDesc', 'categoriaFalhaDesc', 'descricaoFalhaDesc', 'date_time']
        column_headers = {
            'qualMaquinaDesc': 'Máquina',
            'categoriaFalhaDesc': 'Categoria',
            'descricaoFalhaDesc': 'Descrição',
            'date_time': 'Data e Hora',
        }

        # 4. Retornar o estilo como o primeiro valor
        return (
            visible_style,
            df[columns_to_display].to_dict("records"),
            [{"name": column_headers[col], "id": col} for col in columns_to_display],
            style_data,
            style_header,
            style_cell
        )
    # --- FIM DA MODIFICAÇÃO ---