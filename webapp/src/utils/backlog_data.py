# -*- coding: utf-8 -*-
"""Camada de dados da página Backlog de Manutenção (SDD Backlog, DS-07 / SP-04..07).

Lê o snapshot atual da collection `sap_backlog` (alimentada pelo job `backlog` do
sap-scheduler), aplica o recorte de exibição ("preventiva só vencida") e os filtros, e
agrega as contagens dos cards. A página lê SÓ do Mongo — nunca consulta o SAP (RNF-01).
"""
from __future__ import annotations

from datetime import datetime

import pytz

try:
    from src.database.connection import get_mongo_connection
except ImportError:  # execução fora do pacote src
    from database.connection import get_mongo_connection

COLL = "sap_backlog"
META_ID = "meta"
_BRT = pytz.timezone("America/Sao_Paulo")

CATEGORIAS = ["Preventiva", "Corretiva", "Melhoria", "Matrizes"]
CATEGORIAS_COM_DISCIPLINA = ("Preventiva", "Corretiva")
# B34 (2026-07-17): Terceiros (Z03) e Gestão (Z01) ganham fatia própria — antes caíam em
# NaoClassificado e inflavam a pendência. Ordem = ordem de exibição da rosca.
DISCIPLINAS = ["Mecanica", "Eletrica", "Terceiros", "Gestao", "Ferramentaria", "NaoClassificado"]
LABEL_DISCIPLINA = {"Mecanica": "Mecânica", "Eletrica": "Elétrica",
                    "Terceiros": "Serviço de terceiros", "Gestao": "Gestão",
                    "Ferramentaria": "Ferramentaria",  # B37: Z04 (matrizes) — classificada, fora do quadro
                    "NaoClassificado": "Não classificado"}
SUBCLASSIFICACOES = ["Corretiva", "PDCA", "CorretivaProgramada", "Preditiva"]

# Status do usuário (USTXT) que tira a ordem do trabalho pendente: encerrada / cancelada (B35).
_STATUS_MORTOS = frozenset({"CERR", "CANC"})


def esta_encerrada(o: dict) -> bool:
    """True se a ordem está Encerrada (CERR) ou Cancelada (CANC) pelo status do usuário (B35).

    Combos como 'CERR PRIO' contam pela 1ª palavra. Ordem sem status → não encerrada.
    """
    su = (o.get("status_usuario") or "").strip().upper()
    return bool(su) and su.split()[0] in _STATUS_MORTOS


def esconder_encerradas(ordens: list) -> list:
    """Remove as ordens Encerradas/Canceladas de uma lista (fila e aba backlog — B35)."""
    return [o for o in ordens if not esta_encerrada(o)]


# Centros que NÃO são classificáveis pelo PCM nesta tela: genérico (MAN) e sem centro na
# operação 0010 (None/vazio). Não inflam a fila "pendente de classificação" nem a aba backlog (B37).
_CENTROS_NAO_CLASSIFICAVEIS = frozenset({"MAN"})


def sem_centro_classificavel(o: dict) -> bool:
    """True se a ordem não tem centro classificável na operação 0010: sem centro (None/vazio)
    ou centro genérico MAN. Essas nunca serão classificadas nesta tela → fora da fila/backlog (B37)."""
    c = (o.get("centro_operacao_0010") or "").strip().upper()
    return (not c) or (c in _CENTROS_NAO_CLASSIFICAVEIS)


def esconder_sem_centro(ordens: list) -> list:
    """Remove ordens sem centro classificável (None/MAN) de uma lista (fila e aba backlog — B37)."""
    return [o for o in ordens if not sem_centro_classificavel(o)]


def hoje_brt() -> datetime:
    """Meia-noite de hoje no fuso BRT (data de calendário para o recorte de vencidas)."""
    agora = datetime.now(tz=pytz.UTC).astimezone(_BRT)
    return datetime(agora.year, agora.month, agora.day)


def _coleta_atual(coll):
    """Lê o doc `meta` e devolve (coleta_id, coletado_em). (None, None) se não houver."""
    meta = coll.find_one({"_id": META_ID})
    if not meta:
        return None, None
    return meta.get("coleta_id_atual"), meta.get("coletado_em")


