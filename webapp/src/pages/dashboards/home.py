# src/pages/dashboards/home.py

from dash import html
import dash_bootstrap_components as dbc
from src.sap_scheduler.rodape_component import build_rodape


def layout():
    """
    Dashboard principal - Visão geral de toda a fábrica.

    Conteúdo de demonstração removido; aguardando integração com dados reais.
    """
    return dbc.Container([

        # ========================================
        # HEADER DA PÁGINA
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H2("🏭 Visão Geral da Fábrica"),
            ])
        ], className="mb-4"),

        build_rodape(),

    ], fluid=True, className="p-4")
