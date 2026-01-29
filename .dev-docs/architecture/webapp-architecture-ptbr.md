# CLAUDE-PTBR.md

Este arquivo fornece orientações para o Claude Code (claude.ai/code) ao trabalhar com código neste repositório.

## Visão Geral

AMG_Data é uma plataforma de dados IoT industrial construída com Dash/Plotly para monitoramento e análise em tempo real. O sistema consiste em:

- **webapp**: Aplicação web Dash principal com arquitetura multi-página
- **event-gateway**: Serviço de gateway MQTT para publicação de comandos em equipamentos industriais
- **node-red**: Fluxos Node-RED para ingestão e processamento de dados
- **nginx**: Configuração de proxy reverso

A plataforma fornece dashboards para monitoramento de produção (OEE), consumo de energia, alarmes de manutenção, controle supervisório e gerenciamento de utilidades.

## Comandos Comuns

### Desenvolvimento

```bash
# Executar a webapp localmente (modo desenvolvimento)
cd webapp
python run_local.py

# Alternativa: Executar a partir do diretório src
cd webapp/src
python run.py
```

### Serviço de Gateway de Eventos

```bash
# Executar o serviço de gateway MQTT
cd event-gateway
python api.py
# Por padrão executa em http://localhost:5001
```

### Ambiente Python

```bash
# Ativar ambiente virtual
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependências para webapp
cd webapp
pip install -r requirements.txt

# Instalar dependências para event-gateway
cd event-gateway
pip install -r requirements.txt
```

### Configuração do Ambiente

Tanto `webapp` quanto a raiz do projeto requerem arquivos `.env`. Variáveis de ambiente obrigatórias:

```
# Conexão MongoDB
MONGO_URI=mongodb://...
DB_NAME=nome_do_seu_banco

# Segurança Flask
SECRET_KEY=sua_chave_secreta

# Broker MQTT (para event-gateway)
MQTT_BROKER_ADDRESS=endereco_broker
MQTT_BROKER_PORT=8883
MQTT_USERNAME=usuario
MQTT_PASSWORD=senha

# Opcionais
GATEWAY_URL=http://localhost:5001
PORT=8050
LOG_LEVEL=DEBUG  # Opções: DEBUG, INFO, WARNING, ERROR
DOCS_PROCEDURES_PATH=/caminho/para/procedimentos  # Volume externo para documentação de procedimentos
```

## Arquitetura

### Estrutura da Aplicação