def carregar_snapshot(silent: bool = True):
    """Carrega o snapshot atual cru de `sap_backlog`.

    Retorna dict {ordens: list, coleta_id, coletado_em, total_snapshot} ou None se o
    Mongo estiver indisponível (degradação graciosa — RNF-05). `ordens=[]` se ainda não
    houve coleta (estado vazio, não erro).
    """
    coll = get_mongo_connection(COLL, silent=silent)
    if coll is None:
        return None
    coleta_id, coletado_em = _coleta_atual(coll)
    if not coleta_id:
        return {"ordens": [], "coleta_id": None, "coletado_em": None, "total_snapshot": 0}
    ordens = list(coll.find({"coleta_id": coleta_id, "_id": {"$ne": META_ID}}))
    return {
        "ordens": ordens,
        "coleta_id": coleta_id,
        "coletado_em": coletado_em,
        "total_snapshot": len(ordens),
    }


def _vencida_ou_nao_preventiva(o: dict, hoje: datetime) -> bool:
    """Recorte de exibição (SP-04): preventiva só se vencida (data_inicio <= hoje).

    Corretiva/Melhoria/Matrizes sempre passam. Preventiva sem data (None) é tratada como
    visível por completude (IN-02) — nunca descarta ordem por falta de data.
    """
    if o.get("categoria") != "Preventiva":
        return True
    di = o.get("data_inicio")
    if di is None:
        return True
    if isinstance(di, datetime):
        return di <= hoje
    return True


def _data_eixo(o: dict, eixo: str):
    """Data-base do `eixo` escolhido, com fallback. No eixo 'data_criacao' (ERDAT), se a
    ordem não tiver criação (ex: backlog sintetizado da IW37, que não traz ERDAT), cai de
    volta para 'data_inicio' (GSTRP). Mesma regra de idade que o quadro de Hora-Homem usa
    (`base = data_criacao or data_inicio`), p/ as duas telas baterem. Retorna datetime ou None."""
    d = o.get(eixo)
    if not isinstance(d, datetime) and eixo == "data_criacao":
        d = o.get("data_inicio")
    return d if isinstance(d, datetime) else None


def _passa_filtros(o: dict, f: dict, eixo: str = "data_inicio") -> bool:
    """Aplica os 6 filtros (SP-07): E entre dimensões, OU dentro da dimensão.

    `eixo` define qual data o filtro de período usa: 'data_inicio' (GSTRP, default) ou
    'data_criacao' (ERDAT). Não afeta o corte de vencidas (BR-03), que é sempre GSTRP.
    """
    if not f:
        return True
    cat = f.get("categoria")
    if cat and o.get("categoria") not in cat:
        return False
    disc = f.get("disciplina")
    if disc and o.get("disciplina") not in disc:
        return False
    sub = f.get("subclassificacao")
    if sub and o.get("subclassificacao") not in sub:
        return False
    linhas = f.get("linha")
    if linhas and o.get("_linha_id") not in linhas:
        return False
    busca = (f.get("busca") or "").strip().upper()
    if busca:
        alvo = f"{o.get('ordem','')} {o.get('descricao','')}".upper()
        if busca not in alvo:
            return False
    ini = f.get("periodo_ini")
    fim = f.get("periodo_fim")
    if ini or fim:
        di = _data_eixo(o, eixo)
        if di is None:
            return False
        if ini and di < ini:
            return False
        if fim and di > fim:
            return False
    return True


def filtrar(ordens: list, filtros: dict, hoje: datetime | None = None,
            eixo: str = "data_inicio") -> list:
    """Aplica recorte de vencidas + filtros, devolve as ordens visíveis.

    `eixo` ('data_inicio'|'data_criacao') é repassado só ao filtro de período. O recorte de
    vencidas (`_vencida_ou_nao_preventiva`) é sempre por GSTRP (BR-03), independente do eixo.
    """
    if hoje is None:
        hoje = hoje_brt()
    return [
        o for o in ordens
        if _vencida_ou_nao_preventiva(o, hoje) and _passa_filtros(o, filtros, eixo)
    ]


# ---- Dimensão de ativos (hierarquia oficial SAP — sap_ativos) -----------------------------
ATIVOS_COLL = "sap_ativos"
_ativos_cache = {"idx": None}


