# src/components/stores.py

from dash import dcc

# Lista de todos os stores da aplicação que guardam dados de sessão ou de cliente.
# Agrupar todos aqui facilita a manutenção e a reutilização entre páginas.
app_stores = [
    # Stores de filtros de data e hora
    dcc.Store(id='store-start-date', storage_type='session'),
    dcc.Store(id='store-end-date', storage_type='session'),
    dcc.Store(id='store-start-hour', storage_type='session'),
    dcc.Store(id='store-end-hour', storage_type='session'),

    # Store para controle de atualização automática
    dcc.Store(id='store-auto-update-enabled', storage_type='session'),

    # Stores para guardar dados de gráficos e tabelas
    dcc.Store(id='stored-graph-data', storage_type='session'),
    dcc.Store(id='stored-table-data', storage_type='session'),
    dcc.Store(id='stored-oee-occupancy-card-graph', storage_type='session'),
    dcc.Store(id='stored-oee-occupancy02-card-graph', storage_type='session'),
    dcc.Store(id='stored-energy-data'),
    dcc.Store(id='stored-temp-data'),

    # Stores globais que poderiam estar aqui também (ou no index.py)
    # Manter aqui centraliza tudo.
    dcc.Store(id='theme-store', storage_type='local'),
    dcc.Store(id="sidebar-state", storage_type="session", data="expanded"),
]
