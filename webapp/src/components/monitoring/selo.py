# -*- coding: utf-8 -*-
"""O selo de demonstração das duas telas (SP-10).

A tela parece supervisório de verdade — planta da fábrica, cor de estado, linha piscando. É
justamente por parecer que o selo precisa estar **na mesma tela**, ao lado do título, e não
escondido no rodapé: quem passar pela sala e bater o olho não pode achar que é sistema em
produção.

O componente compartilhado (`components/demo_badge.py`) nasce amarelo, e amarelo aqui é
**cor de estado** — significa "rodando abaixo do programado". A variante neutra é aplicada
por CSS só nesta página, via classe própria; o componente segue servindo o resto do webapp
sem mudança nenhuma.
"""
from __future__ import annotations

from src.components.demo_badge import demo_data_badge
from src.config.demo_data_config import should_show_demo_badge


def selo_de_demonstracao(rota: str):
    """O selo da tela, ou nada quando os selos estão desligados na configuração."""
    if not should_show_demo_badge(page_path=rota):
        return None
    return demo_data_badge(size="md", className="mon-selo")
