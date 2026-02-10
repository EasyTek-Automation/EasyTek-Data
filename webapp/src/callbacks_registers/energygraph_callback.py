# callbacks_registers/energygraph_callback.py

from dash.dependencies import Input, Output, State
from dateutil.parser import parse
import pandas as pd
import plotly.express as px
import logging
import dash
from src.config.theme_config import TEMPLATE_THEME_MINTY
from dash import dcc
from src.utils.empty_state import create_empty_state_figure, create_error_state_figure
import os
import traceback
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ_SP = ZoneInfo("America/Sao_Paulo")
TZ_UTC = timezone.utc

# ========== FUNÇÕES AUXILIARES (mantidas do original) ========== #

def sp_range_to_utc_naive(start_date, start_hour, end_date, end_hour):
    start_sp = parse(f"{start_date} {start_hour}").replace(tzinfo=TZ_SP)
    end_sp   = parse(f"{end_date} {end_hour}").replace(tzinfo=TZ_SP)
    start_utc_naive = start_sp.astimezone(TZ_UTC).replace(tzinfo=None)
    end_utc_naive   = end_sp.astimezone(TZ_UTC).replace(tzinfo=None)
    return start_utc_naive, end_utc_naive

def series_utc_to_sp_str(s: pd.Series, fmt="%Y-%m-%d %H:%M:%S"):
    dt_utc = pd.to_datetime(s, utc=True)
    dt_sp  = dt_utc.dt.tz_convert("America/Sao_Paulo")
    return dt_sp.dt.strftime(fmt)

def series_utc_to_sp_naive(s: pd.Series):
    dt_utc = pd.to_datetime(s, utc=True)
    dt_sp  = dt_utc.dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
    return dt_sp

logger = logging.getLogger("energygraph")

def _mongo_meta_info(collection):
    meta = {}
    try:
        meta["db_name"] = getattr(collection.database, "name", None)
        meta["collection_name"] = getattr(collection, "name", None)
        try:
            meta["nodes"] = list(getattr(collection.database.client, "nodes", []))
        except Exception:
            meta["nodes"] = []
        try:
            collection.database.client.admin.command("ping")
            meta["ping"] = "ok"
        except Exception as e:
            meta["ping"] = f"fail: {e}"
        try:
            meta["indexes"] = list(collection.list_indexes())
            meta["indexes_str"] = [str(ix) for ix in meta["indexes"]]
        except Exception as e:
            meta["indexes_error"] = str(e)
    except Exception as e:
        meta["meta_error"] = str(e)
    return meta

def _safe_sample_doc(collection, query):
    try:
        doc = collection.find_one(query)
        if doc:
            brief = {k: type(v).__name__ for k, v in doc.items()}
            return {"sample_types": brief, "has_doc": True}
        return {"has_doc": False}
    except Exception as e:
        return {"sample_error": str(e), "has_doc": False}

def _count_docs(collection, query):
    try:
        return collection.count_documents(query)
    except Exception as e:
        logger.warning(f"[COUNT] Falha ao contar documentos: {e}")
        return None

def _duration_ms(start):
    return round((time.perf_counter() - start) * 1000.0, 1)


# ========== REGISTRO DOS CALLBACKS ========== #

