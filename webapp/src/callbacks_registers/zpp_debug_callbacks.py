"""
Callbacks para a página de Debug ZPP.
Compara chaves do MongoDB com chaves coladas pelo usuário (extraídas da planilha SAP).
"""
from dash import html, Input, Output, State, dash_table
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

SEP = "|"

# Campos exibidos no resultado para cada collection (independente dos campos de chave)
PROD_DISPLAY_FIELDS = ["ordem", "pto_trab", "fininotif", "ffinnotif", "horasact"]
PAR_DISPLAY_FIELDS  = ["ordem", "centro_de_trabalho", "inicio_execucao", "fim_execucao",
                       "inicio_real_hora", "causa_do_desvio", "duration_min"]

DATETIME_FIELDS = {"fininotif", "ffinnotif", "inicio_execucao", "fim_execucao"}


def _fmt_val(v, field, date_fmt):
    """Formata um valor do MongoDB para string comparável."""
    if v is None:
        return ""
    if field in DATETIME_FIELDS and isinstance(v, datetime):
        return v.strftime(date_fmt)
    return str(v).strip()


def _build_mongo_index(collection_name, key_fields, date_fmt, display_fields):
    """
    Busca todos os documentos da collection e constrói:
      - key_to_doc: {chave_composta: doc_dict}  (para lookup dos registros extras)
      - keyset: set de chaves compostas
    """
    from src.database.connection import get_mongo_connection

    col = get_mongo_connection(collection_name)
    projection = {f: 1 for f in set(key_fields + display_fields)}
    projection["_id"] = 0

    docs = list(col.find({}, projection))

    key_to_doc = {}
    for doc in docs:
        parts = [_fmt_val(doc.get(f), f, date_fmt) for f in key_fields]
        key = SEP.join(parts)
        key_to_doc[key] = doc

    return key_to_doc


def _parse_pasted(text):
    """Extrai set de chaves de um texto colado (uma por linha)."""
    if not text:
        return set()
    return {line.strip() for line in text.splitlines() if line.strip()}


def _fmt_date_in_doc(doc, date_fmt):
    """Formata todos os campos datetime de um doc para string exibível."""
    out = {}
    for k, v in doc.items():
        if isinstance(v, datetime):
            out[k] = v.strftime(date_fmt)
        else:
            out[k] = v
    return out


def _result_component(only_mongo, only_sheet, total_mongo, total_sheet,
                      key_fields, date_fmt, display_fields):
    """Monta o componente de resultado."""
    common = total_mongo - len(only_mongo)

    # Cards de resumo
    summary = dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div(str(total_mongo), className="fs-4 fw-bold text-primary"),
            html.Small("no MongoDB", className="text-muted"),
        ]), className="text-center shadow-sm"), xs=6, md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div(str(total_sheet), className="fs-4 fw-bold text-secondary"),
            html.Small("na planilha", className="text-muted"),
        ]), className="text-center shadow-sm"), xs=6, md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div(str(len(only_mongo)),
                     className=f"fs-4 fw-bold {'text-danger' if only_mongo else 'text-success'}"),
            html.Small("apenas no Mongo", className="text-muted"),
        ]), className="text-center shadow-sm"), xs=6, md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div(str(len(only_sheet)),
                     className=f"fs-4 fw-bold {'text-warning' if only_sheet else 'text-success'}"),
            html.Small("apenas na planilha", className="text-muted"),
        ]), className="text-center shadow-sm"), xs=6, md=3),
    ], className="g-2 mb-4")

    blocks = [summary]

    # Tabela: apenas no Mongo
    if only_mongo:
        rows = [_fmt_date_in_doc(doc, date_fmt) for doc in only_mongo]
        cols = [{"name": f, "id": f} for f in display_fields if any(f in r for r in rows)]
        blocks.append(dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-database-fill me-2 text-danger"),
                html.Strong(f"Apenas no MongoDB ({len(only_mongo)} registro(s))")
            ]),
            dbc.CardBody(
                dash_table.DataTable(
                    columns=cols, data=rows,
                    sort_action="native", page_size=50,
                    style_table={"overflowX": "auto"},
                    style_cell={"fontSize": "0.82rem", "padding": "6px 10px",
                                "fontFamily": "inherit"},
                    style_header={"backgroundColor": "#f8d7da", "fontWeight": "bold",
                                  "fontSize": "0.78rem"},
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"}
                    ],
                ),
                style={"padding": "0.5rem"}
            )
        ], className="shadow-sm mb-3"))
    else:
        blocks.append(dbc.Alert(
            [html.I(className="bi bi-check-circle me-2"),
             "Nenhum registro exclusivo no MongoDB — todos estão na planilha."],
            color="success", className="py-2 mb-3"
        ))

    # Lista: apenas na planilha
    if only_sheet:
        items = [html.Li(html.Code(k), style={"marginBottom": "3px"}) for k in sorted(only_sheet)]
        blocks.append(dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-file-earmark-spreadsheet me-2 text-warning"),
                html.Strong(f"Apenas na planilha ({len(only_sheet)} registro(s))")
            ]),
            dbc.CardBody(
                html.Ul(items, style={"fontFamily": "monospace", "fontSize": "0.82rem",
                                      "maxHeight": "300px", "overflowY": "auto",
                                      "paddingLeft": "1.2rem", "marginBottom": 0})
            )
        ], className="shadow-sm mb-3"))
    else:
        blocks.append(dbc.Alert(
            [html.I(className="bi bi-check-circle me-2"),
             "Nenhum registro exclusivo na planilha — todos estão no MongoDB."],
            color="success", className="py-2 mb-3"
        ))

    return html.Div(blocks)


