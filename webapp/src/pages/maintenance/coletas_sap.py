"""Coletas SAP (/maintenance/coletas-sap) — página consolidada do perfil manutenção.

Junta num só lugar (decisão 2026-06-30):
- **Disparo manual** ("Rodar agora") de todas as coletas SAP — antes isolado no rodapé do
  overview (`build_rerun_controls`).
- **Agendamento** de todas as coletas (zppprd, nt0001, backlog, HH, custos) — antes só na
  página admin `/config/sap-scheduler` (que agora redireciona para cá).

Acesso: perfil `manutencao` nível 2+ (PCM gerencia agendamentos e dispara coletas).
Reutiliza `agendamento_section` (ids `sap-sched-*`) e os botões de `manual_trigger` — sem
duplicar callbacks.
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html
from flask_login import current_user

from src.pages.admin.sap_scheduler_config import agendamento_section
from src.sap_scheduler.manual_trigger import build_rerun_controls


def layout_wrapper():
    """Entry point registrada em ROUTES. Captura `current_user` em request scope Flask."""
    return layout(current_user)


def layout(user):
    """Página: cabeçalho + disparo manual + agendamento (seção reutilizada)."""
    return dbc.Container(
        [
            html.H3([html.I(className="bi bi-cloud-arrow-down me-2"), "Coletas SAP"],
                    className="mt-3 mb-1"),
            html.P("Dispare uma coleta na hora (disparo manual) ou configure os horários "
                   "automáticos das coletas SAP — produção, paradas, backlog, Hora-Homem e custos.",
                   className="text-muted"),
            # disparo manual ("Rodar agora") — todos os tipos
            dbc.Card(
                dbc.CardBody([
                    html.H5([html.I(className="bi bi-lightning-charge me-2"), "Disparar agora"],
                            className="mb-2"),
                    html.P("Roda a coleta imediatamente (uma vez), sem mexer no horário agendado.",
                           className="text-muted small"),
                    build_rerun_controls(user),
                ]),
                className="mb-4",
            ),
            # agendamento (seção reutilizada da página antiga)
            *agendamento_section(user),
        ],
        fluid=True,
    )
