# src/components/sidebars/water_sidebar.py

"""
Conteúdo da sidebar específico para páginas de água.
Exibe filtros e informações de consumo de água.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta


def create_water_sidebar_content():
    """
    Cria o conteúdo da sidebar para a página de água.

    Returns:
        html.Div: Componente com filtros e informações
    """
    # Datas padrão (últimos 7 dias)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    return html.Div([
        # ========================================
        # TÍTULO
        # ========================================
        html.H6([
            html.I(className="bi bi-droplet-fill me-2 text-primary"),
            "Filtros de Água"
        ], className="fw-bold mb-3"),

        # ========================================
        # SEÇÃO: PERÍODO
        # ========================================
        dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-calendar-range me-2"),
                "Período de Análise"
            ], className="fw-bold small bg-primary text-white"),
            dbc.CardBody([
                # Data Inicial
                html.Label("Data Inicial:", className="small text-muted mb-1"),
                dcc.DatePickerSingle(
                    id="water-date-start",
                    date=start_date.strftime('%Y-%m-%d'),
                    display_format='DD/MM/YYYY',
                    className="mb-2 w-100",
                    style={'width': '100%'}
                ),

                # Data Final
                html.Label("Data Final:", className="small text-muted mb-1 mt-2"),
                dcc.DatePickerSingle(
                    id="water-date-end",
                    date=end_date.strftime('%Y-%m-%d'),
                    display_format='DD/MM/YYYY',
                    className="mb-2 w-100",
                    style={'width': '100%'}
                ),

                # Botão de atualização
                dbc.Button([
                    html.I(className="bi bi-arrow-clockwise me-2"),
                    "Atualizar"
                ], id="water-update-btn", color="primary", size="sm", className="w-100 mt-2")
            ], className="py-2")
        ], className="mb-3"),

        # ========================================
        # SEÇÃO: FILTROS DE MEDIDORES
        # ========================================
        dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-gear me-2"),
                "Medidores"
            ], className="fw-bold small bg-info text-white"),
            dbc.CardBody([
                dcc.Dropdown(
                    id="water-meters-dropdown",
                    options=[
                        {"label": "🔹 Todos os Medidores", "value": "all"},
                        {"label": "M-001 - Entrada Principal", "value": "M001"},
                        {"label": "M-002 - Produção 1", "value": "M002"},
                        {"label": "M-003 - Produção 2", "value": "M003"},
                        {"label": "M-004 - Torre Resfriamento", "value": "M004"},
                        {"label": "M-005 - Utilidades", "value": "M005"},
                    ],
                    value="all",
                    clearable=False,
                    className="small"
                ),
            ], className="py-2")
        ], className="mb-3"),

        # ========================================
        # SEÇÃO: FILTROS DE ÁREA
        # ========================================
        dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-building me-2"),
                "Áreas"
            ], className="fw-bold small bg-secondary text-white"),
            dbc.CardBody([
                dcc.Dropdown(
                    id="water-areas-dropdown",
                    options=[
                        {"label": "🏭 Todas as Áreas", "value": "all"},
                        {"label": "Produção", "value": "production"},
                        {"label": "Utilidades", "value": "utilities"},
                        {"label": "Administrativo", "value": "admin"},
                        {"label": "Outros", "value": "others"},
                    ],
                    value="all",
                    clearable=False,
                    className="small"
                ),
            ], className="py-2")
        ], className="mb-3"),

        # ========================================
        # SEÇÃO: RESUMO RÁPIDO
        # ========================================
        dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-info-circle me-2"),
                "Resumo do Período"
            ], className="fw-bold small bg-success text-white"),
            dbc.CardBody([
                # Consumo Total
                html.Div([
                    html.Span("Consumo Total:", className="text-muted small"),
                    html.Span(id="water-summary-total", children="-- m³",
                             className="float-end small fw-bold text-primary")
                ], className="d-flex justify-content-between mb-2"),

                html.Hr(className="my-2"),

                # Média Diária
                html.Div([
                    html.Span("Média Diária:", className="text-muted small"),
                    html.Span(id="water-summary-avg", children="-- m³/dia",
                             className="float-end small fw-bold text-info")
                ], className="d-flex justify-content-between mb-2"),

                html.Hr(className="my-2"),

                # Custo Estimado
                html.Div([
                    html.Span("Custo Estimado:", className="text-muted small"),
                    html.Span(id="water-summary-cost", children="R$ --",
                             className="float-end small fw-bold text-success")
                ], className="d-flex justify-content-between"),
            ], className="py-2")
        ], className="mb-3"),

        # ========================================
        # SEÇÃO: ALERTAS
        # ========================================
        dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-exclamation-triangle me-2"),
                "Alertas"
            ], className="fw-bold small bg-warning text-dark"),
            dbc.CardBody([
                dbc.Alert([
                    html.I(className="bi bi-info-circle-fill me-2"),
                    html.Small("Sistema em desenvolvimento. Dados simulados para demonstração.")
                ], color="warning", className="py-2 small mb-0"),
            ], className="py-2")
        ], className="mb-3"),

        # ========================================
        # SEÇÃO: AÇÕES RÁPIDAS
        # ========================================
        html.Div([
            dbc.Button([
                html.I(className="bi bi-download me-2"),
                "Exportar Dados"
            ], color="success", outline=True, size="sm", className="w-100 mb-2"),

            dbc.Button([
                html.I(className="bi bi-printer me-2"),
                "Imprimir Relatório"
            ], color="secondary", outline=True, size="sm", className="w-100"),
        ], className="mt-3"),

    ], className="p-3")


def create_water_default_sidebar():
    """
    Cria sidebar padrão quando não há configuração específica.

    Returns:
        html.Div: Componente com informações básicas
    """
    return html.Div([
        html.H6([
            html.I(className="bi bi-droplet-fill me-2 text-primary"),
            "Monitoramento de Água"
        ], className="fw-bold mb-3"),

        dbc.Alert([
            html.I(className="bi bi-info-circle-fill me-2"),
            "Selecione uma tab para visualizar filtros específicos."
        ], color="info", className="py-2 small"),

        # Informações Gerais
        html.Div([
            html.P("📊 Sistema de Monitoramento", className="small text-muted mb-2"),
            html.P("💧 Acompanhe o consumo de água em tempo real", className="small text-muted mb-2"),
            html.P("💰 Analise custos e otimize o uso", className="small text-muted mb-2"),
        ], className="mt-3")

    ], className="p-3")
