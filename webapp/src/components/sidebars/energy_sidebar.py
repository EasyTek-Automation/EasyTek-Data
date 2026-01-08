# src/components/sidebars/energy_sidebar.py

"""
Conteúdo da sidebar específico para páginas de energia.
Suporta exibição dinâmica de custos quando a tab SE03 está ativa.
"""

from dash import html
import dash_bootstrap_components as dbc


def create_se03_cost_sidebar_content():
    """
    VERSÃO DEBUG - Mostra cálculo detalhado passo a passo.
    Cria o conteúdo da sidebar para a tab SE03 com breakdown completo.
    Os valores serão populados por callback.

    Returns:
        html.Div: Componente com breakdown detalhado dos custos
    """
    return html.Div([
        # Título
        html.H6([
            html.I(className="bi bi-bug-fill me-2"),
            "DEBUG - Custos SE03"
        ], className="text-danger fw-bold mb-3"),

        # Alerta de versão debug
        dbc.Alert([
            html.I(className="bi bi-info-circle-fill me-2"),
            "Versão DEBUG - Mostrando cálculo detalhado"
        ], color="warning", className="py-2 small mb-3"),

        # ========================================
        # SEÇÃO 1: INFORMAÇÕES DO PERÍODO
        # ========================================
        dbc.Card([
            dbc.CardHeader("📅 Períodos de Cálculo", className="fw-bold small"),
            dbc.CardBody([
                html.Div([
                    html.Strong("Consumo (kWh):", className="small d-block text-primary"),
                    html.Div(id="debug-period-info", children="Carregando...", className="small ps-2"),
                ], className="mb-2"),
                html.Div([
                    html.Strong("Demanda (kW):", className="small d-block text-warning"),
                    html.Div(id="debug-month-info", children="Mês inteiro: --", className="small ps-2"),
                ], className="mb-2"),
                html.Div(id="debug-equipment-info", children="Equipamentos: MM02-MM07", className="small text-muted mt-1"),
                html.Div(id="debug-records-count", children="Registros: --", className="small text-muted"),
            ], className="py-2")
        ], className="mb-2"),

        # ========================================
        # SEÇÃO 2: CONSUMO BRUTO (kWh)
        # ========================================
        dbc.Card([
            dbc.CardHeader("⚡ Consumo (kWh)", className="fw-bold small"),
            dbc.CardBody([
                html.Div([
                    html.Span("Ponta:", className="text-muted small"),
                    html.Span(id="debug-kwh-ponta", children="-- kWh", className="float-end small fw-bold text-warning")
                ], className="d-flex justify-content-between mb-1"),
                html.Div([
                    html.Span("Fora Ponta:", className="text-muted small"),
                    html.Span(id="debug-kwh-fora-ponta", children="-- kWh", className="float-end small fw-bold text-info")
                ], className="d-flex justify-content-between"),
            ], className="py-2")
        ], className="mb-2"),

        # ========================================
        # SEÇÃO 3: DEMANDA (kW) - MÊS INTEIRO
        # ========================================
        dbc.Card([
            dbc.CardHeader("📊 Demanda Máxima (Mês Inteiro)", className="fw-bold small"),
            dbc.CardBody([
                dbc.Alert([
                    html.I(className="bi bi-info-circle-fill me-2"),
                    html.Small("Demanda é sempre do mês completo (padrão de cobrança)")
                ], color="info", className="py-1 px-2 mb-2 small"),
                html.Div([
                    html.Span("Ponta:", className="text-muted small"),
                    html.Span(id="se03-demand-ponta-kw", children="-- kW", className="float-end small fw-bold")
                ], className="d-flex justify-content-between mb-1"),
                html.Div([
                    html.Span("Fora Ponta:", className="text-muted small"),
                    html.Span(id="se03-demand-fora-ponta-kw", children="-- kW", className="float-end small fw-bold")
                ], className="d-flex justify-content-between mb-2"),
                html.Hr(className="my-1"),
                html.Div([
                    html.Span("% Contratada Ponta:", className="text-muted small"),
                    html.Span(id="se03-demand-ponta-pct", children="---%", className="float-end small fw-bold text-warning")
                ], className="d-flex justify-content-between mb-1"),
                html.Div([
                    html.Span("% Contratada Fora:", className="text-muted small"),
                    html.Span(id="se03-demand-fora-ponta-pct", children="---%", className="float-end small fw-bold text-info")
                ], className="d-flex justify-content-between"),
            ], className="py-2")
        ], className="mb-2"),

        # ========================================
        # SEÇÃO 4: BREAKDOWN DE CUSTOS
        # ========================================
        dbc.Card([
            dbc.CardHeader("💰 Breakdown de Custos", className="fw-bold small"),
            dbc.CardBody([
                # TUSD
                html.Div("TUSD:", className="small fw-bold text-primary mb-1"),
                html.Div(id="debug-tusd-ponta-calc", children="Ponta: -- kWh × R$ -- = R$ --", className="small text-muted ps-2 mb-1"),
                html.Div(id="debug-tusd-fora-calc", children="Fora: -- kWh × R$ -- = R$ --", className="small text-muted ps-2 mb-2"),

                # Energia
                html.Div("Energia:", className="small fw-bold text-success mb-1"),
                html.Div(id="debug-energia-ponta-calc", children="Ponta: -- kWh × R$ -- = R$ --", className="small text-muted ps-2 mb-1"),
                html.Div(id="debug-energia-fora-calc", children="Fora: -- kWh × R$ -- = R$ --", className="small text-muted ps-2 mb-2"),

                # Demanda
                html.Div("Demanda:", className="small fw-bold text-warning mb-1"),
                html.Div(id="debug-demanda-ponta-calc", children="Ponta: R$ -- × --% = R$ --", className="small text-muted ps-2 mb-1"),
                html.Div(id="debug-demanda-fora-calc", children="Fora: R$ -- × --% = R$ --", className="small text-muted ps-2"),
            ], className="py-2")
        ], className="mb-2"),

        # ========================================
        # SEÇÃO 5: TOTAIS
        # ========================================
        dbc.Card([
            dbc.CardHeader("🎯 Totais", className="fw-bold small"),
            dbc.CardBody([
                html.Div([
                    html.Span("TUSD Total:", className="small"),
                    html.Span(id="debug-tusd-total", children="R$ --", className="float-end small fw-bold")
                ], className="d-flex justify-content-between mb-1"),
                html.Div([
                    html.Span("Energia Total:", className="small"),
                    html.Span(id="debug-energia-total", children="R$ --", className="float-end small fw-bold")
                ], className="d-flex justify-content-between mb-1"),
                html.Div([
                    html.Span("Demanda Total:", className="small"),
                    html.Span(id="debug-demanda-total", children="R$ --", className="float-end small fw-bold")
                ], className="d-flex justify-content-between mb-2"),
                html.Hr(className="my-1"),
                html.Div([
                    html.Span("TOTAL PERÍODO:", className="small fw-bold text-success"),
                    html.Span(id="se03-cost-total-current", children="R$ --", className="float-end small fw-bold text-success")
                ], className="d-flex justify-content-between mb-1"),
                html.Div([
                    html.Span("kWh Total:", className="small text-muted"),
                    html.Span(id="se03-kwh-total-current", children="-- kWh", className="float-end small text-muted")
                ], className="d-flex justify-content-between"),
            ], className="py-2")
        ], className="mb-2"),

        # ========================================
        # SEÇÃO 6: COMPARATIVO
        # ========================================
        dbc.Card([
            dbc.CardHeader("📈 Período Anterior", className="fw-bold small"),
            dbc.CardBody([
                html.Div([
                    html.Span("Total:", className="small"),
                    html.Span(id="se03-cost-total-previous", children="R$ --", className="float-end small fw-bold")
                ], className="d-flex justify-content-between mb-1"),
                html.Div([
                    html.Span("kWh:", className="small text-muted"),
                    html.Span(id="se03-kwh-total-previous", children="-- kWh", className="float-end small text-muted")
                ], className="d-flex justify-content-between"),
            ], className="py-2")
        ], className="mb-2"),

        html.Hr(className="my-2"),

        # Rodapé
        html.Small([
            html.I(className="bi bi-gear-fill me-1"),
            html.A("Configurar tarifas", href="/utilities/energy/config", className="text-decoration-none")
        ], className="text-muted d-block", style={"fontSize": "0.65rem"}),

    ], id="se03-cost-sidebar", style={"padding": "10px"})


