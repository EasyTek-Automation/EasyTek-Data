# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

AMG_Data is an industrial IoT data platform built with Dash/Plotly for real-time monitoring and analytics. The system consists of:

- **webapp**: Main Dash web application with multi-page architecture
- **event-gateway**: MQTT gateway service for publishing commands to industrial equipment
- **node-red**: Node-RED flows for data ingestion and processing
- **nginx**: Reverse proxy configuration

The platform provides dashboards for production monitoring (OEE), energy consumption, maintenance alarms, supervisory control, and utility management.

## Common Commands

### Development

```bash
# Run the webapp locally (development mode)
cd webapp
python run_local.py

# Alternative: Run from src directory
cd webapp/src
python run.py
```

### Event Gateway Service

```bash
# Run the MQTT gateway service
cd event-gateway
python api.py
# Default runs on http://localhost:5001
```

### Python Environment

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies for webapp
cd webapp
pip install -r requirements.txt

# Install dependencies for event-gateway
cd event-gateway
pip install -r requirements.txt
```

### Environment Setup

Both `webapp` and the project root require `.env` files. Required environment variables:

```
# MongoDB connection
MONGO_URI=mongodb://...
DB_NAME=your_database_name

# Flask security
SECRET_KEY=your_secret_key

# MQTT broker (for event-gateway)
MQTT_BROKER_ADDRESS=broker_address
MQTT_BROKER_PORT=8883
MQTT_USERNAME=username
MQTT_PASSWORD=password

# Optional
GATEWAY_URL=http://localhost:5001
PORT=8050
LOG_LEVEL=DEBUG  # Options: DEBUG, INFO, WARNING, ERROR
DOCS_PROCEDURES_PATH=/path/to/procedures  # External volume for procedure documentation
```

### Offline Mode

A aplicação está configurada para funcionar **completamente offline**, sem dependências de CDNs externos. Todos os recursos (Bootstrap themes, Font Awesome) são servidos localmente.

#### Recursos Localizados

- **Bootstrap Themes**: Minty (tema claro) e Darkly (tema escuro) do Bootswatch 5.3.6
- **Font Awesome**: Versão 5.10.2 (CSS + webfonts)
- **Localização**: `webapp/src/assets/vendor/`

#### Scripts de Gerenciamento

```bash
# Download de recursos externos (primeira configuração ou atualização)
cd webapp
python scripts/download_offline_resources.py

# Validação de configuração offline
python scripts/validate_offline.py
```

**Download de Recursos**: Baixa automaticamente Bootstrap e Font Awesome dos CDNs e ajusta URLs internas do CSS para caminhos relativos locais.

**Validação**: Verifica que:
- Todos os 6 arquivos de recursos estão presentes
- Nenhuma referência a CDNs no código
- Configurações corretas em `app.py` e `theme_config.py`

#### Estrutura de Assets

```
webapp/src/assets/
├── vendor/                    # Recursos de terceiros
│   ├── bootstrap/
│   │   ├── minty/
│   │   │   └── bootstrap.min.css
│   │   └── darkly/
│   │       └── bootstrap.min.css
│   └── fontawesome/
│       ├── css/
│       │   └── all.min.css
│       └── webfonts/
│           ├── fa-brands-400.woff2
│           ├── fa-regular-400.woff2
│           └── fa-solid-900.woff2
├── [CSS customizados...]
└── favicon.ico
```

#### Atualizando Versões

Para atualizar Bootstrap ou Font Awesome:

1. Editar URLs em `webapp/scripts/download_offline_resources.py`
2. Executar: `python scripts/download_offline_resources.py`
3. Testar aplicação
4. Validar: `python scripts/validate_offline.py`

**Documentação completa**: Ver `webapp/scripts/README.md`

#### Teste Offline

Para verificar que a aplicação funciona sem internet:

1. Desconectar Wi-Fi/Ethernet
2. Iniciar aplicação: `python webapp/src/run.py`
3. Abrir navegador: `http://localhost:8050`
4. Verificar DevTools → Network tab (nenhuma requisição externa deve falhar)
5. Testar comutação de temas e navegação entre páginas

## Architecture

### Application Structure

