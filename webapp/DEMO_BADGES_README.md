# 🎯 Sistema de Badges para Dados de Demonstração

Sistema simples e flexível para indicar quando dados na tela são fictícios.

## ⚡ Início Rápido

### 1️⃣ Configurar (apenas uma vez)

Edite `webapp/src/config/demo_data_config.py`:

```python
# Ativar/desativar globalmente
ENABLE_DEMO_BADGES = True  # ou False

# Adicionar sua página
DEMO_PAGES = {
    "/sua/pagina": True,  # True = mostra badge, False = oculta
}
```

### 2️⃣ Usar na Página

```python
from src.utils.demo_helpers import (
    add_page_demo_warning,      # Alerta no topo
    create_demo_card,           # Card com badge
    create_demo_graph_card      # Gráfico com badge
)

def layout():
    return html.Div([
        # Alerta no topo da página
        add_page_demo_warning("/sua/pagina"),

        # Card com badge
        create_demo_card(
            title="Meu KPI",
            content=html.H2("123"),
            page_path="/sua/pagina"
        ),

        # Gráfico com badge
        create_demo_graph_card(
            title="Meu Gráfico",
            figure=fig,
            page_path="/sua/pagina"
        )
    ])
```

### 3️⃣ Desativar Quando Pronto

Quando os dados reais estiverem prontos:

```python
# Em config/demo_data_config.py
DEMO_PAGES = {
    "/sua/pagina": False,  # Badge desaparece automaticamente!
}
```

## 📁 Arquivos Criados

- ✅ `webapp/src/components/demo_badge.py` - Componente do badge
- ✅ `webapp/src/config/demo_data_config.py` - Configuração (liga/desliga badges)
- ✅ `webapp/src/utils/demo_helpers.py` - Funções helper (facilita uso)
- ✅ `webapp/src/assets/demo_badge.css` - Estilos visuais
- ✅ `webapp/DEMO_BADGES_GUIDE.md` - Guia completo com exemplos
- ✅ `webapp/DEMO_BADGES_EXAMPLE.py` - Exemplos práticos de código

## 🎨 Exemplos Visuais

### Cards KPI
```python
create_demo_card(
    title="OEE Total",
    content=html.H2("85.5%"),
    page_path="/production/oee"
)
```
**Resultado:** Card com badge "DADOS DE DEMONSTRAÇÃO" no header

### Gráficos
```python
create_demo_graph_card(
    title="Consumo por Hora",
    figure=fig,
    page_path="/energy/overview"
)
```
**Resultado:** Card com gráfico e badge no header

### Alerta de Página
```python
add_page_demo_warning("/production/oee")
```
**Resultado:** Alerta amarelo no topo da página

## 🔧 Controle Fino

### Por Página
```python
DEMO_PAGES = {
    "/production/oee": True,     # Ativo
    "/energy/overview": False,   # Desativado
}
```

### Global
```python
ENABLE_DEMO_BADGES = False  # Desativa TODOS os badges
```

### Por Componente (avançado)
```python
DEMO_COMPONENTS = {
    "graphs": {
        "oee_graph": True,
        "energy_graph": False,
    }
}
```

## 📚 Documentação Completa

- **Guia Completo:** `webapp/DEMO_BADGES_GUIDE.md`
- **Exemplos de Código:** `webapp/DEMO_BADGES_EXAMPLE.py`

## ✅ Checklist de Implementação

- [ ] Adicionar página em `config/demo_data_config.py`
- [ ] Importar funções de `utils.demo_helpers`
- [ ] Aplicar badges nos componentes
- [ ] Testar visualmente
- [ ] Quando pronto, mudar para `False` na config

## 🎯 Dica

Use sempre as **funções helper** - elas já integram tudo automaticamente:
- ✅ `create_demo_card()`
- ✅ `create_demo_graph_card()`
- ✅ `add_page_demo_warning()`

Evite criar badges manualmente (mais trabalhoso e menos consistente).

---

**Dúvidas?** Consulte `DEMO_BADGES_GUIDE.md` para exemplos detalhados.
