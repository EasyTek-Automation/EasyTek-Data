# Dockerfile para AMG Mobile (Next.js)
# Build otimizado em múltiplos estágios

# Estágio 1: Dependências
FROM node:20-alpine AS deps
WORKDIR /app

# Copiar package files
COPY package.json package-lock.json* ./

# Instalar dependências
RUN npm ci --prefer-offline --no-audit

# Estágio 2: Build
FROM node:20-alpine AS builder
WORKDIR /app

# Copiar dependências do estágio anterior
COPY --from=deps /app/node_modules ./node_modules

# Copiar código fonte
COPY . .

# Build da aplicação
RUN npm run build

# Estágio 3: Runner (produção)
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# Criar usuário não-root
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copiar arquivos necessários
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Comando de start
CMD ["node", "server.js"]
