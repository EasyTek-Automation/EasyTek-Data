# src/callbacks_registers/analise_falhas_callbacks.py

"""
Callbacks da página Análise de Falhas (/maintenance/analise-de-falhas).

Replica os mecanismos da indicators-v2:
- i18n PT/ES/EN (bandeiras `af-lang-btn` → `store-af-lang` → traduz textos);
- filtros em dois estágios: Aplicar/Atualizar/`url.pathname` escrevem
  `store-af-filters`; o callback de render reage ao store e busca os dados.

Dados: readers de `utils/zpp_kpi_calculator` sobre a coleção fixa `ZPP_Paradas`.
Todos os ids têm prefixo `af-` (não colidem com os callbacks da v2).
"""

import io
import logging
import datetime

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import dash
from dash import html, dcc, dash_table, no_update, ALL
from dash.dependencies import Input, Output, State

from src.pages.maintenance.analise_de_falhas import TRANS
from src.utils.email_templates import enviar_email_template
from src.utils.failure_events import (
    FAIXAS_DURACAO, GATILHO_MODO_ACIMA, GATILHO_MODO_TODAS,
    ano_padrao, ano_valido, faixa_duracao, faixas_ativas,
)
from src.utils.zpp_kpi_calculator import (
    BREAKDOWN_CODES,
    fetch_zpp_breakdown_data,
    fetch_zpp_equipment_list,
    fetch_top_breakdowns_all,
)

logger = logging.getLogger(__name__)

ROUTE = "/maintenance/analise-de-falhas"
ACCENT = "#c0392b"
ACCENT_EQUIP = "#fd7e14"

# (span_id, chave em TRANS) — children traduzidos
I18N_OUTPUTS = [
    ("af-i18n-title", "title"), ("af-i18n-subtitle", "subtitle"), ("af-i18n-beta", "beta_badge"),
    ("af-i18n-btn-sendmail", "btn_sendmail"),
    ("af-i18n-btn-refresh", "btn_refresh"), ("af-i18n-btn-filters", "btn_filters"),
    ("af-i18n-btn-export", "btn_export"), ("af-i18n-btn-apply", "btn_apply"),
    ("af-i18n-filter-period", "filter_period"), ("af-i18n-filter-year", "filter_year"),
    ("af-i18n-filter-range", "filter_range"), ("af-i18n-filter-equip", "filter_equip"),
    ("af-i18n-filter-codes", "filter_codes"), ("af-i18n-filter-duracao", "filter_duracao"),
    ("af-i18n-filter-gatilho", "filter_gatilho"), ("af-i18n-gatilho-hint", "gatilho_hint"),
    ("af-i18n-kpi-total-title", "kpi_total_title"), ("af-i18n-kpi-total-sub", "kpi_total_sub"),
    ("af-i18n-kpi-count-title", "kpi_count_title"), ("af-i18n-kpi-count-sub", "kpi_count_sub"),
    ("af-i18n-kpi-top-title", "kpi_top_title"), ("af-i18n-kpi-top-sub", "kpi_top_sub"),
    ("af-i18n-causa-title", "causa_title"), ("af-i18n-causa-sub", "causa_sub"),
    ("af-i18n-equip-title", "equip_title"), ("af-i18n-equip-sub", "equip_sub"),
    ("af-i18n-table-title", "table_title"),
    ("af-i18n-paradas-title", "paradas_title"), ("af-i18n-paradas-sub", "paradas_sub"),
    ("af-i18n-paradas-page-size", "paradas_page_size"),
    # Gestão das Análises. Prefixo próprio (`af-i18n-g-`) para ficar óbvio, na
    # leitura, o que pertence a esta aba — a lista já é longa.
    ("af-i18n-g-title", "g_title"), ("af-i18n-g-sub", "g_sub"),
    ("af-i18n-g-kpi-eleg", "g_kpi_eleg"), ("af-i18n-g-kpi-eleg-sub", "g_kpi_eleg_sub"),
    ("af-i18n-g-kpi-analisadas", "g_kpi_analisadas"),
    ("af-i18n-g-kpi-analisadas-sub", "g_kpi_analisadas_sub"),
    ("af-i18n-g-kpi-fila", "g_kpi_fila"), ("af-i18n-g-kpi-fila-sub", "g_kpi_fila_sub"),
    ("af-i18n-g-kpi-plano", "g_kpi_plano"), ("af-i18n-g-kpi-plano-sub", "g_kpi_plano_sub"),
    ("af-i18n-g-kpi-vencidas", "g_kpi_vencidas"),
    ("af-i18n-g-kpi-vencidas-sub", "g_kpi_vencidas_sub"),
    ("af-i18n-g-kpi-voltaram", "g_kpi_voltaram"),
    ("af-i18n-g-kpi-voltaram-sub", "g_kpi_voltaram_sub"),
    ("af-i18n-g-graf-title", "g_graf_title"), ("af-i18n-g-graf-sub", "g_graf_sub"),
    ("af-i18n-g-resp-title", "g_resp_title"), ("af-i18n-g-resp-sub", "g_resp_sub"),
    ("af-i18n-g-aten-title", "g_aten_title"), ("af-i18n-g-aten-sub", "g_aten_sub"),
    ("af-i18n-g-fila-title", "g_fila_title"), ("af-i18n-g-fila-sub", "g_fila_sub"),
    ("af-i18n-g-reinc-title", "g_reinc_title"), ("af-i18n-g-reinc-sub", "g_reinc_sub"),
]


