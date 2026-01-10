"""
Configuração para controlar exibição de badges de dados de demonstração.

Este arquivo permite ativar/desativar facilmente os badges que indicam
dados fictícios em diferentes páginas e componentes do sistema.

Para desativar o badge em uma página específica, mude True para False.
Para desativar todos os badges, mude ENABLE_DEMO_BADGES para False.
"""

# ======================================================================================
# CONTROLE GLOBAL
# ======================================================================================

# Ativar/desativar TODOS os badges de demonstração no sistema
ENABLE_DEMO_BADGES = True

# ======================================================================================
# CONTROLE POR PÁGINA
# ======================================================================================

DEMO_PAGES = {
    # Dashboards
    "/": True,                          # Home
    "/production/oee": True,            # Dashboard OEE

    # Produção
    "/production/states": True,         # Estados da Linha

    # Energia
    "/energy/overview": True,           # Energia - Visão Geral
    "/energy/se01": True,               # Subestação SE01
    "/energy/se02": True,               # Subestação SE02
    "/energy/se03": True,               # Subestação SE03
    "/energy/se04": True,               # Subestação SE04
    "/energy/water": True,              # Água
    "/energy/gas": True,                # Gás Natural
    "/energy/compressed-air": True,     # Ar Comprimido
    "/energy/dashboard": True,          # Dashboard Integrado

    # Supervisório
    "/supervision": True,               # Supervisório
    "/supervision/temperature": True,   # Controle de Temperatura

    # Manutenção
    "/maintenance/alarms": True,        # Alarmes
    "/maintenance/orders": True,        # Ordens de Serviço
    "/maintenance/plan": True,          # Plano de Manutenção
    "/maintenance/history": True,       # Histórico
    "/maintenance/indicators": True,    # Indicadores

    # Relatórios
    "/reports": True,                   # Relatórios
}

# ======================================================================================
# CONTROLE POR TIPO DE COMPONENTE
# ======================================================================================

DEMO_COMPONENTS = {
    # Gráficos
    "graphs": {
        "oee_graph": True,
        "energy_graph": True,
        "temperature_graph": True,
        "consumption_graph": True,
        "alarm_graph": True,
    },

    # Cards KPI
    "kpi_cards": {
        "oee_cards": True,
        "energy_cards": True,
        "production_cards": True,
    },

    # Tabelas
    "tables": {
        "alarm_table": True,
        "report_table": True,
    }
}

# ======================================================================================
# FUNÇÕES HELPER
# ======================================================================================

def should_show_demo_badge(page_path=None, component_type=None, component_name=None):
    """
    Verifica se deve exibir o badge de demonstração.

    Args:
        page_path (str): Caminho da página (ex: "/production/oee")
        component_type (str): Tipo do componente (ex: "graphs", "kpi_cards")
        component_name (str): Nome do componente (ex: "oee_graph")

    Returns:
        bool: True se deve exibir o badge, False caso contrário

    Examples:
        >>> should_show_demo_badge(page_path="/production/oee")
        True
        >>> should_show_demo_badge(component_type="graphs", component_name="oee_graph")
        True
    """
    # Verificar controle global
    if not ENABLE_DEMO_BADGES:
        return False

    # Verificar por página
    if page_path is not None:
        return DEMO_PAGES.get(page_path, False)

    # Verificar por componente
    if component_type and component_name:
        component_group = DEMO_COMPONENTS.get(component_type, {})
        return component_group.get(component_name, False)

    # Se não especificou nada, retorna o controle global
    return ENABLE_DEMO_BADGES


def get_demo_pages():
    """
    Retorna lista de páginas com dados de demonstração.

    Returns:
        list: Lista de caminhos de páginas com demos ativas
    """
    if not ENABLE_DEMO_BADGES:
        return []

    return [path for path, enabled in DEMO_PAGES.items() if enabled]


def disable_demo_badge_for_page(page_path):
    """
    Desativa o badge para uma página específica.

    Args:
        page_path (str): Caminho da página
    """
    if page_path in DEMO_PAGES:
        DEMO_PAGES[page_path] = False


def enable_demo_badge_for_page(page_path):
    """
    Ativa o badge para uma página específica.

    Args:
        page_path (str): Caminho da página
    """
    if page_path in DEMO_PAGES:
        DEMO_PAGES[page_path] = True
