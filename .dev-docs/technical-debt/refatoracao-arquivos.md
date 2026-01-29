# Plano: Lista de Arquivos para Refatoração em webapp/src

## Resumo Executivo

Análise identificou **11 arquivos críticos** que necessitam refatoração em `webapp/src`, totalizando aproximadamente **5.600 linhas** de código com problemas de:
- Tamanho excessivo (arquivos com 400-900+ linhas)
- Responsabilidades múltiplas misturadas
- Código duplicado (especialmente em utilities de timezone)
- Lógica de negócio acoplada a callbacks de UI

---

## Arquivos Prioritários para Refatoração

### 🔴 PRIORIDADE CRÍTICA (P1) - Refatoração Urgente

#### 1. `pages/dashboards/production_oee.py` (901 linhas)
**Problema:** Arquivo monolítico misturando layout + lógica de gráficos + callbacks
- Layout do dashboard OEE
- 15+ funções de criação de gráficos
- Manipulação de cores e gradientes
- 9 callbacks de atualização em tempo real
- Estilos inline espalhados

**Ação Recomendada:**
- Dividir em: `pages/dashboards/production_oee.py` (apenas layout)
- Extrair: `components/oee_charts.py` (gráficos reutilizáveis)
- Extrair: `utils/color_gradients.py` (utilities de cores)

---

#### 2. `callbacks_registers/manage_users_callbacks.py` (591 linhas)
**Problema:** Callbacks aninhados com lógica RBAC e operações MongoDB misturadas
- 1 função contém 8+ callbacks aninhados
- Controle de permissões de gerenciamento de usuários
- Lógica de validação de senhas e MongoDB
- Difícil de testar e manter

**Ação Recomendada:**
- Separar: `callbacks_registers/manage_users_callbacks.py` (UI)
- Criar: `services/user_management_service.py` (lógica de negócio)
- Criar: `validators/user_validator.py` (validação reutilizável)

---

#### 3. `callbacks_registers/energygraph_callback.py` (502 linhas) + `callbacks_registers/hourlyconsumption_callback.py` (468 linhas)
**Problema:** **CÓDIGO DUPLICADO** - 90% das funções auxiliares são idênticas
- Funções de timezone duplicadas: `sp_range_to_utc_naive()`, `series_utc_to_sp_str()`, `series_utc_to_sp_naive()`
- Utilities MongoDB duplicadas: `_mongo_meta_info()`, `_safe_sample_doc()`, `_count_docs()`
- Lógica de logging idêntica
- Mistura de lógica de dados + apresentação

**Ação Recomendada:**
- Criar: `utils/datetime_tz.py` (centralizar todas as funções de timezone)
- Criar: `utils/mongo_helpers.py` (utilities MongoDB reutilizáveis)
- Refatorar ambos arquivos para usar os novos utilities
- **Impacto:** Redução de ~230 linhas duplicadas

---

#### 4. `index.py` (430 linhas)
**Problema:** Viola princípio de responsabilidade única - faz 6+ coisas diferentes
- Roteamento central com 40+ rotas
- Verificação de autenticação
- Resolução de aliases de rota
- Verificação de permissões
- Renderização de markdown
- Construção de layout principal
- 4 callbacks diferentes

**Ação Recomendada:**
- Dividir em: `routing/routes.py` (lógica de rotas e aliases)
- Criar: `middleware/auth_middleware.py` (verificação auth/permissões)
- Criar: `layout/layout_builder.py` (construção de layout principal)

---

### ⚠️ PRIORIDADE ALTA (P2) - Refatoração Recomendada

#### 5. `header.py` (519 linhas)
**Problema:** Arquivo monolítico com múltiplos menus e estilos inline
- Criação de menu de navegação
- Menu mega-dropdown de utilidades (6 submenus)
- Sistema de filtros dinâmico por página
- Dropdown de perfil/usuário
- 30+ linhas de estilos inline

**Ação Recomendada:**
- Dividir em módulo `header/`:
  - `navigation_menu.py` (menu de navegação)
  - `utilities_menu.py` (mega menu de utilidades)
  - `profile_dropdown.py` (dropdown de perfil)
  - `filters.py` (sistema de filtros)
  - `styles.py` (estilos compartilhados)

---