# ---------------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------------

def _empty_fig(msg, height=340):
    """Figura vazia com mensagem (offline / sem dados)."""
    fig = go.Figure()
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        annotations=[dict(text=msg, showarrow=False, font=dict(size=14, color="#9aa5b1"),
                          xref="paper", yref="paper", x=0.5, y=0.5)],
    )
    return fig


def _pareto_fig(labels, values, tr, counts=None, accent=ACCENT, height=340):
    """Pareto: barras (desc) + linha de % acumulada + marca 80%. `tr` = dict de idioma."""
    if not labels:
        return _empty_fig(tr["empty"], height=height)
    total = float(sum(values)) or 1.0
    acum, s = [], 0.0
    for v in values:
        s += float(v)
        acum.append(s / total * 100.0)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    textos = [f"{int(v)} · {int(c)}x" for v, c in zip(values, counts)] if counts is not None else None
    fig.add_trace(go.Bar(x=labels, y=values, name=tr["bars_name"], marker_color=accent,
                         text=textos, textposition="outside", cliponaxis=False), secondary_y=False)
    fig.add_trace(go.Scatter(x=labels, y=acum, name=tr["cum_name"], mode="lines+markers",
                             line=dict(color="#2c3e50", width=2)), secondary_y=True)
    fig.add_hline(y=80, line_dash="dot", line_color="#7f8c8d",
                  annotation_text="80%", annotation_position="top left", secondary_y=True)
    fig.update_yaxes(title_text=tr["y_time"], secondary_y=False)
    fig.update_yaxes(title_text=tr["y_pct"], range=[0, 105], secondary_y=True)
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=28, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), bargap=0.25)
    return fig


def _resolve_window(f):
    """Resolve a janela semi-aberta [start, end) a partir do dict de filtros do store."""
    ptype = f.get("period_type", "year")
    if ptype == "custom" and f.get("start_date") and f.get("end_date"):
        start = datetime.datetime.strptime(f["start_date"][:10], "%Y-%m-%d")
        end = datetime.datetime.strptime(f["end_date"][:10], "%Y-%m-%d") + datetime.timedelta(days=1)
        return start, end
    if ptype == "last12":
        hoje = datetime.datetime.now()
        end = datetime.datetime(hoje.year + 1, 1, 1) if hoje.month == 12 \
            else datetime.datetime(hoje.year, hoje.month + 1, 1)
        return datetime.datetime(end.year - 1, end.month, 1), end
    # `ano_valido` e não `int(...)` cru: o filtro é persistido em `local` e pode
    # trazer um ano que já saiu das opções. Sem o ajuste, a barra mostraria o ano
    # corrente (já ajustado na hidratação) e o gráfico traria o ano antigo.
    y = ano_valido(f.get("year"))
    return datetime.datetime(y, 1, 1), datetime.datetime(y + 1, 1, 1)


