"""
Demand Graph Callbacks
Callbacks para os gráficos de demanda temporal (kW e kVA)
"""

from dash import Input, Output
from datetime import datetime
import pytz
import pandas as pd
from dash_bootstrap_templates import ThemeSwitchAIO
from src.config.theme_config import TEMPLATE_THEME_MINTY, TEMPLATE_THEME_DARKLY
from src.components.demand_graphs import (
    create_empty_demand_figure,
    create_demand_figure,
    create_error_demand_figure
)


def register_demand_callbacks(app, collection_energia):
    """
    Registra callbacks dos gráficos de demanda

    Args:
        app: Dash app instance
        collection_energia: Collection AMG_EnergyData
    """

    @app.callback(
        Output('demand-graph-transversais', 'figure'),
        [
            Input('store-start-date', 'data'),
            Input('store-end-date', 'data'),
            Input('store-start-hour', 'data'),
            Input('store-end-hour', 'data'),
            Input('machine-dropdown-group1', 'value'),
            Input(ThemeSwitchAIO.ids.switch("theme"), "value")
        ]
    )
    def update_demand_transversais(start_date, end_date, start_hour, end_hour, selected_machines, toggle):
        """
        Atualiza gráfico de demanda temporal - Transversais

        Calcula demanda em kW e kVA agregada por hora
        """
        try:
            # Template do tema
            if toggle is None:
                toggle = True
            template = TEMPLATE_THEME_MINTY if toggle else TEMPLATE_THEME_DARKLY

            # Validar inputs
            if not start_date or not end_date:
                return create_empty_demand_figure("Transversais", template)

            # Equipamentos padrão se não selecionado
            if not selected_machines or len(selected_machines) == 0:
                selected_machines = ["SE03_MM02", "SE03_MM04", "SE03_MM06"]

            # Filtrar apenas transversais
            transversais_validos = ["SE03_MM02", "SE03_MM04", "SE03_MM06"]
            selected_machines = [m for m in selected_machines if m in transversais_validos]

            if not selected_machines:
                return create_empty_demand_figure("Transversais", template)

            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            # Validar se data de início é maior que data de fim
            if start_dt > end_dt:
                return create_error_demand_figure(
                    "Data de início maior que data de fim",
                    "Transversais",
                    template
                )

            # Parse hours
            start_h = int(start_hour.split(':')[0]) if start_hour else 0
            end_h = int(end_hour.split(':')[0]) if end_hour else 23

            # Combinar data + hora
            start_datetime = datetime(start_dt.year, start_dt.month, start_dt.day, start_h, 0, 0)
            end_datetime = datetime(end_dt.year, end_dt.month, end_dt.day, end_h, 59, 59)

            # Converter para UTC
            local_tz = pytz.timezone('America/Sao_Paulo')
            start_datetime = local_tz.localize(start_datetime).astimezone(pytz.UTC)
            end_datetime = local_tz.localize(end_datetime).astimezone(pytz.UTC)

            # Pipeline de agregação MongoDB (por hora)
            pipeline = [
                {
                    "$match": {
                        "DateTime": {"$gte": start_datetime, "$lte": end_datetime},
                        "IDMaq": {"$in": selected_machines}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d %H:00:00",
                                "date": "$DateTime"
                            }
                        },
                        "kW": {
                            "$avg": {
                                "$divide": ["$PotenciaAtivaTotal", 1000]
                            }
                        },
                        "FP": {
                            "$avg": "$FatorPotenciaTotal"
                        }
                    }
                },
                {
                    "$addFields": {
                        "kVA": {
                            "$cond": {
                                "if": {"$gt": ["$FP", 0]},
                                "then": {"$divide": ["$kW", "$FP"]},
                                "else": "$kW"
                            }
                        }
                    }
                },
                {"$sort": {"_id": 1}}
            ]

            result = list(collection_energia.aggregate(pipeline))

            print(f"[DEBUG TRANSVERSAIS] Período: {start_datetime} a {end_datetime}")
            print(f"[DEBUG TRANSVERSAIS] Equipamentos: {selected_machines}")
            print(f"[DEBUG TRANSVERSAIS] Documentos retornados: {len(result)}")

            if not result:
                return create_error_demand_figure(
                    "Sem dados para o período selecionado",
                    "Transversais",
                    template
                )

            # Converter para DataFrame
            df = pd.DataFrame(result)
            df['DateTime'] = pd.to_datetime(df['_id'])

            # Converter para timezone local para exibição
            df['DateTime'] = df['DateTime'].dt.tz_localize(pytz.UTC).dt.tz_convert(local_tz)

            # Extrair valores
            timestamps = df['DateTime'].tolist()
            kw_values = df['kW'].tolist()
            kva_values = df['kVA'].tolist()

            print(f"[DEBUG TRANSVERSAIS] Timestamps: {len(timestamps)}, kW: {len(kw_values)}, kVA: {len(kva_values)}")
            if len(timestamps) > 0:
                print(f"[DEBUG TRANSVERSAIS] Primeiro resultado raw: {result[0]}")
                print(f"[DEBUG TRANSVERSAIS] Valor kW[0]: {kw_values[0]}, tipo: {type(kw_values[0])}")
                print(f"[DEBUG TRANSVERSAIS] Valor kVA[0]: {kva_values[0]}, tipo: {type(kva_values[0])}")

                # Verificar se há valores None
                none_kw = sum(1 for v in kw_values if v is None)
                none_kva = sum(1 for v in kva_values if v is None)
                print(f"[DEBUG TRANSVERSAIS] Valores None - kW: {none_kw}, kVA: {none_kva}")

                if none_kw > 0 or none_kva > 0:
                    return create_error_demand_figure(
                        "Dados incompletos para o período selecionado",
                        "Transversais",
                        template
                    )

            # Criar figura
            fig = create_demand_figure(timestamps, kw_values, kva_values, "Transversais", template)

            return fig

        except Exception as e:
            print(f"Erro ao calcular demanda transversais: {e}")
            import traceback
            traceback.print_exc()
            # Template padrão em caso de erro antes de definir
            template = TEMPLATE_THEME_MINTY
            return create_error_demand_figure(
                f"Erro ao processar dados: {str(e)[:50]}",
                "Transversais",
                template
            )

    @app.callback(
        Output('demand-graph-longitudinais', 'figure'),
        [
            Input('store-start-date', 'data'),
            Input('store-end-date', 'data'),
            Input('store-start-hour', 'data'),
            Input('store-end-hour', 'data'),
            Input('machine-dropdown-group2', 'value'),
            Input(ThemeSwitchAIO.ids.switch("theme"), "value")
        ]
    )
    def update_demand_longitudinais(start_date, end_date, start_hour, end_hour, selected_machines, toggle):
        """
        Atualiza gráfico de demanda temporal - Longitudinais

        Calcula demanda em kW e kVA agregada por hora
        """
        try:
            # Template do tema
            if toggle is None:
                toggle = True
            template = TEMPLATE_THEME_MINTY if toggle else TEMPLATE_THEME_DARKLY

            # Validar inputs
            if not start_date or not end_date:
                return create_empty_demand_figure("Longitudinais", template)

            # Equipamentos padrão se não selecionado
            if not selected_machines or len(selected_machines) == 0:
                selected_machines = ["SE03_MM03", "SE03_MM05", "SE03_MM07"]

            # Filtrar apenas longitudinais
            longitudinais_validos = ["SE03_MM03", "SE03_MM05", "SE03_MM07"]
            selected_machines = [m for m in selected_machines if m in longitudinais_validos]

            if not selected_machines:
                return create_empty_demand_figure("Longitudinais", template)

            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            # Validar se data de início é maior que data de fim
            if start_dt > end_dt:
                return create_error_demand_figure(
                    "Data de início maior que data de fim",
                    "Longitudinais",
                    template
                )

            # Parse hours
            start_h = int(start_hour.split(':')[0]) if start_hour else 0
            end_h = int(end_hour.split(':')[0]) if end_hour else 23

            # Combinar data + hora
            start_datetime = datetime(start_dt.year, start_dt.month, start_dt.day, start_h, 0, 0)
            end_datetime = datetime(end_dt.year, end_dt.month, end_dt.day, end_h, 59, 59)

            # Converter para UTC
            local_tz = pytz.timezone('America/Sao_Paulo')
            start_datetime = local_tz.localize(start_datetime).astimezone(pytz.UTC)
            end_datetime = local_tz.localize(end_datetime).astimezone(pytz.UTC)

            # Pipeline de agregação MongoDB (por hora)
            pipeline = [
                {
                    "$match": {
                        "DateTime": {"$gte": start_datetime, "$lte": end_datetime},
                        "IDMaq": {"$in": selected_machines}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d %H:00:00",
                                "date": "$DateTime"
                            }
                        },
                        "kW": {
                            "$avg": {
                                "$divide": ["$PotenciaAtivaTotal", 1000]
                            }
                        },
                        "FP": {
                            "$avg": "$FatorPotenciaTotal"
                        }
                    }
                },
                {
                    "$addFields": {
                        "kVA": {
                            "$cond": {
                                "if": {"$gt": ["$FP", 0]},
                                "then": {"$divide": ["$kW", "$FP"]},
                                "else": "$kW"
                            }
                        }
                    }
                },
                {"$sort": {"_id": 1}}
            ]

            result = list(collection_energia.aggregate(pipeline))

            print(f"[DEBUG LONGITUDINAIS] Período: {start_datetime} a {end_datetime}")
            print(f"[DEBUG LONGITUDINAIS] Equipamentos: {selected_machines}")
            print(f"[DEBUG LONGITUDINAIS] Documentos retornados: {len(result)}")

            if not result:
                return create_error_demand_figure(
                    "Sem dados para o período selecionado",
                    "Longitudinais",
                    template
                )

            # Converter para DataFrame
            df = pd.DataFrame(result)
            df['DateTime'] = pd.to_datetime(df['_id'])

            # Converter para timezone local para exibição
            df['DateTime'] = df['DateTime'].dt.tz_localize(pytz.UTC).dt.tz_convert(local_tz)

            # Extrair valores
            timestamps = df['DateTime'].tolist()
            kw_values = df['kW'].tolist()
            kva_values = df['kVA'].tolist()

            print(f"[DEBUG LONGITUDINAIS] Timestamps: {len(timestamps)}, kW: {len(kw_values)}, kVA: {len(kva_values)}")
            if len(timestamps) > 0:
                print(f"[DEBUG LONGITUDINAIS] Primeiro resultado raw: {result[0]}")
                print(f"[DEBUG LONGITUDINAIS] Valor kW[0]: {kw_values[0]}, tipo: {type(kw_values[0])}")
                print(f"[DEBUG LONGITUDINAIS] Valor kVA[0]: {kva_values[0]}, tipo: {type(kva_values[0])}")

                # Verificar se há valores None
                none_kw = sum(1 for v in kw_values if v is None)
                none_kva = sum(1 for v in kva_values if v is None)
                print(f"[DEBUG LONGITUDINAIS] Valores None - kW: {none_kw}, kVA: {none_kva}")

                if none_kw > 0 or none_kva > 0:
                    return create_error_demand_figure(
                        "Dados incompletos para o período selecionado",
                        "Longitudinais",
                        template
                    )

            # Criar figura
            fig = create_demand_figure(timestamps, kw_values, kva_values, "Longitudinais", template)

            return fig

        except Exception as e:
            print(f"Erro ao calcular demanda longitudinais: {e}")
            import traceback
            traceback.print_exc()
            # Template padrão em caso de erro antes de definir
            template = TEMPLATE_THEME_MINTY
            return create_error_demand_figure(
                f"Erro ao processar dados: {str(e)[:50]}",
                "Longitudinais",
                template
            )
