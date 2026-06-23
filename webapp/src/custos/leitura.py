"""Camada de leitura/agregacao de custo de manutencao (DS-05).

Funcoes puras (sem Dash) que leem as duas coleches do Mongo e entregam, prontos
para a tela, os numeros por nivel: geral -> grupo -> conta -> mes -> dia. Calculam
% consumido, saldo, estouro e a borda "sem orcamento" (BR-05), e a reconciliacao
(DS-09). O filtro por centro de custo recorta **apenas o executado** (vem dos
lancamentos); o orcado permanece o da conta (resumo), sem dimensao de centro.

Dados sao pequenos (dezenas de docs de resumo, milhares de lancamentos), entao a
agregacao por nivel e feita em Python apos um `find()` enxuto — simples e testavel.
Um memo TTL curto evita reconsulta repetida na navegacao (DS-05 #6).
"""
from __future__ import annotations

import logging
import time
from typing import Iterable, Optional

try:  # contexto do webapp (pacote src.custos)
    from src.database.connection import get_mongo_connection
    from src.custos.hierarquia import (EQUIP_OUTROS, GRUPOS, grupo_da_conta, label_grupo,
                                       nome_conta, nome_equipamento)
    from src.custos.storage import COLL_LANCAMENTOS, COLL_RESUMO
except ImportError:  # contexto de teste/script (cwd = webapp/src)
    from database.connection import get_mongo_connection  # type: ignore
    from custos.hierarquia import (EQUIP_OUTROS, GRUPOS, grupo_da_conta,  # type: ignore
                                   label_grupo, nome_conta, nome_equipamento)
    from custos.storage import COLL_LANCAMENTOS, COLL_RESUMO  # type: ignore

logger = logging.getLogger("custos.leitura")

_CACHE_TTL_S = 30.0
_cache: dict[tuple, tuple[float, object]] = {}


# --------------------------------------------------------------------------- #
# Infra: cache TTL e normalizacao de filtros
# --------------------------------------------------------------------------- #
def limpar_cache() -> None:
    """Esvazia o memo TTL. Chamar apos recarga de dados (seed / 'Rodar agora')."""
    _cache.clear()


def _memo(chave: tuple, produtor):
    """Memoiza `produtor()` por `chave` com expiracao TTL."""
    agora = time.monotonic()
    hit = _cache.get(chave)
    if hit is not None and (agora - hit[0]) < _CACHE_TTL_S:
        return hit[1]
    valor = produtor()
    _cache[chave] = (agora, valor)
    return valor


def _norm_centros(centros: Optional[Iterable[str]]) -> Optional[tuple[str, ...]]:
    """Normaliza o filtro de centros: vazio/None -> None (sem filtro); senao tupla ordenada."""
    if not centros:
        return None
    limpos = tuple(sorted({c for c in centros if c}))
    return limpos or None


# --------------------------------------------------------------------------- #
# Metricas (BR-05)
# --------------------------------------------------------------------------- #
def calcular_metricas(orcado: float, executado: float) -> dict:
    """Deriva %, saldo, estouro e 'sem orcamento' de um par (orcado, executado).

    - `pct` = exec/orcado*100; `None` quando orcado = 0 (divisao indefinida).
    - `saldo` = orcado - executado (negativo quando estourou ou nao havia orcamento).
    - `estouro` = pct > 100 (consumo real, nunca capado).
    - `sem_orcamento` = orcado 0 e houve gasto (borda BR-05) -> rotulo proprio na UI.
    """
    orcado = round(orcado, 2)
    executado = round(executado, 2)
    saldo = round(orcado - executado, 2)
    sem_orcamento = orcado == 0 and executado != 0
    pct = round(executado / orcado * 100, 2) if orcado > 0 else None
    estouro = pct is not None and pct > 100
    return {
        "orcado": orcado,
        "executado": executado,
        "saldo": saldo,
        "pct": pct,
        "estouro": estouro,
        "sem_orcamento": sem_orcamento,
    }


# --------------------------------------------------------------------------- #
# Acesso bruto ao Mongo
# --------------------------------------------------------------------------- #
def _filtro_ano(ano: int, mes: Optional[str] = None) -> dict:
    """Match de janela: um mes especifico ('YYYY-MM') ou o ano inteiro (regex '^YYYY-')."""
    if mes:
        return {"mes_referencia": mes}
    return {"mes_referencia": {"$regex": f"^{ano}-"}}