```
webapp/src/
├── app.py              # Inicialização do servidor Flask & app Dash (inclui config do favicon)
├── run.py              # Ponto de entrada da aplicação
├── index.py            # Orquestração principal de roteamento e layout
├── header.py           # Barra de navegação superior com mega menus
├── sidebar.py          # Barra lateral retrátil com conteúdo dinâmico
├── callbacks.py        # Registro central de callbacks
├── callbacks_registers/  # Módulos de callback (um por funcionalidade)
│   ├── main_layout_callbacks.py
│   ├── sidebar_content_callback.py
│   ├── sidebar_filters_callback.py
│   ├── sidebar_toggle_callback.py
│   ├── sidebar_default_dates_callback.py
│   ├── oeegraph_callback.py
│   ├── kpicards_callback.py
│   ├── energygraph_callback.py
│   ├── hourlyconsumption_callback.py
│   ├── states_callbacks.py
│   ├── alarms_callbacks.py
│   ├── procedures_collapse_callbacks.py
│   ├── energy_config_callbacks.py
│   ├── create_user_callbacks.py
│   ├── manage_users_callbacks.py
│   ├── change_password_callbacks.py
│   ├── input_bridge_callbacks.py  # Ponte entre filtros do header e sidebar
│   └── ... (30+ módulos de callback especializados)
├── components/         # Componentes UI reutilizáveis
│   ├── icons.py        # Componentes de ícones SVG
│   ├── stores.py       # Componentes dcc.Store da aplicação
│   ├── dropdown_footer.py  # Rodapé de dropdown reutilizável
│   ├── demo_badge.py   # Componente de badge de dados demo
│   ├── headers/        # Módulos de filtros de cabeçalho específicos por página
│   │   ├── energy_filters.py
│   │   ├── states_filters.py
│   │   └── default_filters.py
│   ├── sidebars/       # Módulos de conteúdo de sidebar específicos por página
│   │   ├── __init__.py
│   │   ├── dashboard_sidebar.py
│   │   ├── states_sidebar.py
│   │   ├── superv_sidebar.py
│   │   ├── energy_sidebar.py  # Inclui cálculos de custo SE03
│   │   ├── procedures_sidebar.py  # Navegação da documentação de procedimentos
│   │   └── default_sidebar.py
│   └── ... (componentes de gráficos e cards)
├── config/             # Módulos de configuração
│   ├── access_control.py   # Matriz de permissões de rotas e menus
│   ├── theme_config.py     # Configuração de tema Dash Bootstrap
│   ├── user_loader.py      # Carregador de usuário Flask-Login
│   ├── docs_config.py      # Configuração do sistema de documentação/procedimentos
│   └── demo_data_config.py # Configuração de badges de dados demo
├── database/
│   └── connection.py   # Conexão MongoDB & modelo User
├── pages/              # Layouts de página organizados por domínio
│   ├── admin/          # Gerenciamento de usuários (create_user, manage_users)
│   ├── auth/           # Login, registro, alterar senha
│   ├── dashboards/     # Home, OEE de produção
│   ├── energy/         # Páginas de monitoramento de energia (overview, config)
│   ├── production/     # Rastreamento de estado de produção
│   ├── maintenance/    # Alarmes e procedimentos (documentação baseada em markdown)
│   ├── supervision/    # Controle supervisório (tipo SCADA)
│   ├── reports/        # Páginas de relatórios
│   └── common/         # Páginas compartilhadas (access_denied, under_development)
├── assets/             # Arquivos estáticos (CSS, imagens)
│   ├── dropdown_menus.css  # Estilo de mega menu
│   ├── markdown.css        # Estilos de renderização markdown
│   └── ... (outros CSS e imagens)
└── utils/
    ├── permissions.py  # Lógica de controle de acesso
    ├── helpers.py      # Funções utilitárias
    ├── empty_state.py  # Componentes de estado vazio
    └── demo_helpers.py # Helpers de dados demo
```

### Padrões Arquiteturais Principais

#### 1. Sistema de Roteamento (`index.py`)

- Dicionário central `ROUTES` mapeia pathnames para funções de layout de página
- Aliases de rota fornecem compatibilidade retroativa (`ROUTE_ALIASES`)
- Controle de acesso integrado ao roteamento via `check_access()`
- Construtor de layout principal (`_build_main_layout()`) combina header, sidebar e conteúdo da página

**Aliases de Rotas** (definidos em `index.py`):
```python
ROUTE_ALIASES = {
    '/dashboard': '/production/oee',
    '/states': '/production/states',
    '/superv': '/supervision',
    '/production/alarms': '/maintenance/alarms',
    '/alarms': '/maintenance/alarms',
}
```

**Estrutura de Rotas de Utilidades**:
- `/utilities/energy`: Visão geral de energia (alias: `/energy`)
- `/utilities/energy/config`: Configuração de tarifas de energia (somente admin)
- `/utilities/energy/se01-se04`: Subestações individuais (em desenvolvimento)
- `/utilities/water`: Monitoramento de consumo de água (em desenvolvimento)
- `/utilities/gas`: Monitoramento de gás natural (em desenvolvimento)
- `/utilities/compressed-air`: Sistema de ar comprimido (em desenvolvimento)
- `/utilities/dashboard`: Dashboard integrado de utilidades (em desenvolvimento)

#### 2. Sistema de Controle de Acesso

**Modelo de permissão bidimensional** (definido em `config/access_control.py`):

- **Vertical (level)**: 1 = básico, 2 = avançado, 3 = admin
- **Horizontal (perfil)**:
  - `manutencao` - Equipe de manutenção
  - `qualidade` - Equipe de controle de qualidade
  - `producao` - Equipe de produção
  - `utilidades` - Equipe de utilidades (energia, água, gás, ar)
  - `admin` - Administradores do sistema
  - `meio_ambiente` - Equipe de meio ambiente
  - `seguranca` - Equipe de segurança
  - `engenharias` - Equipe de engenharia

As rotas podem ser:
- **Compartilhadas** (`shared=True`): Todos os perfis podem acessar se o requisito de nível for atendido
- **Específicas de perfil** (`shared=False`): Requer perfil(s) específico(s) E nível

