# Remoção de Logs e Correção de IndentationErrors

**Data**: 2026-02-10
**Status**: ✅ Concluído
**Branch**: `feat/NewPlantKPI`

## Contexto

Os logs (print statements) estavam bagunçados e não estavam ajudando na depuração. Decisão tomada: deletar TODOS os logs do projeto para começar com logging organizado do zero.

## Problema Encontrado

Após remoção de aproximadamente 190 linhas de `print()` statements, a aplicação passou a apresentar múltiplos `IndentationError` devido a blocos vazios deixados para trás.

### Erro Principal
```
IndentationError: expected an indented block after 'if'/'else'/'try'/'except'/'for' statement
```

## Arquivos Afetados e Correções

### 1. `webapp/src/config/user_loader.py`
- **Linha 6**: Bloco if vazio após remoção de print
- **Correção**: Adicionado `pass` statement

### 2. `webapp/src/callbacks.py`
- **Linhas 62-64**: Blocos if/else vazios
- **Correção**: Adicionados `pass` statements em ambos os blocos

### 3. `webapp/src/callbacks_registers/maintenance_kpi_callbacks.py`
- **Linha 819**: Bloco except vazio
- **Correção**: Adicionado `pass` statement

### 4. `webapp/src/database/connection.py`
- **Linhas 67, 76**: Múltiplos blocos if vazios
- **Correção**: Adicionados `pass` statements

### 5. `webapp/src/utils/maintenance_demo_data.py`
- **Linha 171**: Bloco except vazio
- **Linha 237**: Bloco except vazio
- **Linha 273**: Bloco except vazio (dentro de try aninhado)
- **Linha 294**: Bloco except vazio (dentro de try aninhado)
- **Correção**: Adicionados `pass` statements em todos

### 6. `webapp/src/utils/zpp_kpi_calculator.py`
- **Linhas 238-239**: Blocos if/else vazios (2 ocorrências - usamos replace_all)
- **Linhas 765-767**: F-strings soltas sem função (restos de print removido)
  ```python
  # Antes (QUEBRADO):
  for month_data in kpi_data[first_equipment]:
        f"MTBF={month_data['mtbf']}h, "
        f"MTTR={month_data['mttr']}h, "
        f"Taxa={month_data['breakdown_rate']}%")

  # Depois (CORRETO):
  for month_data in kpi_data[first_equipment]:
      pass
  ```
- **Linha 759**: Bloco for vazio
- **Linha 770**: Bloco except vazio
- **Correção**: Substituídos f-strings por `pass`, adicionados `pass` nos blocos vazios

## Script Criado

**Arquivo**: `fix_empty_blocks.py` (raiz do projeto)

Script Python que automaticamente detecta e corrige blocos vazios em arquivos Python:
- Detecta blocos que terminam com `:` (if/elif/else/try/except/finally/for/while)
- Verifica se próxima linha tem mesma ou menor indentação
- Adiciona `pass` automaticamente com indentação correta

### Arquivos Listados no Script
```python
files_to_fix = [
    'webapp/src/callbacks.py',
    'webapp/src/callbacks_registers/maintenance_kpi_callbacks.py',
    'webapp/src/database/connection.py',
    'webapp/src/utils/maintenance_demo_data.py'
]
```

## Processo de Correção

1. ✅ Primeiro erro: `user_loader.py` - corrigido manualmente
2. ✅ Criado script `fix_empty_blocks.py` para automatizar
3. ✅ Script corrigiu 4 arquivos automaticamente
4. ✅ Erros restantes em `maintenance_demo_data.py` - corrigidos manualmente (linhas 237, 273, 294)
5. ✅ Erro de sintaxe em `zpp_kpi_calculator.py` linha 767 - f-strings soltos removidos
6. ✅ Múltiplos IndentationErrors em `zpp_kpi_calculator.py` - corrigidos com replace_all
7. ✅ Aplicação iniciou com sucesso

## Verificação Final

