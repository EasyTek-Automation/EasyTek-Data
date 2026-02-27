# src/callbacks_registers/se03_telemetry_callbacks.py

"""
Callbacks para a página de telemetria ao vivo da SE03.
Busca dados em tempo real da coleção AMG_EnergyTelemetry e atualiza
KPI cards e gráficos de tendência.
"""

from datetime import datetime, timedelta, timezone

from dash import Input, Output, html, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go


# ─────────────────────────────────────────
# Helpers de serialização / deserialização
# ─────────────────────────────────────────

def _serialize_docs(docs):
    """Converte lista de documentos MongoDB para lista de dicts serializáveis em JSON."""
    result = []
    for doc in docs:
        row = {}
        for k, v in doc.items():
            if k == "_id":
                row["_id"] = str(v)
            elif isinstance(v, datetime):
                row[k] = v.isoformat()
            else:
                row[k] = v
        result.append(row)
    return result


def _get_latest_by_machine(data: list) -> dict:
    """Retorna o registro mais recente por IDMaq."""
    latest = {}
    for row in data:
        maq = row.get("IDMaq", "")
        ts = row.get("DateTime", "")
        if maq not in latest or ts > latest[maq].get("DateTime", ""):
            latest[maq] = row
    return latest


# ─────────────────────────────────────────
# Funções de render dos KPI cards
# ─────────────────────────────────────────

def _render_fp_card(value):
    """Renderiza conteúdo do card de Fator de Potência com código de cor."""
    if value is None:
        return [html.Span("—", className="fs-3 fw-bold text-muted")]

    if value >= 0.92:
        color = "success"
        icon = "bi-check-circle-fill"
    elif value >= 0.85:
        color = "warning"
        icon = "bi-exclamation-circle-fill"
    else:
        color = "danger"
        icon = "bi-x-circle-fill"

    return [
        html.Span(f"{value:.3f}", className=f"fs-3 fw-bold text-{color}"),
        html.I(className=f"bi {icon} text-{color} ms-2"),
    ]


def _render_value_card(value, decimals=1):
    """Renderiza valor numérico simples em bold."""
    if value is None:
        return [html.Span("—", className="fs-3 fw-bold text-muted")]
    return [html.Span(f"{value:,.{decimals}f}", className="fs-3 fw-bold")]


# ─────────────────────────────────────────
# Figura vazia para gráficos sem dados
# ─────────────────────────────────────────

def _empty_fig(message="Aguardando dados…"):
    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.5,
        text=f"<b>{message}</b>",
        showarrow=False,
        xref="paper", yref="paper",
        xanchor="center", yanchor="middle",
        font=dict(size=16, color="#6c757d"),
    )
    fig.update_layout(
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        margin=dict(l=20, r=20, t=30, b=20),
        height=300,
        hovermode=False,
    )
    return fig


# ─────────────────────────────────────────
# Registro dos callbacks
# ─────────────────────────────────────────

