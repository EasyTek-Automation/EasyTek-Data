"""Esquema e indices das coleches de custo de manutencao (DS-03).

Duas coleches, separadas por granularidade:
- **`AMG_CustoResumo`**: 1 doc por conta x mes — alimenta graficos, %/saldo e a
  reconciliacao (guarda o total oficial do mes). Nao tem dimensao de centro.
- **`AMG_CustoLancamentos`**: 1 doc por gasto individual — alimenta a tabela e o
  filtro por centro de custo (unica coleche com centro).

A chave de janela das duas e `mes_referencia` ("YYYY-MM"), base do delete-por-janela
(BR-09 — idempotencia). Indices criados de forma idempotente (`create_index` nao
duplica se ja existir com a mesma definicao), no padrao de `sap_scheduler/migrations.py`.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Nomes fixos das coleches (nao mudam com o ano — padrao do projeto).
COLL_RESUMO = "AMG_CustoResumo"
COLL_LANCAMENTOS = "AMG_CustoLancamentos"
# Config leve da feature (doc unico por chave) — ex: contas fixadas no slide da home.
COLL_CONFIG = "AMG_CustoConfig"
# De/para codigo->nome (1 doc por codigo, _id=codigo), populado pelo daemon a partir do
# OBJ_TXT/CEL_LTXT da KSB1. Fonte do nome de centro/conta na tela (sem dict manual).
COLL_CENTROS = "AMG_CustoCentros"
COLL_CONTAS = "AMG_CustoContas"


def ensure_indexes(db) -> None:
    """Garante os indices das duas coleches de custo. Idempotente.

    Indices:
    - resumo `idx_resumo_conta_mes` (mes_referencia, conta) UNIQUE
        -> 1 doc por conta x mes; suporta o delete-por-janela e o left-join da lista.
    - lancamentos `idx_lanc_conta_data` (mes_referencia, conta, data_lancamento)
        -> drill-down conta -> mes -> dia.
    - lancamentos `idx_lanc_centro` (centro_custo)
        -> filtro lateral por centro de custo.

    Pode ser chamado tanto pelo boot do webapp quanto pelo loader de seed
    (defesa em profundidade — as duas pontas garantem o estado).
    """
    db[COLL_RESUMO].create_index(
        [("mes_referencia", 1), ("conta", 1)],
        name="idx_resumo_conta_mes",
        unique=True,
    )
    db[COLL_LANCAMENTOS].create_index(
        [("mes_referencia", 1), ("conta", 1), ("data_lancamento", 1)],
        name="idx_lanc_conta_data",
    )
    db[COLL_LANCAMENTOS].create_index(
        [("centro_custo", 1)],
        name="idx_lanc_centro",
    )
    logger.info(
        "custos: indices garantidos (%s.idx_resumo_conta_mes unique; "
        "%s.idx_lanc_conta_data, idx_lanc_centro)",
        COLL_RESUMO,
        COLL_LANCAMENTOS,
    )