def carregar_ativos(forcar: bool = False) -> dict:
    """Carrega a dimensão de ativos (`sap_ativos`) como {id: nó}. Cache em memória
    (recarrega no boot/restart ou com forcar=True). 5 níveis pai-filho: Planta, Linha,
    Conjunto (por TPLNR) + Equipamento, Componente (por EQUNR)."""
    if _ativos_cache["idx"] is not None and not forcar:
        return _ativos_cache["idx"]
    coll = get_mongo_connection(ATIVOS_COLL, silent=True)
    if coll is None:
        return {}
    idx = {n["id"]: n for n in coll.find({}, {"_id": 0})}
    _ativos_cache["idx"] = idx
    return idx


def _resolver(tplnr: str, idx: dict):
    """Sobe a árvore a partir do TPLNR da ordem e devolve (nó Linha, nó Conjunto).
    Níveis 1-3 têm id == tplnr. Nó ausente → (None, None)."""
    cur = idx.get((tplnr or "").strip())
    linha = conj = None
    visita = 0
    while cur and visita < 12:
        nv = cur.get("nivel")
        if nv == "LINHA":
            linha = cur
        elif nv == "CONJUNTO":
            conj = cur
        cur = idx.get(cur.get("pai"))
        visita += 1
    return linha, conj


def resolver_linha(tplnr: str, idx: dict | None = None) -> dict | None:
    """Nó Linha da hierarquia oficial a partir de um TPLNR (local de instalação), subindo a árvore.

    Público (usado por `hh_data` para re-resolver a Linha de cards congelados que guardaram o
    TPLNR mas não a `linha_nome`). `idx=None` usa a árvore cacheada (`carregar_ativos`). Devolve o
    nó Linha (`{id, descricao, ...}`) ou `None` se o TPLNR não estiver na árvore / sem Linha acima.
    """
    if not (tplnr or "").strip():
        return None
    linha, _conj = _resolver(tplnr, idx if idx is not None else carregar_ativos())
    return linha


def enriquecer_local(ordens: list, idx: dict) -> list:
    """Anexa a cada ordem o nó Linha/Conjunto resolvido pela árvore oficial.

    Conjunto = local mais específico da ordem: se não há conjunto (ordem amarrada direto
    na Linha), sobe um nível e usa o nó da própria ordem (a Linha) — minimiza os "—".
    Quando o EQUNR chegar (níveis Equipamento/Componente), a ordem amarra mais fundo e o
    conjunto exibe o nível mais baixo disponível automaticamente.
    """
    for o in ordens:
        tplnr = (o.get("local_instalacao") or "").strip()
        node = idx.get(tplnr)
        linha, conj = _resolver(tplnr, idx)
        o["_linha_id"] = linha["id"] if linha else None
        o["_linha_nome"] = linha["descricao"] if linha else ""
        if conj:
            o["_conjunto_nome"] = conj["descricao"]
        elif node:
            o["_conjunto_nome"] = node["descricao"]            # sobe um: nó próprio (Linha)
        else:
            o["_conjunto_nome"] = (o.get("local_descricao") or "").strip()  # fora da árvore
    return ordens


def opcoes_linhas(idx: dict) -> list:
    """Opções do filtro Linha = as 21 Linhas oficiais (label=descrição, value=id)."""
    linhas = [n for n in idx.values() if n.get("nivel") == "LINHA"]
    opts = [{"label": n["descricao"], "value": n["id"]} for n in linhas]
    opts.sort(key=lambda x: x["label"])
    return opts


def dados_rosca_categoria(ordens: list):
    """(labels, valores) por categoria, na ordem fixa Prev/Corr/Melh/Matr."""
    cont = {c: 0 for c in CATEGORIAS}
    for o in ordens:
        c = o.get("categoria")
        if c in cont:
            cont[c] += 1
    labels = ["Preventiva", "Corretiva", "Melhoria", "Matrizes"]
    return labels, [cont[c] for c in labels]


