"""Factory pura do componente do rodapé da home (DS-03 + IM-C1).

Retorna `dbc.Row` única com `dbc.Col(id=...)` vazio — preenchido pelo
callback `timestamp_callback.register_callback` (IM-C2).

Função pura, sem deps de Mongo/config — testável isolada em QA frontend.
"""
from __future__ import annotations

from dash import html
import dash_bootstrap_components as dbc

RODAPE_CONTENT_ID = "rodape-sap-scheduler-content"


def build_rodape():
    """Retorna `dbc.Row` única pro fim do `dbc.Container` da home.

    DS-03 RV-01 F-01-04: posicionar **fora** das Rows existentes (preserva
    BR-09 #3 — layout dos KPIs pixel-idêntico).

    O conteúdo (children) é populado pelo callback Dash em tempo de render.
    Boot inicial mostra o placeholder.
    """
    return dbc.Row(
        dbc.Col(
            html.Span(
                "Carregando status das coletas SAP...",
                id=RODAPE_CONTENT_ID,
                className="text-muted small",
            ),
            width=12,
            className="text-center",
        ),
        className="mt-3 pt-2 border-top",
    )
