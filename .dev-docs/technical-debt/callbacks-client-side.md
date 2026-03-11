# Dívida Técnica — Callbacks UI-only no Servidor

**Data:** 2026-03-11
**Prioridade:** BAIXA 🟢
**Impacto:** Performance percebida (latência de interações UI), carga desnecessária no servidor
**Módulo:** Webapp — callbacks_registers/
**Status:** Identificado — aguardando implementação

---

## Contexto

Análise de 2026-03-11 identificou callbacks Dash que fazem round-trip ao servidor Python
para operações puramente de UI (toggle de collapse, sidebar, etc.).

Nenhum desses callbacks acessa banco de dados, faz cálculos ou precisa de dados do servidor.
O único efeito é alternar um booleano ou retornar um dict de estilos CSS.

O Dash suporta `app.clientside_callback()` — registra como callback Dash normal
(sem ReferenceErrors, sem problemas de componente faltando no DOM), mas a função
roda no browser sem round-trip ao servidor.

---

## Casos identificados

### 1. `toggle_sidebar` — `main_layout_callbacks.py` 🟢 Baixa

**O que faz**: Expande/recolhe a sidebar calculando estilos CSS estáticos.

**Problema**: ~40 linhas de Python que apenas retornam dicts de estilos pré-definidos.
Cada clique no hambúrguer gera uma requisição HTTP ao servidor.

**Solução**: Converter para `app.clientside_callback()` com a lógica em JavaScript.

**Arquivos**: `webapp/src/callbacks_registers/main_layout_callbacks.py`

**Estimativa**: 1-2 horas | **Frequência**: Alta (~3-5 cliques/sessão)

---

### 2. `toggle_alarm_filters` — `alarms_callbacks.py` 🟢 Baixa

**O que faz**: Inverte `is_open` de um `dbc.Collapse` (painel de filtros de alarmes).

**Problema**: Corpo da função é literalmente `return not is_open`. Round-trip ao servidor
para inverter um booleano.

**Solução**: `app.clientside_callback("return !is_open", ...)`.

**Arquivos**: `webapp/src/callbacks_registers/alarms_callbacks.py`

**Estimativa**: 30 min | **Frequência**: Média (~5-10 cliques/sessão na página de alarmes)

---

### 3. `toggle_folder` — `procedures_collapse_callbacks.py` 🟢 Baixa

**O que faz**: Expande/recolhe pastas na navegação de procedimentos + rotação de ícone chevron via CSS.

**Problema**: Toggle de collapse + cálculo de `transform: rotate()`. Zero dados envolvidos.
Pattern-matching callback (MATCH), mas ainda desnecessariamente server-side.

**Solução**: `app.clientside_callback()` com lógica de toggle e rotação em JS.

**Arquivos**: `webapp/src/callbacks_registers/procedures_collapse_callbacks.py`

**Estimativa**: 1 hora | **Frequência**: Alta (~10-20 cliques/sessão na página de procedimentos)

---

### 4. `toggle_error_details` — `database_error_callbacks.py` 🟢 Baixa

**O que faz**: Inverte `is_open` do collapse de detalhes técnicos de erro de DB.

**Problema**: Idêntico ao caso 2 — `return not is_open`.

**Solução**: `app.clientside_callback("return !is_open", ...)`.

**Arquivos**: `webapp/src/callbacks_registers/database_error_callbacks.py`

**Estimativa**: 30 min | **Frequência**: Baixa (só aparece quando há erro de DB)

---

## Como converter (padrão)

```python
# ANTES — server-side desnecessário
@app.callback(
    Output("meu-collapse", "is_open"),
    Input("meu-botao", "n_clicks"),
    State("meu-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_collapse(n_clicks, is_open):
    return not is_open

# DEPOIS — client-side correto
app.clientside_callback(
    "function(n, isOpen) { return !isOpen; }",
    Output("meu-collapse", "is_open"),
    Input("meu-botao", "n_clicks"),
    State("meu-collapse", "is_open"),
    prevent_initial_call=True,
)
```

Para estilos CSS estáticos (como `toggle_sidebar`), definir os dicts de estilo
como constantes JavaScript no corpo da função clientside.

---

## Ordem de execução recomendada

| # | Item | Esforço | Frequência | Prioridade |
|---|------|---------|-----------|------------|
| 1 | toggle_alarm_filters | 30 min | Média | Fazer primeiro (mais simples) |
| 2 | toggle_error_details | 30 min | Baixa | Junto com o 1 |
| 3 | toggle_folder | 1h | Alta | Segundo |
| 4 | toggle_sidebar | 1-2h | Alta | Por último (mais complexo) |

---

## Nota: duplicação identificada

`toggle_sidebar` está implementado em **dois arquivos**:
- `main_layout_callbacks.py`
- `sidebar_toggle_callback.py`

Investigar qual está ativo antes de converter — um deles pode ser código morto.
