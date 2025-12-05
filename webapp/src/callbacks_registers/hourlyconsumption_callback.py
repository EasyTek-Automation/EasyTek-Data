# callbacks_registers/energygraph_callback.py

from dash.dependencies import Input, Output, State
from dateutil.parser import parse
import pandas as pd
import plotly.express as px
import logging
import dash
from dash_bootstrap_templates import ThemeSwitchAIO
from src.config.theme_config import TEMPLATE_THEME_MINTY, TEMPLATE_THEME_DARKLY
from dash import dcc
import os
import traceback
import time
from datetime import datetime

# --------------------------------------------------------------------------------
# LOGGING CONFIG
# Nível padrão DEBUG (ajustável via env LOG_LEVEL=INFO/DEBUG/WARNING/ERROR)
# Formato com timestamp e nome do logger para facilitar grep em múltiplos workers
# --------------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.DEBUG),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
    force=True,  # força reconfigurar se já houver config do gunicorn
)
logger = logging.getLogger("energygraph")

def _mongo_meta_info(collection):
    """Coleta metadados do Mongo com robustez (não quebra se algo não existir)."""
    meta = {}
    try:
        meta["db_name"] = getattr(collection.database, "name", None)
        meta["collection_name"] = getattr(collection, "name", None)
        # Nós do cluster/standalone (set é mais seguro que address único)
        try:
            meta["nodes"] = list(getattr(collection.database.client, "nodes", []))
        except Exception:
            meta["nodes"] = []
        # Teste de ping
        try:
            collection.database.client.admin.command("ping")
            meta["ping"] = "ok"
        except Exception as e:
            meta["ping"] = f"fail: {e}"
        # Índices
        try:
            meta["indexes"] = list(collection.list_indexes())
            meta["indexes_str"] = [str(ix) for ix in meta["indexes"]]
        except Exception as e:
            meta["indexes_error"] = str(e)
    except Exception as e:
        meta["meta_error"] = str(e)
    return meta

def _safe_sample_doc(collection, query):
    """Retorna 1 doc para amostra, sem quebrar em erro."""
    try:
        doc = collection.find_one(query)
        if doc:
            # Evita imprimir valores muito grandes: só keys + tipos
            brief = {k: type(v).__name__ for k, v in doc.items()}
            return {"sample_types": brief, "has_doc": True}
        return {"has_doc": False}
    except Exception as e:
        return {"sample_error": str(e), "has_doc": False}

def _count_docs(collection, query):
    """Usa count_documents (preciso) com proteção de erro."""
    try:
        return collection.count_documents(query)
    except Exception as e:
        logger.warning(f"[COUNT] Falha ao contar documentos: {e}")
        return None

def _duration_ms(start):
    return round((time.perf_counter() - start) * 1000.0, 1)

