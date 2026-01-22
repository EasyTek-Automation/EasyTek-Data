---
name: energy-cost
description: Analisa e explica cálculos de custos de energia para subestações do AMG_Data. Use quando precisar entender ou revisar cálculos de tarifa elétrica.
argument-hint: [SE01|SE02|SE03|SE04]
allowed-tools: Read, Grep, Glob
context: fork
agent: Explore
---

# Analisador de Custos de Energia - AMG_Data

Analise os custos de energia para a subestação: **$ARGUMENTS**

## Estrutura do Cálculo

```
Custo Total = TUSD + Energia + Demanda
```

### Componentes do Custo

**1. TUSD (Tarifa de Uso do Sistema de Distribuição)**
- Tarifa fixa de transmissão
- Aplicada a todas as horas
- Valor por kWh transmitido

**2. Energia (Consumo)**
- **Ponta** (17h-20h): Tarifa mais cara
- **Fora Ponta** (demais horários): Tarifa mais barata
- Multiplicado pelo consumo em kWh

**3. Demanda**
- Baseada na máxima demanda do mês
- Calculada para período completo
- Proratizada por % de consumo no período

## Sua Tarefa

Para **$ARGUMENTS**, você deve:

### 1. Localizar Código Relevante

Encontre os arquivos que implementam o cálculo:
- `webapp/src/pages/energy/overview.py` - Layout da página
- `webapp/src/components/sidebars/energy_sidebar.py` - Cálculos no sidebar
- `webapp/src/pages/energy/config.py` - Configuração de tarifas
- `webapp/src/callbacks_registers/*energy*` - Callbacks relacionados

### 2. Analisar Implementação

Para cada componente, identifique:
- [ ] Como TUSD é calculado
- [ ] Como Energia Ponta é calculada
- [ ] Como Energia Fora Ponta é calculada
- [ ] Como Demanda é calculada
- [ ] Onde as tarifas são definidas
- [ ] Como os equipamentos são agrupados

### 3. Equipamentos por Subestação

**SE03** (totalmente implementada):
- Grupo Transversais: MM02, MM04, MM06
- Grupo Longitudinais: MM03, MM05, MM07

**Outras SEs**: Verificar implementação

### 4. Fórmulas Específicas

Documente as fórmulas exatas usadas:

```python
# Exemplo para SE03
custo_tusd = consumo_total * tarifa_tusd
custo_energia_ponta = consumo_ponta * tarifa_energia_ponta
custo_energia_fora_ponta = consumo_fora_ponta * tarifa_energia_fora_ponta
custo_demanda = (demanda_maxima_mes * tarifa_demanda) * (consumo_periodo / consumo_mes_total)
```

### 5. Configuração de Tarifas

Mostre onde as tarifas são configuradas:
- Arquivo de configuração
- Banco de dados
- Interface admin

### 6. Relatório Final

Produza um relatório com:

**Resumo do Cálculo:**
- Fórmula completa
- Valores de tarifa aplicados
- Período de cálculo (ponta vs fora ponta)

**Implementação:**
- Arquivos envolvidos
- Funções principais
- Callbacks relacionados

**Equipamentos:**
- Lista de equipamentos
- Como são agrupados
- Filtros disponíveis

**Possíveis Melhorias:**
- Otimizações no código
- Funcionalidades faltantes
- Sugestões de UX

**Exemplo de Saída:**

```
📊 Análise de Custos - SE03

Implementação: webapp/src/components/sidebars/energy_sidebar.py:125-230

Equipamentos:
- Transversais: MM02, MM04, MM06
- Longitudinais: MM03, MM05, MM07

Cálculo:
1. TUSD: consumo × R$ 0.15/kWh
2. Energia Ponta (17-20h): consumo × R$ 0.80/kWh
3. Energia Fora Ponta: consumo × R$ 0.45/kWh
4. Demanda: 50 kW × R$ 25/kW × (30% do mês)

Total: R$ 15.243,50

Configuração: /utilities/energy/config (admin only)
```

Seja específico e sempre referencie linhas de código reais.