def create_energy_sidebar_no_config():
    """
    Sidebar exibida quando não há configuração de tarifas cadastrada.
    Mostra mensagem com link para página de configuração.

    Returns:
        html.Div: Componente com alerta e link
    """
    return html.Div([
        # Título
        html.H6([
            html.I(className="bi bi-exclamation-triangle me-2"),
            "Custos"
        ], className="text-warning fw-bold mb-3"),

        # Alerta informativo
        dbc.Alert([
            html.Div([
                html.I(className="bi bi-info-circle-fill me-2"),
                html.Span("Configure as tarifas de energia para visualizar os custos da SE03.")
            ], className="mb-3"),

            dbc.Button(
                [html.I(className="bi bi-gear-fill me-2"), "Configurar Tarifas"],
                href="/utilities/energy/config",
                color="warning",
                outline=True,
                size="sm",
                className="w-100"
            )
        ], color="warning", className="mb-3"),

        html.Hr(className="my-3"),

        # Nota sobre permissões
        html.Small([
            html.I(className="bi bi-shield-lock-fill me-2"),
            "Acesso restrito a Administradores (Nível 3)."
        ], className="text-muted d-block", style={"fontSize": "0.7rem"}),

    ], style={"padding": "10px"})


def create_default_energy_sidebar_content():
    """
    Sidebar padrão para outras tabs de energia (não SE03).
    Informa que custos estão disponíveis apenas para SE03.

    Returns:
        html.Div: Componente com mensagem informativa
    """
    return html.Div([
        # Título
        html.H6([
            html.I(className="bi bi-lightning-charge-fill me-2"),
            "Energia"
        ], className="text-primary fw-bold mb-3"),

        # Mensagem informativa
        html.P(
            "Custos detalhados de energia elétrica estão disponíveis apenas para a SE03 "
            "(Cortadeiras Transversais/Longitudinais).",
            className="text-muted small mb-3"
        ),

        # Dica visual
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.I(className="bi bi-lightbulb-fill text-warning", style={"fontSize": "1.5rem"}),
                    html.P(
                        "Selecione a tab SE03 para visualizar custos detalhados.",
                        className="small mb-0 mt-2"
                    )
                ], className="text-center")
            ], className="py-3")
        ], color="light", className="mb-3"),

        html.Hr(className="my-3"),

        # Informação adicional
        html.Small([
            html.I(className="bi bi-info-circle me-1"),
            "Análise de custos para outras subestações estará disponível em breve."
        ], className="text-muted d-block", style={"fontSize": "0.7rem"}),

    ], style={"padding": "10px"})