```bash
# Teste de compilação
cd webapp/src && python -m py_compile run.py app.py callbacks.py \
  database/connection.py utils/maintenance_demo_data.py \
  callbacks_registers/maintenance_kpi_callbacks.py config/user_loader.py \
  components/maintenance_kpi_graphs.py

# Teste de inicialização
cd webapp && python run_local.py
```

**Resultado**: ✅ Aplicação iniciou com sucesso na porta 8050

## Logs da Aplicação

```
[OK] Variaveis de ambiente carregadas com sucesso!
   - MongoDB: localhost:27017
   - Database: Cluster-EasyTek
   - Gateway: http://localhost:5001

[START] Iniciando servidor em http://localhost:8050

Dash is running on http://0.0.0.0:8050/
```

## Correção Adicional: Logs Poluídos do PyMongo

**Data**: 2026-02-10 (continuação)
**Status**: ✅ Concluído

### Problema
Após remoção dos prints, os logs ainda estavam poluídos com mensagens DEBUG do PyMongo:
- `pymongo.serverSelection`
- `pymongo.connection`
- `pymongo.command`
- `pymongo.topology`

Centenas de linhas de logs DEBUG tornando a saída ilegível.

### Causa Raiz
1. Múltiplos callbacks configurando `logging.basicConfig()` com nível DEBUG
2. Sem configuração centralizada de logging
3. PyMongo herdando o nível DEBUG e emitindo logs verbosos

### Solução Implementada

#### 1. Configuração Centralizada de Logging
**Arquivo criado**: `webapp/src/config/logging_config.py`
- Nível geral: INFO (configurável via `LOG_LEVEL` env var)
- PyMongo: WARNING (silencia logs DEBUG/INFO)
- Werkzeug: INFO (mantém logs de requisições HTTP)
- Formato padronizado: `%(asctime)s [%(levelname)s] %(name)s - %(message)s`

#### 2. Inicialização no Entry Point
**Arquivos modificados**:
- `webapp/run_local.py`: Setup de logging ANTES das importações
- `webapp/src/run.py`: Setup de logging ANTES de importar app

#### 3. Remoção de Configurações Duplicadas
**Arquivos limpos** (removido `logging.basicConfig`):
- `callbacks_registers/energygraph_callback.py`
- `callbacks_registers/hourlyconsumption_callback.py`
- `callbacks_registers/autoupdatetoggle_callback.py`
- `callbacks_registers/input_bridge_callbacks.py`
- `callbacks_registers/kpicards_callback.py`
- `callbacks_registers/msgtable_callback.py`
- `callbacks_registers/oeegraph_callback.py`
- `callbacks_registers/tempgraph_callback.py`

Todos agora usam apenas `logger = logging.getLogger(__name__)`.

### Resultado
✅ Logs limpos e legíveis
✅ PyMongo silenciado (apenas WARNING+)
✅ Configuração centralizada e consistente
✅ Nível de log configurável via variável de ambiente

## Bug Fix: TypeError em Cálculo de Médias KPI

**Data**: 2026-02-10 (continuação)
**Status**: ✅ Concluído

### Problema
```
TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'
```

**Localização**: `maintenance_kpi_callbacks.py:1332`

### Causa
Listas `mtbf_values`, `mttr_values`, `breakdown_values` continham valores `None` misturados com floats. A função `sum()` não consegue somar quando há `None` na lista.

### Solução
**Arquivo**: `maintenance_kpi_callbacks.py` (linhas 1330-1350)

Adicionada filtragem de valores `None` antes de calcular médias:
```python
# Filtra None antes de calcular médias
mtbf_values_clean = [v for v in mtbf_values if v is not None]
mttr_values_clean = [v for v in mttr_values if v is not None]
breakdown_values_clean = [v for v in breakdown_values if v is not None]

eq_summary = {
    "mtbf": sum(mtbf_values_clean) / len(mtbf_values_clean) if mtbf_values_clean else 0,
    # ...
}
```

Mesmo tratamento aplicado para `general_summary` (médias da planta).

### Resultado
✅ Callback não quebra mais quando equipamento tem meses sem dados
✅ Médias calculadas apenas com valores válidos
✅ Fallback para 0 quando não há dados válidos

## Pendências