def _tabela_top(rows, tr):
    """DataTable Top-N de paradas (realce ≥200 amarelo, ≥400 rosa)."""
    if not rows:
        return html.Div(tr["empty"], className="text-muted p-3")
    cols = [tr["col_num"], tr["col_dt"], tr["col_equip"], tr["col_cause"], tr["col_dur"], tr["col_desc"]]
    data = []
    for i, r in enumerate(rows, 1):
        dt = r.get("inicio_execucao")
        dh = dt.strftime("%d/%m/%Y %H:%M") if hasattr(dt, "strftime") else str(dt or "")
        data.append({
            tr["col_num"]: i, tr["col_dt"]: dh, tr["col_equip"]: r.get("equipamento", ""),
            tr["col_cause"]: r.get("causa_do_desvio", ""),
            tr["col_dur"]: round(float(r.get("duration_min", 0) or 0), 1),
            tr["col_desc"]: r.get("descricao", "") or "",
        })
    return dash_table.DataTable(
        data=data, columns=[{"name": c, "id": c} for c in cols], page_size=20,
        style_cell={"fontSize": "0.85rem", "padding": "6px", "textAlign": "left"},
        style_header={"fontWeight": "600"},
        style_data_conditional=[
            {"if": {"filter_query": f"{{{tr['col_dur']}}} >= 400", "column_id": tr["col_dur"]},
             "backgroundColor": "#f8d7da"},
            {"if": {"filter_query": f"{{{tr['col_dur']}}} >= 200 && {{{tr['col_dur']}}} < 400",
                    "column_id": tr["col_dur"]}, "backgroundColor": "#fff3cd"},
        ],
    )


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

