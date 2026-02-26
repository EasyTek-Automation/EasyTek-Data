# ⚠️ Dívida Técnica

> **O que é Dívida Técnica?**
> Melhorias identificadas que **não são bugs críticos**, mas aumentam:
> - 🔒 Segurança
> - 📈 Performance
> - 🧹 Manutenibilidade
> - 🛡️ Robustez

---

## 📊 Status Geral

| Módulo | Total | 🔴 Alta | 🟡 Média | 🟢 Baixa | ✅ Concluído |
|--------|-------|---------|----------|----------|--------------|
| **ZPP Processing** | 9 | 3 | 3 | 3 | 0 |
| **Webapp (KPI)** | 2 | 0 | 1 | 1 | 0 |
| Event Gateway | - | - | - | - | - |
| **TOTAL** | **11** | **3** | **4** | **4** | **0** |

---

## 📋 Lista de Débitos

### 🔴 Alta Prioridade

Impacto direto em segurança, robustez ou prevenção de problemas.

#### ZPP Processing

1. **[Validação de Schema](./zpp-processing-improvements.md#1-validação-de-schema)**
   Validar colunas obrigatórias antes de processar
   `process_zpp_to_mongo.py`

2. **[Exceções Específicas](./zpp-processing-improvements.md#2-exceções-específicas)**
   Substituir `except:` genérico por exceções específicas
   `process_zpp_to_mongo.py:104, clean_zpp_data.py`

3. **[Limite de Tamanho](./zpp-processing-improvements.md#3-limite-de-tamanho)**
   Avisar/limitar arquivos muito grandes (>100MB)
   `clean_zpp_data.py:236`

---

### 🟡 Média Prioridade

Melhorias de código e performance.

#### ZPP Processing

4. **[Refatoração de Duplicação](./zpp-processing-improvements.md#4-refatoração-duplicação)**
   Unificar lógica de índices e verificação de duplicatas
   `process_zpp_to_mongo.py:172-215, 336-376`

5. **[Cache de Duplicatas](./zpp-processing-improvements.md#5-cache-duplicatas)**
   Melhorar performance de verificação
   `process_zpp_to_mongo.py:336-376`

6. **[Argumentos CLI](./zpp-processing-improvements.md#6-argumentos-cli)**
   Tornar `process_zpp_quick.py` configurável via argumentos
   `process_zpp_quick.py:16-18`

#### Webapp (KPI)

7. **[Filtro Inclusivo Month Boundary](./filtro-inclusivo-month-boundary.md)**
   Otimizar filtro de virada de mês usando agregação MongoDB
   `webapp/src/utils/zpp_kpi_calculator.py:81-420`
   **Mitigação atual**: Cache em store (Opção A) - performance aceitável

---

### 🟢 Baixa Prioridade

Nice-to-have, funcionalidades extras.

#### Webapp (KPI)

8. **[Semântica do Botão Atualizar](./indicadores-botao-atualizar.md)**
   Definir comportamento claro entre "Atualizar" e "Aplicar Filtros"
   `webapp/src/callbacks_registers/maintenance_kpi_callbacks.py` — CALLBACK 8
   **Mitigação atual**: Opção C (clientside redirect) — funcional mas com UX ambígua

#### ZPP Processing

7. **[Processamento em Chunks](./zpp-processing-improvements.md#7-chunks)**
   Para arquivos gigantes (>100MB)
   `clean_zpp_data.py:236`

8. **[Relatório de Saúde](./zpp-processing-improvements.md#8-health-report)**
   Estatísticas sobre qualidade dos dados
   *novo módulo*

9. **[Dry-run Integrado](./zpp-processing-improvements.md#9-dry-run)**
   Modo de teste no script principal
   `process_zpp_to_mongo.py`

---

## ✅ Concluídos

| # | Item | Data | Responsável | Commit/PR |
|---|------|------|-------------|-----------|
| - | *(nenhum ainda)* | - | - | - |

---

## 🎯 Meta

**Objetivo Q1 2026**: Zerar débitos de **Alta Prioridade** (3 itens)

**Progresso**:
- 🔴 Alta: 0/3 concluído (0%)
- 🟡 Média: 0/4 concluído (0%)
- 🟢 Baixa: 0/3 concluído (0%)

---

## 📝 Como Usar

### Escolher um Item

1. Escolha da lista de prioridade desejada
2. Clique no link para ver **detalhes técnicos**
3. Implemente seguindo as sugestões

### Marcar como Concluído

1. Mova o item para seção **"Concluídos"**
2. Adicione data, responsável e link do commit/PR
3. Atualize a **tabela de Status Geral**

### Adicionar Novo Débito

1. Crie/edite arquivo específico em `technical-debt/`
2. Adicione entrada neste README na prioridade correta
3. Atualize a tabela de Status Geral

---

## 📚 Arquivos Detalhados

- **[zpp-processing-improvements.md](./zpp-processing-improvements.md)** - Melhorias ZPP detalhadas
- **[filtro-inclusivo-month-boundary.md](./filtro-inclusivo-month-boundary.md)** - Otimização filtro de virada de mês
- **[performance-indicators-kpi.md](./performance-indicators-kpi.md)** - Performance página indicadores
- **[indicadores-botao-atualizar.md](./indicadores-botao-atualizar.md)** - Semântica do botão Atualizar
- **[refatoracao-arquivos.md](./refatoracao-arquivos.md)** - Refatorações arquiteturais

---

**Última atualização**: 2026-02-26
