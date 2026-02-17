# Análise de Migração Mobile — AMG_Data / EasyTek-Data

**Data da Análise:** 2026-02-17
**Projeto:** AMG_Data (aplicação industrial Dash + Flask)
**Objetivo:** Viabilidade de criar interface mobile usando Next.js

---

## Contexto do Projeto

Aplicação industrial de monitoramento web chamada **AMG_Data / EasyTek-Data**.

- **Stack atual:** Flask + Dash (frontend e backend acoplados) + MongoDB
- **Infraestrutura:** HTTPS via Nginx
- **Escopo:** 9 linhas de produção + 4 subestações elétricas
- **Autenticação:** Flask-Login com usuários persistidos no MongoDB
- **Sessão:** Sessão padrão Flask (cookie-based, in-memory)

---

## Problema que Precisa Ser Resolvido

Acesso mobile à aplicação é ruim. A ideia é:

1. Detectar se o dispositivo é mobile
2. Servir páginas específicas para mobile, respeitando hierarquia de perfis e níveis de acesso existente
3. Fazer isso de forma sustentável, sem gambiarra

---

## Arquitetura Proposta (Strangler Fig Pattern)

Migração controlada e incremental, sem derrubar o sistema atual:

```
Fase 0 (atual):      Flask + Dash, tudo junto
Fase 1:              Criar /api/v1/* no Flask (endpoints REST)
Fase 2 (MVP):        Next.js só para mobile, consumindo a API
Fase 3 (futuro):     Next.js começa a substituir páginas Dash desktop
Fase 4 (eventual):   Dash desligado, só Next.js + API Flask
```

O projeto pode parar na **Fase 2** e já resolver o problema mobile sem comprometer nada.

---

## Estrutura de Pastas Proposta

```
AMG_Data/
├── webapp/                        ← Dash existente, NÃO MEXER
│   ├── src/
│   ├── run_local.py
│   └── requirements.txt
│
└── amg-mobile/                    ← Projeto Next.js NOVO
    ├── pages/
    │   ├── api/
    │   │   └── proxy/             ← chama o Flask como proxy
    │   └── mobile/
    │       ├── producao/
    │       └── energia/
    ├── components/
    └── package.json
```

---

# 📋 Análise Técnica Baseada no Código Real

## 1. **Configuração Atual do Flask-Login**

### ✅ O que foi encontrado:

**Localização**: `webapp/src/app.py` (linhas 75-78)

```python
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'
```

**User Loader**: `webapp/src/config/user_loader.py`
```python
@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)
```

### ⚠️ **Pontos Críticos Identificados:**

1. **Sessão padrão Flask** (in-memory cookie-based)
   - ❌ **NÃO usa** `flask-session` com backend externo
   - ❌ **NÃO usa** Redis ou MongoDB para sessões
   - ✅ Usa sessão padrão do Flask (armazenada em cookie assinado)

2. **Configurações de Cookie AUSENTES:**
   ```python
   # NÃO ENCONTRADO no código:
   # SESSION_COOKIE_SAMESITE
   # SESSION_COOKIE_SECURE
   # SESSION_COOKIE_HTTPONLY
   # SESSION_COOKIE_DOMAIN
   ```

3. **SECRET_KEY configurado corretamente:**
   - Carregado via `.env` (obrigatório, falha se não existir)
   - Usado para assinar cookies de sessão

---

## 2. **Configuração Atual do Nginx**

### ⚠️ **PROBLEMA CRÍTICO IDENTIFICADO:**

**Arquivo**: `nginx/nginx.conf`

```nginx
location / {
    proxy_pass http://node-red:1880;  # ⚠️ SÓ roteia para Node-RED!
}
```

### 🚨 **Situação Atual:**
- O Nginx **NÃO está roteando** para o Dash (porta 8050)
- Apenas Node-RED (1880) está exposto
- **O Dash não está acessível via Nginx**

### ✅ **Como o Dash é acessado hoje:**
- Porta: `8050` (definida em `run_local.py` e `src/run.py`)
- Host: `0.0.0.0` (aceita conexões externas)
- Acesso direto: `http://<IP>:8050` (sem proxy Nginx)

---

## 3. **Modelo de Usuário**

**Arquivo**: `webapp/src/database/connection.py`

### ✅ **Classe User:**

```python
class User:
    id          # ObjectId do MongoDB
    username    # Nome de usuário
    email       # E-mail
    password    # Hash pbkdf2:sha256
    level       # Nível vertical (1, 2, 3)
    perfil      # Perfil horizontal (manutencao, qualidade, producao, utilidades, admin, etc.)
```

### 🎯 **Sistema de Permissões Bidimensional:**
- **Vertical (level)**: 1=básico, 2=avançado, 3=admin
- **Horizontal (perfil)**: 8 perfis disponíveis
- ✅ **Totalmente compatível com o modelo mobile proposto**

---

## 4. **Cenário de Autenticação Identificado**

### 🔴 **PIOR CASO + Problemas Adicionais**