def register_analise_falhas_callbacks(app):
    """Registra i18n, filtros (store) e render da página Análise de Falhas."""

    # ---------------- i18n ----------------
    @app.callback(
        Output("store-af-lang", "data"),
        Input({"type": "af-lang-btn", "lang": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _set_lang(_clicks):
        """Clique numa bandeira → grava o idioma no store."""
        trig = dash.callback_context.triggered_id
        if isinstance(trig, dict) and trig.get("type") == "af-lang-btn":
            return trig.get("lang", "pt")
        return no_update

    @app.callback(
        Output({"type": "af-lang-btn", "lang": ALL}, "className"),
        Input("store-af-lang", "data"),
        State({"type": "af-lang-btn", "lang": ALL}, "id"),
    )
    def _highlight_flag(lang, ids):
        """Realça a bandeira do idioma ativo."""
        return ["v2-lang-flag active" if (i or {}).get("lang") == (lang or "pt")
                else "v2-lang-flag" for i in ids]

    @app.callback(
        [Output(eid, "children") for eid, _ in I18N_OUTPUTS] + [
            Output("tab-af-gestao-component", "label"),
            Output("tab-af-pareto-component", "label"),
            Output("tab-af-dados-component", "label"),
            Output("tab-af-paradas-component", "label"),
            Output("filter-af-period-type", "options"),
            Output("filter-af-equipment", "placeholder"),
            Output("filter-af-duracao", "placeholder"),
            Output("filter-af-gatilho", "options"),
            Output("af-beta-tooltip", "children"),
        ],
        Input("store-af-lang", "data"),
    )
    def _translate(lang):
        """Traduz todos os textos da página conforme o idioma."""
        d = TRANS.get(lang or "pt", TRANS["pt"])
        out = [d.get(key, key) for _, key in I18N_OUTPUTS]
        out.append(d["tab_gestao"])
        out.append(d["tab_pareto"])
        out.append(d["tab_dados"])
        out.append(d["tab_paradas"])
        out.append([
            {"label": d["period_year"], "value": "year"},
            {"label": d["period_last12"], "value": "last12"},
            {"label": d["period_custom"], "value": "custom"},
        ])
        out.append(d["equip_placeholder"])
        out.append(d["duracao_placeholder"])
        out.append([
            {"label": d["gatilho_acima"], "value": GATILHO_MODO_ACIMA},
            {"label": d["gatilho_todas"], "value": GATILHO_MODO_TODAS},
        ])
        out.append(d["beta_tooltip"])
        return out

    # ---------------- filtros ----------------
    @app.callback(
        Output("collapse-af-filters", "is_open"),
        Input("btn-af-filters", "n_clicks"),
        State("collapse-af-filters", "is_open"),
        prevent_initial_call=True,
    )
    def _toggle_filtros(_n, is_open):
        """Abre/fecha a barra de filtros."""
        return not bool(is_open)

    @app.callback(
        Output("col-filter-af-year", "style"),
        Output("col-filter-af-range", "style"),
        Input("filter-af-period-type", "value"),
    )
    def _toggle_period_fields(ptype):
        """Mostra ano (year) ou range (custom) conforme o tipo de período."""
        if ptype == "custom":
            return {"display": "none"}, {"display": "block"}
        if ptype == "last12":
            return {"display": "none"}, {"display": "none"}
        return {"display": "block"}, {"display": "none"}

    @app.callback(
        Output("filter-af-equipment", "options"),
        Input("url", "pathname"),
        State("filter-af-year", "value"),
    )
    def _popular_equipamentos(pathname, year):
        """Popula o dropdown de equipamentos ao entrar na página."""
        if pathname != ROUTE:
            return no_update
        try:
            lst = fetch_zpp_equipment_list(int(year or 2025))
            return [{"label": e, "value": e} for e in sorted(lst)]
        except Exception as e:  # noqa: BLE001
            logger.warning("Falha ao listar equipamentos: %s", e)
            return []

    @app.callback(
        Output("store-af-filters", "data"),
        Input("btn-apply-af-filters", "n_clicks"),
        Input("btn-af-refresh", "n_clicks"),
        Input("url", "pathname"),
        State("filter-af-period-type", "value"),
        State("filter-af-year", "value"),
        State("filter-af-date-range", "start_date"),
        State("filter-af-date-range", "end_date"),
        State("filter-af-equipment", "value"),
        State("filter-af-codes", "value"),
        State("filter-af-duracao", "value"),
        State("filter-af-gatilho", "value"),
        State("store-af-filters", "data"),
        prevent_initial_call=False,
    )
    def _aplicar(apply_n, refresh_n, pathname, ptype, year, sdate, edate, equip,
                 codes, duracao, gatilho, atual):
        """Escreve os filtros ativos no store (padrão two-stage da v2).

        `store-af-filters` é persistido em `local`, então ao remontar a página
        ele já vem preenchido. Entrar na rota NÃO pode sobrescrevê-lo com os
        defaults dos controles — senão o filtro salvo se perderia a cada visita.
        Só os botões Aplicar/Atualizar reescrevem o store; a montagem apenas
        semeia o valor inicial na primeira vez.
        """
        if pathname != ROUTE:
            return no_update

        gatilho = (dash.callback_context.triggered[0]["prop_id"] or "").split(".")[0]
        if gatilho in ("url", "") and atual:
            return no_update  # preserva o filtro persistido

        return {
            "period_type": ptype or "year",
            "year": year or ano_padrao(),
            "start_date": sdate, "end_date": edate,
            "equip": list(equip) if equip else None,
            "codes": list(codes) if codes else None,
            "duracao": list(duracao) if duracao else None,
            # Só a aba Análise de Paradas lê esta chave (ver `_render_paradas`);
            # Pareto e Dados a ignoram de propósito (BR-01).
            "gatilho": gatilho or GATILHO_MODO_ACIMA,
            "_n": (apply_n or 0) + (refresh_n or 0),  # muda a cada clique → força re-render
        }

    @app.callback(
        Output("filter-af-period-type", "value"),
        Output("filter-af-year", "value"),
        Output("filter-af-date-range", "start_date"),
        Output("filter-af-date-range", "end_date"),
        Output("filter-af-equipment", "value"),
        Output("filter-af-codes", "value"),
        Output("filter-af-duracao", "value"),
        Output("filter-af-gatilho", "value"),
        Input("url", "pathname"),
        State("store-af-filters", "data"),
    )
    def _hidratar_filtros(pathname, f):
        """Repõe nos controles os filtros persistidos, ao (re)entrar na página.

        Sem isto, o store voltaria correto do `local` mas a barra de filtros
        mostraria os defaults — o usuário veria um filtro na tela e outro no
        gráfico.
        """
        if pathname != ROUTE or not f:
            return (no_update,) * 8
        return (
            f.get("period_type") or "year",
            # Ajusta o ano salvo à lista de hoje — um filtro antigo em `local`
            # pode apontar para um ano que já saiu das opções.
            ano_valido(f.get("year")),
            f.get("start_date"),
            f.get("end_date"),
            f.get("equip") or [],
            f.get("codes") or list(BREAKDOWN_CODES),
            f.get("duracao") or [x["value"] for x in FAIXAS_DURACAO],
            f.get("gatilho") or GATILHO_MODO_ACIMA,
        )

    # ---------------- render ----------------
    @app.callback(
        Output("af-pareto-causa", "figure"),
        Output("af-pareto-equip", "figure"),
        Output("af-kpi-total-min", "children"),
        Output("af-kpi-count", "children"),
        Output("af-kpi-top", "children"),
        Output("af-top-table", "children"),
        Output("store-af-data", "data"),
        Input("store-af-filters", "data"),
        Input("store-af-lang", "data"),
    )
    def _render(filters, lang):
        """Busca paradas e monta Paretos, KPIs e tabela conforme filtros + idioma."""
        tr = TRANS.get(lang or "pt", TRANS["pt"])
        if not filters:
            f = _empty_fig(tr["empty"])
            return f, f, "—", "—", "—", html.Div(tr["empty"], className="text-muted p-3"), no_update

        start, end = _resolve_window(filters)
        codes = filters.get("codes") or list(BREAKDOWN_CODES)
        equipamentos = filters.get("equip")

        try:
            df = fetch_zpp_breakdown_data(start, end, breakdown_codes=codes)
        except Exception as e:  # noqa: BLE001
            logger.error("Análise de Falhas: erro ao buscar paradas: %s", e)
            f = _empty_fig(tr["empty"])
            return (f, f, "—", "—", "—",
                    html.Div("Erro ao carregar dados.", className="text-danger p-3"), no_update)

        if equipamentos:
            df = df[df["linea"].isin(equipamentos)]

        # Faixa de duração. Nestas duas abas a unidade exibida é o apontamento,
        # então a faixa é avaliada sobre a duração de cada apontamento — na aba
        # Análise de Paradas ela vale sobre a duração do evento agregado.
        faixas = faixas_ativas(filters.get("duracao"))
        if len(faixas) < len(FAIXAS_DURACAO) and df is not None and not df.empty:
            df = df[df["duracao_min"].map(faixa_duracao).isin(faixas)]

        if df is None or df.empty:
            f = _empty_fig(tr["empty"])
            return (f, f, "0", "0", "—",
                    html.Div(tr["empty"], className="text-muted p-3"), {"causa": [], "equip": []})

        causa = (df.groupby("motivo")["duracao_min"].agg(total="sum", count="count")
                 .reset_index().sort_values("total", ascending=False))
        fig_causa = _pareto_fig(causa["motivo"].astype(str).tolist(),
                                causa["total"].round(1).tolist(), tr,
                                counts=causa["count"].tolist(), accent=ACCENT)

        equip = (df.groupby("linea")["duracao_min"].sum().reset_index()
                 .sort_values("duracao_min", ascending=False))
        fig_equip = _pareto_fig(equip["linea"].astype(str).tolist(),
                                equip["duracao_min"].round(1).tolist(), tr, accent=ACCENT_EQUIP)

        total_min = int(round(df["duracao_min"].sum()))
        num_paradas = int(len(df))
        top_causa = str(causa.iloc[0]["motivo"]) if not causa.empty else "—"

        try:
            restringe = bool(equipamentos) or len(faixas) < len(FAIXAS_DURACAO)
            top_n = None if restringe else 20
            rows = fetch_top_breakdowns_all(start, end, top_n=top_n, breakdown_codes=codes)
            if equipamentos:
                rows = [r for r in rows if r.get("equipamento") in equipamentos]
            if len(faixas) < len(FAIXAS_DURACAO):
                # `fetch_top_breakdowns_all` devolve `duration_min` (não `duracao_min`)
                rows = [r for r in rows if faixa_duracao(r.get("duration_min")) in faixas]
            rows = rows[:20]
        except Exception as e:  # noqa: BLE001
            logger.warning("Falha ao buscar Top paradas: %s", e)
            rows = []

        store = {"causa": causa.to_dict("records"), "equip": equip.to_dict("records")}
        return (fig_causa, fig_equip, f"{total_min:,}".replace(",", "."),
                str(num_paradas), top_causa, _tabela_top(rows, tr), store)

    # ---------------- export ----------------
    @app.callback(
        Output("download-af-xlsx", "data"),
        Input("btn-af-export", "n_clicks"),
        State("store-af-data", "data"),
        prevent_initial_call=True,
    )
    def _exportar(_n, store):
        """Exporta os dois Paretos vigentes para xlsx (2 abas)."""
        store = store or {}
        causa = pd.DataFrame(store.get("causa") or [])
        equip = pd.DataFrame(store.get("equip") or [])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xls:
            (causa if not causa.empty else pd.DataFrame({"info": ["sem dados"]})).to_excel(
                xls, sheet_name="Pareto por Causa", index=False)
            (equip if not equip.empty else pd.DataFrame({"info": ["sem dados"]})).to_excel(
                xls, sheet_name="Pareto por Equipamento", index=False)
        buf.seek(0)
        return dcc.send_bytes(buf.getvalue(), "analise_de_falhas.xlsx")

    # ---------------- Send Mail (resumo das paradas) ----------------
    @app.callback(
        Output("af-mail-toast", "is_open"),
        Output("af-mail-toast", "children"),
        Output("af-mail-toast", "icon"),
        Input("btn-af-sendmail", "n_clicks"),
        State("store-af-data", "data"),
        State("store-af-filters", "data"),
        State("store-af-lang", "data"),
        prevent_initial_call=True,
    )
    def _enviar_resumo(_n, data, filters, lang):
        """Envia por e-mail um resumo das paradas — exemplo de reuso de enviar_email_template."""
        tr = TRANS.get(lang or "pt", TRANS["pt"])
        causa = (data or {}).get("causa") or []
        if not causa:
            return True, tr["mail_empty"], "warning"

        total_min = int(round(sum(float(c.get("total", 0) or 0) for c in causa)))
        n_paradas = int(sum(int(c.get("count", 0) or 0) for c in causa))
        top = str(causa[0].get("motivo", "—"))

        f = filters or {}
        ptype = f.get("period_type", "year")
        if ptype == "custom" and f.get("start_date") and f.get("end_date"):
            periodo = f"{f['start_date'][:10]} → {f['end_date'][:10]}"
        elif ptype == "last12":
            periodo = tr["period_last12"]
        else:
            periodo = f"{tr['filter_year']}: {f.get('year', '—')}"

        itens = [
            {"label": str(c.get("motivo", "")),
             "valor": f"{int(round(float(c.get('total', 0) or 0)))} min · {int(c.get('count', 0) or 0)}x"}
            for c in causa[:5]
        ]

        contexto = {
            "titulo": tr["mail_title"],
            "preheader": f"{total_min} min · {n_paradas} paradas",
            "paragrafos": [
                f"{tr['filter_period']}: {periodo}.",
                f"{tr['kpi_total_title']}: {total_min} min · "
                f"{tr['kpi_count_title']}: {n_paradas} · {tr['kpi_top_title']}: {top}.",
            ],
            "itens": itens,
        }
        ok = enviar_email_template(assunto=tr["mail_subject"], contexto=contexto)
        return (True, tr["mail_ok"], "success") if ok else (True, tr["mail_fail"], "danger")
