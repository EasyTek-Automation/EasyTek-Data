"""
Módulo para cálculo de KPIs de Manutenção baseado nas collections ZPP
Implementa indicadores M01 (MTBF), M02 (MTTR) e M03 (Taxa de Avaria)
conforme documento PRO017 - KPI Calculation Procedures

Collections utilizadas (FIXAS - não mudar dinamicamente):
- ZPP_Producao: Dados de produção (horas de atividade) - contém dados de múltiplos anos
- ZPP_Paradas: Dados de paradas (avarias) - contém dados de múltiplos anos

IMPORTANTE: Os nomes das collections são FIXOS.
O filtro por ano é feito nos DADOS, não no nome da collection.
NÃO modificar para usar nomes dinâmicos (ZPP_*_{year}).

Códigos de avaria considerados: 201, S201, 202, S202, 203, S203, 204, S204, 205, S205, 110, S110
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import logging
from src.database.connection import get_mongo_connection

logger = logging.getLogger(__name__)


# ==================== CONFIGURAÇÕES ====================

# NOMES FIXOS DAS COLLECTIONS ZPP
# IMPORTANTE: Não alterar para usar ano dinâmico!
# Estas collections contêm dados de MÚLTIPLOS anos.
# O filtro por ano é feito nos documentos, não no nome da collection.
ZPP_PRODUCAO_COLLECTION = "ZPP_Producao"
ZPP_PARADAS_COLLECTION = "ZPP_Paradas"

# Códigos de motivo que representam AVARIAS
BREAKDOWN_CODES = ['201', 'S201', '202', 'S202', '203', 'S203',
                   '204', 'S204', '205', 'S205', '110', 'S110']

# Mapeamento de categorias por prefixo de equipamento
EQUIPMENT_CATEGORY_PREFIXES = {
    "Longitudinais": ["LONGI"],
    "Prensas": ["PRENS"],
    "Transversais": ["TRANS"]
}

# ==================== FILTRO DE VIRADA DE MÊS ====================
# IMPORTANTE: Define como tratar registros que cruzam a virada do mês
#
# Problema: Registros com início em um mês e fim em outro
# Exemplo: Início 30/09 23:59 → Fim 01/10 00:50
#
# MONTH_BOUNDARY_RULE = "fim"     → Conta no mês onde FINALIZOU (padrão)
#                                    Exemplo acima = OUTUBRO
#
# MONTH_BOUNDARY_RULE = "inicio"  → Conta no mês onde COMEÇOU
#                                    Exemplo acima = SETEMBRO
#
# RECOMENDAÇÃO: Usar "fim" para produção e "inicio" para paradas
# ================================================================
MONTH_BOUNDARY_RULE = "fim"  # Opções: "fim" ou "inicio"


# ==================== FUNÇÕES DE BUSCA DE DADOS ====================

def _get_month_periods(start_date: datetime, end_date: datetime) -> List[tuple]:
    """
    Gera lista de (year, month) cobrindo todos os meses entre start_date e end_date.
    Suporta ranges que cruzam virada de ano (ex: Out/2025 → Fev/2026).
    """
    periods = []
    y, m = start_date.year, start_date.month
    end_y, end_m = end_date.year, end_date.month
    while (y, m) <= (end_y, end_m):
        periods.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return periods


def fetch_zpp_equipment_list(year: int = 2026) -> List[str]:
    """
    Busca lista única de equipamentos (linhas) das collections ZPP

    Args:
        year: Ano para buscar dados (padrão: 2026)
              NOTA: O parâmetro year é mantido para compatibilidade futura,
              mas atualmente as collections são FIXAS (ZPP_*_2025)

    Returns:
        List[str]: Lista de equipamentos únicos (ex: ["LONGI001", "LONGI002", ...])
    """
    try:
        logger.debug("Buscando lista de equipamentos (collections fixas: %s, %s)",
                    ZPP_PARADAS_COLLECTION, ZPP_PRODUCAO_COLLECTION)

        # IMPORTANTE: Usar constantes FIXAS, não f"ZPP_Paradas_{year}"
        # As collections sempre se chamam *_2025 mesmo contendo dados de outros anos
        paradas_collection = get_mongo_connection(ZPP_PARADAS_COLLECTION)
        producao_collection = get_mongo_connection(ZPP_PRODUCAO_COLLECTION)

        logger.debug("Collections conectadas com sucesso")

        # Buscar valores únicos do campo 'centro_de_trabalho' (paradas)
        equipment_from_paradas = set(paradas_collection.distinct("centro_de_trabalho"))
        logger.debug("Equipamentos em %s (campo 'centro_de_trabalho'): %d",
                    ZPP_PARADAS_COLLECTION, len(equipment_from_paradas))

        # Buscar valores únicos do campo 'pto_trab' (produção)
        equipment_from_producao = set(producao_collection.distinct("pto_trab"))
        logger.debug("Equipamentos em %s (campo 'pto_trab'): %d",
                    ZPP_PRODUCAO_COLLECTION, len(equipment_from_producao))

        # Combinar ambas as listas
        equipment_list = sorted(equipment_from_paradas | equipment_from_producao)
        logger.debug("Total combinado (antes de limpar): %d equipamentos", len(equipment_list))

        # Remover valores vazios ou None
        equipment_list = [eq for eq in equipment_list if eq]
        logger.debug("Lista final: %d equipamentos", len(equipment_list))

        if equipment_list:
            logger.debug("Equipamentos: %s", equipment_list)
        else:
            logger.warning(
                "Nenhum equipamento nas collections %s e %s",
                ZPP_PARADAS_COLLECTION, ZPP_PRODUCAO_COLLECTION
            )

        return equipment_list

    except Exception as e:
        logger.error(
            "Erro ao buscar lista de equipamentos: %s",
            str(e),
            exc_info=True
        )
        return []


def fetch_zpp_production_data(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Busca dados de produção da collection ZPP (nome fixo: ZPP_Producao)

    IMPORTANTE: Usa filtro INCLUSIVO para capturar registros que cruzam virada de mês
    - Busca registros onde INÍCIO ou FIM estejam no mês
    - Aplica regra de desempate conforme MONTH_BOUNDARY_RULE
    - Suporta ranges multi-ano (ex: Out/2025 → Fev/2026)

    Args:
        start_date: Data de início do período
        end_date: Data de fim do período

    Returns:
        DataFrame com colunas: [linea, date, year, month, year_month, horasact, boundary_case]
    """
    try:
        from calendar import monthrange

        # IMPORTANTE: Usar constante fixa, não nome dinâmico
        collection = get_mongo_connection(ZPP_PRODUCAO_COLLECTION)

        # Buscar TODOS os registros processados no range de datas solicitado
        query = {
            "_processed": True,
            "fininotif": {
                "$gte": start_date,
                "$lte": end_date
            }
        }

        # Buscar documentos com AMBAS as datas
        cursor = collection.find(
            query,
            {
                "pto_trab": 1,
                "fininotif": 1,  # Data de INÍCIO
                "ffinnotif": 1,  # Data de FIM
                "horasact": 1,
                "_id": 0
            }
        )

        records = list(cursor)

        if not records:
            return pd.DataFrame(columns=["linea", "date", "year", "month", "year_month", "horasact", "boundary_case"])

        # Processar dados com filtro INCLUSIVO
        processed_records = []
        boundary_count = 0  # Contador de registros na virada

        for record in records:
            # Extrair datas (IMPORTANTE: fininotif = INÍCIO, ffinnotif = FIM)
            inicio_obj = record.get("fininotif")  # Data de INÍCIO
            fim_obj = record.get("ffinnotif")     # Data de FIM

            # Precisamos de pelo menos uma data válida
            if not fim_obj and not inicio_obj:
                continue

            # Converter datas
            def parse_date(date_obj):
                if date_obj is None:
                    return None
                if isinstance(date_obj, dict) and "$date" in date_obj:
                    return datetime.fromisoformat(date_obj["$date"].replace('Z', '+00:00'))
                elif isinstance(date_obj, datetime):
                    return date_obj
                return None

            inicio = parse_date(inicio_obj)
            fim = parse_date(fim_obj)

            # Se não temos fim, usar início como fallback
            if not fim and inicio:
                fim = inicio
            elif not inicio and fim:
                inicio = fim
            elif not inicio and not fim:
                continue

            # Extrair equipamento
            linea = record.get("pto_trab")
            if not linea:
                linea = record.get("linea")
            if not linea:
                continue

            # Extrair horas
            horasact = record.get("horasact", 0)

            # FILTRO INCLUSIVO: Verificar se registro afeta algum dos meses no range
            for (target_year, target_month) in _get_month_periods(start_date, end_date):
                # Calcular início e fim do mês alvo
                first_day = datetime(target_year, target_month, 1)
                last_day = datetime(target_year, target_month, monthrange(target_year, target_month)[1], 23, 59, 59)

                # Verificar se registro intersecta com o mês
                # Casos:
                # 1. Completamente dentro do mês
                # 2. Começa antes e termina dentro
                # 3. Começa dentro e termina depois
                # 4. Começa antes e termina depois (atravessa o mês todo)

                intersects = False
                boundary_case = False

                # Registro intersecta se:
                # - início está no mês OU
                # - fim está no mês OU
                # - início antes e fim depois (atravessa o mês)
                if (first_day <= inicio <= last_day) or \
                   (first_day <= fim <= last_day) or \
                   (inicio < first_day and fim > last_day):
                    intersects = True

                if not intersects:
                    continue

                # Detectar se é caso de virada de mês (inclui virada de ano)
                if (inicio.year, inicio.month) != (fim.year, fim.month):
                    boundary_case = True
                    boundary_count += 1

                    # APLICAR REGRA DE DESEMPATE
                    if MONTH_BOUNDARY_RULE == "fim":
                        # Conta no mês onde FINALIZOU
                        if (fim.year, fim.month) != (target_year, target_month):
                            continue  # Pula este mês, será contado no mês do fim
                    elif MONTH_BOUNDARY_RULE == "inicio":
                        # Conta no mês onde COMEÇOU
                        if (inicio.year, inicio.month) != (target_year, target_month):
                            continue  # Pula este mês, será contado no mês do início
                    else:
                        # Fallback: usar fim (padrão)
                        if (fim.year, fim.month) != (target_year, target_month):
                            continue

                # Adicionar registro
                processed_records.append({
                    "linea": linea,
                    "date": fim.date(),
                    "year": target_year,
                    "month": target_month,
                    "year_month": f"{target_year}-{target_month:02d}",
                    "horasact": float(horasact),
                    "boundary_case": boundary_case
                })
                break  # Não contar o mesmo registro em múltiplos meses

        df = pd.DataFrame(processed_records)

        if boundary_count > 0:
            pass
        else:
            pass

        return df

    except Exception as e:
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=["linea", "date", "year", "month", "year_month", "horasact", "boundary_case"])