def register_se03_telemetry_callbacks(app, collection):
    """
    Registra os callbacks de telemetria da SE03.

    Args:
        app: instância Dash
        collection: coleção MongoDB AMG_EnergyTelemetry
    """

    # ── Callback 1: Fetch de dados → Store ──────────────────────────────────

    @app.callback(
        Output("store-se03-telemetry", "data"),
        Input("interval-component", "n_intervals"),
        Input("se03-tel-machine-sel", "value"),
        Input("se03-tel-window", "value"),
        Input("url", "pathname"),
        prevent_initial_call=True,
    )
    def fetch_se03_telemetry(n_intervals, machines, window_min, pathname):
        """Busca dados de telemetria apenas quando na página SE03."""
        if pathname != "/utilities/energy/se03":
            raise PreventUpdate

        if collection is None:
            return None

        selected = machines or ["SE03_MM01"]
        minutes = window_min or 15

        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=minutes)

        try:
            docs = list(
                collection.find(
                    {
                        "DateTime": {"$gte": start},
                        "IDMaq": {"$in": selected},
                    },
                    {
                        "_id": 0,
                        "DateTime": 1,
                        "IDMaq": 1,
                        "FatorPotenciaTotal": 1,
                        "PotenciaAtivaMaxPeriodo": 1,
                        "PotenciaReativaMaxPeriodo": 1,
                        "PotenciaAtivaAccImport": 1,
                    },
                ).sort("DateTime", 1)
            )
        except Exception:
            return None

        return _serialize_docs(docs)

    # ── Callback 2: KPI Cards + timestamp ───────────────────────────────────

    @app.callback(
        Output("se03-tel-card-fp", "children"),
        Output("se03-tel-card-pot-ativa", "children"),
        Output("se03-tel-card-pot-reativa", "children"),
        Output("se03-tel-card-energia", "children"),
        Output("se03-telemetry-last-update", "children"),
        Input("store-se03-telemetry", "data"),
    )
    def update_kpi_cards(data):
        """Atualiza cards com os valores mais recentes."""
        if not data:
            empty = [html.Span("—", className="fs-3 fw-bold text-muted")]
            return empty, empty, empty, empty, "—"

        latest = _get_latest_by_machine(data)

        # Agrega: usa MM01 se disponível, senão primeiro disponível
        row = latest.get("SE03_MM01") or next(iter(latest.values()), {})

        fp = row.get("FatorPotenciaTotal")
        pot_ativa_w = row.get("PotenciaAtivaMaxPeriodo")
        pot_reativa_w = row.get("PotenciaReativaMaxPeriodo")
        energia_wh = row.get("PotenciaAtivaAccImport")

        # Converter W → kW e Wh → kWh
        pot_ativa = pot_ativa_w / 1000 if pot_ativa_w is not None else None
        pot_reativa = pot_reativa_w / 1000 if pot_reativa_w is not None else None
        energia = energia_wh / 1000 if energia_wh is not None else None

        # Timestamp da última atualização (hora local)
        ts_str = row.get("DateTime", "")
        try:
            ts_dt = datetime.fromisoformat(ts_str)
            last_update = ts_dt.strftime("%H:%M:%S")
        except Exception:
            last_update = "—"

        return (
            _render_fp_card(fp),
            _render_value_card(pot_ativa),
            _render_value_card(pot_reativa),
            _render_value_card(energia, decimals=2),
            last_update,
        )

    # ── Callback 3: Gráfico Fator de Potência ───────────────────────────────

    @app.callback(
        Output("se03-tel-graph-fp", "figure"),
        Input("store-se03-telemetry", "data"),
    )
    def update_fp_graph(data):
        """Plota FatorPotenciaTotal por IDMaq com linha de threshold em 0.92."""
        if not data:
            return _empty_fig("Aguardando dados de telemetria…")

        # Agrupar por IDMaq
        series: dict[str, list] = {}
        for row in data:
            maq = row.get("IDMaq", "Desconhecido")
            fp = row.get("FatorPotenciaTotal")
            dt_str = row.get("DateTime", "")
            if fp is None:
                continue
            try:
                dt = datetime.fromisoformat(dt_str)
            except Exception:
                continue
            series.setdefault(maq, {"x": [], "y": []})
            series[maq]["x"].append(dt)
            series[maq]["y"].append(fp)

        if not series:
            return _empty_fig("Sem dados de Fator de Potência no período")

        fig = go.Figure()

        for maq, pts in series.items():
            fig.add_trace(go.Scatter(
                x=pts["x"],
                y=pts["y"],
                mode="lines",
                name=maq,
                line=dict(width=2),
            ))

        # Linha de threshold ANEEL 0.92
        if series:
            all_x = [x for pts in series.values() for x in pts["x"]]
            x_min, x_max = min(all_x), max(all_x)
            fig.add_trace(go.Scatter(
                x=[x_min, x_max],
                y=[0.92, 0.92],
                mode="lines",
                name="Threshold (0.92)",
                line=dict(color="red", dash="dash", width=1.5),
                showlegend=True,
            ))

        fig.update_layout(
            margin=dict(l=40, r=20, t=20, b=40),
            height=300,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="FP", range=[0.7, 1.05]),
            xaxis=dict(title="Hora"),
        )
        return fig

    # ── Callback 4: Gráfico Potência Ativa ──────────────────────────────────

    @app.callback(
        Output("se03-tel-graph-potencia", "figure"),
        Input("store-se03-telemetry", "data"),
    )
    def update_potencia_graph(data):
        """Plota PotenciaAtivaMaxPeriodo (kW) por IDMaq."""
        if not data:
            return _empty_fig("Aguardando dados de telemetria…")

        series: dict[str, list] = {}
        for row in data:
            maq = row.get("IDMaq", "Desconhecido")
            pot_w = row.get("PotenciaAtivaMaxPeriodo")
            dt_str = row.get("DateTime", "")
            if pot_w is None:
                continue
            try:
                dt = datetime.fromisoformat(dt_str)
            except Exception:
                continue
            kw = pot_w / 1000
            series.setdefault(maq, {"x": [], "y": []})
            series[maq]["x"].append(dt)
            series[maq]["y"].append(kw)

        if not series:
            return _empty_fig("Sem dados de Potência Ativa no período")

        fig = go.Figure()

        for maq, pts in series.items():
            fig.add_trace(go.Scatter(
                x=pts["x"],
                y=pts["y"],
                mode="lines",
                name=maq,
                line=dict(width=2),
            ))

        fig.update_layout(
            margin=dict(l=40, r=20, t=20, b=40),
            height=300,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="kW"),
            xaxis=dict(title="Hora"),
        )
        return fig