def _resumo_docs(ano: int, mes: Optional[str] = None) -> list[dict]:
    """Docs de `AMG_CustoResumo` da janela (conta x mes: orcado, executado, oficial)."""
    coll = get_mongo_connection(COLL_RESUMO)
    if coll is None:
        return []
    return list(coll.find(_filtro_ano(ano, mes)))


def _exec_por_conta_lancamentos(
    ano: int, centros: Optional[tuple[str, ...]], mes: Optional[str] = None
) -> dict[str, float]:
    """Soma o executado por conta a partir dos lancamentos, filtrando por centro.

    Usado quando ha filtro de centro (o resumo nao tem centro). Retorna {conta: soma}.
    """
    coll = get_mongo_connection(COLL_LANCAMENTOS)
    if coll is None:
        return {}
    match = _filtro_ano(ano, mes)
    if centros:
        match["centro_custo"] = {"$in": list(centros)}
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$conta", "soma": {"$sum": "$valor"}}},
    ]
    return {d["_id"]: round(d["soma"], 2) for d in coll.aggregate(pipeline)}


# --------------------------------------------------------------------------- #
# Niveis de leitura
# --------------------------------------------------------------------------- #
def _orcado_executado_por_conta(
    ano: int, centros: Optional[tuple[str, ...]], mes: Optional[str] = None
) -> dict[str, dict]:
    """Base de todos os niveis: por conta, o orcado (resumo) e o executado (resumo ou centro).

    Sem filtro de centro -> executado vem do resumo (rapido, ja reconciliado).
    Com filtro -> executado recomputado dos lancamentos do(s) centro(s); orcado intacto.
    """
    docs = _resumo_docs(ano, mes)
    por_conta: dict[str, dict] = {}
    for d in docs:
        c = d["conta"]
        acc = por_conta.setdefault(
            c, {"conta": c, "conta_desc": d.get("conta_desc", ""), "orcado": 0.0, "executado": 0.0}
        )
        acc["orcado"] += d.get("orcado", 0.0)
        acc["executado"] += d.get("executado", 0.0)

    if centros:
        exec_centro = _exec_por_conta_lancamentos(ano, centros, mes)
        for c, acc in por_conta.items():
            acc["executado"] = exec_centro.get(c, 0.0)
        # contas que so tem lancamento no centro (sem linha de resumo) — raro, mas cobre
        for c, soma in exec_centro.items():
            if c not in por_conta:
                por_conta[c] = {"conta": c, "conta_desc": "", "orcado": 0.0, "executado": soma}
    return por_conta


def fetch_geral(ano: int, centros: Optional[Iterable[str]] = None) -> dict:
    """Metricas do GT340 inteiro (raiz do drill-down) para o ano."""
    cz = _norm_centros(centros)

    def _calc():
        por_conta = _orcado_executado_por_conta(ano, cz)
        orcado = sum(a["orcado"] for a in por_conta.values())
        executado = sum(a["executado"] for a in por_conta.values())
        return calcular_metricas(orcado, executado)

    return _memo(("geral", ano, cz), _calc)


def fetch_grupos(ano: int, centros: Optional[Iterable[str]] = None) -> list[dict]:
    """Lista dos grupos (G034x) com metricas. Ordem canonica do mapa; % = Sexec/Sorcado."""
    cz = _norm_centros(centros)

    def _calc():
        por_conta = _orcado_executado_por_conta(ano, cz)
        acc: dict[str, dict] = {}
        for a in por_conta.values():
            g = grupo_da_conta(a["conta"])
            if g is None:
                continue
            box = acc.setdefault(g, {"orcado": 0.0, "executado": 0.0})
            box["orcado"] += a["orcado"]
            box["executado"] += a["executado"]
        linhas = []
        for g in GRUPOS:  # ordem canonica G0341..G0344
            if g not in acc:
                continue
            m = calcular_metricas(acc[g]["orcado"], acc[g]["executado"])
            linhas.append({"grupo": g, "label": label_grupo(g), **m})
        return linhas

    return _memo(("grupos", ano, cz), _calc)


def fetch_contas(grupo: str, ano: int, centros: Optional[Iterable[str]] = None) -> list[dict]:
    """Contas de um grupo com metricas (lista vem do orcado — BR-04). Ordena por executado desc."""
    cz = _norm_centros(centros)

    def _calc():
        por_conta = _orcado_executado_por_conta(ano, cz)
        linhas = []
        for a in por_conta.values():
            if grupo_da_conta(a["conta"]) != grupo:
                continue
            m = calcular_metricas(a["orcado"], a["executado"])
            linhas.append({"conta": a["conta"], "conta_desc": a["conta_desc"], **m})
        linhas.sort(key=lambda x: x["executado"], reverse=True)
        return linhas

    return _memo(("contas", grupo, ano, cz), _calc)


