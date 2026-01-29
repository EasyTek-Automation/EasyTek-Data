# Plano: Persistência Simples do Node-RED

## Etapas (Resumo Executivo)

### 0. 🔒 Segurança (antes de começar)
- Criar branch `feature/node-red-persistence` em AMG_Data e AMG_Infra
- Criar tag `checkpoint-before-node-red-persistence` para possível rollback

### 1. 🎯 Escolher Opção de Versionamento
- **Opção A** (Recomendado): Criar repositório separado `AMG_NodeRED`
- **Opção B**: Usar submódulo Git dentro de `AMG_Infra/node-red-data`

### 2. ✏️ Modificar AMG_Data
- Editar `node-red/Dockerfile`: Remover 4 linhas de COPY
- Criar `node-red/.gitignore`: Excluir arquivos de runtime

### 3. ✏️ Modificar AMG_Infra
- Editar `docker-compose.yml`: Descomentar linha do volume
- Atualizar `.gitignore`: Adicionar `node-red-data/` (se Opção A)

### 4. 🚀 Setup Inicial
- Criar diretório do volume
- Copiar arquivos existentes de AMG_Data/node-red
- Inicializar Git no novo local

### 5. ✅ Testar
- Rebuild da imagem
- Subir serviços com `up.ps1`
- Modificar fluxo via UI
- Verificar persistência após rebuild

### 6. 💾 Commit
- Commit das mudanças em AMG_Data e AMG_Infra
- Push das branches
- Merge para main

**Tempo estimado**: 30-60 minutos

---

## Problema

Atualmente, os fluxos do Node-RED são **copiados para dentro da imagem** durante o build. Quando você faz alterações via interface do Node-RED e depois rebuilda/puxa uma nova imagem, **perde as alterações**.

## Solução (Simples)

### 1. Habilitar Volume Persistente

**Arquivo**: `AMG_Infra/docker-compose.yml`

**Mudança**: Descomentar linha do volume

```yaml
node-red:
  volumes:
    - ./node-red-data:/data  # DESCOMENTAR esta linha
```

Isso cria um diretório `node-red-data/` local que persiste todos os dados do Node-RED.

### 2. Simplificar Dockerfile

**Arquivo**: `AMG_Data/node-red/Dockerfile`

**Remover** as linhas de COPY (linhas 3-6):

```dockerfile
FROM nodered/node-red:latest

# REMOVER estas 4 linhas:
# COPY flows.json /data/
# COPY flows_cred.json /data/
# COPY settings.js /data/
# COPY package.json /data/

WORKDIR /data
RUN npm install --unsafe-perm --only=production
WORKDIR /usr/src/node-red
```

**Resultado**: Imagem vazia, dados vêm do volume.

### 3. Primeira Execução (Setup Inicial)

Quando subir pela primeira vez com volume vazio, o Node-RED cria configuração padrão. Você precisa **popular** o volume com seus dados existentes:

```powershell
# 1. Criar diretório
cd E:\Projetos Python\AMG_Infra
mkdir node-red-data

# 2. Copiar arquivos de AMG_Data para AMG_Infra
Copy-Item "E:\Projetos Python\AMG_Data\node-red\flows.json" -Destination ".\node-red-data\"
Copy-Item "E:\Projetos Python\AMG_Data\node-red\flows_cred.json" -Destination ".\node-red-data\"
Copy-Item "E:\Projetos Python\AMG_Data\node-red\settings.js" -Destination ".\node-red-data\"
Copy-Item "E:\Projetos Python\AMG_Data\node-red\package.json" -Destination ".\node-red-data\"
Copy-Item "E:\Projetos Python\AMG_Data\node-red\.config.runtime.json" -Destination ".\node-red-data\"
Copy-Item "E:\Projetos Python\AMG_Data\node-red\.config.users.json" -Destination ".\node-red-data\"
Copy-Item "E:\Projetos Python\AMG_Data\node-red\.config.nodes.json" -Destination ".\node-red-data\"

# 3. Subir serviço
.\scripts\up.ps1 -env local
```

## Versionamento Git - Duas Opções

### Opção 1: Repositório Separado (Recomendado)

**Estrutura**:
```
E:\Projetos Python\
├── AMG_Data/          # Código da aplicação
├── AMG_Infra/         # Orquestração
└── AMG_NodeRED/       # NOVO - Dados do Node-RED
    ├── .git/
    ├── flows.json
    ├── flows_cred.json (gitignored)
    ├── settings.js
    └── ...
```

**Configuração**:

1. Criar novo repositório:
```powershell
cd E:\Projetos Python
mkdir AMG_NodeRED
cd AMG_NodeRED
git init
echo "flows_cred.json" >> .gitignore
echo ".sessions.json" >> .gitignore
echo "node_modules/" >> .gitignore
git add .
git commit -m "Initial commit"
```

2. Atualizar docker-compose.yml:
```yaml
node-red:
  volumes:
    - ../AMG_NodeRED:/data  # Aponta para repositório separado
```

**Vantagens**:
- ✅ Isolamento total dos dados do Node-RED
- ✅ Histórico Git independente
- ✅ Simples de versionar (git add/commit/push normal)
- ✅ Pode ter equipe separada mantendo fluxos

**Desvantagens**:
- ❌ Mais um repositório para gerenciar

---

### Opção 2: Git Submódulo

**Estrutura**:
```
AMG_Infra/
├── .git/
├── docker-compose.yml
├── node-red-data/     # Submódulo Git
│   ├── .git/          # Git próprio
│   ├── flows.json
│   └── ...
└── scripts/
```

**Configuração**:

1. Criar repositório para node-red-data:
```powershell
cd E:\Projetos Python\AMG_Infra
mkdir node-red-data
cd node-red-data
git init
echo "flows_cred.json" >> .gitignore
echo ".sessions.json" >> .gitignore
echo "node_modules/" >> .gitignore
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/seu-usuario/amg-node-red-data.git
git push -u origin main
```

2. Adicionar como submódulo no AMG_Infra:
```powershell
cd E:\Projetos Python\AMG_Infra
git submodule add https://github.com/seu-usuario/amg-node-red-data.git node-red-data
git commit -m "Add node-red-data submodule"
```

**Vantagens**:
- ✅ Tudo em um lugar (AMG_Infra)
- ✅ Git gerencia versionamento automaticamente
- ✅ Clone recursivo traz os dados

**Desvantagens**:
- ⚠️ Submódulos podem ser confusos (precisa de `git submodule update`)
- ⚠️ Commits em dois lugares (submódulo + repo principal)

---

## Minha Recomendação

**Opção 1 (Repositório Separado)** é mais simples e clara:

1. Você edita fluxos no Node-RED
2. Quando quiser versionar:
   ```powershell
   cd E:\Projetos Python\AMG_NodeRED
   git add flows.json settings.js
   git commit -m "feat: adiciona fluxo de monitoramento X"
   git push
   ```
3. Pronto!

**Workflow completo**:
- `AMG_Data`: Código Python/Dash + Dockerfiles (push quando muda código)
- `AMG_Infra`: Docker Compose + scripts (push quando muda infra)
- `AMG_NodeRED`: Fluxos do Node-RED (push quando muda fluxos)

## Passo 0: Segurança - Branch e Checkpoint

Antes de qualquer modificação, criar branch e tag de segurança nos dois repositórios:

**AMG_Data**:
```bash
cd E:\Projetos Python\AMG_Data
git checkout -b feature/node-red-persistence
git tag checkpoint-before-node-red-persistence
git push origin checkpoint-before-node-red-persistence
```

**AMG_Infra**:
```bash
cd E:\Projetos Python\AMG_Infra
git checkout -b feature/node-red-persistence
git tag checkpoint-before-node-red-persistence
git push origin checkpoint-before-node-red-persistence
```

**Rollback (se necessário)**:
```bash
# Em qualquer repositório
git checkout main
git reset --hard checkpoint-before-node-red-persistence
```

## Arquivos a Modificar

### AMG_Infra:

1. ✏️ `docker-compose.yml` - Descomentar volume OU apontar para `../AMG_NodeRED:/data`
2. ✏️ `.gitignore` - Adicionar `node-red-data/` (se usar Opção 1)

### AMG_Data:

1. ✏️ `node-red/Dockerfile` - Remover linhas COPY (linhas 3-6)
2. ✏️ `node-red/.gitignore` - Adicionar arquivos de runtime

### AMG_NodeRED (novo repositório - se usar Opção 1):

1. ✏️ `.gitignore` - Criar com exclusões de credenciais

## Testes

1. **Rebuild não perde dados**:
   ```powershell
   # Alterar fluxo via UI
   # Rebuild imagem
   cd AMG_Infra
   .\scripts\down.ps1 -env local
   cd ..\AMG_Data
   docker build -t test-nr node-red/
   cd ..\AMG_Infra
   .\scripts\up.ps1 -env local
   # ✅ Fluxo alterado ainda existe
   ```

