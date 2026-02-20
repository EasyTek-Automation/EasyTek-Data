# src/components/headers/maintenance_indicators_filters.py

"""
Filtros específicos para a página de Indicadores de Manutenção.
Inclui seleção de tipo de período, ano de referência e date range customizado.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime
from src.components.dropdown_footer import create_dropdown_footer


def create_maintenance_indicators_filters():
    """
    Cria os filtros para a página de Indicadores de Manutenção.

    Filtros disponíveis:
    - Tipo de Período (Radio): Ano | Período
    - Ano de Referência (Dropdown): 2024, 2025, 2026
    - Date Picker Range: Para período customizado

    Returns:
        html.Div: Componente com os filtros da página
    """
    current_year = datetime.now().year

    return html.Div([
        dbc.Row([
            # Coluna 1: Vazia (espaço)
            dbc.Col([], width=4),

            # Coluna 2: Vazia (espaço)
            dbc.Col([], width=4),

            # Coluna 3: Conteúdo dos filtros (4 colunas de largura)
            dbc.Col([
                # Tipo de Período
                html.Div([
                    html.Label(
                        "Tipo de Período",
                        className="form-label fw-bold mb-2",
                        style={"fontSize": "0.9rem", "color": "#495057"}
                    ),
                    dbc.RadioItems(
                        id="filter-period-type",
                        options=[
                            {"label": " Ano", "value": "year"},
                            {"label": " Período", "value": "custom"}
                        ],
                        value="year",  # Padrão: Ano completo
                        inline=False,  # Vertical para ocupar menos espaço
                        className="mb-3",
                        input_class_name="me-2",
                        style={"fontSize": "0.85rem"}
                    )
                ], className="mb-3"),

                # Ano de Referência
                html.Div([
                    html.Label(
                        "Ano de Referência",
                        className="form-label fw-bold mb-2",
                        style={"fontSize": "0.85rem", "color": "#495057"}
                    ),
                    dcc.Dropdown(
                        id="filter-reference-year",
                        options=[
                            {"label": "2024", "value": 2024},
                            {"label": "2025", "value": 2025},
                            {"label": "2026", "value": 2026},
                            {"label": "2027", "value": 2027}
                        ],
                        value=2026,  # Ano padrão
                        clearable=False,
                        style={"fontSize": "0.85rem"}
                    )
                ], id="div-reference-year", style={"display": "block"}, className="mb-3"),

                # Seletor de Equipamentos
                html.Div([
                    html.Label(
                        "Equipamentos",
                        className="form-label fw-bold mb-2",
                        style={"fontSize": "0.85rem", "color": "#495057"}
                    ),
                    dcc.Dropdown(
                        id="filter-equipment-selection",
                        options=[],  # Será populado dinamicamente
                        value=[],    # Será definido dinamicamente (todos exceto DECAP001)
                        multi=True,
                        placeholder="Selecione equipamentos...",
                        style={"fontSize": "0.85rem"}
                    ),
                    html.Small(
                        "Padrão: Todos exceto Decapado",
                        className="text-muted",
                        style={"fontSize": "0.7rem"}
                    )
                ], className="mb-3"),

                # Códigos de Avaria
                html.Div([
                    html.Label(
                        "Motivos de Parada",
                        className="form-label fw-bold mb-2",
                        style={"fontSize": "0.85rem", "color": "#495057"}
                    ),
                    dcc.Dropdown(
                        id="filter-breakdown-codes",
                        options=[
                            {"label": "110",  "value": "110"},
                            {"label": "S110", "value": "S110"},
                            {"label": "201",  "value": "201"},
                            {"label": "S201", "value": "S201"},
                            {"label": "202",  "value": "202"},
                            {"label": "S202", "value": "S202"},
                            {"label": "203",  "value": "203"},
                            {"label": "S203", "value": "S203"},
                            {"label": "204",  "value": "204"},
                            {"label": "S204", "value": "S204"},
                            {"label": "205",  "value": "205"},
                            {"label": "S205", "value": "S205"},
                        ],
                        value=["110", "S110",
                               "201", "S201",
                               "202", "S202",
                               "203", "S203",
                               "204", "S204",
                               "205", "S205"],
                        multi=True,
                        placeholder="Selecione os códigos...",
                        style={"fontSize": "0.85rem"}
                    ),
                    html.Small(
                        "Padrão: todos os códigos de avaria",
                        className="text-muted",
                        style={"fontSize": "0.7rem"}
                    )
                ], className="mb-3"),

                # Date Picker Range
                html.Div([
                    html.Label(
                        "Período Personalizado",
                        className="form-label fw-bold mb-2",
                        style={"fontSize": "0.85rem", "color": "#495057"}
                    ),
                    dcc.DatePickerRange(
                        id="filter-date-range",
                        display_format="DD/MM/YYYY",
                        start_date_placeholder_text="Data Início",
                        end_date_placeholder_text="Data Fim",
                        style={"fontSize": "0.85rem"}
                    )
                ], id="div-date-range", style={"display": "none"}, className="mb-3"),

                # Botão Aplicar
                dbc.Button(
                    [
                        html.I(className="bi bi-check-circle me-2"),
                        "Aplicar Filtros"
                    ],
                    id="btn-apply-indicator-filters",
                    color="primary",
                    size="sm",
                    className="w-100 mb-3",
                    style={"fontWeight": "600"}
                ),

                # Informação adicional
                html.Div([
                    html.I(className="bi bi-info-circle me-2", style={"color": "#0dcaf0"}),
                    html.Span(
                        "Os dados serão filtrados conforme o período selecionado.",
                        style={"fontSize": "0.75rem", "color": "#6c757d"}
                    )
                ], className="d-flex align-items-center mb-3"),

                # Footer "Powered By"
                create_dropdown_footer()

            ], width=4)  # Terceira coluna: 4/12

        ], className="g-0")

    ], style={"padding": "1rem", "minWidth": "750px"}, id="maintenance-indicators-filters-content")
