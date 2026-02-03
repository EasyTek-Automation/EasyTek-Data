# src/pages/maintenance/config.py

"""
Página de Configuração de Metas de Manutenção
==============================================

Permite aos administradores (nível 3) configurar metas de:
- MTBF (Mean Time Between Failures) - Tempo médio entre falhas
- MTTR (Mean Time To Repair) - Tempo médio para reparo
- Taxa de Avaria - Percentual de tempo em falha

Metas podem ser definidas:
1. Globalmente para toda a planta
2. Individualmente por equipamento (sobrescreve metas globais)

Persistência: MongoDB collection AMG_MaintenanceTargets
"""

from dash import html, dcc
import dash_bootstrap_components as dbc


def layout():
    """Layout da página de configuração de metas de manutenção."""

    return dbc.Container([

        # ========================================
        # HEADER DA PÁGINA
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(className="bi bi-sliders me-3"),
                    "Configuração de Metas de Manutenção"
                ], className="mb-3"),

                dbc.Alert([
                    html.I(className="bi bi-shield-lock me-2"),
                    "Esta página é restrita a administradores (Nível 3). ",
                    "As metas configuradas aqui afetam os cálculos e visualizações dos indicadores de manutenção."
                ], color="warning", className="mb-4")
            ])
        ]),

        # ========================================
        # STORE PARA LISTA DE EQUIPAMENTOS
        # ========================================
        dcc.Store(id="maintenance-equipment-list", data=[]),

        # ========================================
        # SEÇÃO 1: METAS GERAIS DA PLANTA
        # ========================================
        dbc.Card([
            dbc.CardHeader([
                html.H4([
                    html.I(className="bi bi-globe me-2"),
                    "Metas Gerais da Planta"
                ], className="mb-0")
            ]),
            dbc.CardBody([
                html.P([
                    "Defina as metas padrão que serão aplicadas a todos os equipamentos. ",
                    "Equipamentos com metas específicas (definidas abaixo) sobrescrevem estas configurações."
                ], className="text-muted mb-3"),

                dbc.Row([
                    # MTBF (horas)
                    dbc.Col([
                        dbc.Label([
                            html.I(className="bi bi-clock-history me-2"),
                            "MTBF (horas)"
                        ]),
                        dbc.Input(
                            id="input-general-mtbf",
                            type="number",
                            placeholder="Ex: 11.30",
                            step=0.01,
                            min=0,
                            className="mb-2"
                        ),
                        html.Small("Tempo médio entre falhas", className="text-muted")
                    ], md=3),

                    # MTTR (minutos)
                    dbc.Col([
                        dbc.Label([
                            html.I(className="bi bi-wrench me-2"),
                            "MTTR (minutos)"
                        ]),
                        dbc.Input(
                            id="input-general-mttr",
                            type="number",
                            placeholder="Ex: 39.00",
                            step=0.01,
                            min=0,
                            className="mb-2"
                        ),
                        html.Small("Tempo médio para reparo", className="text-muted")
                    ], md=3),

                    # Taxa de Avaria (%)
                    dbc.Col([
                        dbc.Label([
                            html.I(className="bi bi-exclamation-triangle me-2"),
                            "Taxa de Avaria (%)"
                        ]),
                        dbc.Input(
                            id="input-general-breakdown-rate",
                            type="number",
                            placeholder="Ex: 5.1",
                            step=0.01,
                            min=0,
                            max=100,
                            className="mb-2"
                        ),
                        html.Small("Percentual de tempo em falha", className="text-muted")
                    ], md=3),

                    # Range de Alerta (%) - NOVO
                    dbc.Col([
                        dbc.Label([
                            html.I(className="bi bi-sliders me-2"),
                            "Range de Alerta (%)"
                        ]),
                        dbc.Input(
                            id="input-general-alert-range",
                            type="number",
                            placeholder="Ex: 3.0",
                            value=3.0,  # Valor padrão
                            step=0.1,
                            min=0.1,
                            max=20,
                            className="mb-2"
                        ),
                        html.Small([
                            "Margem de tolerância para cores ",
                            html.I(className="bi bi-info-circle-fill text-primary",
                                  id="tooltip-alert-range-trigger",
                                  style={"cursor": "pointer"})
                        ], className="text-muted"),
                        dbc.Tooltip(
                            "Define a margem percentual para as cores: "
                            "Verde (melhor e fora da margem), Amarelo (dentro da margem), Vermelho (pior e fora da margem). "
                            "Exemplo: 3% significa que valores dentro de ±3% da meta ficam amarelos.",
                            target="tooltip-alert-range-trigger",
                            placement="top"
                        )
                    ], md=3),
                ])
            ])
        ], className="mb-4"),

        # ========================================
        # SEÇÃO 2: METAS POR EQUIPAMENTO
        # ========================================
        dbc.Card([
            dbc.CardHeader([
                html.H4([
                    html.I(className="bi bi-gear-fill me-2"),
                    "Metas por Equipamento"
                ], className="mb-0")
            ]),
            dbc.CardBody([
                html.P([
                    "Configure metas específicas para equipamentos individuais. ",
                    "Deixe em branco para usar as metas gerais definidas acima."
                ], className="text-muted mb-3"),

                # Spinner enquanto carrega equipamentos
                dbc.Spinner(
                    html.Div(id="equipment-targets-container"),
                    color="primary",
                    size="sm",
                    spinner_style={"marginTop": "1rem"}
                )
            ])
        ], className="mb-4"),

        # ========================================
        # BOTÕES DE AÇÃO
        # ========================================
        dbc.Row([
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button([
                        html.I(className="bi bi-save me-2"),
                        "Salvar Configuração"
                    ], id="btn-save-maintenance-config", color="primary", size="lg"),

                    dbc.Button([
                        html.I(className="bi bi-arrow-clockwise me-2"),
                        "Redefinir"
                    ], id="btn-reset-maintenance-config", color="secondary", size="lg", outline=True)
                ], className="w-100")
            ])
        ], className="mb-4"),

        # ========================================
        # ÁREA DE ALERTAS
        # ========================================
        html.Div(id="maintenance-config-alert"),

        # ========================================
        # CARD INFORMATIVO
        # ========================================
        dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-info-circle me-2"),
                "Informações sobre as Metas"
            ]),
            dbc.CardBody([
                html.Ul([
                    html.Li([
                        html.Strong("MTBF (Mean Time Between Failures): "),
                        "Indica a confiabilidade do equipamento. Valores maiores indicam menor frequência de falhas."
                    ]),
                    html.Li([
                        html.Strong("MTTR (Mean Time To Repair): "),
                        "Indica a eficiência da manutenção. Valores menores indicam reparos mais rápidos."
                    ]),
                    html.Li([
                        html.Strong("Taxa de Avaria: "),
                        "Percentual do tempo em que o equipamento está parado devido a falhas. ",
                        "Calculado como: (MTTR / (MTBF + MTTR)) × 100%"
                    ]),
                    html.Li([
                        html.Strong("Hierarquia de Metas: "),
                        "Equipamentos com metas específicas têm prioridade sobre as metas gerais. ",
                        "Se um equipamento não tiver meta definida, usa-se a meta geral."
                    ]),
                    html.Li([
                        html.Strong("Unidades: "),
                        "MTBF em horas, MTTR em minutos, Taxa de Avaria em percentual (0-100%)."
                    ])
                ])
            ])
        ], color="light", outline=True)

    ], fluid=True, className="p-4")
