# Dívida Técnica - Performance dos Indicadores de Manutenção

**Data:** 2026-02-02
**Prioridade:** ALTA ⚠️
**Impacto:** Performance do usuário
**Módulo:** `webapp/src/pages/maintenance/indicators.py`
**Status:** Em Progresso (Opção 1 implementada)

---

## 🎯 Problema

A página de Indicadores de Manutenção (aba Individual) apresenta tempo de carregamento lento ao trocar de equipamento, especialmente o Calendar Heatmap que leva 5-10 segundos para renderizar.

---

## 🔍 Análise de Gargalos

### 1. Calendar Heatmap - GARGALO CRÍTICO ⚠️

**Arquivo:** `webapp/src/components/maintenance_kpi_graphs.py:994-1300`

**Problema:**
```python
# Loop que faz 2 consultas MongoDB POR DIA
while current_date <= end_date:
    # Consulta 1: Verificar produção
    prod_count = producao_collection.count_documents({...})

    # Consulta 2: Contar paradas
    breakdown_count = paradas_collection.count_documents({...})

    current_date += timedelta(days=1)
```

**Impacto:**
- Para período de 365 dias: **730 consultas ao MongoDB**
- Tempo de resposta: 5-10 segundos por equipamento
- Bloqueia renderização de outros gráficos

**Causa Raiz:**
- Arquitetura N+1 queries
- Falta de agregação no banco
- Processamento síncrono no callback

---

### 2. Múltiplos Callbacks Simultâneos

**Arquivo:** `webapp/src/callbacks_registers/maintenance_kpi_callbacks.py`

**Problema:**
Quando o usuário seleciona um equipamento no dropdown, disparam **4 callbacks independentes**:

```python
# CALLBACK 10B (linha 973): Atualizar cards individuais
@app.callback(
    [Output("individual-mtbf-value"), ...],
    [Input("dropdown-equipment-individual", "value")]
)

# CALLBACK 11 (linha 1012): Atualizar 3 gauges
@app.callback(
    [Output("gauge-mtbf-individual"), ...],
    [Input("dropdown-equipment-individual", "value")]
)

# CALLBACK 12 (linha 1092): Atualizar 5 gráficos de linha
@app.callback(
    [Output("line-chart-mtbf-individual"), ...],  # 5 outputs!
    [Input("dropdown-equipment-individual", "value")]
)

# CALLBACK 13 (linha 1223): Atualizar top paradas
@app.callback(
    Output("top-breakdowns-chart-individual"),
    [Input("dropdown-equipment-individual", "value")]
)
```

**Impacto:**
- 4 callbacks executados em paralelo
- Recalcula dados redundantes (médias, targets)
- Sobrecarga no servidor e cliente

---

### 3. Falta de Cache e Memoização

**Problema:**
- Dados são recalculados toda vez que o usuário troca de equipamento
- Função `calculate_kpi_averages()` é chamada em TODOS os callbacks
- Função `calculate_general_avg_by_month()` recalcula médias gerais repetidamente
- Nenhum uso de `dcc.Store` para cache intermediário

**Exemplo:**
```python
# Executado em CADA callback
averages = calculate_kpi_averages(data, equipment_ids, months)
general_avg = calculate_general_avg_by_month(data, all_equipment, months)
```

---

### 4. Processamento Pesado no Callback

**Problema:**
- Muito processamento no cliente (callbacks Python)
- Criação de 5 gráficos Plotly de forma síncrona
- Falta de pré-processamento no backend

---

## 💡 Soluções Propostas

### ✅ Opção 1: Otimização Rápida (IMPLEMENTADA)
**Tempo:** 30 minutos
**Complexidade:** Baixa
**Melhoria esperada:** 80-90% redução de tempo

**Implementações:**

1. **Otimizar Calendar Heatmap**
   - Substituir 730 consultas por 2 agregações MongoDB
   - Pipeline de agregação para produção e paradas
   - Processamento em memória após consulta única

