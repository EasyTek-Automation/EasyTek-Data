"""Coleta e agregação dos dados do KPIReport — Camada 2 (D8/D9).

Aplica escopo (BR-05), janelas (SP-03), consome `fetch_zpp_kpi_data` /
`calculate_kpi_averages` / `fetch_top_breakdowns_all` / `create_kpi_sunburst_chart`
e monta dict consolidado pronto para o template (SP-04 item 6).

Origem: projeto SDD KPIReport (DS-02 / DS-03 / DS-04 / DS-05) — implementado em IM-04.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from src.components.maintenance_kpi_graphs import create_kpi_sunburst_chart, get_kpi_color
from src.utils import kpi_report_config as cfg
from src.utils.kpi_report_figures import renderizar_sunburst_png
from src.utils.maintenance_demo_data import (
    _build_raw_table_internal,
    calculate_kpi_averages,
    get_all_equipment_targets,
)
from src.utils.zpp_kpi_calculator import (
    fetch_top_breakdowns_all,
    fetch_zpp_kpi_data,
    get_zpp_equipment_categories,
)

logger = logging.getLogger(__name__)


# =========================================================================
# Helpers internos
# =========================================================================

def _date_range_to_year_months(start: datetime, end: datetime) -> list[str]:
    """Converte janela `[start, end]` em lista de `"YYYY-MM"` cobrindo cada mês incluso.

    Compatível com filtro `year_months` usado por `calculate_kpi_averages` e
    `_build_raw_table_internal` (não modifica funções existentes).
    """
    if not start or not end or start > end:
        return []
    result = []
    cur = datetime(start.year, start.month, 1)
    last = datetime(end.year, end.month, 1)
    while cur <= last:
        result.append(f"{cur.year:04d}-{cur.month:02d}")
        # próximo mês
        if cur.month == 12:
            cur = datetime(cur.year + 1, 1, 1)
        else:
            cur = datetime(cur.year, cur.month + 1, 1)
    return result


def _aplicar_escopo(stored_data: dict) -> list[str]:
    """Filtra `equipment_ids` removendo `EQUIPAMENTOS_EXCLUIDOS` (BR-05 item 3). Não muta input."""
    eq_ids = stored_data.get("equipment_ids", []) or []
    return [eq_id for eq_id in eq_ids if eq_id not in cfg.EQUIPAMENTOS_EXCLUIDOS]


def _construir_rotulo_periodo(
    inicio_mensal: datetime,
    fim_mensal: datetime,
    modo: str,
    fuso_label: str = cfg.FUSO_LABEL,
) -> str:
    """Constrói rótulo `"Período: DD/MM/AAAA a DD/MM/AAAA (horário de Brasília)"` (SP-18).

    Para `MES_CORRENTE` exibe último dia incluso (`fim - 1 dia`); para `ULTIMOS_30_DIAS`
    exibe `fim` exato.
    """
    data_inicio = cfg.fmt_data(inicio_mensal)
    if modo == "MES_CORRENTE":
        data_fim = cfg.fmt_data(fim_mensal - timedelta(days=1))
    else:
        data_fim = cfg.fmt_data(fim_mensal)
    return f"Período: {data_inicio} a {data_fim} ({fuso_label})"


# =========================================================================
# Helpers de bloco (D9 — funções pequenas e isoladas)
# =========================================================================

def _build_kpis_bloco_planta(
    eq_ids: list[str],
    inicio: datetime,
    fim: datetime,
    targets: dict,
    names: dict[str, str],
    categories: dict[str, list[str]],
    kpi_data: dict,
    year: int = None,
    monthly_aggregates: dict = None,
    as_png: bool = True,
) -> dict[str, Any]:
    """Helper compartilhado por Blocos 1 e 3 — KPIs planta + 3 sunbursts.

    `kpi_data` deve corresponder à janela específica do bloco — para Bloco 1
    usar dataset mensal (`stored_data["data"]`); para Bloco 3 usar fresh fetch
    com `fetch_zpp_kpi_data(inicio_24h, fim_24h)` (a tabela mensal não tem
    granularidade diária — IM-07 fix).

    `as_png`: True (DOCX) → `sunburst_figures` em bytes PNG via kaleido.
    False (tela — IM-08) → `sunburst_figures` em objetos Plotly Figure nativos
    para renderização interativa via `dcc.Graph`.

    Retorna dict com `kpis_planta`, `sunburst_figures`, `metas`, `cores_kpis`,
    `alert_range`.
    """
    year_months = _date_range_to_year_months(inicio, fim)
    months = sorted({int(ym.split("-")[1]) for ym in year_months})

    averages = calculate_kpi_averages(
        kpi_data,
        eq_ids,
        month_filter=months,
        year=year,
        monthly_aggregates=monthly_aggregates,
        year_months=year_months,
    )

    # Conversão de MTTR de horas → minutos. Tela exibe em minutos:
    # `calculate_kpi_averages` retorna em HORAS, `targets[*]["mttr"]` está em HORAS no banco;
    # a página Indicadores multiplica ambos por 60 antes de exibir/comparar (ver
    # maintenance_kpi_callbacks.py:493-494). Replicamos o mesmo padrão aqui.
    def _h_to_min(v):
        return (v * 60) if isinstance(v, (int, float)) else v

    general = (targets or {}).get("GENERAL", {}) or {}
    metas = {
        "mtbf": general.get("mtbf"),
        "mttr": _h_to_min(general.get("mttr")),
        "taxa_avaria": general.get("breakdown_rate"),
    }
    alert_range = general.get("alert_range", 3.0)

    kpis_planta = {
        "mtbf": averages.get("mtbf"),
        "mttr": _h_to_min(averages.get("mttr")),
        "taxa_avaria": averages.get("breakdown_rate"),
    }

    cores_kpis = {
        "mtbf":        get_kpi_color(kpis_planta["mtbf"],        metas["mtbf"],        "MTBF",            alert_range),
        "mttr":        get_kpi_color(kpis_planta["mttr"],        metas["mttr"],        "MTTR",            alert_range),
        "taxa_avaria": get_kpi_color(kpis_planta["taxa_avaria"], metas["taxa_avaria"], "breakdown_rate",  alert_range),
    }

    # Sunbursts — 3 por bloco (MTBF / MTTR / Taxa Avaria).
    # IMPORTANTE: `create_kpi_sunburst_chart` espera valores BRUTOS (MTTR em horas);
    # ela própria converte MTTR para minutos internamente (linha 561 de maintenance_kpi_graphs.py).
    # Mapping kpi_key (output) ↔ by_equipment_key (chave do dict interno):
    #   "mtbf"        → "mtbf"
    #   "mttr"        → "mttr"           (em horas — função converte)
    #   "taxa_avaria" → "breakdown_rate" (chave real no dict — IM-07 fix)
    by_equipment = averages.get("by_equipment", {}) or {}
    sunburst_specs = [
        # (kpi_key_output, kpi_name_plotly, by_eq_key, target_key, averages_key)
        ("mtbf",        "MTBF",            "mtbf",           "mtbf",           "mtbf"),
        ("mttr",        "MTTR",            "mttr",           "mttr",           "mttr"),
        ("taxa_avaria", "breakdown_rate",  "breakdown_rate", "breakdown_rate", "breakdown_rate"),
    ]
    sunburst_figures: dict = {}
    # Fase 1 — build sequencial dos Plotly Figures (rápido, ~0.1s cada).
    pending_renders = []  # [(kpi_key, fig, label)] — render PNG kaleido em paralelo abaixo.
    for kpi_key, kpi_name_plotly, by_eq_key, target_key, avg_key in sunburst_specs:
        data_by_eq = {eq: by_equipment.get(eq, {}).get(by_eq_key) for eq in eq_ids}
        target_individual = {eq: (targets or {}).get(eq, {}).get(target_key) for eq in eq_ids}
        plant_target_raw = general.get(target_key)
        plant_avg_raw = averages.get(avg_key)
        try:
            fig = create_kpi_sunburst_chart(
                data_by_eq,
                kpi_name_plotly,
                categories,
                names,
                template="minty",
                target_values=target_individual,
                plant_target=plant_target_raw,
                margin_percent=alert_range,
                show_average=True,
                plant_average=plant_avg_raw,
            )
            if as_png:
                # Aumenta fonte das legendas só na figura usada no DOCX — não afeta tela
                # (perfumaria 2026-05-13: legendas eram pequenas demais quando renderizadas).
                fig.update_layout(font=dict(size=22), margin=dict(t=8, b=8, l=8, r=8))
                pending_renders.append((kpi_key, fig, cfg.KPI_LABELS[kpi_key]))
            else:
                # Tela (IM-08) — retorna Plotly Figure nativo (interativo via dcc.Graph)
                sunburst_figures[kpi_key] = fig
        except Exception as exc:
            logger.warning("Falha ao construir sunburst %s: %s — usando placeholder", kpi_key, type(exc).__name__)
            if as_png:
                from src.utils.kpi_report_figures import _gerar_placeholder_png
                sunburst_figures[kpi_key] = _gerar_placeholder_png(cfg.KPI_LABELS[kpi_key], 900, 700, 2)
            else:
                sunburst_figures[kpi_key] = None  # tela trata None mostrando aviso

    # Fase 2 — render PNG em paralelo via Kaleido(n=4) (perf #1).
    if pending_renders:
        from src.utils.kpi_report_figures import renderizar_em_paralelo
        sunburst_figures.update(
            renderizar_em_paralelo(pending_renders, width=900, height=700, scale=2)
        )

    return {
        "kpis_planta":      kpis_planta,
        "sunburst_figures": sunburst_figures,
        "metas":            metas,
        "cores_kpis":       cores_kpis,
        "alert_range":      alert_range,
    }


def _build_top5_paradas(
    inicio: datetime,
    fim: datetime,
    names: dict[str, str],
    top_n: Optional[int] = 5,
) -> dict[str, Any]:
    """Helper compartilhado Blocos 2 e 5 — chama `fetch_top_breakdowns_all`,
    resolve nome via `names`, devolve `{"paradas": [...], "vazio": bool}` (SP-08).

    `top_n=None` lista todas as paradas (Bloco 5 — BR-03 itens 5/7 revistos em 2026-05-13).
    `top_n=5` mantém limite Top 5 (Bloco 2).
    """
    paradas_raw = fetch_top_breakdowns_all(inicio, fim, top_n=top_n)
    paradas = []
    for idx, p in enumerate(paradas_raw):
        eq_id = p.get("equipamento", "")
        dur_min = p.get("duration_min", 0)
        paradas.append({
            "posicao":     idx + 1,
            "equipamento": names.get(eq_id, eq_id),
            "data_hora":   cfg.fmt_data_hora(p["inicio_execucao"]),
            "duracao_min": f"{int(round(dur_min))} min",
            "causa":       p.get("causa_do_desvio", ""),
            "descricao":   p.get("descricao", ""),
        })
    return {"paradas": paradas, "vazio": len(paradas) == 0}


def build_detalhamento_table(
    eq_ids: list[str],
    kpi_data: dict,
    names: dict[str, str],
    months: list[int],
    year_months: Optional[list[str]],
    targets: dict,
) -> dict[str, Any]:
    """Constrói tabela Detalhamento do Bloco 4 + linha TOTAL DA PLANTA (SP-10).

    Reusa `_build_raw_table_internal` (extraída em IM-02 de `update_raw_data_tab`) para
    garantir equivalência exata com a tela (gate RR-01 / RV-07). Adiciona colunas de
    cor (BR-06) por linha. Retorna dict `{"linhas": [...], "total": {...}, "vazio": bool}`.
    """
    rows, totals = _build_raw_table_internal(kpi_data, eq_ids, names, months, year_months)

    general = (targets or {}).get("GENERAL", {}) or {}
    alert_range = general.get("alert_range", 3.0)

    def _target_for(eq_id: str, kpi: str) -> Optional[float]:
        eq_target = (targets or {}).get(eq_id, {}) or {}
        return eq_target.get(kpi, general.get(kpi))

    def _enrich(row: dict, eq_id: Optional[str]) -> dict:
        # Renomeia campos para alinhar com DS-03 contrato + adiciona cores
        out = dict(row)
        out["mtbf"]        = row.pop("mtbf_h", None) if "mtbf_h" in row else row.get("mtbf")
        out["mttr"]        = row.pop("mttr_min", None) if "mttr_min" in row else row.get("mttr")
        out["taxa_avaria"] = row.get("taxa_avaria")
        out["cor_mtbf"]        = get_kpi_color(out["mtbf"],        _target_for(eq_id, "mtbf") if eq_id else general.get("mtbf"),       "MTBF",           alert_range)
        out["cor_mttr"]        = get_kpi_color(out["mttr"],        _target_for(eq_id, "mttr") if eq_id else general.get("mttr"),       "MTTR",           alert_range)
        out["cor_taxa_avaria"] = get_kpi_color(out["taxa_avaria"], _target_for(eq_id, "breakdown_rate") if eq_id else general.get("breakdown_rate"), "breakdown_rate", alert_range)
        return out

    linhas = [_enrich(r, r.get("eq_id")) for r in rows]
    total_enriched = _enrich({**totals, "equipamento": "TOTAL"}, None)

    return {
        "linhas": linhas,
        "total":  total_enriched,
        "vazio":  len(linhas) == 0,
    }


# =========================================================================
# Orquestrador — coletar_dados_relatorio (SP-04 item 6)
# =========================================================================

def coletar_dados_relatorio(stored_data: dict, agora: datetime, as_png: bool = True) -> dict:
    """Orquestra coleta completa — devolve dict consolidado para o template.

    Estrutura em SP-04 item 6 + DS-03 (chaves `periodo`, `bloco1..5`, `planta_vazia`).
    `agora` aware no fuso (`_now_in_report_timezone`). `stored_data` validado pelo callback.

    `as_png`: True (default — DOCX) gera sunbursts em PNG via kaleido. False (tela,
    IM-08) devolve `plotly.graph_objects.Figure` nativos para renderização interativa.
    """
    eq_ids = _aplicar_escopo(stored_data)
    names = stored_data.get("names", {}) or {}
    categories = stored_data.get("categories") or get_zpp_equipment_categories()
    targets = stored_data.get("equipment_targets") or get_all_equipment_targets()

    # Janelas
    modo = cfg.PERIODO_RELATORIO_MODO
    ini_mensal, fim_mensal = cfg.compute_monthly_window(agora, modo)
    ini_24h, fim_24h       = cfg.compute_last_24h_window(agora)

    periodo = {
        "modo":          modo,
        "inicio_mensal": ini_mensal,
        "fim_mensal":    fim_mensal,
        "inicio_24h":    ini_24h,
        "fim_24h":       fim_24h,
        "fuso":          cfg._resolve_timezone().key,
        "rotulo":        _construir_rotulo_periodo(ini_mensal, fim_mensal, modo),
        "data_clique":   agora,
    }

    # Datasets: cada bloco faz fresh fetch da sua própria janela. NÃO reusar
    # `stored_data["data"]` — o store reflete o filtro custom da página, que pode
    # divergir do mês corrente (bug reportado em 2026-05-13: filtro "11→11" da tela
    # contaminava Bloco 1 do DOCX, violando BR-01). Custo: 2 queries Mongo extras
    # por geração, sem cache do store.
    #
    # Perf #4: 4 queries Mongo independentes (data_mensal, data_24h, top5 mensal,
    # top5 24h) executam em paralelo via ThreadPool. PyMongo libera GIL no I/O.
    from concurrent.futures import ThreadPoolExecutor as _TPE

    def _safe_fetch_kpi(ini, fim, label):
        try:
            return fetch_zpp_kpi_data(ini, fim)
        except Exception as exc:
            logger.warning("Falha ao buscar dados %s: %s — usando dict vazio",
                            label, type(exc).__name__)
            return {}

    def _safe_top5(ini, fim, names_arg, top_n=5):
        try:
            return _build_top5_paradas(ini, fim, names_arg, top_n=top_n)
        except Exception as exc:
            logger.warning("Falha ao buscar top5 paradas (%s, %s): %s",
                            ini, fim, type(exc).__name__)
            return {"paradas": [], "total": 0, "vazio": True}

    with _TPE(max_workers=4, thread_name_prefix="kpi-mongo") as _pool:
        _f_mensal = _pool.submit(_safe_fetch_kpi, ini_mensal, fim_mensal, "mensais para Bloco 1/4")
        _f_24h    = _pool.submit(_safe_fetch_kpi, ini_24h, fim_24h, "24h para Bloco 3")
        _f_b2     = _pool.submit(_safe_top5, ini_mensal, fim_mensal, names, 5)
        # Bloco 5 lista TODAS as paradas das 24h, sem limite (BR-03 itens 5/7 revistos 2026-05-13)
        _f_b5     = _pool.submit(_safe_top5, ini_24h, fim_24h, names, None)
        data_mensal = _f_mensal.result()
        data_24h    = _f_24h.result()
        bloco2      = _f_b2.result()
        bloco5      = _f_b5.result()

    # `year` e `monthly_aggregates` derivam da janela mensal própria do DOCX,
    # não do store da página — força recomputação a partir de data_mensal.
    year = ini_mensal.year

    bloco1 = _build_kpis_bloco_planta(eq_ids, ini_mensal, fim_mensal, targets, names, categories,
                                       kpi_data=data_mensal, year=year, monthly_aggregates=None,
                                       as_png=as_png)
    bloco3 = _build_kpis_bloco_planta(eq_ids, ini_24h, fim_24h, targets, names, categories,
                                       kpi_data=data_24h, year=year, monthly_aggregates=None,
                                       as_png=as_png)

    year_months = _date_range_to_year_months(ini_mensal, fim_mensal)
    months = sorted({int(ym.split("-")[1]) for ym in year_months})
    bloco4 = build_detalhamento_table(eq_ids, data_mensal, names, months, year_months, targets)

    # planta_vazia = ambos blocos planta sem dados
    def _kpis_vazio(b):
        return all(v is None for v in b.get("kpis_planta", {}).values())
    planta_vazia = _kpis_vazio(bloco1) and _kpis_vazio(bloco3)

    return {
        "periodo":      periodo,
        "bloco1":       bloco1,
        "bloco2":       bloco2,
        "bloco3":       bloco3,
        "bloco4":       bloco4,
        "bloco5":       bloco5,
        "planta_vazia": planta_vazia,
    }
