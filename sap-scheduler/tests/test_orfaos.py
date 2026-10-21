# -*- coding: utf-8 -*-
"""Self-heal de órfãos no boot (OP-06 — revisado 2026-07-28): detectar_orfaos marca jobs
`executando` antigos como `falhou`, e não estoura mais no fuso (iniciado_em naive × now aware)."""
import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytz

_PARENT = Path(__file__).resolve().parents[2]  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

mongo = importlib.import_module("sap-scheduler.core.mongo")


def _db_com_orfaos(docs):
    """Fake de db: find() devolve os docs; update_one() conta chamadas e devolve modified_count=1."""
    coll = MagicMock()
    coll.find.return_value = iter(docs)
    coll.update_one.return_value = MagicMock(modified_count=1)
    db = MagicMock()
    db.__getitem__.return_value = coll
    return db, coll


def test_orfao_naive_marca_falhou_sem_typeerror():
    """iniciado_em NAIVE (como o Mongo devolve) + antigo → marca falhou, sem TypeError de fuso."""
    ini = datetime.now(tz=pytz.UTC).replace(tzinfo=None) - timedelta(hours=5)
    db, coll = _db_com_orfaos([{"_id": "x1", "tipo": "backlog", "iniciado_em": ini}])
    n = mongo.detectar_orfaos(db, idade_minima_horas=1)
    assert n == 1
    # update_one chamado transicionando para 'falhou'
    _, kwargs = coll.update_one.call_args
    setter = kwargs["update"]["$set"] if "update" in kwargs else coll.update_one.call_args[0][1]["$set"]
    assert setter["status"] == "falhou"


def test_orfao_aware_normaliza():
    """iniciado_em AWARE (conexão tz_aware) também é tratado, sem estourar."""
    ini = datetime.now(tz=pytz.UTC) - timedelta(hours=3)
    db, coll = _db_com_orfaos([{"_id": "x2", "tipo": "hh_realizado", "iniciado_em": ini}])
    n = mongo.detectar_orfaos(db, idade_minima_horas=1)
    assert n == 1
    assert coll.update_one.called


def test_sem_orfaos_nao_marca_nada():
    """Nenhum doc órfão → count 0, nenhum update."""
    db, coll = _db_com_orfaos([])
    n = mongo.detectar_orfaos(db, idade_minima_horas=1)
    assert n == 0
    coll.update_one.assert_not_called()