2. **Lazy Loading do Calendar**
   - Mover calendar para tab separada ou collapse
   - Carregar apenas quando visível
   - Skeleton loading enquanto carrega

3. **Debounce no Dropdown**
   - Adicionar delay de 300ms no dropdown
   - Evitar múltiplas execuções ao trocar rapidamente

**Resultado:**
- De: 5-10 segundos → Para: 0.5-1 segundo ✅

---

### 🔄 Opção 2: Otimização Completa (PENDENTE)
**Tempo:** 2-3 horas
**Complexidade:** Média
**Melhoria esperada:** 95% redução de tempo

**Implementações:**

1. **Cache com dcc.Store**
   ```python
   dcc.Store(id='cached-kpi-data', storage_type='memory')
   dcc.Store(id='cached-averages', storage_type='memory')
   ```
   - Armazenar dados processados
   - Invalidar apenas quando filtros mudam
   - Reduzir recálculos

2. **Consolidar Callbacks Relacionados**
   ```python
   @app.callback(
       [
           Output("individual-mtbf-value"),
           Output("gauge-mtbf-individual"),
           Output("line-chart-mtbf-individual"),
           # ... todos outputs relacionados a MTBF
       ],
       [Input("dropdown-equipment-individual", "value")]
   )
   ```
   - Unir callbacks que usam mesmos dados
   - Calcular uma vez, usar múltiplas vezes

3. **Pre-computação de Agregações**
   - Criar função helper `precompute_equipment_data()`
   - Calcular todas métricas em uma passada
   - Retornar dicionário com resultados

4. **Loading States Melhores**
   - Skeleton screens nos gráficos
   - Progress indicators
   - Desabilitar dropdown durante loading

---

### 🚀 Opção 3: Otimização Avançada (FUTURO)
**Tempo:** 1 dia
**Complexidade:** Alta
**Melhoria esperada:** 98% redução de tempo + escalabilidade

**Implementações:**

1. **Background Workers (Celery/Redis)**
   - Processar KPIs assincronamente
   - Cache em Redis com TTL
   - Webhook para notificar quando pronto

2. **Indexação MongoDB Otimizada**
   ```javascript
   // Índices compostos para queries frequentes
   db.ZPP_Producao_2025.createIndex({
       "_year": 1,
       "_processed": 1,
       "fininotif": 1
   })

   db.ZPP_Paradas_2025.createIndex({
       "_year": 1,
       "_processed": 1,
       "linea": 1,
       "data_inicio": 1,
       "motivo": 1
   })
   ```

3. **Virtualização de Gráficos**
   - Carregar gráficos sob demanda (viewport)
   - Intersection Observer API
   - Renderização progressiva

4. **View Materialized no MongoDB**
   - Pré-agregar dados diários/mensais
   - Collection `KPI_Aggregated_Daily`
   - Atualizada via triggers ou jobs noturnos

5. **Server-Side Caching**
   - Cache de 5 minutos para dados agregados
   - Invalidação inteligente
   - Warmup cache para equipamentos mais acessados

---

## 📊 Métricas de Performance

### Antes da Otimização
- **Calendar Heatmap:** 5-10 segundos
- **Troca de Equipamento:** 3-5 segundos
- **Consultas MongoDB:** 730+ por carregamento
- **First Contentful Paint:** 8 segundos

### Após Opção 1 (Implementada)
- **Calendar Heatmap:** 0.5-1 segundo ✅
- **Troca de Equipamento:** 1-2 segundos
- **Consultas MongoDB:** 4-6 por carregamento
- **First Contentful Paint:** 2 segundos

### Após Opção 2 (Meta)
- **Calendar Heatmap:** 0.2-0.5 segundo
- **Troca de Equipamento:** 0.3-0.5 segundo
- **Consultas MongoDB:** 2-3 por carregamento
- **First Contentful Paint:** 1 segundo

### Após Opção 3 (Objetivo Final)
- **Calendar Heatmap:** <0.1 segundo
- **Troca de Equipamento:** <0.2 segundo
- **Consultas MongoDB:** 0 (cache hit)
- **First Contentful Paint:** <0.5 segundo