2. **Versionamento funciona**:
   ```powershell
   cd E:\Projetos Python\AMG_NodeRED  # ou node-red-data se Opção 2
   git status
   # Deve mostrar flows.json modificado
   git add flows.json
   git commit -m "test"
   ```

## Resumo

**Antes**: Dados na imagem → perda nas alterações
**Depois**: Dados no volume + Git → persistência + versionamento

**Sua responsabilidade**:
- Fazer commits quando quiser versionar
- Push para backup remoto

**Benefício**:
- Simplicidade total
- Controle manual do versionamento

---

## Etapas Detalhadas (Guia Passo a Passo)

### Etapa -1: Salvar Documentação nos Projetos

**Objetivo**: Copiar este plano para os repositórios para consulta futura.

**Comandos**:

```powershell
# Criar diretórios docs se não existirem
New-Item -ItemType Directory -Force -Path "E:\Projetos Python\AMG_Data\docs"
New-Item -ItemType Directory -Force -Path "E:\Projetos Python\AMG_Infra\docs"

# Copiar plano para ambos os repositórios
Copy-Item "C:\Users\rgust\.claude\plans\unified-soaring-crane.md" -Destination "E:\Projetos Python\AMG_Data\docs\NODE-RED-PERSISTENCE.md"
Copy-Item "C:\Users\rgust\.claude\plans\unified-soaring-crane.md" -Destination "E:\Projetos Python\AMG_Infra\docs\NODE-RED-PERSISTENCE.md"
```

**Verificação**:
```powershell
Get-Item "E:\Projetos Python\AMG_Data\docs\NODE-RED-PERSISTENCE.md"
Get-Item "E:\Projetos Python\AMG_Infra\docs\NODE-RED-PERSISTENCE.md"
```

---

### Etapa 0: Segurança - Criar Branch e Checkpoint

**Objetivo**: Criar ponto de restauração antes de qualquer mudança.

**Comandos**:

```powershell
# AMG_Data
cd "E:\Projetos Python\AMG_Data"
git checkout main
git pull origin main
git checkout -b feature/node-red-persistence
git tag checkpoint-before-node-red-persistence
git push origin checkpoint-before-node-red-persistence

# AMG_Infra
cd "E:\Projetos Python\AMG_Infra"
git checkout main
git pull origin main
git checkout -b feature/node-red-persistence
git tag checkpoint-before-node-red-persistence
git push origin checkpoint-before-node-red-persistence
```

**Verificação**:
```powershell
git branch  # Deve mostrar * feature/node-red-persistence
git tag     # Deve listar checkpoint-before-node-red-persistence
```

**Rollback (se necessário no futuro)**:
```powershell
git checkout main
git reset --hard checkpoint-before-node-red-persistence
git push origin main --force
```

---

### Etapa 1: Escolher Opção de Versionamento

**Decisão**: Escolher entre Opção A (repositório separado) ou Opção B (submódulo).

**Recomendação**: Opção A (repositório separado `AMG_NodeRED`) por ser mais simples.

**Se escolher Opção A**, seguir **Etapa 1A**.
**Se escolher Opção B**, seguir **Etapa 1B**.

#### Etapa 1A: Criar Repositório Separado

```powershell
# Criar diretório e inicializar Git
cd "E:\Projetos Python"
mkdir AMG_NodeRED
cd AMG_NodeRED
git init

# Criar .gitignore
@"
# Credenciais e dados sensíveis
flows_cred.json
.sessions.json
.npmrc

# Node modules
node_modules/

# Backups automáticos
*.backup

# Configurações de runtime (geradas automaticamente)
.config.runtime.json
.config.users.json
.config.nodes.json
"@ | Out-File -FilePath .gitignore -Encoding UTF8

# Copiar arquivos de AMG_Data
Copy-Item "E:\Projetos Python\AMG_Data\node-red\flows.json" -Destination .
Copy-Item "E:\Projetos Python\AMG_Data\node-red\flows_cred.json" -Destination .
Copy-Item "E:\Projetos Python\AMG_Data\node-red\settings.js" -Destination .
Copy-Item "E:\Projetos Python\AMG_Data\node-red\package.json" -Destination .
Copy-Item "E:\Projetos Python\AMG_Data\node-red\.config.runtime.json" -Destination .
Copy-Item "E:\Projetos Python\AMG_Data\node-red\.config.users.json" -Destination .
Copy-Item "E:\Projetos Python\AMG_Data\node-red\.config.nodes.json" -Destination .

# Primeiro commit
git add .
git commit -m "Initial commit: Node-RED data from AMG_Data"

# Criar repositório no GitHub (manual ou via gh CLI)
# gh repo create AMG_NodeRED --private --source=. --remote=origin
# Ou criar via interface web e depois:
git remote add origin https://github.com/SEU_USUARIO/AMG_NodeRED.git
git branch -M main
git push -u origin main
```

