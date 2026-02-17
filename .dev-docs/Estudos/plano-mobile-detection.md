# Plano: Detecção de Dispositivo e Interface Mobile

**Objetivo:** Detectar se é mobile e redirecionar automaticamente para interface Next.js otimizada

---

## 🎯 Comportamento Desejado

```
┌─────────────────────────────────────────────┐
│  Usuário acessa etd.easytek-data.com.br     │
└─────────────┬───────────────────────────────┘
              │
              ├─── Mobile? ──► Redireciona para /mobile (Next.js)
              │                └─► Interface touch-friendly
              │                └─► Cards grandes, navegação simples
              │                └─► Gráficos otimizados
              │
              └─── Desktop? ─► Mantém no / (Dash)
                               └─► Interface completa atual
```

---

## 🏗️ Arquitetura da Solução

### **Opção 1: Detecção no Backend (RECOMENDADO)** ⭐

**Vantagens:**
- ✅ Mais robusto (não pode ser contornado)
- ✅ Funciona sem JavaScript
- ✅ Controle centralizado

**Implementação:**
```python
# Flask middleware que detecta user-agent
# Redireciona mobile automaticamente para /mobile
```

### **Opção 2: Detecção no Frontend (ALTERNATIVA)**

**Vantagens:**
- ✅ Mais rápido de implementar
- ✅ Usuário pode escolher versão

**Implementação:**
```javascript
// JavaScript detecta tamanho de tela
// Oferece opção de ir para versão mobile
```

---

## 📋 Checklist de Implementação

### **Fase 1: Setup Next.js (2-3h)**

- [ ] Criar projeto `amg-mobile/` na raiz do AMG_Data
- [ ] Setup Next.js 14+ com TypeScript
- [ ] Configurar Tailwind CSS (design bonito)
- [ ] Criar layout base mobile-first
- [ ] Criar página inicial `/mobile`
- [ ] Integrar com API `/api/v1/user/profile`

### **Fase 2: Detecção de Dispositivo Flask (30min)**

- [ ] Criar middleware de detecção em `webapp/src/middleware/`
- [ ] Detectar user-agent mobile (iOS, Android)
- [ ] Redirecionar automaticamente para `/mobile`
- [ ] Adicionar cookie para preferência do usuário
- [ ] Permitir forçar versão desktop/mobile

### **Fase 3: Página Mobile Bonita (2-3h)**

- [ ] Dashboard com cards de OEE
- [ ] Gráficos responsivos (Chart.js ou Recharts)
- [ ] Navegação bottom-tab (iOS/Android style)
- [ ] Dark mode automático
- [ ] Animações suaves

### **Fase 4: Docker + NPM (30min)**

- [ ] Criar Dockerfile para Next.js
- [ ] Adicionar serviço ao `docker-compose.yml` (AMG_Infra)
- [ ] Configurar rota `/mobile` no NPM
- [ ] Build e deploy

---

## 🎨 Design da Interface Mobile

### **Paleta de Cores (baseada no Minty)**

```css
--primary: #78C2AD;      /* Verde água (Minty) */
--secondary: #F3969A;    /* Rosa suave */
--success: #56CC9D;      /* Verde */
--warning: #FFCE67;      /* Amarelo */
--danger: #FF7851;       /* Vermelho coral */
--dark: #343A40;         /* Cinza escuro */
```

### **Componentes Principais**

1. **Header Mobile**
   - Logo AMG
   - Nome do usuário
   - Botão de menu (hamburguer)

2. **Dashboard Cards**
   ```
   ┌─────────────────┐  ┌─────────────────┐
   │  OEE Geral      │  │  Disponibilidade│
   │  78.5%          │  │  85.2%          │
   │  ↗ +2.3%        │  │  ↘ -1.1%        │
   └─────────────────┘  └─────────────────┘
   ```

3. **Bottom Navigation**
   ```
   [ 🏠 Home ] [ 📊 Produção ] [ ⚙️ Manutenção ] [ 👤 Perfil ]
   ```

4. **Gráficos Touch-Friendly**
   - Grandes (fácil de tocar)
   - Zoom com pinch
   - Tooltips grandes

---

## 🔧 Tecnologias a Usar

### **Next.js Stack**

```json
{
  "next": "^14.0.0",
  "react": "^18.2.0",
  "typescript": "^5.0.0",
  "tailwindcss": "^3.3.0",
  "recharts": "^2.10.0",          // Gráficos responsivos
  "framer-motion": "^10.16.0",    // Animações
  "zustand": "^4.4.0",            // State management leve
  "swr": "^2.2.0"                 // Cache de API calls
}
```

