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

def register_energygraph_callbacks(app, collection_energia):
    # Loga metadados da coleção no registro do callback
    meta = _mongo_meta_info(collection_energia)
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
        Output("stored-energy-data", "data"),
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
            doc_count = _count_docs(collection_energia, query)
            logger.info(
                f"[FETCH] count_documents={doc_count} (count_ms={_duration_ms(t_count)})"
            )

            # Amostra de um doc (para diagnosticar schema)
            sample = _safe_sample_doc(collection_energia, query)
            logger.debug(f"[FETCH] Sample: {sample}")

            # Busca paginada total (para o gráfico)
            t_find = time.perf_counter()
            cursor = collection_energia.find(query).sort("DateTime", 1)
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

            # DataFrame + normalização
            t_df = time.perf_counter()
            df = pd.DataFrame(data)

            # Log de colunas e tipos (primeiras 5)
            head_cols = list(df.columns)
            logger.debug(f"[FETCH] DF columns: {head_cols}")
            if not df.empty:
                logger.debug(
                    f"[FETCH] DF head dtypes: {df.dtypes.astype(str).to_dict()}"
                )

            # Conversão de campos
            if "DateTime" in df.columns:
                df["DateTime"] = pd.to_datetime(df["DateTime"]).dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            if "_id" in df.columns:
                df["_id"] = df["_id"].astype(str)

            logger.debug(f"[FETCH] DF preparado (df_ms={_duration_ms(t_df)})")
            return df.to_dict("records")

        except Exception as e:
            logger.error(
                f"[FETCH][EXC] Erro ao consultar o MongoDB (energia): {e}\n{traceback.format_exc()}"
            )
            return {"error": f"Erro ao consultar dados: {e}"}

    # 2) CALLBACK PARA ATUALIZAR O GRÁFICO
    @app.callback(
        [Output("energy-graph", "figure"), Output("energy-graph", "style")],
        [Input("stored-energy-data", "data"), Input("url", "pathname")],
        [Input(ThemeSwitchAIO.ids.switch("theme"), "value")],
    )
    def update_energy_graph(stored_data, pathname, toggle):
        t0 = time.perf_counter()
        if toggle is None:
            toggle = True
        template = TEMPLATE_THEME_MINTY if toggle else TEMPLATE_THEME_DARKLY

        visible_style = {"visibility": "visible", "height": "450px"}
        error_style = {"visibility": "visible", "height": "450px"}

        logger.debug(
            f"[GRAPH] Update pathname={pathname} toggle={toggle} "
            f"has_data={bool(stored_data and 'error' not in stored_data)}"
        )

        if not stored_data or "error" in stored_data:
            msg = stored_data.get("error", "Sem dados para o período.") if isinstance(
                stored_data, dict
            ) else "Sem dados para o período."
            logger.warning(f"[GRAPH] Sem dados ou erro no stored_data: {msg}")
            # Se houver diagnóstico, loga também
            if isinstance(stored_data, dict) and "diagnostic" in stored_data:
                logger.warning(f"[GRAPH][DIAG] {stored_data['diagnostic']}")
            error_fig = px.line(title=msg)
            error_fig.update_layout(template=template)
            return error_fig, error_style

        # Converte para DF
        try:
            df = pd.DataFrame(stored_data)
        except Exception as e:
            logger.error(f"[GRAPH][EXC] Falha ao criar DataFrame: {e}")
            invalid_data_fig = px.line(title="Erro: Dados inválidos (DF).")
            invalid_data_fig.update_layout(template=template)
            return invalid_data_fig, error_style

        # Verifica colunas necessárias
        required_cols = ["DateTime", "TensaoL1", "TensaoL2", "TensaoL3"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.error(f"[GRAPH] Colunas faltantes: {missing} | cols={list(df.columns)}")
            invalid_data_fig = px.line(
                title=f"Erro: Dados de energia inválidos (faltam colunas: {missing})."
            )
            invalid_data_fig.update_layout(template=template)
            return invalid_data_fig, error_style

        # Gráfico
        try:
            fig = px.line(
                df,
                x="DateTime",
                y=["TensaoL1", "TensaoL2", "TensaoL3"],
                title="Monitoramento de Energia",
            )
            fig.update_layout(
                xaxis_title="Data e Hora",
                yaxis_title="Valor",
                template=template,
                margin=dict(l=40, r=10, t=40, b=40),
                xaxis=dict(tickfont=dict(size=20), nticks=20),
                yaxis=dict(tickfont=dict(size=20)),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    font=dict(size=9),
                ),
            )
            logger.debug(
                f"[GRAPH] Figura gerada ok (ms={_duration_ms(t0)}), rows={len(df)}"
            )
            return fig, visible_style
        except Exception as e:
            logger.error(f"[GRAPH][EXC] Falha ao renderizar gráfico: {e}")
            invalid_data_fig = px.line(title="Erro ao renderizar gráfico.")
            invalid_data_fig.update_layout(template=template)
            return invalid_data_fig, error_style

    # 3) CALLBACK PARA EXPORTAR EXCEL
    @app.callback(
        Output("download-energy-excel", "data"),
        Input("btn-export-energy", "n_clicks"),
        State("stored-energy-data", "data"),
        prevent_initial_call=True,
    )
    def export_energy_data_to_excel(n_clicks, stored_data):
        logger.debug(
            f"[EXPORT] n_clicks={n_clicks} has_data={bool(stored_data and 'error' not in stored_data)}"
        )
        if not stored_data or "error" in stored_data:
            logger.warning("[EXPORT] Sem dados para exportação -> PreventUpdate")
            raise dash.exceptions.PreventUpdate

        try:
            df_to_export = pd.DataFrame(stored_data)
            if "_id" in df_to_export.columns:
                df_to_export = df_to_export.drop(columns=["_id"])
            logger.info(f"[EXPORT] Exportando {len(df_to_export)} linhas para Excel")
            return dcc.send_data_frame(
                df_to_export.to_excel, "dados_energia.xlsx", sheet_name="Dados", index=False
            )
        except Exception as e:
            logger.error(f"[EXPORT][EXC] Falha ao exportar Excel: {e}")
            raise dash.exceptions.PreventUpdate
