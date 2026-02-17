# Protótipo MVP Mobile - Passo a Passo

**Objetivo:** Validar que a autenticação Flask funciona com API REST
**Tempo estimado:** 2-3 horas
**Resultado:** Endpoint `/api/v1/ping` funcionando com autenticação via cookie

---

## 📋 Checklist de Tarefas

- [ ] **Passo 1:** Configurar cookies no Flask (10min)
- [ ] **Passo 2:** Criar estrutura da API (15min)
- [ ] **Passo 3:** Criar endpoint de teste (20min)
- [ ] **Passo 4:** Testar no navegador (10min)
- [ ] **Passo 5:** Criar endpoint de OEE (1-2h)
- [ ] **Passo 6:** Testar com dados reais (30min)

---

## 🔧 Passo 1: Configurar Cookies no Flask (10min)

### 1.1 Editar `webapp/src/app.py`

Adicionar configuração de cookies após a linha 30 (depois de `server.config.update(SECRET_KEY=SECRET_KEY)`):

```python
# webapp/src/app.py
# Linha 30 - Configuração existente
server.config.update(SECRET_KEY=SECRET_KEY)

# ADICIONAR AQUI (nova configuração de cookies)
server.config.update(
    # Cookies de sessão seguros
    SESSION_COOKIE_SAMESITE='Lax',      # Permite navegação cross-location no mesmo domínio
    SESSION_COOKIE_SECURE=True,         # Exige HTTPS (produção)
    SESSION_COOKIE_HTTPONLY=True,       # Proteção contra XSS
    SESSION_COOKIE_PATH='/',            # Cookie válido para todo o domínio
    SESSION_COOKIE_NAME='etd_session',  # Nome customizado (opcional)
)
```

### 1.2 Verificar mudanças

```bash
cd "E:\Projetos Python\AMG_Data\webapp"
git diff src/app.py
```

---

## 📦 Passo 2: Criar Estrutura da API (15min)

### 2.1 Criar diretório e arquivos

```bash
cd "E:\Projetos Python\AMG_Data\webapp\src"

# Criar diretório api
mkdir api
cd api

# Criar arquivos
New-Item -ItemType File -Name "__init__.py"
New-Item -ItemType File -Name "auth.py"
New-Item -ItemType File -Name "producao.py"
```

### 2.2 Criar Blueprint (`src/api/__init__.py`)

```python
# src/api/__init__.py
"""
API REST Blueprint para AMG_Data
Fornece endpoints JSON para consumo mobile
"""

from flask import Blueprint

# Blueprint principal da API v1
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Importar rotas (isso registra os endpoints)
from . import auth, producao
```

### 2.3 Criar endpoints de autenticação (`src/api/auth.py`)

```python
# src/api/auth.py
"""
Endpoints de autenticação e perfil de usuário
"""

from flask import jsonify
from flask_login import login_required, current_user
from . import api_bp


@api_bp.route('/ping', methods=['GET'])
@login_required
def ping():
    """
    Endpoint de teste simples.
    Retorna status OK se usuário estiver autenticado.
    """
    return jsonify({
        'status': 'ok',
        'message': 'API funcionando!',
        'user': current_user.username,
        'authenticated': True
    })


@api_bp.route('/user/profile', methods=['GET'])
@login_required
def get_user_profile():
    """
    Retorna perfil completo do usuário autenticado.
    """
    return jsonify({
        'username': current_user.username,
        'email': current_user.email,
        'level': current_user.level,
        'perfil': current_user.perfil,
    })


@api_bp.route('/user/permissions', methods=['GET'])
@login_required
def get_user_permissions():
    """
    Retorna permissões do usuário (para controle de acesso no mobile).
    """
    from src.config.access_control import ROUTE_ACCESS

    # Lista de rotas que o usuário pode acessar
    accessible_routes = []

    for route, config in ROUTE_ACCESS.items():
        min_level = config.get('min_level', 1)
        perfis = config.get('perfis', [])
        shared = config.get('shared', False)

        # Verificar se usuário tem acesso
        has_level = current_user.level >= min_level
        has_perfil = shared or (current_user.perfil in perfis)

        if has_level and has_perfil:
            accessible_routes.append(route)

    return jsonify({
        'user': current_user.username,
        'level': current_user.level,
        'perfil': current_user.perfil,
        'accessible_routes': accessible_routes
    })
```

