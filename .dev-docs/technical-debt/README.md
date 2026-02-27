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
| **Webapp (KPI)** | 4 | 0 | 0 | 0 | 4 |
| Event Gateway | - | - | - | - | - |
| **TOTAL** | **13** | **3** | **3** | **3** | **4** |

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

---

### 🟢 Baixa Prioridade

Nice-to-have, funcionalidades extras.

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

| # | Item | Data | Commit |
|---|------|------|--------|
| NR | **Cache persistente no `dcc.Store`** — Store de indicadores usava `storage_type="session"`, mantendo dados obsoletos entre navegações e causando exibição de KPIs errados ao retornar à página. Corrigido para `storage_type="memory"`. *(não registrado como dívida)* `webapp/src/pages/maintenance/indicators.py` | 2026-02-26 | `df806a9` |
| NR | **Race condition nos callbacks de indicadores** — Callback de renderização de UI podia executar antes do callback de dados terminar, lendo um store vazio e gerando outputs inválidos. Eliminado reordenando as dependências de input/output. *(não registrado como dívida)* `maintenance_kpi_callbacks.py` | 2026-02-26 | `a6999c4` |
| 7 | **Filtro Month Boundary / Filtro Multi-ano** — API `(year, months)` truncava filtro na virada de ano (loop `while current.year == start.year`), tornando impossível consultas como Out/2025 → Fev/2026. Refatorado para API `(start_date, end_date)` com helper `_get_month_periods()` gerando tuplas `(year, month)` corretamente através de qualquer fronteira de ano. Chaves `year_months` ("YYYY-MM") adicionadas ao store para filtro preciso. Ver [filtro-inclusivo-month-boundary.md](./filtro-inclusivo-month-boundary.md) | 2026-02-26 | `852b159` |
| 8 | **Semântica do Botão Atualizar** — Callback Python do `btn-atualizar` replicava toda a lógica do `btn-aplicar`, causando chamadas duplicadas ao MongoDB. Substituído por clientside callback que delega o clique ao `btn-aplicar`. Ver [indicadores-botao-atualizar.md](./indicadores-botao-atualizar.md) | 2026-02-26 | `8898a41` |

> **NR** = Não Registrado — item concluído que não constava na lista de débitos mas é documentado aqui para rastreabilidade.

---

## 🎯 Meta

**Objetivo Q1 2026**: Zerar débitos de **Alta Prioridade** (3 itens)

**Progresso**:
- 🔴 Alta: 0/3 concluído (0%)
- 🟡 Média: 1/4 concluído (25%) — item 7 (Webapp KPI) concluído
- 🟢 Baixa: 1/4 concluído (25%) — item 8 (Webapp KPI) concluído
- Não registrados: 2 concluído (race condition + cache store)

---

## 📝 Como Usar

### Escolher um Item

1. Escolha da lista de prioridade desejada
2. Clique no link para ver **detalhes técnicos**
3. Implemente seguindo as sugestões

### Marcar como Concluído

1. Mova o item para seção **"Concluídos"**
2. Adicione data e link do commit
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
