# -*- coding: utf-8 -*-
"""Sintetiza um snapshot de `sap_backlog` a partir do CSV do IW37 (para TESTE local).

O backlog real vem do job IW39+IW37 (/BACKLOG) do daemon, que precisa do SAP. Sem ele,
esta ferramenta deriva um `sap_backlog` de volume realista a partir do IW37 já exportado
(uma ordem por AUFNR, usando a operação 0010 para tipo/centro/descrição/local/data),
reusando a MESMA classificação do daemon (`_classifica`). Para testar a aba Backlog com
dados de verdade enquanto o backlog real não é coletado.

⚠️ APROXIMAÇÃO: a descrição vira o texto da operação 0010 (LTXA1) — o IW37 não traz o
título da ordem (KTEXT, que vem da IW39). Demais campos (tipo/categoria/disciplina/local/
data de início) são fiéis. data_criacao fica vazia (não há ERDAT no IW37).

Uso (host, Mongo local):
  python3 sap-scheduler/ferramentas/seed_backlog_from_iw37.py \
      --iw37 IW37_planejado.csv --mongo-uri mongodb://localhost:27017 --db Cluster-EasyTek
"""
from __future__ import annotations

import argparse
import csv
import datetime
import importlib
import sys
from pathlib import Path

_PARENT = Path(__file__).resolve().parents[2]  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

_classifica = importlib.import_module("sap-scheduler.trabalhos.backlog._classifica")
_carga = importlib.import_module("sap-scheduler.trabalhos.backlog._carga")
_parse = importlib.import_module("sap-scheduler.trabalhos.hh._parse")

COLL = "sap_backlog"


def _op_repr(linhas: list[dict]) -> dict:
    """Linha representativa da ordem: a operação 0010 se houver, senão a de menor VORNR."""
    by = {str(l.get("VORNR", "") or "").strip(): l for l in linhas}
    return by.get("0010") or linhas[sorted(range(len(linhas)),
                                            key=lambda i: str(linhas[i].get("VORNR") or ""))[0]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iw37", required=True)
    ap.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    ap.add_argument("--db", default="Cluster-EasyTek")
    a = ap.parse_args()

    with open(a.iw37, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    # agrupa por ordem (descarta linha de total/sem ordem)
    por_ordem: dict[str, list] = {}
    for r in rows:
        aufnr = str(r.get("AUFNR", "") or "").strip()
        if not aufnr:
            continue
        por_ordem.setdefault(aufnr, []).append(r)

    agora = datetime.datetime.now()
    coleta_id = agora.strftime("%Y%m%d.%H%M")
    docs = []
    for aufnr, linhas in por_ordem.items():
        rep = _op_repr(linhas)
        # menor data de início planejada entre as operações
        datas = [_parse.parse_data(l.get("FSAVD")) for l in linhas]
        datas = [d for d in datas if d]
        cru = {
            "ordem": aufnr,
            "tipo": rep.get("AUART"),
            "descricao": rep.get("LTXA1") or "",     # ⚠ texto da operação (aprox. do título)
            "local_instalacao": rep.get("TPLNR") or "",
            "local_descricao": "",
            "data_inicio": min(datas) if datas else None,
            "data_criacao": None,                      # IW37 não traz ERDAT
            "centro_operacao_0010": rep.get("ARBPL"),
        }
        docs.append(_classifica.montar_doc(cru, coleta_id, agora))

    docs = [d for d in docs if d.get("categoria")]    # só tipos válidos (YPM1/2/8/9)

    from pymongo import MongoClient
    direto = any(h in a.mongo_uri for h in ("localhost", "127.0.0.1"))
    db = MongoClient(a.mongo_uri, directConnection=direto)[a.db]
    db[COLL].drop()        # reseed limpo (descarta o seed antigo e seus índices)
    _carga.ensure_indexes(db, COLL)
    n = _carga.gravar_snapshot(db, COLL, docs, coleta_id, agora)
    from collections import Counter
    disc = Counter(d["disciplina"] for d in docs)
    print(f"[backlog sintetizado] {len(por_ordem)} ordens → {n} gravadas (tipos válidos) | "
          f"disciplina: {dict(disc)} | coleta_id={coleta_id}")
    print("⚠ descrição = texto da operação 0010 (aprox.); backlog real exige export IW39 do cliente.")


if __name__ == "__main__":
    main()