### 2.4 Criar arquivo placeholder para produção (`src/api/producao.py`)

```python
# src/api/producao.py
"""
Endpoints de dados de produção (OEE, estados, alarmes)
"""

from flask import jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from . import api_bp


@api_bp.route('/producao/oee', methods=['GET'])
@login_required
def get_oee_data():
    """
    Retorna dados de OEE (placeholder por enquanto).

    Query params:
    - linha: Nome da linha de produção (ex: LCT08, LCT16)
    - data_inicio: Data inicial (ISO format)
    - data_fim: Data final (ISO format)
    """
    # TODO: Implementar lógica real de busca no MongoDB

    linha = request.args.get('linha', 'LCT08')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    # Por enquanto, retorna dados mockados
    return jsonify({
        'status': 'success',
        'data': {
            'linha': linha,
            'periodo': {
                'inicio': data_inicio,
                'fim': data_fim
            },
            'oee': {
                'valor': 78.5,
                'disponibilidade': 85.2,
                'performance': 92.1,
                'qualidade': 99.8
            },
            'message': 'DADOS MOCKADOS - Implementar lógica real'
        }
    })
```

---

## 🔗 Passo 3: Registrar Blueprint no Flask (5min)

### 3.1 Editar `webapp/src/app.py`

Adicionar import e registro do Blueprint **DEPOIS** da configuração do Flask-Login (após linha 79):

```python
# webapp/src/app.py

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'

# ADICIONAR AQUI - Registro da API REST
from src.api import api_bp
server.register_blueprint(api_bp)

# --- Rota para servir assets do volume de documentação ---
# (resto do código continua igual)
```

### 3.2 Verificar estrutura

```bash
cd "E:\Projetos Python\AMG_Data\webapp"
tree src/api /F
```

Deve mostrar:
```
src/api
│   __init__.py
│   auth.py
│   producao.py
```

---

## ✅ Passo 4: Testar Localmente (10min)

### 4.1 Iniciar aplicação

```bash
cd "E:\Projetos Python\AMG_Data\webapp"
python run_local.py
```

Aguardar mensagem:
```
[START] Iniciando servidor em http://localhost:8050
```

### 4.2 Fazer login

1. Abrir navegador: `http://localhost:8050`
2. Fazer login com suas credenciais
3. Verificar que está autenticado

### 4.3 Testar endpoint no navegador

Abrir **DevTools** (F12) → **Console** e executar:

```javascript
// Teste 1: Ping simples
fetch('/api/v1/ping', {
  credentials: 'include'
})
.then(r => r.json())
.then(data => {
  console.log('✅ PING:', data);
})
.catch(err => {
  console.error('❌ ERRO:', err);
});

// Teste 2: Perfil do usuário
fetch('/api/v1/user/profile', {
  credentials: 'include'
})
.then(r => r.json())
.then(data => {
  console.log('✅ PERFIL:', data);
})
.catch(err => {
  console.error('❌ ERRO:', err);
});

// Teste 3: Permissões
fetch('/api/v1/user/permissions', {
  credentials: 'include'
})
.then(r => r.json())
.then(data => {
  console.log('✅ PERMISSÕES:', data.accessible_routes);
})
.catch(err => {
  console.error('❌ ERRO:', err);
});
```

### 4.4 Resultado esperado

Console deve mostrar:

```json
✅ PING: {
  "status": "ok",
  "message": "API funcionando!",
  "user": "seu-usuario",
  "authenticated": true
}

✅ PERFIL: {
  "username": "seu-usuario",
  "email": "seu-email@empresa.com",
  "level": 2,
  "perfil": "manutencao"
}

✅ PERMISSÕES: [
  "/production/oee",
  "/maintenance/alarms",
  "/maintenance/indicators",
  ...
]
```

---

## 🧪 Passo 5: Testar Sem Autenticação (5min)

### 5.1 Fazer logout

Clicar no avatar no canto superior direito → Logout

### 5.2 Testar endpoint sem estar logado