Fluxo de verificação de permissão:
1. Busca de configuração de rota em `ROUTE_ACCESS`
2. Verificação de nível: `user.level >= min_level`
3. Verificação de perfil (se não compartilhado): `user.perfil in perfis`
4. Em caso de negação: Mostra página de acesso negado com motivo

#### 3. Autenticação de Usuário (`database/connection.py`)

- Integração Flask-Login com classe `User`
- Coleção MongoDB `usuarios` armazena documentos de usuário
- Campos do modelo User: `username`, `email`, `password` (hash), `level`, `perfil`
- Padrão singleton de conexão global para cliente MongoDB

#### 4. Padrão de Registro de Callbacks

Todos os callbacks registrados em `callbacks.py` via funções modulares:

```python
def register_callbacks(app):
    collection_graph = get_mongo_connection('DecapadoPerformance')
    register_oeegraph_callbacks(app, collection_graph)
    register_kpicards_callbacks(app, collection_graph)
    # ... mais registros
```

Cada módulo de callback em `callbacks_registers/` exporta uma função `register_*_callbacks(app, ...)`.

#### 5. Sistema de Header (`header.py`)

Barra de navegação superior localizada em `src/header.py` com:

- **Navegação Mega Menu**: Menus dropdown multi-coluna para seção de Utilidades
  - Energia Elétrica (com opções de subestação SE01-SE04)
  - Água, Gás Natural, Ar Comprimido
- **Filtros Dinâmicos de Página**: `get_filters_for_page(pathname)` carrega filtros de `components/headers/`
- **Alternador de Tema**: Componente `ThemeSwitchAIO` para modo claro/escuro
- **Menu Hambúrguer**: Alternância para recolher/expandir sidebar
- **Dropdown de Perfil de Usuário**: Avatar, informações de perfil, badge de nível, logout
- **Menus Baseados em Permissão**: Usa `can_see_menu()` para mostrar/ocultar itens

**Filtros Específicos de Página** (em `components/headers/`):
- `energy_filters.py`: Dropdowns de equipamento e seletores de data/hora
- `states_filters.py`: Filtros para monitoramento de estado de produção
- `default_filters.py`: Layout de filtro genérico

#### 6. Sistema de Sidebar (`sidebar.py`)

Barra lateral retrátil localizada em `src/sidebar.py` com:

- **Logo da Empresa**: Exibido no topo
- **Conteúdo Dinâmico**: `get_sidebar_content_for_page(pathname)` carrega conteúdo por rota
- **Gerenciamento de Estado**: Estado expandido/recolhido armazenado em `dcc.Store`
- **Transições CSS**: Animações suaves de recolher/expandir

**Conteúdo de Sidebar Específico de Página** (em `components/sidebars/`):
- `dashboard_sidebar.py`: Navegação de Dashboard/OEE
- `states_sidebar.py`: Navegação de estados de produção
- `superv_sidebar.py`: Controles de supervisão
- `energy_sidebar.py`: Página de energia com cálculos de custo dinâmicos
  - `create_se03_cost_sidebar_with_groups()`: Detalhamento de custo por grupos de equipamento (Transversais/Longitudinais)
  - `create_se03_cost_sidebar_content()`: Cálculo de custo passo a passo detalhado (versão debug)
  - `create_energy_sidebar_no_config()`: Alerta quando configuração de tarifa está faltando
  - `create_default_energy_sidebar_content()`: Padrão para abas não-SE03
- `procedures_sidebar.py`: Árvore de navegação de documentação (estrutura hierárquica do docs.yml)
- `default_sidebar.py`: Conteúdo genérico de fallback

**Importante**: O conteúdo da sidebar é determinado APÓS resolução de aliases de rota.

**Sincronização de Filtros de Data**:
- Seletores de data da sidebar são sincronizados com seletores de data do header via `input_bridge_callbacks.py`
- Datas padrão são definidas por `sidebar_default_dates_callback.py` (últimos 7 dias)
- Mudanças nos filtros do header ou sidebar atualizam ambas as localizações
- Armazenados em componentes `dcc.Store` para persistência durante navegação

#### 7. Coleções MongoDB

