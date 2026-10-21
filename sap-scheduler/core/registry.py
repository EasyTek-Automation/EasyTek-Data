# -*- coding: utf-8 -*-
"""Registro tipo → script. ÚNICO lugar que liga um tipo de job ao seu script.

Adicionar uma transação nova = 1 import + 1 linha aqui (+ o arquivo do script).
O motor (executor) NÃO conhece nenhum tipo — só consulta este dict.
"""
from __future__ import annotations

from ..trabalhos.kpis_manut import zppprd, nt0001, zpp_paradas
from ..trabalhos.custos_manut import custo_exec, custo_orcado
from ..trabalhos.backlog import backlog
from ..trabalhos.hh import hh

# tipo (campo `tipo` da coleche sap_jobs) → função run(job, ctx) -> Result
REGISTRY = {
    "zppprd":       zppprd.run,
    "zpp_nt0001":   nt0001.run,
    "zpp_paradas_pendentes": zpp_paradas.run,  # KPIReport-v2 BR-14 (retrato ZPPPARADAS)
    "custo_exec":   custo_exec.run,
    "custo_orcado": custo_orcado.run,
    "backlog":      backlog.run,
    "hh_planejado": hh.run_planejado,
    "hh_realizado": hh.run_realizado,
    "hh_entregas":  hh.run_entregas,
}