Abrir **DevTools Console** novamente:

```javascript
fetch('/api/v1/ping', {
  credentials: 'include'
})
.then(r => {
  console.log('Status:', r.status);
  return r.text();
})
.then(data => {
  console.log('Resposta:', data);
});
```

### 5.3 Resultado esperado

```
Status: 401
Resposta: (redirecionamento para /login ou mensagem de não autorizado)
```

**Isso confirma que `@login_required` está funcionando!** ✅

---

## 📊 Passo 6: Implementar Endpoint Real de OEE (1-2h)

### 6.1 Editar `src/api/producao.py`

Substituir função `get_oee_data()` pela implementação real:

```python
# src/api/producao.py

from flask import jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from src.database.connection import get_mongo_connection


@api_bp.route('/producao/oee', methods=['GET'])
@login_required
def get_oee_data():
    """
    Retorna dados de OEE de uma linha de produção.

    Query params:
    - linha: Nome da linha (padrão: LCT08)
    - data_inicio: ISO format (padrão: 7 dias atrás)
    - data_fim: ISO format (padrão: hoje)
    """
    try:
        # Parâmetros da requisição
        linha = request.args.get('linha', 'LCT08')

        # Datas padrão (últimos 7 dias)
        data_fim = request.args.get('data_fim')
        data_inicio = request.args.get('data_inicio')

        if not data_fim:
            data_fim = datetime.now()
        else:
            data_fim = datetime.fromisoformat(data_fim)

        if not data_inicio:
            data_inicio = data_fim - timedelta(days=7)
        else:
            data_inicio = datetime.fromisoformat(data_inicio)

        # Buscar dados no MongoDB
        collection = get_mongo_connection('DecapadoPerformance')

        if collection is None:
            return jsonify({
                'status': 'error',
                'message': 'Banco de dados offline'
            }), 503

        # Query MongoDB
        query = {
            'linha': linha,
            'timestamp': {
                '$gte': data_inicio,
                '$lte': data_fim
            }
        }

        # Buscar documentos
        documentos = list(collection.find(query).sort('timestamp', -1).limit(100))

        # Calcular médias de OEE
        if documentos:
            oee_valores = [doc.get('OEE', 0) for doc in documentos if 'OEE' in doc]
            disp_valores = [doc.get('Disponibilidade', 0) for doc in documentos if 'Disponibilidade' in doc]
            perf_valores = [doc.get('Performance', 0) for doc in documentos if 'Performance' in doc]
            qual_valores = [doc.get('Qualidade', 0) for doc in documentos if 'Qualidade' in doc]

            oee_medio = sum(oee_valores) / len(oee_valores) if oee_valores else 0
            disp_media = sum(disp_valores) / len(disp_valores) if disp_valores else 0
            perf_media = sum(perf_valores) / len(perf_valores) if perf_valores else 0
            qual_media = sum(qual_valores) / len(qual_valores) if qual_valores else 0
        else:
            oee_medio = disp_media = perf_media = qual_media = 0

        # Preparar série temporal para gráfico
        serie_temporal = []
        for doc in documentos:
            serie_temporal.append({
                'timestamp': doc.get('timestamp').isoformat() if 'timestamp' in doc else None,
                'oee': doc.get('OEE', 0),
                'disponibilidade': doc.get('Disponibilidade', 0),
                'performance': doc.get('Performance', 0),
                'qualidade': doc.get('Qualidade', 0)
            })

        return jsonify({
            'status': 'success',
            'data': {
                'linha': linha,
                'periodo': {
                    'inicio': data_inicio.isoformat(),
                    'fim': data_fim.isoformat()
                },
                'resumo': {
                    'oee': round(oee_medio, 2),
                    'disponibilidade': round(disp_media, 2),
                    'performance': round(perf_media, 2),
                    'qualidade': round(qual_media, 2)
                },
                'serie_temporal': serie_temporal,
                'total_registros': len(documentos)
            }
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
```

### 6.2 Testar endpoint com dados reais

```javascript
// No console do navegador (após fazer login)
fetch('/api/v1/producao/oee?linha=LCT08', {
  credentials: 'include'
})
.then(r => r.json())
.then(data => {
  console.log('📊 OEE:', data.data.resumo);
  console.log('📈 Série temporal:', data.data.serie_temporal.length, 'pontos');
})
.catch(err => {
  console.error('❌ ERRO:', err);
});
```

