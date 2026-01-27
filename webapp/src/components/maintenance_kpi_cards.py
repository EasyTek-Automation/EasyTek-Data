"""
Maintenance KPI Cards Components
Cards de resumo de KPIs de manutenção
"""

from dash import html
import dash_bootstrap_components as dbc


def create_mtbf_summary_card():
    """
    Card de resumo: MTBF Médio

    - Ícone: clock-history (verde)
    - Valor dinâmico via callback
    - Badge de status (verde: >= meta, vermelho: < meta)
    """
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(
                    className="bi bi-clock-history",
                    style={"fontSize": "1.5rem", "color": "#20c997"}
                ),
                html.Div([
                    html.Small("MTBF Médio", className="text-muted d-block mb-1"),
                    html.H3(
                        id="summary-mtbf-value",
                        children="--",
                        className="mb-1 fw-bold"
                    ),
                    dbc.Badge(
                        id="summary-mtbf-badge",
                        children="Aguardando dados",
                        color="secondary",
                        className="mt-1"
                    )
                ], className="ms-3")
            ], className="d-flex align-items-center")
        ])
    ], className="shadow-sm h-100")


def create_mttr_summary_card():
    """
    Card de resumo: MTTR Médio

    - Ícone: tools (azul)
    - Valor dinâmico via callback
    - Badge de status (verde: <= meta, vermelho: > meta)
    """
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(
                    className="bi bi-tools",
                    style={"fontSize": "1.5rem", "color": "#0d6efd"}
                ),
                html.Div([
                    html.Small("MTTR Médio", className="text-muted d-block mb-1"),
                    html.H3(
                        id="summary-mttr-value",
                        children="--",
                        className="mb-1 fw-bold"
                    ),
                    dbc.Badge(
                        id="summary-mttr-badge",
                        children="Aguardando dados",
                        color="secondary",
                        className="mt-1"
                    )
                ], className="ms-3")
            ], className="d-flex align-items-center")
        ])
    ], className="shadow-sm h-100")


def create_breakdown_summary_card():
    """
    Card de resumo: Taxa de Avaria Média

    - Ícone: exclamation-triangle (laranja)
    - Valor dinâmico via callback
    - Badge de status (verde: <= meta, vermelho: > meta)
    """
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(
                    className="bi bi-exclamation-triangle-fill",
                    style={"fontSize": "1.5rem", "color": "#fd7e14"}
                ),
                html.Div([
                    html.Small("Taxa de Avaria Média", className="text-muted d-block mb-1"),
                    html.H3(
                        id="summary-breakdown-value",
                        children="--",
                        className="mb-1 fw-bold"
                    ),
                    dbc.Badge(
                        id="summary-breakdown-badge",
                        children="Aguardando dados",
                        color="secondary",
                        className="mt-1"
                    )
                ], className="ms-3")
            ], className="d-flex align-items-center")
        ])
    ], className="shadow-sm h-100")


def create_equipment_count_card():
    """
    Card de resumo: Total de Equipamentos

    - Ícone: gear-fill (cinza)
    - Contagem de equipamentos filtrados
    - Sem badge de status
    """
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(
                    className="bi bi-gear-fill",
                    style={"fontSize": "1.5rem", "color": "#6c757d"}
                ),
                html.Div([
                    html.Small("Equipamentos", className="text-muted d-block mb-1"),
                    html.H3(
                        id="summary-equipment-count",
                        children="7",
                        className="mb-1 fw-bold"
                    ),
                    html.Small("Total monitorado", className="text-muted")
                ], className="ms-3")
            ], className="d-flex align-items-center")
        ])
    ], className="shadow-sm h-100")
