"""Mapa canonico da hierarquia de contas de manutencao (DS-04 / BR-01, BR-02).

Em linguagem simples: a manutencao tem um "bolo" unico (o grupo geral **GT340**),
dividido em **4 grupos** (Maquinas, Utilidades, Edificios, Outras), e cada grupo
reune **classes de custo** (as "contas" — cada uma e um tipo de gasto). Esta tabela
diz a qual grupo cada conta pertence. E a *fonte unica da verdade* da lista de
contas: qualquer conta fora dela nao entra (BR-01 — inclui a fantasma `33102104`,
que nao pertence ao GT340 e e descartada).

Detalhe tecnico: a conta e a classe de custo do SAP (`KSTAR`/`classe_custo`); o
grupo e o subgrupo da hierarquia GT340 do relatorio ZBRCO019. Grupo e geral sao
sempre *derivados por soma* das contas (BR-02), nunca lidos prontos.
"""
from __future__ import annotations

# Grupo geral (raiz da hierarquia de manutencao).
GRUPO_GERAL = "GT340"
GRUPO_GERAL_LABEL = "Manutenção (GT340)"

# Rotulos dos 4 grupos (subgrupos GT340), na grafia do relatorio do gestor.
GRUPOS: dict[str, str] = {
    "G0341": "Manutenção de Máquinas",
    "G0342": "Manutenção de Utilidades",
    "G0343": "Manutenção de Edifícios",
    "G0344": "Outras Manutenções",
}

# Mapa conta -> grupo (15 contas canonicas do GT340; sem a fantasma 33102104).
# Nota: 33102264, 33102105 e 33102103 estao zeradas no periodo 2026 (sem orcado
# nem executado nos CSVs) — permanecem no mapa por serem contas legitimas do GT340
# (BR-01/BR-04); a decisao de renderiza-las quando totalmente zeradas e da camada
# de leitura (Bloco B).
CONTA_PARA_GRUPO: dict[str, str] = {
    # G0341 — Manutenção de Máquinas
    "33102101": "G0341",
    "33102260": "G0341",
    "33102264": "G0341",
    "33102211": "G0341",
    "33102130": "G0341",
    # G0342 — Manutenção de Utilidades
    "33102265": "G0342",
    "33102382": "G0342",
    # G0343 — Manutenção de Edifícios
    "33102102": "G0343",
    "33102105": "G0343",
    "33102100": "G0343",
    # G0344 — Outras Manutenções
    "33102106": "G0344",
    "33102261": "G0344",
    "33102263": "G0344",
    "33102103": "G0344",
    "33102400": "G0344",
}

# Conjunto imutavel das contas validas — uso rapido em validacao/filtro.
CONTAS: frozenset[str] = frozenset(CONTA_PARA_GRUPO)

# Aliases historicos de grafia (doc antiga usou letra O: GO343/GO344). Canonico = G034x.
_ALIAS_GRUPO: dict[str, str] = {"GO343": "G0343", "GO344": "G0344"}

# Nome legivel de cada conta (expansao das descricoes truncadas do SAP, 16 chars).
# Permite mostrar nome em vez do codigo cru na tela — sem depender do SAP no cliente.
# As 3 contas zeradas no periodo (sem dado/descricao real) ficam com nome generico.
CONTA_NOME: dict[str, str] = {
    "33102100": "Conserto / Manutenção",
    "33102101": "Consumo de Material de Manutenção",
    "33102102": "Manutenção de Edifícios",
    "33102103": "Manutenção (conta 33102103)",
    "33102105": "Manutenção (conta 33102105)",
    "33102106": "Manutenção de Móveis / Utensílios",
    "33102130": "Manutenção de Veículos",
    "33102211": "Óleo Lubrificante de Manutenção",
    "33102260": "Manutenção de Máquinas e Equipamentos",
    "33102261": "Manutenção de Informática",
    "33102263": "Manutenção de Empilhadeiras",
    "33102264": "Manutenção (conta 33102264)",
    "33102265": "Manutenção de Matrizes",
    "33102382": "Utilidades / Ferramentas de Produção",
    "33102400": "Despesas com Aferição",
}


def nome_conta(conta: str) -> str:
    """Nome legivel da conta; ecoa o codigo se desconhecida."""
    return CONTA_NOME.get(conta, conta)


def normalizar_grupo(grupo: str) -> str:
    """Normaliza a grafia de um grupo para a forma canonica `G034x`.

    Aceita os aliases historicos `GO343`/`GO344` (com letra O) e os converte.
    """
    return _ALIAS_GRUPO.get(grupo, grupo)


def conta_valida(conta: str) -> bool:
    """True se a conta pertence ao GT340 (esta no mapa canonico). BR-01."""
    return conta in CONTA_PARA_GRUPO


def grupo_da_conta(conta: str) -> str | None:
    """Retorna o grupo (`G034x`) da conta, ou `None` se a conta nao for canonica."""
    return CONTA_PARA_GRUPO.get(conta)


def contas_do_grupo(grupo: str) -> list[str]:
    """Lista (ordenada) das contas de um grupo. Aceita alias de grafia; [] se invalido."""
    g = normalizar_grupo(grupo)
    return sorted(c for c, gr in CONTA_PARA_GRUPO.items() if gr == g)


def label_grupo(grupo: str) -> str:
    """Rotulo legivel do grupo; ecoa o codigo se desconhecido."""
    return GRUPOS.get(normalizar_grupo(grupo), grupo)
