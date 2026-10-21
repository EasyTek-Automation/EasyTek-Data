# -*- coding: utf-8 -*-
"""Carrega os CSVs de HH (IW37 planejado + IW47 realizado, gerados pelo iw_fastexport.py no
cliente) no Mongo LOCAL — para testar o quadro semanal sem coleta SAP real.

Reusa a MESMA agregação dos jobs do daemon (`trabalhos/hh/_agg` e `_carga`): dedup do
planejado, soma do realizado, exclusão da linha de total (BR-10), checagem de sanidade, e
snapshot atômico nas collections `sap_hh_planejado`/`sap_hh_realizado`.

Uso (na máquina local, FORA do jail, Mongo local na 27017):
  python3 sap-scheduler/ferramentas/load_hh_csv.py \
      --planejado IW37_planejado.csv --realizado IW47_realizado.csv \
      --mongo-uri mongodb://localhost:27017 --db Cluster-EasyTek

Cada arquivo é opcional (carrega só o que passar). Substitui o snapshot atual da collection.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import importlib
import sys
from pathlib import Path

# pacote do daemon tem hífen → importlib com o parent (AMG_Data/) no sys.path
_PARENT = Path(__file__).resolve().parents[2]  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

_agg = importlib.import_module("sap-scheduler.trabalhos.hh._agg")
_carga = importlib.import_module("sap-scheduler.trabalhos.hh._carga")


def _ler_csv(caminho: str) -> list[dict]:
    """Lê o CSV (cabeçalho = nomes técnicos SAP) como list[dict]."""
    with open(caminho, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--planejado", help="CSV do IW37 (planejado)")
    ap.add_argument("--realizado", help="CSV do IW47 (realizado)")
    ap.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    ap.add_argument("--db", default="Cluster-EasyTek")
    a = ap.parse_args()

    from pymongo import MongoClient
    # directConnection: o Mongo local é replica set que se anuncia como 'database:27017'
    # (nome interno da rede docker) — sem isso, a descoberta de topologia falha a partir do host.
    direto = any(h in a.mongo_uri for h in ("localhost", "127.0.0.1"))
    db = MongoClient(a.mongo_uri, directConnection=direto)[a.db]
    agora = datetime.datetime.now()
    coleta_id = agora.strftime("%Y%m%d.%H%M")

    if a.planejado:
        rows = _ler_csv(a.planejado)
        docs, info = _agg.agregar_planejado(rows, coleta_id, agora)
        ok = _agg.checar_sanidade_total(rows, info["total_planejado_min"], "ARBEI")
        _carga.ensure_indexes(db, _carga_coll_plan())
        n = _carga.gravar_snapshot(db, _carga_coll_plan(), docs, coleta_id, agora)
        print(f"[planejado] {len(rows)} linhas → {n} operações | "
              f"total {info['total_planejado_min']} min | sanidade {'OK' if ok else 'DIVERGE'}")

    if a.realizado:
        rows = _ler_csv(a.realizado)
        docs, info = _agg.agregar_realizado(rows, coleta_id, agora)
        ok = _agg.checar_sanidade_total(rows, info["total_realizado_min"], "ISMNW")
        _carga.ensure_indexes(db, _carga_coll_real())
        n = _carga.gravar_snapshot(db, _carga_coll_real(), docs, coleta_id, agora)
        print(f"[realizado] {len(rows)} linhas → {n} operações | "
              f"total {info['total_realizado_min']} min | sanidade {'OK' if ok else 'DIVERGE'}")

    if not a.planejado and not a.realizado:
        print("nada a carregar — passe --planejado e/ou --realizado")
    else:
        print(f"coleta_id={coleta_id} | db={a.db} | OK. Recarregue o quadro no webapp.")


def _carga_coll_plan() -> str:
    """Nome da collection-fonte de planejado (espelha hh.COLL_PLANEJADO)."""
    return "sap_hh_planejado"


def _carga_coll_real() -> str:
    """Nome da collection-fonte de realizado (espelha hh.COLL_REALIZADO)."""
    return "sap_hh_realizado"


if __name__ == "__main__":
    main()