def _formula_hint(fields, field_options, date_fmt):
    """Gera dica de fórmula Excel para os campos selecionados."""
    if not fields:
        return "Selecione pelo menos um campo."

    label_map = {f["value"]: f["label"] for f in field_options}
    parts = []
    for f in fields:
        label = label_map.get(f, f)
        if f in DATETIME_FIELDS:
            # Converter strftime para formato Excel TEXT()
            excel_fmt = (date_fmt
                         .replace("%d", "DD").replace("%m", "MM").replace("%Y", "AAAA")
                         .replace("%H", "hh").replace("%M", "mm").replace("%S", "ss"))
            parts.append(f'TEXT([col_{f}],"{excel_fmt}")')
        else:
            parts.append(f"[col_{f}]")

    if len(parts) == 1:
        formula = f"={parts[0]}"
    else:
        formula = "=" + f'&"{SEP}"&'.join(parts)

    return f"Fórmula Excel:  {formula}"


def register_zpp_debug_callbacks(app):

    # ── Hints de fórmula ─────────────────────────────────────────────

    from src.pages.maintenance.zpp_debug import PROD_FIELDS, PAR_FIELDS

    @app.callback(
        Output("debug-formula-prod", "children"),
        [Input("debug-fields-prod", "value"),
         Input("debug-date-fmt-prod", "value")],
    )
    def update_formula_prod(fields, date_fmt):
        return _formula_hint(fields or [], PROD_FIELDS, date_fmt or "%d.%m.%Y %H:%M:%S")

    @app.callback(
        Output("debug-formula-par", "children"),
        [Input("debug-fields-par", "value"),
         Input("debug-date-fmt-par", "value")],
    )
    def update_formula_par(fields, date_fmt):
        return _formula_hint(fields or [], PAR_FIELDS, date_fmt or "%d.%m.%Y %H:%M:%S")

    # ── Comparação Produção ──────────────────────────────────────────

    @app.callback(
        Output("debug-result-prod", "children"),
        Input("btn-debug-compare-prod", "n_clicks"),
        [State("debug-fields-prod", "value"),
         State("debug-date-fmt-prod", "value"),
         State("debug-textarea-prod", "value")],
        prevent_initial_call=True,
    )
    def compare_producao(n_clicks, fields, date_fmt, pasted):
        if not fields:
            return dbc.Alert("Selecione pelo menos um campo.", color="warning")
        if not pasted or not pasted.strip():
            return dbc.Alert("Cole os dados da planilha antes de comparar.", color="warning")

        date_fmt = date_fmt or "%d.%m.%Y %H:%M:%S"
        pasted_keys = _parse_pasted(pasted)

        try:
            key_to_doc = _build_mongo_index("ZPP_Producao", fields, date_fmt, PROD_DISPLAY_FIELDS)
        except Exception as e:
            return dbc.Alert(f"Erro ao consultar MongoDB: {e}", color="danger")

        mongo_keys = set(key_to_doc.keys())
        only_mongo_docs = [key_to_doc[k] for k in (mongo_keys - pasted_keys)]
        only_sheet      = pasted_keys - mongo_keys

        return _result_component(
            only_mongo=only_mongo_docs,
            only_sheet=only_sheet,
            total_mongo=len(mongo_keys),
            total_sheet=len(pasted_keys),
            key_fields=fields,
            date_fmt=date_fmt,
            display_fields=PROD_DISPLAY_FIELDS,
        )

    # ── Comparação Paradas ───────────────────────────────────────────

    @app.callback(
        Output("debug-result-par", "children"),
        Input("btn-debug-compare-par", "n_clicks"),
        [State("debug-fields-par", "value"),
         State("debug-date-fmt-par", "value"),
         State("debug-textarea-par", "value")],
        prevent_initial_call=True,
    )
    def compare_paradas(n_clicks, fields, date_fmt, pasted):
        if not fields:
            return dbc.Alert("Selecione pelo menos um campo.", color="warning")
        if not pasted or not pasted.strip():
            return dbc.Alert("Cole os dados da planilha antes de comparar.", color="warning")

        date_fmt = date_fmt or "%d.%m.%Y %H:%M:%S"
        pasted_keys = _parse_pasted(pasted)

        try:
            key_to_doc = _build_mongo_index("ZPP_Paradas", fields, date_fmt, PAR_DISPLAY_FIELDS)
        except Exception as e:
            return dbc.Alert(f"Erro ao consultar MongoDB: {e}", color="danger")

        mongo_keys = set(key_to_doc.keys())
        only_mongo_docs = [key_to_doc[k] for k in (mongo_keys - pasted_keys)]
        only_sheet      = pasted_keys - mongo_keys

        return _result_component(
            only_mongo=only_mongo_docs,
            only_sheet=only_sheet,
            total_mongo=len(mongo_keys),
            total_sheet=len(pasted_keys),
            key_fields=fields,
            date_fmt=date_fmt,
            display_fields=PAR_DISPLAY_FIELDS,
        )