| Aspecto | Status Atual | Impacto |
|---------|-------------|---------|
| **Nginx não roteia Dash** | ❌ Só roteia Node-RED | Alto |
| **Sem configuração de cookie** | ❌ SameSite, Secure, Domain não definidos | Alto |
| **Sessão padrão Flask** | ⚠️ In-memory cookie | Médio |
| **Sem CORS configurado** | ❌ Não encontrado | Alto |

### 📊 **Análise de Viabilidade:**

#### **Opção A: Path-based routing (IDEAL)**
```nginx
location / {
    proxy_pass http://webapp:8050;  # Dash
}
location /mobile {
    proxy_pass http://amg-mobile:3000;  # Next.js
}
```

✅ **Vantagens:**
- Cookies funcionam automaticamente (mesmo domínio)
- Não precisa JWT
- Menor esforço de desenvolvimento

⚠️ **Requer:**
- Reconfigurar Nginx (adicionar roteamento do Dash)
- Configurar cookies corretamente:
  ```python
  server.config.update(
      SESSION_COOKIE_SAMESITE='Lax',
      SESSION_COOKIE_SECURE=True,  # Se usar HTTPS
      SESSION_COOKIE_HTTPONLY=True,
      SESSION_COOKIE_PATH='/'
  )
  ```

#### **Opção B: Subdomínio (SE Node-RED for necessário no root)**
```nginx
# app.empresa.com → Dash
# mobile.empresa.com → Next.js
# iot.empresa.com → Node-RED
```

❌ **Desvantagens:**
- Cookies não trafegam entre subdomínios
- **Exige implementar JWT** (+ 2-3 dias de trabalho)

---

## 5. **O que Precisa Ser Alterado no Flask**

### 🔧 **Mudanças Necessárias:**

#### **A. Configuração de Sessão (app.py)**
```python
server.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=True,  # Se HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_PATH='/',
    # SESSION_COOKIE_DOMAIN='.empresa.com'  # Só se usar subdomínios
)
```

#### **B. Criar API REST (novo arquivo: `api/v1/routes.py`)**
```python
from flask import Blueprint, jsonify
from flask_login import login_required, current_user

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

@api_bp.route('/producao/oee', methods=['GET'])
@login_required
def get_oee_data():
    # Reutilizar lógica existente de callbacks_registers/oeegraph_callback.py
    # Retornar JSON ao invés de componentes Dash
    return jsonify({...})

@api_bp.route('/user/profile', methods=['GET'])
@login_required
def get_user_profile():
    return jsonify({
        'username': current_user.username,
        'level': current_user.level,
        'perfil': current_user.perfil
    })
```

#### **C. Registrar Blueprint (app.py)**
```python
from api.v1.routes import api_bp
server.register_blueprint(api_bp)
```

#### **D. Configurar CORS (se Next.js em porta diferente durante dev)**
```python
from flask_cors import CORS

CORS(server,
     supports_credentials=True,
     origins=['http://localhost:3000'])  # Next.js dev
```

---

## 6. **Estimativa Real do MVP**

### 📅 **Timeline Baseada no Código Atual:**

| Fase | Tarefa | Tempo Estimado | Risco |
|------|--------|----------------|-------|
| **0. Preparação Nginx** | Adicionar roteamento Dash + configurar cookies | 2-3h | Baixo |
| **1. API REST** | Criar `/api/v1/producao/oee` + middleware auth | 1 dia | Baixo |
| **2. Next.js Setup** | Scaffold + configurar proxy/auth | 0.5 dia | Baixo |
| **3. Página Mobile OEE** | UI + integração API | 1 dia | Baixo |
| **4. Testes** | Cross-browser, mobile, autenticação | 0.5 dia | Médio |

### 🎯 **Total: 3-4 dias úteis** (assumindo Opção A - Path-based routing)

**Se precisar implementar JWT (Opção B): +2-3 dias**

---

## 7. **Riscos Escondidos Identificados**

### 🚨 **ALTO IMPACTO:**

1. **Nginx Atual Não Serve o Dash**
   - O Dash está acessível apenas via porta direta (8050)
   - Precisa adicionar roteamento no Nginx **antes** de qualquer coisa
   - **Risco:** Se Dash já está em produção, usuários podem estar acessando direto pela porta

2. **Sessão Não Configurada para Proxy**
   - Sem `X-Forwarded-*` headers configurados no Flask
   - Pode causar loops de redirecionamento ou erros de autenticação

3. **HTTPS/Certificado**
   - Se produção usa HTTPS (provável, já que mencionou Nginx)
   - `SESSION_COOKIE_SECURE=True` é **obrigatório**
   - Cookies não funcionarão em HTTP se flag estiver ativa

### ⚠️ **MÉDIO IMPACTO:**

4. **MongoDB Connection Singleton**
   - Padrão singleton em `connection.py` pode causar problemas com múltiplas workers Gunicorn
   - Recomendo migrar para `pymongo.MongoClient` com pooling nativo

5. **Sem Rate Limiting na API**
   - API REST exposta sem proteção contra abuso
   - Considere `flask-limiter` para `/api/*`

