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
```

## Architecture

### Application Structure

```
webapp/src/
├── app.py              # Flask server & Dash app initialization (includes favicon config)
├── run.py              # Application entry point
├── index.py            # Main routing and layout orchestration
├── callbacks.py        # Central callback registration
├── callbacks_registers/  # Callback modules (one per feature)
├── components/         # Reusable UI components (graphs, cards, tables)
│   ├── header.py       # Top navigation bar
│   ├── sidebar.py      # Sidebar with logo
│   ├── headers/        # Page-specific header filter modules
│   │   ├── energy_filters.py
│   │   ├── states_filters.py
│   │   └── default_filters.py
│   └── icons.py        # SVG icon components
├── config/             # Configuration modules
│   ├── access_control.py   # Route & menu permissions matrix
│   ├── theme_config.py     # Dash Bootstrap theme configuration
│   └── user_loader.py      # Flask-Login user loader
├── database/
│   └── connection.py   # MongoDB connection & User model
├── pages/              # Page layouts organized by domain
│   ├── auth/           # Login and registration
│   ├── dashboards/     # Home, production OEE
│   ├── energy/         # Energy monitoring pages
│   ├── production/     # Production state tracking
│   ├── maintenance/    # Alarms and work orders
│   ├── supervision/    # Supervisory control (SCADA-like)
│   ├── reports/        # Reporting pages
│   └── common/         # Shared pages (404, access denied, under_development.py)
└── utils/
    ├── permissions.py  # Access control logic
    └── helpers.py      # Utility functions
```

### Key Architectural Patterns

#### 1. Routing System (`index.py`)

- Central `ROUTES` dictionary maps pathnames to page layout functions
- Route aliases provide backward compatibility (`ROUTE_ALIASES`)
- Access control integrated into routing via `check_access()`
- Main layout builder (`_build_main_layout()`) combines header, sidebar, and page content

#### 2. Access Control System

**Two-dimensional permission model** (defined in `config/access_control.py`):

- **Vertical (level)**: 1 = basic, 2 = advanced, 3 = admin
- **Horizontal (perfil)**: manutencao, qualidade, producao, utilidades, admin

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

#### 5. Header and Sidebar System

**Header**: Top navigation bar (`components/header.py`) with:
- Page-specific filters loaded dynamically from `components/headers/` directory
- Theme switcher using `ThemeSwitchAIO`
- Hamburger menu for sidebar toggle
- Profile icon and user menu

**Sidebar**: Collapsible sidebar (`components/sidebar.py`) with:
- Company logo display
- Sidebar state (expanded/collapsed) stored in `dcc.Store`
- Currently minimal - awaiting future menu items

**Page-Specific Filters**: Located in `components/headers/`:
- `energy_filters.py`: Equipment dropdowns and date/time pickers for energy pages
- `states_filters.py`: Filters for production state monitoring
- `default_filters.py`: Generic filter layout for other pages

#### 6. MongoDB Collections

Key collections referenced in codebase:
- `usuarios`: User accounts
- `DecapadoPerformance`: OEE and production metrics
- `DecapadoFalhas`: Failure/alarm messages
- `DecapadoTemp`: Temperature sensor data
- `AMG_EnergyData`: Energy consumption data
- `AMG_Consumo`: Hourly consumption aggregates

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

## Important Development Notes

### Adding New Pages

1. Create page module in appropriate `pages/` subdirectory with `layout` function/variable
2. Add route to `ROUTES` dict in `index.py`
3. Add permission config to `ROUTE_ACCESS` in `config/access_control.py`
4. If callbacks needed, create module in `callbacks_registers/` and register in `callbacks.py`
5. Update sidebar menu in `sidebar.py` if navigation item needed

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
- Custom CSS files in `assets/` directory for component-specific styling
- Favicon configured via `app.index_string` to use `/assets/favicon.ico`

### UI Components and Layouts

**Under Development Pages** (`pages/common/under_development.py`):
- Centralized layout function for pages not yet implemented
- Uses responsive Bootstrap grid with offset columns for centering
- Pre-configured variants: `states_development()`, `alarms_development()`, `maintenance_development()`, etc.
- Layout adapts correctly to sidebar collapse/expand states

**Multi-Tab Pattern** (e.g., `pages/energy/overview.py`):
- Uses `dbc.Tabs` for organizing content by category
- Tab content loaded dynamically via callbacks
- Under-development tabs use `get_under_development_content()` helper
- Fully developed tabs (like SE03) include multiple graphs and KPI cards

### MQTT Command Publishing

To send commands to equipment:
1. Frontend makes POST to `{GATEWAY_URL}/api/command`
2. Event gateway publishes to MQTT broker with TLS
3. Payload format: `{"topic": "device/command", "payload": "command_data"}`

### Development Mode Features

- Hot reload enabled when running via `run_local.py`
- Debug mode provides detailed error messages
- Loading overlay with spinner during initial page load
- Environment validation on startup (checks required env vars)

## Git Branch Structure

- **Main branch**: `main`
- Current feature branch pattern: `feature/[FeatureName]` (e.g., `feature/ProfileIcon`)
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
- **Frontend**: Dash 3.1.1, Dash Bootstrap Components 2.0.3
- **Database**: MongoDB via PyMongo 4.13.2
- **Visualization**: Plotly 6.1.2
- **Data Processing**: Pandas 2.3.1, NumPy 2.3.2
- **MQTT**: Paho-MQTT (in event-gateway)
- **Web Server**: Gunicorn (production)
