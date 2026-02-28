# Plano: Volume Persistente e Versionamento do Node-RED

## Contexto

**Problema atual**: Os fluxos, credenciais e configurações do Node-RED são copiados para
dentro da imagem Docker durante o build (`COPY flows.json /data/` etc.). Isso causa:

1. **Perda de fluxos**: Qualquer alteração feita via UI do Node-RED é descartada ao rebuildar a imagem.
2. **Erro de credenciais** (screenshot): O Node-RED gera um `_credentialSecret` novo a cada
   container fresh. O `flows_cred.json` na imagem foi encriptado com uma chave diferente → não
   decriptável. Aparece o erro "As credenciais não puderam ser descriptografadas".
3. **Nenhuma rastreabilidade**: Alterações de fluxo feitas em produção não são versionadas.
4. **Dois diretórios duplicados**: `node-red/` (243 KB, ativo) e `node-red-config/` (63 KB,
   legado) convivem em AMG_Data sem clareza sobre qual é canônico.

**Estado alvo**:
- Imagem leve: só base Node-RED, sem dados
- Volume `../AMG_NodeRED:/data` monta todos os arquivos de configuração
- Volume nomeado `node_red_modules:/data/node_modules` preserva pacotes instalados (mantido)
- `credentialSecret` fixo via variável de ambiente → credenciais sempre decriptáveis
- Repositório `AMG_NodeRED` rastreia fluxos com workflow de commit manual

---

## Arquivos Críticos

| Arquivo | Repositório | O que muda |
|---------|-------------|------------|
| `node-red/Dockerfile` | AMG_Data | Remover todos os `COPY` |
| `node-red/.gitignore` | AMG_Data | Ignorar arquivos de runtime e credenciais |
| `node-red/flows.json` | AMG_Data | Mover para AMG_NodeRED (não deletar ainda — migração) |
| `node-red/flows_cred.json` | AMG_Data | Mover para AMG_NodeRED (gitignored lá) |
| `node-red/settings.js` | AMG_Data | Mover para AMG_NodeRED + adicionar `credentialSecret` |
| `docker-compose.yml` | AMG_Infra | Ativar volume `/data` + `env_file` para node-red |
| `.env.common` | AMG_Infra | Adicionar `NODE_RED_CREDENTIAL_SECRET` |
| `node-red-config/` | AMG_Data | **Deletar** (diretório legado, fluxo 4× menor que o ativo) |
| AMG_NodeRED | **(novo repo)** | Criar com todos os arquivos de dados |

---

## Parte 1 — Criar repositório AMG_NodeRED

### 1.1. Criar diretório e inicializar Git

```powershell
cd "E:\Projetos Python"
mkdir AMG_NodeRED
cd AMG_NodeRED
git init
```

### 1.2. Criar `.gitignore`

```gitignore
# Credenciais encriptadas — NUNCA versionar
flows_cred.json

# Arquivos de runtime gerados automaticamente
.config.runtime.json
.config.users.json
.config.nodes.json
.config.nodes.json.backup
.sessions.json
.flows.json.backup

# Dependências e backups
node_modules/
*.backup
```

### 1.3. Popular com arquivos de AMG_Data

Copiar do diretório **ativo** (`node-red/`, não `node-red-config/`):

```powershell
$src = "E:\Projetos Python\AMG_Data\node-red"
$dst = "E:\Projetos Python\AMG_NodeRED"

Copy-Item "$src\flows.json"              -Destination $dst
Copy-Item "$src\flows_cred.json"         -Destination $dst   # copiado, mas será gitignored
Copy-Item "$src\settings.js"             -Destination $dst
Copy-Item "$src\package.json"            -Destination $dst
Copy-Item "$src\config.json"             -Destination $dst
Copy-Item "$src\configAreaDecapado.json" -Destination $dst
Copy-Item "$src\.config.runtime.json"    -Destination $dst   # CRÍTICO — contém _credentialSecret atual
Copy-Item "$src\.config.users.json"      -Destination $dst
Copy-Item "$src\.config.nodes.json"      -Destination $dst
```

