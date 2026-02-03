# 🔌 Sistema de Graceful Degradation - MongoDB

## 📋 Resumo

Este documento descreve o sistema implementado para permitir que a aplicação **continue funcionando mesmo quando o MongoDB está offline**, exibindo mensagens amigáveis aos usuários em vez de quebrar completamente.

---

## ❌ Problema Original

**Antes das mudanças:**

Quando o serviço MongoDB estava offline ou inacessível, a aplicação:
1. ❌ **Quebrava durante a inicialização** (não conseguia nem iniciar)
2. ❌ **Levantava exceção fatal** no `get_mongo_connection()`
3. ❌ **Não exibia nenhuma mensagem amigável** aos usuários
4. ❌ **Logs técnicos assustavam** os usuários finais

**Traceback típico:**
```
ConnectionError: Não foi possível conectar ao MongoDB: localhost:27017: [WinError 10061]
Nenhuma conexão pôde ser feita porque a máquina de destino as recusou ativamente
```

---

## ✅ Solução Implementada

### **1. Conexão Não-Fatal** (`database/connection.py`)

#### **Antes:**
```python
def get_mongo_connection(collection_name=None):
    # ...
    raise ConnectionError(f"Não foi possível conectar ao MongoDB: {e}")
```

#### **Depois:**
```python
def get_mongo_connection(collection_name=None, silent=False):
    # ...
    # Retorna None em vez de levantar exceção
    return None

# Novas funções adicionadas:
check_mongo_health()        # Verifica se MongoDB está acessível
reconnect_mongodb()         # Tenta reconectar ao MongoDB
get_connection_status()     # Retorna status atual (available, error)
```

**Mudanças principais:**
- ✅ Retorna `None` quando falha, em vez de levantar exceção fatal
- ✅ Armazena último erro em variável global `LAST_ERROR`
- ✅ Flag `MONGO_AVAILABLE` rastreia estado da conexão
- ✅ Parâmetro `silent=True` suprime logs (útil para health checks)
- ✅ Emojis nos logs: 🔄 (tentando), ✅ (sucesso), ❌ (falha), ⚠️ (aviso)

---

### **2. Componentes Visuais de Erro** (`components/database_error.py`)

Criados **3 componentes** React-like para exibir mensagens amigáveis:

#### **A) Página Inteira de Erro**
```python
create_database_error_layout(error_message, show_retry=True)
```

**Características:**
- 🔴 Ícone grande de banco de dados offline
- 📋 Mensagem principal amigável
- 🔽 Detalhes técnicos colapsáveis (escondidos por padrão)
- 🔄 Botão "Tentar Novamente" (reconecta e recarrega página)
- 💡 Instruções de troubleshooting

#### **B) Erro Inline (para cards/gráficos)**
```python
create_inline_database_error(component_name, error_message)
```

**Características:**
- Mensagem compacta para usar em cards
- Detalhes técnicos colapsáveis
- Sem botão de retry (economiza espaço)

#### **C) Gráficos de Erro** (`maintenance_kpi_graphs.py`)
```python
create_database_error_figure(kpi_name, error_message, template)
```

**Características:**
- Figura Plotly com fundo amarelo claro (alerta)
- Ícone 🔌 indicando desconexão
- Mensagem clara: "Banco de Dados Offline"
- Sugestão: "Verifique se o serviço está rodando"
- Detalhes técnicos truncados (primeiros 80 chars)

---

### **3. Callbacks Resilientes**

#### **A) Registro de Callbacks** (`callbacks.py`)

**Antes:**
```python
def register_callbacks(app):
    collection_graph = get_mongo_connection('DecapadoPerformance')  # Quebra aqui!
    collection_table = get_mongo_connection('DecapadoFalhas')
    # ...
```

**Depois:**
```python
def register_callbacks(app):
    print("\n🔌 Configurando conexões MongoDB...")

    collection_graph = get_mongo_connection('DecapadoPerformance', silent=False)
    collection_table = get_mongo_connection('DecapadoFalhas', silent=True)
    # Pode retornar None - callbacks lidam com isso!

    status = get_connection_status()
    if not status["available"]:
        print(f"\n⚠️  MongoDB OFFLINE - Aplicação iniciará em modo degradado")
        print(f"   ℹ️  Os usuários verão mensagens amigáveis")
```