def register_energygraph_callbacks(app, collection_energia):
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

    # ========== CALLBACK PARA BUSCAR DADOS DE ENERGIA (UNIFICADO) ========== #
    @app.callback(
        Output("stored-energy-data", "data"),
        [
            Input("interval-component", "n_intervals"),
            Input("store-start-date", "data"),
            Input("store-end-date", "data"),
            Input("store-start-hour", "data"),
            Input("store-end-hour", "data"),
            Input("machine-dropdown-group1", "value"),
            Input("machine-dropdown-group2", "value"),
        ],
    )
    def fetch_energy_data(n_intervals, start_date, end_date, start_hour, end_hour, group1, group2):
        t0 = time.perf_counter()
        logger.debug(
            f"[FETCH] interval={n_intervals} start={start_date} {start_hour} end={end_date} {end_hour} "
            f"group1={group1} group2={group2}"
        )

        if not all([start_date, end_date, start_hour, end_hour]):
            logger.debug("[FETCH] Params incompletos -> PreventUpdate")
            raise dash.exceptions.PreventUpdate

        # Garante que são listas
        group1 = group1 or []
        group2 = group2 or []

        # Une os dois grupos e remove duplicatas
        selected_machines = list(set(group1 + group2))

        if not selected_machines:
            logger.warning("[FETCH] Nenhum equipamento selecionado em nenhum grupo.")
            return {
                "error": "Selecione pelo menos um equipamento para carregar os dados.",
                "machine_count": 0
            }

        logger.info(f"[FETCH] Equipamentos selecionados (unificados): {selected_machines}")

        try:
            # Parse datas
            t_parse = time.perf_counter()
            start_sp = parse(f"{start_date} {start_hour}").replace(tzinfo=TZ_SP)
            end_sp   = parse(f"{end_date} {end_hour}").replace(tzinfo=TZ_SP)
            start_datetime = start_sp.astimezone(TZ_UTC).replace(tzinfo=None)
            end_datetime   = end_sp.astimezone(TZ_UTC).replace(tzinfo=None)

            logger.debug(
                f"[FETCH] Parsed datetime ok: start={start_datetime} end={end_datetime} "
                f"(parse_ms={_duration_ms(t_parse)})"
            )

            if end_datetime < start_datetime:
                logger.warning(f"[FETCH] Janela invertida")
                return {"error": "Janela inválida: fim < início."}

            # Monta query com $in para múltiplos equipamentos
            query = {
                "DateTime": {"$gte": start_datetime, "$lte": end_datetime},
                "IDMaq": {"$in": selected_machines}
            }

            logger.info(f"[FETCH] Query montada: {query}")

            # Contagem
            t_count = time.perf_counter()
            doc_count = _count_docs(collection_energia, query)
            logger.info(f"[FETCH] count_documents={doc_count} (count_ms={_duration_ms(t_count)})")

            # Amostra
            sample = _safe_sample_doc(collection_energia, query)
            logger.debug(f"[FETCH] Sample: {sample}")

            # Busca
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
                    "machine_count": len(selected_machines),
                    "diagnostic": {
                        "query": str(query),
                        "doc_count": doc_count,
                        "sample": sample,
                    },
                }

            # DataFrame
            t_df = time.perf_counter()
            df = pd.DataFrame(data)

            logger.debug(f"[FETCH] DF columns: {list(df.columns)}")

            # Conversão DateTime
            if "DateTime" in df.columns:
                dt_utc = pd.to_datetime(df["DateTime"], utc=True, errors="coerce")
                df = df.loc[~dt_utc.isna()].copy()
                df["DateTime"] = (
                    dt_utc.loc[~dt_utc.isna()]
                        .dt.tz_convert("America/Sao_Paulo")
                        .dt.strftime("%Y-%m-%d %H:%M:%S")
                )

            if "_id" in df.columns:
                df["_id"] = df["_id"].astype(str)

            logger.debug(f"[FETCH] DF preparado (df_ms={_duration_ms(t_df)})")
            
            # Retorna com metadados
            return {
                "data": df.to_dict("records"),
                "machine_count": len(selected_machines),
                "machines": selected_machines
            }

        except Exception as e:
            logger.error(f"[FETCH][EXC] Erro: {e}\n{traceback.format_exc()}")
            return {"error": f"Erro ao consultar dados: {e}"}

    # ========== CALLBACK PARA ATUALIZAR GRÁFICO DE TENSÃO ========== #
    @app.callback(
        [Output("energy-graph", "figure"), Output("energy-graph", "style")],
        [Input("stored-energy-data", "data"), Input("url", "pathname")],
    )
    def update_energy_graph(stored_data, pathname):
        t0 = time.perf_counter()
        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        visible_style = {"visibility": "visible", "height": "450px"}
        error_style = {"visibility": "visible", "height": "450px"}

        logger.debug(f"[GRAPH] Update pathname={pathname} toggle={toggle}")

        # Verifica erro
        if not stored_data or (isinstance(stored_data, dict) and "error" in stored_data):
            if isinstance(stored_data, dict) and stored_data.get("error"):
                error_msg = stored_data.get("error", "")
                if "Selecione pelo menos um equipamento" in error_msg:
                    # Empty state
                    logger.info("[GRAPH] Empty state: nenhum equipamento selecionado")
                    empty_fig = create_empty_state_figure('voltage', template)
                    return empty_fig, visible_style
                else:
                    # Erro real
                    logger.warning(f"[GRAPH] Erro: {error_msg}")
                    error_fig = create_error_state_figure(error_msg, template)
                    return error_fig, error_style
            
            # Fallback
            logger.warning("[GRAPH] Sem dados")
            empty_fig = create_empty_state_figure('voltage', template)
            return empty_fig, visible_style

        # Extrai dados
        data_records = stored_data.get("data", []) if isinstance(stored_data, dict) else stored_data
        machine_count = stored_data.get("machine_count", 0) if isinstance(stored_data, dict) else 0

        try:
            df = pd.DataFrame(data_records)
        except Exception as e:
            logger.error(f"[GRAPH][EXC] Falha ao criar DataFrame: {e}")
            error_fig = create_error_state_figure("Dados inválidos", template)
            return error_fig, error_style

        # Verifica colunas
        required_cols = ["DateTime", "TensaoL1", "TensaoL2", "TensaoL3"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.error(f"[GRAPH] Colunas faltantes: {missing}")
            error_fig = create_error_state_figure(f"Faltam colunas: {', '.join(missing)}", template)
            return error_fig, error_style
        
        df_tensao = df.dropna(subset=["TensaoL1", "TensaoL2", "TensaoL3"])

        if df_tensao.empty:
            logger.warning("[GRAPH] Nenhum dado de tensão após filtragem.")
            empty_fig = create_empty_state_figure('voltage', template)
            return empty_fig, visible_style

        # Cria gráfico
        try:
            # Se houver coluna IDMaq, usa como color para diferenciar equipamentos
            if "IDMaq" in df_tensao.columns:
                # Cria DataFrame "long format" para plotly diferenciar por equipamento E fase
                df_melted = df_tensao.melt(
                    id_vars=["DateTime", "IDMaq"],
                    value_vars=["TensaoL1", "TensaoL2", "TensaoL3"],
                    var_name="Fase",
                    value_name="Tensao"
                )
                # Cria uma coluna combinada "Equipamento - Fase" para a legenda
                df_melted["Legenda"] = df_melted["IDMaq"] + " - " + df_melted["Fase"]
                
                fig = px.line(
                    df_melted,
                    x="DateTime",
                    y="Tensao",
                    color="Legenda",
                    title=f"Monitoramento de Tensão - SE03 ({machine_count} equipamento{'s' if machine_count > 1 else ''})",
                )
            else:
                # Fallback: sem IDMaq, só mostra as 3 fases
                fig = px.line(
                    df_tensao,
                    x="DateTime",
                    y=["TensaoL1", "TensaoL2", "TensaoL3"],
                    title=f"Monitoramento de Tensão - SE03 ({machine_count} equipamento{'s' if machine_count > 1 else ''})",
                )

            fig.update_layout(
                xaxis_title="Data e Hora",
                yaxis_title="Tensão (V)",
                template=template,
                margin=dict(l=40, r=10, t=50, b=40),
                xaxis=dict(tickfont=dict(size=10)),
                yaxis=dict(tickfont=dict(size=10)),
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02,
                    font=dict(size=9),
                    title="Equipamento/Fase"
                ),
            )
            logger.debug(f"[GRAPH] Figura de tensão gerada (ms={_duration_ms(t0)}), rows={len(df_tensao)}")
            return fig, visible_style

        except Exception as e:
            logger.error(f"[GRAPH][EXC] Falha ao renderizar: {e}")
            error_fig = create_error_state_figure("Erro ao renderizar gráfico de tensão", template)
            return error_fig, error_style

    # ========== CALLBACK PARA ATUALIZAR GRÁFICO DE CORRENTE ========== #
    @app.callback(
        [Output("current-graph", "figure"), Output("current-graph", "style")],
        [Input("stored-energy-data", "data"), Input("url", "pathname")],
    )
    def update_current_graph(stored_data, pathname):
        t0 = time.perf_counter()
        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        visible_style = {"visibility": "visible", "height": "450px"}
        error_style = {"visibility": "visible", "height": "450px"}

        logger.debug(f"[GRAPH_CURRENT] Update triggered")

        # Verifica erro
        if not stored_data or (isinstance(stored_data, dict) and "error" in stored_data):
            if isinstance(stored_data, dict) and stored_data.get("error"):
                error_msg = stored_data.get("error", "")
                if "Selecione pelo menos um equipamento" in error_msg:
                    # Empty state
                    logger.info("[GRAPH_CURRENT] Empty state: nenhum equipamento selecionado")
                    empty_fig = create_empty_state_figure('current', template)
                    return empty_fig, visible_style
                else:
                    # Erro real
                    logger.warning(f"[GRAPH_CURRENT] Erro: {error_msg}")
                    error_fig = create_error_state_figure(error_msg, template)
                    return error_fig, error_style
            
            # Fallback
            logger.warning("[GRAPH_CURRENT] Sem dados")
            empty_fig = create_empty_state_figure('current', template)
            return empty_fig, visible_style

        # Extrai dados
        data_records = stored_data.get("data", []) if isinstance(stored_data, dict) else stored_data
        machine_count = stored_data.get("machine_count", 0) if isinstance(stored_data, dict) else 0

        try:
            df = pd.DataFrame(data_records)
        except Exception as e:
            logger.error(f"[GRAPH_CURRENT][EXC] Falha ao criar DataFrame: {e}")
            error_fig = create_error_state_figure("Dados inválidos", template)
            return error_fig, error_style

        # Verifica colunas
        required_cols = ["DateTime", "CorrenteL1", "CorrenteL2", "CorrenteL3"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.error(f"[GRAPH_CURRENT] Colunas faltantes: {missing}")
            error_fig = create_error_state_figure(f"Faltam colunas: {', '.join(missing)}", template)
            return error_fig, error_style

        df_corrente = df.dropna(subset=["CorrenteL1", "CorrenteL2", "CorrenteL3"])

        if df_corrente.empty:
            logger.warning("[GRAPH_CURRENT] Nenhum dado de corrente após filtragem.")
            empty_fig = create_empty_state_figure('current', template)
            return empty_fig, visible_style

        # Cria gráfico
        try:
            # Se houver coluna IDMaq, usa como color para diferenciar equipamentos
            if "IDMaq" in df_corrente.columns:
                # Cria DataFrame "long format"
                df_melted = df_corrente.melt(
                    id_vars=["DateTime", "IDMaq"],
                    value_vars=["CorrenteL1", "CorrenteL2", "CorrenteL3"],
                    var_name="Fase",
                    value_name="Corrente"
                )
                df_melted["Legenda"] = df_melted["IDMaq"] + " - " + df_melted["Fase"]
                
                fig = px.line(
                    df_melted,
                    x="DateTime",
                    y="Corrente",
                    color="Legenda",
                    title=f"Monitoramento de Corrente - SE03 ({machine_count} equipamento{'s' if machine_count > 1 else ''})",
                )
            else:
                # Fallback
                fig = px.line(
                    df_corrente,
                    x="DateTime",
                    y=["CorrenteL1", "CorrenteL2", "CorrenteL3"],
                    title=f"Monitoramento de Corrente - SE03 ({machine_count} equipamento{'s' if machine_count > 1 else ''})",
                )

            fig.update_layout(
                xaxis_title="Data e Hora",
                yaxis_title="Corrente (A)",
                template=template,
                margin=dict(l=40, r=10, t=50, b=40),
                xaxis=dict(tickfont=dict(size=10)),
                yaxis=dict(tickfont=dict(size=10)),
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02,
                    font=dict(size=9),
                    title="Equipamento/Fase"
                ),
            )
            logger.debug(f"[GRAPH_CURRENT] Figura de corrente gerada (ms={_duration_ms(t0)}), rows={len(df_corrente)}")
            return fig, visible_style

        except Exception as e:
            logger.error(f"[GRAPH_CURRENT][EXC] Falha ao renderizar: {e}")
            error_fig = create_error_state_figure("Erro ao renderizar gráfico de corrente", template)
            return error_fig, error_style

    # ========== CALLBACK PARA EXPORTAR EXCEL ========== #
    @app.callback(
        Output("download-energy-excel", "data"),
        Input("btn-export-energy", "n_clicks"),
        State("stored-energy-data", "data"),
        prevent_initial_call=True,
    )
    def export_energy_data_to_excel(n_clicks, stored_data):
        logger.debug(f"[EXPORT] n_clicks={n_clicks}")
        
        if not stored_data or "error" in stored_data:
            logger.warning("[EXPORT] Sem dados -> PreventUpdate")
            raise dash.exceptions.PreventUpdate

        data_records = stored_data.get("data", []) if isinstance(stored_data, dict) else stored_data
        if not data_records:
            logger.warning("[EXPORT] data_records vazio -> PreventUpdate")
            raise dash.exceptions.PreventUpdate

        try:
            df_to_export = pd.DataFrame(data_records)
            if "_id" in df_to_export.columns:
                df_to_export = df_to_export.drop(columns=["_id"])
            
            logger.info(f"[EXPORT] Exportando {len(df_to_export)} linhas")
            return dcc.send_data_frame(
                df_to_export.to_excel,
                "dados_energia_tensao_corrente.xlsx",
                sheet_name="Dados",
                index=False
            )
        except Exception as e:
            logger.error(f"[EXPORT][EXC] Falha: {e}")
            raise dash.exceptions.PreventUpdate