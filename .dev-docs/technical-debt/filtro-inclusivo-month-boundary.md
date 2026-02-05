# Dívida Técnica: Filtro Inclusivo de Virada de Mês

**Status:** 🟡 Médio Impacto
**Prioridade:** Baixa (performance aceitável com cache implementado)
**Esforço estimado:** 3-5 dias
**Arquivos afetados:**
- `webapp/src/utils/zpp_kpi_calculator.py` (linhas 81-250)
- `webapp/src/utils/zpp_kpi_calculator.py` (linhas 252-420)

## 📋 Descrição do Problema

O filtro inclusivo de virada de mês (`MONTH_BOUNDARY_RULE`) possui custo computacional elevado devido a três problemas arquiteturais:

### 1. Busca Completa do Ano sem Filtro no MongoDB
```python
query = {
    "_year": year,
    "_processed": True
}
# NÃO filtra por mês aqui! Busca TUDO do ano.
cursor = collection.find(query, {...})
```

**Problema:** Traz todos os registros do ano inteiro para a memória do servidor, sem filtrar por mês no banco de dados.

### 2. Loop Duplo Aninhado (Explosão Combinatória)
```python
for record in records:              # Loop EXTERNO: Todos os registros do ano
    for target_month in months:     # Loop INTERNO: Cada mês solicitado
        # Verificações complexas de intersecção
```

**Impacto:**
- 10.000 registros × 12 meses = **120.000 verificações**
- 50.000 registros × 12 meses = **600.000 verificações**

### 3. Cálculos Complexos por Verificação
Para CADA combinação (registro × mês):
- Calcular primeiro e último dia do mês
- Verificar 4 casos de intersecção de datas
- Detectar se cruza virada de mês (`inicio.month != fim.month`)
- Aplicar regra de desempate (`MONTH_BOUNDARY_RULE`)

## 📊 Impacto na Performance

| Cenário | Registros/ano | Meses | Verificações | Tempo |
|---------|---------------|-------|--------------|-------|
| Pequeno | 1.000 | 1 | 1.000 | ~0.1s |
| Médio | 5.000 | 6 | 30.000 | ~0.5s |
| Grande | 10.000 | 12 | 120.000 | ~2s |
| Muito Grande | 50.000 | 12 | 600.000 | ~10s |

**Problema secundário:** Sem cache, essa operação era executada 6 vezes (uma por callback), resultando em **~12s de delay** na página de indicadores.

## ✅ Mitigação Atual (Opção A - Cache no Store)

**Implementado em:** 2025-02-05
**Commit:** [pendente]

Implementado sistema de cache em `dcc.Store` para evitar recálculos:
1. CALLBACK 2 calcula `monthly_aggregates` **1 vez** e armazena no store
2. Callbacks 3, 4, 5, 6, 10B, 11 reutilizam o cache
3. Redução: 6 chamadas → 1 chamada por atualização de filtros

**Performance atual:**
- Primeira carga: ~2s (aceitável)
- Callbacks subsequentes: <100ms (usando cache)

## 🚀 Soluções Propostas

### Solução 1: Filtro no MongoDB com Agregação Pipeline ⭐ (Recomendada)

**Objetivo:** Mover a lógica de filtro para o MongoDB, reduzindo dados transferidos.

```python
def fetch_zpp_production_data_optimized(year: int, months: List[int]) -> pd.DataFrame:
    """
    Versão otimizada usando MongoDB aggregation pipeline
    """
    from calendar import monthrange

    collection = get_mongo_connection("ZPP_Producao_2025")

    # Construir ranges de datas para cada mês
    month_ranges = []
    for month in months:
        first_day = datetime(year, month, 1)
        last_day = datetime(year, month, monthrange(year, month)[1], 23, 59, 59)
        month_ranges.append((first_day, last_day))

    # Pipeline de agregação
    pipeline = [
        # Stage 1: Filtrar por ano e status
        {
            "$match": {
                "_year": year,
                "_processed": True
            }
        },
        # Stage 2: Adicionar campo de mês calculado
        {
            "$addFields": {
                "start_month": {"$month": "$fininotif"},
                "end_month": {"$month": "$ffinnotif"},
                "crosses_boundary": {
                    "$ne": [
                        {"$month": "$fininotif"},
                        {"$month": "$ffinnotif"}
                    ]
                }
            }
        },
        # Stage 3: Filtrar por meses solicitados (aplicar regra)
        {
            "$match": {
                "$or": [
                    # Caso 1: Não cruza virada, mês fim está na lista
                    {
                        "crosses_boundary": False,
                        "end_month": {"$in": months}
                    },
                    # Caso 2: Cruza virada, aplicar MONTH_BOUNDARY_RULE
                    {
                        "crosses_boundary": True,
                        f"{'end_month' if MONTH_BOUNDARY_RULE == 'fim' else 'start_month'}": {"$in": months}
                    }
                ]
            }
        },
        # Stage 4: Projetar apenas campos necessários
        {
            "$project": {
                "linea": "$pto_trab",
                "inicio": "$fininotif",
                "fim": "$ffinnotif",
                "horasact": 1,
                "month": f"${'end_month' if MONTH_BOUNDARY_RULE == 'fim' else 'start_month'}",
                "boundary_case": "$crosses_boundary",
                "_id": 0
            }
        }
    ]

    cursor = collection.aggregate(pipeline)
    records = list(cursor)

    return pd.DataFrame(records)
```

