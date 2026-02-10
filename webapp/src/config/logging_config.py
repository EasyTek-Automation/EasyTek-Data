"""
Configuração centralizada de logging para a aplicação.

Este módulo configura o sistema de logging de forma consistente,
organizando logs por PÁGINA e TIPO de operação (callbacks, database, cálculos, etc).

Estrutura de logs:
    logs/
    ├── app.log              # Log geral (INFO+)
    ├── errors.log           # Apenas erros (ERROR+)
    └── maintenance.log      # Módulo de manutenção (indicadores KPI)

Variáveis de ambiente (.env) - Controle granular por página:
    LOG_LEVEL=INFO                          # Nível geral (DEBUG, INFO, WARNING, ERROR)

    # Controle por página (ALL ou tipos específicos separados por vírgula)
    DEBUG_MAINTENANCE_INDICATORS=ALL        # Liga TUDO da página
    DEBUG_MAINTENANCE_INDICATORS=CALLBACKS,CALC  # Apenas callbacks e cálculos
    DEBUG_ENERGY_OVERVIEW=CALLBACKS         # Apenas callbacks de energia

    # Tipos disponíveis: ALL, CALLBACKS, DATABASE, CALC, UI

    # Formato antigo ainda suportado (para compatibilidade):
    DEBUG_MAINTENANCE=1      # Liga tudo de manutenção
    DEBUG_KPI_CALC=1         # Liga cálculos de KPI
"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Set


# ==================== CONFIGURAÇÃO DE DEBUG POR PÁGINA ====================

def parse_debug_config(page_name: str) -> Set[str]:
    """
    Parseia configuração de debug de uma página.

    Args:
        page_name: Nome da variável de ambiente (ex: "MAINTENANCE_INDICATORS")

    Returns:
        Set com tipos habilitados: {"CALLBACKS", "DATABASE", "CALC", "UI"} ou {"ALL"}

    Exemplos:
        DEBUG_MAINTENANCE_INDICATORS=ALL          → {"ALL"}
        DEBUG_MAINTENANCE_INDICATORS=CALLBACKS,DB → {"CALLBACKS", "DATABASE"}
        DEBUG_MAINTENANCE_INDICATORS=1            → {"ALL"} (compatibilidade)
    """
    env_var = f"DEBUG_{page_name}"
    value = os.getenv(env_var, "").strip().upper()

    if not value or value == "0":
        return set()

    # Compatibilidade: "1" = ALL
    if value == "1":
        return {"ALL"}

    # Se for ALL, retorna ALL
    if value == "ALL":
        return {"ALL"}

    # Parse tipos separados por vírgula
    types = set()
    for type_str in value.split(","):
        type_str = type_str.strip()

        # Aliases para facilitar
        if type_str in ("DB", "DATABASE"):
            types.add("DATABASE")
        elif type_str in ("CALC", "CALCULATIONS"):
            types.add("CALC")
        elif type_str in ("CALLBACKS", "CALLBACK"):
            types.add("CALLBACKS")
        elif type_str == "UI":
            types.add("UI")

    return types


def should_log_debug(page_name: str, log_type: str = "ALL") -> bool:
    """
    Verifica se deve logar DEBUG para uma página/tipo específico.

    Args:
        page_name: Nome da página (ex: "MAINTENANCE_INDICATORS")
        log_type: Tipo de log ("CALLBACKS", "DATABASE", "CALC", "UI", "ALL")

    Returns:
        bool: True se deve logar

    Exemplos:
        should_log_debug("MAINTENANCE_INDICATORS", "CALLBACKS")
        should_log_debug("ENERGY_OVERVIEW", "DATABASE")
    """
    enabled_types = parse_debug_config(page_name)

    if not enabled_types:
        return False

    if "ALL" in enabled_types:
        return True

    return log_type.upper() in enabled_types


def setup_logging():
    """
    Configura o sistema de logging da aplicação.

    Cria estrutura de logs organizados por módulo com rotação automática.
    Permite debug seletivo via variáveis de ambiente.

    Returns:
        logging.Logger: Logger configurado
    """
    # Obtém nível de log da variável de ambiente (padrão: INFO)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Cria diretório de logs
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # ========== FORMATADORES ==========

    # Formato padrão (timestamp + nível + módulo + mensagem)
    standard_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S"
    )

    # ========== HANDLERS ==========

    # 1. Console (desenvolvimento - mostra tudo no terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(standard_formatter)
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))

    # 2. Arquivo geral (app.log - INFO+)
    general_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    general_handler.setFormatter(standard_formatter)
    general_handler.setLevel(logging.INFO)

    # 3. Arquivo de erros (errors.log - ERROR+)
    error_handler = RotatingFileHandler(
        logs_dir / "errors.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setFormatter(standard_formatter)
    error_handler.setLevel(logging.ERROR)

    # ========== CONFIGURAÇÃO ROOT ==========

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Aceita tudo, handlers filtram
    root_logger.addHandler(console_handler)
    root_logger.addHandler(general_handler)
    root_logger.addHandler(error_handler)

    # ========== BIBLIOTECAS EXTERNAS ==========

    # Silencia logs verbosos do PyMongo
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
    logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)
    logging.getLogger("pymongo.command").setLevel(logging.WARNING)
    logging.getLogger("pymongo.topology").setLevel(logging.WARNING)

    # Werkzeug (Flask dev server) - controlável via env var
    # SHOW_HTTP_LOGS=1 para mostrar requisições HTTP (padrão: desabilitado)
    show_http_logs = os.getenv("SHOW_HTTP_LOGS", "0") == "1"
    werkzeug_level = logging.INFO if show_http_logs else logging.WARNING
    logging.getLogger("werkzeug").setLevel(werkzeug_level)

    if not show_http_logs:
        print("[HTTP LOGS DISABLED] Werkzeug silenciado")

    # ========== MÓDULOS DA APLICAÇÃO ==========
    # Logs específicos por módulo (adicionar conforme necessário)

    # === MANUTENÇÃO (Indicadores KPI) ===
    maintenance_handler = RotatingFileHandler(
        logs_dir / "maintenance.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    maintenance_handler.setFormatter(standard_formatter)
    maintenance_handler.setLevel(logging.INFO)

    # Callbacks de manutenção
    maintenance_logger = logging.getLogger("src.callbacks_registers.maintenance_kpi_callbacks")
    maintenance_logger.addHandler(maintenance_handler)

    # Calculadora de KPIs
    kpi_calc_logger = logging.getLogger("src.utils.zpp_kpi_calculator")
    kpi_calc_logger.addHandler(maintenance_handler)

    # Dados demo de manutenção
    demo_logger = logging.getLogger("src.utils.maintenance_demo_data")
    demo_logger.addHandler(maintenance_handler)

    # Componentes de gráficos
    graphs_logger = logging.getLogger("src.components.maintenance_kpi_graphs")
    graphs_logger.addHandler(maintenance_handler)

    # ========== DEBUG SELETIVO POR PÁGINA ====================
    # Ativa debug detalhado por página e tipo de operação

    # === MANUTENÇÃO - INDICADORES ===
    maintenance_indicators_config = parse_debug_config("MAINTENANCE_INDICATORS")

    # Compatibilidade: DEBUG_MAINTENANCE=1 ou DEBUG_KPI_CALC=1 ativam tudo
    if os.getenv("DEBUG_MAINTENANCE") == "1" or os.getenv("DEBUG_KPI_CALC") == "1":
        maintenance_indicators_config = {"ALL"}

    if maintenance_indicators_config:
        # Callbacks
        if "ALL" in maintenance_indicators_config or "CALLBACKS" in maintenance_indicators_config:
            logging.getLogger("src.callbacks_registers.maintenance_kpi_callbacks").setLevel(logging.DEBUG)
            print("[DEBUG] Maintenance Indicators - CALLBACKS")

        # Cálculos
        if "ALL" in maintenance_indicators_config or "CALC" in maintenance_indicators_config:
            logging.getLogger("src.utils.zpp_kpi_calculator").setLevel(logging.DEBUG)
            logging.getLogger("src.utils.maintenance_demo_data").setLevel(logging.DEBUG)
            print("[DEBUG] Maintenance Indicators - CALC")

        # UI/Componentes
        if "ALL" in maintenance_indicators_config or "UI" in maintenance_indicators_config:
            logging.getLogger("src.components.maintenance_kpi_graphs").setLevel(logging.DEBUG)
            print("[DEBUG] Maintenance Indicators - UI")

    # === ENERGIA - OVERVIEW ===
    # energy_overview_config = parse_debug_config("ENERGY_OVERVIEW")
    # if energy_overview_config:
    #     if "ALL" in energy_overview_config or "CALLBACKS" in energy_overview_config:
    #         logging.getLogger("src.callbacks_registers.energygraph_callback").setLevel(logging.DEBUG)
    #         print("[DEBUG] Energy Overview - CALLBACKS")

    # === Adicione outras páginas aqui ===

    # ========== CONFIRMAÇÃO ==========

    app_logger = logging.getLogger("src.config.logging_config")
    app_logger.info("Sistema de logging configurado com sucesso")
    app_logger.info("Logs salvos em: %s", logs_dir.absolute())
    app_logger.info("Nível geral: %s", log_level)

    return app_logger
