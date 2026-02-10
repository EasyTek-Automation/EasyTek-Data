# callbacks/kpicards_callback.py
from dash.dependencies import Input, Output, State
from dateutil.parser import parse
import pandas as pd
import plotly.express as px
import logging
import dash
import time # Importe o time para simular o carregamento

from src.metrics import filtrar_dados_mongo
from src.metrics import calcular_metricas

logger = logging.getLogger(__name__)

def register_kpicards_callbacks(app, collection_graph):
    @app.callback(
        [
            # --- INÍCIO DA MODIFICAÇÃO ---
            # 1. Adicione o Output para o estilo do container principal
            Output("kpi-main-card", "style"),
            # 2. Mantenha os Outputs existentes
            Output("card-media-oee", "children"),
            Output("card-media-disp", "children"),
            Output("card-media-desemp", "children"),
            Output("card-media-quali", "children"),
        ],
        [
            Input("store-start-date", "data"),
            Input("store-end-date", "data"),
            Input("store-start-hour", "data"),
            Input("store-end-hour", "data"),
            Input('interval-component', 'n_intervals'),
            Input('url', 'pathname')
        ]
    )
    def atualizar_metricas(start_date, end_date, start_hour, end_hour, n_intervals, pathname):
        # Estilo para tornar o container visível
        visible_style = {"visibility": "visible", "min-height": "250px"}
        
        # Placeholder para os valores enquanto não há dados
        placeholder = "..."

        if not all([start_date, end_date, start_hour, end_hour]):
            # Mesmo que não atualize, precisamos retornar um valor para cada Output
            raise dash.exceptions.PreventUpdate

        logger.info(f"Iniciando atualização de métricas para cards (intervalo {n_intervals}) para {pathname}")
        try:
            start_datetime = parse(f"{start_date} {start_hour}")
            end_datetime = parse(f"{end_date} {end_hour}")
            logger.info(f"Métricas: Intervalo de datetime: {start_datetime} a {end_datetime}")

            df = filtrar_dados_mongo(collection_graph, start_datetime, end_datetime)
            
            # Adicionando um pequeno delay para garantir que o loading apareça em requisições rápidas
            time.sleep(0.5)

            if df.empty:
                logger.warning("Nenhum dado encontrado para o período. Exibindo 'N/A'.")
                return visible_style, "N/A", "N/A", "N/A", "N/A"

            metricas = calcular_metricas(df)

            oee_val = f"{metricas['media_oee']:.2f}%" if not pd.isna(metricas['media_oee']) else "N/A"
            disp_val = f"{metricas['media_disp']:.2f}%" if not pd.isna(metricas['media_disp']) else "N/A"
            desemp_val = f"{metricas['media_desemp']:.2f}%" if not pd.isna(metricas['media_desemp']) else "N/A"
            quali_val = f"{metricas['media_quali']:.2f}%" if not pd.isna(metricas['media_quali']) else "N/A"

            logger.info("Métricas atualizadas com sucesso para os cards.")
            # 3. Retorne o estilo como o primeiro valor
            return visible_style, oee_val, disp_val, desemp_val, quali_val

        except Exception as e:
            logger.error(f"Erro geral ao atualizar as métricas dos cards: {e}")
            # 4. Retorne o estilo visível também em caso de erro para mostrar a mensagem
            return visible_style, "Erro", "Erro", "Erro", "Erro"
    # --- FIM DA MODIFICAÇÃO ---
