# 📊 Sistema de Filtros - Página de Indicadores de Manutenção

## 🎯 Localização dos Filtros

Os filtros estão localizados no **header dropdown** (canto superior direito), visíveis apenas quando você está na página `/maintenance/indicators`.

### Arquivo: `components/headers/maintenance_indicators_filters.py`

## 🔧 Tipos de Filtros Disponíveis

### 1️⃣ **Tipo de Período** (Radio Button)
- **ID**: `filter-period-type`
- **Opções**:
  - `year` - Ano completo (12 meses)
  - `last12` - Últimos 12 meses (padrão)
  - `custom` - Período personalizado
- **Valor Padrão**: `last12`

### 2️⃣ **Ano de Referência** (Dropdown)
- **ID**: `filter-reference-year`
- **Opções**: 2024, 2025, 2026
- **Valor Padrão**: 2025 (ano com dados ZPP disponíveis)
- **Visibilidade**: Aparece quando tipo = `year` ou `last12`

### 3️⃣ **Período Personalizado** (Date Picker Range)
- **ID**: `filter-date-range`
- **Campos**: Data Início + Data Fim
- **Visibilidade**: Aparece quando tipo = `custom`

### 4️⃣ **Botão Aplicar**
- **ID**: `btn-apply-indicator-filters`
- **Função**: Dispara o carregamento dos dados com os filtros selecionados

---

## 🔄 Fluxo de Funcionamento

```
┌─────────────────────────────────────────────────────────────────┐
│  1. USUÁRIO SELECIONA FILTROS NO HEADER                        │
│     - Tipo de Período: Últimos 12 Meses                        │
│     - Ano de Referência: 2025                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. USUÁRIO CLICA EM "APLICAR FILTROS"                         │
│     (btn-apply-indicator-filters)                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. CALLBACK: process_filters_and_load_data()                  │
│     (maintenance_kpi_callbacks.py: linha 78-218)               │
│                                                                 │
│     a) Valida os filtros                                       │
│     b) Calcula ano e meses a buscar                           │
│     c) Busca dados do MongoDB (ZPP_KPI_AVAILABLE)            │
│     d) Busca metas do MongoDB (AMG_MaintenanceTargets)       │
│     e) Retorna estrutura de dados                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  4. ATUALIZA STORE: store-indicator-filters                    │
│     {                                                           │
│       "period_type": "last12",                                 │
│       "year": 2025,                                            │
│       "months": [1,2,3,4,5,6,7,8,9,10,11,12],                │
│       "equipment_ids": ["LONGI001", "TRANS001", ...],         │
│       "data": {...},                                           │
│       "targets": {...},                                        │
│       "equipment_targets": {...},                             │
│       "names": {...},                                          │
│       "categories": {...},                                     │
│       "has_data": true                                         │
│     }                                                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  5. TODOS OS GRÁFICOS ATUALIZAM AUTOMATICAMENTE                │
│     (Input: "store-indicator-filters", "data")                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📈 Gráficos que Obedecem os Filtros

### ✅ TAB "GERAL" - TODOS OS GRÁFICOS

#### 1. **Summary Cards** (4 cards no topo)
- **Callback**: `update_summary_cards` (linha 223-293)
- **IDs**:
  - `summary-mtbf-value`, `summary-mtbf-badge`
  - `summary-mttr-value`, `summary-mttr-badge`
  - `summary-breakdown-value`, `summary-breakdown-badge`
  - `summary-equipment-count`
- **O que filtra**: Calcula médias gerais para o período selecionado

#### 2. **Gráficos Sunburst** (3 gráficos hierárquicos)
- **Callback**: `update_sunburst_charts` (linha 381-437)
- **IDs**:
  - `sunburst-chart-mtbf`
  - `sunburst-chart-mttr`
  - `sunburst-chart-breakdown`
- **O que filtra**: Hierarquia por categoria para o período selecionado

#### 3. **Gráficos de Barras** (3 gráficos por equipamento)
- **Callback**: `update_bar_charts` (linha 298-376)
- **IDs**:
  - `bar-chart-mtbf`
  - `bar-chart-mttr`
  - `bar-chart-breakdown`
- **O que filtra**: Médias por equipamento para o período selecionado

#### 4. **Tabela Resumo**
- **Callback**: `update_summary_table` (linha 442-486)
- **ID**: `kpi-summary-table-container`
- **O que filtra**: Tabela completa com médias por equipamento

---

### ✅ TAB "INDIVIDUAL" - TODOS OS GRÁFICOS

#### 5. **Dropdown de Equipamentos**
- **Callback**: `populate_equipment_dropdown` (linha 600-625)
- **ID**: `dropdown-equipment-individual`
- **O que filtra**: Lista de equipamentos disponíveis no período

#### 6. **Badges de Metas**
- **Callback**: `display_equipment_targets_badges` (linha 630-694)
- **ID**: `equipment-targets-badges`
- **O que filtra**: Metas específicas do equipamento selecionado

#### 7. **Gauges** (3 gauges)
- **Callback**: `update_individual_gauges` (linha 833-896)
- **IDs**:
  - `gauge-mtbf-individual`
  - `gauge-mttr-individual`
  - `gauge-breakdown-individual`
- **O que filtra**: Valores médios do equipamento no período

#### 8. **Top 10 Paradas Críticas**
- **Callback**: `update_top_breakdowns_chart` (linha 998-1085)
- **ID**: `top-breakdowns-chart-individual`
- **O que filtra**: Top 10 paradas do equipamento no período selecionado

#### 9. **Gráficos de Evolução Temporal** (3 gráficos de linha)
- **Callback**: `update_individual_tab` (linha 901-993)
- **IDs**:
  - `line-chart-mtbf-individual`
  - `line-chart-mttr-individual`
  - `line-chart-breakdown-individual`
- **O que filtra**: Evolução mensal do equipamento no período

#### 10. **Gráfico de Comparação**
- **Callback**: `update_individual_tab` (linha 901-993)
- **ID**: `comparison-chart-individual`
- **O que filtra**: Compara equipamento com média geral no período

---

## 📊 Resumo Visual

```
FILTROS (Header)                    AFETA
─────────────────────────────────────────────────────────────
┌─────────────────────┐
│ Tipo: Últimos 12    │────┐
│ Ano: 2025           │    │
│ [Aplicar Filtros]   │    │
└─────────────────────┘    │
                           │
                           ↓
                   ┌───────────────┐
                   │ Store Global  │
                   │ (cached data) │
                   └───────────────┘
                           ↓
        ┌──────────────────┴──────────────────┐
        │                                     │
   TAB GERAL                            TAB INDIVIDUAL
   ─────────                            ──────────────
   ✓ 4 Summary Cards                    ✓ Dropdown Equipamentos
   ✓ 3 Sunbursts                        ✓ 3 Gauges
   ✓ 3 Barras                           ✓ Top 10 Paradas
   ✓ 1 Tabela                           ✓ 3 Linhas (Evolução)
                                        ✓ 1 Comparativo