Principais coleções referenciadas no código:
- `usuarios`: Contas de usuário
- `DecapadoPerformance`: Métricas de OEE e produção
- `DecapadoFalhas`: Mensagens de falha/alarme
- `DecapadoTemp`: Dados de sensor de temperatura
- `AMG_EnergyData`: Dados de consumo de energia
- `AMG_Consumo`: Agregados de consumo horário

#### 8. Sistema de Documentação (`config/docs_config.py`)

**Sistema de Documentação de Procedimentos** para procedimentos de manutenção:

- **Suporte a Volume Externo**: Documentos armazenados em volume externo via variável de ambiente `DOCS_PROCEDURES_PATH`
- **Configuração YAML**: Arquivo `docs.yml` define estrutura de navegação com seções/subseções
- **Hot-Reload**: Recarga automática quando `docs.yml` muda (rastreamento de tempo de modificação)
- **Modo Fallback**: Escaneia diretório automaticamente se `docs.yml` não existir
- **Extração de Título**: Extrai automaticamente títulos H1 de arquivos markdown
- **Segurança**: Proteção contra travessia de caminho para prevenir acesso fora do volume

**Estrutura de Configuração** (`docs.yml`):
```yaml
title: "Procedimentos"
icon: "bi-book"
index: "index.md"  # Homepage opcional
sections:
  - name: "preventive"
    label: "Manutenção Preventiva"
    icon: "bi-calendar-check"
    expanded: true
    files:
      - path: "preventive/procedure1.md"
        title: "Título auto-extraído ou customizado"
```

**Funções Principais**:
- `get_docs_path()`: Retorna caminho do volume (variável de ambiente ou fallback)
- `load_docs_structure()`: Carrega e armazena em cache estrutura de navegação
- `get_markdown_title(filepath)`: Extrai título do H1 do markdown
- `check_file_exists(relative_path)`: Valida arquivo com verificações de segurança

#### 9. Sistema de Dados Demo (`config/demo_data_config.py`)

**Sistema de Badge Demo** para indicar dados não-produção:

- **Alternância Global**: `ENABLE_DEMO_BADGES` habilita/desabilita todos os badges
- **Controle por Página**: Dicionário `DEMO_PAGES` controla badges por rota
- **Controle por Componente**: Dicionário `DEMO_COMPONENTS` controla por tipo de componente
- **Funções Helper**: `should_show_demo_badge()`, `get_demo_pages()`

**Padrão de Uso**:
```python
from src.config.demo_data_config import should_show_demo_badge
from src.components.demo_badge import create_demo_badge

# No layout da página
if should_show_demo_badge(page_path="/production/oee"):
    badge = create_demo_badge()
```

**Lógica de Exibição de Badge**:
1. Verificar flag global `ENABLE_DEMO_BADGES`
2. Verificar configuração específica de página ou componente
3. Renderizar badge se ambas as condições forem verdadeiras

### Fluxo de Inicialização da Aplicação

1. **app.py**: Inicializa servidor Flask, app Dash, Flask-Login
2. **run.py**: Carrega template de tema, importa módulo index (dispara registro de callbacks)
3. **index.py**: Define layout da app, importa todos os módulos de página, registra callbacks de rota
4. **callbacks.py**: Registra todos os callbacks específicos de funcionalidade

Quando usuário navega:
1. Mudança de localização `url` dispara callback de roteamento
2. Verifica status de autenticação
3. Resolve aliases de rota
4. **Verifica permissões** via `check_access()`
5. Carrega layout de página ou mostra acesso negado
6. Constrói layout principal com header, sidebar, conteúdo
7. Carrega conteúdo dinâmico de sidebar baseado na rota resolvida

## Notas Importantes de Desenvolvimento

### Adicionando Novas Páginas

1. Criar módulo de página no subdiretório apropriado de `pages/` com função/variável `layout`
2. Adicionar rota ao dicionário `ROUTES` em `index.py`
3. Adicionar configuração de permissão a `ROUTE_ACCESS` em `config/access_control.py`
4. Se callbacks forem necessários, criar módulo em `callbacks_registers/` e registrar em `callbacks.py`
5. Se página precisar de conteúdo customizado de sidebar, adicionar módulo em `components/sidebars/` e atualizar `get_sidebar_content_for_page()` em `sidebar.py`
6. Se página precisar de filtros customizados de header, adicionar módulo em `components/headers/` e atualizar `get_filters_for_page()` em `header.py`

### Modificando Controle de Acesso