```
webapp/src/
├── app.py              # Flask server & Dash app initialization (includes favicon config)
├── run.py              # Application entry point
├── index.py            # Main routing and layout orchestration
├── header.py           # Top navigation bar with mega menus
├── sidebar.py          # Collapsible sidebar with dynamic content
├── callbacks.py        # Central callback registration
├── callbacks_registers/  # Callback modules (one per feature)
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
│   ├── input_bridge_callbacks.py  # Bridge between header filters and sidebar
│   └── ... (30+ specialized callback modules)
├── components/         # Reusable UI components
│   ├── icons.py        # SVG icon components
│   ├── stores.py       # Application dcc.Store components
│   ├── dropdown_footer.py  # Reusable dropdown footer
│   ├── demo_badge.py   # Demo data badge component
│   ├── headers/        # Page-specific header filter modules
│   │   ├── energy_filters.py
│   │   ├── states_filters.py
│   │   └── default_filters.py
│   ├── sidebars/       # Page-specific sidebar content modules
│   │   ├── __init__.py
│   │   ├── dashboard_sidebar.py
│   │   ├── states_sidebar.py
│   │   ├── superv_sidebar.py
│   │   ├── energy_sidebar.py  # Includes SE03 cost calculations
│   │   ├── procedures_sidebar.py  # Procedures documentation navigation
│   │   └── default_sidebar.py
│   └── ... (graph and card components)
├── config/             # Configuration modules
│   ├── access_control.py   # Route & menu permissions matrix
│   ├── theme_config.py     # Dash Bootstrap theme configuration
│   ├── user_loader.py      # Flask-Login user loader
│   ├── docs_config.py      # Documentation/procedures system configuration
│   └── demo_data_config.py # Demo data badges configuration
├── database/
│   └── connection.py   # MongoDB connection & User model
├── pages/              # Page layouts organized by domain
│   ├── admin/          # User management (create_user, manage_users)
│   ├── auth/           # Login, registration, change password
│   ├── dashboards/     # Home, production OEE
│   ├── energy/         # Energy monitoring pages (overview, config)
│   ├── production/     # Production state tracking
│   ├── maintenance/    # Alarms and procedures (markdown-based documentation)
│   ├── supervision/    # Supervisory control (SCADA-like)
│   ├── reports/        # Reporting pages
│   └── common/         # Shared pages (access_denied, under_development)
├── assets/             # Static files (CSS, images)
│   ├── dropdown_menus.css  # Mega menu styling
│   ├── markdown.css        # Markdown rendering styles
│   └── ... (other CSS and images)
└── utils/
    ├── permissions.py  # Access control logic
    ├── helpers.py      # Utility functions
    ├── empty_state.py  # Empty state components
    └── demo_helpers.py # Demo data helpers
```

### Key Architectural Patterns

#### 1. Routing System (`index.py`)

- Central `ROUTES` dictionary maps pathnames to page layout functions
- Route aliases provide backward compatibility (`ROUTE_ALIASES`)
- Access control integrated into routing via `check_access()`
- Main layout builder (`_build_main_layout()`) combines header, sidebar, and page content

**Route Aliases** (defined in `index.py`):
```python
ROUTE_ALIASES = {
    '/dashboard': '/production/oee',
    '/states': '/production/states',
    '/superv': '/supervision',
    '/production/alarms': '/maintenance/alarms',
    '/alarms': '/maintenance/alarms',
}
```

**Utilities Routes Structure**:
- `/utilities/energy`: Energy overview (alias: `/energy`)
- `/utilities/energy/config`: Energy tariff configuration (admin only)
- `/utilities/energy/se01-se04`: Individual substations (in development)
- `/utilities/water`: Water consumption monitoring (in development)
- `/utilities/gas`: Natural gas monitoring (in development)
- `/utilities/compressed-air`: Compressed air system (in development)
- `/utilities/dashboard`: Integrated utilities dashboard (in development)

#### 2. Access Control System

**Two-dimensional permission model** (defined in `config/access_control.py`):

- **Vertical (level)**: 1 = basic, 2 = advanced, 3 = admin
- **Horizontal (perfil)**:
  - `manutencao` - Maintenance team
  - `qualidade` - Quality control team
  - `producao` - Production team
  - `utilidades` - Utilities team (energy, water, gas, air)
  - `admin` - System administrators
  - `meio_ambiente` - Environmental team
  - `seguranca` - Safety team
  - `engenharias` - Engineering team

Routes can be:
- **Shared** (`shared=True`): All profiles can access if level requirement met
- **Profile-specific** (`shared=False`): Requires specific profile(s) AND level

Permission checking flow:
1. Route config lookup in `ROUTE_ACCESS`
2. Level check: `user.level >= min_level`
3. Profile check (if not shared): `user.perfil in perfis`
4. On denial: Show access denied page with reason

#### 3. User Authentication (`database/connection.py`)

- Flask-Login integration with `User` class
- MongoDB `usuarios` collection stores user documents
- User model fields: `username`, `email`, `password` (hashed), `level`, `perfil`
- Global connection singleton pattern for MongoDB client

