# -*- coding: utf-8 -*-
"""Seed de QA — popula `sap_backlog` com o snapshot mock (8 ordens) para testar a página
Backlog sem depender do SAP do cliente. Rodar FORA do ai-jail (precisa de MONGO_URI/DB_NAME).

    cd ~/projects/AMG/AMG_Infra && set -a && . environments/local/.env && set +a
    python ~/projects/AMG/AMG-wt/backlog/AMG_Data/webapp/seed_backlog_mock.py

Cobre as 4 categorias, Mecânica/Elétrica/Não classificado e 1 preventiva futura (não
vencida) — que NÃO deve aparecer na página (recorte "só vencidas"). Espelha mock_ordens()
do daemon já derivado por _classifica.py (DS-03). Idempotente: limpa e regrava o snapshot.
"""
import os
from datetime import datetime

from pymongo import MongoClient

COLL = "sap_backlog"
COLETA_ID = "MOCKSEED.0001"
COLETADO_EM = datetime(2026, 6, 27, 4, 1)  # naïve UTC (como o Mongo guarda)

# 8 ordens mock já DERIVADAS (categoria/disciplina/subclassificação) conforme BR-02/04/05/06.
ORDENS = [
    ("5012522", "YPM1", "Corretiva", "TROCA ROLAMENTO PRENSA 01", "BR02-0100-1600",
     datetime(2026, 5, 13), "Z10", "Mecanica", "Corretiva"),
    ("5013391", "YPM1", "Corretiva", "PAINEL ELETRICO LINHA 2", "BR02-0100-1300",
     datetime(2026, 4, 11), "Z20", "Eletrica", "Corretiva"),
    ("5019639", "YPM1", "Corretiva", "ORDEM NOVA SEM RECLASSIFICAR", "BR02-0700-0200",
     datetime(2026, 6, 20), "Z02", "NaoClassificado", None),
    ("5012523", "YPM2", "Preventiva", "CALIBRACAO BALANCA ROD", "BR02-0100-1600",
     datetime(2026, 2, 21), "Z13", "Mecanica", "Preditiva"),
    ("5010812", "YPM2", "Preventiva", "PREVENTIVA CENTRAL EMG - ELE", "BR02-0700-0200",
     datetime(2026, 5, 25), "Z21", "Eletrica", "PDCA"),
    ("5099999", "YPM2", "Preventiva", "PREVENTIVA FUTURA (NAO VENCIDA)", "BR02-0100-0300",
     datetime(2026, 12, 15), "Z10", "Mecanica", "Corretiva"),
    ("5019529", "YPM8", "Melhoria", "(TEK)MELHORIA SINOPTICO IHM PRENSA", "BR02-0100-1600",
     datetime(2026, 6, 1), "Z10", None, None),
    ("5019628", "YPM9", "Matrizes", "MANUT MATRIZ ESTAMPO", "BR02-0100-1500",
     datetime(2026, 5, 30), "Z12", None, None),
]


def main():
    uri, dbn = os.getenv("MONGO_URI"), os.getenv("DB_NAME")
    if not uri or not dbn:
        raise SystemExit("Defina MONGO_URI e DB_NAME (carregue o .env do ambiente local).")
    coll = MongoClient(uri)[dbn][COLL]
    docs = [{
        "ordem": o[0], "tipo": o[1], "categoria": o[2], "descricao": o[3],
        "local_instalacao": o[4], "data_inicio": o[5], "centro_operacao_0010": o[6],
        "disciplina": o[7], "subclassificacao": o[8],
        "coleta_id": COLETA_ID, "coletado_em": COLETADO_EM,
    } for o in ORDENS]
    coll.delete_many({})
    coll.insert_many(docs)
    coll.update_one({"_id": "meta"}, {"$set": {
        "coleta_id_atual": COLETA_ID, "coletado_em": COLETADO_EM, "total": len(docs)}},
        upsert=True)
    print(f"seed OK — {len(docs)} ordens em '{COLL}' (coleta_id={COLETA_ID})")


if __name__ == "__main__":
    main()
