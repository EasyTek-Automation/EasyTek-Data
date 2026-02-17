# Guia: Configurar Rota /mobile no Nginx Proxy Manager

**Objetivo:** Adicionar rota `/mobile` que aponta para o container Next.js

**Tempo estimado:** 5 minutos

---

## 🔐 Passo 1: Acessar o Nginx Proxy Manager

### 1.1 Abrir o NPM no navegador

```
https://etdngx.easytek-data.com.br
```

Ou se preferir pela porta direta:
```
http://<ip-do-servidor>:81
```

### 1.2 Fazer Login

**Credenciais padrão** (se não alterou):
- **Email:** `admin@example.com`
- **Senha:** `changeme`

⚠️ **Se aparecer erro de login:**
- Tente `admin@example.com` / `changeme`
- Ou verifique se você já alterou a senha padrão

---

## 🎯 Passo 2: Localizar o Host Principal

### 2.1 Ir para a lista de Proxy Hosts

1. No menu lateral esquerdo, clique em **"Hosts"**
2. Depois clique em **"Proxy Hosts"**

### 2.2 Encontrar o host `etd.easytek-data.com.br`

Na lista de hosts, procure por:
```
Domain Names: etd.easytek-data.com.br
Forward Host / IP: webapp
Forward Port: 8050
```

**É o host #2** (conforme vimos antes)

### 2.3 Clicar para Editar

Clique nos **3 pontinhos** (⋮) à direita do host e selecione **"Edit"**

Ou clique diretamente no nome do host.

---

## ⚙️ Passo 3: Adicionar Custom Location

### 3.1 Ir para a Aba "Custom Locations"

Na janela de edição do host, você verá várias abas no topo:
```
[ Details ] [ SSL ] [ Advanced ] [ Custom Locations ]
```

Clique em **"Custom Locations"**

### 3.2 Adicionar Nova Location

Clique no botão **"Add location"** (geralmente um botão verde ou azul)

### 3.3 Preencher o Formulário

Você verá um formulário com vários campos. Preencha assim:

#### **Define Location:** ⭐ IMPORTANTE
```
/mobile
```
⚠️ **Atenção:**
- NÃO colocar `/mobile/` (com barra no final)
- NÃO colocar `mobile` (sem barra no início)
- Deve ser exatamente: `/mobile`

#### **Scheme:**
```
http://
```
(Selecione `http` no dropdown, NÃO `https`)

#### **Forward Hostname / IP:**
```
amg-mobile
```
⚠️ **Importante:** É o NOME do container, não um IP!

#### **Forward Port:**
```
3000
```

#### **Opções Adicionais (Checkboxes):**

Marque as seguintes opções:

- ✅ **Websockets Support** (importante para Next.js)
- ✅ **Block Common Exploits** (segurança)

#### **Custom Config:** (deixar VAZIO)

Não preencher nada aqui por enquanto.

---

## 📸 Resumo Visual do Formulário

```
┌─────────────────────────────────────────────────┐
│ Add Custom Location                             │
├─────────────────────────────────────────────────┤
│                                                 │
│ Define Location: *                              │
│ ┌─────────────────────────────────────────┐    │
│ │ /mobile                                  │    │
│ └─────────────────────────────────────────┘    │
│                                                 │
│ Scheme: *                                       │
│ ┌─────────┐                                     │
│ │ http:// ▼│                                    │
│ └─────────┘                                     │
│                                                 │
│ Forward Hostname / IP: *                        │
│ ┌─────────────────────────────────────────┐    │
│ │ amg-mobile                               │    │
│ └─────────────────────────────────────────┘    │
│                                                 │
│ Forward Port: *                                 │
│ ┌─────────────────────────────────────────┐    │
│ │ 3000                                     │    │
│ └─────────────────────────────────────────┘    │
│                                                 │
│ ☑ Websockets Support                           │
│ ☑ Block Common Exploits                        │
│ ☐ HTTP/2 Support                               │
│                                                 │
│ Custom Nginx Configuration                      │
│ ┌─────────────────────────────────────────┐    │
│ │                                          │    │
│ │ (deixar vazio)                           │    │
│ │                                          │    │
│ └─────────────────────────────────────────┘    │
│                                                 │
│        [ Cancel ]  [ Save ]                     │
└─────────────────────────────────────────────────┘
```