### Próxima Tarefa
**Investigar problema do callback da aba individual** (reportado antes da remoção de logs):
- Últimos 6 outputs do callback #3 não atualizam no carregamento da página
- Só atualizam quando muda o dropdown de equipamento
- Primeiros 2 cards (top paradas e gauges) funcionam normalmente
- Todos os callbacks têm Inputs idênticos (`store-indicator-filters` data + dropdown value)
- Possível causa: erro silencioso ou ordem de registro

## Sistema de Logging Estruturado

**Data**: 2026-02-10 (continuação)
**Status**: ✅ Implementado (Fase 1)

### Estrutura Criada

```
logs/
├── app.log              # Log geral (INFO+) - rotação 10MB
├── errors.log           # Apenas erros (ERROR+) - rotação 10MB
└── maintenance.log      # Módulo manutenção - rotação 5MB
```

### Configuração

**Arquivo**: `webapp/src/config/logging_config.py`
- Logs organizados por módulo
- Rotação automática (evita disco cheio)
- Debug seletivo via variáveis de ambiente

**Variáveis de Ambiente** (`.env`):
```bash
LOG_LEVEL=INFO           # Nível geral
DEBUG_MAINTENANCE=0      # Debug detalhado manutenção
DEBUG_KPI_CALC=0         # Debug cálculos KPI
```

### Módulos Configurados (Manutenção)

✅ `src.callbacks_registers.maintenance_kpi_callbacks`
✅ `src.utils.zpp_kpi_calculator`
✅ `src.utils.maintenance_demo_data`
✅ `src.components.maintenance_kpi_graphs`

### Como Usar

```bash
# Ver logs de manutenção em tempo real
tail -f logs/maintenance.log

# Ver apenas erros
tail -f logs/errors.log

# Filtrar por equipamento
grep "LONGI001" logs/maintenance.log

# Ativar debug para manutenção (editar .env)
DEBUG_MAINTENANCE=1
# Reiniciar aplicação
```

### Evolução Futura

✅ **Fase 1** - Logs em arquivos + debug seletivo (IMPLEMENTADO)
📋 **Fase 2** - Página web `/admin/logs` para visualização
📋 **Fase 3** - Grafana Loki ou Portainer (produção)

---

## 📘 Procedimento: Como Adicionar Logs

### 1. Em Callbacks

```python
# No início do arquivo
import logging

logger = logging.getLogger(__name__)

def register_example_callbacks(app):
    @app.callback(...)
    def update_data(input1, input2):
        # Início (DEBUG)
        logger.debug("Callback iniciado: input1=%s, input2=%s", input1, input2)

        # Validação (WARNING se problema)
        if not input1:
            logger.warning("Input vazio, retornando estado padrão")
            return default_state

        # Operação importante (INFO)
        logger.info("Processando %d registros para %s", len(data), input1)

        # Erro (ERROR com contexto)
        try:
            result = process_data(input1)
        except Exception as e:
            logger.error(
                "Erro ao processar %s: %s",
                input1, str(e),
                exc_info=True  # ← Inclui stack trace
            )
            return error_state

        # Sucesso (INFO resumido)
        logger.info("Processamento concluído: %d itens", len(result))
        return result
```

### 2. Em Funções Utilitárias

```python
import logging

logger = logging.getLogger(__name__)

def calculate_mtbf(equipment_id, data):
    logger.debug("Calculando MTBF para %s com %d registros",
                 equipment_id, len(data))

    if not data:
        logger.warning("Sem dados para calcular MTBF: %s", equipment_id)
        return None

    try:
        # Cálculo...
        result = total_hours / failures
        logger.info("MTBF calculado para %s: %.2f horas",
                   equipment_id, result)
        return result
    except ZeroDivisionError:
        logger.error("Divisão por zero ao calcular MTBF: %s", equipment_id)
        return 0
```

### 3. Níveis de Log - Quando Usar

