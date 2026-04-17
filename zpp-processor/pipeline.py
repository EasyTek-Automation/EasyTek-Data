"""
Pipeline de processamento ZPP — orquestra as 10 etapas (SP-01 a SP-07).
Ponto de entrada único para ambos os canais: padrão e retroativo.
"""
import logging
import re
import traceback
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import BulkWriteError

import config
from cleaner import ZPPCleaner, UnknownFileTypeError, detect_file_type
from locks import acquire_lock, LockActiveError
from models.processing_log import build_log_doc

logger = logging.getLogger(__name__)

_BRT = ZoneInfo("America/Sao_Paulo")

# Prefixos de equipamentos a filtrar antes do threshold (regra de negócio)
_IGNORE_PREFIXES = ("EMBAL", "EMBBOBCP")


# ---------------------------------------------------------------------------
# Resultado do pipeline
# ---------------------------------------------------------------------------

@dataclass
class ProcessResult:
    arquivo: str
    tipo: str
    canal: str
    operador: str
    justificativa: str | None
    mes_referencia: str
    iniciado_em: datetime
    finalizado_em: datetime
    status: str                              # "success" | "failed" | "rejected"
    registros_inseridos: int = 0
    registros_deletados: int = 0
    strays_descartados: list = field(default_factory=list)
    duplicatas_ignoradas: int = 0
    inconsistencias: list = field(default_factory=list)
    motivo_rejeicao: str | None = None
    erro: str | None = None

    def to_log_doc(self) -> dict:
        return build_log_doc(
            arquivo=self.arquivo,
            tipo=self.tipo,
            canal=self.canal,
            operador=self.operador,
            justificativa=self.justificativa,
            mes_referencia=self.mes_referencia,
            iniciado_em=self.iniciado_em,
            finalizado_em=self.finalizado_em,
            status=self.status,
            registros_inseridos=self.registros_inseridos,
            registros_deletados=self.registros_deletados,
            strays_descartados=self.strays_descartados,
            duplicatas_ignoradas=self.duplicatas_ignoradas,
            inconsistencias=self.inconsistencias,
            motivo_rejeicao=self.motivo_rejeicao,
            erro=self.erro,
        )


