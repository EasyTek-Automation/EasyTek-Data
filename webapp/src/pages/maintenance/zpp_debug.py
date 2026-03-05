"""
Página de Debug ZPP — Comparador MongoDB vs Planilha
Ferramenta temporária de diagnóstico para identificar registros
presentes apenas no Mongo ou apenas na planilha exportada do SAP.
"""
from dash import html, dcc
import dash_bootstrap_components as dbc


PROD_FIELDS = [
    {"label": "ordem",                    "value": "ordem"},
    {"label": "pto_trab (equipamento)",   "value": "pto_trab"},
    {"label": "fininotif (data início)",  "value": "fininotif"},
    {"label": "ffinnotif (data fim)",     "value": "ffinnotif"},
    {"label": "horasact",                 "value": "horasact"},
]

PAR_FIELDS = [
    {"label": "ordem",                              "value": "ordem"},
    {"label": "centro_de_trabalho (equipamento)",   "value": "centro_de_trabalho"},
    {"label": "inicio_execucao (datetime)",         "value": "inicio_execucao"},
    {"label": "fim_execucao (datetime)",            "value": "fim_execucao"},
    {"label": "inicio_real_hora (HH:MM:SS)",        "value": "inicio_real_hora"},
    {"label": "causa_do_desvio (motivo)",           "value": "causa_do_desvio"},
    {"label": "duration_min",                       "value": "duration_min"},
]

DATE_FORMATS = [
    {"label": "DD.MM.AAAA HH:MM:SS  (SAP padrão)", "value": "%d.%m.%Y %H:%M:%S"},
    {"label": "DD/MM/AAAA HH:MM:SS",               "value": "%d/%m/%Y %H:%M:%S"},
    {"label": "AAAA-MM-DD HH:MM:SS  (ISO)",         "value": "%Y-%m-%d %H:%M:%S"},
    {"label": "DD.MM.AAAA HH:MM  (sem segundos)",  "value": "%d.%m.%Y %H:%M"},
    {"label": "DD/MM/AAAA  (só data)",              "value": "%d/%m/%Y"},
    {"label": "DD.MM.AAAA  (só data)",              "value": "%d.%m.%Y"},
]


def _tab_content(fields, default_fields, fields_id, date_fmt_id,
                 textarea_id, formula_id, btn_id, result_id):
    return html.Div([
        dbc.Row([
            # Coluna esquerda: campos + formato
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([html.I(className="bi bi-key me-2"), html.Strong("Campos da chave")]),
                    dbc.CardBody([
                        dbc.Checklist(
                            id=fields_id,
                            options=fields,
                            value=default_fields,
                            labelStyle={"display": "block", "marginBottom": "6px"},
                        ),
                        html.Hr(className="my-2"),
                        html.Small("Formato para campos datetime:", className="text-muted d-block mb-1"),
                        dcc.Dropdown(
                            id=date_fmt_id,
                            options=DATE_FORMATS,
                            value="%d.%m.%Y %H:%M:%S",
                            clearable=False,
                            style={"fontSize": "0.82rem"},
                        ),
                    ])
                ], className="shadow-sm h-100")
            ], md=4),

            # Coluna direita: fórmula + textarea
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([html.I(className="bi bi-clipboard me-2"), html.Strong("Colar chaves da planilha")]),
                    dbc.CardBody([
                        dbc.Alert(id=formula_id, color="light",
                                  className="py-2 mb-2 small font-monospace",
                                  style={"wordBreak": "break-all"}),
                        dcc.Textarea(
                            id=textarea_id,
                            placeholder="Cole aqui — um registro por linha.\nExemplo:\n4500012345\n4500012346",
                            style={"width": "100%", "height": "220px",
                                   "fontFamily": "monospace", "fontSize": "0.82rem",
                                   "resize": "vertical"},
                        ),
                    ])
                ], className="shadow-sm h-100")
            ], md=8),
        ], className="mb-3 mt-3"),

        dbc.Alert([
            html.I(className="bi bi-info-circle me-2"),
            "O Mongo descarta equipamentos com prefixo ",
            html.Code("EMBAL"), " e ", html.Code("EMBBOBCP"),
            ". Registros desses equipamentos na planilha aparecerão como \"apenas na planilha\" — é esperado.",
        ], color="info", className="py-2 small mb-3"),

        dbc.Button(
            [html.I(className="bi bi-search me-2"), "Comparar"],
            id=btn_id, color="primary", className="mb-4",
        ),

        html.Div(id=result_id),
    ])


def layout():
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(className="bi bi-bug me-3", style={"color": "#dc3545"}),
                    "Debug ZPP — Comparador MongoDB vs Planilha"
                ], className="mb-2"),
                html.P(
                    "Identifica registros presentes apenas no MongoDB ou apenas na planilha exportada do SAP.",
                    className="text-muted"
                )
            ])
        ], className="mb-3"),

        dbc.Tabs([
            dbc.Tab(label="ZPP_Producao", tab_id="tab-debug-prod",
                    children=_tab_content(
                        fields=PROD_FIELDS, default_fields=["ordem"],
                        fields_id="debug-fields-prod", date_fmt_id="debug-date-fmt-prod",
                        textarea_id="debug-textarea-prod", formula_id="debug-formula-prod",
                        btn_id="btn-debug-compare-prod", result_id="debug-result-prod",
                    )),
            dbc.Tab(label="ZPP_Paradas", tab_id="tab-debug-par",
                    children=_tab_content(
                        fields=PAR_FIELDS, default_fields=["ordem", "centro_de_trabalho"],
                        fields_id="debug-fields-par", date_fmt_id="debug-date-fmt-par",
                        textarea_id="debug-textarea-par", formula_id="debug-formula-par",
                        btn_id="btn-debug-compare-par", result_id="debug-result-par",
                    )),
        ]),

    ], fluid=True, className="p-4")
