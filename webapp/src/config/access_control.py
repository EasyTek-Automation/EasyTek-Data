# src/config/access_control.py

"""
Configuração Central de Controle de Acesso
==========================================

Este arquivo define a matriz de permissões do sistema, combinando:
- Nível (vertical): 1=básico, 2=avançado, 3=admin
- Perfil (horizontal): manutencao, qualidade, producao, utilidades, admin

Regras:
- Páginas "shared=True": Verificam APENAS o nível (todos os perfis podem acessar)
- Páginas "shared=False": Verificam nível E perfil

Exemplo de uso:
    from src.config.access_control import ROUTE_ACCESS, MENU_ACCESS
    
    # Verificar se rota é compartilhada
    config = ROUTE_ACCESS.get("/maintenance/alarms", {})
    if config.get("shared", False):
        # Só verifica nível
    else:
        # Verifica nível E perfil
"""

# ========================================
# PERFIS DISPONÍVEIS NO SISTEMA
# ========================================
PERFIS = [
    "manutencao",    # Equipe de manutenção
    "qualidade",     # Equipe de qualidade
    "producao",      # Equipe de produção
    "utilidades",    # Equipe de utilidades (energia, água, etc.)
    "admin",         # Administradores do sistema (privilégios especiais)
    "meio_ambiente", # Meio Ambiente
    "seguranca",     # Segurança do Trabalho
    "engenharias",   # Engenharias
]

# ========================================
# CONFIGURAÇÃO DE ACESSO ÀS ROTAS
# ========================================
# 
# Estrutura de cada rota:
# {
#     "shared": bool,          # True = todos os perfis podem acessar (só verifica nível)
#     "perfis": list,          # Lista de perfis permitidos (quando shared=False)
#     "min_level": int,        # Nível mínimo para acessar (default=1)
#     "description": str       # Descrição da página (para logs/debug)
# }
#
# NOTA: Quando "shared=True", o campo "perfis" é ignorado

ROUTE_ACCESS = {
    
    # ========================================
    # PÁGINAS PÚBLICAS (não requerem autenticação)
    # ========================================
    "/login": {
        "shared": True,
        "min_level": 0,
        "description": "Página de Login"
    },
    "/register": {
        "shared": True,
        "min_level": 0,
        "description": "Página de Registro"
    },
    "/change-password": {
        "shared": True,
        "min_level": 1,
        "description": "Alterar Senha"
    },
    
    # ========================================
    # PÁGINAS COMPARTILHADAS (todos os perfis)
    # ========================================
    "/": {
        "shared": True,
        "min_level": 1,
        "description": "Página Inicial (Home)"
    },
    
    # ========================================
    # MANUTENÇÃO
    # ========================================
    "/maintenance/alarms": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Alarmes de Manutenção"
    },
    "/maintenance/work-orders": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Ordens de Serviço"
    },
    "/maintenance/schedule": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Plano de Manutenção"
    },
    "/maintenance/history": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Histórico de Intervenções"
    },
    "/maintenance/indicators": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Indicadores de Manutenção"
    },
    "/maintenance/config": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 3,  # Apenas administradores
        "description": "Configuração de Metas de Manutenção"
    },
    "/maintenance/procedures": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Procedimentos de Manutenção"
    },
    "/maintenance/preventive/daily.md": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Procedimentos de Manutenção"
    },

    # ========================================
    # PRODUÇÃO
    # ========================================
    "/production/oee": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Dashboard OEE"
    },
    "/production/states": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Estados da Linha"
    },
    
    # ========================================
    # UTILIDADES - ENERGIA
    # ========================================
    "/energy": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Energia - Visão Geral"
    },
    "/utilities/energy": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Energia - Visão Geral"
    },
    "/utilities/energy/se01": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Subestação SE01"
    },
    "/utilities/energy/se02": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Subestação SE02"
    },
    "/utilities/energy/se03": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Subestação SE03"
    },
    "/utilities/energy/se04": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Subestação SE04"
    },
    "/utilities/energy/history": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Histórico de Consumo"
    },
    "/utilities/energy/costs": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Análise de Custos"
    },
    "/utilities/energy/config": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 3,  # Apenas administradores
        "description": "Configuração de Tarifas de Energia"
    },
    
    # ========================================
    # UTILIDADES - ÁGUA
    # ========================================
    "/utilities/water": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Água - Visão Geral"
    },
    "/utilities/water/points": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Pontos de Consumo de Água"
    },
    "/utilities/water/history": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Histórico de Água"
    },
    "/utilities/water/costs": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Custos de Água"
    },
    
    # ========================================
    # UTILIDADES - GÁS
    # ========================================
    "/utilities/gas": {
        "shared": False,
        "perfis": ["utilidades", "manutencao"],
        "min_level": 1,
        "description": "Gás - Visão Geral"
    },
    "/utilities/gas/points": {
        "shared": False,
        "perfis": ["utilidades", "manutencao"],
        "min_level": 1,
        "description": "Pontos de Medição de Gás"
    },
    "/utilities/gas/history": {
        "shared": False,
        "perfis": ["utilidades", "manutencao"],
        "min_level": 1,
        "description": "Histórico de Gás"
    },
    "/utilities/gas/costs": {
        "shared": False,
        "perfis": ["utilidades", "manutencao"],
        "min_level": 1,
        "description": "Custos de Gás"
    },
    
    # ========================================
    # UTILIDADES - AR COMPRIMIDO
    # ========================================
    "/utilities/compressed-air": {
        "shared": False,
        "perfis": ["utilidades", "manutencao"],
        "min_level": 1,
        "description": "Ar Comprimido - Visão Geral"
    },
    "/utilities/compressed-air/compressors": {
        "shared": False,
        "perfis": ["utilidades", "manutencao"],
        "min_level": 1,
        "description": "Compressores"
    },
    "/utilities/compressed-air/efficiency": {
        "shared": False,
        "perfis": ["utilidades", "manutencao"],
        "min_level": 1,
        "description": "Eficiência de Ar Comprimido"
    },
    
    # ========================================
    # UTILIDADES - DASHBOARD INTEGRADO
    # ========================================
    "/utilities/dashboard": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Dashboard Integrado de Utilidades"
    },
    
    # ========================================
    # SUPERVISÓRIO
    # ========================================
    "/supervision": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 2,  # Requer nível 2 ou 3
        "description": "Supervisório - Controle de Temperatura"
    },
    
    # ========================================
    # RELATÓRIOS
    # ========================================
    "/reports": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Relatórios"
    },
    
    # ========================================
    # CONFIGURAÇÕES (apenas nível 3)
    # ========================================
    "/config/users": {
        "shared": False,
        "perfis": ["manutencao", "admin", "qualidade", "producao", "utilidades"],
        "min_level": 3,
        "description": "Gerenciar Usuários"
    },
    "/config/preferences": {
        "shared": False,
        "perfis": ["manutencao", "admin"],
        "min_level": 3,
        "description": "Preferências do Sistema"
    },
    "/config/logs": {
        "shared": False,
        "perfis": ["manutencao", "admin"],
        "min_level": 3,
        "description": "Logs do Sistema"
    },
    "/config/users/create": {
        "shared": True,  # Todos os perfis de nível 3 podem criar usuários
        "min_level": 3,
        "description": "Criar Novo Usuário"
    },
}