#### 4. Callback Registration Pattern

All callbacks registered in `callbacks.py` via modular functions:

```python
def register_callbacks(app):
    collection_graph = get_mongo_connection('DecapadoPerformance')
    register_oeegraph_callbacks(app, collection_graph)
    register_kpicards_callbacks(app, collection_graph)
    # ... more registrations
```

Each callback module in `callbacks_registers/` exports a `register_*_callbacks(app, ...)` function.

#### 5. Header System (`header.py`)

Top navigation bar located at `src/header.py` with:

- **Mega Menu Navigation**: Multi-column dropdown menus for Utilities section
  - Energia Elétrica (with substation options SE01-SE04)
  - Água, Gás Natural, Ar Comprimido
- **Dynamic Page Filters**: `get_filters_for_page(pathname)` loads filters from `components/headers/`
- **Theme Switcher**: `ThemeSwitchAIO` component for light/dark mode
- **Hamburger Menu**: Toggle for sidebar collapse/expand
- **User Profile Dropdown**: Avatar, profile info, level badge, logout
- **Permission-based Menus**: Uses `can_see_menu()` to show/hide items

**Page-Specific Filters** (in `components/headers/`):
- `energy_filters.py`: Equipment dropdowns and date/time pickers
- `states_filters.py`: Filters for production state monitoring
- `default_filters.py`: Generic filter layout

#### 6. Sidebar System (`sidebar.py`)

Collapsible sidebar located at `src/sidebar.py` with:

- **Company Logo**: Displayed at top
- **Dynamic Content**: `get_sidebar_content_for_page(pathname)` loads content per route
- **State Management**: Expanded/collapsed state stored in `dcc.Store`
- **CSS Transitions**: Smooth collapse/expand animations

**Page-Specific Sidebar Content** (in `components/sidebars/`):
- `dashboard_sidebar.py`: Dashboard/OEE navigation
- `states_sidebar.py`: Production states navigation
- `superv_sidebar.py`: Supervision controls
- `energy_sidebar.py`: Energy page with dynamic cost calculations
  - `create_se03_cost_sidebar_with_groups()`: Cost breakdown by equipment groups (Transversais/Longitudinais)
  - `create_se03_cost_sidebar_content()`: Detailed step-by-step cost calculation (debug version)
  - `create_energy_sidebar_no_config()`: Alert when tariff config is missing
  - `create_default_energy_sidebar_content()`: Default for non-SE03 tabs
- `procedures_sidebar.py`: Documentation navigation tree (hierarchical structure from docs.yml)
- `default_sidebar.py`: Generic fallback content

**Important**: Sidebar content is determined AFTER route alias resolution.

**Date Filter Synchronization**:
- Sidebar date pickers are synchronized with header date pickers via `input_bridge_callbacks.py`
- Default dates are set by `sidebar_default_dates_callback.py` (last 7 days)
- Changes in either header or sidebar filters update both locations
- Stored in `dcc.Store` components for persistence during navigation

#### 7. MongoDB Collections

Key collections referenced in codebase:
- `usuarios`: User accounts
- `DecapadoPerformance`: OEE and production metrics
- `DecapadoFalhas`: Failure/alarm messages
- `DecapadoTemp`: Temperature sensor data
- `AMG_EnergyData`: Energy consumption data
- `AMG_Consumo`: Hourly consumption aggregates

#### 8. Documentation System (`config/docs_config.py`)

**Procedures Documentation System** for maintenance procedures:

- **External Volume Support**: Documents stored in external volume via `DOCS_PROCEDURES_PATH` env var
- **YAML Configuration**: `docs.yml` file defines navigation structure with sections/subsections
- **Hot-Reload**: Automatic reload when `docs.yml` changes (modification time tracking)
- **Fallback Mode**: Auto-scans directory if `docs.yml` doesn't exist
- **Title Extraction**: Automatically extracts H1 titles from markdown files
- **Security**: Path traversal protection to prevent access outside volume

**Configuration Structure** (`docs.yml`):
```yaml
title: "Procedimentos"
icon: "bi-book"
index: "index.md"  # Optional homepage
sections:
  - name: "preventive"
    label: "Manutenção Preventiva"
    icon: "bi-calendar-check"
    expanded: true
    files:
      - path: "preventive/procedure1.md"
        title: "Auto-extracted or custom title"
```

**Key Functions**:
- `get_docs_path()`: Returns volume path (env var or fallback)
- `load_docs_structure()`: Loads and caches navigation structure
- `get_markdown_title(filepath)`: Extracts title from markdown H1
- `check_file_exists(relative_path)`: Validates file with security checks