### 1.4. Corrigir `credentialSecret` em settings.js

No `AMG_NodeRED/settings.js`, localizar a linha comentada:
```javascript
// credentialSecret: "a-secret-key",
```
Substituir por:
```javascript
credentialSecret: process.env.NODE_RED_CREDENTIAL_SECRET || false,
```

Isso torna a chave de encriptação configurável por variável de ambiente e determinística
(não depende mais do `.config.runtime.json` gerado automaticamente).

### 1.5. Commit inicial e push

```powershell
cd "E:\Projetos Python\AMG_NodeRED"
git add .
git commit -m "feat: initial commit — Node-RED data extracted from AMG_Data image"

# Criar repo no GitHub (privado) e linkar:
gh repo create AMG_NodeRED --private --source=. --remote=origin --push
# OU criar manualmente no GitHub e depois:
# git remote add origin https://github.com/easytek-automation/AMG_NodeRED.git
# git push -u origin main
```

---

## Parte 2 — AMG_Data: simplificar Dockerfile

**Arquivo**: `E:\Projetos Python\AMG_Data\node-red\Dockerfile`

**Antes** (atual — dados na imagem):
```dockerfile
FROM nodered/node-red:latest
COPY flows.json /data/
COPY flows_cred.json /data/
COPY settings.js /data/
COPY package.json /data/
WORKDIR /data
RUN npm install --unsafe-perm --only=production
WORKDIR /usr/src/node-red
```

**Depois** (dados no volume):
```dockerfile
FROM nodered/node-red:latest
# Dados gerenciados via volume externo (AMG_NodeRED)
# Pacotes persistidos via named volume node_red_modules
WORKDIR /usr/src/node-red
```

> **Nota**: O `package.json` atual não tem dependências — o `npm install` era no-op. Os pacotes
> instalados (modbus, mongodb4) estão no volume nomeado `node_red_modules`, que é mantido intacto.

**Criar** `E:\Projetos Python\AMG_Data\node-red\.gitignore`:
```gitignore
# Arquivos de dados — gerenciados no repositório AMG_NodeRED
flows.json
flows_cred.json
settings.js
config.json
configAreaDecapado.json

# Runtime (gerados automaticamente)
.config.*.json
.sessions.json
*.backup
node_modules/
```

**Deletar diretório legado**:
```powershell
Remove-Item -Recurse -Force "E:\Projetos Python\AMG_Data\node-red-config"
```

**Commit em AMG_Data**:
```powershell
cd "E:\Projetos Python\AMG_Data"
git add node-red/Dockerfile node-red/.gitignore
git rm -r --cached node-red-config/
git commit -m "refactor(node-red): imagem leve sem dados — volumes externos gerenciam configs"
```

---

## Parte 3 — AMG_Infra: ativar volume e variável de ambiente

**Arquivo**: `E:\Projetos Python\AMG_Infra\docker-compose.yml`

Seção `node-red` atual:
```yaml
node-red:
  image: ghcr.io/easytek-automation/easytek-data/node-red:${TAG:-latest}
  restart: unless-stopped
  user: root
  volumes:
    - node_red_modules:/data/node_modules
    #- ${NODE_RED_DATA_PATH}:/data          ← comentado, não funciona
  networks:
    - easytek-net
```

Seção `node-red` nova:
```yaml
node-red:
  image: ghcr.io/easytek-automation/easytek-data/node-red:${TAG:-latest}
  restart: unless-stopped
  user: root
  env_file:
    - .env.common
  volumes:
    - ../AMG_NodeRED:/data                  # ← volume de dados (fluxos, configs, credenciais)
    - node_red_modules:/data/node_modules   # ← pacotes npm persistidos (overlay, mantido)
  networks:
    - easytek-net
```

**Arquivo**: `E:\Projetos Python\AMG_Infra\.env.common`

