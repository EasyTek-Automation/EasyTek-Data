"""
Energy KPI Callbacks
Callbacks para os cards de indicadores da página SE03
"""

from dash import Input, Output, html
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go
from src.components.energy_kpi_cards import get_fp_badge, get_desbalanco_badge


def register_kpi_callbacks(app, collection_energia, collection_consumo):
    """
    Registra todos os callbacks dos KPIs de energia

    Args:
        app: Dash app instance
        collection_energia: Collection AMG_EnergyData
        collection_consumo: Collection AMG_Consumo
    """

    @app.callback(
        [
            Output('fp-value', 'children'),
            Output('fp-badge', 'children'),
            Output('fp-badge', 'color'),
            Output('fp-period-label', 'children')
        ],
        [
            Input('fp-period-radio', 'value')
        ]
    )
    def update_fp_card(period_hours):
        """
        Atualiza card de Fator de Potência Médio (MM01)

        Calcula FP médio do MM01 no período selecionado (1h, 8h ou 24h)
        """
        try:
            # Calcular intervalo de tempo baseado no período selecionado
            end_datetime = datetime.now(pytz.UTC)
            start_datetime = end_datetime - timedelta(hours=period_hours)

            # Usar apenas MM01 (soma de todos equipamentos)
            equipamento = "SE03_MM01"

            # Pipeline de agregação MongoDB
            pipeline = [
                {
                    "$match": {
                        "DateTime": {"$gte": start_datetime, "$lte": end_datetime},
                        "IDMaq": equipamento
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "fp_medio": {
                            "$avg": "$FatorPotenciaTotal"
                        }
                    }
                }
            ]

            result = list(collection_energia.aggregate(pipeline))

            # Label do período
            period_label = f"Últimas {period_hours} hora{'s' if period_hours > 1 else ''}"

            if result and result[0].get('fp_medio'):
                fp_value = result[0]['fp_medio']
                badge_text, badge_color = get_fp_badge(fp_value)
                return f"{fp_value:.3f}", badge_text, badge_color, period_label
            else:
                return "--", "Sem dados", "secondary", period_label

        except Exception as e:
            return "--", "Erro", "danger", f"Últimas {period_hours} horas"

    @app.callback(
        Output('desbalanco-content', 'children'),
        [
            Input('store-start-date', 'data'),
            Input('store-end-date', 'data'),
            Input('store-start-hour', 'data'),
            Input('store-end-hour', 'data')
        ]
    )
    def update_desbalanco_card(start_date, end_date, start_hour, end_hour):
        """
        Atualiza card de Desbalanceamento de Fases

        Calcula desbalanceamento de CORRENTE e TENSÃO das últimas 24h para cada equipamento
        """
        try:
            # Usar últimas 24h
            end_datetime = datetime.now(pytz.UTC)
            start_datetime = end_datetime - timedelta(hours=24)

            equipamentos = ["SE03_MM02", "SE03_MM03", "SE03_MM04",
                          "SE03_MM05", "SE03_MM06", "SE03_MM07"]

            result_elements = []

            # Calcular desbalanceamento para cada equipamento
            for equip in equipamentos:
                # Pipeline para calcular desbalanceamento de CORRENTE e TENSÃO
                pipeline = [
                    {
                        "$match": {
                            "DateTime": {"$gte": start_datetime, "$lte": end_datetime},
                            "IDMaq": equip
                        }
                    },
                    {
                        "$project": {
                            # Desbalanceamento de CORRENTE
                            "max_corrente": {"$max": ["$CorrenteL1", "$CorrenteL2", "$CorrenteL3"]},
                            "min_corrente": {"$min": ["$CorrenteL1", "$CorrenteL2", "$CorrenteL3"]},
                            "avg_corrente": {"$avg": ["$CorrenteL1", "$CorrenteL2", "$CorrenteL3"]},
                            # Desbalanceamento de TENSÃO
                            "max_tensao": {"$max": ["$TensaoL1", "$TensaoL2", "$TensaoL3"]},
                            "min_tensao": {"$min": ["$TensaoL1", "$TensaoL2", "$TensaoL3"]},
                            "avg_tensao": {"$avg": ["$TensaoL1", "$TensaoL2", "$TensaoL3"]}
                        }
                    },
                    {
                        "$project": {
                            "desbal_corrente": {
                                "$multiply": [
                                    {"$divide": [
                                        {"$subtract": ["$max_corrente", "$min_corrente"]},
                                        "$avg_corrente"
                                    ]},
                                    100
                                ]
                            },
                            "desbal_tensao": {
                                "$multiply": [
                                    {"$divide": [
                                        {"$subtract": ["$max_tensao", "$min_tensao"]},
                                        "$avg_tensao"
                                    ]},
                                    100
                                ]
                            }
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "desbal_corrente_medio": {"$avg": "$desbal_corrente"},
                            "desbal_tensao_medio": {"$avg": "$desbal_tensao"}
                        }
                    }
                ]

                result = list(collection_energia.aggregate(pipeline))

                if result and result[0]:
                    desbal_corrente = result[0].get('desbal_corrente_medio')
                    desbal_tensao = result[0].get('desbal_tensao_medio')

                    # Se temos pelo menos um valor
                    if desbal_corrente is not None or desbal_tensao is not None:
                        # Badge para corrente
                        if desbal_corrente is not None:
                            badge_text_i, badge_color_i = get_desbalanco_badge(desbal_corrente)
                            corrente_display = f"{desbal_corrente:.1f}%"
                        else:
                            badge_text_i, badge_color_i = "?", "secondary"
                            corrente_display = "--"

                        # Badge para tensão (critério mais rigoroso: < 2%)
                        if desbal_tensao is not None:
                            if desbal_tensao < 2:
                                badge_text_v, badge_color_v = "✓", "success"
                            elif desbal_tensao < 5:
                                badge_text_v, badge_color_v = "⚠", "warning"
                            else:
                                badge_text_v, badge_color_v = "✗", "danger"
                            tensao_display = f"{desbal_tensao:.1f}%"
                        else:
                            badge_text_v, badge_color_v = "?", "secondary"
                            tensao_display = "--"

                        result_elements.append(
                            html.Div([
                                html.Span(f"{equip.replace('SE03_', '')}",
                                         className="text-muted fw-bold me-2",
                                         style={"minWidth": "45px", "display": "inline-block", "fontSize": "0.85rem"}),
                                html.Span("I:", className="text-muted me-1", style={"fontSize": "0.75rem"}),
                                html.Span(corrente_display,
                                         className="me-1",
                                         style={"fontSize": "0.8rem", "minWidth": "38px", "display": "inline-block"}),
                                dbc.Badge(badge_text_i, color=badge_color_i, className="me-2",
                                         style={"fontSize": "0.65rem", "padding": "2px 4px"}),
                                html.Span("V:", className="text-muted me-1", style={"fontSize": "0.75rem"}),
                                html.Span(tensao_display,
                                         className="me-1",
                                         style={"fontSize": "0.8rem", "minWidth": "38px", "display": "inline-block"}),
                                dbc.Badge(badge_text_v, color=badge_color_v,
                                         style={"fontSize": "0.65rem", "padding": "2px 4px"})
                            ], className="mb-1", style={"lineHeight": "1.8"})
                        )
                    else:
                        result_elements.append(
                            html.Div([
                                html.Small(f"{equip.replace('SE03_', '')}:",
                                          className="text-muted me-2"),
                                html.Span("Sem dados", className="fw-bold")
                            ], className="mb-1")
                        )
                else:
                    result_elements.append(
                        html.Div([
                            html.Small(f"{equip.replace('SE03_', '')}:",
                                      className="text-muted me-2"),
                            html.Span("--", className="fw-bold")
                        ], className="mb-1")
                    )

            return result_elements if result_elements else [html.Small("Sem dados", className="text-muted")]

        except Exception as e:
            return [html.Small("Erro ao calcular", className="text-danger")]

    @app.callback(
        Output('consumo-medio-content', 'children'),
        [
            Input('store-start-date', 'data'),
            Input('store-end-date', 'data'),
            Input('store-start-hour', 'data'),
            Input('store-end-hour', 'data')
        ]
    )
    def update_consumo_medio_card(start_date, end_date, start_hour, end_hour):
        """
        Atualiza card de Consumo Médio

        Calcula consumo médio de Transversais e Longitudinais no período
        """
        try:
            # Converter datas
            if not start_date or not end_date:
                return _empty_consumo_content()

            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

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

            # Equipamentos
            transversais = ["SE03_MM02", "SE03_MM04", "SE03_MM06"]
            longitudinais = ["SE03_MM03", "SE03_MM05", "SE03_MM07"]

            # Query para Transversais
            query_trans = {
                "DateTime": {"$gte": start_datetime, "$lte": end_datetime},
                "IDMaq": {"$in": transversais}
            }
            data_trans = list(collection_consumo.find(query_trans))

            # Query para Longitudinais
            query_long = {
                "DateTime": {"$gte": start_datetime, "$lte": end_datetime},
                "IDMaq": {"$in": longitudinais}
            }
            data_long = list(collection_consumo.find(query_long))

            if not data_trans and not data_long:
                return _empty_consumo_content()

            # Calcular médias (ignorar valores None)
            consumo_trans = sum(d.get('kwh_intervalo', 0) for d in data_trans if d.get('kwh_intervalo') is not None)
            consumo_long = sum(d.get('kwh_intervalo', 0) for d in data_long if d.get('kwh_intervalo') is not None)

            # Contar horas para calcular média
            horas_trans = len(data_trans) / len(transversais) if data_trans else 1
            horas_long = len(data_long) / len(longitudinais) if data_long else 1

            media_trans = (consumo_trans / horas_trans) if horas_trans > 0 else 0
            media_long = (consumo_long / horas_long) if horas_long > 0 else 0
            total_medio = media_trans + media_long

            return [
                html.Div([
                    html.Small("Transversais:", className="text-muted me-2"),
                    html.Span(f"{media_trans:.1f} kW", className="fw-bold",
                             style={"color": "#2E86AB"})
                ], className="mb-1"),
                html.Div([
                    html.Small("Longitudinais:", className="text-muted me-2"),
                    html.Span(f"{media_long:.1f} kW", className="fw-bold",
                             style={"color": "#F77F00"})
                ], className="mb-2"),
                html.Hr(className="my-2"),
                html.Div([
                    html.Small("Total:", className="text-muted me-2"),
                    html.H5(f"{total_medio:.1f} kW", className="mb-0 d-inline",
                           style={"color": "#28a745"})
                ])
            ]

        except Exception as e:
            return _empty_consumo_content()

    @app.callback(
        Output('donut-chart', 'figure'),
        [
            Input('store-start-date', 'data'),
            Input('store-end-date', 'data'),
            Input('store-start-hour', 'data'),
            Input('store-end-hour', 'data')
        ]
    )
    def update_donut_chart(start_date, end_date, start_hour, end_hour):
        """
        Atualiza gráfico de rosca com distribuição de consumo

        Mostra proporção Transversais vs Longitudinais
        """
        try:
            # Converter datas
            if not start_date or not end_date:
                return _empty_donut_figure()

            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

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

            # Equipamentos
            transversais = ["SE03_MM02", "SE03_MM04", "SE03_MM06"]
            longitudinais = ["SE03_MM03", "SE03_MM05", "SE03_MM07"]

            # Query para Transversais
            query_trans = {
                "DateTime": {"$gte": start_datetime, "$lte": end_datetime},
                "IDMaq": {"$in": transversais}
            }
            data_trans = list(collection_consumo.find(query_trans))

            # Query para Longitudinais
            query_long = {
                "DateTime": {"$gte": start_datetime, "$lte": end_datetime},
                "IDMaq": {"$in": longitudinais}
            }
            data_long = list(collection_consumo.find(query_long))

            if not data_trans and not data_long:
                return _empty_donut_figure()

            # Somar consumo total (ignorar valores None)
            total_trans = sum(d.get('kwh_intervalo', 0) for d in data_trans if d.get('kwh_intervalo') is not None)
            total_long = sum(d.get('kwh_intervalo', 0) for d in data_long if d.get('kwh_intervalo') is not None)
            total_geral = total_trans + total_long

            if total_geral == 0:
                return _empty_donut_figure()

            # Criar gráfico
            fig = go.Figure(data=[go.Pie(
                labels=['Transversais', 'Longitudinais'],
                values=[total_trans, total_long],
                hole=.65,
                marker=dict(colors=['#2E86AB', '#F77F00']),
                textinfo='percent',
                textposition='inside',
                hovertemplate='<b>%{label}</b><br>%{value:.1f} kWh<br>%{percent}<extra></extra>'
            )])

            fig.update_layout(
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.2,
                    xanchor="center",
                    x=0.5
                ),
                height=250,
                margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                annotations=[dict(
                    text=f'{total_geral:.0f}<br>kWh',
                    x=0.5, y=0.5,
                    font=dict(size=20, color='#28a745', weight='bold'),
                    showarrow=False
                )]
            )

            return fig

        except Exception as e:
            return _empty_donut_figure()


def _empty_consumo_content():
    """Retorna conteúdo vazio para o card de consumo médio"""
    return [
        html.Div([
            html.Small("Transversais:", className="text-muted me-2"),
            html.Span("-- kW", className="fw-bold")
        ], className="mb-1"),
        html.Div([
            html.Small("Longitudinais:", className="text-muted me-2"),
            html.Span("-- kW", className="fw-bold")
        ], className="mb-2"),
        html.Hr(className="my-2"),
        html.Div([
            html.Small("Total:", className="text-muted me-2"),
            html.H5("-- kW", className="mb-0 d-inline")
        ])
    ]


def _empty_donut_figure():
    """Retorna figura vazia para o donut chart"""
    fig = go.Figure(data=[go.Pie(
        labels=['Transversais', 'Longitudinais'],
        values=[1, 1],
        hole=.65,
        marker=dict(colors=['#2E86AB', '#F77F00']),
        textinfo='percent',
        textposition='inside'
    )])

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5
        ),
        height=250,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        annotations=[dict(
            text='--<br>kWh',
            x=0.5, y=0.5,
            font=dict(size=20, color='#6c757d'),
            showarrow=False
        )]
    )

    return fig