- Editar `config/access_control.py` para mudar permissões de rota/menu
- Nunca codificar verificações de permissão diretamente nas páginas individuais
- Usar `check_access()` de `utils/permissions.py` para verificações programáticas
- Visibilidade de menu controlada via configuração `MENU_ACCESS`

### Trabalhando com MongoDB

- Sempre usar `get_mongo_connection(collection_name)` para obter coleções
- Conexão é singleton - primeira chamada estabelece conexão, chamadas subsequentes reutilizam
- Tratar exceções `ConnectionError` para falhas de banco de dados

### Tema e Estilização

- Tema Bootstrap configurado em `app.py`: templates `MINTY` e `darkly` carregados
- Dash Bootstrap Components (dbc) usado em todo o sistema
- Funcionalidade de alternância de tema customizada via `ThemeSwitchAIO`
- Arquivos CSS customizados no diretório `assets/`:
  - `dropdown_menus.css`: Estilo de mega menu
  - `markdown.css`: Estilos de renderização markdown
- Favicon configurado via `app.index_string` para usar `/assets/favicon.ico`

### Componentes UI e Layouts

**Páginas em Desenvolvimento** (`pages/common/under_development.py`):
- Função de layout centralizada para páginas ainda não implementadas
- Usa grid Bootstrap responsivo com colunas offset para centralização
- Variantes pré-configuradas: `states_development()`, `alarms_development()`, `maintenance_development()`, `utilities_development()`, `config_development()`, etc.
- Layout se adapta corretamente aos estados de recolher/expandir da sidebar

**Padrão Multi-Tab** (ex: `pages/energy/overview.py`):
- Usa `dbc.Tabs` para organizar conteúdo por categoria
- Conteúdo de tab carregado dinamicamente via callbacks
- Tabs em desenvolvimento usam helper `get_under_development_content()`
- Tabs totalmente desenvolvidas (como SE03) incluem múltiplos gráficos e cards KPI

**Sistema de Cálculo de Custo de Energia** (`pages/energy/overview.py` + `energy_sidebar.py`):
- **Tab SE03**: Cálculo avançado de custo com detalhamento por grupos de equipamento
  - Grupo Transversais: MM02, MM04, MM06
  - Grupo Longitudinais: MM03, MM05, MM07
- **Componentes de Custo**: TUSD (transmissão), Energia (consumo), Demanda (encargos de demanda)
- **Precificação por Horário de Uso**: Cálculos separados para Ponta (pico) e Fora Ponta (fora de pico)
- **Cálculo de Demanda**: Sempre usa dados do mês completo, rateado por porcentagem de consumo
- **Configuração de Tarifa**: Página apenas admin em `/utilities/energy/config`
- **Atualizações em Tempo Real**: Sidebar atualiza dinamicamente quando intervalo de data ou seleção de equipamento muda

**Componente Demo Badge** (`components/demo_badge.py`):
- Design de badge consistente para marcar dados não-produção
- Controlado por configurações de `demo_data_config.py`
- Usado em páginas e componentes

**Sistema de Ícones** (`components/icons.py`):
- Componentes de ícones SVG centralizados
- Usado em menus de header e elementos UI
- Estilização consistente em toda a aplicação

### Publicação de Comandos MQTT

Para enviar comandos a equipamentos:
1. Frontend faz POST para `{GATEWAY_URL}/api/command`
2. Gateway de eventos publica para broker MQTT com TLS
3. Formato de payload: `{"topic": "device/command", "payload": "command_data"}`

### Sistema de Documentação (Procedimentos)

**Adicionando/Atualizando Procedimentos**:
1. Colocar arquivos markdown em volume externo (caminho definido por `DOCS_PROCEDURES_PATH`)
2. Criar ou atualizar `docs.yml` na raiz do volume com estrutura de navegação
3. Sistema recarrega automaticamente quando `docs.yml` é modificado
4. Títulos são auto-extraídos dos cabeçalhos H1 markdown se não especificados no YAML

**Estrutura do docs.yml**:
```yaml
title: "Procedimentos"
icon: "bi-book"
sections:
  - name: "nome_categoria"
    label: "Nome de Exibição"
    icon: "bi-nome-icone"
    expanded: false
    files:
      - path: "caminho/relativo/para/arquivo.md"
        title: "Título customizado opcional"
```

