# Plano: Sync Automático de Flows Node-RED (Datacenter → Edge)

**Status:** Planejado — não implementado
**Data:** 2026-02-26

## Contexto

A aplicação precisa migrar para uma VM no datacenter, mantendo o computador de borda
apenas para conectividade com a rede de máquinas (Modbus TCP).

O objetivo é: **desenvolver os flows Node-RED no datacenter e tê-los atualizados
automaticamente na instância da borda**, sem nenhuma intervenção manual recorrente.

### Situação atual do projeto

1. **Dockerfile já faz COPY dos flows**: `flows.json` é embutido na imagem Docker durante o build
2. **Imagem já vai para GHCR**: `ghcr.io/easytek-automation/easytek-data/node-red:${TAG}`
3. **Volume de flows está comentado**: mudanças no editor NR são perdidas no restart
4. **Projects/Git do NR está desativado**: `enabled: false` em `node-red/settings.js`
5. **Node-RED usa Modbus TCP direto → MongoDB**: sem MQTT no NR (MQTT só no event-gateway)

### Por que 80% do trabalho já existe

- Imagem buildada e publicada no GHCR ✓
- Docker rodando na borda ✓
- Repositório Git como fonte de verdade ✓

Falta apenas: **Watchtower na borda** + **volume montado no NR do datacenter**.

---

## Arquitetura: GitOps + Watchtower

```
DATACENTER (VM)
┌─────────────────────────────────────────────────────┐
│  Node-RED Editor (GUI, porta 1880)                  │
│    ↓  desenvolvedor edita flows no browser          │
│  flows.json salvo em volume local (persistido)      │
│    ↓  commit + push → GitHub                        │
│  GitHub Actions → build imagem → push GHCR         │
└─────────────────────────────────────────────────────┘
                        ↕ internet (rede TI)
BORDA (Edge Computer)
┌─────────────────────────────────────────────────────┐
│  Watchtower (container ~10MB)                       │
│    ↓  polling GHCR a cada 5 minutos                 │
│  Nova imagem disponível?                            │
│    → pull automático                                │
│    → restart do node-red container                  │
│  Node-RED ← atualizado sem toque manual             │
│    → Modbus TCP → máquinas (rede local isolada)     │
└─────────────────────────────────────────────────────┘
```

**Tempo total do save ao edge atualizado: ~8-10 minutos.**
Build GitHub Actions (~3 min) + polling Watchtower (~5 min).

### Por que Watchtower

| Critério | Detalhe |
|----------|---------|
| Pull model | Borda puxa do GHCR — nenhuma porta inbound precisa ser aberta |
| Zero toque na borda | Após configuração inicial, nunca mais precisa acessar o edge para atualizar NR |
| Leve | Container de ~10MB, impacto mínimo |
| Compatível | Já usa GHCR e Docker Compose |
| Tolerante a falha | Se borda ficar offline, sincroniza quando voltar online |

---

## Implementação

### 1. Datacenter — NR com volume montado

```yaml
# docker-compose.override.yml (datacenter / dev)
node-red:
  volumes:
    - ./node-red/flows.json:/data/flows.json     # persiste edições do editor
    - ./node-red/settings.js:/data/settings.js
    - node_red_modules:/data/node_modules
  ports:
    - "1880:1880"   # exposto via Nginx Proxy Manager com auth
```

O `flows.json` fica montado do repositório. Ao editar e salvar no editor → arquivo
atualizado no repo → commit + push → pipeline dispara.

### 2. GitHub Actions — trigger em mudanças do Node-RED

Verificar/adicionar trigger no pipeline existente:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'node-red/flows.json'
      - 'node-red/Dockerfile'
      - 'node-red/settings.js'
      - 'node-red/package.json'
```

### 3. Borda — Adicionar Watchtower

```yaml
# docker-compose.yml (borda)
watchtower:
  image: containrrr/watchtower
  restart: unless-stopped
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - ~/.docker/config.json:/config.json        # credenciais GHCR
  environment:
    - WATCHTOWER_POLL_INTERVAL=300              # 5 minutos
    - WATCHTOWER_CLEANUP=true                   # remove imagens antigas
    - WATCHTOWER_INCLUDE_STOPPED=false
  command: node-red                             # monitora APENAS o container node-red
```

### 4. Credenciais — flows_cred.json na borda

O `flows_cred.json` contém credenciais Modbus/MongoDB criptografadas com o `instanceId`
da borda. **Não deve ir na imagem Docker.** Deve permanecer no volume local da borda.

Mapeamento correto no docker-compose da borda:
```yaml
node-red:
  volumes:
    - node_red_modules:/data/node_modules
    - ${NODE_RED_DATA_PATH}:/data               # descomentado — persiste flows_cred.json
```

O volume `/data` contém `flows_cred.json` com as credenciais. A imagem nova sobrescreve
`flows.json` (que vem do COPY do Dockerfile), mas as credenciais no volume persistem.

### 5. node-red/Dockerfile — fixar versão

```dockerfile
# Antes
FROM nodered/node-red:latest

# Depois
FROM nodered/node-red:4.0.5   # ou versão estável atual
```

---

## Fluxo de trabalho após implementação

```
1. Abre browser → acessa Node-RED do datacenter
2. Edita flows, adiciona nós, ajusta lógica
3. Clica "Deploy" no editor → flows.json atualizado no volume
4. git commit + push → GitHub
5. GitHub Actions builda nova imagem → push para GHCR (~3 min)
6. Watchtower na borda detecta nova tag → pull → restart (~5 min)
7. Node-RED da borda está atualizado, Modbus continua coletando
```

---

## Arquivos a modificar

| Arquivo | Mudança |
|---------|---------|
| `node-red/Dockerfile` | Fixar versão (remover `latest`) |
| `node-red/settings.js` | Opcional: ativar Projects para git nativo |
| `AMG_Infra/docker-compose.yml` | Descomentar volume `NODE_RED_DATA_PATH` |
| `AMG_Infra/environments/*/docker-compose.override.yml` | Volume montado para dev |
| `AMG_Infra/.github/workflows/` | Adicionar trigger para mudanças em `node-red/` |
| `AMG_Infra/docker-compose.yml` (borda) | Adicionar serviço `watchtower` |

---

## Verificação (checklist pós-implementação)

- [ ] Editar um flow no datacenter e salvar
- [ ] Confirmar que `flows.json` no repo foi atualizado (git diff)
- [ ] Verificar GitHub Actions rodando o build da imagem
- [ ] Aguardar ~8-10 min e verificar log do Watchtower na borda
- [ ] Confirmar que container `node-red` na borda reiniciou com nova imagem (`docker ps`)
- [ ] Validar que coleta Modbus continuou sem interrupção (dados chegando no MongoDB)