```

---

## 🎯 Comportamento dos Filtros

### Cenário 1: Tipo = "Ano"
```python
period_type = "year"
ref_year = 2025
# Resultado: Todos os meses de 2025 (jan-dez)
months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
```

### Cenário 2: Tipo = "Últimos 12 Meses"
```python
period_type = "last12"
ref_year = 2025
# Resultado: Últimos 12 meses a partir de 2025 (jan-dez 2025)
months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
```

### Cenário 3: Tipo = "Período Personalizado"
```python
period_type = "custom"
start_date = "2025-03-01"
end_date = "2025-08-31"
# Resultado: Meses de março a agosto de 2025
months = [3, 4, 5, 6, 7, 8]
```

---

## 🔍 Detalhes Técnicos

### Callback Central: `process_filters_and_load_data`

**Inputs** (triggers):
- `btn-apply-indicator-filters.n_clicks` - Botão Aplicar
- `interval-initial-load.n_intervals` - Carregamento inicial (1x)

**States** (valores dos filtros):
- `filter-period-type.value`
- `filter-reference-year.value`
- `filter-date-range.start_date`
- `filter-date-range.end_date`
- `store-indicator-filters.data` (dados atuais)

**Output**:
- `store-indicator-filters.data` - Estrutura completa com dados e metadados

### Otimização de Performance

1. **Carregamento Inicial**: Interval executa apenas 1 vez (500ms após carregar)
2. **Aplicar Filtros**: Usuário precisa clicar para atualizar
3. **Cache Inteligente**: Interval não recarrega dados se já existem (apenas metas)
4. **Botão Refresh**: Força reload completo de dados + metas

---

## ⚡ Pontos Importantes

1. **Todos os gráficos são filtráveis** - 100% dos gráficos obedecem os filtros
2. **Store centralizado** - `store-indicator-filters` é a fonte única de verdade
3. **Reatividade total** - Qualquer mudança no store atualiza todos os gráficos automaticamente
4. **Performance otimizada** - Dados carregados 1x, reutilizados em todos os gráficos
5. **Não há filtros locais** - Todos os filtros vêm do header (centralizados)

---

## 🚀 Melhorias Futuras Sugeridas

- [ ] Adicionar filtro por categoria de equipamento (Longitudinais, Transversais, Prensas)
- [ ] Adicionar filtro por múltiplos equipamentos (checkboxes)
- [ ] Salvar filtros favoritos do usuário
- [ ] Exportar dados filtrados para Excel (já implementado parcialmente)
- [ ] Adicionar comparação entre períodos (ex: 2024 vs 2025)
