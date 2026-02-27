# Plano: Sync Automático de Flows Node-RED — Borda sem Internet

**Status:** Planejado — não implementado
**Data:** 2026-02-26
**Variante de:** `node-red-edge-sync-architecture.md`
**Diferença:** Borda não tem acesso à internet — usa registry Docker local no datacenter

---

## Contexto

Mesma necessidade da versão anterior (sync automático de flows NR datacenter → borda),
mas com a restrição adicional de que o computador de borda **não tem acesso à internet**.

A borda enxerga **apenas a rede interna do TI**, que também é onde a VM do datacenter está.
O datacenter tem internet normalmente.

---

## Arquitetura: GitOps + Registry Local + Watchtower

```
DATACENTER (VM) — tem internet
┌────────────────────────────────────────────────────────┐
│  Node-RED Editor (GUI, porta 1880)                     │
│    ↓  edita flows no browser                           │
│  flows.json salvo em volume local                      │
│    ↓  commit + push → GitHub                           │
│  GitHub Actions → build imagem → push GHCR             │
│                                                        │
│  Registry Mirror (cron a cada 5 min):                  │
│    docker pull GHCR → docker tag → push Registry Local │
│                                                        │
│  Registry Local Docker (porta 5000)  ←─────────────┐  │
└────────────────────────────────────────────────────────┘
                    ↕ rede TI interna apenas
BORDA (Edge Computer) — SEM internet
┌────────────────────────────────────────────────────────┐
│  Watchtower                                            │
│    ↓  polling registry local (datacenter:5000)         │
│  Nova imagem disponível?                               │
│    → pull do registry local                            │
│    → restart do node-red container                     │
│  Node-RED ← atualizado sem toque manual               │
│    → Modbus TCP → máquinas (rede local isolada)        │
└────────────────────────────────────────────────────────┘
```

**Tempo total: ~8-15 minutos** — build GHA (~3 min) + mirror (~5 min) + Watchtower (~5 min).

---

## O que muda em relação à versão com internet

| Aspecto | Com internet | Sem internet (este plano) |
|---------|-------------|--------------------------|
| Registry | GHCR (nuvem) | Registry local no datacenter |
| Borda puxa de | github.com | IP interno do datacenter |
| Passo extra | — | Serviço de mirror GHCR → registry local |
| Porta necessária na borda | 443 (HTTPS) | 5000 (TCP interno) |
| Custo | Zero | Zero (registry:2 é open source) |

---

## Implementação

### 1. Datacenter — Registry Docker Local

Adicionar ao `docker-compose.yml` do datacenter:

```yaml
registry:
  image: registry:2
  restart: unless-stopped
  ports:
    - "5000:5000"
  volumes:
    - ${REGISTRY_DATA_PATH}:/var/lib/registry
  environment:
    REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY: /var/lib/registry
    REGISTRY_HTTP_ADDR: 0.0.0.0:5000
```

> **Nota de segurança:** O registry na porta 5000 estará acessível na rede interna
> sem autenticação. Se houver necessidade de auth, adicionar `htpasswd` ou usar
> o Nginx Proxy Manager para proteger o endpoint.

### 2. Datacenter — Mirror automático GHCR → Registry Local

Criar script `scripts/mirror-node-red.sh`:

```bash
#!/bin/bash
# Puxa imagem do GHCR e re-publica no registry local
# Executar: a cada 5 min via cron, ou via webhook do GitHub Actions

GHCR_IMAGE="ghcr.io/easytek-automation/easytek-data/node-red:latest"
LOCAL_IMAGE="localhost:5000/node-red:latest"

echo "[$(date)] Verificando nova imagem..."
docker pull "$GHCR_IMAGE"

# Comparar digest para evitar push desnecessário
GHCR_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "$GHCR_IMAGE" 2>/dev/null)
LOCAL_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "$LOCAL_IMAGE" 2>/dev/null)

if [ "$GHCR_DIGEST" != "$LOCAL_DIGEST" ]; then
  echo "[$(date)] Nova versão detectada. Publicando no registry local..."
  docker tag "$GHCR_IMAGE" "$LOCAL_IMAGE"
  docker push "$LOCAL_IMAGE"
  echo "[$(date)] Publicado com sucesso."
else
  echo "[$(date)] Imagem já atualizada. Nenhuma ação necessária."
fi
```

Adicionar ao crontab do datacenter:

```bash
# Verificar nova imagem a cada 5 minutos
*/5 * * * * /opt/amg/scripts/mirror-node-red.sh >> /var/log/mirror-node-red.log 2>&1
```

**Alternativa ao cron:** Adicionar um passo ao final do GitHub Actions que aciona
o mirror via webhook ou SSH no datacenter — elimina o delay do polling:

```yaml
# .github/workflows/build.yml (passo adicional após push para GHCR)
- name: Trigger mirror on datacenter
  run: |
    curl -X POST http://${{ secrets.DATACENTER_WEBHOOK_URL }}/mirror/node-red
```