#### 9. Demo Data System (`config/demo_data_config.py`)

**Demo Badge System** for indicating non-production data:

- **Global Toggle**: `ENABLE_DEMO_BADGES` enables/disables all badges
- **Per-Page Control**: `DEMO_PAGES` dict controls badges by route
- **Per-Component Control**: `DEMO_COMPONENTS` dict controls by component type
- **Helper Functions**: `should_show_demo_badge()`, `get_demo_pages()`

**Usage Pattern**:
```python
from src.config.demo_data_config import should_show_demo_badge
from src.components.demo_badge import create_demo_badge

# In page layout
if should_show_demo_badge(page_path="/production/oee"):
    badge = create_demo_badge()
```

**Badge Display Logic**:
1. Check global `ENABLE_DEMO_BADGES` flag
2. Check page-specific or component-specific setting
3. Render badge if both conditions are true

### Application Initialization Flow

1. **app.py**: Initialize Flask server, Dash app, Flask-Login
2. **run.py**: Load theme template, import index module (triggers callback registration)
3. **index.py**: Define app layout, import all page modules, register route callbacks
4. **callbacks.py**: Register all feature-specific callbacks

When user navigates:
1. `url` location change triggers routing callback
2. Check authentication status
3. Resolve route aliases
4. **Check permissions** via `check_access()`
5. Load page layout or show access denied
6. Build main layout with header, sidebar, content
7. Load dynamic sidebar content based on resolved route

## Important Development Notes

### Adding New Pages

1. Create page module in appropriate `pages/` subdirectory with `layout` function/variable
2. Add route to `ROUTES` dict in `index.py`
3. Add permission config to `ROUTE_ACCESS` in `config/access_control.py`
4. If callbacks needed, create module in `callbacks_registers/` and register in `callbacks.py`
5. If page needs custom sidebar content, add module in `components/sidebars/` and update `get_sidebar_content_for_page()` in `sidebar.py`
6. If page needs custom header filters, add module in `components/headers/` and update `get_filters_for_page()` in `header.py`

### Modifying Access Control

- Edit `config/access_control.py` to change route/menu permissions
- Never hardcode permission checks in individual pages
- Use `check_access()` from `utils/permissions.py` for programmatic checks
- Menu visibility controlled via `MENU_ACCESS` configuration

### Working with MongoDB

- Always use `get_mongo_connection(collection_name)` to get collections
- Connection is singleton - first call establishes connection, subsequent calls reuse
- Handle `ConnectionError` exceptions for database failures

### Theme and Styling

- Bootstrap theme configured in `app.py`: `MINTY` and `darkly` templates loaded
- Dash Bootstrap Components (dbc) used throughout
- Custom theme toggle functionality via `ThemeSwitchAIO`
- Custom CSS files in `assets/` directory:
  - `dropdown_menus.css`: Mega menu styling
  - `markdown.css`: Markdown rendering styles
- Favicon configured via `app.index_string` to use `/assets/favicon.ico`

### UI Components and Layouts

**Under Development Pages** (`pages/common/under_development.py`):
- Centralized layout function for pages not yet implemented
- Uses responsive Bootstrap grid with offset columns for centering
- Pre-configured variants: `states_development()`, `alarms_development()`, `maintenance_development()`, `utilities_development()`, `config_development()`, etc.
- Layout adapts correctly to sidebar collapse/expand states

**Multi-Tab Pattern** (e.g., `pages/energy/overview.py`):
- Uses `dbc.Tabs` for organizing content by category
- Tab content loaded dynamically via callbacks
- Under-development tabs use `get_under_development_content()` helper
- Fully developed tabs (like SE03) include multiple graphs and KPI cards

**Energy Cost Calculation System** (`pages/energy/overview.py` + `energy_sidebar.py`):
- **SE03 Tab**: Advanced cost calculation with breakdown by equipment groups
  - Transversais group: MM02, MM04, MM06
  - Longitudinais group: MM03, MM05, MM07
- **Cost Components**: TUSD (transmission), Energia (consumption), Demanda (demand charges)
- **Time-of-Use Pricing**: Separate calculations for Ponta (peak) and Fora Ponta (off-peak)
- **Demand Calculation**: Always uses full month data, prorated by consumption percentage
- **Tariff Configuration**: Admin-only page at `/utilities/energy/config`
- **Real-time Updates**: Sidebar updates dynamically when date range or equipment selection changes