---

## 8. **Recomendações de Arquitetura**

### ✅ **Arquitetura Recomendada (Path-based):**

```
┌─────────────────────────────────────────┐
│         Nginx Reverse Proxy             │
│      (easytek.duckdns.org:443)          │
└──────────┬──────────────────────────────┘
           │
           ├─ / ──────────────► webapp:8050 (Dash Desktop)
           ├─ /mobile ────────► amg-mobile:3000 (Next.js Mobile)
           ├─ /api/v1/* ──────► webapp:8050 (API REST)
           └─ /node-red ──────► node-red:1880 (Node-RED)
```

### 🔐 **Fluxo de Autenticação:**

```
1. Usuário faz login no Dash (/login)
   └─ Flask-Login cria sessão com cookie assinado

2. Next.js faz fetch('/api/v1/producao/oee', {credentials: 'include'})
   └─ Cookie é enviado automaticamente (mesmo domínio)

3. Flask valida sessão via @login_required
   └─ Retorna JSON com dados ou 401 Unauthorized
```

---

## 9. **Checklist de Implementação**

### **Fase 0: Infraestrutura (CRÍTICO - FAZER PRIMEIRO)**

- [ ] Adicionar roteamento Dash no `nginx/nginx.conf`
- [ ] Mover Node-RED para `/node-red` path
- [ ] Configurar headers `X-Forwarded-*`
- [ ] Testar acesso Dash via Nginx
- [ ] Configurar cookies no `app.py`

### **Fase 1: API REST**

- [ ] Criar estrutura `webapp/src/api/v1/`
- [ ] Implementar endpoint `/api/v1/producao/oee`
- [ ] Implementar endpoint `/api/v1/user/profile`
- [ ] Adicionar CORS (dev only)
- [ ] Testar endpoints com Postman

### **Fase 2: Next.js Mobile**

- [ ] Criar projeto `amg-mobile/` com Next.js 14+
- [ ] Configurar autenticação (SessionProvider)
- [ ] Criar página `/mobile/producao/oee`
- [ ] Implementar detecção de device mobile (optional)
- [ ] Configurar build/deploy

### **Fase 3: Integração**

- [ ] Atualizar `nginx.conf` com roteamento `/mobile`
- [ ] Testar autenticação cross-app
- [ ] Validar permissões (level + perfil)
- [ ] Testes mobile (Chrome DevTools)

---

## 10. **Resposta às Perguntas Originais**

### ❓ **1. Qual cenário de autenticação se aplica?**
**PIOR CASO** - mas resolúvel com path-based routing (3-4 dias)

### ❓ **2. O cookie de sessão vai funcionar com Next.js no mesmo Nginx?**
✅ **SIM** - SE configurar:
- Path-based routing (`/mobile`)
- `SESSION_COOKIE_SAMESITE='Lax'`
- `credentials: 'include'` no fetch do Next.js

### ❓ **3. O que precisa ser alterado no Flask?**
1. Configurar cookies (5 linhas em `app.py`)
2. Criar API REST (`/api/v1/*`)
3. Adicionar CORS (dev only)

### ❓ **4. Estimativa real do MVP?**
**3-4 dias** (path-based) ou **6-7 dias** (subdomínio com JWT)

### ❓ **5. Algum risco escondido?**
🚨 **SIM** - Nginx não roteia Dash atualmente (precisa reconfigurar **primeiro**)

---

## 📝 **Próximos Passos Recomendados**

1. **URGENTE**: Verificar como Dash está sendo acessado em produção
   - Se via porta direta (8050) → pode quebrar ao adicionar Nginx
   - Se via Nginx → arquivo de config está desatualizado no repo

2. **Decisão de Arquitetura**: Path-based OU subdomínio?
   - Recomendo **path-based** (mais simples, menos risco)

3. **Protótipo Rápido** (1 dia):
   - Configurar Nginx corretamente
   - Criar 1 endpoint de teste `/api/v1/ping`
   - Criar página Next.js simples que chama o endpoint

---

## Dependências Atuais do Projeto

```
Flask==3.1.1
Flask-Login==0.6.3
dash==3.1.1
dash-bootstrap-components==2.0.3
pymongo==4.13.2
Werkzeug==3.1.3
gunicorn
```

**Nota:** Não usa `flask-session`, `flask-cors`, ou `pyjwt` atualmente.

---

## Arquivos-Chave Analisados

- `webapp/src/app.py` - Inicialização Flask + Dash
- `webapp/src/database/connection.py` - Modelo User e MongoDB
- `webapp/src/config/user_loader.py` - Flask-Login user_loader
- `nginx/nginx.conf` - Configuração atual do proxy reverso
- `webapp/requirements.txt` - Dependências Python
- `webapp/.env.example` - Variáveis de ambiente

---

**Conclusão:** O MVP é **viável** com 3-4 dias de desenvolvimento, mas requer reconfiguração crítica do Nginx antes de qualquer implementação. A arquitetura path-based é a mais simples e recomendada.