**Modificar AMG_Infra/docker-compose.yml**:
```yaml
node-red:
  image: ghcr.io/easytek-automation/easytek-data/node-red:latest
  container_name: node-red
  restart: unless-stopped
  ports:
    - "1880:1880"
  networks:
    - easytek-net
  user: root
  volumes:
    - ../AMG_NodeRED:/data  # ← MUDAR para apontar para repo separado
```

#### Etapa 1B: Criar Submódulo Git

```powershell
cd "E:\Projetos Python\AMG_Infra"

# Criar diretório temporário para node-red-data
mkdir node-red-data-temp
cd node-red-data-temp

# Inicializar Git
git init

# Criar .gitignore
@"
flows_cred.json
.sessions.json
.npmrc
node_modules/
*.backup
.config.runtime.json
.config.users.json
.config.nodes.json
"@ | Out-File -FilePath .gitignore -Encoding UTF8

# Copiar arquivos
Copy-Item "E:\Projetos Python\AMG_Data\node-red\*" -Destination . -Exclude "*.backup"

# Commit inicial
git add .
git commit -m "Initial commit: Node-RED data"

# Criar repo no GitHub e push
# gh repo create AMG_NodeRED_Data --private --source=. --remote=origin
git remote add origin https://github.com/SEU_USUARIO/AMG_NodeRED_Data.git
git branch -M main
git push -u origin main

# Voltar para AMG_Infra e adicionar como submódulo
cd ..
rmdir node-red-data-temp -Recurse -Force
git submodule add https://github.com/SEU_USUARIO/AMG_NodeRED_Data.git node-red-data
git commit -m "Add node-red-data as submodule"
git push
```

**Modificar AMG_Infra/docker-compose.yml**:
```yaml
node-red:
  volumes:
    - ./node-red-data:/data  # ← DESCOMENTAR (já deve estar assim)
```

---

### Etapa 2: Modificar AMG_Data

**Arquivo 1**: `node-red/Dockerfile`

**Localização**: `E:\Projetos Python\AMG_Data\node-red\Dockerfile`

**Mudança**: Remover linhas 3-6 (COPY commands)

**Antes**:
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

**Depois**:
```dockerfile
FROM nodered/node-red:latest

WORKDIR /data
RUN npm install --unsafe-perm --only=production

WORKDIR /usr/src/node-red
```

**Arquivo 2**: `node-red/.gitignore`

**Localização**: `E:\Projetos Python\AMG_Data\node-red\.gitignore`

**Criar novo arquivo** (se não existir) ou adicionar:
```gitignore
# Runtime files
.config.*
.sessions.json
*.backup
node_modules/

# Dados sensíveis
flows_cred.json
```

**Commit**:
```powershell
cd "E:\Projetos Python\AMG_Data"
git add node-red/Dockerfile node-red/.gitignore
git commit -m "refactor(node-red): remove data COPY from Dockerfile for volume persistence"
```

---

### Etapa 3: Modificar AMG_Infra

**Arquivo 1**: `docker-compose.yml`

**Localização**: `E:\Projetos Python\AMG_Infra\docker-compose.yml`

**Se Opção A (repositório separado)**:
```yaml
node-red:
  volumes:
    - ../AMG_NodeRED:/data  # Apontar para repo separado
```

**Se Opção B (submódulo)**:
```yaml
node-red:
  volumes:
    - ./node-red-data:/data  # Descomentar linha existente
```

**Arquivo 2**: `.gitignore` (se usar Opção A)

**Localização**: `E:\Projetos Python\AMG_Infra\.gitignore`

**Adicionar** (se usar Opção A):
```gitignore
# Node-RED data (gerenciado em repo separado)
node-red-data/
```

**Commit**:
```powershell
cd "E:\Projetos Python\AMG_Infra"
git add docker-compose.yml .gitignore
git commit -m "feat(node-red): enable persistent volume for Node-RED data"
```

---

### Etapa 4: Setup Inicial e Primeiro Teste

**Parar serviços**:
```powershell
cd "E:\Projetos Python\AMG_Infra"
.\scripts\down.ps1 -env local
```

**Rebuild da imagem Node-RED**:
```powershell
cd "E:\Projetos Python\AMG_Infra"
.\scripts\build-and-push.ps1 -tag node-red-persistence-test
```

