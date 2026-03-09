# Dívida Técnica — Performance da Webapp

**Data:** 2026-03-09
**Prioridade:** ALTA ⚠️
**Impacto:** Latência, concorrência e estabilidade
**Módulo:** Transversal (connection.py, index.py, manage_users.py, Dockerfile)
**Status:** Identificado — aguardando implementação

---

## Contexto

Análise arquitetural de 2026-03-09 identificou 5 problemas de performance na webapp.
Alguns são correções simples (1-2h), outros requerem planejamento de migração.

---

## 1. Eliminar `ping` obrigatório em `get_mongo_connection()` 🔴 Alta

### Problema

`get_mongo_connection()` chama `check_mongo_health()` (que executa um `ping` no MongoDB)
em **toda chamada**, mesmo quando a conexão já está estabelecida e saudável:

```python
# connection.py linha 99 — executa em TODA chamada
if not check_mongo_health():
    client = None
    db = None
    return get_mongo_connection(collection_name, silent)

return db[collection_name]
```

Com 31 pontos no código chamando `get_mongo_connection()`, cada ciclo de interação
do usuário dispara múltiplos pings antes de qualquer query real. Latência pura.

Os callbacks de energia (`energygraph_callback.py`, `hourlyconsumption_callback.py`)
ainda fazem **um ping extra próprio** por cima disso.

### Solução

Remover o `check_mongo_health()` do caminho feliz. Verificar conexão apenas quando
`client is None`. Deixar o PyMongo lidar com reconexão automática (ele já faz isso).

```python
def get_mongo_connection(collection_name=None, silent=False):
    global client, db, MONGO_AVAILABLE, LAST_ERROR

    if client is None:
        # ... lógica de conexão inicial (mantida)

    # ← REMOVER: if not check_mongo_health(): ...

    if db is not None:
        return db[collection_name] if collection_name else db

    return None
```

Remover também os pings manuais em `energygraph_callback.py` e `hourlyconsumption_callback.py`.

### Arquivos afetados

- `webapp/src/database/connection.py`
- `webapp/src/callbacks_registers/energygraph_callback.py`
- `webapp/src/callbacks_registers/hourlyconsumption_callback.py`

### Estimativa

- **Esforço:** 1-2 horas
- **Complexidade:** Baixa
- **Ganho:** Redução de latência em toda interação com MongoDB

---

## 2. `refresh-users-table` — atualizar só após ação 🔴 Alta

### Problema

A página `manage_users` tem um `dcc.Interval` de **5 segundos** que recarrega a tabela
de usuários continuamente, mesmo sem nenhuma alteração:

```python
# manage_users.py linha 47
dcc.Interval(id="refresh-users-table", interval=5000, n_intervals=0)
```

Isso significa 12 queries MongoDB por minuto por usuário com a página aberta,
sem nenhum benefício real — a tabela de usuários raramente muda.

### Solução

Eliminar o `dcc.Interval`. Disparar recarregamento da tabela apenas como efeito
colateral das ações que realmente modificam dados:

- **Edição de usuário** → após salvar, recarregar tabela
- **Reset de senha** → após confirmar, recarregar tabela
- **Deletar usuário** → após confirmar exclusão, recarregar tabela

Usar `Output('tabela-usuarios', 'data')` nos callbacks de cada ação já existentes,
ao invés de um timer separado.

### Arquivos afetados

- `webapp/src/pages/admin/manage_users.py`
- `webapp/src/callbacks_registers/manage_users_callbacks.py`

### Estimativa

- **Esforço:** 2-3 horas
- **Complexidade:** Baixa-Média
- **Ganho:** Elimina 12 queries/min por usuário admin com a página aberta

---

## 3. Eliminar `interval-component` global de 10s 🟡 Média

### Problema

`index.py` define um `dcc.Interval` global que dispara a cada **10 segundos**
em todas as páginas, para todos os usuários logados:

```python
# index.py linha 324
dcc.Interval(id='interval-component', interval=10 * 1000, n_intervals=0, disabled=False)
```

Com 5 usuários simultâneos: **30 callbacks/minuto** disparados automaticamente,
consumindo workers Gunicorn mesmo sem interação do usuário.

### Investigar primeiro

Mapear quais callbacks dependem de `interval-component` e qual é a finalidade real
de cada um. Pode haver auto-refresh legítimo em páginas específicas (ex: supervisão SCADA).

### Solução

- Remover o `interval-component` global de `index.py`
- Para páginas que precisam de auto-refresh (ex: supervisão), criar um `dcc.Interval`
  **local** na própria página, com `disabled=True` por padrão e habilitado apenas
  quando a página estiver ativa
- Avaliar se o auto-refresh pode ser substituído por um botão "Atualizar" manual
  nas páginas que não são de monitoramento em tempo real

### Arquivos afetados

- `webapp/src/index.py`
- Todos os `callbacks_registers/` que usam `Input('interval-component', 'n_intervals')`

