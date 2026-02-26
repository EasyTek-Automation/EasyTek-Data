# Dívida Técnica — Botão "Atualizar" nos Indicadores de Manutenção

**Data:** 2026-02-26
**Prioridade:** 🟢 Baixa
**Módulo:** `webapp/src/callbacks_registers/maintenance_kpi_callbacks.py`
**Status:** Solução provisória ativa (Opção C)

---

## Contexto

O botão "Atualizar" (header da página `/maintenance/indicators`) deveria rebuscar
dados novos do MongoDB sem que o usuário precise mudar filtros.

Durante a correção de bugs de cache e race condition (2026-02-26), surgiu uma
ambiguidade de comportamento:

> O botão "Atualizar" deve usar os filtros **pendentes** do header (que o usuário
> pode ter alterado mas ainda não aplicou) ou os filtros **salvos** no store
> (última busca confirmada)?

---

## Decisão Provisória Adotada (Opção C)

**Implementação:**
```python
# maintenance_kpi_callbacks.py — CALLBACK 8
app.clientside_callback(
    "function(n) { if (!n) return window.dash_clientside.no_update; return n; }",
    Output("btn-apply-indicator-filters", "n_clicks"),
    Input("btn-refresh-indicators", "n_clicks"),
    prevent_initial_call=True
)
```

**Efeito:** clicar "Atualizar" é idêntico a clicar "Aplicar Filtros" — usa os
filtros **atuais do header**, incluindo alterações ainda não aplicadas.

**Motivo da escolha:** elimina duplicação de lógica de fetch sem custo de
implementação. Solução mais simples disponível no momento.

---

## Por Que Isto É Uma Dívida

### Problema de UX potencial

Se o usuário **alterou o ano no header mas ainda não clicou "Aplicar"**, ao
clicar "Atualizar" a busca usará o **ano alterado**, não o ano dos dados
exibidos. Isso pode ser contraintuitivo: o usuário queria apenas dados novos
para o período já exibido.

### Ambiguidade semântica dos dois botões

Com a Opção C, "Atualizar" e "Aplicar Filtros" fazem **exatamente a mesma
coisa**. Ter dois botões com comportamento idêntico confunde o usuário sobre
qual usar.

---

## Opções para Resolver

### Opção A — "Atualizar" lê filtros do header explicitamente
Adicionar States dos filtros do header ao callback `refresh_data`.

- Pro: comportamento igual à Opção C, mais explícito
- Contra: duplica a lógica de `process_filters_and_load_data`

### Opção B — Fundir os dois botões
Remover "Atualizar", deixar apenas "Aplicar Filtros".

- Pro: sem ambiguidade, sem dívida
- Contra: perde o botão de ação rápida visível na página (não no header)

### Opção C — Delegação clientside (ATUAL)
- Pro: DRY, zero lógica duplicada
- Contra: UX ambígua se filtros pendentes existirem

### Opção D — Dois comportamentos distintos e documentados
- "Aplicar": processa novos filtros + rebusca
- "Atualizar": rebusca com filtros do **store** (ignora alterações pendentes)

Requer manter dois callbacks separados mas com semântica clara para o usuário
(ex: tooltip explicativo em cada botão).

---

## Quando Revisitar

Revisitar quando **qualquer uma** das condições ocorrer:

- [ ] Usuário reportar confusão entre os dois botões
- [ ] Refatoração geral dos callbacks de indicadores (Opção 2 do `performance-indicators-kpi.md`)
- [ ] Adição de indicador visual de "filtros pendentes não aplicados" no header

---

## Arquivos Afetados

- `webapp/src/callbacks_registers/maintenance_kpi_callbacks.py` — CALLBACK 8
- `webapp/src/components/headers/maintenance_indicators_filters.py` — botão "Aplicar"
- `webapp/src/pages/maintenance/indicators.py` — botão "Atualizar"

---

**Próxima revisão sugerida:** junto com refatoração de callbacks (Q2 2026)