**Mudanças:**
- ✅ Aceita `None` como retorno (não quebra)
- ✅ Imprime status claro no console
- ✅ Permite que aplicação inicie mesmo sem MongoDB

#### **B) Callbacks Individuais** (exemplo: `maintenance_kpi_callbacks.py`)

Todos os callbacks que usam MongoDB agora verificam o estado da conexão:

```python
@app.callback(...)
def process_filters_and_load_data(...):
    # ⚠️ VERIFICAÇÃO CRÍTICA: MongoDB disponível?
    db_status = get_connection_status()
    if not db_status["available"]:
        print(f"❌ [CALLBACK KPI] MongoDB offline - retornando erro")
        return {
            "has_data": False,
            "db_error": True,  # ← Flag para indicar erro de BD
            "error_message": db_status.get("error", "MongoDB indisponível"),
            # ... outros campos padrão
        }

    # Continuar normalmente se MongoDB estiver online
    # ...
```

**Callbacks de gráficos:**
```python
@app.callback(...)
def update_bar_charts(stored_data):
    # Verificar se há erro de banco de dados
    if stored_data.get("db_error"):
        print("❌ [DEBUG] MongoDB offline - retornando gráficos de erro")
        from src.components.maintenance_kpi_graphs import create_database_error_figure
        error_msg = stored_data.get("error_message", "Banco de dados offline")
        return [
            create_database_error_figure("MTBF", error_msg, template),
            create_database_error_figure("MTTR", error_msg, template),
            create_database_error_figure("Taxa de Avaria", error_msg, template)
        ]

    # Continuar normalmente se dados estiverem disponíveis
    # ...
```

---

### **4. Botão "Tentar Novamente"** (`database_error_callbacks.py`)

Implementado callback para reconectar ao MongoDB:

```python
@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    Output("store-db-reconnect-status", "data"),
    Input("btn-retry-database", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True
)
def retry_database_connection(n_clicks, current_path):
    print("🔄 Usuário solicitou reconexão ao MongoDB...")

    success = reconnect_mongodb()

    if success:
        print("✅ Reconexão bem-sucedida! Recarregando página...")
        return current_path, {"success": True, "timestamp": n_clicks}
    else:
        print(f"❌ Reconexão falhou")
        raise PreventUpdate
```

**Características:**
- Tenta reconectar ao MongoDB
- Se bem-sucedido: força reload da página atual
- Se falhar: mantém mensagem de erro visível
- Logs claros no console

---

## 🔄 Fluxo de Funcionamento

### **Cenário 1: MongoDB Offline na Inicialização**

```mermaid
Usuário inicia aplicação
  ↓
callbacks.py tenta conectar ao MongoDB
  ↓
get_mongo_connection() retorna None (sem exceção)
  ↓
callbacks.py imprime "⚠️ MongoDB OFFLINE - modo degradado"
  ↓
Aplicação INICIA normalmente ✅
  ↓
Usuário navega para /maintenance/indicators
  ↓
Callback verifica: get_connection_status() → {"available": False}
  ↓
Retorna dados com flag "db_error": True
  ↓
Gráficos exibem create_database_error_figure() 🔌
  ↓
Usuário clica "Tentar Novamente"
  ↓
reconnect_mongodb() → success = True
  ↓
Página recarrega automaticamente ✅
  ↓
Dados carregam normalmente 📊
```

### **Cenário 2: MongoDB Cai Durante Execução**

```mermaid
Aplicação rodando normalmente
  ↓
MongoDB cai (serviço para)
  ↓
Próximo callback que precisa de dados:
  ↓
get_mongo_connection() tenta conectar
  ↓
check_mongo_health() → False
  ↓
MONGO_AVAILABLE = False, LAST_ERROR = "erro de conexão"
  ↓
get_connection_status() → {"available": False, "error": "..."}
  ↓
Callback retorna dados com "db_error": True
  ↓
Gráficos exibem mensagem de erro 🔌
  ↓
[Usuário reinicia MongoDB]
  ↓
Usuário clica "Tentar Novamente"
  ↓
Página recarrega com dados ✅
```

---

## 📁 Arquivos Modificados

