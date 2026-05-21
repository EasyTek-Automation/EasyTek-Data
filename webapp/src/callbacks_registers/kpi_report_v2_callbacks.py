"""KPIReport-v2 — registro de callbacks (DS-06, IM-06..IM-11).

Callbacks registrados (12 total):

| ID  | Função                          | Trigger                          | Output                       |
|-----|----------------------------------|----------------------------------|------------------------------|
| C1  | init_data                        | Interval / btn-refresh           | store-kpi-v2-data            |
| C2  | compute_compare                  | store-kpi-v2-data                | store-kpi-v2-compare         |
| C3  | render_blocks                    | data + compare + lang + toggle   | container blocks             |
| C4  | translate_all                    | store-kpi-v2-lang                | labels i18n                  |
| C5  | toggle_block_visibility          | checkbox-block                   | store-kpi-v2-blocks-toggle   |
| C6  | open_drilldown_modal             | pattern-matching click           | modal open/body              |
| C7  | close_drilldown_modal            | botão fechar                     | modal close                  |
| C8  | export_pdf                       | btn-kpi-v2-export-pdf            | download-kpi-v2-pdf          |
| C9  | export_docx                      | btn-kpi-v2-export-docx (v1)      | download-kpi-v2-docx         |
| C10 | copy_share_link                  | btn-kpi-v2-share                 | toast + clipboard            |
| C11 | update_export_buttons_disabled   | store-kpi-v2-data                | disabled 3 botões            |
| C12 | switch_lang                      | bandeira PT/ES/EN                | store-kpi-v2-lang            |
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta
from typing import Any

import dash
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update

from src.pages.maintenance import kpi_report_v2 as page
from src.utils import kpi_report_config as cfg
from src.utils.kpi_report_data import coletar_dados_relatorio
from src.utils.kpi_report_v2_compare import (
    build_compare_dict,
    fetch_anterior_last24h_window,
    fetch_anterior_monthly_window,
)
from src.utils.kpi_report_v2_layout import (
    build_drilldown_modal_body,
    render_all_blocks,
)
from src.utils.kpi_report_v2_series import (
    build_daily_series_last_n,
    build_daily_series_last_n_ending,
    build_monthly_series_for_year,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helpers
# ============================================================================

def _serialize_figures(bloco_dict: dict | None) -> dict | None:
    """Converte Plotly Figure → dict (JSON-friendly) pra ir no dcc.Store."""
    if not bloco_dict:
        return bloco_dict
    out = dict(bloco_dict)
    sb = out.get("sunburst_figures")
    if isinstance(sb, dict):
        new_sb: dict[str, Any] = {}
        for k, v in sb.items():
            if v is None:
                new_sb[k] = None
            elif hasattr(v, "to_plotly_json"):
                new_sb[k] = v.to_plotly_json()
            elif isinstance(v, (bytes, bytearray)):
                # bytes não viajam por JSON store — descartar pra HTML; PDF reusa fluxo v1
                new_sb[k] = None
            elif isinstance(v, dict):
                new_sb[k] = v
            else:
                new_sb[k] = None
        out["sunburst_figures"] = new_sb
    return out


def _serialize_dados_for_store(dados: dict) -> dict:
    """Aplica `_serialize_figures` nos blocos 1 e 3 + serializa datetimes em metadata.

    Mantém `sunburst_figures` por retrocompat (legado): bytes viram None pra
    transitar via JSON. O refactor RF-* prefere `monthly_series` / `daily_series`
    em vez de sunburst — esses ficam JSON-friendly nativamente.
    """
    if not dados:
        return {}
    out = dict(dados)
    out["bloco1"] = _serialize_figures(dados.get("bloco1"))
    out["bloco3"] = _serialize_figures(dados.get("bloco3"))

    periodo = dados.get("periodo") or {}
    out["periodo"] = {
        k: (v.isoformat() if isinstance(v, datetime) else v)
        for k, v in periodo.items()
    }
    return out


def _resolve_data_24h(value: Any, agora: datetime) -> datetime:
    """Resolve DatePicker value (ISO 'YYYY-MM-DD') → datetime do dia escolhido.

    None/inválido → ontem (BR-02 padrão). Mesmo helper usado no tab_callback —
    duplicado aqui pra evitar import circular.
    """
    if value:
        try:
            return datetime.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            pass
    return (agora.replace(hour=0, minute=0, second=0, microsecond=0,
                            tzinfo=None) - timedelta(days=1))


def _override_blocos_24h(dados: dict, stored: dict, data_dia: datetime) -> dict:
    """Sobrescreve blocos 3/5 com janela `[data_dia 00:00, data_dia+1 00:00)`.

    Reusa helpers V1 canônicos (`_build_kpis_bloco_planta`, `_build_top5_paradas`).
    BR-02b — V1 intocada.
    """
    if not dados:
        return dados
    from src.utils.kpi_report_data import (
        _build_kpis_bloco_planta,
        _build_top5_paradas,
    )
    from src.utils.zpp_kpi_calculator import fetch_zpp_kpi_data

    d_start = data_dia.replace(hour=0, minute=0, second=0, microsecond=0,
                                 tzinfo=None)
    d_end = d_start + timedelta(days=1)
    eq_ids = stored.get("equipment_ids") or []
    names = stored.get("names") or {}
    categories = stored.get("categories") or {}
    targets = stored.get("equipment_targets") or {}

    try:
        data_dia_kpi = fetch_zpp_kpi_data(d_start, d_end)
    except Exception:
        logger.warning("KPI v2 export BR-02b: sem dados [%s, %s)", d_start, d_end)
        data_dia_kpi = {}

    try:
        dados["bloco3"] = _build_kpis_bloco_planta(
            eq_ids, d_start, d_end, targets, names, categories,
            kpi_data=data_dia_kpi, year=d_start.year,
            monthly_aggregates=None, as_png=True,
        )
        dados["bloco5"] = _build_top5_paradas(d_start, d_end, names, top_n=None)
    except Exception:
        logger.exception("KPI v2 export BR-02b: falha override blocos 3/5")
    return dados


def _replace_sunbursts_with_bars(dados: dict) -> dict:
    """Substitui `bloco{1,3}.sunburst_figures` PNG bytes por bar chart PNG bytes.

    Reusa `monthly_series` / `daily_series` já injetadas + `kpi_report_v2_bars` +
    kaleido. Mantém compat com template DOCX v1 que renderiza
    `{{ bloco1.sunburst_figures.mtbf }}` — bytes continuam bytes; só muda o que
    o usuário vê (sunburst → bar). Não toca V1 (refactor RF-08).
    """
    if not dados:
        return dados
    try:
        from src.utils.kpi_report_figures import renderizar_sunburst_png
        from src.utils.kpi_report_v2_bars import build_bar_figure
    except Exception:
        logger.exception("KPI v2 docx: imports bars/figures falharam")
        return dados

    for bloco_key, series_key in (("bloco1", "monthly_series"),
                                    ("bloco3", "daily_series")):
        bloco = dados.get(bloco_key)
        if not isinstance(bloco, dict):
            continue
        series = bloco.get(series_key)
        if not isinstance(series, dict):
            continue
        labels = series.get("labels") or []
        if not labels:
            continue
        metas = bloco.get("metas") or {}
        new_figs: dict[str, bytes] = {}
        for kpi_key in ("mtbf", "mttr", "taxa_avaria"):
            values = series.get(kpi_key) or []
            try:
                fig = build_bar_figure(
                    labels=labels, values=values, kpi=kpi_key,
                    target=metas.get(kpi_key), title="",
                    highlight_idx=series.get("current_idx"), height=300,
                    bar_text_size=36, meta_text_size=30,
                    axis_tick_size=33,
                )
                png = renderizar_sunburst_png(fig, kpi_key.upper())
                if isinstance(png, (bytes, bytearray)):
                    new_figs[kpi_key] = bytes(png)
            except Exception:
                logger.warning("KPI v2 docx: falha bar PNG %s/%s",
                                bloco_key, kpi_key)
        if new_figs:
            bloco["sunburst_figures"] = new_figs
    return dados


def _inject_series(
    dados: dict, stored: dict, agora: datetime,
    end_day_24h: datetime | None = None,
) -> dict:
    """Injeta `monthly_series` (bloco 1) e `daily_series` (bloco 3) — refactor RF.

    Reusa `build_monthly_series_for_year` / `build_daily_series_last_n*` que delegam
    a fórmulas canônicas v1. Mantém BR-01/02/05/06/08 (janelas, escopo, fuso, metas).

    `end_day_24h` (BR-02b): se fornecido, série diária encerra no dia escolhido em
    vez de ontem (default V1).
    """
    if not dados:
        return dados

    eq_ids = stored.get("equipment_ids") or []
    bloco1 = dados.get("bloco1") or {}
    bloco3 = dados.get("bloco3") or {}

    try:
        bloco1["monthly_series"] = build_monthly_series_for_year(
            year=agora.year, equipment_ids=eq_ids, current_month=agora.month,
        )
    except Exception:
        logger.exception("KPI v2 inject_series: monthly falhou")
        bloco1["monthly_series"] = None

    try:
        if end_day_24h is not None:
            bloco3["daily_series"] = build_daily_series_last_n_ending(
                end_day=end_day_24h, n_days=7, equipment_ids=eq_ids,
            )
        else:
            bloco3["daily_series"] = build_daily_series_last_n(
                now=agora, n_days=7, equipment_ids=eq_ids,
            )
    except Exception:
        logger.exception("KPI v2 inject_series: daily falhou")
        bloco3["daily_series"] = None

    dados["bloco1"] = bloco1
    dados["bloco3"] = bloco3
    return dados


def _build_default_stored_data() -> dict:
    """Monta `stored_data` minimal pro `coletar_dados_relatorio` da v2.

    v2 é rota standalone — não depende de filtros da v1. Carrega equipment_ids /
    names / categories / targets do banco usando funções canônicas de v1.
    """
    try:
        from src.utils.zpp_kpi_calculator import get_zpp_equipment_categories
        from src.utils.maintenance_demo_data import get_all_equipment_targets
    except ImportError as exc:
        logger.exception("Falha ao importar helpers v1 para defaults: %s", exc)
        return {"equipment_ids": [], "names": {}, "categories": {},
                "equipment_targets": {}, "data": {}, "year": datetime.now().year}

    try:
        categories = get_zpp_equipment_categories() or {}
        eq_ids: list[str] = []
        for cat_eqs in categories.values():
            eq_ids.extend(cat_eqs or [])
        # dedup preservando ordem
        seen: set[str] = set()
        eq_ids = [x for x in eq_ids if not (x in seen or seen.add(x))]
    except Exception:
        logger.exception("Falha ao listar equipamentos via get_zpp_equipment_categories")
        categories = {}
        eq_ids = []

    try:
        targets = get_all_equipment_targets() or {}
    except Exception:
        logger.exception("Falha ao carregar targets")
        targets = {}

    return {
        "equipment_ids":     eq_ids,
        "names":             {},
        "categories":        categories,
        "equipment_targets": targets,
        "data":              {},
        "year":              datetime.now().year,
    }


def _extract_kpis(bloco: dict | None) -> dict:
    """Extrai dict de KPIs (mtbf/mttr/breakdown_rate) do bloco 1 ou 3."""
    if not isinstance(bloco, dict):
        return {"mtbf": None, "mttr": None, "breakdown_rate": None}
    kpis = bloco.get("kpis_planta") or {}
    return {
        "mtbf":           kpis.get("mtbf"),
        "mttr":           kpis.get("mttr"),
        "breakdown_rate": kpis.get("taxa_avaria"),
    }


def _coletar_with_timeout(stored_data: dict, agora: datetime) -> dict:
    """Wrapper ThreadPool com timeout duro (BR-09)."""
    def _job():
        return coletar_dados_relatorio(stored_data, agora, as_png=False)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_job)
        try:
            return future.result(timeout=cfg.TIMEOUT_GERACAO_S)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"Coleta KPIReport v2 excedeu {cfg.TIMEOUT_GERACAO_S}s"
            ) from exc


# ============================================================================
# Registro
# ============================================================================

def register_kpi_report_v2_callbacks(app: dash.Dash) -> None:
    """Registra todos os callbacks da rota /maintenance/kpi-report-v2."""

    # ------------------------------------------------------------------
    # C1 — init_data
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-kpi-v2-data", "data", allow_duplicate=True),
        Input("kpi-v2-load-once", "n_intervals"),
        Input("btn-kpi-v2-refresh", "n_clicks"),
        prevent_initial_call="initial_duplicate",
    )
    def init_data(n_intervals, n_refresh):
        """Carga inicial e refresh manual — chama coletar_dados_relatorio (as_png=False)."""
        triggered = ctx.triggered_id if ctx.triggered else None
        # Skip first server-side fire sem trigger real (alguns navegadores).
        if triggered is None and not n_intervals and not n_refresh:
            return no_update

        stored = _build_default_stored_data()
        if not stored.get("equipment_ids"):
            logger.warning("KPI v2 init_data: sem equipamentos — coleta abortada.")
            return {"empty": True, "reason": "no_equipment"}

        agora = cfg._now_in_report_timezone()
        t_inicio = time.perf_counter()
        try:
            dados = _coletar_with_timeout(stored, agora)
        except TimeoutError:
            logger.exception("KPI v2 init_data: timeout duro (>%ds)",
                              int(cfg.TIMEOUT_GERACAO_S))
            return {"empty": True, "reason": "timeout"}
        except Exception:
            logger.exception("KPI v2 init_data: erro inesperado")
            return {"empty": True, "reason": "error"}

        delta_t = time.perf_counter() - t_inicio
        if delta_t > cfg.LATENCIA_GUIDELINE_S:
            logger.warning("KPI v2 init_data ultrapassou guideline: %.2fs", delta_t)

        # RF-04: injeta séries mensais/diárias pros bar charts blocos 1/3
        dados = _inject_series(dados, stored, agora)

        return _serialize_dados_for_store(dados)

    # ------------------------------------------------------------------
    # C2 — compute_compare
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-kpi-v2-compare", "data"),
        Input("store-kpi-v2-data", "data"),
    )
    def compute_compare(dados_atuais):
        """Calcula ∆ vs período anterior pra blocos 1 (mês) e 3 (24h)."""
        if not dados_atuais or dados_atuais.get("empty"):
            return None

        periodo = dados_atuais.get("periodo") or {}
        # datetimes vieram como isoformat strings — reconstrói
        def _p(key):
            v = periodo.get(key)
            if isinstance(v, str):
                try:
                    return datetime.fromisoformat(v)
                except ValueError:
                    return None
            return v

        win_mes = (_p("inicio_mensal"), _p("fim_mensal"))
        win_24h = (_p("inicio_24h"), _p("fim_24h"))
        if None in win_mes or None in win_24h:
            return None

        stored = _build_default_stored_data()
        if not stored.get("equipment_ids"):
            return None

        # Helper: roda coletar pra uma janela específica sobrescrevendo agora
        def _coletar_para(win_start, win_end):
            # Hack: usar `agora` no fim da janela faz compute_monthly_window
            # retornar (start_atual_mes, agora) — mas precisamos da janela anterior.
            # Em vez disso, montamos dados via fetch direto:
            from src.utils.zpp_kpi_calculator import fetch_zpp_kpi_data
            from src.utils.maintenance_demo_data import calculate_kpi_averages
            try:
                data_window = fetch_zpp_kpi_data(win_start, win_end)
                months = sorted({win_start.month, win_end.month})
                year_months = []
                cur = datetime(win_start.year, win_start.month, 1)
                last = datetime(win_end.year, win_end.month, 1)
                while cur <= last:
                    year_months.append(f"{cur.year:04d}-{cur.month:02d}")
                    if cur.month == 12:
                        cur = datetime(cur.year + 1, 1, 1)
                    else:
                        cur = datetime(cur.year, cur.month + 1, 1)
                avg = calculate_kpi_averages(
                    data_window, stored["equipment_ids"],
                    month_filter=months, year=win_start.year,
                    year_months=year_months,
                )
                return {
                    "mtbf":           avg.get("mtbf"),
                    "mttr":           (avg.get("mttr") * 60) if isinstance(avg.get("mttr"), (int, float)) else avg.get("mttr"),
                    "breakdown_rate": avg.get("breakdown_rate"),
                }
            except Exception as exc:
                # Janela anterior sem dados (típico em local / fim-de-semana) —
                # tratado como ∆=na no UI; downgrade log de error pra warning.
                logger.warning(
                    "KPI v2 compute_compare: sem dados em janela anterior "
                    "[%s, %s): %s — ∆ exibido como 'n/d'.",
                    win_start, win_end, type(exc).__name__,
                )
                return {"mtbf": None, "mttr": None, "breakdown_rate": None}

        ant_mes = fetch_anterior_monthly_window(win_mes)
        ant_24h = fetch_anterior_last24h_window(win_24h)

        atual_mes_kpis = _extract_kpis(dados_atuais.get("bloco1"))
        atual_24h_kpis = _extract_kpis(dados_atuais.get("bloco3"))
        anterior_mes_kpis = _coletar_para(*ant_mes)
        anterior_24h_kpis = _coletar_para(*ant_24h)

        return {
            "mes": build_compare_dict(atual_mes_kpis, anterior_mes_kpis),
            "24h": build_compare_dict(atual_24h_kpis, anterior_24h_kpis),
        }

    # ------------------------------------------------------------------
    # C3 — render_blocks
    # ------------------------------------------------------------------
    @app.callback(
        Output("kpi-v2-blocks-container", "children"),
        Input("store-kpi-v2-data", "data"),
        Input("store-kpi-v2-compare", "data"),
        Input("store-kpi-v2-lang", "data"),
        Input("store-kpi-v2-blocks-toggle", "data"),
    )
    def render_blocks(dados, compare, lang, toggle):
        """Render dos 5 cards baseado em data/compare/lang/toggle."""
        lang = lang or "pt"
        if not dados:
            return html.Div(
                page.TRANS.get(lang, page.TRANS["pt"]).get("loading", "Carregando…"),
                className="text-center text-muted py-5",
            )
        if dados.get("empty"):
            return html.Div(
                page.TRANS.get(lang, page.TRANS["pt"]).get("no_data",
                                                            "Sem dados no período"),
                className="text-center text-muted py-5",
            )
        return render_all_blocks(dados, compare, lang, toggle)

    # ------------------------------------------------------------------
    # C4 + C12 — i18n
    # ------------------------------------------------------------------
    @app.callback(
        Output("kpi-v2-i18n-page-title", "children"),
        Output("kpi-v2-i18n-page-subtitle", "children"),
        Output("kpi-v2-i18n-beta-badge", "children"),
        Output("kpi-v2-beta-badge", "title"),
        Output("kpi-v2-i18n-toggle-label", "children"),
        Output("kpi-v2-i18n-btn-pdf", "children"),
        Output("kpi-v2-i18n-btn-docx", "children"),
        Output("kpi-v2-i18n-btn-share", "children"),
        Input("store-kpi-v2-lang", "data"),
    )
    def translate_all(lang):
        """Atualiza todos os labels visíveis com base no idioma escolhido."""
        lang = lang or "pt"
        t = page.TRANS.get(lang, page.TRANS["pt"])
        return (
            t["page_title"],
            t["page_subtitle"],
            t["beta_badge"],
            t["beta_tooltip"],
            t["block_toggle_label"],
            t["btn_export_pdf"],
            t["btn_export_docx"],
            t["btn_share_link"],
        )

    @app.callback(
        Output("store-kpi-v2-lang", "data"),
        Input({"type": "kpi-v2-lang-btn", "lang": ALL}, "n_clicks"),
        State("store-kpi-v2-lang", "data"),
        prevent_initial_call=True,
    )
    def switch_lang(_n_clicks_list, current_lang):
        """Lê id da bandeira clicada (pattern-matching) e atualiza store-kpi-v2-lang."""
        triggered = ctx.triggered_id
        if not triggered or not any(_n_clicks_list or []):
            return no_update
        new_lang = triggered.get("lang") if isinstance(triggered, dict) else None
        if new_lang in page.TRANS:
            return new_lang
        return current_lang or "pt"

    # ------------------------------------------------------------------
    # C5 — toggle_block_visibility
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-kpi-v2-blocks-toggle", "data"),
        Input("kpi-v2-block-toggle", "value"),
        prevent_initial_call=True,
    )
    def toggle_block_visibility(values):
        """Persiste estado dos checkboxes no storage local."""
        out = {str(i): False for i in range(1, 6)}
        for v in (values or []):
            out[str(v)] = True
        return out

    # ------------------------------------------------------------------
    # C6 — open_drilldown_modal
    # ------------------------------------------------------------------
    @app.callback(
        Output("kpi-v2-drilldown-modal", "is_open"),
        Output("kpi-v2-drilldown-title", "children"),
        Output("kpi-v2-drilldown-body", "children"),
        Output("store-kpi-v2-drilldown-ctx", "data"),
        Input({"type": "kpi-v2-drilldown-trigger", "block": ALL}, "n_clicks"),
        Input({"type": "kpi-v2-row-trigger", "block": 5, "idx": ALL}, "n_clicks"),
        Input({"type": "kpi-v2-drilldown-close", "index": ALL}, "n_clicks"),
        State("store-kpi-v2-data", "data"),
        State("store-kpi-v2-lang", "data"),
        prevent_initial_call=True,
    )
    def open_drilldown_modal(_b2_clicks, _b5_clicks, _close_clicks, dados, lang):
        """Abre modal pra bloco 2 (Top 10) ou bloco 5 (detalhe evento) + fecha botão."""
        lang = lang or "pt"
        triggered = ctx.triggered_id

        # Fechar
        if isinstance(triggered, dict) and triggered.get("type") == "kpi-v2-drilldown-close":
            return False, no_update, no_update, no_update

        if not isinstance(triggered, dict) or not any((_b2_clicks or []) + (_b5_clicks or [])):
            return no_update, no_update, no_update, no_update

        block = triggered.get("block")
        if block == 2:
            paradas = ((dados or {}).get("bloco2") or {}).get("paradas") or []
            # Top 10 — chama fetch dedicado se v1 já só tem top 5 no store
            top10 = paradas[:10]
            if len(top10) < 10:
                # Tenta carregar via fetch_top_breakdowns_all(limit=10) com janela do bloco
                periodo = (dados or {}).get("periodo") or {}
                try:
                    ini = datetime.fromisoformat(periodo.get("inicio_mensal"))
                    fim = datetime.fromisoformat(periodo.get("fim_mensal"))
                    from src.utils.zpp_kpi_calculator import fetch_top_breakdowns_all
                    from src.utils.kpi_report_data import _build_top5_paradas
                    extra = _build_top5_paradas(ini, fim, names={}, top_n=10)
                    top10 = extra.get("paradas", paradas)[:10]
                except Exception:
                    logger.exception("KPI v2 drilldown b2: falha ao buscar top10 ampliado")

            title = page.TRANS.get(lang, page.TRANS["pt"])["drilldown_title_b2"]
            body = build_drilldown_modal_body(2, top10, lang)
            return True, title, body, {"block": 2}

        if block == 5:
            idx = triggered.get("idx")
            paradas = ((dados or {}).get("bloco5") or {}).get("paradas") or []
            evt = next((p for p in paradas if p.get("posicao") == idx), None)
            title = page.TRANS.get(lang, page.TRANS["pt"])["drilldown_title_b5"]
            body = build_drilldown_modal_body(5, [evt] if evt else [], lang)
            return True, title, body, {"block": 5, "idx": idx}

        return no_update, no_update, no_update, no_update

    # ------------------------------------------------------------------
    # C8 / C9 / C10 / C11 — exports
    # ------------------------------------------------------------------
    @app.callback(
        Output("btn-kpi-v2-export-pdf", "disabled"),
        Output("btn-kpi-v2-export-docx", "disabled"),
        Output("btn-kpi-v2-share", "disabled"),
        Input("store-kpi-v2-data", "data"),
    )
    def update_export_buttons_disabled(dados):
        """Habilita botões somente quando dados estão disponíveis."""
        ready = bool(dados) and not dados.get("empty")
        return (not ready, not ready, not ready)

    @app.callback(
        Output("download-kpi-v2-pdf", "data"),
        Input("btn-kpi-v2-export-pdf", "n_clicks"),
        State("store-kpi-v2-data", "data"),
        State("store-kpi-v2-blocks-toggle", "data"),
        State("store-kpi-v2-lang", "data"),
        State("kpi-v2-date-24h", "date"),
        prevent_initial_call=True,
    )
    def export_pdf(n, dados, toggle, lang, date_24h):
        """Gera PDF via reportlab respeitando toggle de blocos + DatePicker (BR-02b)."""
        if not n or not dados or dados.get("empty"):
            raise dash.exceptions.PreventUpdate

        from src.utils.kpi_report_v2_pdf import gerar_pdf

        lang = lang or "pt"
        active = {int(k) for k, v in (toggle or {}).items() if v}
        if not active:
            active = {1, 2, 3, 4, 5}

        # Para PDF: coleta com as_png=True (kaleido bytes sunburst legado) E injeta
        # monthly_series/daily_series — gerar_pdf prefere series (bar chart refactor RF-03)
        # com fallback automático pra sunburst PNG caso série esteja vazia.
        stored = _build_default_stored_data()
        agora = cfg._now_in_report_timezone()
        data_dia = _resolve_data_24h(date_24h, agora)
        ontem = (agora.replace(hour=0, minute=0, second=0, microsecond=0,
                                 tzinfo=None) - timedelta(days=1))
        try:
            dados_png = coletar_dados_relatorio(stored, agora, as_png=True)
            # BR-02b: se DatePicker ≠ ontem, sobrescreve blocos 3/5 com janela custom
            if data_dia.date() != ontem.date():
                dados_png = _override_blocos_24h(dados_png, stored, data_dia)
                end_day_override = data_dia
                dia_label = data_dia.strftime("%d/%m/%Y")
            else:
                end_day_override = None
                dia_label = ""
            dados_png = _inject_series(dados_png, stored, agora,
                                         end_day_24h=end_day_override)
            pdf_bytes = gerar_pdf(dados_png, active, lang,
                                    dia_24h_label=dia_label)
        except Exception:
            logger.exception("KPI v2 export_pdf: falha")
            raise dash.exceptions.PreventUpdate

        nome = cfg.gerar_nome_arquivo(agora).replace(".docx", ".pdf")
        # Embute dia no filename se diferente de ontem
        if data_dia.date() != ontem.date():
            nome = nome.replace(".pdf", f"_24h-{data_dia.strftime('%Y-%m-%d')}.pdf")
        return dcc.send_bytes(lambda buf: buf.write(pdf_bytes), nome,
                               type="application/pdf")

    @app.callback(
        Output("download-kpi-v2-docx", "data"),
        Input("btn-kpi-v2-export-docx", "n_clicks"),
        State("store-kpi-v2-data", "data"),
        State("kpi-v2-date-24h", "date"),
        prevent_initial_call=True,
    )
    def export_docx(n, dados, date_24h):
        """Delega ao `montar_docx` v1 + respeita DatePicker BR-02b."""
        if not n or not dados or dados.get("empty"):
            raise dash.exceptions.PreventUpdate

        # Lazy import — docxtpl só carrega no servidor onde a dep está instalada.
        from src.utils.kpi_report_builder import TemplateLoadError, montar_docx

        stored = _build_default_stored_data()
        agora = cfg._now_in_report_timezone()
        data_dia = _resolve_data_24h(date_24h, agora)
        ontem = (agora.replace(hour=0, minute=0, second=0, microsecond=0,
                                 tzinfo=None) - timedelta(days=1))
        try:
            dados_png = coletar_dados_relatorio(stored, agora, as_png=True)
            # BR-02b override blocos 3/5
            if data_dia.date() != ontem.date():
                dados_png = _override_blocos_24h(dados_png, stored, data_dia)
                end_day_override = data_dia
            else:
                end_day_override = None
            # RF-08: injeta séries + substitui sunburst PNG por bar chart PNG
            # antes do template DOCX renderizar (template v1 fica intocado).
            dados_png = _inject_series(dados_png, stored, agora,
                                         end_day_24h=end_day_override)
            dados_png = _replace_sunbursts_with_bars(dados_png)
            docx_bytes = montar_docx(dados_png)
        except (TemplateLoadError, Exception):
            logger.exception("KPI v2 export_docx: falha")
            raise dash.exceptions.PreventUpdate

        nome = cfg.gerar_nome_arquivo(agora)
        if data_dia.date() != ontem.date():
            nome = nome.replace(".docx",
                                  f"_24h-{data_dia.strftime('%Y-%m-%d')}.docx")
        return dcc.send_bytes(
            lambda buf: buf.write(docx_bytes), nome,
            type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    @app.callback(
        Output("kpi-v2-share-toast", "is_open"),
        Output("kpi-v2-share-toast", "children"),
        Output("kpi-v2-share-toast", "icon"),
        Output("kpi-v2-share-clipboard", "content"),
        Input("btn-kpi-v2-share", "n_clicks"),
        State("store-kpi-v2-lang", "data"),
        State("store-kpi-v2-blocks-toggle", "data"),
        prevent_initial_call=True,
    )
    def copy_share_link(n, lang, toggle):
        """Monta URL com filtros codificados em query string + copia pra clipboard via dcc.Clipboard."""
        if not n:
            raise dash.exceptions.PreventUpdate
        lang = lang or "pt"

        params = {
            "lang": lang,
            "blocks": "".join(k for k, v in (toggle or {}).items() if v) or "12345",
        }
        # Build absolute URL — Flask serve em / ; rota /maintenance/kpi-report-v2
        try:
            from flask import request
            base = request.host_url.rstrip("/")
        except Exception:
            base = ""

        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{base}/maintenance/kpi-report-v2?{qs}"

        msg = page.TRANS.get(lang, page.TRANS["pt"])["share_toast_success"]
        return True, msg, "success", url