**Demo Badge Component** (`components/demo_badge.py`):
- Consistent badge design for marking non-production data
- Controlled by `demo_data_config.py` settings
- Used across pages and components

**Icon System** (`components/icons.py`):
- Centralized SVG icon components
- Used throughout header menus and UI elements
- Consistent styling across the application

### MQTT Command Publishing

To send commands to equipment:
1. Frontend makes POST to `{GATEWAY_URL}/api/command`
2. Event gateway publishes to MQTT broker with TLS
3. Payload format: `{"topic": "device/command", "payload": "command_data"}`

### Documentation System (Procedures)

**Adding/Updating Procedures**:
1. Place markdown files in external volume (path defined by `DOCS_PROCEDURES_PATH`)
2. Create or update `docs.yml` in the volume root with navigation structure
3. System automatically reloads when `docs.yml` is modified
4. Titles are auto-extracted from markdown H1 headers if not specified in YAML

**docs.yml structure**:
```yaml
title: "Procedimentos"
icon: "bi-book"
sections:
  - name: "category_name"
    label: "Display Name"
    icon: "bi-icon-name"
    expanded: false
    files:
      - path: "relative/path/to/file.md"
        title: "Optional custom title"
```

**Security Considerations**:
- Path traversal is prevented - files must be within `DOCS_PROCEDURES_PATH`
- Access control is enforced at the route level via `ROUTE_ACCESS`

### Demo Data System

**Managing Demo Badges**:
1. Global control: Set `ENABLE_DEMO_BADGES = False` in `config/demo_data_config.py` to hide all badges
2. Per-page control: Update `DEMO_PAGES` dict to enable/disable specific pages
3. Per-component control: Update `DEMO_COMPONENTS` dict for specific components

**Adding Demo Badge to New Page**:
```python
from src.config.demo_data_config import should_show_demo_badge
from src.components.demo_badge import create_demo_badge

def layout():
    badge = create_demo_badge() if should_show_demo_badge(page_path="/your/route") else None
    # Include badge in layout
```

### Development Mode Features

- Hot reload enabled when running via `run_local.py`
- Debug mode provides detailed error messages
- Loading overlay with spinner during initial page load
- Environment validation on startup (checks required env vars)

## Known Limitations and Future Features

### In Development

**Production Module**:
- `/production/states`: Production state monitoring (under development)

**Energy Module**:
- SE01, SE02, SE04: Individual substation monitoring (SE03 is fully functional)
- `/utilities/energy/history`: Historical consumption analysis
- `/utilities/energy/costs`: Cost analysis dashboard

**Utilities Module** (all under development):
- Water consumption monitoring and cost tracking
- Natural gas monitoring (measurement points, history, costs)
- Compressed air system (compressors, efficiency analysis)
- Integrated utilities dashboard (consolidated view of all utilities)

**Maintenance Module**:
- Work orders management system
- Maintenance schedule/calendar
- Maintenance history and analytics
- Maintenance indicators/KPIs

**Configuration Module**:
- User preferences management
- System logs viewer

### Fully Functional Features

- User authentication and authorization
- OEE dashboard with production metrics
- Energy monitoring for SE03 (with cost calculations)
- Energy tariff configuration (admin only)
- Alarm monitoring and history
- Maintenance procedures documentation system
- Supervisory control interface
- User management (create, edit, delete users)

## Git Branch Structure

- **Main branch**: `main`
- Current feature branch pattern: `feature/[FeatureName]` (e.g., `feature/mkdocs`)
- Commit message style: Conventional Commits format
  - `feat(scope): description` for new features
  - `fix(scope): description` for bug fixes
  - `refactor(scope): description` for refactoring

## Security Considerations

- SECRET_KEY must be set via environment variable (application fails if missing)
- Passwords hashed with `pbkdf2:sha256` via Werkzeug
- MQTT connections use TLS (port 8883) with authentication
- No hardcoded credentials - all via `.env` files
- `.env` files are gitignored

## Technology Stack

- **Backend**: Flask 3.1.1 with Flask-Login 0.6.3
- **Frontend**: Dash 3.1.1, Dash Bootstrap Components 2.0.3, Dash Bootstrap Templates 2.1.0
- **Database**: MongoDB via PyMongo 4.13.2
- **Visualization**: Plotly 6.1.2
- **Data Processing**: Pandas 2.3.1, NumPy 2.3.2
- **Documentation**: Markdown 3.7, PyYAML (for docs.yml configuration)
- **MQTT**: Paho-MQTT (in event-gateway)
- **Web Server**: Gunicorn (production)
- **Other**: python-dotenv 1.1.1, Werkzeug 3.1.3