#### 6. `callbacks_registers/energy_sidebar_callbacks.py` (436 linhas)
**Problema:** Lógica comercial (cálculo de custos) em callback de UI
- Renderização dinâmica de sidebar baseada em tabs
- Cálculo de custos de energia em tempo real
- Formatação de valores monetários
- Integração com MongoDB
- Difícil de testar

**Ação Recomendada:**
- Manter: `callbacks_registers/energy_sidebar_callbacks.py` (apenas UI)
- Criar: `services/energy_cost_calculator.py` (cálculos isolados e testáveis)

---

#### 7. `callbacks_registers/energy_config_callbacks.py` (348 linhas)
**Problema:** Validação espalhada entre callbacks, sem camada de serviço
- Gerenciamento de configuração de tarifas
- Validação de entrada de usuário
- Persistência em MongoDB
- Feedback visual ao usuário

**Ação Recomendada:**
- Criar: `validators/energy_config_validator.py`
- Criar: `services/energy_config_service.py`

---

#### 8. `callbacks_registers/create_user_callbacks.py` (343 linhas)
**Problema:** Validação não reutilizável e lógica de negócio em callback
- Validação de usuário (email, username, senha)
- Hash de senhas
- Criação em MongoDB
- Verificação de duplicatas

**Ação Recomendada:**
- Criar: `validators/user_validator.py` (reutilizável)
- Integrar com `services/user_management_service.py`

---

### ⚡ PRIORIDADE MÉDIA (P3) - Melhorias Incrementais

#### 9. `pages/dashboards/home.py` (297 linhas)
**Problema:** Muitos cards KPI duplicando estrutura
- Poderia usar componentes reutilizáveis

**Ação Recomendada:**
- Criar: `components/kpi_card.py` (componente genérico)
- Refatorar home.py para usar o componente

---

#### 10. `pages/energy/overview.py` (307 linhas)
**Problema:** Sistema de tabs complexo
- Estrutura razoável mas pode melhorar

**Ação Recomendada:**
- Extrair tabs individuais para arquivos separados se crescer mais

---

#### 11. `components/sidebars/energy_sidebar.py` (267 linhas)
**Problema:** Lógica de cálculo de custos duplicada
- Conteúdo DEBUG misturado com produção

**Ação Recomendada:**
- Remover DEBUG
- Usar `services/energy_cost_calculator.py` quando criado

---

## Arquivos Adicionais de Atenção

### Callbacks Medianos (não críticos, mas monitorar crescimento):
- `callbacks_registers/home_callbacks.py` (230 linhas)
- `callbacks_registers/msgtable_callback.py` (154 linhas)
- `callbacks_registers/sidebar_filters_callback.py` (134 linhas)
- `callbacks_registers/tempgraph_callback.py` (131 linhas)
- `callbacks_registers/oeegraph_callback.py` (130 linhas)

### Duplicação Detectada:
- `callbacks_registers/states_callbacks.py` vs `states_callbacks02.py` - investigar se há duplicação

---

## Matriz de Decisão

| # | Arquivo | Linhas | Severidade | Esforço | Prioridade | ROI |
|---|---------|--------|-----------|---------|------------|-----|
| 1 | production_oee.py | 901 | 🔴 Crítico | Muito Alto | P1 | Alto |
| 2 | manage_users_callbacks.py | 591 | 🔴 Crítico | Alto | P1 | Alto |
| 3 | energygraph + hourlyconsumption | 970 | 🔴 Crítico | Médio | P1 | **Muito Alto** |
| 4 | index.py | 430 | 🔴 Crítico | Alto | P1 | Médio |
| 5 | header.py | 519 | ⚠️ Moderado | Alto | P2 | Médio |
| 6 | energy_sidebar_callbacks.py | 436 | ⚠️ Moderado | Médio | P2 | Alto |
| 7 | energy_config_callbacks.py | 348 | ⚠️ Moderado | Médio | P2 | Médio |
| 8 | create_user_callbacks.py | 343 | ⚠️ Moderado | Médio | P2 | Médio |
| 9 | home.py | 297 | ✅ Baixo | Baixo | P3 | Baixo |
| 10 | energy/overview.py | 307 | ✅ Baixo | Médio | P3 | Baixo |
| 11 | energy_sidebar.py | 267 | ✅ Baixo | Baixo | P3 | Baixo |

