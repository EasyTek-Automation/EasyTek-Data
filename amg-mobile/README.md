# AMG Mobile - Interface Mobile Next.js

Interface mobile otimizada para AMG Data, construída com Next.js 14, TypeScript e Tailwind CSS.

---

## 🚀 Build via Docker (SEM Node.js instalado)

### Pré-requisitos

- Docker instalado
- Estar na pasta `AMG_Data/amg-mobile`

### Build da Imagem

```bash
# Na pasta amg-mobile/
docker build -t amg-mobile:latest .
```

Esse comando irá:
1. Instalar dependências (npm ci)
2. Build da aplicação Next.js
3. Criar imagem otimizada de produção

### Testar Localmente

```bash
# Rodar container
docker run -p 3000:3000 amg-mobile:latest

# Acessar
http://localhost:3000/mobile
```

---

## 🐳 Integração com AMG_Infra

### 1. Adicionar ao `docker-compose.yml`

No repositório `AMG_Infra/docker-compose.yml`, adicionar:

```yaml
  amg-mobile:
    image: amg-mobile:latest
    container_name: amg-mobile
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_API_URL=http://webapp:8050/api/v1
      - PORT=3000
    ports:
      - "3000:3000"  # Opcional - apenas para debug direto
    networks:
      - easytek-net
    depends_on:
      - webapp
```

### 2. Configurar Rota no Nginx Proxy Manager

1. Acessar NPM UI: `https://etdngx.easytek-data.com.br`
2. Editar host `etd.easytek-data.com.br`
3. Ir em **Custom Locations**
4. Adicionar:
   - **Location:** `/mobile`
   - **Forward:** `http://amg-mobile:3000`
   - **Websockets:** ✅

### 3. Deploy

```bash
# No servidor (via SSH)
cd /opt/easytek-infra

# Carregar imagem (opção 1: build local e enviar)
docker save amg-mobile:latest | ssh usuario@servidor docker load

# Ou (opção 2: build direto no servidor)
scp -r amg-mobile/ usuario@servidor:/tmp/
ssh usuario@servidor
cd /tmp/amg-mobile
docker build -t amg-mobile:latest .

# Iniciar container
docker compose up -d amg-mobile

# Verificar logs
docker compose logs -f amg-mobile
```

---

## 🎨 Estrutura do Projeto

```
amg-mobile/
├── app/
│   ├── layout.tsx           # Layout raiz
│   ├── page.tsx             # Dashboard principal (/mobile)
│   ├── globals.css          # Estilos globais
│   ├── producao/            # Páginas de produção (futuro)
│   └── manutencao/          # Páginas de manutenção (futuro)
│
├── components/
│   ├── Header.tsx           # Cabeçalho com avatar e logo
│   ├── BottomNav.tsx        # Navegação inferior (tabs)
│   ├── OEECard.tsx          # Card de métricas OEE
│   └── LoadingSpinner.tsx   # Loading state
│
├── lib/                     # Utilitários (futuro)
├── public/                  # Assets estáticos
│
├── Dockerfile               # Build otimizado multi-stage
├── next.config.js           # Config do Next.js
├── tailwind.config.ts       # Config do Tailwind
└── package.json             # Dependências
```

---

## 🎯 Funcionalidades Implementadas

### ✅ Dashboard Principal (`/mobile`)

- **Header com avatar** e badge de nível de acesso
- **Cards de OEE** (4 métricas principais):
  - OEE Geral
  - Disponibilidade
  - Performance
  - Qualidade
- **Tendências** (setas e percentuais)
- **Informações do usuário** (perfil, nível, email)
- **Bottom Navigation** (Home, Produção, Manutenção, Perfil)

### ✅ Autenticação

- Integrada com API REST do Flask (`/api/v1/user/profile`)
- Cookies compartilhados (domínio único)
- Redirect para login se não autenticado

### ✅ Design

- **Mobile-first** (otimizado para smartphone)
- **Tailwind CSS** (utilitário, leve)
- **Gradientes** baseados no tema Minty
- **Animações suaves** (slide-up, transitions)
- **Touch-friendly** (botões grandes, espaçamento adequado)

---

## 🔧 Desenvolvimento Local (Se tiver Node.js)

```bash
# Instalar dependências
npm install

# Rodar em modo dev
npm run dev

# Acessar
http://localhost:3000/mobile
```

**Nota:** Para integração com API, precisa de proxy ou CORS configurado no Flask.

---

## 📊 Próximas Funcionalidades

### Fase 2 (Em Desenvolvimento)

- [ ] Página de Produção (`/mobile/producao`)
  - Gráficos de OEE por linha
  - Histórico de produção
  - Estados da máquina

- [ ] Página de Manutenção (`/mobile/manutencao`)
  - Alarmes ativos
  - KPIs de manutenção
  - Indicadores (MTBF, MTTR)

- [ ] Página de Perfil (`/mobile/perfil`)
  - Dados do usuário
  - Configurações
  - Logout
  - Forçar versão desktop

### Fase 3 (Futuro)

- [ ] Dark mode toggle
- [ ] Offline support (PWA)
- [ ] Push notifications
- [ ] Gráficos interativos (zoom, pan)
- [ ] Filtros por data/linha

---

## 🐛 Troubleshooting

### Build falha

```bash
# Limpar cache Docker
docker builder prune

# Rebuild sem cache
docker build --no-cache -t amg-mobile:latest .
```

### Container não inicia

```bash
# Ver logs
docker logs amg-mobile

# Verificar rede
docker network ls | grep easytek-net
```

### API não conecta

- Verificar que `webapp` está na mesma rede (`easytek-net`)
- Verificar variável `NEXT_PUBLIC_API_URL`
- Verificar cookies (mesma domínio)

---

## 📝 Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `NODE_ENV` | Ambiente (production/development) | `production` |
| `PORT` | Porta do servidor | `3000` |
| `NEXT_PUBLIC_API_URL` | URL da API Flask | `http://webapp:8050/api/v1` |

---

## 🎓 Stack Tecnológica

- **Framework:** Next.js 14 (App Router)
- **Linguagem:** TypeScript 5
- **Estilização:** Tailwind CSS 3.4
- **UI Components:** React 18
- **Animações:** Framer Motion 11
- **State:** Zustand 4.5
- **Data Fetching:** SWR 2.2
- **Charts:** Recharts 2.10

---

## 📄 Licença

Propriedade da AMG/EasyTek - Uso interno apenas.
