# -*- coding: utf-8 -*-
"""A cor que o servidor decide e o navegador aplica (DS-06, adaptado).

O SVG preparado é geometria pura, sem cor de estado. A cada render o servidor entrega um
mapa — *que conjunto está de que cor, que ativo recebe marcação* — e o navegador escreve
esse estado no desenho, como atributo. A folha de estilo fixa (`assets/monitoring.css`) faz
o resto.

Por que atributo e não um bloco `<style>` gerado, como o design previa: o desenho não pode
ser injetado no layout do Dash como HTML (o renderizador de Markdown desmonta as tags do
SVG), então ele é carregado como arquivo pelo próprio navegador. Uma folha de estilo gerada
no servidor não alcançaria esse conteúdo sem voltar a injetar HTML; o atributo alcança, e é
o mesmo mecanismo que o mockup de origem já usava.

A convenção do desenho continua respeitada: **só o `.body` do conjunto recebe cor de
estado**, e a moldura do ativo é um elemento à parte, que nunca pinta máquina nenhuma.
"""
from __future__ import annotations

from src.utils.monitoring.events import Cor, nome_do_conjunto


def mapa_de_estados(
    cor_dos_conjuntos: dict[str, Cor],
    cor_dos_ativos: dict[str, Cor | None] | None = None,
) -> dict[str, dict[str, str]]:
    """O que pintar neste render.

    **Todo conjunto do inventário sai daqui com uma cor** — inclusive o verde. Verde é um
    estado afirmado ("rodando 100%"), não a ausência de instrução: a cor de repouso do
    desenho é a carcaça branca do mockup, então omitir o conjunto verde deixaria a máquina
    branca e a régua de cor da BR-02 sem o seu primeiro degrau.

    Ativo com valor `None` (verde) continua de fora: moldura em todo ativo deixa de informar
    (BR-03). Vermelho, amarelo e cinza recebem moldura; o cinza se distingue pela forma
    tracejada, não pela ausência.
    """
    conjuntos = {chave: Cor.VERDE.value for chave in nome_do_conjunto()}
    conjuntos.update({chave: cor.value for chave, cor in cor_dos_conjuntos.items()})
    return {
        "conjuntos": conjuntos,
        "ativos": {
            ativo: cor.value
            for ativo, cor in (cor_dos_ativos or {}).items()
            if cor is not None
        },
    }
