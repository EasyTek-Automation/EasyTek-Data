# Arquitetura Real do Nginx Proxy Manager

**Data:** 2026-02-17
**Infraestrutura:** AMG_Infra (repositório separado)

---

## 🏗️ Arquitetura Atual

```
Internet (HTTPS)
    │
    ├─ etd.easytek-data.com.br ──────────► webapp:8050 (Dash/Flask)
    ├─ etdnr.easytek-data.com.br ────────► node-red:1880
    ├─ etdportainer.easytek-data.com.br ─► portainer:9443 (HTTPS)
    └─ etdngx.easytek-data.com.br ───────► nginx-proxy-manager:81 (UI)
```

**Rede Docker:** `easytek-net` (bridge externa)

---

## 📋 Hosts Configurados no NPM

| ID | Domínio | Destino | SSL | WebSockets | HTTP/2 |
|----|---------|---------|-----|------------|--------|
| 2 | `etd.easytek-data.com.br` | `webapp:8050` | ✅ | ✅ | ❌ |
| 3 | `etdnr.easytek-data.com.br` | `node-red:1880` | ✅ | ✅ | ❌ |
| 4 | `etdportainer.easytek-data.com.br` | `portainer:9443` | ✅ | ✅ | ✅ |
| 5 | `etdngx.easytek-data.com.br` | `nginx-proxy-manager:81` | ✅ | ✅ | ❌ |

---

## 🔐 Configurações de Segurança

### SSL/TLS
- **Certificado:** Let's Encrypt (wildcard `npm-1`)
- **Force SSL:** ✅ Habilitado em todos os hosts
- **HSTS:** ✅ Habilitado (2 anos) no Portainer
- **Ciphers:** Configuração segura via `ssl-ciphers.conf`

### Headers de Proxy
```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $http_connection;
proxy_http_version 1.1;
```

**Isso garante:**
- ✅ WebSockets funcionando (importante para Dash callbacks)
- ✅ HTTP/1.1 (necessário para keep-alive)

---

## ✅ Implicações para o Projeto Mobile

### 🎯 **MELHOR CENÁRIO CONFIRMADO!**

| Aspecto | Status | Impacto Mobile |
|---------|--------|----------------|
| **Mesmo domínio** | ✅ `etd.easytek-data.com.br` | Cookies funcionam automaticamente |
| **SSL habilitado** | ✅ Let's Encrypt | `SESSION_COOKIE_SECURE=True` funcionará |
| **WebSockets ativos** | ✅ Upgrade headers | Dash callbacks funcionam |
| **Rede Docker** | ✅ `easytek-net` | Containers se comunicam por nome |
| **HTTP/2 disponível** | ✅ No Portainer | Pode habilitar para mobile se necessário |

---

## 📝 Configuração do Host Principal (webapp)

**Arquivo:** `/data/nginx/proxy_host/2.conf`

```nginx
server {
  set $forward_scheme http;
  set $server         "webapp";
  set $port           8050;

  listen 80;
  listen [::]:80;
  listen 443 ssl;
  listen [::]:443 ssl;

  server_name etd.easytek-data.com.br;

  # SSL
  ssl_certificate /etc/letsencrypt/live/npm-1/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/npm-1/privkey.pem;

  # Force HTTPS
  include conf.d/include/force-ssl.conf;

  # WebSockets
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection $http_connection;
  proxy_http_version 1.1;

  location / {
    include conf.d/include/proxy.conf;
  }
}
```

---

## 🚀 Como Adicionar Rota `/mobile`

### Opção 1: Via NPM UI (RECOMENDADO) ⭐

1. **Acessar NPM:**
   ```
   https://etdngx.easytek-data.com.br
   ou
   http://<ip-servidor>:81
   ```

2. **Login:**
   - Email: `admin@example.com`
   - Senha: `changeme`

