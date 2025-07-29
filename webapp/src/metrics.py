# metrics.py
import pandas as pd
from datetime import datetime
from pymongo.collection import Collection
import logging

logger = logging.getLogger(__name__)

def calcular_metricas(df: pd.DataFrame):
    """
    Função para calcular métricas a partir de um DataFrame de dados de performance.
    Calcula as médias de OEE, Disponibilidade, Desempenho e Qualidade.
    """
    if df.empty:
        logger.warning("DataFrame vazio passado para calcular_metricas. Retornando 0 para todas as métricas.")
        return {
            "media_oee": 0,
            "media_disp": 0,
            "media_desemp": 0,
            "media_quali": 0,
        }

    # Validação de colunas essenciais
    required_cols = ['OEE', 'Disp', 'Desemp', 'Quali']
    if not all(col in df.columns for col in required_cols):
        logger.error(f"Colunas esperadas {required_cols} não encontradas no DataFrame. Colunas disponíveis: {df.columns.tolist()}")
        return {
            "media_oee": float('nan'), # Not a Number
            "media_disp": float('nan'),
            "media_desemp": float('nan'),
            "media_quali": float('nan'),
        }

    # Cálculos de médias, ignorando NaNs
    media_oee = df["OEE"].mean()
    media_disp = df["Disp"].mean()
    media_desemp = df["Desemp"].mean()
    media_quali = df["Quali"].mean()

    logger.info(f"Métricas calculadas: OEE={media_oee:.2f}, Disp={media_disp:.2f}, Desemp={media_desemp:.2f}, Quali={media_quali:.2f}")

    return {
        "media_oee": media_oee,
        "media_disp": media_disp,
        "media_desemp": media_desemp,
        "media_quali": media_quali,
    }

def filtrar_dados_mongo(collection: Collection, start_datetime: datetime, end_datetime: datetime):
    """
    Consulta dados do MongoDB filtrados por intervalo de tempo.
    Retorna um DataFrame pandas.
    """
    query = {
        "DateTime": {"$gte": start_datetime, "$lte": end_datetime}
    }
    logger.info(f"Consultando MongoDB para data_time entre {start_datetime} e {end_datetime}")
    try:
        data = list(collection.find(query))
        if not data:
            logger.info("Nenhum dado encontrado para a consulta.")
            return pd.DataFrame() # Retorna um DataFrame vazio se não houver dados
        
        df = pd.DataFrame(data)
        logger.info(f"Consulta MongoDB retornou {len(df)} registros.")
        return df
    except Exception as e:
        logger.error(f"Erro ao consultar MongoDB em filtrar_dados_mongo: {e}")
        return pd.DataFrame() # Retorna um DataFrame vazio em caso de erro