# -*- coding: utf-8 -*-
"""_ids_lote (Atualizar agora) — correção 2026-07-28: acompanha só o job ATIVO de cada tipo,
nunca um concluído antigo (que fazia a UI mostrar 'concluído ✓' para coleta não disparada)."""
from unittest.mock import MagicMock

from src.callbacks_registers.hh_quadro_callbacks import _ids_lote


def test_ids_lote_pega_ativo_ignora_tipo_sem_ativo():
    db = MagicMock()
    coll = MagicMock()
    db.__getitem__.return_value = coll

    def fake_find_one(filtro, sort=None, projection=None):
        # backlog tem job ativo; hh_planejado não tem ativo (find_one filtrado devolve None)
        return {"_id": "ativo-backlog"} if filtro.get("tipo") == "backlog" else None

    coll.find_one.side_effect = fake_find_one
    ids = _ids_lote(db, ("backlog", "hh_planejado"))
    assert ids == ["ativo-backlog"]                    # só o ativo entra; sem ativo não vira "concluído"

    # o filtro DEVE exigir status ativo (pendente/executando)
    filtro0 = coll.find_one.call_args_list[0][0][0]
    assert filtro0["tipo"] == "backlog"
    assert filtro0["status"]["$in"] == ["pendente", "executando"]
