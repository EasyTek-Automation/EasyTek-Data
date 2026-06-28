# -*- coding: utf-8 -*-
"""Callbacks da página Backlog de Manutenção (SDD Backlog, Bloco B).

Carga do snapshot → cards + tabela + selo de frescor, respeitando os 6 filtros.
Lê só do Mongo (`sap_backlog`) via utils.backlog_data. Degradação graciosa (RNF-05).

Atualizar-agora / export ficam no Bloco C (callbacks adicionados depois).
"""
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import pytz
from dash import Output, Input, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask_login import current_user

try:
    from src.utils import backlog_data as bd
    from src.utils import backlog_pdf
    from src.database.connection import get_mongo_connection
    from src.sap_scheduler.manual_trigger import inserir_job_manual
except ImportError:
    from utils import backlog_data as bd
    from utils import backlog_pdf
    from database.connection import get_mongo_connection
    from sap_scheduler.manual_trigger import inserir_job_manual

_TZ = "America/Sao_Paulo"
_COOLDOWN_S = 300          # 5 min (RF-09.3)
_MIN_LEVEL_TRIGGER = 2     # nível mínimo para acionar a coleta (RF-09.2)

_BRT = pytz.timezone("America/Sao_Paulo")
_LIMITE_FRESCOR_H = 26  # alinhado ao frescor_horas_limite do sap-scheduler

_DISC = bd.DISCIPLINAS  # ["Mecanica","Eletrica","NaoClassificado"]
LABEL_DISC = {"Mecanica": "Mecânica", "Eletrica": "Elétrica", "NaoClassificado": "Não classificado"}
LABEL_SUB = {"Corretiva": "Corretiva", "PDCA": "PDCA",
             "CorretivaProgramada": "Corretiva Programada", "Preditiva": "Preditiva"}

# colunas do export XLSX (id interno → nome amigável)
_COLS_EXPORT = [
    {"id": "ordem", "name": "Ordem"},
    {"id": "descricao", "name": "Descrição"},
    {"id": "categoria", "name": "Categoria"},
    {"id": "disciplina", "name": "Disciplina"},
    {"id": "centro_operacao_0010", "name": "Centro / Operação"},
    {"id": "data_inicio", "name": "Início"},
    {"id": "local_pai_nome", "name": "Linha"},
    {"id": "local_descricao", "name": "Conjunto"},
    {"id": "local_instalacao_cod", "name": "Cód. conjunto"},
]


def _fmt_data(di):
    """datetime → 'DD/MM/YYYY'; vazio se não for data."""
    return di.strftime("%d/%m/%Y") if isinstance(di, datetime) else ""


