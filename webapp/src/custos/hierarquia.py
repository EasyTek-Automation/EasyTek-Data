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
    "33102103": "Manutenção de Transporte",
    "33102105": "Manutenção de Imóveis",
    "33102106": "Manutenção de Móveis / Utensílios",
    "33102130": "Manutenção de Veículos",
    "33102211": "Óleo Lubrificante de Manutenção",
    "33102260": "Manutenção de Máquinas e Equipamentos",
    "33102261": "Manutenção de Informática",
    "33102263": "Manutenção de Empilhadeiras",
    "33102264": "Grandes Manutenções",
    "33102265": "Manutenção de Matrizes",
    "33102382": "Utilidades / Ferramentas de Produção",
    "33102400": "Despesas com Aferição",
}


# Nome legivel de cada centro de custo (grafia do SAP — KOSTL -> texto da KSB1).
# Em linguagem simples: traduz o codigo do centro (ex: "208401") para o nome que o
# gestor reconhece (ex: "PRENSA FAGOR"), para exibir no filtro/tooltip/resumo — o dado
# gravado no Mongo continua sendo o codigo. Mapa estatico (igual a CONTA_NOME): nao
# depende do SAP no cliente. Centros sem nome conhecido aparecem so com o codigo.
# IMPORTANTE: os centros do SAP desta planta usam prefixo "2" (2xxxxx) — mesmo prefixo
# da ponte CENTRO_ARBPL. (Versao anterior usava "1xxxxx" por engano, e por isso nenhum
# nome casava com os lancamentos reais.)
CENTRO_NOME: dict[str, str] = {
    "202001": "LINHA LASER",
    "202004": "LINHA LASER II",
    "205001": "LINHA LONGIDUDINAL-Q",
    "205002": "LINHA LONGIDUDINAL-F",
    "206001": "LINHA TRANSVERSAL-F",
    "206002": "LINHA TRANSVERS.-QTE",
    "208401": "PRENSA FAGOR",
    "208402": "PRENSA SCHULLER 500",
    "208403": "PRENSA SCHULLER 630",
    "209000": "GERENTE INDUSTRIAL",
    "209002": "SERVIÇOS GERAIS -ADM",
    "209008": "ESTRUT CNTL COML PR",
    "209012": "EST CENTRAL SUP PR",
    "209100": "MANUTENÇÃO DA PLANTA",
    "209710": "ARMAZENS E TRANSLADO",
    "209800": "QUALIDADE PROD PR",
    "209900": "SERVIÇOS GERAIS-PROD",
    "209902": "ADMIN. PRODUÇÃO - PR",
    "209903": "FERRAMENTARIA",
}


def nome_conta(conta: str) -> str:
    """Nome legivel da conta; ecoa o codigo se desconhecida."""
    return CONTA_NOME.get(conta, conta)


def nome_centro(centro: str) -> str:
    """Nome legivel do centro de custo; ecoa o codigo se desconhecido."""
    return CENTRO_NOME.get(centro, centro)


# Ponte centro de custo (KOSTL) → posto de trabalho (ARBPL) das LINHAS de produção. O nome
# de exibição NÃO mora aqui — vem da FONTE ÚNICA `EQUIPAMENTO_NOMES` (KPIs), reusada via essa
# ponte. Identidade tirada do descritor das ordens de manutenção (ex: 206001 = "LCT8" = TRANS001).
# Centros fora desta ponte (apoio/admin: 209xxx, 201xxx, 203xxx, 207xxx) caem em "Apoio/Admin".
CENTRO_ARBPL: dict[str, str] = {
    "206001": "TRANS001",   # LCT-08
    "206002": "TRANS002",   # LCT-16
    "206003": "TRANS003",   # LCT-2,5
    "205001": "LONGI001",   # LCL-08
    "205002": "LONGI002",   # LCL-4,5
    "208401": "PRENS001",   # PRENSA-01
    "208402": "PRENS002",   # PRENSA-02
}

EQUIP_OUTROS = "Outros"          # cauda de fatias pequenas (não usado quando há ponte completa)
EQUIP_APOIO = "Apoio/Admin"      # centros sem linha (predial, ferramentaria, serviços, TI…)


def nome_equipamento(centro: str) -> str:
    """Nome do equipamento de um centro de custo: ponte KOSTL→ARBPL → `EQUIPAMENTO_NOMES`
    (fonte única dos KPIs). Centro sem linha mapeada → 'Apoio/Admin'."""
    arbpl = CENTRO_ARBPL.get(centro)
    if not arbpl:
        return EQUIP_APOIO
    try:
        from src.utils.zpp_kpi_calculator import EQUIPAMENTO_NOMES
    except ImportError:  # pragma: no cover
        from utils.zpp_kpi_calculator import EQUIPAMENTO_NOMES  # type: ignore
    return EQUIPAMENTO_NOMES.get(arbpl, arbpl)


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