Adicionar linha:
```env
NODE_RED_CREDENTIAL_SECRET=de1a1bba241820f538492b60e0c56eedd4fcb2e5474dd1d73c185ca4b9b734e7
```

> **Importante**: Este é o valor atual do `_credentialSecret` em `.config.runtime.json`.
> Garante que o `flows_cred.json` existente seja decriptado corretamente.

**Commit em AMG_Infra**:
```powershell
cd "E:\Projetos Python\AMG_Infra"
git add docker-compose.yml .env.common
git commit -m "feat(node-red): ativar volume externo AMG_NodeRED e credentialSecret via env"
```

---

## Parte 4 — Migração em produção (deploy)

### 4.1. Clonar AMG_NodeRED no servidor de produção

```powershell
# No servidor de produção, ao lado de AMG_Infra:
cd "E:\Projetos Python"   # ou diretório onde AMG_Infra está em produção
git clone https://github.com/easytek-automation/AMG_NodeRED.git
```

### 4.2. Parar container, rebuildar e subir

```powershell
cd "E:\Projetos Python\AMG_Infra"
.\scripts\down.ps1 -env local   # (ou -env prod em produção)

# Build e push da imagem simplificada (a partir de AMG_Infra após merge):
.\scripts\build-and-push.ps1 -tag latest

# Subir com novo volume:
.\scripts\up.ps1 -env local     # (ou -env prod)
```

### 4.3. Verificar logs

```powershell
docker logs -f amg_infra-node-red-1 2>&1 | Select-String -Pattern "Started|Error|credential"
```

Esperado: `Started flows` **sem** mensagem de erro de credenciais.

### 4.4. Validar no browser

- Abrir Node-RED (URL via Nginx ou `http://localhost:1880` em dev)
- Login → verificar que fluxos carregaram ✅
- Verificar conexões MQTT e MongoDB ativas ✅

---

## Parte 5 — Workflow: sincronizar alterações para o repositório

Após editar fluxos via UI do Node-RED e fazer Deploy:

```powershell
cd "E:\Projetos Python\AMG_NodeRED"

git status                    # mostra flows.json modificado
git diff flows.json           # revisar as mudanças

git add flows.json
# Se settings.js ou package.json também mudou:
# git add settings.js package.json

git commit -m "feat(flows): <descrição da mudança>"
git push
```

> `flows_cred.json` é **sempre gitignored** — nunca vai para o repo.
> `.config.runtime.json` também é gitignored — a chave está em `.env.common`.

---

## Parte 6 — Workflow: puxar alterações do repositório para produção

```powershell
cd "E:\Projetos Python\AMG_NodeRED"
git pull

# Node-RED faz hot-reload de flows.json automaticamente.
# Se precisar forçar (mudança em settings.js, por exemplo):
docker restart amg_infra-node-red-1
```

---

## Verificação End-to-End

| # | Teste | Resultado esperado |
|---|-------|--------------------|
| 1 | Node-RED sobe após migração | Sem erro "credenciais não puderam ser descriptografadas" |
| 2 | Criar fluxo de teste → Deploy → restart container | Fluxo ainda existe |
| 3 | Rebuild imagem + restart | Fluxos preservados (dados no volume, não na imagem) |
| 4 | `cd AMG_NodeRED && git status` após Deploy | `flows.json` aparece como modificado |
| 5 | Verificar `node-red-config/` em AMG_Data | Diretório não existe mais |

---

## Resumo de mudanças por repositório

| Repositório | Mudanças |
|-------------|----------|
| **AMG_NodeRED** (novo) | Criar com flows, settings, configs; `.gitignore` excluindo credenciais e runtime |
| **AMG_Data** | Dockerfile simplificado (sem COPY); `.gitignore` para `node-red/`; deletar `node-red-config/` |
| **AMG_Infra** | Ativar volume `../AMG_NodeRED:/data`; adicionar `env_file` + `NODE_RED_CREDENTIAL_SECRET` em `.env.common` |
