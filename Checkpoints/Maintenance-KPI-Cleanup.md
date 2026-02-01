# Remoção de Dados Fictícios dos Indicadores de Manutenção

**Data**: 2026-01-30
**Branch**: Fixing/OfflinePerformance

## Resumo das Alterações

### Objetivo
Remover completamente os dados fictícios (demo) dos indicadores de manutenção. Quando não houver dados no banco de dados MongoDB (collections ZPP), a página não exibe nada ao invés de mostrar dados de demonstração.

### Arquivos Modificados

#### 1. `webapp/src/callbacks_registers/maintenance_kpi_callbacks.py`
**Mudanças principais:**
- **CALLBACK 2 (process_filters_and_load_data)**:
  - Removido fallback para `generate_monthly_kpi_data()` quando ZPP falha
  - Agora retorna estrutura vazia (`data={}`, `all_equipment=[]`) quando não há dados
  - Adicionada flag `has_data` ao invés de `using_demo`
  - Usa `get_zpp_equipment_names()` e `get_zpp_equipment_categories()` do módulo ZPP

- **CALLBACK 3 (update_summary_cards)**:
  - Verifica `has_data` antes de processar
  - Retorna "Sem dados" ao invés de "Aguardando dados" quando não há dados
  - Mostra "0" equipamentos quando não há dados

- **CALLBACK 6 (update_summary_table)**:
  - Mensagem aprimorada com ícone quando não há dados
  - Empty state mais informativo e visualmente agradável

- **CALLBACK 8 (refresh_data)**:
  - Removido fallback para dados demo
  - Atualiza `has_data` flag corretamente

- **CALLBACK 9 (NOVO - populate_equipment_dropdown)**:
  - Novo callback para popular dropdown de equipamentos dinamicamente
  - Retorna lista vazia quando não há dados

- **Importações**:
  - Removidas importações não utilizadas: `generate_monthly_kpi_data`
  - Adicionadas importações do ZPP: `get_zpp_equipment_names`, `get_zpp_equipment_categories`
  - Mantidas funções de cálculo: `calculate_kpi_averages`, `calculate_general_avg_by_month`, `get_kpi_targets`

- **Banner de Demo**:
  - Callback removido completamente

#### 2. `webapp/src/pages/maintenance/indicators.py`
**Mudanças principais:**
- Removido componente `dbc.Alert` de banner de demo (linhas 35-39)
- Removidas importações: `get_equipment_names`, `get_kpi_targets`
- Dropdown de equipamentos agora inicia vazio e é populado via callback
- Placeholder adicionado ao dropdown: "Selecione um equipamento..."

#### 3. `webapp/src/utils/maintenance_demo_data.py`
**Status**: Mantido
**Razão**: Contém funções úteis de cálculo e agregação que ainda são necessárias:
- `calculate_kpi_averages()` - Calcula médias dos KPIs
- `calculate_general_avg_by_month()` - Médias mensais gerais
- `get_kpi_targets()` - Retorna metas configuradas
- `check_equipment_meets_targets()` - Valida se equipamento atende metas

**Funções NÃO MAIS USADAS** (mas mantidas no arquivo):
- `generate_monthly_kpi_data()` - Geração de dados fictícios
- `_generate_kpi_value()` - Geração de valores aleatórios

### Comportamento Atual

#### Quando HÁ dados no banco (ZPP):
1. Dados são carregados das collections `ZPP_Producao_2025` e `ZPP_Paradas_2025`
2. KPIs são calculados pela função `fetch_zpp_kpi_data()`
3. Todos os gráficos, cards e tabelas são populados
4. Dropdown de equipamentos é preenchido dinamicamente
5. Banner de demo NÃO é exibido

#### Quando NÃO HÁ dados no banco:
1. Flag `has_data = False` é setada
2. Summary cards mostram "--" e badge "Sem dados"
3. Contagem de equipamentos mostra "0"
4. Tabela mostra empty state com ícone e mensagem informativa
5. Gráficos mostram figuras vazias (via `create_empty_kpi_figure()`)
6. Dropdown de equipamentos fica vazio
7. **NENHUM DADO FICTÍCIO é gerado ou exibido**

### Collections MongoDB Utilizadas
- `ZPP_Producao_2025`: Dados de produção (horas de atividade)
- `ZPP_Paradas_2025`: Dados de paradas/avarias

### Códigos de Avaria (Breakdown Codes)
- 201, S201, 202, S202, 203, S203

### Metas (Targets) - Configuráveis em `maintenance_demo_data.py`
```python
KPI_TARGETS = {
    "mtbf": 20.0,           # horas
    "mttr": 2.0,            # horas
    "breakdown_rate": 3.0   # %
}
```

### KPIs Calculados (conforme documento PRO017)
- **M01 (MTBF)**: (∑Horas Atividade - ∑Tempo Falha) / Número Falhas
- **M02 (MTTR)**: Minutos Paragem / Número Paragens (convertido para horas)
- **M03 (Taxa Avaria)**: (Tempo Paragem / Horas Atividade) × 100

### Próximos Passos Sugeridos
1. ✅ Remover dados fictícios - CONCLUÍDO
2. Testar com dados reais do banco de dados
3. Validar cálculos de KPI conforme documento PRO017
4. Considerar mover `get_kpi_targets()` para um arquivo de configuração separado
5. Adicionar logging mais detalhado para debug
6. Implementar cache para melhorar performance

### Notas de Desenvolvimento
- Módulo `zpp_kpi_calculator.py` deve estar disponível e funcional
- Collections MongoDB devem ter campo `_processed: true` para serem consideradas
- Filtro de ano: `_year: 2025` (atualmente hardcoded para 2025)
- Caso de erro: Não há mais fallback - página mostra empty state

### Testes Recomendados
1. ✅ Verificar que sem dados no banco, página não mostra dados fictícios
2. ✅ Verificar que summary cards mostram "Sem dados" corretamente
3. ✅ Verificar que tabela mostra empty state
4. ✅ Verificar que dropdown de equipamentos fica vazio
5. ⏳ Com dados reais: verificar que todos os gráficos e cards são populados
6. ⏳ Testar botão de refresh
7. ⏳ Testar botão de export

---
**Desenvolvedor**: Claude Code
**Status**: IMPLEMENTADO E PRONTO PARA TESTE
