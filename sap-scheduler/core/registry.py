# -*- coding: utf-8 -*-
"""Registro tipo → script. ÚNICO lugar que liga um tipo de job ao seu script.

Adicionar uma transação nova = 1 import + 1 linha aqui (+ o arquivo do script).
O motor (executor) NÃO conhece nenhum tipo — só consulta este dict.
"""
from __future__ import annotations

from ..trabalhos.kpis_manut import zppprd, nt0001
from ..trabalhos.custos_manut import custo_exec, custo_orcado
from ..trabalhos.backlog import backlog

# tipo (campo `tipo` da coleche sap_jobs) → função run(job, ctx) -> Result
REGISTRY = {
    "zppprd":       zppprd.run,
    "zpp_nt0001":   nt0001.run,
    "custo_exec":   custo_exec.run,
    "custo_orcado": custo_orcado.run,
    "backlog":      backlog.run,
}