### Estimativa

- **Esforço:** 3-5 horas (mapeamento + refatoração)
- **Complexidade:** Média
- **Ganho:** Elimina carga de fundo constante proporcional ao número de usuários

---

## 4. Migrar para workers async (Gunicorn + gevent) 🟡 Média

### Problema

O Dockerfile configura Gunicorn com 4 workers síncronos:

```dockerfile
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8050", "src.run:server"]
```

Workers síncronos bloqueiam durante queries MongoDB. Com callbacks de KPI que
podem levar 2-5 segundos (agregações em coleções grandes), o 5º usuário simultâneo
aguarda na fila. Os `dcc.Interval` ativos agravam isso ao consumir workers
automaticamente.

### Plano de migração

**Fase 1 — Testar com gevent (baixo risco):**

```dockerfile
# Instalar gevent no requirements.txt
# gevent==23.9.1

CMD ["gunicorn", \
     "--workers", "4", \
     "--worker-class", "gevent", \
     "--worker-connections", "100", \
     "--bind", "0.0.0.0:8050", \
     "src.run:server"]
```

gevent usa green threads — compatível com Flask/Dash sem mudança de código.
Permite que um worker atenda múltiplas requisições enquanto aguarda I/O (MongoDB).

**Fase 2 — Ajustar número de workers:**

Com gevent, menos workers são necessários (I/O não bloqueia):
```
workers = 2 * CPU_cores + 1  # fórmula padrão para sync
# Com gevent: 2-4 workers com 100 connections cada são suficientes
```

**Fase 3 — Monitorar:**

Acompanhar tempo de resposta e uso de memória após migração. gevent
tem overhead menor por conexão comparado a threads nativas.

### Pré-requisitos

- Verificar compatibilidade de todas as bibliotecas com gevent (PyMongo ✅, Flask ✅, Dash ✅)
- Testar localmente antes de aplicar em produção

### Arquivos afetados

- `AMG_Data/webapp/Dockerfile`
- `AMG_Data/webapp/requirements.txt` (adicionar gevent)

### Estimativa

- **Esforço:** 3-4 horas (instalação + teste + validação)
- **Complexidade:** Média
- **Ganho:** Capacidade de concorrência muito maior sem adicionar servidores

---

## 5. Resolver reconexão recursiva em `get_mongo_connection()` 🟡 Média

### Problema

Quando `check_mongo_health()` detecta falha, o código zera o cliente e chama
a si mesmo recursivamente:

```python
# connection.py linhas 100-105
if not check_mongo_health():
    client = None
    db = None
    return get_mongo_connection(collection_name, silent)  # ← recursão
```

Se o MongoDB ficar instável por alguns segundos e múltiplos callbacks
dispararem simultaneamente (ex: `interval-component` + interação do usuário),
cada worker Gunicorn entra em loop de reconexão ao mesmo tempo — tempestade
de conexões simultâneas no MongoDB.

### Solução

Substituir a recursão por retry explícito com backoff e tentativas limitadas:

```python
def get_mongo_connection(collection_name=None, silent=False, _retry=False):
    global client, db, MONGO_AVAILABLE, LAST_ERROR

    if client is None:
        mongo_uri = os.getenv('MONGO_URI')
        db_name = os.getenv('DB_NAME')

        if not mongo_uri or not db_name:
            MONGO_AVAILABLE = False
            return None

        try:
            client = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000,
            )
            client.admin.command('ping')
            db = client[db_name]
            MONGO_AVAILABLE = True
            LAST_ERROR = None

        except Exception as e:
            client = None
            db = None
            MONGO_AVAILABLE = False
            LAST_ERROR = str(e)
            return None

    if db is not None:
        return db[collection_name] if collection_name else db

    return None
```

Adicionalmente, adicionar `socketTimeoutMS` e `connectTimeoutMS` explícitos
para evitar que queries travem indefinidamente em caso de instabilidade de rede.

### Arquivos afetados

- `webapp/src/database/connection.py`

### Estimativa

- **Esforço:** 2-3 horas
- **Complexidade:** Média
- **Ganho:** Estabilidade em cenários de instabilidade do MongoDB

---

## Ordem de Execução Recomendada

| # | Item | Esforço | Impacto | Fazer primeiro? |
|---|------|---------|---------|-----------------|
| 1 | Eliminar ping | 1-2h | Alto | ✅ Sim |
| 2 | refresh-users-table | 2-3h | Médio | ✅ Sim |
| 3 | Reconexão recursiva | 2-3h | Médio | ✅ Sim |
| 4 | interval-component global | 3-5h | Médio | Após mapear dependências |
| 5 | Workers async (gevent) | 3-4h | Alto | Após itens 1-3 |

Itens 1, 2 e 3 são independentes e podem ser feitos em qualquer ordem.
Item 5 (gevent) tem maior impacto em concorrência e deve ser validado em
ambiente local antes de aplicar em produção.
