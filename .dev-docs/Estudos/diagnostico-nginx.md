# Diagnóstico da Configuração Real do Nginx

**Data:** 2026-02-17
**Contexto:** A configuração do nginx no repositório está desatualizada. O sistema está acessível via `etd.easytek-data.com.br` com múltiplos serviços (Dash, Node-RED, Portainer, Nginx) funcionando via proxy.

---

## 🔍 Cenários Possíveis

### **Cenário 1: Nginx Proxy Manager (NPM)** ⭐ MAIS PROVÁVEL
- Interface web para gerenciar proxies
- Configuração armazenada em banco de dados interno (SQLite/MySQL)
- Arquivo `.conf` do repositório é ignorado
- Você acessa Nginx via UI do Portainer ou porta 81

### **Cenário 2: Configuração via Volume Docker**
- O `nginx.conf` do repositório é substituído por volume montado
- Configuração real está em `/var/lib/docker/volumes/` no servidor
- Não está versionado no Git

### **Cenário 3: ConfigMap/Secrets (menos provável sem Kubernetes)**
- Configuração injetada via variáveis de ambiente
- Menos comum em Docker puro

---

## 🛠️ Comandos para Diagnóstico

### **1. Identificar o Container do Nginx**

Execute no servidor (SSH ou diretamente):

```bash
# Listar containers rodando
docker ps | grep -E "nginx|proxy"

# Ou via docker compose (se estiver usando)
docker compose ps
```

**O que procurar:**
- Nome do container (ex: `nginx-proxy-manager`, `nginx`, `webproxy`)
- Imagem usada (ex: `jc21/nginx-proxy-manager:latest`, `nginx:alpine`)
- Portas mapeadas (80:80, 443:443, 81:81)

---

### **2. Verificar a Configuração REAL do Nginx**

```bash
# Substituir <nome-do-container> pelo nome encontrado acima
docker exec <nome-do-container> cat /etc/nginx/nginx.conf

# Exemplo:
docker exec nginx-proxy-manager cat /etc/nginx/nginx.conf
```

**Se for Nginx Proxy Manager:**
```bash
# A configuração fica em outro lugar
docker exec <nome-do-container> cat /data/nginx/proxy_host/*.conf

# Listar todos os hosts configurados
docker exec <nome-do-container> ls -la /data/nginx/proxy_host/
```

---

### **3. Verificar Volumes Montados**

```bash
# Ver detalhes do container
docker inspect <nome-do-container> | grep -A 20 "Mounts"

# Ou de forma mais legível
docker inspect <nome-do-container> --format='{{json .Mounts}}' | jq
```

**Isso mostra:**
- Volumes montados (onde está a configuração real)
- Bind mounts (arquivos locais montados no container)

---

### **4. Acessar o Nginx Proxy Manager (se for o caso)**

Se você vê uma interface web do Nginx:

1. Acesse `http://<seu-servidor>:81` (porta padrão do NPM)
2. Login padrão:
   - Email: `admin@example.com`
   - Senha: `changeme`
3. Vá em **Hosts → Proxy Hosts**
4. Veja a configuração de `etd.easytek-data.com.br`

---

### **5. Verificar Docker Compose (se estiver usando)**

```bash
# No servidor, procurar por docker-compose.yml
find /opt /srv /home -name "docker-compose.yml" 2>/dev/null

# Ou verificar diretório de trabalho do Portainer
docker inspect portainer | grep -i "workingdir\|volume"
```

---

## 📊 Interpretando os Resultados

### **Se encontrar Nginx Proxy Manager:**

**Vantagens:**
- ✅ Interface visual para gerenciar proxies
- ✅ Certificados SSL automáticos (Let's Encrypt)
- ✅ Não precisa editar arquivos de configuração

**Para o projeto mobile:**
- Adicionar rota `/mobile` pela UI do NPM
- Configurar proxy para `http://amg-mobile:3000`
- Habilitar Websockets se necessário
- Cookie headers funcionam automaticamente

---

### **Se encontrar Nginx tradicional:**

**Localização da configuração:**
```bash
# Configuração principal
/etc/nginx/nginx.conf

# Sites habilitados
/etc/nginx/conf.d/*.conf
/etc/nginx/sites-enabled/*.conf
```

**Para o projeto mobile:**
- Editar arquivo de configuração via volume montado
- Adicionar bloco `location /mobile { ... }`
- Reiniciar container

---

## 🎯 Próximos Passos Recomendados

### **Passo 1: Identificar o Setup Atual**

Execute os comandos acima e me forneça:

1. **Nome e imagem do container Nginx**
   ```bash
   docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}"
   ```

2. **Configuração visível** (primeiras 50 linhas)
   ```bash
   docker exec <container> cat /etc/nginx/nginx.conf | head -50
   ```

3. **Volumes montados**
   ```bash
   docker inspect <container> --format='{{json .Mounts}}' | jq
   ```

---

### **Passo 2: Documentar a Arquitetura Real**

Após identificar, vamos criar um diagrama do setup atual:

```
Cliente (Browser)
    ↓
etd.easytek-data.com.br (DNS)
    ↓
Nginx Proxy Manager (Container)
    ↓
    ├─ / ──────────► webapp:8050 (Dash)
    ├─ /node-red ──► node-red:1880
    ├─ /portainer ─► portainer:9000
    └─ (?)
```

---

### **Passo 3: Planejar Integração Mobile**

Com a configuração real em mãos, vamos definir:

- [ ] Como adicionar rota `/mobile` (NPM UI ou edit config)
- [ ] Se precisa configurar headers especiais para cookies
- [ ] Se SSL/HTTPS está habilitado (importante para `SESSION_COOKIE_SECURE`)
- [ ] Como fazer deploy do container Next.js no mesmo Docker network

---

## 📝 Template para Resposta

Copie e execute os comandos, depois me envie os resultados no formato:

```
### Container Nginx
Nome: <nome>
Imagem: <imagem>
Portas: <portas>

### Tipo de Setup
[ ] Nginx Proxy Manager (tem UI na porta 81)
[ ] Nginx tradicional
[ ] Traefik
[ ] Outro: ___________

### Configuração Atual (primeiras 20 linhas)
<cole aqui>

### Volumes Montados
<cole aqui>

### Acessos Funcionando Atualmente
- [ ] etd.easytek-data.com.br → Dash (porta 8050)
- [ ] etd.easytek-data.com.br/node-red → Node-RED
- [ ] etd.easytek-data.com.br/portainer → Portainer
- [ ] Outros: ___________
```

---

## ⚡ Atalho para Nginx Proxy Manager

Se for NPM, você pode simplesmente:

1. Acessar UI em `http://<servidor>:81`
2. Criar novo Proxy Host:
   - **Domain:** `etd.easytek-data.com.br`
   - **Forward Hostname:** `amg-mobile`
   - **Forward Port:** `3000`
   - **Custom Locations:** `/mobile`
3. Salvar e testar

**Zero necessidade de editar arquivos .conf!**

---

## 🔧 Se Precisar Atualizar o Repositório

Após identificar a configuração real:

```bash
# Exportar configuração do container
docker exec <container> cat /etc/nginx/nginx.conf > nginx/nginx.conf.REAL

# Ou se for NPM, exportar host específico
docker exec <container> cat /data/nginx/proxy_host/<ID>.conf > nginx/etd-proxy.conf

# Commitar ao repositório para documentação
git add nginx/
git commit -m "docs(nginx): adicionar configuração real de produção"
```

---

**Aguardando seus comandos para continuar! 🚀**