def register_hourlyconsumption_callbacks(app, collection_consumo):
    # Loga metadados da coleção no registro do callback
    meta = _mongo_meta_info(collection_consumo)
    logger.info(
        f"[INIT] EnergyGraph ligado em Mongo: "
        f"db={meta.get('db_name')} col={meta.get('collection_name')} "
        f"nodes={meta.get('nodes')} ping={meta.get('ping')}"
    )
    if "indexes_str" in meta:
        logger.info(f"[INIT] Indexes: {meta['indexes_str']}")
    elif "indexes_error" in meta:
        logger.warning(f"[INIT] Falha ao listar índices: {meta['indexes_error']}")

    # 1) CALLBACK PARA BUSCAR DADOS DE ENERGIA
    @app.callback(
        Output("stored-hourly-consumption-data", "data"),
        [
            Input("interval-component", "n_intervals"),
            Input("store-start-date", "data"),
            Input("store-end-date", "data"),
            Input("store-start-hour", "data"),
            Input("store-end-hour", "data"),
        ],
    )
    def fetch_energy_data(n_intervals, start_date, end_date, start_hour, end_hour):
        t0 = time.perf_counter()
        logger.debug(
            f"[FETCH] Trigger interval={n_intervals} "
            f"start_date={start_date} end_date={end_date} "
            f"start_hour={start_hour} end_hour={end_hour}"
        )

        if not all([start_date, end_date, start_hour, end_hour]):
            logger.debug("[FETCH] Params incompletos -> PreventUpdate")
            raise dash.exceptions.PreventUpdate

        try:
            # Parse datas
            t_parse = time.perf_counter()
            start_datetime = parse(f"{start_date} {start_hour}")
            end_datetime = parse(f"{end_date} {end_hour}")
            logger.debug(
                f"[FETCH] Parsed datetime ok: start={start_datetime} end={end_datetime} "
                f"(parse_ms={_duration_ms(t_parse)})"
            )

            # Validação janela
            if end_datetime < start_datetime:
                logger.warning(
                    f"[FETCH] Janela invertida: end < start (start={start_datetime}, end={end_datetime})"
                )
                return {
                    "error": f"Janela inválida: fim < início (início={start_datetime}, fim={end_datetime})."
                }

            # Monta query
            query = {"DateTime": {"$gte": start_datetime, "$lte": end_datetime}}
            logger.info(f"[FETCH] Query montada: {query}")

            # Contagem precisa (rápida para diagnóstico)
            t_count = time.perf_counter()
            doc_count = _count_docs(collection_consumo, query)
            logger.info(
                f"[FETCH] count_documents={doc_count} (count_ms={_duration_ms(t_count)})"
            )

            # Amostra de um doc (para diagnosticar schema)
            sample = _safe_sample_doc(collection_consumo, query)
            logger.debug(f"[FETCH] Sample: {sample}")

            # Busca paginada total (para o gráfico)
            t_find = time.perf_counter()
            cursor = collection_consumo.find(query).sort("DateTime", 1)
            data = list(cursor)
            logger.info(
                f"[FETCH] fetch_len={len(data)} (find_ms={_duration_ms(t_find)}) "
                f"(total_ms={_duration_ms(t0)})"
            )

            if not data:
                logger.warning("[FETCH] Nenhum dado encontrado para o período.")
                return {
                    "error": "Sem dados de energia para o período.",
                    "diagnostic": {
                        "query": str(query),
                        "doc_count": doc_count,
                        "sample": sample,
                        "env": {
                            "DB_NAME": os.getenv("DB_NAME"),
                            "COLLECTION_NAME": os.getenv("COLLECTION_NAME"),
                            "MONGO_URI": os.getenv("MONGO_URI"),
                        },
                    },
                }
        ####
                  # DataFrame + agregação por hora
            t_df = time.perf_counter()
            df = pd.DataFrame(data)

            # Log de colunas e tipos (primeiras 5)
            head_cols = list(df.columns)
            logger.debug(f"[FETCH] DF columns: {head_cols}")
            if not df.empty:
                logger.debug(
                    f"[FETCH] DF head dtypes: {df.dtypes.astype(str).to_dict()}"
                )

            # --- 1) Garantir que DateTime exista ---
            if "DateTime" not in df.columns:
                logger.error("[FETCH] Coluna DateTime não encontrada em AMG_Consumo.")
                return {"error": "Dados inválidos: coluna DateTime ausente em AMG_Consumo."}

            # Converte DateTime para datetime (sem formatar para string ainda)
            df["DateTime"] = pd.to_datetime(df["DateTime"])

            # --- 2) Garantir que a coluna de CONSUMO exista e seja numérica ---
            # TROQUE "kwh_intervalo" PELO NOME EXATO DA SUA COLUNA DE DELTA
            if "kwh_intervalo" not in df.columns:
                logger.error("[FETCH] Coluna kwh_intervalo não encontrada em AMG_Consumo.")
                return {
                    "error": "Dados inválidos: coluna de consumo (delta) não encontrada em AMG_Consumo."
                }

            df["kwh_intervalo"] = pd.to_numeric(df["kwh_intervalo"], errors="coerce")
            df = df.dropna(subset=["kwh_intervalo"])

            if df.empty:
                logger.warning("[FETCH] Nenhuma linha válida de consumo após limpeza.")
                return {"error": "Sem dados de consumo válidos para o período."}

            # --- 3) Criar coluna 'Hora' truncada para a hora cheia ---
            # Ex.: 2025-12-05 14:23:10 -> 2025-12-05 14:00:00
            df["Hora"] = df["DateTime"].dt.floor("H")

            # --- 4) Agregar por hora: soma do consumo no intervalo daquela hora ---
            df_hourly = (
                df.groupby("Hora", as_index=False)["kwh_intervalo"]
                  .sum()
                  .rename(columns={"kwh_intervalo": "ConsumoHora_kWh"})
            )

            if df_hourly.empty:
                logger.warning("[FETCH] df_hourly vazio após groupby.")
                return {"error": "Sem dados de consumo agregados para o período."}

            # --- 5) Criar coluna string para exibir no eixo X do gráfico ---
            df_hourly["HoraStr"] = df_hourly["Hora"].dt.strftime("%Y-%m-%d %H:%M")

            logger.debug(
                f"[FETCH] DF hourly pronto (linhas={len(df_hourly)}) (df_ms={_duration_ms(t_df)})"
            )

            # Retorna só o que o gráfico precisa
            return df_hourly.to_dict("records")

        
        ####

        except Exception as e:
            logger.error(
                f"[FETCH][EXC] Erro ao consultar o MongoDB (energia): {e}\n{traceback.format_exc()}"
            )
            return {"error": f"Erro ao consultar dados: {e}"}

    # 2) CALLBACK PARA ATUALIZAR O GRÁFICO
        # 2) CALLBACK PARA ATUALIZAR O GRÁFICO DE CONSUMO POR HORA
    @app.callback(
        [
            Output("hourly-consumption-graph", "figure"),
            Output("hourly-consumption-graph", "style"),
        ],
        [
            Input("stored-hourly-consumption-data", "data"),
            Input("url", "pathname"),
        ],
        [
            Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
        ],
    )
    def update_hourly_consumption_graph(stored_data, pathname, toggle):
        t0 = time.perf_counter()

        if toggle is None:
            toggle = True
        template = TEMPLATE_THEME_MINTY if toggle else TEMPLATE_THEME_DARKLY

        visible_style = {"visibility": "visible", "height": "450px"}
        error_style = {"visibility": "visible", "height": "450px"}

        logger.debug(
            f"[GRAPH_HOURLY] Update pathname={pathname} toggle={toggle} "
            f"has_data={bool(stored_data and 'error' not in stored_data)}"
        )

        # --- 1) Sem dados ou erro ---
        if (not stored_data) or (isinstance(stored_data, dict) and "error" in stored_data):
            msg = (
                stored_data.get("error", "Sem dados de consumo para o período.")
                if isinstance(stored_data, dict)
                else "Sem dados de consumo para o período."
            )
            logger.warning(f"[GRAPH_HOURLY] Sem dados ou erro no stored_data: {msg}")
            error_fig = px.bar(title=msg)
            error_fig.update_layout(template=template)
            return error_fig, error_style

        # --- 2) Converter para DataFrame ---
        try:
            df = pd.DataFrame(stored_data)
        except Exception as e:
            logger.error(f"[GRAPH_HOURLY][EXC] Falha ao criar DataFrame: {e}")
            error_fig = px.bar(title="Erro: Dados inválidos para gráfico de consumo.")
            error_fig.update_layout(template=template)
            return error_fig, error_style

        # --- 3) Conferir colunas obrigatórias ---
        required_cols = ["HoraStr", "ConsumoHora_kWh"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.error(f"[GRAPH_HOURLY] Colunas faltantes: {missing} | cols={list(df.columns)}")
            error_fig = px.bar(
                title=f"Erro: Dados inválidos (faltam colunas: {missing})."
            )
            error_fig.update_layout(template=template)
            return error_fig, error_style

        if df.empty:
            logger.warning("[GRAPH_HOURLY] DataFrame vazio.")
            error_fig = px.bar(title="Sem dados de consumo para exibir.")
            error_fig.update_layout(template=template)
            return error_fig, error_style

        # --- 4) Criar o gráfico de barras ---
        try:
            fig = px.bar(
                df,
                x="HoraStr",
                y="ConsumoHora_kWh",
                title="Consumo por Hora",
            )
            fig.update_layout(
                xaxis_title="Hora",
                yaxis_title="Consumo (kWh)",
                template=template,
                margin=dict(l=40, r=10, t=40, b=40),
                xaxis=dict(tickfont=dict(size=10), nticks=24),
                yaxis=dict(tickfont=dict(size=10)),
            )

            logger.debug(
                f"[GRAPH_HOURLY] Figura gerada ok (ms={_duration_ms(t0)}), rows={len(df)}"
            )
            return fig, visible_style

        except Exception as e:
            logger.error(f"[GRAPH_HOURLY][EXC] Falha ao renderizar gráfico: {e}")
            error_fig = px.bar(title="Erro ao renderizar gráfico de consumo por hora.")
            error_fig.update_layout(template=template)
            return error_fig, error_style
