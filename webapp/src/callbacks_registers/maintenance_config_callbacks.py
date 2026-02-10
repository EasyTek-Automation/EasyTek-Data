# src/callbacks_registers/maintenance_config_callbacks.py

"""
Callbacks para Configuração de Metas de Manutenção
===================================================

Gerencia a interface de configuração de metas de MTBF, MTTR e Taxa de Avaria.

Callbacks principais:
1. Carregar lista de equipamentos e gerar formulários dinâmicos
2. Carregar configuração existente do MongoDB
3. Salvar nova configuração (com validação)
4. Redefinir formulário

Pattern-Matching IDs usados:
- {"type": "equipment-mtbf", "index": equipment_id}
- {"type": "equipment-mttr", "index": equipment_id}
- {"type": "equipment-breakdown", "index": equipment_id}
"""

from dash import Input, Output, State, html, ALL, MATCH, ctx
import dash_bootstrap_components as dbc
from flask_login import current_user
from datetime import datetime

from src.database.connection import get_mongo_connection
from src.utils.maintenance_demo_data import get_equipment_names


def register_maintenance_config_callbacks(app):
    """Registra todos os callbacks da página de configuração de metas."""

    # ========================================
    # CALLBACK 1: CARREGAR EQUIPAMENTOS
    # ========================================
    @app.callback(
        [Output("maintenance-equipment-list", "data"),
         Output("equipment-targets-container", "children")],
        Input("url", "pathname")
    )
    def load_equipment_list(pathname):
        """
        Carrega lista de equipamentos e gera formulários dinâmicos.

        Returns:
            tuple: (lista de equipamentos, componentes HTML)
        """
        if pathname != "/maintenance/config":
            return [], []

        # Buscar equipamentos
        equipment_list = get_equipment_names()

        if not equipment_list:
            return [], dbc.Alert([
                html.I(className="bi bi-exclamation-circle me-2"),
                "Nenhum equipamento encontrado no sistema."
            ], color="warning")

        # Gerar card para cada equipamento
        equipment_cards = []

        for eq_id in sorted(equipment_list):
            card = dbc.Card([
                dbc.CardHeader([
                    html.H5([
                        html.I(className="bi bi-gear me-2"),
                        eq_id
                    ], className="mb-0")
                ]),
                dbc.CardBody([
                    dbc.Row([
                        # MTBF
                        dbc.Col([
                            dbc.Label("MTBF (h)", className="small"),
                            dbc.Input(
                                id={"type": "equipment-mtbf", "index": eq_id},
                                type="number",
                                placeholder="Usar meta geral",
                                step=0.01,
                                min=0,
                                size="sm"
                            )
                        ], md=4),

                        # MTTR
                        dbc.Col([
                            dbc.Label("MTTR (min)", className="small"),
                            dbc.Input(
                                id={"type": "equipment-mttr", "index": eq_id},
                                type="number",
                                placeholder="Usar meta geral",
                                step=0.01,
                                min=0,
                                size="sm"
                            )
                        ], md=4),

                        # Taxa de Avaria
                        dbc.Col([
                            dbc.Label("Avaria (%)", className="small"),
                            dbc.Input(
                                id={"type": "equipment-breakdown", "index": eq_id},
                                type="number",
                                placeholder="Usar meta geral",
                                step=0.01,
                                min=0,
                                max=100,
                                size="sm"
                            )
                        ], md=4),
                    ])
                ])
            ], className="mb-2")

            equipment_cards.append(card)

        return equipment_list, equipment_cards

    # ========================================
    # CALLBACK 2: CARREGAR CONFIGURAÇÃO
    # ========================================
    @app.callback(
        [Output("input-general-mtbf", "value"),
         Output("input-general-mttr", "value"),
         Output("input-general-breakdown-rate", "value"),
         Output("input-general-alert-range", "value"),
         Output({"type": "equipment-mtbf", "index": ALL}, "value"),
         Output({"type": "equipment-mttr", "index": ALL}, "value"),
         Output({"type": "equipment-breakdown", "index": ALL}, "value")],
        [Input("maintenance-equipment-list", "data"),
         Input("url", "pathname")]
    )
    def load_config(equipment_list, pathname):
        if pathname != "/maintenance/config" or not equipment_list:
            return None, None, None, 3.0, [], [], []

        try:
            collection = get_mongo_connection("AMG_MaintenanceTargets")
            config = collection.find_one()

            if not config:
                return None, None, None, 3.0, [None] * len(equipment_list), [None] * len(equipment_list), [None] * len(equipment_list)

            general = config.get("general", {})
            general_mtbf = general.get("mtbf")
            general_mttr = general.get("mttr")
            general_breakdown = general.get("breakdown_rate")
            alert_range = general.get("alert_range", 3.0)

            equipment_targets = config.get("equipment_targets", {})

            mtbf_values = []
            mttr_values = []
            breakdown_values = []

            for eq_id in sorted(equipment_list):
                eq_config = equipment_targets.get(eq_id, {})
                mtbf_values.append(eq_config.get("mtbf"))
                mttr_values.append(eq_config.get("mttr"))
                breakdown_values.append(eq_config.get("breakdown_rate"))

            return general_mtbf, general_mttr, general_breakdown, alert_range, mtbf_values, mttr_values, breakdown_values

        except Exception as e:
            return None, None, None, 3.0, [None] * len(equipment_list), [None] * len(equipment_list), [None] * len(equipment_list)

    # ========================================
    # CALLBACK 3: SALVAR CONFIGURAÇÃO ⭐
    # ========================================
    @app.callback(
        Output("maintenance-config-alert", "children"),
        Input("btn-save-maintenance-config", "n_clicks"),
        [State("input-general-mtbf", "value"),
         State("input-general-mttr", "value"),
         State("input-general-breakdown-rate", "value"),
         State("input-general-alert-range", "value"),
         State("maintenance-equipment-list", "data"),
         State({"type": "equipment-mtbf", "index": ALL}, "value"),
         State({"type": "equipment-mttr", "index": ALL}, "value"),
         State({"type": "equipment-breakdown", "index": ALL}, "value")],
        prevent_initial_call=True
    )
    def save_config(n_clicks, general_mtbf, general_mttr, general_breakdown, alert_range,
                    equipment_list, eq_mtbf_values, eq_mttr_values, eq_breakdown_values):
        """
        Salva configuração no MongoDB com validação.

        Validações:
        1. Usuário autenticado + Nível 3
        2. Metas gerais obrigatórias
        3. Valores numéricos >= 0
        4. Taxa de avaria <= 100%

        Returns:
            dbc.Alert: Mensagem de sucesso ou erro
        """
        if not n_clicks:
            return None

        # VALIDAÇÃO 1: Autenticação e permissão
        if not current_user.is_authenticated:
            return dbc.Alert([
                html.I(className="bi bi-x-circle me-2"),
                "Você precisa estar autenticado para salvar configurações."
            ], color="danger", dismissable=True)

        if current_user.level < 3:
            return dbc.Alert([
                html.I(className="bi bi-shield-lock me-2"),
                "Apenas administradores (Nível 3) podem modificar as metas."
            ], color="danger", dismissable=True)

        # VALIDAÇÃO 2: Metas gerais obrigatórias
        if general_mtbf is None or general_mttr is None or general_breakdown is None:
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                "Todas as metas gerais (MTBF, MTTR e Taxa de Avaria) são obrigatórias."
            ], color="warning", dismissable=True)

        # VALIDAÇÃO 3: Valores numéricos válidos
        try:
            general_mtbf = float(general_mtbf)
            general_mttr = float(general_mttr)
            general_breakdown = float(general_breakdown)

            if general_mtbf < 0 or general_mttr < 0 or general_breakdown < 0:
                raise ValueError("Valores não podem ser negativos")

        except (ValueError, TypeError) as e:
            return dbc.Alert([
                html.I(className="bi bi-x-circle me-2"),
                f"Erro nos valores das metas gerais: {str(e)}"
            ], color="danger", dismissable=True)

        # VALIDAÇÃO 4: Taxa de avaria <= 100%
        if general_breakdown > 100:
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                "Taxa de Avaria não pode exceder 100%."
            ], color="warning", dismissable=True)

        # VALIDAÇÃO 5: Alert range
        if alert_range is None:
            alert_range = 3.0
        try:
            alert_range = float(alert_range)
            if alert_range < 0.1 or alert_range > 20:
                raise ValueError("Range deve estar entre 0.1% e 20%")
        except (ValueError, TypeError) as e:
            return dbc.Alert([
                html.I(className="bi bi-x-circle me-2"),
                f"Erro no Range de Alerta: {str(e)}"
            ], color="danger", dismissable=True)

        # CONSTRUIR DOCUMENTO DE CONFIGURAÇÃO
        config_document = {
            "version": 1,
            "last_updated": datetime.utcnow(),
            "updated_by": current_user.username,
            "general": {
                "mtbf": general_mtbf,
                "mttr": general_mttr,
                "breakdown_rate": general_breakdown,
                "alert_range": alert_range
            },
            "equipment_targets": {}
        }

        # Processar metas por equipamento (apenas valores preenchidos)
        for idx, eq_id in enumerate(sorted(equipment_list)):
            eq_mtbf = eq_mtbf_values[idx]
            eq_mttr = eq_mttr_values[idx]
            eq_breakdown = eq_breakdown_values[idx]

            # Verificar se pelo menos um campo foi preenchido
            if eq_mtbf is not None or eq_mttr is not None or eq_breakdown is not None:
                eq_config = {}

                # Validar e adicionar MTBF
                if eq_mtbf is not None:
                    try:
                        eq_mtbf = float(eq_mtbf)
                        if eq_mtbf < 0:
                            raise ValueError(f"MTBF negativo para {eq_id}")
                        eq_config["mtbf"] = eq_mtbf
                    except (ValueError, TypeError) as e:
                        return dbc.Alert([
                            html.I(className="bi bi-x-circle me-2"),
                            f"Erro no MTBF de {eq_id}: {str(e)}"
                        ], color="danger", dismissable=True)

                # Validar e adicionar MTTR
                if eq_mttr is not None:
                    try:
                        eq_mttr = float(eq_mttr)
                        if eq_mttr < 0:
                            raise ValueError(f"MTTR negativo para {eq_id}")
                        eq_config["mttr"] = eq_mttr
                    except (ValueError, TypeError) as e:
                        return dbc.Alert([
                            html.I(className="bi bi-x-circle me-2"),
                            f"Erro no MTTR de {eq_id}: {str(e)}"
                        ], color="danger", dismissable=True)

                # Validar e adicionar Taxa de Avaria
                if eq_breakdown is not None:
                    try:
                        eq_breakdown = float(eq_breakdown)
                        if eq_breakdown < 0 or eq_breakdown > 100:
                            raise ValueError(f"Taxa de Avaria fora da faixa 0-100% para {eq_id}")
                        eq_config["breakdown_rate"] = eq_breakdown
                    except (ValueError, TypeError) as e:
                        return dbc.Alert([
                            html.I(className="bi bi-x-circle me-2"),
                            f"Erro na Taxa de Avaria de {eq_id}: {str(e)}"
                        ], color="danger", dismissable=True)

                # Adicionar ao documento se houver algum campo válido
                if eq_config:
                    config_document["equipment_targets"][eq_id] = eq_config

        # SALVAR NO MONGODB
        try:
            collection = get_mongo_connection("AMG_MaintenanceTargets")

            # Upsert: substitui documento existente ou cria novo
            result = collection.replace_one({}, config_document, upsert=True)

            if result.matched_count > 0:
                action = "atualizada"
            else:
                action = "criada"

            return dbc.Alert([
                html.I(className="bi bi-check-circle me-2"),
                f"Configuração {action} com sucesso! ",
                html.Br(),
                html.Small([
                    f"Metas gerais definidas. ",
                    f"{len(config_document['equipment_targets'])} equipamento(s) com metas específicas.",
                    html.Br(),
                    html.Br(),
                    html.Strong("💡 Dica: "),
                    "Clique no botão ",
                    html.Strong("'Atualizar'"),
                    " na página de Indicadores para ver as novas metas aplicadas."
                ], className="text-muted")
            ], color="success", dismissable=True, duration=12000)

        except Exception as e:
            return dbc.Alert([
                html.I(className="bi bi-x-circle me-2"),
                f"Erro ao salvar configuração no MongoDB: {str(e)}"
            ], color="danger", dismissable=True)

    # ========================================
    # CALLBACK 4: REDEFINIR FORMULÁRIO
    # ========================================
    @app.callback(
        [Output("input-general-mtbf", "value", allow_duplicate=True),
         Output("input-general-mttr", "value", allow_duplicate=True),
         Output("input-general-breakdown-rate", "value", allow_duplicate=True),
         Output("input-general-alert-range", "value", allow_duplicate=True),
         Output({"type": "equipment-mtbf", "index": ALL}, "value", allow_duplicate=True),
         Output({"type": "equipment-mttr", "index": ALL}, "value", allow_duplicate=True),
         Output({"type": "equipment-breakdown", "index": ALL}, "value", allow_duplicate=True),
         Output("maintenance-config-alert", "children", allow_duplicate=True)],
        Input("btn-reset-maintenance-config", "n_clicks"),
        State("maintenance-equipment-list", "data"),
        prevent_initial_call=True
    )
    def reset_config(n_clicks, equipment_list):
        """
        Limpa todos os campos do formulário.

        Returns:
            tuple: None para todos os campos + mensagem de confirmação
        """
        if not n_clicks:
            return [None, None, None, 3.0, [], [], [], None]

        num_equipment = len(equipment_list) if equipment_list else 0

        alert = dbc.Alert([
            html.I(className="bi bi-info-circle me-2"),
            "Formulário limpo. Preencha novamente para salvar."
        ], color="info", dismissable=True, duration=4000)

        return None, None, None, 3.0, [None] * num_equipment, [None] * num_equipment, [None] * num_equipment, alert