### 6.3 Resultado esperado

```json
📊 OEE: {
  "oee": 78.5,
  "disponibilidade": 85.2,
  "performance": 92.1,
  "qualidade": 99.8
}
📈 Série temporal: 87 pontos
```

---

## 🎯 Passo 7: Validação Final (10min)

### Checklist de Validação

Execute cada teste e marque ✅:

- [ ] **Cookies configurados:** Inspecionar cookie no DevTools → Application → Cookies
  - Nome: `etd_session`
  - Path: `/`
  - HttpOnly: `true`
  - Secure: `true` (se HTTPS)
  - SameSite: `Lax`

- [ ] **Endpoint `/api/v1/ping` funciona** quando logado

- [ ] **Endpoint retorna 401** quando NÃO logado

- [ ] **Endpoint `/api/v1/user/profile`** retorna dados corretos

- [ ] **Endpoint `/api/v1/user/permissions`** retorna rotas acessíveis

- [ ] **Endpoint `/api/v1/producao/oee`** retorna dados reais do MongoDB

- [ ] **Logout invalida sessão** (endpoints retornam 401 após logout)

---

## 🚀 Próximos Passos (Após Protótipo Validado)

Com a API funcionando, você pode:

### **Opção A: Testar com Postman/Insomnia**
- Exportar cookie de sessão
- Criar collection de testes
- Validar todos os endpoints

### **Opção B: Criar Interface Mobile Simples**
1. Setup Next.js básico
2. Criar hook `useAuth()`
3. Criar página `/mobile/oee`
4. Integrar com API

### **Opção C: Deploy em Produção**
1. Commitar mudanças
2. Build de imagem Docker
3. Deploy no servidor
4. Configurar rota `/mobile` no NPM

---

## 📝 Troubleshooting

### Problema: `ModuleNotFoundError: No module named 'src.api'`

**Causa:** Blueprint não foi importado corretamente

**Solução:**
```bash
# Verificar estrutura
ls -la webapp/src/api/

# Deve mostrar __init__.py, auth.py, producao.py
```

### Problema: `401 Unauthorized` mesmo estando logado

**Causa 1:** Cookie não está sendo enviado

**Solução:**
```javascript
// Sempre usar credentials: 'include'
fetch('/api/v1/ping', {
  credentials: 'include'  // IMPORTANTE!
})
```

**Causa 2:** Configuração de cookies não foi aplicada

**Solução:**
```bash
# Reiniciar aplicação
Ctrl+C
python run_local.py
```

### Problema: `503 Service Unavailable` no endpoint de OEE

**Causa:** MongoDB offline

**Solução:**
```bash
# Verificar conexão MongoDB
# Ver logs da aplicação
```

### Problema: CORS error ao testar de outro domínio

**Solução:** Adicionar flask-cors (apenas para dev):

```bash
pip install flask-cors
```

```python
# src/app.py
from flask_cors import CORS
import os

if os.getenv('NODE_ENV') != 'production':
    CORS(server,
         supports_credentials=True,
         origins=['http://localhost:3000'])
```

---

## 📊 Métricas de Sucesso do Protótipo

- ✅ **Tempo de implementação:** < 3 horas
- ✅ **Autenticação funcionando:** Cookie trafega corretamente
- ✅ **API REST operacional:** Endpoints retornam JSON válido
- ✅ **Dados reais:** Integração com MongoDB funciona
- ✅ **Segurança:** `@login_required` bloqueia acesso não autenticado

**Se todos os itens acima estiverem ✅, o MVP mobile está VALIDADO!** 🎉

---

## 🎓 Aprendizados

Ao final deste protótipo, você terá:

1. ✅ Configurado cookies seguros no Flask
2. ✅ Criado estrutura de API REST modular
3. ✅ Implementado autenticação via `@login_required`
4. ✅ Integrado com MongoDB para dados reais
5. ✅ Validado que a arquitetura funciona

**Próxima etapa:** Criar interface mobile com Next.js que consome essa API! 🚀