def fetch_meses_da_conta(conta: str, ano: int, centros: Optional[Iterable[str]] = None) -> list[dict]:
    """Serie mensal de uma conta (orcado x executado por mes). Ordenada por mes."""
    cz = _norm_centros(centros)

    def _calc():
        docs = [d for d in _resumo_docs(ano) if d["conta"] == conta]
        exec_centro_mes: dict[str, float] = {}
        if cz:
            coll = get_mongo_connection(COLL_LANCAMENTOS)
            if coll is not None:
                match = {"conta": conta, "centro_custo": {"$in": list(cz)},
                         "mes_referencia": {"$regex": f"^{ano}-"}}
                pipe = [{"$match": match},
                        {"$group": {"_id": "$mes_referencia", "soma": {"$sum": "$valor"}}}]
                exec_centro_mes = {d["_id"]: round(d["soma"], 2) for d in coll.aggregate(pipe)}
        linhas = []
        for d in docs:
            mes = d["mes_referencia"]
            executado = exec_centro_mes.get(mes, 0.0) if cz else d.get("executado", 0.0)
            m = calcular_metricas(d.get("orcado", 0.0), executado)
            linhas.append({"mes": mes, **m})
        linhas.sort(key=lambda x: x["mes"])
        return linhas

    return _memo(("meses", conta, ano, cz), _calc)


def fetch_dias_da_conta_mes(
    conta: str, mes: str, centros: Optional[Iterable[str]] = None
) -> list[dict]:
    """Executado diario de uma conta num mes (orcado e mensal, nao existe por dia)."""
    cz = _norm_centros(centros)

    def _calc():
        coll = get_mongo_connection(COLL_LANCAMENTOS)
        if coll is None:
            return []
        match = {"conta": conta, "mes_referencia": mes}
        if cz:
            match["centro_custo"] = {"$in": list(cz)}
        pipe = [
            {"$match": match},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$data_lancamento"}},
                        "executado": {"$sum": "$valor"}}},
            {"$sort": {"_id": 1}},
        ]
        return [{"dia": d["_id"], "executado": round(d["executado"], 2)} for d in coll.aggregate(pipe)]

    return _memo(("dias", conta, mes, cz), _calc)


def fetch_centros_disponiveis(ano: int) -> list[str]:
    """Lista (ordenada) dos centros de custo presentes nos lancamentos do ano — filtro lateral."""
    def _calc():
        coll = get_mongo_connection(COLL_LANCAMENTOS)
        if coll is None:
            return []
        centros = coll.distinct("centro_custo", {"mes_referencia": {"$regex": f"^{ano}-"}})
        return sorted(c for c in centros if c)

    return _memo(("centros", ano), _calc)


def fetch_por_equipamento(ano: int, centros: Optional[Iterable[str]] = None,
                          top: int = 10) -> list[dict]:
    """Executado do ano por EQUIPAMENTO (centro de custo) — gráfico de rosca.

    Soma o executado de cada `centro_custo`, nomeia pelo de/para (`nome_equipamento`,
    fallback = código) e mostra os `top` maiores como fatias; a cauda vai p/ 'Outros'.
    Centros já mapeados ao MESMO nome no de/para somam juntos (ex: várias linhas de uma
    família). Retorna `[{equip, executado, centros}]` ordenado desc, com 'Outros' por último.
    """
    cz = _norm_centros(centros)

    def _calc():
        coll = get_mongo_connection(COLL_LANCAMENTOS)
        if coll is None:
            return []
        match: dict = {"mes_referencia": {"$regex": f"^{ano}-"}}
        if cz:
            match["centro_custo"] = {"$in": list(cz)}
        pipe = [{"$match": match},
                {"$group": {"_id": "$centro_custo", "executado": {"$sum": "$valor"}}}]
        # agrega por nome de equipamento (de/para); guarda os centros que compõem cada um
        acc: dict[str, float] = {}
        membros: dict[str, list] = {}
        for d in coll.aggregate(pipe):
            nome = nome_equipamento(d["_id"])
            acc[nome] = acc.get(nome, 0.0) + (d["executado"] or 0.0)
            membros.setdefault(nome, []).append(d["_id"])
        ordenado = sorted(acc.items(), key=lambda kv: kv[1], reverse=True)
        principais = ordenado[:top]
        cauda = ordenado[top:]
        out = [{"equip": nome, "executado": round(v, 2), "centros": membros[nome]}
               for nome, v in principais]
        if cauda:
            out.append({"equip": EQUIP_OUTROS, "executado": round(sum(v for _, v in cauda), 2),
                        "centros": [c for nome, _ in cauda for c in membros[nome]]})
        # Reconcilia com o GERAL das barras (resumo ZBRCO019): os lançamentos (KSB1) podem
        # somar menos que o executado oficial — no mês corrente, provisões/itens pós-D-1 não
        # têm centro, logo não entram por equipamento. O resto vira "Não atribuído".
        rcoll = get_mongo_connection(COLL_RESUMO)
        if rcoll is not None:
            rmatch = {"mes_referencia": {"$regex": f"^{ano}-"}}
            g = list(rcoll.aggregate([{"$match": rmatch},
                                      {"$group": {"_id": None, "v": {"$sum": "$executado"}}}]))
            total_oficial = g[0]["v"] if g else 0
            gap = round(total_oficial - sum(acc.values()), 2)
            if gap > 1:
                out.append({"equip": "Não atribuído", "executado": gap, "centros": []})
        return out

    return _memo(("equip", ano, cz, top), _calc)


