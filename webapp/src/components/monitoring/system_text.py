# -*- coding: utf-8 -*-
"""A marcação de projeto realçada dentro do texto do evento.

As descrições citam o componente pela marcação de projeto — motor `M09`, drive `U31`, sensor
`B12`, emergência `S14`, código de falha `F0001` (BR-07). Escritas no meio da frase, essas
marcações se perdem: são justamente o que o técnico procura primeiro, e o olho passa por elas
como se fossem palavra comum.

Aqui elas saem do texto corrido e ganham forma de leitura de sistema — monoespaçado, fundo
discreto —, do mesmo jeito que um supervisório apresenta um endereço de equipamento. O texto
em si não muda: só a forma de exibir.
"""
from __future__ import annotations

import re

from dash import html

# Uma ou duas letras seguidas de dois a quatro dígitos (M09, U31, B12, F0001), com a variante
# de painel separada por hífen (QP-08). O limite de palavra nas duas pontas evita capturar
# pedaço de número solto ou de unidade — "24 Vcc" e "ISO 20/18/15" ficam de fora.
MARCACAO = re.compile(r"\b([A-Z]{1,3}-?\d{2,4})\b")


def com_marcacoes(texto: str) -> list:
    """O texto quebrado em pedaços, com cada marcação de projeto dentro de um `<code>`.

    Devolve lista para ir direto como `children` de um componente do Dash. Texto sem marcação
    nenhuma volta como lista de um item só — nada muda para quem não cita componente.
    """
    partes: list = []
    posicao = 0
    for achado in MARCACAO.finditer(texto):
        if achado.start() > posicao:
            partes.append(texto[posicao:achado.start()])
        partes.append(html.Code(achado.group(1), className="mon-tag"))
        posicao = achado.end()
    if posicao < len(texto):
        partes.append(texto[posicao:])
    return partes or [texto]