def dados_rosca_disciplina(ordens: list):
    """(labels, valores) por disciplina: Mecânica/Elétrica/Terceiros/Gestão/Não classificado (B34).

    Fatias com contagem 0 saem do gráfico (plotly ignora), então Terceiros/Gestão só aparecem
    quando houver ordens desses centros (Z03/Z01).
    """
    cont = {d: 0 for d in DISCIPLINAS}
    for o in ordens:
        d = o.get("disciplina")
        if d in cont:
            cont[d] += 1
    labels = [LABEL_DISCIPLINA[d] for d in DISCIPLINAS]
    return labels, [cont[d] for d in DISCIPLINAS]


def dados_rosca_linha(ordens: list, topn: int = 8):
    """(labels, valores) por Linha (equipamento-pai): top N + 'Outras'. Requer ordens
    já enriquecidas (`_linha_nome`)."""
    cont = {}
    for o in ordens:
        nome = o.get("_linha_nome") or "(sem linha)"
        cont[nome] = cont.get(nome, 0) + 1
    itens = sorted(cont.items(), key=lambda kv: kv[1], reverse=True)
    top = itens[:topn]
    outras = sum(v for _, v in itens[topn:])
    labels = [k for k, _ in top]
    vals = [v for _, v in top]
    if outras:
        labels.append("Outras")
        vals.append(outras)
    return labels, vals


def dados_barras_mes(ordens: list, eixo: str = "data_inicio"):
    """(labels 'MM/AAAA', valores) por mês/ano da data do `eixo` escolhido (início ou
    criação), em ordem cronológica."""
    cont = {}
    for o in ordens:
        di = _data_eixo(o, eixo)
        if di is not None:
            cont[(di.year, di.month)] = cont.get((di.year, di.month), 0) + 1
    chaves = sorted(cont.keys())
    labels = [f"{m:02d}/{y}" for (y, m) in chaves]
    return labels, [cont[k] for k in chaves]


def insights(ordens: list, hoje: datetime | None = None,
             eixo: str = "data_inicio") -> dict:
    """Métricas de texto do painel (respeitam o recorte filtrado).

    `eixo` define a data-base da idade/inflow: 'data_inicio' (GSTRP) ou 'data_criacao' (ERDAT).
    """
    if hoje is None:
        hoje = hoje_brt()
    total = len(ordens)
    res = {"total": total}
    idades = []
    for o in ordens:
        di = _data_eixo(o, eixo)
        if di is not None:
            d = (hoje - di).days
            if d >= 0:
                idades.append((d, o))
    if idades:
        idades.sort(key=lambda x: x[0], reverse=True)
        d0, o0 = idades[0]
        res["mais_antiga_dias"] = d0
        res["mais_antiga_ordem"] = o0.get("ordem", "")
        ds = [d for d, _ in idades]
        res["idade_media"] = round(sum(ds) / len(ds))
        res["idade_mediana"] = sorted(ds)[len(ds) // 2]
        res["inflow_30"] = sum(1 for d in ds if d <= 30)
    nc = sum(1 for o in ordens if o.get("disciplina") == "NaoClassificado")
    res["nc_n"] = nc
    res["nc_pct"] = round(100 * nc / total) if total else 0
    cont_linha = {}
    for o in ordens:
        nome = o.get("_linha_nome") or "(sem linha)"
        cont_linha[nome] = cont_linha.get(nome, 0) + 1
    if cont_linha:
        nome, c = max(cont_linha.items(), key=lambda kv: kv[1])
        res["linha_top_nome"] = nome
        res["linha_top_n"] = c
    corr = sum(1 for o in ordens if o.get("categoria") == "Corretiva")
    prev = sum(1 for o in ordens if o.get("categoria") == "Preventiva")
    res["razao_cp"] = round(corr / prev, 2) if prev else None
    return res


def agregar_cards(ordens: list) -> dict:
    """Contagens dos cards (SP-05): total, por categoria, e por disciplina nas que têm."""
    res = {"total": len(ordens)}
    for cat in CATEGORIAS:
        do_cat = [o for o in ordens if o.get("categoria") == cat]
        if cat in CATEGORIAS_COM_DISCIPLINA:
            bloco = {"total": len(do_cat)}
            for d in DISCIPLINAS:
                bloco[d] = sum(1 for o in do_cat if o.get("disciplina") == d)
            res[cat] = bloco
        else:
            res[cat] = {"total": len(do_cat)}
    return res
