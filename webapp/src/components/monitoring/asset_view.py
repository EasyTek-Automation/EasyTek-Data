# -*- coding: utf-8 -*-
"""O croqui de um ativo, recortado do desenho do grupo (DS-07).

A página do ativo mostra **um** ativo, mas os desenhos de origem trazem vários lado a lado.
Em vez de gerar oito arquivos, serve-se o mesmo desenho com o `viewBox` recortado à faixa
daquele ativo.

Por que recorte e não oito arquivos: arquivos independentes reintroduzem a divergência que o
mockup já tinha resolvido — corrigir uma máquina exigiria lembrar de corrigir em dois
lugares. Com recorte, a geometria tem um dono só.

A faixa de cada ativo está no `inventario.json`, gravada pelo script de preparação.
"""
from __future__ import annotations

from dash import dcc, html

from src.utils.monitoring.events import inventario

ID_ART = "mon-asset-art"
ID_CANVAS = "mon-asset-canvas"
ID_FONTE = "mon-asset-src"
ID_ESTADOS = "mon-asset-estados"
ID_PINTADO = "mon-asset-pintado"
ID_RECORTE = "mon-asset-recorte"

PREFIXO_ARTE = "/monitoring/art"


def _croqui_do(ativo: str) -> dict:
    for item in inventario()["ativos"]:
        if item["ativo"] == ativo:
            return item["croqui"]
    raise KeyError(ativo)


def fonte(ativo: str) -> str:
    """Endereço do desenho de onde o croqui é recortado."""
    return f"{PREFIXO_ARTE}/{_croqui_do(ativo)['desenho']}"


def recorte(ativo: str) -> str:
    """O `viewBox` que deixa só este ativo à vista."""
    return " ".join(str(v) for v in _croqui_do(ativo)["view_box"])


def croqui(ativo: str) -> html.Div:
    """O desenho do ativo, pronto para receber as cores do render.

    Sem moldura: ela só faz sentido na planta, onde há vários ativos para comparar.
    """
    return html.Div(
        [
            dcc.Store(id=ID_FONTE, data=fonte(ativo)),
            dcc.Store(id=ID_RECORTE, data=recorte(ativo)),
            dcc.Store(id=ID_ESTADOS, data={"conjuntos": {}, "ativos": {}}),
            dcc.Store(id=ID_PINTADO),
            html.Div(id=ID_CANVAS, className="mon-asset-canvas"),
        ],
        id=ID_ART,
        className="mon-art mon-asset-art",
    )
