# callbacks/callbacks.py
from src.database.connection import get_mongo_connection, get_connection_status

# Energy graph callbacks (SE03)
from src.callbacks_registers.energy_kpi_callbacks import register_kpi_callbacks
from src.callbacks_registers.demand_graph_callbacks import register_demand_callbacks

# Seus imports existentes
from src.callbacks_registers.oeegraph_callback import register_oeegraph_callbacks
from src.callbacks_registers.msgtable_callback import register_msgtable_callbacks
from src.callbacks_registers.kpicards_callback import register_kpicards_callbacks
from src.callbacks_registers.autoupdatetoggle_callback import register_autoupdatetoggle_callbacks
from src.callbacks_registers.input_bridge_callbacks import register_input_bridge_callbacks
from src.callbacks_registers.sidebar_filters_callback import register_sidebar_filter_callbacks
from src.callbacks_registers.sidebar_default_dates_callback import (
    register_sidebar_default_dates_callback,
)
from src.callbacks_registers.states_callbacks import register_states_callbacks
from src.callbacks_registers.states_callbacks02 import register_states02_callbacks
from src.callbacks_registers.storetheme import register_storetheme_callbacks
from src.callbacks_registers.states_switch_callback import register_states_switch_callback
from src.callbacks_registers.sp_callback import register_sp_callback
from src.callbacks_registers.tempgraph_callback import register_tempgraph_callbacks
from src.callbacks_registers.hourlyconsumption_callback import register_hourlyconsumption_callbacks
from src.callbacks_registers.sidebar_content_callback import register_sidebar_content_callback
from src.callbacks_registers.sidebar_toggle_callback import register_sidebar_toggle_callback
from src.callbacks_registers.home_callbacks import register_home_callbacks
from src.callbacks_registers.alarms_callbacks import register_alarms_callbacks
from src.callbacks_registers.create_user_callbacks import register_create_user_callbacks
from src.callbacks_registers.change_password_callbacks import register_change_password_callbacks
from src.callbacks_registers.manage_users_callbacks import register_manage_users_callbacks
from src.callbacks_registers.energy_config_callbacks import register_energy_config_callbacks
from src.callbacks_registers.energy_sidebar_callbacks import register_energy_sidebar_callbacks
from src.callbacks_registers.procedures_collapse_callbacks import register_procedures_collapse_callbacks
from src.callbacks_registers.maintenance_kpi_callbacks import register_maintenance_kpi_callbacks
from src.callbacks_registers.maintenance_config_callbacks import register_maintenance_config_callbacks
from src.callbacks_registers.zpp_processor_callbacks import register_zpp_processor_callbacks
from src.callbacks_registers.zpp_debug_callbacks import register_zpp_debug_callbacks
from src.callbacks_registers.database_error_callbacks import register_database_error_callbacks
from src.callbacks_registers.workflow_callbacks import register_workflow_callbacks
from src.callbacks_registers.workflow_create_callbacks import register_create_callbacks
from src.callbacks_registers.workflow_edit_callbacks import register_edit_callbacks
from src.callbacks_registers.workflow_subtask_callbacks import register_subtask_callbacks

from src.pages.energy import callbacks as energy_callbacks
from src.callbacks_registers.se03_telemetry_callbacks import register_se03_telemetry_callbacks

# (Seu logger, se houver)

def register_callbacks(app):
    """
    Registra todos os callbacks da aplicação.

    IMPORTANTE: Esta função NÃO falha se o MongoDB estiver offline.
    As conexões são tentadas, mas se falharem, None é passado para os callbacks.
    Cada callback individual deve verificar se recebeu None e tratar apropriadamente.
    """

    # Tentar configurar conexões (modo não-fatal)

    collection_graph = get_mongo_connection(collection_name='DecapadoPerformance', silent=False)
    collection_table = get_mongo_connection(collection_name='DecapadoFalhas', silent=True)
    collection_energia = get_mongo_connection(collection_name='AMG_EnergyData', silent=True)
    collection_temp = get_mongo_connection(collection_name='DecapadoTemp', silent=True)
    collection_consumo = get_mongo_connection(collection_name="AMG_Consumo", silent=True)

    # Verificar status
    status = get_connection_status()
    if not status["available"]:
        pass  # MongoDB offline - modo degradado
    else:
        pass  # MongoDB conectado

    # Registra os callbacks existentes (sem alterações aqui)
    register_input_bridge_callbacks(app)
    register_oeegraph_callbacks(app, collection_graph)
    register_msgtable_callbacks(app, collection_table)
    register_kpicards_callbacks(app, collection_graph)
    register_autoupdatetoggle_callbacks(app)
    register_sidebar_filter_callbacks(app)
    register_sidebar_default_dates_callback(app)
    register_states_callbacks(app, collection_graph)
    register_states02_callbacks(app, collection_graph)
    # register_storetheme_callbacks(app)  # Desabilitado - ThemeSwitchAIO removido
    register_states_switch_callback(app)
    register_sp_callback(app)

    # Energy page callbacks (SE03 KPIs and demand graphs)
    register_kpi_callbacks(app, collection_energia, collection_consumo)
    register_demand_callbacks(app, collection_energia)

    register_tempgraph_callbacks(app, collection_temp)
    register_hourlyconsumption_callbacks(app, collection_consumo)
    register_sidebar_content_callback(app)
    register_sidebar_toggle_callback(app)
    register_home_callbacks(app)
    register_alarms_callbacks(app)
    register_create_user_callbacks(app)
    register_change_password_callbacks(app)
    register_manage_users_callbacks(app)

    # Energy configuration and costs
    register_energy_config_callbacks(app)

    # Energy sidebar (MUST be after sidebar_content_callback)
    # This callback overrides the default sidebar for energy pages
    register_energy_sidebar_callbacks(app)

    # Procedures collapse callbacks (for documentation navigation)
    register_procedures_collapse_callbacks(app)

    # Maintenance KPI indicators callbacks
    register_maintenance_kpi_callbacks(app)

    # Maintenance configuration callbacks
    register_maintenance_config_callbacks(app)

    # ZPP Processor callbacks
    register_zpp_processor_callbacks(app)
    register_zpp_debug_callbacks(app)

    # Workflow callbacks
    register_workflow_callbacks(app)
    register_create_callbacks(app)    # Workflow CRUD - Criação
    register_edit_callbacks(app)      # Workflow CRUD - Edição
    register_subtask_callbacks(app)   # Workflow CRUD - Subtarefas e Logs

    # Database error handling callbacks
    register_database_error_callbacks(app)

    # SE03 Telemetria ao vivo
    collection_telemetry = get_mongo_connection("AMG_EnergyTelemetry", silent=True)
    register_se03_telemetry_callbacks(app, collection_telemetry)
