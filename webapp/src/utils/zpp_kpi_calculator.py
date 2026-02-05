"""
Módulo para cálculo de KPIs de Manutenção baseado nas collections ZPP
Implementa indicadores M01 (MTBF), M02 (MTTR) e M03 (Taxa de Avaria)
conforme documento PRO017 - KPI Calculation Procedures

Collections utilizadas:
- ZPP_Producao_2025: Dados de produção (horas de atividade)
- ZPP_Paradas_2025: Dados de paradas (avarias)

Códigos de avaria considerados: 201, S201, 202, S202, 203, S203
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from src.database.connection import get_mongo_connection


# ==================== CONFIGURAÇÕES ====================

# Códigos de motivo que representam AVARIAS
BREAKDOWN_CODES = ['201', 'S201', '202', 'S202', '203', 'S203']

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

def fetch_zpp_equipment_list() -> List[str]:
    """
    Busca lista única de equipamentos (linhas) das collections ZPP

    Returns:
        List[str]: Lista de equipamentos únicos (ex: ["LONGI001", "LONGI002", ...])
    """
    try:
        # Buscar de ambas as collections para garantir lista completa
        paradas_collection = get_mongo_connection("ZPP_Paradas_2025")
        producao_collection = get_mongo_connection("ZPP_Producao_2025")

        # Buscar valores únicos do campo 'linea' (paradas)
        equipment_from_paradas = set(paradas_collection.distinct("linea"))

        # Buscar valores únicos do campo 'pto_trab' (produção)
        equipment_from_producao = set(producao_collection.distinct("pto_trab"))

        # Combinar ambas as listas
        equipment_list = sorted(equipment_from_paradas | equipment_from_producao)

        # Remover valores vazios ou None
        equipment_list = [eq for eq in equipment_list if eq]

        print(f"[ZPP] {len(equipment_list)} equipamentos encontrados: {equipment_list}")
        return equipment_list

    except Exception as e:
        print(f"[ERRO] Falha ao buscar lista de equipamentos: {e}")
        return []


def fetch_zpp_production_data(year: int, months: List[int]) -> pd.DataFrame:
    """
    Busca dados de produção da collection ZPP_Producao_2025

    IMPORTANTE: Usa filtro INCLUSIVO para capturar registros que cruzam virada de mês
    - Busca registros onde INÍCIO ou FIM estejam no mês
    - Aplica regra de desempate conforme MONTH_BOUNDARY_RULE

    Args:
        year: Ano de referência (ex: 2025)
        months: Lista de meses (ex: [1, 2, 3] para Jan-Mar)

    Returns:
        DataFrame com colunas: [linea, date, month, horasact, boundary_case]
    """
    try:
        from calendar import monthrange

        collection = get_mongo_connection("ZPP_Producao_2025")

        # Buscar TODOS os registros processados do ano
        # Vamos filtrar por mês depois (para aplicar regra inclusiva)
        query = {
            "_year": year,
            "_processed": True
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
            print(f"[AVISO] Nenhum dado de producao encontrado para {year}")
            return pd.DataFrame(columns=["linea", "date", "month", "horasact", "boundary_case"])

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

            # FILTRO INCLUSIVO: Verificar se registro afeta algum dos meses solicitados
            for target_month in months:
                # Calcular início e fim do mês alvo
                first_day = datetime(year, target_month, 1)
                last_day = datetime(year, target_month, monthrange(year, target_month)[1], 23, 59, 59)

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

                # Detectar se é caso de virada de mês
                if inicio.month != fim.month:
                    boundary_case = True
                    boundary_count += 1

                    # APLICAR REGRA DE DESEMPATE
                    if MONTH_BOUNDARY_RULE == "fim":
                        # Conta no mês onde FINALIZOU
                        if fim.month != target_month:
                            continue  # Pula este mês, será contado no mês do fim
                    elif MONTH_BOUNDARY_RULE == "inicio":
                        # Conta no mês onde COMEÇOU
                        if inicio.month != target_month:
                            continue  # Pula este mês, será contado no mês do início
                    else:
                        # Fallback: usar fim (padrão)
                        if fim.month != target_month:
                            continue

                # Adicionar registro
                processed_records.append({
                    "linea": linea,
                    "date": fim.date(),
                    "month": target_month,
                    "horasact": float(horasact),
                    "boundary_case": boundary_case
                })
                break  # Não contar o mesmo registro em múltiplos meses

        df = pd.DataFrame(processed_records)

        if boundary_count > 0:
            print(f"[ZPP] Producao: {len(df)} registros carregados ({boundary_count} cruzam virada de mes)")
            print(f"      Regra aplicada: MONTH_BOUNDARY_RULE = '{MONTH_BOUNDARY_RULE}'")
        else:
            print(f"[ZPP] Producao: {len(df)} registros carregados para {year}, meses {months}")

        return df

    except Exception as e:
        print(f"[ERRO] Falha ao buscar dados de producao: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=["linea", "date", "month", "horasact", "boundary_case"])


def fetch_zpp_breakdown_data(year: int, months: List[int]) -> pd.DataFrame:
    """
    Busca dados de paradas (avarias) da collection ZPP_Paradas_2025

    IMPORTANTE: Usa filtro INCLUSIVO para capturar registros que cruzam virada de mês
    - Busca registros onde INÍCIO ou FIM estejam no mês
    - Aplica regra de desempate conforme MONTH_BOUNDARY_RULE

    Args:
        year: Ano de referência (ex: 2025)
        months: Lista de meses (ex: [1, 2, 3])

    Returns:
        DataFrame com colunas: [linea, date, month, motivo, duracao_min, boundary_case]
    """
    try:
        from calendar import monthrange

        collection = get_mongo_connection("ZPP_Paradas_2025")

        # Buscar TODOS os registros processados do ano
        query = {
            "_year": year,
            "_processed": True,
            "motivo": {"$in": BREAKDOWN_CODES}
        }

        # Buscar documentos com AMBAS as datas
        cursor = collection.find(
            query,
            {
                "linea": 1,
                "data_inicio": 1,  # Início da parada
                "data_fim": 1,     # Fim da parada (novo)
                "motivo": 1,
                "duracao_min": 1,
                "_id": 0
            }
        )

        records = list(cursor)

        if not records:
            print(f"[AVISO] Nenhuma parada (avaria) encontrada para {year}")
            return pd.DataFrame(columns=["linea", "date", "month", "motivo", "duracao_min", "boundary_case"])

        # Processar dados com filtro INCLUSIVO
        processed_records = []
        boundary_count = 0

        for record in records:
            # Extrair datas
            inicio_obj = record.get("data_inicio")
            fim_obj = record.get("data_fim")

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
            linea = record.get("linea")
            motivo = record.get("motivo")
            duracao_min = record.get("duracao_min", 0)

            if not linea:
                continue

            # FILTRO INCLUSIVO por mês
            for target_month in months:
                first_day = datetime(year, target_month, 1)
                last_day = datetime(year, target_month, monthrange(year, target_month)[1], 23, 59, 59)

                # Verificar interseção
                intersects = False
                boundary_case = False

                if (first_day <= inicio <= last_day) or \
                   (first_day <= fim <= last_day) or \
                   (inicio < first_day and fim > last_day):
                    intersects = True

                if not intersects:
                    continue

                # Detectar virada de mês
                if inicio.month != fim.month:
                    boundary_case = True
                    boundary_count += 1

                    # APLICAR REGRA DE DESEMPATE
                    if MONTH_BOUNDARY_RULE == "fim":
                        if fim.month != target_month:
                            continue
                    elif MONTH_BOUNDARY_RULE == "inicio":
                        if inicio.month != target_month:
                            continue
                    else:
                        if fim.month != target_month:
                            continue

                # Adicionar registro
                processed_records.append({
                    "linea": linea,
                    "date": inicio.date(),
                    "month": target_month,
                    "motivo": motivo,
                    "duracao_min": float(duracao_min),
                    "boundary_case": boundary_case
                })
                break

        df = pd.DataFrame(processed_records)

        if boundary_count > 0:
            print(f"[ZPP] Paradas: {len(df)} registros carregados ({boundary_count} cruzam virada de mes)")
            print(f"      Regra aplicada: MONTH_BOUNDARY_RULE = '{MONTH_BOUNDARY_RULE}'")
        else:
            print(f"[ZPP] Paradas: {len(df)} registros de avarias carregados para {year}, meses {months}")

        return df

    except Exception as e:
        print(f"[ERRO] Falha ao buscar dados de paradas: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=["linea", "date", "month", "motivo", "duracao_min", "boundary_case"])


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
        print("[AVISO] Sem dados de produção para calcular KPIs")
        return result

    # Obter lista de equipamentos e meses únicos
    equipment_list = production_df['linea'].unique()
    months = sorted(production_df['month'].unique())

    print(f"[ZPP] Calculando KPIs para {len(equipment_list)} equipamentos, {len(months)} meses")

    for linea in equipment_list:
        monthly_data = []

        # Filtrar dados do equipamento
        prod_linea = production_df[production_df['linea'] == linea]
        breakdown_linea = breakdown_df[breakdown_df['linea'] == linea]

        for month in months:
            # Filtrar dados do mês
            prod_month = prod_linea[prod_linea['month'] == month]
            breakdown_month = breakdown_linea[breakdown_linea['month'] == month]

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
                    # Sem falhas = MTBF infinito (usar valor alto)
                    mtbf = 999.0

                # M02 - MTTR (horas)
                if num_failures > 0:
                    mttr = total_breakdown_hours / num_failures
                else:
                    mttr = 0.0

                # M03 - Taxa de Avaria (%)
                breakdown_rate = (total_breakdown_hours / total_active_hours) * 100
            else:
                # Sem horas de atividade
                mtbf = None
                mttr = None
                breakdown_rate = None

            monthly_data.append({
                "month": month,
                "mtbf": round(mtbf, 2) if mtbf is not None else None,
                "mttr": round(mttr, 2) if mttr is not None else None,
                "breakdown_rate": round(breakdown_rate, 2) if breakdown_rate is not None else None
            })

        result[linea] = monthly_data

    print(f"[ZPP] KPIs calculados com sucesso para {len(result)} equipamentos")
    return result


# ==================== FUNÇÃO PRINCIPAL ====================

def fetch_zpp_kpi_data(year: int, months: List[int]) -> Dict:
    """
    Função principal: busca dados do MongoDB e calcula KPIs

    Args:
        year: Ano de referência (ex: 2025)
        months: Lista de meses (ex: [1, 2, 3] para Jan-Mar)

    Returns:
        dict: Dados de KPIs no formato esperado pelos callbacks

    Raises:
        Exception: Se houver erro ao buscar ou processar dados
    """
    print("\n" + "-"*60)
    print(f">>> ZPP: Iniciando fetch_zpp_kpi_data")
    print(f"    Ano: {year}")
    print(f"    Meses: {months}")
    print("-"*60)

    try:
        # 1. Buscar dados de produção
        production_df = fetch_zpp_production_data(year, months)

        # 2. Buscar dados de paradas
        breakdown_df = fetch_zpp_breakdown_data(year, months)

        # 3. Calcular KPIs
        kpi_data = calculate_monthly_kpis(production_df, breakdown_df)

        if not kpi_data:
            raise Exception("Nenhum dado de KPI foi calculado (sem dados de produção)")

        print(f"[ZPP] ✓ Dados carregados com sucesso: {len(kpi_data)} equipamentos")
        return kpi_data

    except Exception as e:
        print(f"[ERRO] Falha ao buscar dados ZPP: {e}")
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
        equipment_list = fetch_zpp_equipment_list()

        categories = {}

        for category_name, prefixes in EQUIPMENT_CATEGORY_PREFIXES.items():
            # Filtrar equipamentos que começam com algum dos prefixos
            category_equipment = [
                eq for eq in equipment_list
                if any(eq.startswith(prefix) for prefix in prefixes)
            ]

            if category_equipment:
                categories[category_name] = category_equipment

        # Adicionar categoria "Outros" para equipamentos não categorizados
        categorized = [eq for cat_list in categories.values() for eq in cat_list]
        others = [eq for eq in equipment_list if eq not in categorized]
        if others:
            categories["Outros"] = others

        return categories

    except Exception as e:
        print(f"[ERRO] Falha ao buscar categorias: {e}")
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
        "LONGI001": "LCL-4,5",  # Pode alterar lado direito depois para "Longitudinal 1"
        "LONGI002": "LCL-08",
        "PRENS001": "PRENSA-01",
        "PRENS002": "PRENSA-02",
        "TRANS001": "LCT-16",
        "TRANS002": "LCT-08",
        "TRANS003": "LCT-2,5"
        }

    try:
        equipment_list = fetch_zpp_equipment_list()

        print(f"[DEBUG] get_zpp_equipment_names: {len(equipment_list)} equipamentos encontrados")
        print(f"[DEBUG] CUSTOM_NAMES definidos: {list(CUSTOM_NAMES.keys())}")

        # Criar nomes amigáveis
        names = {}
        for eq_id in equipment_list:
            # Verificar se há nome customizado
            if eq_id in CUSTOM_NAMES:
                names[eq_id] = CUSTOM_NAMES[eq_id]
                print(f"[DEBUG] Usando nome customizado: {eq_id} -> {CUSTOM_NAMES[eq_id]}")
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
        print(f"[ERRO] Falha ao buscar nomes de equipamentos: {e}")
        return {}


# ==================== FUNÇÃO DE TESTE ====================

def fetch_top_breakdowns_by_equipment(equipment_id: str, year: int, months: List[int], top_n: int = 10) -> List[Dict]:
    """
    Busca as N paradas com maior duração para um equipamento específico

    Args:
        equipment_id: ID do equipamento (ex: "LONGI001")
        year: Ano de referência (ex: 2025)
        months: Lista de meses (ex: [1, 2, 3])
        top_n: Número de paradas a retornar (padrão: 10)

    Returns:
        Lista de dicionários ordenada por duração (maior para menor):
        [
            {
                "date": datetime.date(2025, 1, 15),
                "motivo": "201",
                "duracao_min": 120.5,
                "duracao_horas": 2.01,
                "descricao": "Observação da notificação"  # Campo 'observacao_de_notificacao'
            },
            ...
        ]
    """
    try:
        collection = get_mongo_connection("ZPP_Paradas_2025")

        # Construir pipeline de agregação para filtrar por mês primeiro
        # Usar $expr para comparar mês extraído de data_inicio
        pipeline = [
            # Stage 1: Filtrar por equipamento, ano, códigos de parada
            {
                "$match": {
                    "_year": year,
                    "_processed": True,
                    "linea": equipment_id,
                    "motivo": {"$in": BREAKDOWN_CODES},
                    "data_inicio": {"$exists": True}  # Garantir que data_inicio existe
                }
            },
            # Stage 2: Adicionar campo calculado com o mês extraído
            {
                "$addFields": {
                    "_month": {"$month": "$data_inicio"}
                }
            },
            # Stage 3: Filtrar pelos meses desejados
            {
                "$match": {
                    "_month": {"$in": months}
                }
            },
            # Stage 4: Ordenar por duração (maior para menor)
            {
                "$sort": {"duracao_min": -1}
            },
            # Stage 5: Limitar ao top_n
            {
                "$limit": top_n
            },
            # Stage 6: Projetar apenas os campos necessários
            {
                "$project": {
                    "data_inicio": 1,
                    "motivo": 1,
                    "duracao_min": 1,
                    "observacao_de_notificacao": 1,
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
            date_obj = record.get("data_inicio")
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

            motivo = record.get("motivo", "")
            duracao_min = record.get("duracao_min", 0)

            # ✅ USAR OBSERVAÇÃO DA NOTIFICAÇÃO DO BANCO DE DADOS
            descricao = record.get("observacao_de_notificacao", f"Motivo {motivo}")

            result.append({
                "date": date.date(),
                "motivo": motivo,
                "duracao_min": float(duracao_min),
                "duracao_horas": round(duracao_min / 60.0, 2),
                "descricao": descricao  # ✅ OBSERVAÇÃO DA NOTIFICAÇÃO
            })

        return result

    except Exception as e:
        print(f"[ERRO] Falha ao buscar top paradas: {e}")
        return []


if __name__ == "__main__":
    """Script de teste para validar cálculos"""
    print("\n" + "="*80)
    print("TESTE: Módulo ZPP KPI Calculator")
    print("="*80 + "\n")

    # Testar busca de equipamentos
    print("1. Buscando lista de equipamentos...")
    equipments = fetch_zpp_equipment_list()
    print(f"   → Encontrados: {equipments}\n")

    # Testar busca de categorias
    print("2. Buscando categorias...")
    categories = get_zpp_equipment_categories()
    for cat, eqs in categories.items():
        print(f"   → {cat}: {eqs}")
    print()

    # Testar busca de dados e cálculo de KPIs
    print("3. Testando cálculo de KPIs para Jan-Mar 2025...")
    try:
        kpi_data = fetch_zpp_kpi_data(year=2025, months=[1, 2, 3])

        # Mostrar exemplo de resultado
        if kpi_data:
            first_equipment = list(kpi_data.keys())[0]
            print(f"\n   Exemplo: {first_equipment}")
            for month_data in kpi_data[first_equipment]:
                print(f"   → Mês {month_data['month']}: "
                      f"MTBF={month_data['mtbf']}h, "
                      f"MTTR={month_data['mttr']}h, "
                      f"Taxa={month_data['breakdown_rate']}%")

        print(f"\n   ✓ Teste concluído com sucesso!")

    except Exception as e:
        print(f"\n   ✗ Erro no teste: {e}")

    print("\n" + "="*80)