| Nível | Uso | Exemplo |
|-------|-----|---------|
| **DEBUG** | Detalhes para troubleshooting | `logger.debug("Query: %s", query)` |
| **INFO** | Fluxo normal da aplicação | `logger.info("Usuário %s autenticado", user)` |
| **WARNING** | Inesperado mas recuperável | `logger.warning("Nenhum dado encontrado")` |
| **ERROR** | Erro que impede operação | `logger.error("Falha ao calcular: %s", e)` |
| **CRITICAL** | Erro grave (app inteira) | `logger.critical("MongoDB inacessível")` |

### 4. Adicionar Novo Módulo aos Logs

**Editar**: `webapp/src/config/logging_config.py`

```python
# Seção: MÓDULOS DA APLICAÇÃO

# === NOVO MÓDULO ===
novo_handler = RotatingFileHandler(
    logs_dir / "novo_modulo.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding='utf-8'
)
novo_handler.setFormatter(standard_formatter)
novo_handler.setLevel(logging.INFO)

# Adicionar aos loggers necessários
logging.getLogger("src.callbacks_registers.novo_callback").addHandler(novo_handler)
```

**Adicionar debug seletivo**:

```python
# Seção: DEBUG SELETIVO

debug_modules = {
    # ... existentes ...
    "DEBUG_NOVO_MODULO": "src.callbacks_registers.novo_callback",
}
```

**Atualizar `.env.example`**:
```bash
# Novo módulo
DEBUG_NOVO_MODULO=0
```

### 5. Evitar

```python
# ❌ Logs demais em loops
for item in large_list:  # 10k items
    logger.debug(f"Processing {item}")  # ← 10k linhas!

# ✅ Melhor
logger.debug("Processing %d items", len(large_list))
logger.info("Processed %d items successfully", processed_count)


# ❌ Informação sensível
logger.info(f"Password: {password}")

# ✅ Melhor
logger.info("User authenticated: %s", username)


# ❌ F-strings com cálculos pesados
logger.info(f"Result: {expensive_calculation()}")  # ← Calcula sempre!

# ✅ Melhor
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("Result: %s", expensive_calculation())
```

### 6. Ferramentas Úteis

```bash
# Ver logs em tempo real
tail -f logs/app.log

# Filtrar e seguir
tail -f logs/app.log | grep "ERRO"

# Últimos 100 erros
tail -n 100 logs/errors.log

# Contar erros por tipo
grep ERROR logs/app.log | cut -d'-' -f2 | sort | uniq -c | sort -rn

# Logs de hoje
grep "$(date +%d/%m/%Y)" logs/app.log

# Ver contexto de um erro
grep -A 10 -B 5 "TypeError" logs/errors.log
```

---

## Lições Aprendidas

1. **Remoção de código**: Sempre verificar blocos vazios deixados para trás
2. **Automação**: Script `fix_empty_blocks.py` pode ser útil no futuro
3. **Testes**: Compilação + inicialização antes de commit
4. **F-strings soltas**: Não são válidas em Python - sempre precisam estar dentro de uma função/statement
5. **Logging estruturado**: Facilita debug e evolução incremental sem refatoração

## Comandos para Commit

```bash
git add -A
git status

git commit -m "fix(logs): Corrigir IndentationErrors após remoção de logs

- Adicionados pass statements em blocos if/else/try/except vazios
- Arquivos corrigidos:
  * callbacks.py (linhas 62-64)
  * maintenance_kpi_callbacks.py (linha 819)
  * user_loader.py (linha 6)
  * connection.py (linhas 67, 76)
  * maintenance_demo_data.py (linhas 171, 237, 273, 294)
  * zpp_kpi_calculator.py (linhas 238-239, 765-767, 759)
- Criado fix_empty_blocks.py para automatizar correções futuras
- Removidos f-strings soltos sem função em zpp_kpi_calculator.py

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

## Arquivos para Commit

```
M  webapp/src/callbacks.py
M  webapp/src/callbacks_registers/maintenance_kpi_callbacks.py
M  webapp/src/config/user_loader.py
M  webapp/src/database/connection.py
M  webapp/src/utils/maintenance_demo_data.py
M  webapp/src/utils/zpp_kpi_calculator.py
A  fix_empty_blocks.py
A  devdocs/divida_tecnica/2026-02-10_remocao_logs_indentacao.md
```
