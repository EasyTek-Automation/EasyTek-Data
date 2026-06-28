"""Migracoes idempotentes do sap-scheduler (DS-07 / SP-08 RF-08-08..11).

Convencao pra futuras migracoes:
- Funcao publica nomeada `migracao_<descricao_curta>`.
- Idempotente — rodar 2x nao causa efeito colateral.
- Loga INFO ao iniciar e ao concluir; INFO por grupo afetado.
- Nao levanta excecao em estado consistente — retorna 0 silenciosamente.
- Roda no boot do webapp ANTES de operacoes que dependam do estado limpo.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def migracao_dedup_sap_jobs(db, collection_name: str = "sap_jobs") -> int:
    """Remove duplicatas de `sap_jobs` por chave `(tipo, agendado_para)`.

    Mantem o PRIMEIRO doc de cada grupo (insertion order ~= ordem dos `_id`),
    deleta os demais. Idempotente: 2a chamada acha 0 grupos duplicados.

    DEVE rodar ANTES de `ensure_indexes()` (que cria `idx_dedup_agendamento`
    unique e falharia em duplicates pre-existentes com `E11000`).

    Args:
        db: handle do database Mongo (objeto, nao Collection).
        collection_name: nome da collection (override em teste).

    Returns:
        Numero total de docs deletados (0 se ambiente ja consistente).
    """
    coll = db[collection_name]

    pipeline = [
        {
            "$group": {
                "_id": {"tipo": "$tipo", "agendado_para": "$agendado_para"},
                "ids": {"$push": "$_id"},
                "count": {"$sum": 1},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
    ]

    duplicados = list(coll.aggregate(pipeline))

    if not duplicados:
        logger.info("[migracao_dedup_sap_jobs] no-op — sem duplicatas")
        return 0

    total_deletados = 0
    for grupo in duplicados:
        ids_a_deletar = grupo["ids"][1:]  # mantem o primeiro _id de cada grupo
        result = coll.delete_many({"_id": {"$in": ids_a_deletar}})
        deletados = result.deleted_count
        total_deletados += deletados
        logger.info(
            "[migracao_dedup_sap_jobs] tipo=%s agendado_para=%s deletados=%d",
            grupo["_id"]["tipo"],
            grupo["_id"]["agendado_para"],
            deletados,
        )

    logger.info(
        "[migracao_dedup_sap_jobs] concluido. grupos_duplicados=%d total_deletados=%d",
        len(duplicados),
        total_deletados,
    )
    return total_deletados


def migracao_agendamento_backlog(
    db, collection_name: str = "sap_scheduler_config"
) -> int:
    """Garante o agendamento diário do job `backlog` (04:00) no singleton de config.

    Idempotente: adiciona `{tipo:"backlog", hora:"04:00", ativo:True}` ao array
    `agendamentos` apenas se ainda não houver entrada `tipo=backlog`. Necessária porque
    `bootstrap_config` usa `$setOnInsert` — não toca singletons já existentes (instalações
    em produção). Não sobrescreve a hora se o usuário já tiver ajustado pela UI admin.

    Args:
        db: handle do database Mongo (objeto, não Collection).
        collection_name: nome da collection do singleton (default sap_scheduler_config).

    Returns:
        1 se inseriu o agendamento; 0 se já existia (no-op).
    """
    coll = db[collection_name]
    res = coll.update_one(
        {"_id": "singleton", "agendamentos.tipo": {"$ne": "backlog"}},
        {"$push": {"agendamentos": {"tipo": "backlog", "hora": "04:00", "ativo": True}}},
    )
    if res.modified_count:
        logger.info("[migracao_agendamento_backlog] agendamento backlog 04:00 adicionado")
        return 1
    logger.info("[migracao_agendamento_backlog] no-op — backlog já agendado ou singleton ausente")
    return 0