class RejectionError(Exception):
    """Arquivo rejeitado por regra de negócio."""
    pass


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _normalize_col(name: str) -> str:
    """Normaliza nome de coluna para MongoDB-friendly (sem acentos, snake_case)."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ASCII", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _last_business_day(year: int, month: int) -> datetime:
    """Retorna o último dia útil (seg-sex) do mês."""
    import calendar
    last = datetime(year, month, calendar.monthrange(year, month)[1], tzinfo=_BRT)
    while last.weekday() in (5, 6):  # sábado=5, domingo=6
        last -= timedelta(days=1)
    return last


def _month_label(mes_referencia: str) -> str:
    """Converte '2026-01' → 'Jan/2026'."""
    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    year, month = mes_referencia.split("-")
    return f"{meses[int(month) - 1]}/{year}"


def _prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


# ---------------------------------------------------------------------------
# Etapa 4 — Cálculo do mês de referência
# ---------------------------------------------------------------------------

def _calc_mes_referencia(df: pd.DataFrame, tipo: str, today: datetime) -> str:
    """
    Calcula o mês de referência para o canal padrão (SP-02).
    Lança RejectionError se multi-mês (R1) ou fora do alcance (R3).
    """
    campo = config.get_reference_field(tipo)

    if campo not in df.columns:
        raise RejectionError(
            f"Arquivo rejeitado: campo de referência '{campo}' não encontrado nas colunas."
        )

    if today.day != 1:
        return f"{today.year}-{today.month:02d}"

    # Janela de tolerância: dia 1 do mês
    dates = df[campo].dropna()
    if dates.empty:
        raise RejectionError(
            f"Arquivo rejeitado: nenhum valor válido no campo '{campo}'."
        )

    month_counts = dates.apply(
        lambda d: f"{d.year}-{d.month:02d}" if hasattr(d, "year") else None
    ).value_counts()

    total = month_counts.sum()
    dominant = month_counts.index[0]
    ratio = month_counts.iloc[0] / total

    if ratio < config.MIN_REFERENCE_MONTH_RATIO if hasattr(config, "MIN_REFERENCE_MONTH_RATIO") else 0.80:
        dist = " | ".join(
            f"{_month_label(m)} ({(c/total*100):.0f}%)"
            for m, c in month_counts.items()
        )
        raise RejectionError(
            f"Arquivo rejeitado: apenas {ratio*100:.0f}% dos registros pertencem ao mês "
            f"dominante {_month_label(dominant)} (mínimo: 80%). "
            f"Verifique o período exportado no SAP ou use o canal retroativo.\n"
            f"Distribuição detectada: {dist}"
        )

    mes_atual = f"{today.year}-{today.month:02d}"
    prev_y, prev_m = _prev_month(today.year, today.month)
    mes_anterior = f"{prev_y}-{prev_m:02d}"

    if dominant == mes_anterior:
        return mes_anterior
    if dominant == mes_atual:
        return mes_atual

    raise RejectionError(
        f"Arquivo rejeitado: mês dominante ({_month_label(dominant)}) não é o mês "
        f"imediatamente anterior. Fora do alcance da janela de tolerância."
    )


# ---------------------------------------------------------------------------
# Etapa 5 — Validações de rejeição
# ---------------------------------------------------------------------------

def _validate(df: pd.DataFrame, tipo: str, mes_referencia: str,
              canal: str, today: datetime) -> None:
    """
    Executa as 5 validações de rejeição em ordem (SP-03).
    R1 e R2 já foram verificados antes de chegar aqui (no cálculo do mês).
    """
    campo = config.get_reference_field(tipo)

    # R2 — Ausência total do mês de referência
    registros_do_mes = df[df[campo].apply(
        lambda d: hasattr(d, "year") and f"{d.year}-{d.month:02d}" == mes_referencia
    )]
    if registros_do_mes.empty:
        raise RejectionError(
            f"Arquivo rejeitado: nenhum registro pertence ao mês de referência "
            f"{_month_label(mes_referencia)}. Verifique o período exportado."
        )

    if today.day == 1 and canal == "padrao":
        prev_y, prev_m = _prev_month(today.year, today.month)
        mes_anterior = f"{prev_y}-{prev_m:02d}"

        # R3 — já validado no cálculo do mês (dominante fora do alcance)

        # R4 — Dados incompletos na janela de tolerância
        if mes_referencia == mes_anterior:
            ultimo_dia_util = _last_business_day(prev_y, prev_m)
            max_date = registros_do_mes[campo].dropna().max()
            if hasattr(max_date, "date") and max_date.date() < ultimo_dia_util.date():
                raise RejectionError(
                    f"Arquivo rejeitado: dados de {_month_label(mes_referencia)} não cobrem "
                    f"o fim do mês (último registro: {max_date.strftime('%d/%m/%Y')}, "
                    f"esperado até {ultimo_dia_util.strftime('%d/%m/%Y')}). "
                    f"Para dados parciais, use o canal retroativo."
                )

    # R5 — Bloqueio retroativo no canal padrão
    if canal == "padrao":
        mes_atual = f"{today.year}-{today.month:02d}"
        prev_y, prev_m = _prev_month(today.year, today.month)
        meses_aceitos = [mes_atual]
        if today.day == 1:
            meses_aceitos.append(f"{prev_y}-{prev_m:02d}")

        if mes_referencia not in meses_aceitos:
            raise RejectionError(
                f"Arquivo rejeitado: o canal padrão não permite sobrescrever dados de "
                f"{_month_label(mes_referencia)}. Meses anteriores ao período aceito só "
                f"podem ser corrigidos pelo canal retroativo (nível 3+)."
            )


# ---------------------------------------------------------------------------
# Etapa 6 — Filtragem de strays
# ---------------------------------------------------------------------------

def _filter_strays(df: pd.DataFrame, tipo: str, mes_referencia: str) -> tuple[pd.DataFrame, list]:
    """
    Remove registros fora do mes_referencia (SP-04).
    Retorna (df_válido, strays_log).
    """
    campo = config.get_reference_field(tipo)

    def mes_de(d):
        if hasattr(d, "year"):
            return f"{d.year}-{d.month:02d}"
        return None

    mask = df[campo].apply(lambda d: mes_de(d) == mes_referencia)
    df_valid = df[mask].copy()
    df_strays = df[~mask]

    strays_log = []
    if not df_strays.empty:
        contagem = df_strays[campo].apply(mes_de).value_counts()
        for mes, qtd in contagem.items():
            if mes:
                label = _month_label(mes)
                logger.info(f"  {qtd} dado(s) descartado(s) de {label}")
                strays_log.append({"mes": label, "quantidade": int(qtd)})

    return df_valid, strays_log


# ---------------------------------------------------------------------------
# Etapa 7 — Preparação do DataFrame
# ---------------------------------------------------------------------------

def _prepare_df(df: pd.DataFrame, mes_referencia: str) -> list[dict]:
    """Normaliza colunas, converte tipos e adiciona mes_referencia."""
    from datetime import time as dt_time
    df = df.copy()
    df.columns = [_normalize_col(c) for c in df.columns]

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].apply(lambda x:
                x.strftime("%H:%M:%S") if isinstance(x, dt_time)
                else str(x) if isinstance(x, timedelta)
                else x
            )
        elif str(df[col].dtype) == "timedelta64[ns]":
            df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else None)
        elif str(df[col].dtype) == "datetime64[ns]":
            df[col] = df[col].apply(lambda x: x.to_pydatetime() if pd.notna(x) else None)

    df = df.where(pd.notna(df), None)
    df["mes_referencia"] = mes_referencia
    df["_processed"] = True
    return df.to_dict("records")


# ---------------------------------------------------------------------------
# Etapa 9 — Substituição atômica
# ---------------------------------------------------------------------------

_UNIQUE_KEYS = {
    "zppprd":      ("pto_trab", "ordem", "mes_referencia"),
    "zppparadas":  ("centro_de_trabalho", "ordem", "inicio_real_hora", "causa_do_desvio"),
}


def _dedup_records(records: list[dict], tipo: str) -> tuple[list[dict], int]:
    """Remove duplicatas dentro do próprio batch, mantendo última ocorrência."""
    key_fields = _UNIQUE_KEYS.get(tipo)
    if not key_fields:
        return records, 0
    seen: dict = {}
    for rec in records:
        k = tuple(rec.get(f) for f in key_fields)
        seen[k] = rec
    deduped = list(seen.values())
    return deduped, len(records) - len(deduped)


def _legacy_date_filter(mes_referencia: str, tipo: str) -> dict:
    """
    Filtro de data para deletar registros legados (sem mes_referencia) do mesmo mês.
    Usa o campo de âncora do MONTH_BOUNDARY_RULE para identificar o mês.
    """
    import calendar
    year, month = int(mes_referencia[:4]), int(mes_referencia[5:7])
    start = datetime(year, month, 1, tzinfo=_BRT)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59, tzinfo=_BRT)
    date_field = config.get_reference_field(tipo)
    return {
        "mes_referencia": {"$exists": False},
        date_field: {"$gte": start.replace(tzinfo=None), "$lte": end.replace(tzinfo=None)},
    }


def _substitute_atomic(client: MongoClient, db_name: str, collection_name: str,
                        records: list[dict], mes_referencia: str,
                        batch_size: int, tipo: str) -> tuple[int, int, int]:
    """
    Delete + insert em transaction MongoDB (SP-05).
    Apaga tanto registros novos (por mes_referencia) quanto legados (por range de data)
    para evitar duplicação durante a migração do pipeline antigo para o novo.
    Retorna (inseridos, deletados, duplicatas_ignoradas).
    """
    records, duplicatas = _dedup_records(records, tipo)
    if duplicatas:
        logger.warning(f"  {duplicatas} duplicata(s) removida(s) antes da inserção")

    db = client[db_name]
    collection = db[collection_name]

    legacy_filter = _legacy_date_filter(mes_referencia, tipo)
    deletados_novos = collection.count_documents({"mes_referencia": mes_referencia})
    deletados_legados = collection.count_documents(legacy_filter)
    deletados = deletados_novos + deletados_legados

    if deletados_legados:
        logger.info(f"  {deletados_legados} registro(s) legado(s) sem mes_referencia serão removidos")

    if deletados > 0 and len(records) < deletados:
        pct = (1 - len(records) / deletados) * 100
        logger.warning(
            f"  Atenção: arquivo contém {len(records)} registros; "
            f"substituindo {deletados} existentes (redução de {pct:.0f}%)."
        )

    inseridos = 0

    with client.start_session() as session:
        with session.start_transaction():
            collection.delete_many({"mes_referencia": mes_referencia}, session=session)
            collection.delete_many(legacy_filter, session=session)
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                result = collection.insert_many(batch, session=session)
                inseridos += len(result.inserted_ids)

    return inseridos, deletados, duplicatas


# ---------------------------------------------------------------------------
# Etapa 10 — Detecção de sobreposições (ZPP_Paradas)
# ---------------------------------------------------------------------------

def _detect_overlaps(records: list[dict]) -> list[dict]:
    """
    Detecta sobreposições de janelas em ZPP_Paradas (SP-07).
    Retorna lista de inconsistências.
    """
    from collections import defaultdict
    inconsistencias = []
    grupos = defaultdict(list)

    for r in records:
        ct = r.get("centro_de_trabalho")
        ordem = r.get("ordem")
        if ct and ordem:
            grupos[(ct, ordem)].append(r)

    for (ct, ordem), regs in grupos.items():
        if len(regs) < 2:
            continue
        for i in range(len(regs)):
            for j in range(i + 1, len(regs)):
                a, b = regs[i], regs[j]
                ini_a = a.get("inicio_execucao")
                fim_a = a.get("fim_execucao")
                ini_b = b.get("inicio_execucao")
                fim_b = b.get("fim_execucao")
                causa_a = a.get("causa_do_desvio")
                causa_b = b.get("causa_do_desvio")

                if not all([ini_a, fim_a, ini_b, fim_b]):
                    continue
                if causa_a == causa_b:
                    continue

                overlap = min(fim_a, fim_b) - max(ini_a, ini_b)
                if hasattr(overlap, "total_seconds") and overlap.total_seconds() > 0:
                    minutos = int(overlap.total_seconds() / 60)
                    inc = {
                        "equipamento": ct,
                        "ordem": ordem,
                        "registro_a": {"inicio": str(ini_a), "fim": str(fim_a), "causa": str(causa_a)},
                        "registro_b": {"inicio": str(ini_b), "fim": str(fim_b), "causa": str(causa_b)},
                        "sobreposicao_min": minutos,
                    }
                    inconsistencias.append(inc)
                    logger.warning(
                        f"  INCONSISTÊNCIA: sobreposição de janelas — "
                        f"{ct} | Ordem: {ordem} | {minutos} min"
                    )

    return inconsistencias


# ---------------------------------------------------------------------------
# Criação de índices
# ---------------------------------------------------------------------------

def ensure_indexes(db, collection_name: str, tipo: str) -> None:
    from pymongo.errors import DuplicateKeyError, OperationFailure

    def _safe_create(col, keys, **kwargs):
        try:
            col.create_index(keys, **kwargs)
        except (DuplicateKeyError, OperationFailure) as e:
            logger.warning(f"  Índice {kwargs.get('name')} não criado (dados legados): {e}")

    collection = db[collection_name]

    if tipo == "zppprd":
        _safe_create(collection,
            [("pto_trab", ASCENDING), ("ordem", ASCENDING), ("mes_referencia", ASCENDING)],
            name="idx_unique_producao", unique=True, sparse=True
        )
        _safe_create(collection, "mes_referencia", name="idx_mes_ref")
        _safe_create(collection,
            [("pto_trab", ASCENDING), ("fininotif", DESCENDING)],
            name="idx_equipamento_data"
        )
        _safe_create(collection,
            [("fininotif", ASCENDING), ("ffinnotif", ASCENDING)],
            name="idx_range_datas"
        )
    else:
        _safe_create(collection,
            [("centro_de_trabalho", ASCENDING), ("ordem", ASCENDING),
             ("inicio_real_hora", ASCENDING), ("causa_do_desvio", ASCENDING)],
            name="idx_unique_paradas", unique=True, sparse=True
        )
        _safe_create(collection, "mes_referencia", name="idx_mes_ref")
        _safe_create(collection,
            [("centro_de_trabalho", ASCENDING), ("inicio_execucao", DESCENDING)],
            name="idx_linha_data"
        )
        _safe_create(collection,
            [("inicio_execucao", ASCENDING), ("fim_execucao", ASCENDING)],
            name="idx_range_datas"
        )
        _safe_create(collection, "causa_do_desvio", name="idx_motivo")
        _safe_create(collection, [("duration_min", DESCENDING)], name="idx_duracao")


# ---------------------------------------------------------------------------
# Função pública principal
# ---------------------------------------------------------------------------

def process_file(
    file_path: Path,
    client: MongoClient,
    canal: str,
    operador: str,
    mes_referencia_override: str | None = None,
    justificativa: str | None = None,
) -> ProcessResult:
    """
    Executa o pipeline completo para um arquivo Excel.

    canal: "padrao" | "retroativo"
    mes_referencia_override: obrigatório se canal == "retroativo"
    """
    iniciado_em = datetime.now(tz=_BRT)
    arquivo = file_path.name
    tipo = ""
    mes_referencia = mes_referencia_override or ""

    try:
        # Etapa 1 — Detecção de tipo
        tipo = detect_file_type(str(file_path))
        collection_name = "ZPP_Producao" if tipo == "zppprd" else "ZPP_Paradas"

        # Etapa 2 — Limpeza de totalizadoras
        cleaner = ZPPCleaner(str(file_path), tipo)
        cleaner.load_data()
        df = cleaner.get_cleaned_dataframe()

        # Normalizar colunas aqui para que etapas 3-7 usem nomes snake_case consistentes
        df.columns = [_normalize_col(c) for c in df.columns]

        # Etapa 3 — Filtro EMBAL (antes do threshold)
        equip_col = "pto_trab" if tipo == "zppprd" else "centro_de_trabalho"
        if equip_col in df.columns:
            mask = ~df[equip_col].astype(str).str.upper().str.startswith(_IGNORE_PREFIXES)
            removidos = (~mask).sum()
            df = df[mask]
            if removidos:
                logger.info(f"  {removidos} registros EMBAL removidos")

        # Etapa 4 — Cálculo do mês de referência
        today = datetime.now(tz=_BRT)
        if canal == "retroativo":
            if not mes_referencia_override:
                raise ValueError("mes_referencia_override obrigatório no canal retroativo")
            mes_referencia = mes_referencia_override
        else:
            mes_referencia = _calc_mes_referencia(df, tipo, today)

        # Etapa 5 — Validações de rejeição
        _validate(df, tipo, mes_referencia, canal, today)

        # Etapa 6 — Filtragem de strays
        df, strays_log = _filter_strays(df, tipo, mes_referencia)

        # Etapa 7 — Preparação do DataFrame
        records = _prepare_df(df, mes_referencia)

        # Etapa 8 — Lock + Etapa 9 — Substituição atômica
        with acquire_lock(tipo):
            inseridos, deletados, duplicatas = _substitute_atomic(
                client, config.DB_NAME, collection_name,
                records, mes_referencia, config.BATCH_SIZE, tipo
            )

        # Etapa 10 — Pós-processamento
        inconsistencias = []
        if tipo == "zppparadas":
            inconsistencias = _detect_overlaps(records)

        # Índices (idempotente)
        ensure_indexes(client[config.DB_NAME], collection_name, tipo)

        logger.info(
            f"  {arquivo} | success | {tipo} | {mes_referencia} | "
            f"ins={inseridos} del={deletados}"
        )

        return ProcessResult(
            arquivo=arquivo, tipo=tipo, canal=canal,
            operador=operador, justificativa=justificativa,
            mes_referencia=mes_referencia,
            iniciado_em=iniciado_em, finalizado_em=datetime.now(tz=_BRT),
            status="success",
            registros_inseridos=inseridos,
            registros_deletados=deletados,
            strays_descartados=strays_log,
            duplicatas_ignoradas=duplicatas,
            inconsistencias=inconsistencias,
        )

    except (RejectionError, UnknownFileTypeError) as e:
        motivo = str(e)
        logger.error(f"  {arquivo} | rejected | {motivo}")
        return ProcessResult(
            arquivo=arquivo, tipo=tipo, canal=canal,
            operador=operador, justificativa=justificativa,
            mes_referencia=mes_referencia,
            iniciado_em=iniciado_em, finalizado_em=datetime.now(tz=_BRT),
            status="rejected",
            motivo_rejeicao=motivo,
        )

    except LockActiveError as e:
        motivo = str(e)
        logger.warning(f"  {arquivo} | lock ativo | {motivo}")
        return ProcessResult(
            arquivo=arquivo, tipo=tipo, canal=canal,
            operador=operador, justificativa=justificativa,
            mes_referencia=mes_referencia,
            iniciado_em=iniciado_em, finalizado_em=datetime.now(tz=_BRT),
            status="rejected",
            motivo_rejeicao=motivo,
        )

    except Exception as e:
        erro = traceback.format_exc()
        logger.error(f"  {arquivo} | failed | {e}")
        return ProcessResult(
            arquivo=arquivo, tipo=tipo, canal=canal,
            operador=operador, justificativa=justificativa,
            mes_referencia=mes_referencia,
            iniciado_em=iniciado_em, finalizado_em=datetime.now(tz=_BRT),
            status="failed",
            erro=erro,
        )
