# -*- coding: utf-8 -*-
"""Carrega e guarda em memória os desenhos preparados (DS-02).

O desenho é lido do disco uma vez e fica em cache: é o mesmo arquivo em toda visita, e
reler a cada render custaria ~140 KB de disco por página aberta.

O texto é entregue **numa linha só**. A página injeta o SVG com
`dcc.Markdown(dangerously_allow_html=True)` — o mesmo caminho que `components/icons.py` já
usa — e o Markdown trata linha indentada com quatro espaços como bloco de código. Um SVG
indentado chegaria à tela como texto-fonte em vez de desenho.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

PREPARADO = Path(__file__).resolve().parent / "art" / "preparado"

PLANTA = "planta.svg"
DESENHO_DO_ATIVO = {
    "LCP01": "linha_prensa.svg",
    "LCP02": "linha_prensa.svg",
    "LCT2,5": "linha_prensa.svg",
    "LCT16": "linhas_corte.svg",
    "LCT08": "linhas_corte.svg",
    "LCL4,5": "linhas_corte.svg",
    "LCL08": "linhas_corte.svg",
    "LWB": "linha_lwb.svg",
}

_ENTRE_TAGS = re.compile(r">\s+<")


@lru_cache(maxsize=8)
def desenho(arquivo: str) -> str:
    """O SVG preparado, pronto para ser injetado inline."""
    caminho = PREPARADO / arquivo
    if not caminho.is_file():
        raise FileNotFoundError(
            f"desenho preparado ausente: {caminho}. Rode "
            f"`python webapp/scripts/prepare_monitoring_art.py`."
        )
    return _ENTRE_TAGS.sub("><", caminho.read_text(encoding="utf-8").strip())


def planta() -> str:
    """O desenho da fábrica inteira, com os oito ativos."""
    return desenho(PLANTA)


def desenho_do_ativo(ativo: str) -> str:
    """O desenho do grupo de linhas a que o ativo pertence."""
    return desenho(DESENHO_DO_ATIVO[ativo])