### **Novos Arquivos**
1. `webapp/src/components/database_error.py` - Componentes visuais de erro
2. `webapp/src/callbacks_registers/database_error_callbacks.py` - Callbacks de reconexão
3. `webapp/MONGODB_GRACEFUL_DEGRADATION.md` - Este documento

### **Arquivos Modificados**
1. `webapp/src/database/connection.py`
   - Função `get_mongo_connection()` - Não-fatal, retorna None
   - Nova função `check_mongo_health()` - Verifica saúde do MongoDB
   - Nova função `reconnect_mongodb()` - Reconecta ao MongoDB
   - Nova função `get_connection_status()` - Status atual
   - Variáveis globais: `MONGO_AVAILABLE`, `LAST_ERROR`

2. `webapp/src/components/stores.py`
   - Adicionado: `dcc.Store(id='store-db-reconnect-status')`

3. `webapp/src/callbacks.py`
   - Import: `get_connection_status, reconnect_mongodb`
   - Conexões não-fatais
   - Registro de `database_error_callbacks`
   - Logs informativos

4. `webapp/src/callbacks_registers/maintenance_kpi_callbacks.py`
   - Verificação de MongoDB no callback de filtros
   - Verificação de MongoDB nos gráficos de barras
   - Verificação nos summary cards
   - Retorno de `db_error` flag

5. `webapp/src/components/maintenance_kpi_graphs.py`
   - Nova função: `create_database_error_figure()`

---

## 🧪 Como Testar

### **Teste 1: MongoDB Offline na Inicialização**

1. **Parar o MongoDB:**
   ```bash
   # Windows
   net stop MongoDB

   # Linux/Mac
   sudo systemctl stop mongod
   ```

2. **Iniciar a aplicação:**
   ```bash
   cd webapp
   python run_local.py
   ```

3. **Verificar logs:**
   ```
   🔄 Tentando conectar ao MongoDB (URI: localhost:27017, DB: Cluster-EasyTek)...
   ❌ Falha na conexão: ...
   ⚠️  MongoDB OFFLINE - Aplicação iniciará em modo degradado
   ```

4. **Acessar no navegador:** `http://localhost:8050/maintenance/indicators`

5. **Verificar UI:**
   - ✅ Página carrega normalmente
   - ✅ Gráficos exibem ícone 🔌 e mensagem "Banco de Dados Offline"
   - ✅ Cards de resumo mostram "BD Offline" badge vermelho

### **Teste 2: Reconexão Bem-Sucedida**

1. **Com aplicação rodando e MongoDB offline (teste anterior)**

2. **Reiniciar MongoDB:**
   ```bash
   # Windows
   net start MongoDB

   # Linux/Mac
   sudo systemctl start mongod
   ```

3. **Na página de indicadores:**
   - Clicar no botão "Tentar Novamente" (se disponível)
   - OU clicar em "Atualizar" no header

4. **Verificar logs:**
   ```
   🔄 Usuário solicitou reconexão ao MongoDB...
   🔄 Tentando conectar ao MongoDB...
   ✅ Conexão com o MongoDB (DB: 'Cluster-EasyTek') estabelecida com sucesso!
   ✅ Reconexão bem-sucedida! Recarregando página...
   ```

5. **Verificar UI:**
   - ✅ Página recarrega automaticamente
   - ✅ Gráficos exibem dados reais 📊
   - ✅ Cards de resumo mostram valores corretos

### **Teste 3: MongoDB Cai Durante Execução**

1. **Com aplicação rodando e MongoDB online**

2. **Carregar dados normalmente** (deve funcionar)

3. **Parar MongoDB:**
   ```bash
   net stop MongoDB  # Windows
   ```

4. **Clicar em "Atualizar" ou mudar filtros**

5. **Verificar logs:**
   ```
   ❌ [CALLBACK KPI] MongoDB offline - retornando erro
   ❌ [DEBUG] MongoDB offline - retornando gráficos de erro
   ```

6. **Verificar UI:**
   - ✅ Gráficos mudam para estado de erro 🔌
   - ✅ Mensagem clara sobre banco offline
   - ✅ Aplicação não quebra

---

## 💡 Boas Práticas para Desenvolvedores