**Legenda ROI:**
- **Muito Alto:** Elimina duplicação ou resolve problema arquitetural grave
- **Alto:** Melhora significativa em testabilidade/manutenibilidade
- **Médio:** Melhoria incremental importante
- **Baixo:** Nice-to-have

---

## Recomendação de Ordem de Execução

### Fase 1: Quick Wins - Eliminar Duplicação (1-2 dias)
**ROI mais alto com menor esforço**

1. Criar `utils/datetime_tz.py` com funções de timezone
2. Criar `utils/mongo_helpers.py` com utilities MongoDB
3. Refatorar `energygraph_callback.py` para usar novos utils
4. Refatorar `hourlyconsumption_callback.py` para usar novos utils
5. **Resultado:** ~230 linhas eliminadas, código mais testável

### Fase 2: Separar Lógica de Negócio (3-5 dias)
**Melhora testabilidade drasticamente**

6. Extrair `services/user_management_service.py`
7. Extrair `validators/user_validator.py`
8. Refatorar `manage_users_callbacks.py`
9. Refatorar `create_user_callbacks.py`
10. Criar `services/energy_cost_calculator.py`
11. Refatorar `energy_sidebar_callbacks.py`

### Fase 3: Dividir Monolitos (5-7 dias)
**Impacto arquitetural de longo prazo**

12. Dividir `header.py` em módulo `header/`
13. Dividir `index.py` em módulo `routing/` + `middleware/` + `layout/`
14. Extrair gráficos de `production_oee.py` para `components/oee_charts.py`

### Fase 4: Melhorias Incrementais (2-3 dias)
**Polish e consistência**

15. Criar componentes reutilizáveis para home.py
16. Limpar DEBUG de energy_sidebar.py
17. Adicionar testes unitários para novos services/validators

**Estimativa Total:** 11-17 dias de trabalho

---

## Arquivos Críticos a Serem Modificados

### Criação de Novos Arquivos (utilidades):
- `webapp/src/utils/datetime_tz.py`
- `webapp/src/utils/mongo_helpers.py`
- `webapp/src/services/user_management_service.py`
- `webapp/src/services/energy_cost_calculator.py`
- `webapp/src/services/energy_config_service.py`
- `webapp/src/validators/user_validator.py`
- `webapp/src/validators/energy_config_validator.py`

### Refatoração de Arquivos Existentes (P1):
- `webapp/src/callbacks_registers/energygraph_callback.py`
- `webapp/src/callbacks_registers/hourlyconsumption_callback.py`
- `webapp/src/callbacks_registers/manage_users_callbacks.py`
- `webapp/src/pages/dashboards/production_oee.py`
- `webapp/src/index.py`

### Divisão de Monolitos (P2):
- `webapp/src/header.py` → `webapp/src/header/` (5 arquivos)
- `webapp/src/components/sidebars/energy_sidebar.py`

---

## Verificação de Sucesso

### Critérios de Aceitação:
1. ✅ Nenhum arquivo Python com mais de 400 linhas (exceto pages complexas)
2. ✅ Zero duplicação de código entre energygraph e hourlyconsumption
3. ✅ Lógica de negócio separada de callbacks de UI
4. ✅ Services e validators com testes unitários
5. ✅ index.py com responsabilidades claras e separadas
6. ✅ header.py dividido em módulos temáticos

### Como Testar:
1. Executar aplicação: `cd webapp && python run_local.py`
2. Verificar todos os endpoints continuam funcionando
3. Testar fluxos de usuário críticos:
   - Login/logout
   - Dashboard OEE
   - Gráficos de energia
   - Gerenciamento de usuários (admin)
4. Executar testes unitários (se criados): `pytest`
5. Verificar logs não contêm erros de importação

---

## Observações Finais

- **Padrão de callbacks_registers/** é BOM e deve ser mantido
- **Arquitetura base** (pages/, components/, callbacks_registers/) está correta
- Problema principal é **crescimento orgânico** sem refatoração contínua
- **Duplicação de código** é o problema mais fácil de resolver com maior ROI
- **Separação de concerns** (UI vs lógica) é o próximo passo natural

---

## Próximos Passos

Após decidir quais refatorações realizar:
1. Confirmar prioridade P1 (Fase 1 + Fase 2)
2. Criar branch de refatoração: `refactor/split-large-files`
3. Executar Fase 1 (quick wins)
4. Validar com testes
5. Iterar para Fases seguintes