### **User-Agent Detection (Flask)**

```python
from user_agents import parse

def is_mobile_device(request):
    user_agent = parse(request.headers.get('User-Agent', ''))
    return user_agent.is_mobile or user_agent.is_tablet
```

---

## 🚀 Implementação Passo a Passo

### **Passo 1: Criar Projeto Next.js**

```bash
cd "E:\Projetos Python\AMG_Data"
npx create-next-app@latest amg-mobile --typescript --tailwind --app --no-src-dir
cd amg-mobile
npm install recharts framer-motion zustand swr
```

### **Passo 2: Estrutura de Pastas**

```
amg-mobile/
├── app/
│   ├── layout.tsx           # Layout base
│   ├── page.tsx             # Home/Dashboard
│   ├── producao/
│   │   └── page.tsx         # OEE mobile
│   └── manutencao/
│       └── page.tsx         # Manutenção mobile
├── components/
│   ├── Header.tsx
│   ├── BottomNav.tsx
│   ├── OEECard.tsx
│   └── OEEChart.tsx
├── lib/
│   ├── api.ts               # Cliente API
│   └── hooks.ts             # Custom hooks
└── public/
    └── logo.svg
```

### **Passo 3: Middleware Flask**

```python
# webapp/src/middleware/mobile_detection.py
from flask import redirect, request, make_response
from user_agents import parse

def mobile_redirect_middleware():
    # Ignorar rotas de API e assets
    if request.path.startswith('/api/') or request.path.startswith('/assets/'):
        return None

    # Verificar preferência do usuário (cookie)
    force_desktop = request.cookies.get('force_desktop') == 'true'
    if force_desktop:
        return None

    # Detectar mobile
    user_agent = parse(request.headers.get('User-Agent', ''))
    is_mobile = user_agent.is_mobile or user_agent.is_tablet

    # Redirecionar mobile para /mobile
    if is_mobile and not request.path.startswith('/mobile'):
        return redirect('/mobile')

    return None
```

### **Passo 4: Página Mobile Exemplo**

```typescript
// amg-mobile/app/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { OEECard } from '@/components/OEECard';
import { Header } from '@/components/Header';
import { BottomNav } from '@/components/BottomNav';

export default function DashboardMobile() {
  const [user, setUser] = useState(null);
  const [oee, setOee] = useState(null);

  useEffect(() => {
    // Buscar perfil do usuário
    fetch('/api/v1/user/profile', { credentials: 'include' })
      .then(r => r.json())
      .then(setUser);

    // Buscar dados de OEE
    fetch('/api/v1/producao/oee?linha=LCT08', { credentials: 'include' })
      .then(r => r.json())
      .then(data => setOee(data.data));
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 to-blue-50">
      <Header user={user} />

      <main className="p-4 pb-20">
        <h1 className="text-2xl font-bold text-gray-800 mb-4">
          Dashboard de Produção
        </h1>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <OEECard
            title="OEE Geral"
            value={oee?.resumo?.oee || 0}
            trend={+2.3}
            color="green"
          />
          <OEECard
            title="Disponibilidade"
            value={oee?.resumo?.disponibilidade || 0}
            trend={-1.1}
            color="blue"
          />
        </div>

        {/* Mais componentes... */}
      </main>

      <BottomNav />
    </div>
  );
}
```

---

## ⏱️ Estimativa de Tempo

| Fase | Tempo | Complexidade |
|------|-------|--------------|
| Setup Next.js | 30min | Baixa |
| Layout base mobile | 1h | Média |
| Componentes (Cards, Charts) | 2h | Média |
| Integração API | 1h | Baixa |
| Middleware Flask | 30min | Baixa |
| Docker + NPM | 30min | Baixa |
| **Total** | **5-6h** | **Média** |

---

## 🎯 Resultado Final

### **Desktop (mantém como está):**
```
https://etd.easytek-data.com.br/
└─► Dash completo (atual)
```

### **Mobile (nova interface):**
```
https://etd.easytek-data.com.br/
└─► Detecta mobile
    └─► Redireciona para /mobile
        └─► Next.js otimizado
```

### **Forçar versão:**
```
https://etd.easytek-data.com.br/?desktop=true
└─► Seta cookie force_desktop
    └─► Mobile usa versão desktop
```

---

## 📝 Próximos Passos Imediatos

1. **Criar projeto Next.js** (agora)
2. **Implementar página exemplo** (2h)
3. **Adicionar middleware Flask** (30min)
4. **Testar localmente** (30min)
5. **Deploy** (30min)

---

Quer que eu comece criando o projeto Next.js agora? 🚀
