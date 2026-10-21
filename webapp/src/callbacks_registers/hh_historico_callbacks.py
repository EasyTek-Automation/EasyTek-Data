# -*- coding: utf-8 -*-
"""Callbacks da aba Histórico Semanal (SDD hh-historico, fase 06).

- Bloco B: carregamento **lazy** — preenche `hist-content` quando a aba é ativada.
- Bloco D: painel **reativo** — reconstrói cards+gráficos a cada mudança de período/modo/N/janela;
  e persiste a janela de insights (BR-13) em `hh_config`.
"""
import logging

import dash
from dash import Input, Output, State

try:
    from src.pages.maintenance import hh_historico
    from src.utils import hh_historico_data as hh
except ImportError:
    from pages.maintenance import hh_historico
    from utils import hh_historico_data as hh

_log = logging.getLogger(__name__)


def register_hh_historico_callbacks(app):
    """Registra o carregamento lazy + o painel reativo + a persistência da janela de insights."""

    @app.callback(
        Output("hist-content", "children"),
        Input("backlog-tabs", "active_tab"),
    )
    def _carregar_historico(active_tab):
        """Monta o corpo da aba (cabeçalho + controles + painel) só quando ela vira ativa (lazy).

        Sem `prevent_initial_call`: quando o `active_tab` é **persistido** como `tab-historico`
        (o PCM recarregou a página nessa aba — persistence_type=session em `backlog-tabs`), o
        conteúdo tem que ser montado no load inicial. O guard abaixo evita trabalho nas demais abas."""
        if active_tab != "tab-historico":
            return dash.no_update
        try:
            return hh_historico.hist_body()
        except Exception:
            _log.exception("hist_body falhou — servindo fallback")
            return hh_historico.hist_placeholder()

    @app.callback(
        Output("hist-painel", "children"),
        Input("hist-periodo", "start_date"),
        Input("hist-periodo", "end_date"),
        Input("hist-modo", "value"),
        Input("hist-n", "value"),
        Input("hist-insights-janela", "value"),
    )
    def _painel(d_ini, d_fim, modo, n, janela):
        """Reconstrói o painel (cards + gráficos + insights) para o período e modo escolhidos."""
        try:
            return hh_historico.build_painel(d_ini, d_fim, modo, n, janela)
        except Exception:
            _log.exception("build_painel falhou")
            return hh_historico.hist_placeholder()

    @app.callback(
        Output("hist-insights-saved", "data"),
        Input("hist-insights-janela", "value"),
        prevent_initial_call=True,
    )
    def _salvar_janela(n):
        """Persiste a janela dos insights (1–52) em hh_config quando o usuário a edita (BR-13)."""
        if n is None:
            return dash.no_update
        return hh.salvar_insights_janela(n)

    def _janela_ok(janela):
        try:
            return max(1, min(52, int(janela or hh.INSIGHTS_JANELA_DEFAULT)))
        except (TypeError, ValueError):
            return hh.INSIGHTS_JANELA_DEFAULT

    @app.callback(
        Output("hist-replan-modal", "is_open"),
        Output("hist-replan-modal-body", "children"),
        Input("hist-replan-btn", "n_clicks"),
        State("hist-insights-janela", "value"),
        prevent_initial_call=True,
    )
    def _abrir_replan_detalhe(n, janela):
        """Abre o modal e popula com a tabela que compõe o Top motivos (drill-down, BR-13)."""
        if not n:
            return dash.no_update, dash.no_update
        j = _janela_ok(janela)
        rows = hh.insight_replan_detalhe(j)
        motivos = [(m["motivo"], m["total"]) for m in hh.insight_top_motivos(j)]
        return True, hh_historico._replan_detalhe_body(rows, motivos, "__all")

    @app.callback(
        Output("hist-replan-table", "children"),
        Input("hist-replan-motivo", "value"),
        State("hist-insights-janela", "value"),
        prevent_initial_call=True,
    )
    def _filtrar_replan_detalhe(motivo, janela):
        """Refiltra a tabela do modal por motivo (ex: só 'Outro' — o porquê dos 105)."""
        mv = None if (not motivo or motivo == "__all") else motivo
        rows = hh.insight_replan_detalhe(_janela_ok(janela), motivo=mv)
        return hh_historico._replan_table(rows)

    @app.callback(
        Output("hist-semana-modal", "is_open"),
        Output("hist-semana-sel", "data"),
        Output("hist-semana-modal-body", "children", allow_duplicate=True),
        Input("hist-fluxo-graph", "clickData"),
        State("hist-weeks", "data"),
        prevent_initial_call=True,
    )
    def _abrir_semana(click, weeks):
        """Clique numa semana → abre o modal NA HORA (com spinner) e guarda a semana p/ o preenchimento."""
        if not click:
            return dash.no_update, dash.no_update, dash.no_update
        lbl = (click.get("points") or [{}])[0].get("x")
        iso = next((w for w in (weeks or []) if hh_historico._wlabel(w) == lbl), None)
        if not iso:
            return dash.no_update, dash.no_update, dash.no_update
        # abre já + limpa o corpo (spinner do dcc.Loading aparece enquanto o 2º callback monta)
        return True, iso, None

    @app.callback(
        Output("hist-semana-modal-body", "children"),
        Input("hist-semana-sel", "data"),
        prevent_initial_call=True,
    )
    def _preencher_semana(iso):
        """Monta o corpo do modal (resumo + mini-gráficos por disciplina) da semana selecionada."""
        if not iso:
            return dash.no_update
        return hh_historico._semana_modal_body(hh.detalhe_semana(iso))