---

## 💾 Passo 4: Salvar as Configurações

### 4.1 Salvar a Location

Clique no botão **"Save"** (dentro do formulário de Custom Location)

### 4.2 Salvar o Host

Depois, clique no botão **"Save"** principal (no canto inferior direito da janela de edição do host)

⚠️ **Importante:** São 2 saves:
1. Save da location
2. Save do host

### 4.3 Aguardar Confirmação

Você verá uma mensagem de sucesso tipo:
```
✓ Successfully saved proxy host
```

O NPM vai recarregar automaticamente o Nginx (leva ~2 segundos).

---

## ✅ Passo 5: Verificar se Funcionou

### 5.1 Verificar na Lista de Locations

Volte para editar o host `etd.easytek-data.com.br` novamente.

Na aba **"Custom Locations"**, você deve ver:

```
┌──────────────────────────────────────────────────┐
│ Location    │ Scheme  │ Forward To             │
├─────────────┼─────────┼────────────────────────┤
│ /mobile     │ http:// │ amg-mobile:3000        │
└──────────────────────────────────────────────────┘
```

### 5.2 Testar Acesso

Abra um navegador e acesse:

```
https://etd.easytek-data.com.br/mobile
```

**Resultado esperado:**

- Se container `amg-mobile` NÃO está rodando:
  ```
  502 Bad Gateway
  ```
  (Normal! Só precisa iniciar o container)

- Se container está rodando:
  ```
  Página do Next.js carrega! 🎉
  ```

---

## 🐳 Passo 6: Iniciar o Container (Se Ainda Não Fez)

### 6.1 Fazer Build da Imagem

No seu computador (Windows):

```bash
cd "E:\Projetos Python\AMG_Data\amg-mobile"
docker build -t amg-mobile:latest .
```

### 6.2 Testar Localmente (Opcional)

```bash
docker run -p 3000:3000 amg-mobile:latest
```

Acessar: `http://localhost:3000/mobile`

### 6.3 Deploy no Servidor

**Opção A: Transferir imagem via SSH**

```bash
# Salvar imagem
docker save amg-mobile:latest -o amg-mobile.tar

# Enviar para servidor
scp amg-mobile.tar usuario@servidor:/tmp/

# No servidor
ssh usuario@servidor
docker load -i /tmp/amg-mobile.tar
```

**Opção B: Build direto no servidor**

```bash
# Enviar código fonte
scp -r "E:\Projetos Python\AMG_Data\amg-mobile" usuario@servidor:/tmp/

# No servidor
ssh usuario@servidor
cd /tmp/amg-mobile
docker build -t amg-mobile:latest .
```

### 6.4 Adicionar ao Docker Compose

No servidor, editar `/opt/easytek-infra/docker-compose.yml`:

```yaml
  amg-mobile:
    image: amg-mobile:latest
    container_name: amg-mobile
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_API_URL=http://webapp:8050/api/v1
      - PORT=3000
    networks:
      - easytek-net
    depends_on:
      - webapp
```

### 6.5 Iniciar Container

```bash
cd /opt/easytek-infra
docker compose up -d amg-mobile

# Verificar logs
docker compose logs -f amg-mobile
```

---

## 🧪 Passo 7: Teste Final Completo

### 7.1 Testar Acesso Desktop

No navegador desktop, acessar:
```
https://etd.easytek-data.com.br/
```

**Resultado esperado:**
- Dash carrega normalmente (versão desktop)

### 7.2 Testar Acesso Mobile

**Opção A: Chrome DevTools**

1. Abrir `https://etd.easytek-data.com.br/`
2. Pressionar `F12` (DevTools)
3. Clicar no ícone de celular (Toggle device toolbar)
4. Selecionar "iPhone 12 Pro" ou similar
5. Recarregar página (`Ctrl+R`)

**Resultado esperado:**
- Middleware detecta mobile
- Redireciona automaticamente para `/mobile`
- Next.js carrega! 🎉