def _to_aware_utc(dt):
    """Normaliza datetime (naïve do Mongo = UTC) para aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return pytz.UTC.localize(dt)
    return dt.astimezone(pytz.UTC)


def _fmt_frescor(coletado_em):
    """Selo de frescor: 'Atualizado às HH:MM de DD/MM' + alerta se > 26h (RF-10.3)."""
    if not coletado_em:
        return "Sem coleta ainda — rode 'Atualizar agora'"
    dt = _to_aware_utc(coletado_em)
    local = dt.astimezone(_BRT)
    agora = datetime.now(tz=pytz.UTC)
    horas = (agora - dt).total_seconds() / 3600.0
    base = f"Atualizado às {local.strftime('%H:%M')} de {local.strftime('%d/%m')}"
    if horas > _LIMITE_FRESCOR_H:
        return f"⚠ {base} — dado pode estar desatualizado ({int(horas)}h)"
    return base


def _parse_date(s):
    """ISO 'YYYY-MM-DD' (DatePickerRange) → datetime naïve à meia-noite, ou None."""
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


# dígito final do centro Zxy → descrição da operação (subclassificação embutida no centro)
_SUB_POR_DIGITO = {"0": "Corretiva", "1": "PDCA", "2": "Corretiva Programada", "3": "Preditiva"}


def _centro_label(centro):
    """Centro + descrição da operação na mesma célula. Ex: 'Z10 - Corretiva';
    'Z02 - Técnicos de Manutenção'; sem centro → '—'."""
    if not centro:
        return "—"
    c = str(centro).strip().upper()
    if c == "Z02":
        return "Z02 - Técnicos de Manutenção"
    if c[:2] in ("Z1", "Z2") and len(c) >= 3:
        sub = _SUB_POR_DIGITO.get(c[2])
        if sub:
            return f"{c} - {sub}"
    return c


def _local_label(o):
    """Local: 'NOME (CÓDIGO)'. Só nome se faltar código; só código se faltar nome."""
    nome = (o.get("local_descricao") or "").strip()
    cod = (o.get("local_instalacao") or "").strip()
    if nome and cod:
        return f"{nome} ({cod})"
    return nome or cod


def _linha_tabela(o):
    return {
        "ordem": o.get("ordem", ""),
        "descricao": o.get("descricao", ""),
        "categoria": o.get("categoria", ""),  # mantido p/ export (coluna removida da tabela)
        "disciplina": LABEL_DISC.get(o.get("disciplina"), "—"),
        "centro_operacao_0010": _centro_label(o.get("centro_operacao_0010")),
        "data_inicio": _fmt_data(o.get("data_inicio")),
        "local_pai_nome": o.get("_linha_nome", ""),                 # coluna Linha (oficial)
        "local_instalacao": o.get("_conjunto_nome") or "—",         # coluna Conjunto (oficial)
        "local_descricao": o.get("_conjunto_nome", ""),             # export: Conjunto
        "local_instalacao_cod": (o.get("local_instalacao") or "").strip(),  # export: código TPLNR
    }


_NAVY = "#08137C"
_COR_CATEGORIA = ["#198754", "#dc3545", "#fd7e14", "#6f42c1"]   # Prev/Corr/Melh/Matr
_COR_DISCIPLINA = ["#08137C", "#20c997", "#adb5bd"]             # Mec/Ele/NãoClass
_COR_LINHA = ["#08137C", "#0d6efd", "#20c997", "#198754", "#fd7e14",
              "#6f42c1", "#dc3545", "#0dcaf0", "#adb5bd"]


def _donut(labels, valores, cores, centro):
    """Rosca (Pie hole) com total no centro. Vazia se soma 0."""
    if not sum(valores or [0]):
        fig = go.Figure()
        fig.update_layout(margin=dict(t=6, b=6, l=6, r=6), height=270,
                          annotations=[dict(text="Sem dados", x=0.5, y=0.5,
                                            showarrow=False, font=dict(size=13, color="#adb5bd"))],
                          xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig
    fig = go.Figure(go.Pie(labels=labels, values=valores, hole=0.58, sort=False,
                           marker=dict(colors=cores, line=dict(color="#fff", width=1)),
                           textinfo="value", textfont=dict(size=11),
                           hovertemplate="%{label}: %{value} (%{percent})<extra></extra>"))
    fig.update_layout(
        margin=dict(t=6, b=6, l=6, r=6), height=270,
        legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center", font=dict(size=10)),
        annotations=[dict(text=f"<b>{int(sum(valores))}</b>", x=0.5, y=0.5, showarrow=False,
                          font=dict(size=24, color=_NAVY))],
    )
    return fig


def _barras(labels, valores):
    """Barras do backlog por mês/ano (navy)."""
    if not sum(valores or [0]):
        fig = go.Figure()
        fig.update_layout(margin=dict(t=6, b=6, l=6, r=6), height=250,
                          annotations=[dict(text="Sem dados", x=0.5, y=0.5, showarrow=False,
                                            font=dict(size=13, color="#adb5bd"))],
                          xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig
    fig = go.Figure(go.Bar(x=labels, y=valores, marker_color=_NAVY,
                           hovertemplate="%{x}: %{y} ordens<extra></extra>"))
    fig.update_layout(
        margin=dict(t=8, b=44, l=8, r=8), height=250, bargap=0.25,
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        yaxis=dict(gridcolor="#eef0f6", zeroline=False),
    )
    return fig


def _li(label, valor, cor=_NAVY):
    return html.Div([
        html.Span(f"{valor}", className="fw-bold", style={"color": cor, "fontSize": "1.05rem"}),
        html.Span(f"  {label}", className="text-muted small"),
    ], className="mb-2")


def _render_insights(ins: dict):
    """Painel de texto a partir do dict de insights."""
    linhas = []
    if ins.get("mais_antiga_dias") is not None:
        linhas.append(_li(f"a mais antiga — OS {ins['mais_antiga_ordem']}",
                          f"{ins['mais_antiga_dias']} dias", "#dc3545"))
    linhas.append(_li(f"não reclassificadas ({ins.get('nc_n', 0)})",
                      f"{ins.get('nc_pct', 0)}%", "#fd7e14"))
    if ins.get("linha_top_nome"):
        linhas.append(_li(f"ordens na linha mais carregada ({ins['linha_top_nome']})",
                          f"{ins['linha_top_n']}"))
    if ins.get("inflow_30") is not None:
        linhas.append(_li("abertas nos últimos 30 dias", f"{ins['inflow_30']}"))
    if ins.get("idade_media") is not None:
        linhas.append(_li(f"idade média (mediana {ins['idade_mediana']} d)",
                          f"{ins['idade_media']} d"))
    if ins.get("razao_cp") is not None:
        linhas.append(_li("corretivas por preventiva", f"{ins['razao_cp']}"))
    return linhas


def _descrever_filtros(cat, disc, sub, linhas_ids, dt_ini, dt_fim, busca, idx):
    """Texto humano dos filtros ativos, para o cabeçalho do PDF."""
    parts = []
    if cat:
        parts.append("Categoria: " + ", ".join(cat))
    if disc:
        parts.append("Disciplina: " + ", ".join(LABEL_DISC.get(d, d) for d in disc))
    if sub:
        parts.append("Subclassificação: " + ", ".join(LABEL_SUB.get(x, x) for x in sub))
    if linhas_ids:
        nomes = [(idx.get(i) or {}).get("descricao", i) for i in linhas_ids]
        parts.append("Linha: " + ", ".join(nomes))
    if dt_ini or dt_fim:
        parts.append(f"Período: {dt_ini or '...'} a {dt_fim or '...'}")
    if busca:
        parts.append(f"Busca: '{busca}'")
    return " · ".join(parts) if parts else "Backlog completo (sem filtros)"


def _saida_vazia(frescor_txt):
    """Saída offline/sem-dado: roscas + barras vazias + insights vazio + tabela vazia."""
    vazio = _donut([], [], [], 0)
    return (vazio, vazio, _barras([], []),
            html.Div("Sem dados.", className="text-muted small"), [], frescor_txt)


def register_backlog_callbacks(app):
    """Registra os callbacks do Backlog (carga, filtros, limpar)."""

    @app.callback(
        Output("bk-rosca-cat", "figure"),
        Output("bk-rosca-linha", "figure"),
        Output("bk-barras-mes", "figure"),
        Output("bk-insights", "children"),
        Output("bk-table", "data"),
        Output("bk-frescor", "children"),
        Input("bk-interval-load", "n_intervals"),
        Input("btn-apply-backlog-filters", "n_clicks"),
        Input("btn-backlog-clear", "n_clicks"),
        Input("bk-rosca-mode", "value"),
        State("bk-f-categoria", "value"),
        State("bk-f-disciplina", "value"),
        State("bk-f-subclass", "value"),
        State("bk-f-local-pai", "value"),
        State("bk-f-periodo", "start_date"),
        State("bk-f-periodo", "end_date"),
        State("bk-f-busca", "value"),
    )
    def carregar(_n_int, _n_apply, _n_clear, rosca_mode, cat, disc, sub, locais_pai,
                 dt_ini, dt_fim, busca):
        snap = bd.carregar_snapshot(silent=True)
        if snap is None:
            return _saida_vazia("⚠ Banco indisponível")
        bd.enriquecer_local(snap["ordens"], bd.carregar_ativos())

        # 'Limpar' ignora os filtros (a redefinição visual é outro callback)
        if ctx.triggered_id == "btn-backlog-clear":
            filtros = {}
        else:
            filtros = {
                "categoria": cat or [],
                "disciplina": disc or [],
                "subclassificacao": sub or [],
                "linha": locais_pai or [],
                "busca": busca or "",
                "periodo_ini": _parse_date(dt_ini),
                "periodo_fim": _parse_date(dt_fim),
            }

        visiveis = bd.filtrar(snap["ordens"], filtros)

        # Rosca 1: Categoria ou Disciplina (toggle)
        if rosca_mode == "disc":
            lab, val = bd.dados_rosca_disciplina(visiveis)
            fig_cat = _donut(lab, val, _COR_DISCIPLINA, sum(val))
        else:
            lab, val = bd.dados_rosca_categoria(visiveis)
            fig_cat = _donut(lab, val, _COR_CATEGORIA, sum(val))
        # Rosca 2: por Linha (equipamento-pai)
        lab2, val2 = bd.dados_rosca_linha(visiveis, topn=8)
        fig_linha = _donut(lab2, val2, _COR_LINHA, sum(val2))
        # Barras: backlog por mês/ano (data de início)
        labm, valm = bd.dados_barras_mes(visiveis)
        fig_barras = _barras(labm, valm)

        insights = _render_insights(bd.insights(visiveis))
        tabela = [_linha_tabela(o) for o in visiveis]
        return (fig_cat, fig_linha, fig_barras, insights, tabela,
                _fmt_frescor(snap.get("coletado_em")))

    @app.callback(
        Output("bk-f-categoria", "value"),
        Output("bk-f-disciplina", "value"),
        Output("bk-f-subclass", "value"),
        Output("bk-f-local-pai", "value"),
        Output("bk-f-periodo", "start_date"),
        Output("bk-f-periodo", "end_date"),
        Output("bk-f-busca", "value"),
        Input("btn-backlog-clear", "n_clicks"),
        prevent_initial_call=True,
    )
    def limpar_filtros(n):
        if not n:
            raise PreventUpdate
        return [], [], [], [], None, None, ""

    # popula as opções do multi de Local (níveis-pai) a partir do snapshot
    @app.callback(
        Output("bk-f-local-pai", "options"),
        Input("bk-interval-load", "n_intervals"),
    )
    def popular_locais_pai(_n):
        idx = bd.carregar_ativos()
        return bd.opcoes_linhas(idx) if idx else []

    # --- IM-11 — Atualizar agora (level 2+) + cooldown 5 min -----------------------------
    @app.callback(
        Output("btn-backlog-refresh", "disabled"),
        Output("bk-refresh-status", "children"),
        Output("bk-last-trigger", "data"),
        Input("btn-backlog-refresh", "n_clicks"),
        Input("bk-cooldown", "n_intervals"),
        State("bk-last-trigger", "data"),
    )
    def atualizar_agora(n_click, _tick, last_iso):
        agora = datetime.now(tz=pytz.UTC)

        # clique no botão → tenta disparar a coleta
        if ctx.triggered_id == "btn-backlog-refresh" and n_click:
            if getattr(current_user, "level", 0) < _MIN_LEVEL_TRIGGER:
                return False, "🔒 Sem permissão — atualizar requer nível ≥ 2.", no_update
            db = get_mongo_connection()
            if db is None:
                return False, "⚠ Banco indisponível — tente novamente.", no_update
            try:
                res = inserir_job_manual(db, "backlog", _TZ)
            except Exception as e:  # noqa: BLE001
                return False, f"❌ Falha ao disparar: {e}", no_update
            msg = {
                "inserido": "⏳ Coletando… o backlog atualiza em ~1–2 min (reabra a página).",
                "ja_em_andamento": "⏳ Já há uma coleta em andamento.",
                "dedup": "⏳ Coleta já solicitada neste minuto.",
            }.get(res, "❌ Falha ao disparar a coleta.")
            disparou = res in ("inserido", "ja_em_andamento", "dedup")
            return disparou, msg, (agora.isoformat() if disparou else no_update)

        # tick do cooldown → re-habilita o botão depois de 5 min
        if last_iso:
            try:
                last = datetime.fromisoformat(last_iso)
            except (ValueError, TypeError):
                last = None
            if last and (agora - last).total_seconds() < _COOLDOWN_S:
                restante = int(_COOLDOWN_S - (agora - last).total_seconds())
                return True, f"⏳ Aguardando coleta… (cooldown {restante}s)", no_update
        return False, "", no_update

    # --- Itens por página da tabela -----------------------------------------------------
    @app.callback(
        Output("bk-table", "page_size"),
        Input("bk-page-size", "value"),
    )
    def ajustar_page_size(valor):
        try:
            return max(1, int(valor))
        except (ValueError, TypeError):
            return 20

    # --- IM-12 — Export XLSX do recorte filtrado ----------------------------------------
    @app.callback(
        Output("download-backlog-xlsx", "data"),
        Input("btn-backlog-export", "n_clicks"),
        State("bk-f-categoria", "value"),
        State("bk-f-disciplina", "value"),
        State("bk-f-subclass", "value"),
        State("bk-f-local-pai", "value"),
        State("bk-f-periodo", "start_date"),
        State("bk-f-periodo", "end_date"),
        State("bk-f-busca", "value"),
        prevent_initial_call=True,
    )
    def exportar(n, cat, disc, sub, locais_pai, dt_ini, dt_fim, busca):
        if not n:
            raise PreventUpdate
        snap = bd.carregar_snapshot(silent=True)
        if snap is None:
            raise PreventUpdate
        bd.enriquecer_local(snap["ordens"], bd.carregar_ativos())
        filtros = {
            "categoria": cat or [], "disciplina": disc or [], "subclassificacao": sub or [],
            "linha": locais_pai or [], "busca": busca or "",
            "periodo_ini": _parse_date(dt_ini), "periodo_fim": _parse_date(dt_fim),
        }
        visiveis = bd.filtrar(snap["ordens"], filtros)
        linhas = [_linha_tabela(o) for o in visiveis]
        df = pd.DataFrame(linhas, columns=[c["id"] for c in _COLS_EXPORT])
        df.columns = [c["name"] for c in _COLS_EXPORT]
        hoje = datetime.now(tz=pytz.timezone(_TZ)).strftime("%Y%m%d")
        return dcc.send_data_frame(df.to_excel, f"backlog_BR02_{hoje}.xlsx",
                                   sheet_name="Backlog", index=False)

    # --- Exportar PDF (relatório do recorte filtrado) -----------------------------------
    @app.callback(
        Output("download-backlog-pdf", "data"),
        Input("btn-backlog-pdf", "n_clicks"),
        State("bk-f-categoria", "value"),
        State("bk-f-disciplina", "value"),
        State("bk-f-subclass", "value"),
        State("bk-f-local-pai", "value"),
        State("bk-f-periodo", "start_date"),
        State("bk-f-periodo", "end_date"),
        State("bk-f-busca", "value"),
        prevent_initial_call=True,
    )
    def exportar_pdf(n, cat, disc, sub, locais_pai, dt_ini, dt_fim, busca):
        if not n:
            raise PreventUpdate
        snap = bd.carregar_snapshot(silent=True)
        if snap is None:
            raise PreventUpdate
        idx = bd.carregar_ativos()
        bd.enriquecer_local(snap["ordens"], idx)
        filtros = {
            "categoria": cat or [], "disciplina": disc or [], "subclassificacao": sub or [],
            "linha": locais_pai or [], "busca": busca or "",
            "periodo_ini": _parse_date(dt_ini), "periodo_fim": _parse_date(dt_fim),
        }
        visiveis = bd.filtrar(snap["ordens"], filtros)
        desc = _descrever_filtros(cat, disc, sub, locais_pai, dt_ini, dt_fim, busca, idx)
        pdf_bytes = backlog_pdf.gerar_pdf(visiveis, desc, _fmt_frescor(snap.get("coletado_em")))
        hoje = datetime.now(tz=pytz.timezone(_TZ)).strftime("%Y%m%d")
        return dcc.send_bytes(lambda b: b.write(pdf_bytes), f"backlog_BR02_{hoje}.pdf")