3. **Editar Host:**
   - Vá em **Hosts → Proxy Hosts**
   - Clique em `etd.easytek-data.com.br` (host #2)
   - Vá para aba **Custom Locations**

4. **Adicionar Location:**
   - **Define Location:** `/mobile`
   - **Scheme:** `http://`
   - **Forward Hostname/IP:** `amg-mobile`
   - **Forward Port:** `3000`
   - ✅ **Websockets Support:** Marcar
   - ✅ **Block Common Exploits:** Marcar
   - **Custom Config:** (deixar vazio por enquanto)

5. **Salvar**

6. **Resultado:**
   ```
   https://etd.easytek-data.com.br/mobile → amg-mobile:3000
   ```

---

### Opção 2: Via Docker Exec (Avançado)

**Não recomendado** porque:
- NPM regenera configs automaticamente
- Edições manuais podem ser perdidas
- UI do NPM é muito mais segura

Mas se precisar:

```bash
# Backup da config atual
docker exec nginx-proxy-manager cat /data/nginx/proxy_host/2.conf > backup-2.conf

# Editar config (NÃO RECOMENDADO - use a UI!)
docker exec nginx-proxy-manager vi /data/nginx/proxy_host/2.conf

# Recarregar Nginx
docker exec nginx-proxy-manager nginx -s reload
```

---

## 📦 Adicionando Container `amg-mobile` ao Docker Compose

**Arquivo:** `AMG_Infra/docker-compose.yml`

Adicionar serviço:

```yaml
  amg-mobile:
    image: ghcr.io/easytek-automation/easytek-data/amg-mobile:${TAG:-latest}
    container_name: amg-mobile
    restart: unless-stopped
    ports:
      - "3000:3000"  # Opcional - apenas para debug
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_API_URL=http://webapp:8050/api/v1
      - PORT=3000
    networks:
      - easytek-net
    depends_on:
      - webapp
```

**Importante:**
- ✅ Mesma rede: `easytek-net`
- ✅ Comunicação interna: `http://webapp:8050/api/v1`
- ✅ Porta externa opcional (só para debug local)
- ✅ Acesso público via NPM: `https://etd.easytek-data.com.br/mobile`

---

## 🔧 Configurações de Cookie no Flask

**Arquivo:** `AMG_Data/webapp/src/app.py`

Adicionar após linha 30:

```python
server.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_SAMESITE='Lax',      # Permite cross-location no mesmo domínio
    SESSION_COOKIE_SECURE=True,         # Exige HTTPS (NPM já força SSL)
    SESSION_COOKIE_HTTPONLY=True,       # Proteção XSS
    SESSION_COOKIE_PATH='/',            # Cookie válido para todo o domínio
    SESSION_COOKIE_NAME='etd_session',  # Nome customizado (opcional)
)
```

**Por que funciona:**
- ✅ Mesmo domínio: `etd.easytek-data.com.br`
- ✅ Path `/` cobre tanto `/` (Dash) quanto `/mobile` (Next.js)
- ✅ `SameSite=Lax` permite navegação cross-location
- ✅ NPM força HTTPS, então `Secure=True` funciona

---

## 🧪 Teste de Autenticação Cross-App

### 1. Verificar Cookie no Dash

1. Acessar `https://etd.easytek-data.com.br`
2. Fazer login
3. Abrir DevTools → Application → Cookies
4. Verificar cookie `session` (ou `etd_session`):
   - **Domain:** `.etd.easytek-data.com.br` ou `etd.easytek-data.com.br`
   - **Path:** `/`
   - **Secure:** ✅
   - **HttpOnly:** ✅
   - **SameSite:** `Lax`

### 2. Testar API REST

```bash
# Com cookie de sessão ativo no navegador
curl -X GET https://etd.easytek-data.com.br/api/v1/user/profile \
  --cookie "session=<valor-do-cookie>" \
  -H "Content-Type: application/json"

# Resposta esperada:
{
  "username": "seu-usuario",
  "level": 2,
  "perfil": "manutencao"
}
```

### 3. Testar Next.js Fetch

```javascript
// No Next.js (client-side)
const response = await fetch('/api/v1/user/profile', {
  credentials: 'include',  // IMPORTANTE: envia cookies
});

const user = await response.json();
console.log(user);
```

---

## 📊 Monitoramento

### Logs do NPM

```bash
# Logs de acesso do webapp
docker exec nginx-proxy-manager tail -f /data/logs/proxy-host-2_access.log

# Logs de erro
docker exec nginx-proxy-manager tail -f /data/logs/proxy-host-2_error.log

# Logs gerais do Nginx
docker logs -f nginx-proxy-manager
```

### Verificar SSL

```bash
# Testar certificado
openssl s_client -connect etd.easytek-data.com.br:443 -servername etd.easytek-data.com.br

# Verificar expiração
docker exec nginx-proxy-manager certbot certificates
```

---

## ⚡ Estimativa Atualizada do MVP Mobile

Com a arquitetura real identificada:

| Fase | Tarefa | Tempo | Complexidade |
|------|--------|-------|--------------|
| **0. Configurar Flask** | Adicionar cookies config | 10min | Trivial |
| **1. API REST** | Criar endpoint `/api/v1/producao/oee` | 4h | Baixa |
| **2. Next.js Setup** | Scaffold + config | 2h | Baixa |
| **3. Docker Config** | Adicionar serviço no docker-compose | 15min | Trivial |
| **4. NPM Config** | Adicionar rota `/mobile` via UI | 5min | Trivial |
| **5. Página Mobile** | UI + integração | 4h | Média |
| **6. Testes** | Auth + responsivo | 2h | Baixa |

### 🎯 **Total: 1-1.5 dias úteis** ✨

**Redução de 3-4 dias para 1-1.5 dias** porque:
- ✅ Nginx já configurado (NPM UI simplifica tudo)
- ✅ SSL já funcionando (Let's Encrypt automático)
- ✅ Rede Docker já pronta
- ✅ WebSockets já habilitados
- ✅ Não precisa implementar JWT
- ✅ Não precisa mexer em configs de Nginx manualmente

---

## 🔒 Checklist de Segurança

- [x] SSL/TLS habilitado (Let's Encrypt)
- [x] Force HTTPS ativo
- [x] HSTS configurado
- [x] Cookies com flags HttpOnly e Secure
- [x] WebSockets seguros (wss://)
- [x] Rate limiting (padrão do NPM)
- [ ] **TODO:** Adicionar rate limiting específico para `/api/v1/*`
- [ ] **TODO:** Configurar CORS apenas para domínio específico

---

## 📝 Próximos Passos

1. **Configurar cookies no Flask** (10min)
2. **Criar API REST básica** (meio dia)
3. **Adicionar `amg-mobile` ao docker-compose** (15min)
4. **Criar rota `/mobile` no NPM** (5min via UI)
5. **Desenvolver página mobile** (meio dia)
6. **Testar e ajustar** (2h)

**MVP funcional em 1-2 dias!** 🚀

---

**Arquivos relacionados:**
- `AMG_Infra/docker-compose.yml` - Configuração de containers
- `AMG_Infra/proxy-compose.yml` - NPM config
- `AMG_Data/webapp/src/app.py` - Flask server (onde adicionar cookies)
- NPM UI: `https://etdngx.easytek-data.com.br`