### **Ao criar novos callbacks que usam MongoDB:**

```python
from src.database.connection import get_connection_status

@app.callback(...)
def my_callback(inputs):
    # 1️⃣ SEMPRE verificar se MongoDB está disponível
    db_status = get_connection_status()
    if not db_status["available"]:
        # Retornar estado de erro apropriado
        return create_database_error_layout(db_status["error"])

    # 2️⃣ Continuar normalmente
    collection = get_mongo_connection("my_collection")
    if collection is None:
        # Double-check (se conexão caiu entre as verificações)
        return create_database_error_layout("Conexão perdida")

    # 3️⃣ Usar try-except para queries
    try:
        data = collection.find({...})
        return process_data(data)
    except Exception as e:
        print(f"❌ Erro ao buscar dados: {e}")
        return create_database_error_layout(str(e))
```

### **Padrão para retornar erros em callbacks de dados:**

```python
# Sempre incluir estas flags no retorno:
return {
    "has_data": False,
    "db_error": True,
    "error_message": db_status.get("error", "Erro desconhecido"),
    # ... outros campos com valores padrão seguros
}
```

### **Padrão para gráficos:**

```python
from src.components.maintenance_kpi_graphs import create_database_error_figure

if stored_data.get("db_error"):
    return create_database_error_figure("Nome do KPI", error_msg, template)
```

---

## 🚀 Melhorias Futuras

### **Curto Prazo**
- [ ] Adicionar retry automático em background (tentar reconectar a cada X segundos)
- [ ] Toast notification quando reconexão for bem-sucedida
- [ ] Indicador visual no header mostrando status do MongoDB (🟢/🔴)
- [ ] Página de health check: `/admin/health` com status de todos os serviços

### **Médio Prazo**
- [ ] Cache local de dados para funcionar offline por tempo limitado
- [ ] Fila de operações pendentes (escrever no MongoDB quando voltar)
- [ ] Logs estruturados (JSON) para melhor monitoramento
- [ ] Integração com sistema de alertas (email/Slack quando MongoDB cair)

### **Longo Prazo**
- [ ] Suporte a múltiplos bancos de dados (fallback automático)
- [ ] Dashboard de monitoramento de infraestrutura
- [ ] Métricas de uptime e disponibilidade
- [ ] Auto-scaling e redundância

---

## ⚠️ Notas Importantes

1. **Performance**: A verificação `get_connection_status()` é leve (apenas um ping), mas evite chamá-la em loops. Chame uma vez por callback.

2. **Segurança**: Os detalhes técnicos de erro são colapsados por padrão para não expor informações sensíveis aos usuários finais.

3. **Logs**: Todos os logs relacionados a MongoDB usam emojis para fácil identificação:
   - 🔄 Tentando conectar
   - ✅ Sucesso
   - ❌ Falha
   - ⚠️ Aviso

4. **Backward Compatibility**: Código antigo que espera exceptions de `get_mongo_connection()` pode precisar ser atualizado para verificar `None`.

---

## 🆘 Troubleshooting

### **"A aplicação ainda quebra ao iniciar"**

- Verifique se importou as mudanças em `database/connection.py`
- Confira se `.env` está configurado corretamente
- Veja os logs para identificar qual callback está levantando exceção

### **"Botão 'Tentar Novamente' não funciona"**

- Verifique se `store-db-reconnect-status` foi adicionado aos stores
- Confirme se `register_database_error_callbacks(app)` está sendo chamado
- Veja console do navegador para erros JavaScript

### **"Gráficos mostram 'Sem dados' em vez de erro de banco"**

- Confirme que o callback está verificando `stored_data.get("db_error")`
- Verifique se `create_database_error_figure` está sendo importado corretamente
- Confira se callback de filtros está retornando flag `"db_error": True`

---

## 📞 Suporte

Para questões sobre este sistema:
- **Documentação**: Este arquivo (`MONGODB_GRACEFUL_DEGRADATION.md`)
- **Código**: Ver arquivos listados na seção "Arquivos Modificados"
- **Logs**: Ativar `LOG_LEVEL=DEBUG` no `.env` para logs detalhados

---

**Implementado em:** 01/02/2026
**Versão:** 1.0
**Status:** ✅ Produção