**Considerações de Segurança**:
- Travessia de caminho é prevenida - arquivos devem estar dentro de `DOCS_PROCEDURES_PATH`
- Controle de acesso é aplicado no nível de rota via `ROUTE_ACCESS`

### Sistema de Dados Demo

**Gerenciando Badges Demo**:
1. Controle global: Definir `ENABLE_DEMO_BADGES = False` em `config/demo_data_config.py` para ocultar todos os badges
2. Controle por página: Atualizar dicionário `DEMO_PAGES` para habilitar/desabilitar páginas específicas
3. Controle por componente: Atualizar dicionário `DEMO_COMPONENTS` para componentes específicos

**Adicionando Badge Demo a Nova Página**:
```python
from src.config.demo_data_config import should_show_demo_badge
from src.components.demo_badge import create_demo_badge

def layout():
    badge = create_demo_badge() if should_show_demo_badge(page_path="/sua/rota") else None
    # Incluir badge no layout
```

### Funcionalidades do Modo Desenvolvimento

- Hot reload habilitado ao executar via `run_local.py`
- Modo debug fornece mensagens de erro detalhadas
- Overlay de carregamento com spinner durante carregamento inicial da página
- Validação de ambiente no startup (verifica variáveis de ambiente obrigatórias)

## Limitações Conhecidas e Funcionalidades Futuras

### Em Desenvolvimento

**Módulo de Produção**:
- `/production/states`: Monitoramento de estado de produção (em desenvolvimento)

**Módulo de Energia**:
- SE01, SE02, SE04: Monitoramento de subestação individual (SE03 está totalmente funcional)
- `/utilities/energy/history`: Análise de consumo histórico
- `/utilities/energy/costs`: Dashboard de análise de custos

**Módulo de Utilidades** (tudo em desenvolvimento):
- Monitoramento de consumo de água e rastreamento de custos
- Monitoramento de gás natural (pontos de medição, histórico, custos)
- Sistema de ar comprimido (compressores, análise de eficiência)
- Dashboard integrado de utilidades (visão consolidada de todas as utilidades)

**Módulo de Manutenção**:
- Sistema de gerenciamento de ordens de serviço
- Cronograma/calendário de manutenção
- Histórico e análises de manutenção
- Indicadores/KPIs de manutenção

**Módulo de Configuração**:
- Gerenciamento de preferências de usuário
- Visualizador de logs do sistema

### Funcionalidades Totalmente Funcionais

- Autenticação e autorização de usuário
- Dashboard OEE com métricas de produção
- Monitoramento de energia para SE03 (com cálculos de custo)
- Configuração de tarifas de energia (somente admin)
- Monitoramento e histórico de alarmes
- Sistema de documentação de procedimentos de manutenção
- Interface de controle supervisório
- Gerenciamento de usuários (criar, editar, deletar usuários)

## Estrutura de Branches Git

- **Branch principal**: `main`
- Padrão atual de branch de funcionalidade: `feature/[NomeFuncionalidade]` (ex: `feature/mkdocs`)
- Estilo de mensagem de commit: formato Conventional Commits
  - `feat(escopo): descrição` para novas funcionalidades
  - `fix(escopo): descrição` para correções de bugs
  - `refactor(escopo): descrição` para refatoração

## Considerações de Segurança

- SECRET_KEY deve ser definida via variável de ambiente (aplicação falha se ausente)
- Senhas com hash `pbkdf2:sha256` via Werkzeug
- Conexões MQTT usam TLS (porta 8883) com autenticação
- Sem credenciais hardcoded - todas via arquivos `.env`
- Arquivos `.env` estão no gitignore

## Stack Tecnológico

- **Backend**: Flask 3.1.1 com Flask-Login 0.6.3
- **Frontend**: Dash 3.1.1, Dash Bootstrap Components 2.0.3, Dash Bootstrap Templates 2.1.0
- **Banco de Dados**: MongoDB via PyMongo 4.13.2
- **Visualização**: Plotly 6.1.2
- **Processamento de Dados**: Pandas 2.3.1, NumPy 2.3.2
- **Documentação**: Markdown 3.7, PyYAML (para configuração docs.yml)
- **MQTT**: Paho-MQTT (em event-gateway)
- **Servidor Web**: Gunicorn (produção)
- **Outros**: python-dotenv 1.1.1, Werkzeug 3.1.3
