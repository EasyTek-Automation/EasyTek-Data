# src/pages/energy/se03_telemetry.py

"""
Página de Telemetria em Tempo Real — SE03
Exibe valores ao vivo da coleção AMG_EnergyTelemetry com atualização automática.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc


def layout():
    """
    Layout da página de telemetria da SE03.
    Atualiza via interval-component global (10 s).
    """
    return dbc.Container([

        # ========================================
        # HEADER DA PÁGINA
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H4([
                    html.I(className="bi bi-lightning-charge-fill text-warning me-2"),
                    "SE03 — Telemetria em Tempo Real",
                ], className="mb-1"),
                html.P(
                    "Subestação Cortadeiras Transversais / Longitudinais",
                    className="text-muted mb-0 small"
                ),
            ], width=8),
            dbc.Col([
                html.Div([
                    # Badge "AO VIVO" animado
                    html.Span([
                        html.Span(className="se03-live-dot me-1"),
                        "AO VIVO",
                    ], className="badge bg-danger se03-live-badge me-3"),
                    # Timestamp da última atualização
                    html.Span([
                        html.I(className="bi bi-arrow-clockwise me-1"),
                        "Última att: ",
                        html.Span("--:--:--", id="se03-telemetry-last-update"),
                    ], className="text-muted small"),
                ], className="d-flex align-items-center justify-content-end h-100"),
            ], width=4),
        ], className="mb-4 align-items-center"),

        # ========================================
        # KPI CARDS — valores mais recentes
        # ========================================
        dbc.Row([
            # Fator de Potência
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="bi bi-speedometer2 fs-4 text-primary me-2"),
                            html.Span("Fator de Potência", className="text-muted small"),
                        ], className="d-flex align-items-center mb-2"),
                        html.Div(id="se03-tel-card-fp", children=[
                            html.Span("—", className="fs-3 fw-bold"),
                        ]),
                        html.Small("Threshold: ≥ 0.92 (ANEEL)", className="text-muted"),
                    ])
                ], className="h-100 shadow-sm"),
            ], md=3, className="mb-3"),

            # Potência Ativa Máxima
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="bi bi-bar-chart-fill fs-4 text-success me-2"),
                            html.Span("Potência Ativa Máx.", className="text-muted small"),
                        ], className="d-flex align-items-center mb-2"),
                        html.Div(id="se03-tel-card-pot-ativa", children=[
                            html.Span("—", className="fs-3 fw-bold"),
                        ]),
                        html.Small("kW", className="text-muted"),
                    ])
                ], className="h-100 shadow-sm"),
            ], md=3, className="mb-3"),

            # Potência Reativa Máxima
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="bi bi-activity fs-4 text-warning me-2"),
                            html.Span("Potência Reativa Máx.", className="text-muted small"),
                        ], className="d-flex align-items-center mb-2"),
                        html.Div(id="se03-tel-card-pot-reativa", children=[
                            html.Span("—", className="fs-3 fw-bold"),
                        ]),
                        html.Small("kVAR", className="text-muted"),
                    ])
                ], className="h-100 shadow-sm"),
            ], md=3, className="mb-3"),

            # Energia Acumulada
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="bi bi-lightning fs-4 text-info me-2"),
                            html.Span("Energia Ativa Acumulada", className="text-muted small"),
                        ], className="d-flex align-items-center mb-2"),
                        html.Div(id="se03-tel-card-energia", children=[
                            html.Span("—", className="fs-3 fw-bold"),
                        ]),
                        html.Small("kWh", className="text-muted"),
                    ])
                ], className="h-100 shadow-sm"),
            ], md=3, className="mb-3"),
        ], className="mb-2"),

        # ========================================
        # GRÁFICOS DE TENDÊNCIA
        # ========================================
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-graph-up me-2"),
                        "Fator de Potência — Tendência",
                        html.Span(
                            " (linha vermelha = threshold 0.92)",
                            className="text-muted small ms-2"
                        ),
                    ]),
                    dbc.CardBody([
                        dcc.Graph(
                            id="se03-tel-graph-fp",
                            config={"displayModeBar": False},
                            style={"height": "320px"},
                        )
                    ], className="p-2"),
                ], className="shadow-sm"),
            ], md=12, className="mb-3"),
        ]),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-bar-chart me-2"),
                        "Potência Ativa — Tendência (kW)",
                    ]),
                    dbc.CardBody([
                        dcc.Graph(
                            id="se03-tel-graph-potencia",
                            config={"displayModeBar": False},
                            style={"height": "320px"},
                        )
                    ], className="p-2"),
                ], className="shadow-sm"),
            ], md=12, className="mb-3"),
        ]),

    ], fluid=True, className="p-4")