**Subir serviços**:
```powershell
.\scripts\up.ps1 -env local -tag node-red-persistence-test
```

**Verificar logs**:
```powershell
docker logs -f amg_infra-node-red-1
# Aguardar até ver "Started flows" ou similar
```

**Acessar Node-RED**:
- Abrir: http://localhost:1880
- Login: `rgustavo32` / senha do settings.js
- Verificar que fluxos carregaram corretamente

---

### Etapa 5: Testar Persistência

**Teste 1: Modificar fluxo**:
1. No Node-RED, criar novo fluxo simples: `inject → debug`
2. Deploy
3. Verificar no filesystem que arquivo foi atualizado:
   ```powershell
   # Se Opção A:
   Get-Item "E:\Projetos Python\AMG_NodeRED\flows.json" | Select-Object LastWriteTime

   # Se Opção B:
   Get-Item "E:\Projetos Python\AMG_Infra\node-red-data\flows.json" | Select-Object LastWriteTime
   ```

**Teste 2: Restart container**:
```powershell
cd "E:\Projetos Python\AMG_Infra"
.\scripts\down.ps1 -env local
.\scripts\up.ps1 -env local -tag node-red-persistence-test
```
- Abrir Node-RED novamente
- ✅ Verificar que novo fluxo ainda existe

**Teste 3: Rebuild completo** (teste crítico!):
```powershell
# Rebuild da imagem
cd "E:\Projetos Python\AMG_Infra"
.\scripts\down.ps1 -env local
.\scripts\build-and-push.ps1 -tag node-red-persistence-test

# Subir novamente
.\scripts\up.ps1 -env local -tag node-red-persistence-test
```
- Abrir Node-RED
- ✅ Verificar que fluxo modificado AINDA EXISTE (problema resolvido!)

---

### Etapa 6: Commit e Merge

**Push das branches**:
```powershell
# AMG_Data
cd "E:\Projetos Python\AMG_Data"
git push -u origin feature/node-red-persistence

# AMG_Infra
cd "E:\Projetos Python\AMG_Infra"
git push -u origin feature/node-red-persistence

# AMG_NodeRED (se Opção A)
cd "E:\Projetos Python\AMG_NodeRED"
git push -u origin main
```

**Criar Pull Requests** (via GitHub web ou gh CLI):
```powershell
# AMG_Data
cd "E:\Projetos Python\AMG_Data"
gh pr create --title "refactor(node-red): Enable volume persistence" --body "Remove data COPY from Dockerfile to support external volumes"

# AMG_Infra
cd "E:\Projetos Python\AMG_Infra"
gh pr create --title "feat(node-red): Enable persistent volume" --body "Configure docker-compose to mount Node-RED data from external repository"
```

**Após aprovação, merge para main**:
```powershell
# Via GitHub web ou:
gh pr merge --merge --delete-branch
```

**Atualizar local**:
```powershell
cd "E:\Projetos Python\AMG_Data"
git checkout main
git pull origin main

cd "E:\Projetos Python\AMG_Infra"
git checkout main
git pull origin main
```

**Deploy em produção** (quando pronto):
```powershell
cd "E:\Projetos Python\AMG_Infra"

# Fazer backup primeiro!
docker exec amg_infra-node-red-1 tar -czf /tmp/node-red-backup.tar.gz /data
docker cp amg_infra-node-red-1:/tmp/node-red-backup.tar.gz ./backups/

# Deploy
.\scripts\build-and-push.ps1 -tag latest
.\scripts\up.ps1 -env prod -tag latest
```

---

## Workflow Futuro (Após Implementação)

### Para modificar fluxos:
1. Editar via interface Node-RED (http://localhost:1880)
2. Deploy
3. Testar

### Para versionar alterações:
```powershell
# Se Opção A:
cd "E:\Projetos Python\AMG_NodeRED"
git add flows.json settings.js
git commit -m "feat: adiciona fluxo de monitoramento X"
git push

# Se Opção B:
cd "E:\Projetos Python\AMG_Infra\node-red-data"
git add flows.json settings.js
git commit -m "feat: adiciona fluxo de monitoramento X"
git push
cd ..
git add node-red-data
git commit -m "Update node-red-data submodule"
git push
```

### Para atualizar código Node-RED em produção:
```powershell
cd "E:\Projetos Python\AMG_Infra"
.\scripts\build-and-push.ps1 -tag latest
.\scripts\up.ps1 -env prod -tag latest
# Dados preservados automaticamente!
```
