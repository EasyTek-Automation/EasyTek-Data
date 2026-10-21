# -*- coding: utf-8 -*-
"""O evento e o vocabulário em volta dele (BR-01, BR-02, BR-04).

Tudo o que a tela mostra vem de uma lista de eventos. Um evento é uma coisa que aconteceu —
ou está acontecendo — com uma máquina específica. Cor, linha do tempo, tabelas e cards são
projeções dessa lista; nada disso fica guardado pronto.

Verde não é evento: verde é o que sobra quando um conjunto não tem nenhum evento no escopo
filtrado.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path

INVENTARIO = (
    Path(__file__).resolve().parents[2]
    / "components" / "monitoring" / "art" / "preparado" / "inventario.json"
)


class Origem(str, Enum):
    """De que área é o assunto do evento."""

    PRODUCAO = "producao"
    MANUTENCAO = "manutencao"


class Gravidade(str, Enum):
    """O quanto o evento atrapalha."""

    DEGRADACAO = "degradacao"
    PARADA = "parada"
    PLANEJADA = "planejada"


class Escopo(str, Enum):
    """As três opções do filtro (BR-04). A entrada é sempre `TUDO`."""

    TUDO = "tudo"
    PRODUCAO = "producao"
    MANUTENCAO = "manutencao"


class Cor(str, Enum):
    """As quatro cores da régua (BR-02), nas variáveis que o desenho já usa."""

    VERDE = "cheio"
    AMARELO = "parcial"
    CINZA = "parado"
    VERMELHO = "vermelho"


# O pior evento manda (BR-02): parada > degradação > planejada > nada.
PRECEDENCIA: tuple[Gravidade, ...] = (
    Gravidade.PARADA,
    Gravidade.DEGRADACAO,
    Gravidade.PLANEJADA,
)

COR_DA_GRAVIDADE: dict[Gravidade, Cor] = {
    Gravidade.PARADA: Cor.VERMELHO,
    Gravidade.DEGRADACAO: Cor.AMARELO,
    Gravidade.PLANEJADA: Cor.CINZA,
}

# Os seis tipos de evento e como cada um se chama na tela (BR-01).
NOME_NA_TELA: dict[tuple[Origem, Gravidade], str] = {
    (Origem.PRODUCAO, Gravidade.DEGRADACAO): "Rodando abaixo do programado",
    (Origem.PRODUCAO, Gravidade.PARADA): "Parada de produção",
    (Origem.PRODUCAO, Gravidade.PLANEJADA): "Sem programação",
    (Origem.MANUTENCAO, Gravidade.DEGRADACAO): "Alerta preditivo",
    (Origem.MANUTENCAO, Gravidade.PARADA): "Avaria",
    (Origem.MANUTENCAO, Gravidade.PLANEJADA): "Preventiva programada",
}


@dataclass(frozen=True)
class Evento:
    """Uma coisa que aconteceu com uma máquina.

    Sem número de ordem, sem responsável, sem código de causa: o protótipo não finge ter
    rastreabilidade até o SAP (BR-01).
    """

    conjunto: str            # chave do conjunto, ex: "LCP01.APLANADORA"
    origem: Origem
    gravidade: Gravidade
    inicio: datetime
    fim: datetime | None     # vazio = ainda em curso
    descricao: str

    @property
    def ativo(self) -> str:
        """A linha a que o conjunto pertence — o que vem antes do ponto na chave."""
        return self.conjunto.split(".", 1)[0]

    @property
    def tipo(self) -> str:
        """Como este evento se chama na tela."""
        return NOME_NA_TELA[(self.origem, self.gravidade)]

    @property
    def em_curso(self) -> bool:
        return self.fim is None

    def duracao(self, agora: datetime) -> float:
        """Duração em horas. Evento em curso conta até agora (SP-08)."""
        fim = self.fim or agora
        return max(0.0, (fim - self.inicio).total_seconds() / 3600.0)

    def vigente_em(self, instante: datetime) -> bool:
        """O evento está valendo neste instante?"""
        if instante < self.inicio:
            return False
        return self.fim is None or instante < self.fim


def pior_gravidade(eventos) -> Gravidade | None:
    """A gravidade que manda na cor, pela precedência da BR-02. `None` = nada."""
    presentes = {e.gravidade for e in eventos}
    for gravidade in PRECEDENCIA:
        if gravidade in presentes:
            return gravidade
    return None


def cor_de(eventos) -> Cor:
    """A cor de um punhado de eventos. Sem evento é verde — verde é ausência (BR-01)."""
    gravidade = pior_gravidade(eventos)
    return COR_DA_GRAVIDADE[gravidade] if gravidade else Cor.VERDE


@lru_cache(maxsize=1)
def inventario() -> dict:
    """O que o desenho preparado contém: ativos, conjuntos e chaves."""
    return json.loads(INVENTARIO.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def conjuntos_por_ativo() -> dict[str, tuple[str, ...]]:
    """Chaves de conjunto de cada ativo, na ordem física em que estão na linha."""
    return {
        ativo["ativo"]: tuple(c["chave"] for c in ativo["conjuntos"])
        for ativo in inventario()["ativos"]
    }


@lru_cache(maxsize=1)
def nome_do_conjunto() -> dict[str, str]:
    """Chave do conjunto -> nome legível, do jeito que está escrito no desenho."""
    return {
        c["chave"]: c["nome"]
        for ativo in inventario()["ativos"]
        for c in ativo["conjuntos"]
    }


def ativos() -> tuple[str, ...]:
    """Os oito ativos, na ordem em que o inventário os lista."""
    return tuple(conjuntos_por_ativo())


def chaves_conhecidas() -> frozenset[str]:
    return frozenset(nome_do_conjunto())
