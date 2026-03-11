# callbacks_registers/hourlyconsumption_callback.py

from dash.dependencies import Input, Output, State
from dateutil.parser import parse
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

logger = logging.getLogger("consumptiongraph")

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

def register_hourlyconsumption_callbacks(app, collection_consumo):
    meta = _mongo_meta_info(collection_consumo)
    logger.info(
        f"[INIT] consumptionGraph ligado em Mongo: "
        f"db={meta.get('db_name')} col={meta.get('collection_name')} "
        f"nodes={meta.get('nodes')} ping={meta.get('ping')}"
    )
    if "indexes_str" in meta:
        logger.info(f"[INIT] Indexes: {meta['indexes_str']}")
    elif "indexes_error" in meta:
        logger.warning(f"[INIT] Falha ao listar índices: {meta['indexes_error']}")

    # ========== CALLBACK DE VALIDAÇÃO (interrupção de duplicatas) ========== #
    @app.callback(
        Output("validation-message", "children"),
        Output("validation-message", "style"),
        Input("machine-dropdown-group1", "value"),
        Input("machine-dropdown-group2", "value"),
    )
    def validate_machine_selection(group1, group2):
        base_style = {
            "margin-top": "10px",
            "padding": "8px",
            "border-radius": "4px",
            "font-size": "0.85rem"
        }

        # Garante que são listas
        group1 = group1 or []
        group2 = group2 or []

        # Verifica duplicatas
        duplicates = set(group1) & set(group2)
        if duplicates:
            dup_str = ", ".join(duplicates)
            return (
                f"⚠️ Equipamentos duplicados: {dup_str}",
                {**base_style, "background-color": "#fff3cd", "color": "#856404", "border": "1px solid #ffc107", "display": "block"}
            )

        # Verifica se ambos estão vazios
        if not group1 and not group2:
            return (
                "ℹ️ Selecione pelo menos um equipamento em um dos grupos",
                {**base_style, "background-color": "#d1ecf1", "color": "#0c5460", "border": "1px solid #bee5eb", "display": "block"}
            )

        # Tudo OK
        return "", {**base_style, "display": "none"}

    # ========== CALLBACK PARA BUSCAR DADOS DE ENERGIA (2 GRUPOS) ========== #
    @app.callback(
        Output("stored-hourly-consumption-data", "data"),
        Input("btn-apply-energy-filters", "n_clicks"),
        [
            State("store-start-date", "data"),
            State("store-end-date", "data"),
            State("store-start-hour", "data"),
            State("store-end-hour", "data"),
            State("machine-dropdown-group1", "value"),
            State("machine-dropdown-group2", "value"),
        ],
        prevent_initial_call=False,
    )
    def fetch_consumption_data(n_clicks, start_date, end_date, start_hour, end_hour, group1, group2):
        t0 = time.perf_counter()
        logger.debug(
            f"[FETCH] n_clicks={n_clicks} start={start_date} {start_hour} end={end_date} {end_hour} "
            f"group1={group1} group2={group2}"
        )

        if not all([start_date, end_date, start_hour, end_hour]):
            logger.debug("[FETCH] Params incompletos -> PreventUpdate")
            raise dash.exceptions.PreventUpdate

        # Garante que são listas
        group1 = group1 or []
        group2 = group2 or []

        # Validação: pelo menos 1 grupo deve ter seleção
        if not group1 and not group2:
            logger.warning("[FETCH] Nenhum equipamento selecionado em nenhum grupo.")
            return {"error": "Selecione pelo menos um equipamento em um dos grupos."}

        # Validação: não pode haver duplicatas
        duplicates = set(group1) & set(group2)
        if duplicates:
            logger.warning(f"[FETCH] Equipamentos duplicados detectados: {duplicates}")
            return {"error": f"Equipamentos duplicados nos grupos: {', '.join(duplicates)}"}

        try:
            # Parse de datas
            t_parse = time.perf_counter()
            start_sp = parse(f"{start_date} {start_hour}").replace(tzinfo=TZ_SP)
            end_sp   = parse(f"{end_date} {end_hour}").replace(tzinfo=TZ_SP)
            start_datetime = start_sp.astimezone(TZ_UTC).replace(tzinfo=None)
            end_datetime   = end_sp.astimezone(TZ_UTC).replace(tzinfo=None)

            logger.debug(f"[FETCH] Parsed: start={start_datetime} end={end_datetime} (parse_ms={_duration_ms(t_parse)})")

            if end_datetime < start_datetime:
                logger.warning(f"[FETCH] Janela invertida")
                return {"error": "Janela inválida: fim < início."}

            # Query base (range de tempo)
            base_query = {"DateTime": {"$gte": start_datetime, "$lte": end_datetime}}

            # ========== PROCESSAR Transversais ========== #
            df_grupo1 = None
            if group1:
                query1 = {**base_query, "IDMaq": {"$in": group1}}
                logger.info(f"[FETCH] Query Transversais: {query1}")
                
                t_find1 = time.perf_counter()
                cursor1 = collection_consumo.find(query1).sort("DateTime", 1)
                data1 = list(cursor1)
                logger.info(f"[FETCH] Transversais: {len(data1)} docs (find_ms={_duration_ms(t_find1)})")

                if data1:
                    df1 = pd.DataFrame(data1)
                    
                    if "DateTime" not in df1.columns or "kwh_intervalo" not in df1.columns:
                        logger.error("[FETCH] Colunas necessárias ausentes no Transversais")
                        return {"error": "Dados inválidos: colunas ausentes"}

                    df1["DateTime"] = pd.to_datetime(df1["DateTime"], utc=True, errors="coerce").dt.tz_convert("America/Sao_Paulo")
                    df1["kwh_intervalo"] = pd.to_numeric(df1["kwh_intervalo"], errors="coerce")
                    df1 = df1.dropna(subset=["DateTime", "kwh_intervalo"])

                    if not df1.empty:
                        df1["Hora"] = df1["DateTime"].dt.floor("H")
                        df_grupo1 = (
                            df1.groupby("Hora", as_index=False)["kwh_intervalo"]
                               .sum()
                               .rename(columns={"kwh_intervalo": "Grupo1_kWh"})
                        )

            # ========== PROCESSAR Longitudinais ========== #
            df_grupo2 = None
            if group2:
                query2 = {**base_query, "IDMaq": {"$in": group2}}
                logger.info(f"[FETCH] Query Longitudinais: {query2}")
                
                t_find2 = time.perf_counter()
                cursor2 = collection_consumo.find(query2).sort("DateTime", 1)
                data2 = list(cursor2)
                logger.info(f"[FETCH] Longitudinais: {len(data2)} docs (find_ms={_duration_ms(t_find2)})")

                if data2:
                    df2 = pd.DataFrame(data2)
                    
                    if "DateTime" not in df2.columns or "kwh_intervalo" not in df2.columns:
                        logger.error("[FETCH] Colunas necessárias ausentes no Longitudinais")
                        return {"error": "Dados inválidos: colunas ausentes"}

                    df2["DateTime"] = pd.to_datetime(df2["DateTime"], utc=True, errors="coerce").dt.tz_convert("America/Sao_Paulo")
                    df2["kwh_intervalo"] = pd.to_numeric(df2["kwh_intervalo"], errors="coerce")
                    df2 = df2.dropna(subset=["DateTime", "kwh_intervalo"])

                    if not df2.empty:
                        df2["Hora"] = df2["DateTime"].dt.floor("H")
                        df_grupo2 = (
                            df2.groupby("Hora", as_index=False)["kwh_intervalo"]
                               .sum()
                               .rename(columns={"kwh_intervalo": "Grupo2_kWh"})
                        )

            # ========== MERGE DOS GRUPOS ========== #
            if df_grupo1 is None and df_grupo2 is None:
                logger.warning("[FETCH] Nenhum dado encontrado para nenhum grupo")
                return {"error": "Sem dados para o período selecionado."}

            # Merge com outer join para garantir todas as horas
            if df_grupo1 is not None and df_grupo2 is not None:
                df_final = pd.merge(df_grupo1, df_grupo2, on="Hora", how="outer")
                df_final = df_final.fillna(0)  # Preenche horas sem dados
            elif df_grupo1 is not None:
                df_final = df_grupo1.copy()
                df_final["Grupo2_kWh"] = 0
            else:  # só grupo2
                df_final = df_grupo2.copy()
                df_final["Grupo1_kWh"] = 0

            df_final = df_final.sort_values("Hora")
            df_final["HoraStr"] = df_final["Hora"].dt.strftime("%Y-%m-%d %H:%M")

            logger.info(f"[FETCH] Merge completo: {len(df_final)} horas (total_ms={_duration_ms(t0)})")

            # Retorna estrutura com metadados
            return {
                "data": df_final.to_dict("records"),
                "has_group1": group1 != [],
                "has_group2": group2 != [],
            }

        except Exception as e:
            logger.error(f"[FETCH][EXC] Erro: {e}\n{traceback.format_exc()}")
            return {"error": f"Erro ao consultar dados: {e}"}

    # ========== CALLBACK PARA ATUALIZAR O GRÁFICO ========== #
    @app.callback(
        [
            Output("hourly-consumption-graph", "figure"),
            Output("hourly-consumption-graph", "style"),
        ],
        [
            Input("stored-hourly-consumption-data", "data"),
            Input("url", "pathname"),
        ]
    )
    def update_hourly_consumption_graph(stored_data, pathname):
        t0 = time.perf_counter()

        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        visible_style = {"visibility": "visible", "height": "450px"}
        error_style = {"visibility": "visible", "height": "450px"}

        logger.debug(f"[GRAPH_HOURLY] Update pathname={pathname} template={template}")

        # --- 1) Sem dados ou erro ---
        if (not stored_data) or (isinstance(stored_data, dict) and "error" in stored_data):
            # Verifica se é erro de "nenhum equipamento selecionado"
            if isinstance(stored_data, dict) and stored_data.get("error"):
                error_msg = stored_data.get("error", "")
                if "Selecione pelo menos um equipamento" in error_msg:
                    # Empty state (nenhum equipamento selecionado)
                    logger.info("[GRAPH_HOURLY] Empty state: nenhum equipamento selecionado")
                    empty_fig = create_empty_state_figure('consumption', template)
                    return empty_fig, visible_style
                else:
                    # Erro real
                    logger.warning(f"[GRAPH_HOURLY] Erro: {error_msg}")
                    error_fig = create_error_state_figure(error_msg, template)
                    return error_fig, error_style
            
            # Fallback para sem dados
            logger.warning("[GRAPH_HOURLY] Sem dados")
            empty_fig = create_empty_state_figure('consumption', template)
            return empty_fig, visible_style

        # Extrai metadados
        has_group1 = stored_data.get("has_group1", False)
        has_group2 = stored_data.get("has_group2", False)
        data_records = stored_data.get("data", [])

        if not data_records:
            logger.warning("[GRAPH_HOURLY] data_records vazio")
            empty_fig = create_empty_state_figure('consumption', template)
            return empty_fig, visible_style

        # --- 2) Converter para DataFrame ---
        try:
            df = pd.DataFrame(data_records)
        except Exception as e:
            logger.error(f"[GRAPH_HOURLY][EXC] Falha ao criar DataFrame: {e}")
            error_fig = create_error_state_figure("Dados inválidos para gráfico de consumo", template)
            return error_fig, error_style

        # --- 3) Conferir colunas obrigatórias ---
        required_cols = ["HoraStr", "Grupo1_kWh", "Grupo2_kWh"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.error(f"[GRAPH_HOURLY] Colunas faltantes: {missing} | cols={list(df.columns)}")
            error_fig = create_error_state_figure(
                f"Dados inválidos (faltam colunas: {', '.join(missing)})",
                template
            )
            return error_fig, error_style

        if df.empty:
            logger.warning("[GRAPH_HOURLY] DataFrame vazio.")
            empty_fig = create_empty_state_figure('consumption', template)
            return empty_fig, visible_style

        # --- 4) Criar o gráfico tipo histograma com áreas transparentes ---
        try:
            fig = go.Figure()

            # Adiciona área Transversais (se existir)
            if has_group1 and "Grupo1_kWh" in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["HoraStr"],
                    y=df["Grupo1_kWh"],
                    name="Transversais",
                    mode='lines',
                    line=dict(color="#1f77b4", width=2),  # Azul
                    fill='tozeroy',  # Preenche até o eixo zero
                    fillcolor="rgba(31, 119, 180, 0.3)",  # Azul com 30% de opacidade
                    hovertemplate='<b>Transversais</b><br>Hora: %{x}<br>Consumo: %{y:.2f} kWh<extra></extra>',
                ))

            # Adiciona área Longitudinais (se existir)
            if has_group2 and "Grupo2_kWh" in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["HoraStr"],
                    y=df["Grupo2_kWh"],
                    name="Longitudinais",
                    mode='lines',
                    line=dict(color="#ff7f0e", width=2),  # Laranja
                    fill='tozeroy',  # Preenche até o eixo zero
                    fillcolor="rgba(255, 127, 14, 0.3)",  # Laranja com 30% de opacidade
                    hovertemplate='<b>Longitudinais</b><br>Hora: %{x}<br>Consumo: %{y:.2f} kWh<extra></extra>',
                ))

            # Layout do gráfico
            fig.update_layout(
                title="Consumo por Hora - Comparação de Grupos",
                xaxis_title="Hora",
                yaxis_title="Consumo (kWh)",
                template=template,
                margin=dict(l=40, r=10, t=50, b=40),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                xaxis=dict(tickfont=dict(size=10)),
                yaxis=dict(
                    tickfont=dict(size=10),
                    rangemode='tozero'  # Garante que o eixo Y começa em zero
                ),
                hovermode='x unified',  # Mostra todos os valores ao passar o mouse
            )

            logger.debug(f"[GRAPH_HOURLY] Figura gerada (ms={_duration_ms(t0)}), rows={len(df)}")
            return fig, visible_style

        except Exception as e:
            logger.error(f"[GRAPH_HOURLY][EXC] Falha ao renderizar: {e}")
            error_fig = create_error_state_figure("Erro ao renderizar gráfico de consumo", template)
            return error_fig, error_style

    # ========== CALLBACK PARA EXPORTAR EXCEL ========== #
    @app.callback(
        Output("download-consumption-excel", "data"),
        Input("btn-export-consumption", "n_clicks"),
        State("stored-hourly-consumption-data", "data"),
        prevent_initial_call=True,
    )
    def export_consumption_data_to_excel(n_clicks, stored_data):
        logger.debug(f"[EXPORT] n_clicks={n_clicks}")
        
        if not stored_data or "error" in stored_data:
            logger.warning("[EXPORT] Sem dados -> PreventUpdate")
            raise dash.exceptions.PreventUpdate

        data_records = stored_data.get("data", [])
        if not data_records:
            logger.warning("[EXPORT] data_records vazio -> PreventUpdate")
            raise dash.exceptions.PreventUpdate

        try:
            df_to_export = pd.DataFrame(data_records)
            
            # Remove colunas desnecessárias
            cols_to_drop = ["_id", "Hora"]
            df_to_export = df_to_export.drop(columns=[c for c in cols_to_drop if c in df_to_export.columns])

            # Reordena colunas para ficar mais intuitivo
            cols_order = ["HoraStr"]
            if "Grupo1_kWh" in df_to_export.columns:
                cols_order.append("Grupo1_kWh")
            if "Grupo2_kWh" in df_to_export.columns:
                cols_order.append("Grupo2_kWh")
            
            df_to_export = df_to_export[cols_order]

            logger.info(f"[EXPORT] Exportando {len(df_to_export)} linhas")
            return dcc.send_data_frame(
                df_to_export.to_excel,
                "dados_consumo_comparacao.xlsx",
                sheet_name="Comparacao",
                index=False
            )
        except Exception as e:
            logger.error(f"[EXPORT][EXC] Falha: {e}")
            raise dash.exceptions.PreventUpdate