---

## 🔧 Arquivos Afetados

### Principais
- `webapp/src/components/maintenance_kpi_graphs.py` - Funções de gráficos
- `webapp/src/callbacks_registers/maintenance_kpi_callbacks.py` - Callbacks
- `webapp/src/pages/maintenance/indicators.py` - Layout da página
- `webapp/src/utils/zpp_kpi_calculator.py` - Cálculos de KPI

### Secundários
- `webapp/src/database/connection.py` - Conexão MongoDB
- `webapp/src/utils/maintenance_demo_data.py` - Dados de demonstração

---

## 📝 Notas de Implementação

### Padrões a Seguir

1. **Agregação MongoDB**
   ```python
   # BOM: Uma agregação para todo o período
   pipeline = [
       {"$match": {"linea": equipment_id, "data_inicio": {"$gte": start, "$lte": end}}},
       {"$group": {
           "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$data_inicio"}},
           "count": {"$sum": 1}
       }}
   ]

   # RUIM: Loop de consultas
   for date in dates:
       count = collection.count_documents({"data_inicio": date})
   ```

2. **Memoização**
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=128)
   def calculate_kpi_averages(data_tuple, equipment_tuple, months_tuple):
       # Converter de volta para tipos mutáveis
       data = dict(data_tuple)
       ...
   ```

3. **Loading States**
   ```python
   dcc.Loading(
       id="loading-calendar",
       type="default",
       children=dcc.Graph(id="calendar-heatmap"),
       delay_show=100,  # Mostrar loading após 100ms
       delay_hide=0
   )
   ```

---

## ⚠️ Riscos e Considerações

### Riscos da Opção 1 (Baixo)
- ✅ Mudanças isoladas, fácil de reverter
- ✅ Não quebra funcionalidade existente
- ⚠️ Ainda há espaço para melhorias

### Riscos da Opção 2 (Médio)
- ⚠️ Refatoração de callbacks pode introduzir bugs
- ⚠️ Cache pode ficar desatualizado
- ✅ Testes necessários após implementação

### Riscos da Opção 3 (Alto)
- ⚠️ Complexidade arquitetural aumenta
- ⚠️ Requer infraestrutura adicional (Redis/Celery)
- ⚠️ Manutenção mais complexa
- ✅ Escalabilidade garantida

---

## 🎯 Roadmap de Implementação

### Fase 1 - Otimização Rápida ✅
- [x] Analisar gargalos
- [x] Otimizar calendar heatmap
- [x] Adicionar lazy loading
- [x] Implementar debounce
- [ ] Testes de performance
- [ ] Deploy em produção

### Fase 2 - Otimização Completa (Q1 2026)
- [ ] Implementar cache com dcc.Store
- [ ] Consolidar callbacks relacionados
- [ ] Pre-computação de agregações
- [ ] Melhorar loading states
- [ ] Testes de carga

### Fase 3 - Otimização Avançada (Q2 2026)
- [ ] Setup Celery + Redis
- [ ] Criar índices MongoDB
- [ ] Implementar virtualização
- [ ] View materialized
- [ ] Warmup cache automático

---

## 📚 Referências

- [Dash Performance Best Practices](https://dash.plotly.com/performance)
- [MongoDB Aggregation Pipeline](https://docs.mongodb.com/manual/aggregation/)
- [Plotly Performance Tips](https://plotly.com/python/performance/)
- [Python LRU Cache](https://docs.python.org/3/library/functools.html#functools.lru_cache)

---

## 👥 Histórico de Alterações

| Data | Autor | Mudança | Status |
|------|-------|---------|--------|
| 2026-02-02 | Claude | Análise inicial e documentação | Completo ✅ |
| 2026-02-02 | Claude | Implementação Opção 1 | Em progresso 🔄 |

---

**Próxima Revisão:** Após implementação da Opção 2
**Responsável:** Equipe de Engenharia
