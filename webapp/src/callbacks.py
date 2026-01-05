# callbacks/callbacks.py
from src.database.connection import get_mongo_connection

# Importe o novo registro de callback
from src.callbacks_registers.energygraph_callback import register_energygraph_callbacks

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
from src.callbacks_registers.main_layout_callbacks import register_main_layout_callbacks 
from src.callbacks_registers.hourlyconsumption_callback import register_hourlyconsumption_callbacks
from src.callbacks_registers.sidebar_content_callback import register_sidebar_content_callback
from src.callbacks_registers.home_callbacks import register_home_callbacks
from src.callbacks_registers.alarms_callbacks import register_alarms_callbacks
from src.callbacks_registers.create_user_callbacks import register_create_user_callbacks

from src.pages.energy import callbacks as energy_callbacks

# (Seu logger, se houver)

def register_callbacks(app):
    # Configurar conexões específicas para as coleções MongoDB
    collection_graph = get_mongo_connection(collection_name='DecapadoPerformance')
    collection_table = get_mongo_connection(collection_name='DecapadoFalhas')
    collection_energia = get_mongo_connection(collection_name='AMG_EnergyData')
    collection_temp = get_mongo_connection(collection_name='DecapadoTemp')
    collection_consumo = get_mongo_connection(collection_name="AMG_Consumo")

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
    register_storetheme_callbacks(app)
    register_states_switch_callback(app)
    register_sp_callback(app)    
    register_energygraph_callbacks(app, collection_energia)
    register_tempgraph_callbacks(app, collection_temp)
    register_main_layout_callbacks(app)     
    register_hourlyconsumption_callbacks(app, collection_consumo)
    register_sidebar_content_callback(app)
    register_home_callbacks(app)
    register_alarms_callbacks(app)
    register_create_user_callbacks(app)
