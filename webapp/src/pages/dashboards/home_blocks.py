# src/pages/dashboards/home_blocks.py
#
# Registry declarativo de blocos da home por perfil + nível (DS-14 / BR-16).
#
# Cada home por perfil (manutenção, produção, ...) monta seu conteúdo a partir de uma
# lista de HomeBlock. `blocos_visiveis` filtra pela combinação de nível vertical
# (1=básico, 2=avançado, 3=admin) E perfil horizontal do usuário logado — mesma
# semântica de utils/permissions.py, centralizada aqui para não espalhar checagem de
# permissão pelas páginas (CLAUDE.md: nunca hardcodar permissão na página).

from dataclasses import dataclass
from typing import Callable, List


@dataclass
class HomeBlock:
    """Bloco/atalho de uma home. Visível só se o usuário atende perfil E min_level.

    render_fn recebe o idioma (lang) e devolve um componente Dash.
    """
    id: str
    render_fn: Callable
    perfis: List[str]
    min_level: int = 1


def blocos_visiveis(blocos, user):
    """Filtra blocos pelo nível E perfil do usuário (gating de BR-16).

    Bloco oculto = ausente da lista retornada — logo, ausente do DOM, não escondido por
    CSS (não vaza informação nem botão clicável).
    """
    level = getattr(user, "level", 0) or 0
    perfil = getattr(user, "perfil", None)
    return [b for b in blocos if level >= b.min_level and perfil in b.perfis]


def render_blocos(blocos, user, lang="pt"):
    """Renderiza, em ordem, os blocos visíveis ao usuário."""
    return [b.render_fn(lang) for b in blocos_visiveis(blocos, user)]
