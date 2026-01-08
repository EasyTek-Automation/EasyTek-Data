# src/pages/energy/config.py

"""
Página de configuração de tarifas de energia elétrica.
Permite administradores (Nível 3) configurar:
- Custos de demanda contratada (ponta e fora ponta)
- Tarifas TUSD e energia (ponta e fora ponta)
- Horário de ponta
"""

from dash import html, dcc
import dash_bootstrap_components as dbc


def layout():
    """
    Layout da página de configuração de tarifas de energia.
    Acesso restrito a usuários Nível 3 (Administradores).
    """
    return dbc.Container([

        # ========================================
        # HEADER DA PÁGINA
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(className="bi bi-gear-fill me-2"),
                    "Configuração de Tarifas de Energia"
                ]),
                html.P(
                    "Configure os preços e horários para cálculo de custos de energia elétrica",
                    className="text-muted"
                ),
                dbc.Alert([
                    html.I(className="bi bi-shield-lock-fill me-2"),
                    "Acesso restrito a Administradores (Nível 3)"
                ], color="info", className="mt-2")
            ])
        ], className="mb-4"),

        # ========================================
        # FORMULÁRIO DE CONFIGURAÇÃO
        # ========================================
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # ========================================
                    # COLUNA 1: CUSTOS DE DEMANDA
                    # ========================================
                    dbc.Col([
                        html.H5([
                            html.I(className="bi bi-lightning-charge-fill me-2 text-warning"),
                            "Custos de Demanda"
                        ], className="mb-3"),

                        # Demanda Ponta
                        html.Label("Custo Demanda Contratada Ponta", className="fw-bold mb-1"),
                        dbc.InputGroup([
                            dbc.InputGroupText("R$"),
                            dbc.Input(
                                id="input-demanda-ponta",
                                type="number",
                                placeholder="0.00",
                                min=0,
                                step="any"
                            )
                        ], className="mb-2"),
                        html.Small("Custo mensal da demanda contratada no horário de ponta", className="text-muted d-block mb-3"),

                        # Demanda Fora de Ponta
                        html.Label("Custo Demanda Contratada Fora de Ponta", className="fw-bold mb-1"),
                        dbc.InputGroup([
                            dbc.InputGroupText("R$"),
                            dbc.Input(
                                id="input-demanda-fora-ponta",
                                type="number",
                                placeholder="0.00",
                                min=0,
                                step="any"
                            )
                        ], className="mb-2"),
                        html.Small("Custo mensal da demanda contratada fora do horário de ponta", className="text-muted d-block mb-3"),

                        html.Hr(className="my-3"),

                        # Demanda Contratada Ponta (kW)
                        html.Label("Demanda Contratada Ponta", className="fw-bold mb-1"),
                        dbc.InputGroup([
                            dbc.Input(
                                id="input-demanda-contratada-ponta",
                                type="number",
                                placeholder="0.00",
                                min=0,
                                step="any"
                            ),
                            dbc.InputGroupText("kW")
                        ], className="mb-2"),
                        html.Small("Limite de demanda contratada no horário de ponta", className="text-muted d-block mb-3"),

                        # Demanda Contratada Fora de Ponta (kW)
                        html.Label("Demanda Contratada Fora de Ponta", className="fw-bold mb-1"),
                        dbc.InputGroup([
                            dbc.Input(
                                id="input-demanda-contratada-fora-ponta",
                                type="number",
                                placeholder="0.00",
                                min=0,
                                step="any"
                            ),
                            dbc.InputGroupText("kW")
                        ], className="mb-2"),
                        html.Small("Limite de demanda contratada fora do horário de ponta", className="text-muted d-block mb-3"),

                    ], md=6, className="border-end"),

                    # ========================================
                    # COLUNA 2: TARIFAS DE CONSUMO
                    # ========================================
                    dbc.Col([
                        html.H5([
                            html.I(className="bi bi-cash-stack me-2 text-success"),
                            "Tarifas de Consumo"
                        ], className="mb-3"),

                        # TUSD Ponta
                        html.Label("Preço TUSD Ponta", className="fw-bold mb-1"),
                        dbc.InputGroup([
                            dbc.Input(
                                id="input-tusd-ponta",
                                type="number",
                                placeholder="0.00000000",
                                min=0,
                                step="any"
                            ),
                            dbc.InputGroupText("R$/kWh")
                        ], className="mb-2"),
                        html.Small("Tarifa de Uso do Sistema de Distribuição - Ponta", className="text-muted d-block mb-3"),

                        # TUSD Fora de Ponta
                        html.Label("Preço TUSD Fora de Ponta", className="fw-bold mb-1"),
                        dbc.InputGroup([
                            dbc.Input(
                                id="input-tusd-fora-ponta",
                                type="number",
                                placeholder="0.00000000",
                                min=0,
                                step="any"
                            ),
                            dbc.InputGroupText("R$/kWh")
                        ], className="mb-2"),
                        html.Small("Tarifa de Uso do Sistema de Distribuição - Fora de Ponta", className="text-muted d-block mb-3"),

                        html.Hr(className="my-3"),

                        # Energia Ponta
                        html.Label("Preço Energia Ponta", className="fw-bold mb-1"),
                        dbc.InputGroup([
                            dbc.Input(
                                id="input-energia-ponta",
                                type="number",
                                placeholder="0.00000000",
                                min=0,
                                step="any"
                            ),
                            dbc.InputGroupText("R$/kWh")
                        ], className="mb-2"),
                        html.Small("Tarifa de energia elétrica - Ponta", className="text-muted d-block mb-3"),

                        # Energia Fora de Ponta
                        html.Label("Preço Energia Fora de Ponta", className="fw-bold mb-1"),
                        dbc.InputGroup([
                            dbc.Input(
                                id="input-energia-fora-ponta",
                                type="number",
                                placeholder="0.00000000",
                                min=0,
                                step="any"
                            ),
                            dbc.InputGroupText("R$/kWh")
                        ], className="mb-2"),
                        html.Small("Tarifa de energia elétrica - Fora de Ponta", className="text-muted d-block mb-3"),

                    ], md=6),
                ]),

                html.Hr(className="my-4"),

                # ========================================
                # SEÇÃO: HORÁRIO DE PONTA
                # ========================================
                dbc.Row([
                    dbc.Col([
                        html.H5([
                            html.I(className="bi bi-clock-fill me-2 text-danger"),
                            "Horário de Ponta"
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Horário de Início", className="fw-bold mb-1"),
                                dbc.Input(
                                    id="input-horario-inicio",
                                    type="time",
                                    value="18:00"
                                ),
                                html.Small("Início do horário de ponta", className="text-muted d-block mt-1")
                            ], md=6),

                            dbc.Col([
                                html.Label("Horário de Término", className="fw-bold mb-1"),
                                dbc.Input(
                                    id="input-horario-fim",
                                    type="time",
                                    value="21:00"
                                ),
                                html.Small("Fim do horário de ponta", className="text-muted d-block mt-1")
                            ], md=6),
                        ]),

                        # Indicador visual do período de ponta
                        dbc.Card([
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="bi bi-info-circle me-2"),
                                    html.Span(id="horario-ponta-preview", children="Horário de ponta: 18:00 às 21:00")
                                ], className="text-center")
                            ])
                        ], color="light", className="mt-3")

                    ])
                ]),

                html.Hr(className="my-4"),

                # ========================================
                # BOTÕES DE AÇÃO
                # ========================================
                dbc.Row([
                    dbc.Col([
                        dbc.ButtonGroup([
                            dbc.Button(
                                [html.I(className="bi bi-check-circle-fill me-2"), "Salvar Configuração"],
                                id="btn-save-config",
                                color="success",
                                size="lg",
                                className="px-5"
                            ),
                            dbc.Button(
                                [html.I(className="bi bi-arrow-clockwise me-2"), "Redefinir"],
                                id="btn-reset-config",
                                color="warning",
                                outline=True,
                                size="lg"
                            ),
                        ], className="d-flex justify-content-center w-100")
                    ])
                ]),

                # ========================================
                # ÁREA DE ALERTAS
                # ========================================
                html.Div(id="config-alert", className="mt-4")

            ], className="p-4")
        ], className="shadow-lg"),

        # ========================================
        # INFORMAÇÕES ADICIONAIS
        # ========================================
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6([
                            html.I(className="bi bi-lightbulb-fill me-2 text-warning"),
                            "Dicas de Preenchimento"
                        ], className="mb-3"),

                        html.Ul([
                            html.Li("Todos os valores devem ser maiores ou iguais a zero"),
                            html.Li("Custos de demanda são valores mensais fixos cobrados pela concessionária"),
                            html.Li("Tarifas TUSD e Energia são cobradas por kWh consumido"),
                            html.Li("O horário de ponta pode ser configurado conforme contrato com a concessionária"),
                            html.Li("Horários noturnos (ex: 23:00 às 06:00) são suportados automaticamente"),
                        ], className="text-muted small mb-0")
                    ])
                ], color="light", className="mt-4")
            ])
        ])

    ], fluid=True, className="p-4")