### 3. Datacenter — NR com volume montado (igual à versão com internet)

```yaml
# docker-compose.override.yml (datacenter)
node-red:
  volumes:
    - ./node-red/flows.json:/data/flows.json
    - ./node-red/settings.js:/data/settings.js
    - node_red_modules:/data/node_modules
  ports:
    - "1880:1880"
```

### 4. Borda — Watchtower apontando para registry local

```yaml
# docker-compose.yml (borda)
watchtower:
  image: containrrr/watchtower
  restart: unless-stopped
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  environment:
    - WATCHTOWER_POLL_INTERVAL=300
    - WATCHTOWER_CLEANUP=true
    - WATCHTOWER_INCLUDE_STOPPED=false
  command: node-red

node-red:
  image: 192.168.X.X:5000/node-red:latest  # IP do datacenter na rede TI
  restart: unless-stopped
  # ... resto da config
```

**Importante:** Para Docker aceitar registry HTTP (sem HTTPS), adicionar no
`/etc/docker/daemon.json` da borda:

```json
{
  "insecure-registries": ["192.168.X.X:5000"]
}
```

Reiniciar Docker após: `sudo systemctl restart docker`

Se preferir HTTPS, configurar o Nginx Proxy Manager do datacenter como proxy
reverso do registry com certificado válido na rede interna.

### 5. Credenciais — mesmo tratamento da versão com internet

`flows_cred.json` permanece no volume local da borda. A imagem nova sobrescreve
`flows.json`, mas as credenciais Modbus/MongoDB no volume persistem intactas.

```yaml
# docker-compose.yml (borda) — descomentado
node-red:
  volumes:
    - node_red_modules:/data/node_modules
    - ${NODE_RED_DATA_PATH}:/data      # persiste flows_cred.json localmente
```

---

## Fluxo de trabalho após implementação

```
1. Abre browser → acessa Node-RED do datacenter
2. Edita flows → salva → flows.json atualizado no volume
3. git commit + push → GitHub Actions builda imagem → push GHCR (~3 min)
4. Script de mirror no datacenter detecta nova imagem → re-publica no registry local (~5 min)
5. Watchtower na borda detecta nova imagem no registry local → pull → restart (~5 min)
6. Node-RED da borda atualizado. Modbus continua coletando.
```

**Total: ~8-15 minutos. Zero toque na borda.**

---

## Diagrama de rede detalhado

```
Internet
    │
    ▼
DATACENTER VM (rede TI: 192.168.X.X)
├── :1880  → Node-RED editor (dev)
├── :5000  → Registry Docker local
└── :80/443 → Nginx Proxy Manager

rede TI interna ───────────────────────
                                       │
EDGE COMPUTER (rede TI: 192.168.X.Y)  │
├── :1880  → Node-RED (produção)       │
│     └── coleta Modbus                │
│                                      │
└── Watchtower ──────────── pull ──────┘
      (poll 192.168.X.X:5000)

rede máquinas (isolada, sem TI)
├── 192.168.1.10 → PAC3100 (Modbus TCP)
└── outros CLPs / inversores
```

---

## Arquivos a criar/modificar

| Arquivo | Local | Mudança |
|---------|-------|---------|
| `docker-compose.yml` | Datacenter (AMG_Infra) | Adicionar serviço `registry` |
| `docker-compose.yml` | Borda | Adicionar `watchtower`; mudar image para registry local |
| `scripts/mirror-node-red.sh` | Datacenter | Script de mirror GHCR → local |
| `/etc/docker/daemon.json` | Borda | Permitir registry HTTP inseguro |
| `node-red/Dockerfile` | Repositório | Fixar versão (remover `latest`) |
| `.github/workflows/build.yml` | Repositório | Opcional: webhook trigger no mirror |

---

## Verificação (checklist pós-implementação)

- [ ] `curl http://192.168.X.X:5000/v2/_catalog` retorna lista de imagens (registry ativo)
- [ ] Executar `mirror-node-red.sh` manualmente → imagem aparece no catalog local
- [ ] Na borda: `docker pull 192.168.X.X:5000/node-red:latest` funciona sem erros
- [ ] Watchtower inicia e aparece nos logs puxando do registry local
- [ ] Editar flow no datacenter → aguardar ~10-15 min → confirmar restart na borda
- [ ] Validar coleta Modbus contínua após restart (`docker logs node-red`)

---

## Comparativo das duas versões

| | Com internet | Sem internet (este plano) |
|--|-------------|--------------------------|
| **Complexidade** | Baixa | Média |
| **Serviços extras** | Watchtower | Watchtower + Registry + Mirror script |
| **Delay** | ~8-10 min | ~8-15 min |
| **Dependência externa** | GitHub + GHCR | Apenas GitHub (datacenter acessa GHCR) |
| **Dependência interna** | — | Registry local precisa estar saudável |
| **Manutenção** | Mínima | Monitorar espaço em disco do registry |