**Benefícios:**
- ✅ Filtro executado no MongoDB (mais rápido)
- ✅ Menos dados transferidos pela rede
- ✅ Elimina loop duplo no Python
- ✅ Escalável para grandes volumes

**Desafios:**
- Requer reescrever lógica em `fetch_zpp_production_data()` e `fetch_zpp_breakdown_data()`
- Testar extensivamente para garantir mesmos resultados
- Manter compatibilidade com `MONTH_BOUNDARY_RULE`

**Esforço:** 3 dias

---

### Solução 2: Índices Otimizados no MongoDB

**Objetivo:** Acelerar queries com índices compostos.

```python
# Criar índices (executar uma vez no MongoDB)
db.ZPP_Producao_2025.createIndex({"_year": 1, "ffinnotif": 1})
db.ZPP_Producao_2025.createIndex({"_year": 1, "fininotif": 1})
db.ZPP_Paradas_2025.createIndex({"_year": 1, "ffinnotif": 1})
db.ZPP_Paradas_2025.createIndex({"_year": 1, "fininotif": 1})
```

**Benefícios:**
- ✅ Queries mais rápidas no MongoDB
- ✅ Não requer mudanças no código
- ✅ Implementação simples

**Limitação:**
- ⚠️ Não resolve loop duplo aninhado
- ⚠️ Melhoria marginal (~20-30%)

**Esforço:** 1 dia

---

### Solução 3: Cache em Redis/Memória com TTL

**Objetivo:** Cachear resultados de `fetch_zpp_production_data()` e `fetch_zpp_breakdown_data()` por range de datas.

```python
import hashlib
import pickle
from functools import lru_cache

def _generate_cache_key(year: int, months: List[int]) -> str:
    """Gera chave única para cache baseada em parâmetros"""
    key_str = f"{year}_{sorted(months)}"
    return hashlib.md5(key_str.encode()).hexdigest()

@lru_cache(maxsize=128)
def fetch_zpp_production_data_cached(year: int, months_tuple: tuple) -> pd.DataFrame:
    """Versão cacheada (months como tuple para ser hashable)"""
    months = list(months_tuple)
    return fetch_zpp_production_data(year, months)
```

**Benefícios:**
- ✅ Evita recálculos para mesmos parâmetros
- ✅ Implementação simples (decorador)
- ✅ Funciona bem com padrões de acesso repetidos

**Limitação:**
- ⚠️ Não resolve problema de performance na primeira carga
- ⚠️ Requer gestão de memória

**Esforço:** 1 dia

---

### Solução 4: Pré-processamento em Collection Auxiliar

**Objetivo:** Criar collection `ZPP_Producao_2025_Monthly` com dados já agregados por mês.

```python
# Collection auxiliar (criada por job ETL)
{
    "year": 2025,
    "month": 1,
    "linea": "LONGI001",
    "horasact": 720.5,
    "boundary_count": 3  # Registros que cruzaram virada
}
```

**Benefícios:**
- ✅ Queries extremamente rápidas
- ✅ Elimina completamente processamento de filtro
- ✅ Ideal para dashboards

**Desafios:**
- ⚠️ Requer job ETL para manter atualizado
- ⚠️ Duplicação de dados
- ⚠️ Complexidade operacional

**Esforço:** 5 dias

---

## 🎯 Recomendação

**Para resolver definitivamente:**
1. **Curto prazo** (já feito): Manter cache atual (Opção A) - performance aceitável
2. **Médio prazo** (próxima sprint): Implementar **Solução 1** (Agregação MongoDB)
3. **Opcional**: Adicionar **Solução 2** (índices) como melhoria incremental

**Critério de sucesso:**
- Reduzir tempo de primeira carga de ~2s para <500ms
- Manter precisão dos cálculos
- Manter flexibilidade do `MONTH_BOUNDARY_RULE`

## 📝 Notas Adicionais

### Por que mantemos assim atualmente?

1. **Simplicidade**: Código fácil de entender e manter
2. **Flexibilidade**: Regra configurável via `MONTH_BOUNDARY_RULE`
3. **Precisão**: Captura TODOS os casos de virada de mês corretamente
4. **Performance aceitável**: Com cache (Opção A), só calcula 1x por filtro

### Contexto histórico

- **2025-02-05**: Identificado problema de performance (12s de delay)
- **2025-02-05**: Implementado cache em store (Opção A) - redução para ~2s
- Performance é aceitável para casos de uso atuais (volume médio de dados)

### Quando priorizar?

Aumentar prioridade se:
- Volume de dados crescer >50.000 registros/ano
- Usuários reportarem lentidão na página de indicadores
- Necessidade de consultas em tempo real (<500ms)

## 🔗 Referências

- Código atual: `webapp/src/utils/zpp_kpi_calculator.py` (linhas 81-420)
- Cache implementado: `webapp/src/callbacks_registers/maintenance_kpi_callbacks.py` (CALLBACK 2)
- Documentação MongoDB Aggregation: https://www.mongodb.com/docs/manual/aggregation/
- PRO017: KPI Calculation Procedures (documento interno)
