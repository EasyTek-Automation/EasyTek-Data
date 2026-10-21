# -*- coding: utf-8 -*-
"""De/para do código de executor (PERNR persona `8999xxxx`) → nome real do técnico.

O SAP não guarda o nome real do executor — só uma máscara de 1-2 letras (infotipo 0002). O
IW47 devolve a persona anonimizada (`89990001`, ...) e é isso que chega no campo `executores`
das collections de HH realizado. Sem tradução, o modal de detalhe da ordem mostra o código
cru. Este módulo semeia a collection `hh_executores` (fonte autoritativa = `roster_executores.json`,
validado contra SAP em 2026-07-22) e expõe o lookup usado na renderização.

Realiza SP-06.6 / BR-14 (fonte sigla↔nome). A collection é dado ESTÁTICO — nenhum daemon a
reescreve —, então o seed é upsert idempotente por código: editar o JSON + redeploy
re-sincroniza. Manter o JSON quando entrar técnico novo (é a única fonte do nome real).
"""
from __future__ import annotations

import json
import logging
import os

try:
    from src.database.connection import get_mongo_connection
except ImportError:  # execução fora do pacote src
    from database.connection import get_mongo_connection

logger = logging.getLogger("hh_executores")

COLL_EXECUTORES = "hh_executores"
_ROSTER_JSON = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "roster_executores.json"
)
LABEL_SEM_EXECUTOR = "Sem executor"
# valores que o IW47 usa para "sem executor" (além do 89990000 do roster)
_SEM_EXECUTOR = {"", "0", "00000000", "89990000"}

# cache do mapa código→nome de exibição (montado 1x; a collection é estática)
_CACHE: dict | None = None


def _carregar_roster() -> dict:
    """Lê o roster_executores.json empacotado. {} se ausente/ilegível (degrada gracioso)."""
    try:
        with open(_ROSTER_JSON, encoding="utf-8") as fh:
            return json.load(fh).get("executores") or {}
    except (OSError, ValueError):
        logger.exception("roster_executores.json ausente/inválido — seed de executores pulado")
        return {}


def seed_executores(silent: bool = True) -> int:
    """Semeia/atualiza `hh_executores` a partir do JSON (upsert idempotente por código).

    Bootstrap-no-boot: chamado no `app.py`. Retorna o nº de códigos processados (0 se Mongo
    offline ou JSON vazio). Não é bootstrap-only — o JSON é a fonte autoritativa, então cada
    boot re-sincroniza; sem daemon concorrente, o upsert idempotente é seguro entre workers.
    """
    roster = _carregar_roster()
    if not roster:
        return 0
    coll = get_mongo_connection(COLL_EXECUTORES, silent=silent)
    if coll is None:
        return 0
    n = 0
    for codigo, dados in roster.items():
        doc = {
            "nome": dados.get("nome"),
            "tipo": dados.get("tipo"),
            "sap_vorna": dados.get("sap_vorna"),
            "sap_nachn": dados.get("sap_nachn"),
            "inicial_confere": dados.get("inicial_confere"),
        }
        coll.update_one({"_id": str(codigo)}, {"$set": doc}, upsert=True)
        n += 1
    _reset_cache()
    logger.info("hh_executores: %d executores semeados/atualizados", n)
    return n


def _reset_cache() -> None:
    """Invalida o cache do mapa (após seed ou em teste)."""
    global _CACHE
    _CACHE = None


def _rotulo(doc: dict) -> str:
    """Nome de exibição de um doc de executor. Terceiro/técnico → nome; sem_executor → rótulo."""
    if doc.get("tipo") == "sem_executor" or not doc.get("nome"):
        return LABEL_SEM_EXECUTOR
    return doc["nome"]


def mapa_executores(silent: bool = True) -> dict:
    """Mapa código→nome de exibição (cacheado). {} se Mongo offline."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    coll = get_mongo_connection(COLL_EXECUTORES, silent=silent)
    if coll is None:
        return {}
    _CACHE = {str(d["_id"]): _rotulo(d) for d in coll.find({})}
    return _CACHE


def nome_executor(codigo, silent: bool = True) -> str:
    """Nome de exibição de um código. Código desconhecido → o próprio código (fallback seguro)."""
    if codigo is None or str(codigo) in _SEM_EXECUTOR:
        return LABEL_SEM_EXECUTOR
    return mapa_executores(silent).get(str(codigo), str(codigo))


def nomes_executores(codigos, silent: bool = True) -> list[str]:
    """Traduz uma lista de códigos → nomes, preservando ordem e sem duplicar. [] se vazio/None.

    Entradas 'sem executor' (0/vazio/89990000) são descartadas da lista — não poluem a linha
    com "Sem executor" ao lado de técnicos reais.
    """
    if not codigos:
        return []
    mp = mapa_executores(silent)
    out: list[str] = []
    for c in codigos:
        if c is None or str(c) in _SEM_EXECUTOR:
            continue
        nome = mp.get(str(c), str(c))
        if nome not in out:
            out.append(nome)
    return out