**Opção B: Celular Real**

1. Pegar seu smartphone
2. Conectar na mesma rede (ou usar internet)
3. Acessar `https://etd.easytek-data.com.br/`

**Resultado esperado:**
- Redireciona para `/mobile`
- Dashboard mobile lindo aparece! 🎊

### 7.3 Testar Forçar Desktop

No celular, acessar:
```
https://etd.easytek-data.com.br/?desktop=true
```

**Resultado esperado:**
- Cookie `force_desktop=true` é setado
- Dash desktop carrega (mesmo no celular)

---

## 🐛 Troubleshooting

### Problema 1: "502 Bad Gateway" ao acessar /mobile

**Causa:** Container `amg-mobile` não está rodando ou não está na rede `easytek-net`

**Solução:**

```bash
# Verificar se container está rodando
docker ps | grep amg-mobile

# Se não estiver, iniciar
docker compose up -d amg-mobile

# Verificar logs
docker compose logs amg-mobile

# Verificar rede
docker inspect amg-mobile | grep -A 10 Networks
```

### Problema 2: "404 Not Found" ao acessar /mobile

**Causa:** Custom location não foi salva corretamente no NPM

**Solução:**

1. Voltar no NPM
2. Editar host `etd.easytek-data.com.br`
3. Verificar aba "Custom Locations"
4. Confirmar que `/mobile` está lá
5. Se não estiver, adicionar novamente

### Problema 3: Página carrega mas não mostra dados

**Causa:** API não está acessível ou cookies não estão funcionando

**Solução:**

```bash
# No container Next.js, verificar se consegue acessar API
docker exec amg-mobile sh -c "wget -O- http://webapp:8050/api/v1/ping"

# Deve retornar JSON (ou erro 401 se não logado)
```

### Problema 4: Container reinicia constantemente

**Causa:** Erro no build ou dependências faltando

**Solução:**

```bash
# Ver logs detalhados
docker logs amg-mobile --tail 100

# Rebuild sem cache
docker build --no-cache -t amg-mobile:latest .
```

### Problema 5: Mobile não redireciona automaticamente

**Causa:** Middleware não está ativo ou user-agent não é detectado

**Solução:**

1. Verificar logs do Flask:
   ```bash
   docker logs webapp | grep mobile
   ```

2. Testar manualmente:
   ```bash
   curl -H "User-Agent: iPhone" https://etd.easytek-data.com.br/
   # Deve retornar redirect 302 para /mobile
   ```

---

## 📋 Checklist Final

- [ ] NPM acessível via `https://etdngx.easytek-data.com.br`
- [ ] Host `etd.easytek-data.com.br` encontrado
- [ ] Custom Location `/mobile` adicionada
- [ ] Forward para `amg-mobile:3000` configurado
- [ ] Websockets habilitado
- [ ] Configuração salva (2x save)
- [ ] Container `amg-mobile` buildado
- [ ] Container rodando (`docker ps`)
- [ ] Logs sem erros (`docker logs amg-mobile`)
- [ ] Desktop acessa `/` normalmente
- [ ] Mobile redireciona para `/mobile` automaticamente
- [ ] Interface Next.js carrega e mostra dados
- [ ] Cookies de autenticação funcionando

---

## 🎓 Resumo de Comandos Úteis

### No NPM (Interface Web)

```
1. Acessar: https://etdngx.easytek-data.com.br
2. Login: admin@example.com / changeme
3. Hosts → Proxy Hosts
4. Editar: etd.easytek-data.com.br
5. Aba: Custom Locations
6. Add location: /mobile → amg-mobile:3000
7. Save (2x)
```

### No Servidor (Docker)

```bash
# Build
cd amg-mobile && docker build -t amg-mobile:latest .

# Adicionar ao compose
vim /opt/easytek-infra/docker-compose.yml

# Iniciar
docker compose up -d amg-mobile

# Logs
docker compose logs -f amg-mobile

# Parar
docker compose stop amg-mobile

# Restart
docker compose restart amg-mobile
```

---

**Boa sorte com a configuração! Se encontrar algum problema, me avise qual erro aparece que eu ajudo.** 🚀