def fetch_lancamentos(
    ano: int,
    conta: Optional[str] = None,
    mes: Optional[str] = None,
    centros: Optional[Iterable[str]] = None,
    limit: int = 500,
) -> list[dict]:
    """Lancamentos do recorte acumulado (conta/mes/centro) para a tabela (DS-08).

    Ordena por data. `limit` evita despejar milhares de linhas no nivel planta/grupo.
    """
    coll = get_mongo_connection(COLL_LANCAMENTOS)
    if coll is None:
        return []
    cz = _norm_centros(centros)
    match: dict = {"mes_referencia": mes} if mes else {"mes_referencia": {"$regex": f"^{ano}-"}}
    if conta:
        match["conta"] = conta
    if cz:
        match["centro_custo"] = {"$in": list(cz)}
    cursor = coll.find(match).sort([("data_lancamento", 1)]).limit(limit)
    return list(cursor)


def fetch_contas_geral(ano: int, mes: Optional[str] = None,
                       centros: Optional[Iterable[str]] = None) -> list[dict]:
    """GERAL + todas as contas (orçado × executado) da janela — eixo do gráfico.

    Primeira linha = GERAL (rollup GT340); depois cada conta, ordenada por ORÇADO
    desc (desempate executado). `mes=None` → ano inteiro. Cada item tem o contrato do gráfico
    (label/code/orcado/executado/pct/estouro/sem_orcamento).
    """
    cz = _norm_centros(centros)

    def _calc():
        por_conta = _orcado_executado_por_conta(ano, cz, mes)
        tot_o = sum(a["orcado"] for a in por_conta.values())
        tot_e = sum(a["executado"] for a in por_conta.values())
        geral = {"code": "__GERAL__", "label": "GERAL", "conta_desc": "Manutenção (GT340)",
                 **calcular_metricas(tot_o, tot_e)}
        contas = []
        for a in por_conta.values():
            contas.append({"code": a["conta"], "label": nome_conta(a["conta"]),
                           "conta_desc": a.get("conta_desc", ""),
                           **calcular_metricas(a["orcado"], a["executado"])})
        # ordem das barras (esq→dir) por ORÇADO desc; desempate por executado
        contas.sort(key=lambda x: (x["orcado"], x["executado"]), reverse=True)
        return [geral] + contas

    return _memo(("contas_geral", ano, mes, cz), _calc)


def meses_com_dados(ano: int) -> list[str]:
    """Meses 'YYYY-MM' com dados de resumo no ano (ordenados)."""
    coll = get_mongo_connection(COLL_RESUMO)
    if coll is None:
        return []
    return sorted(coll.distinct("mes_referencia", {"mes_referencia": {"$regex": f"^{ano}-"}}))