# ========================================
# CONFIGURAÇÃO DE ACESSO AOS MENUS
# ========================================
#
# Define quais menus/dropdowns aparecem para cada perfil
# Estrutura similar à ROUTE_ACCESS

MENU_ACCESS = {
    # Menu Início - Compartilhado
    "home": {
        "shared": True,
        "min_level": 1,
        "description": "Menu Início"
    },
    
    # Menu Manutenção
    "manutencao": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Menu Manutenção"
    },
    
    # Menu Produção
    "producao": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Menu Produção"
    },
    
    # Menu Utilidades
    "utilidades": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 1,
        "description": "Menu Utilidades"
    },
    
    # Menu Supervisório
    "supervisorio": {
        "shared": False,
        "perfis": ["manutencao"],
        "min_level": 2,
        "description": "Menu Supervisório"
    },
    
    # Menu Configurações
    "configuracoes": {
        "shared": True,  # Todos os perfis de nível 3 podem acessar
        "min_level": 3,
        "description": "Menu Configurações"
    },
}


# ========================================
# FUNÇÕES AUXILIARES DE CONFIGURAÇÃO
# ========================================

def get_route_config(pathname):
    """
    Retorna a configuração de acesso para uma rota.

    Args:
        pathname (str): Caminho da rota

    Returns:
        dict: Configuração da rota ou configuração padrão restritiva
    """
    # Configuração padrão para rotas não mapeadas (restritivo)
    default_config = {
        "shared": False,
        "perfis": ["admin"],
        "min_level": 3,
        "description": "Rota não configurada"
    }

    # Verificar se a rota existe no mapeamento
    if pathname in ROUTE_ACCESS:
        return ROUTE_ACCESS[pathname]

    # Suporte a rotas dinâmicas de markdown (procedimentos de manutenção)
    if pathname.startswith('/maintenance/') and pathname.endswith('.md'):
        return {
            "shared": False,
            "perfis": ["manutencao"],
            "min_level": 1,
            "description": "Procedimento de manutenção"
        }

    return default_config


def get_menu_config(menu_key):
    """
    Retorna a configuração de acesso para um menu.
    
    Args:
        menu_key (str): Chave do menu
        
    Returns:
        dict: Configuração do menu ou configuração padrão restritiva
    """
    default_config = {
        "shared": False,
        "perfis": ["admin"],
        "min_level": 3,
        "description": "Menu não configurado"
    }
    
    return MENU_ACCESS.get(menu_key, default_config)


def is_public_route(pathname):
    """
    Verifica se uma rota é pública (não requer autenticação).
    
    Args:
        pathname (str): Caminho da rota
        
    Returns:
        bool: True se a rota é pública
    """
    config = get_route_config(pathname)
    return config.get("min_level", 1) == 0