def fetch_zpp_breakdown_data(start_date: datetime, end_date: datetime,
                             breakdown_codes: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Busca dados de paradas (avarias) da collection ZPP (nome fixo: ZPP_Paradas)

    IMPORTANTE: Usa filtro INCLUSIVO para capturar registros que cruzam virada de mês
    - Busca registros onde INÍCIO ou FIM estejam no mês
    - Aplica regra de desempate conforme MONTH_BOUNDARY_RULE
    - Suporta ranges multi-ano (ex: Out/2025 → Fev/2026)

    Args:
        start_date: Data de início do período
        end_date: Data de fim do período
        breakdown_codes: Códigos de avaria a considerar (padrão: BREAKDOWN_CODES)

    Returns:
        DataFrame com colunas: [linea, date, year, month, year_month, motivo, duracao_min, boundary_case]
    """
    codes = breakdown_codes if breakdown_codes else BREAKDOWN_CODES
    try:
        from calendar import monthrange

        # IMPORTANTE: Usar constante fixa, não nome dinâmico
        collection = get_mongo_connection(ZPP_PARADAS_COLLECTION)

        # Buscar TODOS os registros processados no range de datas solicitado
        query = {
            "_processed": True,
            "causa_do_desvio": {"$in": codes},
            "inicio_execucao": {
                "$gte": start_date,
                "$lte": end_date
            }
        }

        # Buscar documentos com AMBAS as datas
        cursor = collection.find(
            query,
            {
                "centro_de_trabalho": 1,
                "inicio_execucao": 1,  # Início da parada
                "fim_execucao": 1,     # Fim da parada
                "causa_do_desvio": 1,
                "duration_min": 1,
                "_id": 0
            }
        )

        records = list(cursor)

        if not records:
            return pd.DataFrame(columns=["linea", "date", "year", "month", "year_month", "motivo", "duracao_min", "boundary_case"])

        # Processar dados com filtro INCLUSIVO
        processed_records = []
        boundary_count = 0

        for record in records:
            # Extrair datas
            inicio_obj = record.get("inicio_execucao")
            fim_obj = record.get("fim_execucao")

            if not inicio_obj and not fim_obj:
                continue

            # Converter datas
            def parse_date(date_obj):
                if date_obj is None:
                    return None
                if isinstance(date_obj, dict) and "$date" in date_obj:
                    return datetime.fromisoformat(date_obj["$date"].replace('Z', '+00:00'))
                elif isinstance(date_obj, datetime):
                    return date_obj
                return None

            inicio = parse_date(inicio_obj)
            fim = parse_date(fim_obj)

            # Se não temos fim, usar início
            if not fim and inicio:
                fim = inicio
            elif not inicio and fim:
                inicio = fim
            elif not inicio and not fim:
                continue

            # Extrair campos
            linea = record.get("centro_de_trabalho")
            motivo = record.get("causa_do_desvio")
            duracao_min = record.get("duration_min", 0)

            if not linea:
                continue

            # FILTRO INCLUSIVO por mês (suporta multi-ano)
            for (target_year, target_month) in _get_month_periods(start_date, end_date):
                first_day = datetime(target_year, target_month, 1)
                last_day = datetime(target_year, target_month, monthrange(target_year, target_month)[1], 23, 59, 59)

                # Verificar interseção
                intersects = False
                boundary_case = False

                if (first_day <= inicio <= last_day) or \
                   (first_day <= fim <= last_day) or \
                   (inicio < first_day and fim > last_day):
                    intersects = True

                if not intersects:
                    continue

                # Detectar virada de mês (inclui virada de ano)
                if (inicio.year, inicio.month) != (fim.year, fim.month):
                    boundary_case = True
                    boundary_count += 1

                    # APLICAR REGRA DE DESEMPATE
                    if MONTH_BOUNDARY_RULE == "fim":
                        if (fim.year, fim.month) != (target_year, target_month):
                            continue
                    elif MONTH_BOUNDARY_RULE == "inicio":
                        if (inicio.year, inicio.month) != (target_year, target_month):
                            continue
                    else:
                        if (fim.year, fim.month) != (target_year, target_month):
                            continue

                # Adicionar registro
                processed_records.append({
                    "linea": linea,
                    "date": inicio.date(),
                    "year": target_year,
                    "month": target_month,
                    "year_month": f"{target_year}-{target_month:02d}",
                    "motivo": motivo,
                    "duracao_min": float(duracao_min),
                    "boundary_case": boundary_case
                })
                break

        df = pd.DataFrame(processed_records)

        if boundary_count > 0:
            pass
        else:
            pass

        return df

    except Exception as e:
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=["linea", "date", "year", "month", "year_month", "motivo", "duracao_min", "boundary_case"])


# ==================== FUNÇÕES DE CÁLCULO DE KPIs ====================

def calculate_monthly_kpis(production_df: pd.DataFrame, breakdown_df: pd.DataFrame) -> Dict:
    """
    Calcula KPIs mensais por equipamento baseado nos dados de produção e paradas

    Implementa fórmulas do documento PRO017:
    - M01 (MTBF): (∑Horas Atividade - ∑Tempo Falha) / Número Falhas
    - M02 (MTTR): Minutos Paragem / Número Paragens (convertido para horas)
    - M03 (Taxa Avaria): (Tempo Paragem / Horas Atividade) × 100

    Args:
        production_df: DataFrame com dados de produção
        breakdown_df: DataFrame com dados de paradas

    Returns:
        dict: Estrutura {
            "LINEA001": [
                {"month": 1, "mtbf": 22.3, "mttr": 1.8, "breakdown_rate": 2.9},
                ...
            ],
            ...
        }
    """
    result = {}

    # Verificar se há dados
    if production_df.empty:
        return result

    # Obter lista de equipamentos e períodos únicos (year, month)
    equipment_list = production_df['linea'].unique()
    # Determinar períodos disponíveis a partir do DataFrame (preserva ordem cronológica)
    if 'year' in production_df.columns:
        periods = sorted(
            production_df[['year', 'month']].drop_duplicates().itertuples(index=False, name=None)
        )
    else:
        periods = [(None, m) for m in sorted(production_df['month'].unique())]

    for linea in equipment_list:
        monthly_data = []

        # Filtrar dados do equipamento
        prod_linea = production_df[production_df['linea'] == linea]
        breakdown_linea = breakdown_df[breakdown_df['linea'] == linea] if not breakdown_df.empty else breakdown_df

        for (target_year, month) in periods:
            # Filtrar dados do mês (por year+month se disponível)
            if target_year is not None and 'year' in prod_linea.columns:
                prod_month = prod_linea[(prod_linea['year'] == target_year) & (prod_linea['month'] == month)]
            else:
                prod_month = prod_linea[prod_linea['month'] == month]

            if target_year is not None and not breakdown_linea.empty and 'year' in breakdown_linea.columns:
                breakdown_month = breakdown_linea[(breakdown_linea['year'] == target_year) & (breakdown_linea['month'] == month)]
            elif not breakdown_linea.empty:
                breakdown_month = breakdown_linea[breakdown_linea['month'] == month]
            else:
                breakdown_month = breakdown_linea

            # Calcular agregações
            total_active_hours = prod_month['horasact'].sum()

            if breakdown_month.empty:
                # Sem paradas no mês
                num_failures = 0
                total_breakdown_minutes = 0
            else:
                num_failures = len(breakdown_month)
                total_breakdown_minutes = breakdown_month['duracao_min'].sum()

            total_breakdown_hours = total_breakdown_minutes / 60.0

            # Calcular KPIs
            if total_active_hours > 0:
                # M01 - MTBF (horas)
                if num_failures > 0:
                    mtbf = (total_active_hours - total_breakdown_hours) / num_failures
                else:
                    # Sem falhas = usar tempo total de produção como MTBF
                    # Lógica: se produziu X horas sem falhar, o tempo entre falhas é X
                    mtbf = total_active_hours

                # M02 - MTTR (horas)
                if num_failures > 0:
                    mttr = total_breakdown_hours / num_failures
                else:
                    mttr = 0.0

                # M03 - Taxa de Avaria (%)
                breakdown_rate = (total_breakdown_hours / total_active_hours) * 100
            else:
                # Sem horas de atividade = não calcular KPIs
                mtbf = None
                mttr = None
                breakdown_rate = None

            monthly_data.append({
                "year": target_year,
                "month": month,
                "year_month": f"{target_year}-{month:02d}" if target_year is not None else f"????-{month:02d}",
                "num_failures": int(num_failures),
                "num_orders": int(len(prod_month)),
                "total_active_hours": round(total_active_hours, 4),
                "total_breakdown_minutes": round(total_breakdown_minutes, 4),
                "total_breakdown_hours": round(total_breakdown_hours, 4),
                "uptime_hours": round(max(total_active_hours - total_breakdown_hours, 0), 4),
                "mtbf": round(mtbf, 2) if mtbf is not None else None,
                "mttr": round(mttr, 2) if mttr is not None else None,
                "breakdown_rate": round(breakdown_rate, 2) if breakdown_rate is not None else None
            })

        result[linea] = monthly_data

    return result


# ==================== COBERTURA DE DADOS ====================

def get_zpp_data_coverage(start_date: datetime, end_date: datetime,
                          breakdown_codes: Optional[List[str]] = None) -> dict:
    """
    Retorna metadados de cobertura dos dados ZPP para o período selecionado.

    Consulta as duas collections e retorna:
    - Último dia com registro (ffinnotif em ZPP_Producao, fim_execucao em ZPP_Paradas)
    - Quantidade de dias distintos com registros dentro do período
    - Suporta ranges multi-ano (ex: Out/2025 → Fev/2026)

    Args:
        start_date: Data de início do período
        end_date: Data de fim do período
        breakdown_codes: Códigos de avaria a considerar (padrão: BREAKDOWN_CODES)

    Returns:
        dict: {prod_last_date, prod_num_days, paradas_last_date, paradas_num_days}
    """
    result = {
        "prod_last_date": None,
        "prod_num_days": 0,
        "paradas_last_date": None,
        "paradas_num_days": 0,
    }

    def _parse(d):
        if d is None:
            return None
        if isinstance(d, dict) and "$date" in d:
            return datetime.fromisoformat(d["$date"].replace('Z', '+00:00'))
        if isinstance(d, datetime):
            return d
        return None

    try:
        start_date_naive = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
        end_date_naive = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date

        # ── ZPP_Producao ──────────────────────────────────────────────
        prod_coll = get_mongo_connection(ZPP_PRODUCAO_COLLECTION)
        prod_docs = list(prod_coll.find(
            {"_processed": True, "fininotif": {"$gte": start_date_naive, "$lte": end_date_naive}},
            {"ffinnotif": 1, "_id": 0}
        ))

        prod_days = set()
        for doc in prod_docs:
            d = _parse(doc.get("ffinnotif"))
            if d:
                d_naive = d.replace(tzinfo=None) if d.tzinfo else d
                if start_date_naive.date() <= d_naive.date() <= end_date_naive.date():
                    prod_days.add(d_naive.date())

        if prod_days:
            result["prod_last_date"] = max(prod_days).strftime("%d/%m/%Y")
            result["prod_num_days"] = len(prod_days)

        # ── ZPP_Paradas ───────────────────────────────────────────────
        codes = breakdown_codes if breakdown_codes else BREAKDOWN_CODES
        paradas_coll = get_mongo_connection(ZPP_PARADAS_COLLECTION)
        paradas_docs = list(paradas_coll.find(
            {
                "_processed": True,
                "causa_do_desvio": {"$in": codes},
                "inicio_execucao": {"$gte": start_date_naive, "$lte": end_date_naive}
            },
            {"fim_execucao": 1, "inicio_execucao": 1, "_id": 0}
        ))

        paradas_days = set()
        for doc in paradas_docs:
            d = _parse(doc.get("fim_execucao")) or _parse(doc.get("inicio_execucao"))
            if d:
                d_naive = d.replace(tzinfo=None) if d.tzinfo else d
                if start_date_naive.date() <= d_naive.date() <= end_date_naive.date():
                    paradas_days.add(d_naive.date())

        if paradas_days:
            result["paradas_last_date"] = max(paradas_days).strftime("%d/%m/%Y")
            result["paradas_num_days"] = len(paradas_days)

    except Exception as e:
        logger.error("Erro ao buscar cobertura ZPP: %s", e)

    return result


# ==================== FUNÇÃO PRINCIPAL ====================

def fetch_zpp_kpi_data(start_date: datetime, end_date: datetime,
                       breakdown_codes: Optional[List[str]] = None) -> Dict:
    """
    Função principal: busca dados do MongoDB e calcula KPIs

    Args:
        start_date: Data de início do período
        end_date: Data de fim do período
        breakdown_codes: Códigos de avaria a considerar (padrão: BREAKDOWN_CODES)

    Returns:
        dict: Dados de KPIs no formato esperado pelos callbacks

    Raises:
        Exception: Se houver erro ao buscar ou processar dados
    """

    try:
        # 1. Buscar dados de produção
        production_df = fetch_zpp_production_data(start_date, end_date)

        # 2. Buscar dados de paradas (com filtro de códigos selecionados)
        breakdown_df = fetch_zpp_breakdown_data(start_date, end_date, breakdown_codes=breakdown_codes)

        # 3. Calcular KPIs
        kpi_data = calculate_monthly_kpis(production_df, breakdown_df)

        if not kpi_data:
            raise Exception("Nenhum dado de KPI foi calculado (sem dados de produção)")

        return kpi_data

    except Exception as e:
        raise


# ==================== FUNÇÕES AUXILIARES ====================

def get_zpp_equipment_categories() -> Dict[str, List[str]]:
    """
    Retorna categorias de equipamentos baseado nos prefixos

    Returns:
        dict: {
            "Longitudinais": ["LONGI001", "LONGI002"],
            "Prensas": ["PRENS001", ...],
            ...
        }
    """
    try:
        logger.debug("Iniciando categorização de equipamentos")

        equipment_list = fetch_zpp_equipment_list()
        logger.debug("Equipamentos encontrados: %d total", len(equipment_list))
        logger.debug("Lista: %s", equipment_list)

        categories = {}

        # Log dos prefixos configurados
        logger.debug("Prefixos configurados: %s", EQUIPMENT_CATEGORY_PREFIXES)

        for category_name, prefixes in EQUIPMENT_CATEGORY_PREFIXES.items():
            # Filtrar equipamentos que começam com algum dos prefixos
            category_equipment = [
                eq for eq in equipment_list
                if any(eq.startswith(prefix) for prefix in prefixes)
            ]

            if category_equipment:
                categories[category_name] = category_equipment
                logger.debug(
                    "Categoria '%s': %d equipamentos (%s)",
                    category_name,
                    len(category_equipment),
                    ", ".join(category_equipment)
                )
            else:
                logger.debug(
                    "Categoria '%s' (prefixos %s): nenhum equipamento",
                    category_name, prefixes
                )

        # Adicionar categoria "Outros" para equipamentos não categorizados
        categorized = [eq for cat_list in categories.values() for eq in cat_list]
        others = [eq for eq in equipment_list if eq not in categorized]
        if others:
            categories["Outros"] = others
            logger.debug(
                "Categoria 'Outros': %d não categorizados (%s)",
                len(others), ", ".join(others)
            )

        # Log do resultado final
        total_categorized = sum(len(eqs) for eqs in categories.values())
        logger.info(
            "Categorização concluída: %d categorias, %d equipamentos",
            len(categories), total_categorized
        )

        if not categories:
            logger.warning("Nenhuma categoria criada - lista de equipamentos vazia")

        return categories

    except Exception as e:
        logger.error(
            "Erro ao categorizar equipamentos: %s",
            str(e),
            exc_info=True
        )
        return {}


def get_zpp_equipment_names() -> Dict[str, str]:
    """
    Retorna dicionário de equipamentos {id: nome_amigavel}

    Returns:
        dict: {"LONGI001": "Longitudinal 001", ...}
    """
    # Mapeamento manual de nomes customizados (opcional)
    # Se um equipamento estiver neste dicionário, usa o nome customizado
    # Caso contrário, gera automaticamente baseado no prefixo
    CUSTOM_NAMES = {
        "LONGI001": "LCL-08",
        "LONGI002": "LCL-4,5",
        "PRENS001": "PRENSA-01",
        "PRENS002": "PRENSA-02",
        "TRANS001": "LCT-08",
        "TRANS002": "LCT-16",
        "TRANS003": "LCT-2,5"
        }

    try:
        equipment_list = fetch_zpp_equipment_list()


        # Criar nomes amigáveis
        names = {}
        for eq_id in equipment_list:
            # Verificar se há nome customizado
            if eq_id in CUSTOM_NAMES:
                names[eq_id] = CUSTOM_NAMES[eq_id]
            else:
                # Gerar nome automaticamente baseado no prefixo
                if eq_id.startswith("LONGI"):
                    tipo = "Longitudinal"  # ← CUSTOMIZÁVEL
                    numero = eq_id.replace("LONGI", "")
                elif eq_id.startswith("PRENS"):
                    tipo = "Prensa"  # ← CUSTOMIZÁVEL
                    numero = eq_id.replace("PRENS", "")
                elif eq_id.startswith("TRANS"):
                    tipo = "Transversal"  # ← CUSTOMIZÁVEL
                    numero = eq_id.replace("TRANS", "")
                else:
                    tipo = "Equipamento"
                    numero = eq_id

                names[eq_id] = f"{tipo} {numero}"

        return names

    except Exception as e:
        return {}


# ==================== FUNÇÃO DE TESTE ====================

def fetch_top_breakdowns_by_equipment(equipment_id: str,
                                      start_date: datetime, end_date: datetime,
                                      top_n: int = 10,
                                      breakdown_codes: Optional[List[str]] = None) -> List[Dict]:
    """
    Busca as N paradas com maior duração para um equipamento específico

    Args:
        equipment_id: ID do equipamento (ex: "LONGI001")
        start_date: Data de início do período
        end_date: Data de fim do período
        top_n: Número de paradas a retornar (padrão: 10)
        breakdown_codes: Códigos de avaria a considerar (padrão: BREAKDOWN_CODES)

    Returns:
        Lista de dicionários ordenada por duração (maior para menor):
        [
            {
                "date": datetime.date(2025, 1, 15),
                "motivo": "201",
                "duracao_min": 120.5,
                "duracao_horas": 2.01,
                "descricao": "Troca de referência e bobina"
            },
            ...
        ]
    """
    codes = breakdown_codes if breakdown_codes else BREAKDOWN_CODES
    try:
        # IMPORTANTE: Usar constante fixa, não nome dinâmico
        collection = get_mongo_connection(ZPP_PARADAS_COLLECTION)

        # Construir pipeline de agregação usando range de datas direto
        pipeline = [
            # Stage 1: Filtrar por equipamento, range de datas, códigos de parada
            {
                "$match": {
                    "_processed": True,
                    "centro_de_trabalho": equipment_id,
                    "causa_do_desvio": {"$in": codes},
                    "inicio_execucao": {
                        "$gte": start_date,
                        "$lte": end_date,
                        "$exists": True
                    }
                }
            },
            # Stage 2: Ordenar por duração (maior para menor)
            {
                "$sort": {"duration_min": -1}
            },
            # Stage 3: Limitar ao top_n
            {
                "$limit": top_n
            },
            # Stage 4: Projetar apenas os campos necessários
            {
                "$project": {
                    "inicio_execucao": 1,
                    "causa_do_desvio": 1,
                    "duration_min": 1,
                    "descricao": 1,
                    "texto_de_confirmacao": 1,
                    "_id": 0
                }
            }
        ]

        # Executar pipeline
        cursor = collection.aggregate(pipeline)

        # Processar dados
        result = []
        for record in cursor:
            # Extrair data
            date_obj = record.get("inicio_execucao")
            if date_obj is None:
                continue

            # Converter para datetime se necessário
            if isinstance(date_obj, dict) and "$date" in date_obj:
                date_str = date_obj["$date"]
                date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            elif isinstance(date_obj, datetime):
                date = date_obj
            else:
                continue

            motivo = record.get("causa_do_desvio", "")
            duracao_min = record.get("duration_min", 0)

            # ✅ USAR TEXTO DE CONFIRMAÇÃO COMO PRIORIDADE
            descricao = record.get("texto_de_confirmacao", record.get("descricao", f"Motivo {motivo}"))

            result.append({
                "date": date.date(),
                "motivo": motivo,
                "duracao_min": float(duracao_min),
                "duracao_horas": round(duracao_min / 60.0, 2),
                "descricao": descricao  # ✅ DESCRIÇÃO DA PARADA
            })

        return result

    except Exception as e:
        return []


if __name__ == "__main__":
    """Script de teste para validar cálculos"""

    # Testar busca de equipamentos
    equipments = fetch_zpp_equipment_list()

    # Testar busca de categorias
    categories = get_zpp_equipment_categories()
    for cat, eqs in categories.items():
        pass

    # Testar busca de dados e cálculo de KPIs
    try:
        # Exemplo de uso: Jan–Mar 2025 (apenas para teste manual)
        # Em produção, start_date/end_date vêm do filtro selecionado pelo usuário
        kpi_data = fetch_zpp_kpi_data(datetime(2025, 1, 1), datetime(2025, 3, 31, 23, 59, 59))

        # Mostrar exemplo de resultado
        if kpi_data:
            first_equipment = list(kpi_data.keys())[0]
            for month_data in kpi_data[first_equipment]:
                pass

    except Exception as e:
        pass