def fetch_dias_total_mes(ano: int, mes: str,
                         centros: Optional[Iterable[str]] = None) -> list[dict]:
    """Executado total por dia no mês (todas as contas somadas) — cards/gráfico de dia."""
    cz = _norm_centros(centros)

    def _calc():
        coll = get_mongo_connection(COLL_LANCAMENTOS)
        if coll is None:
            return []
        match: dict = {"mes_referencia": mes}
        if cz:
            match["centro_custo"] = {"$in": list(cz)}
        pipe = [
            {"$match": match},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$data_lancamento"}},
                        "executado": {"$sum": "$valor"}}},
            {"$sort": {"_id": 1}},
        ]
        return [{"code": d["_id"], "label": d["_id"][-2:], "dia": d["_id"],
                 "orcado": 0, "executado": round(d["executado"], 2),
                 "pct": None, "estouro": False, "sem_orcamento": False}
                for d in coll.aggregate(pipe)]

    return _memo(("dias_total", ano, mes, cz), _calc)


def fetch_contas_no_dia(ano: int, dia: str,
                        centros: Optional[Iterable[str]] = None) -> list[dict]:
    """GERAL + contas com executado num dia específico ('YYYY-MM-DD'). Só executado."""
    cz = _norm_centros(centros)

    def _calc():
        coll = get_mongo_connection(COLL_LANCAMENTOS)
        if coll is None:
            return []
        match: dict = {"mes_referencia": dia[:7]}
        if cz:
            match["centro_custo"] = {"$in": list(cz)}
        pipe = [
            {"$match": match},
            {"$addFields": {"_d": {"$dateToString": {"format": "%Y-%m-%d", "date": "$data_lancamento"}}}},
            {"$match": {"_d": dia}},
            {"$group": {"_id": "$conta", "executado": {"$sum": "$valor"}}},
        ]
        contas = [{"code": d["_id"], "label": nome_conta(d["_id"]), "orcado": 0,
                   "executado": round(d["executado"], 2), "pct": None,
                   "estouro": False, "sem_orcamento": False}
                  for d in coll.aggregate(pipe)]
        contas.sort(key=lambda x: x["executado"], reverse=True)
        tot = round(sum(c["executado"] for c in contas), 2)
        geral = {"code": "__GERAL__", "label": "GERAL", "orcado": 0, "executado": tot,
                 "pct": None, "estouro": False, "sem_orcamento": False}
        return [geral] + contas

    return _memo(("contas_dia", ano, dia, cz), _calc)


def fetch_lancamentos_no_dia(ano: int, dia: str, conta: Optional[str] = None,
                             centros: Optional[Iterable[str]] = None,
                             limit: int = 500) -> list[dict]:
    """Lançamentos de um dia ('YYYY-MM-DD'), opcionalmente de uma conta."""
    docs = fetch_lancamentos(ano, conta=conta, mes=dia[:7], centros=centros, limit=limit)
    return [d for d in docs if d.get("data_lancamento")
            and d["data_lancamento"].strftime("%Y-%m-%d") == dia]


def fonte_dos_dados(ano: int) -> Optional[str]:
    """Retorna a origem predominante dos dados do ano ('csv'|'sap') ou None se vazio."""
    coll = get_mongo_connection(COLL_RESUMO)
    if coll is None:
        return None
    doc = coll.find_one({"mes_referencia": {"$regex": f"^{ano}-"}}, {"fonte": 1})
    return doc.get("fonte") if doc else None


def reconciliacao(ano: int, mes: Optional[str] = None) -> dict:
    """Confere a soma do executado das contas x total oficial do mes (DS-09).

    Reconciliacao usa o resumo (sempre o numero oficial), independente de filtro de
    centro. Retorna {bate, soma_exec, oficial, diff, por_mes}. `bate` = diferenca < 1 centavo.
    """
    def _calc():
        docs = _resumo_docs(ano, mes)
        por_mes: dict[str, dict] = {}
        for d in docs:
            box = por_mes.setdefault(d["mes_referencia"], {"soma_exec": 0.0, "oficial": 0.0})
            box["soma_exec"] += d.get("executado", 0.0)
            box["oficial"] = d.get("total_oficial_geral", 0.0)  # igual em todos os docs do mes
        soma_exec = round(sum(b["soma_exec"] for b in por_mes.values()), 2)
        oficial = round(sum(b["oficial"] for b in por_mes.values()), 2)
        detalhe = {
            m: {"soma_exec": round(b["soma_exec"], 2), "oficial": round(b["oficial"], 2),
                "bate": abs(round(b["soma_exec"], 2) - round(b["oficial"], 2)) < 0.005}
            for m, b in sorted(por_mes.items())
        }
        return {
            "bate": abs(soma_exec - oficial) < 0.005,
            "soma_exec": soma_exec,
            "oficial": oficial,
            "diff": round(soma_exec - oficial, 2),
            "por_mes": detalhe,
        }

    return _memo(("reconc", ano, mes), _calc)
