# src/callbacks_registers/energy_config_callbacks.py

"""
Callbacks para a página de configuração de tarifas de energia.
Gerencia carregamento e salvamento da configuração no MongoDB.
"""

from dash import Input, Output, State, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from src.database.connection import get_mongo_connection
from flask_login import current_user
from datetime import datetime


def register_energy_config_callbacks(app):
    """
    Registra os callbacks para a página de configuração de energia.

    Args:
        app: Instância da aplicação Dash.
    """

    # ========================================
    # CALLBACK 1: Carregar configuração existente
    # ========================================
    @app.callback(
        [
            Output("input-demanda-ponta", "value"),
            Output("input-demanda-fora-ponta", "value"),
            Output("input-demanda-contratada-ponta", "value"),
            Output("input-demanda-contratada-fora-ponta", "value"),
            Output("input-tusd-ponta", "value"),
            Output("input-tusd-fora-ponta", "value"),
            Output("input-energia-ponta", "value"),
            Output("input-energia-fora-ponta", "value"),
            Output("input-horario-inicio", "value"),
            Output("input-horario-fim", "value"),
        ],
        Input("url", "pathname")
    )
    def load_config(pathname):
        """
        Carrega a configuração existente ao acessar a página.

        Args:
            pathname: Caminho da URL atual

        Returns:
            list: Valores dos campos de configuração
        """
        if pathname != "/utilities/energy/config":
            raise PreventUpdate

        try:
            # Buscar configuração no MongoDB
            collection = get_mongo_connection("AMG_EnergyConfig")
            config = collection.find_one()

            if config:
                # Retornar valores existentes
                return [
                    config.get("demanda_usd_ponta"),
                    config.get("demanda_usd_fora_ponta"),
                    config.get("demanda_contratada_ponta_kw"),
                    config.get("demanda_contratada_fora_ponta_kw"),
                    config.get("preco_tusd_ponta"),
                    config.get("preco_tusd_fora_ponta"),
                    config.get("preco_energia_ponta"),
                    config.get("preco_energia_fora_ponta"),
                    config.get("horario_ponta_inicio", "18:00"),
                    config.get("horario_ponta_fim", "21:00"),
                ]
            else:
                # Retornar valores padrão
                return [None, None, None, None, None, None, None, None, "18:00", "21:00"]

        except Exception as e:
            print(f"Erro ao carregar configuração: {e}")
            # Retornar valores padrão em caso de erro
            return [None, None, None, None, None, None, None, None, "18:00", "21:00"]


    # ========================================
    # CALLBACK 2: Atualizar preview do horário de ponta
    # ========================================
    @app.callback(
        Output("horario-ponta-preview", "children"),
        [
            Input("input-horario-inicio", "value"),
            Input("input-horario-fim", "value")
        ]
    )
    def update_horario_preview(inicio, fim):
        """
        Atualiza o preview do horário de ponta conforme usuário digita.

        Args:
            inicio: Horário de início (HH:MM)
            fim: Horário de término (HH:MM)

        Returns:
            str: Texto formatado do horário de ponta
        """
        if not inicio or not fim:
            return "Configure os horários de início e fim"

        return f"Horário de ponta: {inicio} às {fim}"


    # ========================================
    # CALLBACK 3: Salvar configuração
    # ========================================
    @app.callback(
        Output("config-alert", "children"),
        Input("btn-save-config", "n_clicks"),
        [
            State("input-demanda-ponta", "value"),
            State("input-demanda-fora-ponta", "value"),
            State("input-demanda-contratada-ponta", "value"),
            State("input-demanda-contratada-fora-ponta", "value"),
            State("input-tusd-ponta", "value"),
            State("input-tusd-fora-ponta", "value"),
            State("input-energia-ponta", "value"),
            State("input-energia-fora-ponta", "value"),
            State("input-horario-inicio", "value"),
            State("input-horario-fim", "value"),
        ],
        prevent_initial_call=True
    )
    def save_config(
        n_clicks,
        demanda_ponta,
        demanda_fora_ponta,
        demanda_contratada_ponta,
        demanda_contratada_fora_ponta,
        tusd_ponta,
        tusd_fora_ponta,
        energia_ponta,
        energia_fora_ponta,
        horario_inicio,
        horario_fim
    ):
        """
        Salva a configuração de tarifas no MongoDB.

        Args:
            n_clicks: Número de cliques no botão
            demanda_ponta: Custo demanda ponta (R$)
            demanda_fora_ponta: Custo demanda fora ponta (R$)
            demanda_contratada_ponta: Demanda contratada ponta (kW)
            demanda_contratada_fora_ponta: Demanda contratada fora ponta (kW)
            tusd_ponta: Tarifa TUSD ponta (R$/kWh)
            tusd_fora_ponta: Tarifa TUSD fora ponta (R$/kWh)
            energia_ponta: Tarifa energia ponta (R$/kWh)
            energia_fora_ponta: Tarifa energia fora ponta (R$/kWh)
            horario_inicio: Horário início ponta (HH:MM)
            horario_fim: Horário fim ponta (HH:MM)

        Returns:
            dbc.Alert: Mensagem de sucesso ou erro
        """
        if not n_clicks:
            raise PreventUpdate

        # ========================================
        # VALIDAÇÃO 1: Verificar permissão (Nível 3)
        # ========================================
        if not current_user.is_authenticated:
            return dbc.Alert([
                html.I(className="bi bi-x-circle-fill me-2"),
                "Você precisa estar autenticado para salvar configurações."
            ], color="danger", dismissable=True, duration=5000)

        if current_user.level < 3:
            return dbc.Alert([
                html.I(className="bi bi-shield-lock-fill me-2"),
                f"Acesso negado. Esta página requer Nível 3 (Administrador). Seu nível: {current_user.level}"
            ], color="danger", dismissable=True, duration=5000)

        # ========================================
        # VALIDAÇÃO 2: Verificar campos obrigatórios
        # ========================================
        campos_obrigatorios = [
            ("Custo Demanda Ponta", demanda_ponta),
            ("Custo Demanda Fora de Ponta", demanda_fora_ponta),
            ("Demanda Contratada Ponta", demanda_contratada_ponta),
            ("Demanda Contratada Fora de Ponta", demanda_contratada_fora_ponta),
            ("TUSD Ponta", tusd_ponta),
            ("TUSD Fora de Ponta", tusd_fora_ponta),
            ("Energia Ponta", energia_ponta),
            ("Energia Fora de Ponta", energia_fora_ponta),
            ("Horário Início", horario_inicio),
            ("Horário Fim", horario_fim),
        ]

        campos_vazios = [nome for nome, valor in campos_obrigatorios if valor is None or valor == ""]

        if campos_vazios:
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle-fill me-2"),
                html.Div([
                    html.P("Os seguintes campos são obrigatórios:", className="mb-1"),
                    html.Ul([html.Li(campo) for campo in campos_vazios], className="mb-0")
                ])
            ], color="warning", dismissable=True, duration=5000)

        # ========================================
        # VALIDAÇÃO 3: Verificar valores numéricos >= 0
        # ========================================
        try:
            valores_numericos = [
                ("Custo Demanda Ponta", float(demanda_ponta)),
                ("Custo Demanda Fora de Ponta", float(demanda_fora_ponta)),
                ("Demanda Contratada Ponta", float(demanda_contratada_ponta)),
                ("Demanda Contratada Fora de Ponta", float(demanda_contratada_fora_ponta)),
                ("TUSD Ponta", float(tusd_ponta)),
                ("TUSD Fora de Ponta", float(tusd_fora_ponta)),
                ("Energia Ponta", float(energia_ponta)),
                ("Energia Fora de Ponta", float(energia_fora_ponta)),
            ]

            valores_negativos = [nome for nome, valor in valores_numericos if valor < 0]

            if valores_negativos:
                return dbc.Alert([
                    html.I(className="bi bi-exclamation-triangle-fill me-2"),
                    html.Div([
                        html.P("Os seguintes campos não podem ser negativos:", className="mb-1"),
                        html.Ul([html.Li(campo) for campo in valores_negativos], className="mb-0")
                    ])
                ], color="warning", dismissable=True, duration=5000)

        except (ValueError, TypeError) as e:
            return dbc.Alert([
                html.I(className="bi bi-x-circle-fill me-2"),
                f"Erro ao validar valores numéricos: {str(e)}"
            ], color="danger", dismissable=True, duration=5000)

        # ========================================
        # VALIDAÇÃO 4: Verificar formato dos horários (HH:MM)
        # ========================================
        import re
        horario_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

        if not horario_pattern.match(horario_inicio):
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle-fill me-2"),
                "Horário de início inválido. Use o formato HH:MM (00:00 a 23:59)"
            ], color="warning", dismissable=True, duration=5000)

        if not horario_pattern.match(horario_fim):
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle-fill me-2"),
                "Horário de término inválido. Use o formato HH:MM (00:00 a 23:59)"
            ], color="warning", dismissable=True, duration=5000)

        # ========================================
        # SALVAR NO MONGODB (Upsert - replace if exists)
        # ========================================
        try:
            collection = get_mongo_connection("AMG_EnergyConfig")

            # Documento de configuração
            config_document = {
                "version": 1,
                "last_updated": datetime.utcnow(),
                "updated_by": current_user.username,

                # Custos de demanda
                "demanda_usd_ponta": float(demanda_ponta),
                "demanda_usd_fora_ponta": float(demanda_fora_ponta),

                # Demanda contratada (kW)
                "demanda_contratada_ponta_kw": float(demanda_contratada_ponta),
                "demanda_contratada_fora_ponta_kw": float(demanda_contratada_fora_ponta),

                # Tarifas TUSD (R$/kWh)
                "preco_tusd_ponta": float(tusd_ponta),
                "preco_tusd_fora_ponta": float(tusd_fora_ponta),

                # Tarifas Energia (R$/kWh)
                "preco_energia_ponta": float(energia_ponta),
                "preco_energia_fora_ponta": float(energia_fora_ponta),

                # Horário de ponta
                "horario_ponta_inicio": horario_inicio,
                "horario_ponta_fim": horario_fim
            }

            # Upsert: atualiza se existe, cria se não existe
            result = collection.replace_one({}, config_document, upsert=True)

            if result.matched_count > 0:
                mensagem = "Configuração atualizada com sucesso!"
            else:
                mensagem = "Configuração criada com sucesso!"

            return dbc.Alert([
                html.I(className="bi bi-check-circle-fill me-2"),
                html.Div([
                    html.P(mensagem, className="mb-1 fw-bold"),
                    html.Small(f"Última atualização por: {current_user.username}", className="text-muted")
                ])
            ], color="success", dismissable=True, duration=5000)

        except Exception as e:
            print(f"Erro ao salvar configuração: {e}")
            return dbc.Alert([
                html.I(className="bi bi-x-circle-fill me-2"),
                f"Erro ao salvar configuração: {str(e)}"
            ], color="danger", dismissable=True, duration=5000)


    # ========================================
    # CALLBACK 4: Redefinir formulário
    # ========================================
    @app.callback(
        [
            Output("input-demanda-ponta", "value", allow_duplicate=True),
            Output("input-demanda-fora-ponta", "value", allow_duplicate=True),
            Output("input-demanda-contratada-ponta", "value", allow_duplicate=True),
            Output("input-demanda-contratada-fora-ponta", "value", allow_duplicate=True),
            Output("input-tusd-ponta", "value", allow_duplicate=True),
            Output("input-tusd-fora-ponta", "value", allow_duplicate=True),
            Output("input-energia-ponta", "value", allow_duplicate=True),
            Output("input-energia-fora-ponta", "value", allow_duplicate=True),
            Output("input-horario-inicio", "value", allow_duplicate=True),
            Output("input-horario-fim", "value", allow_duplicate=True),
        ],
        Input("btn-reset-config", "n_clicks"),
        prevent_initial_call=True
    )
    def reset_config(n_clicks):
        """
        Redefine o formulário para valores vazios.

        Args:
            n_clicks: Número de cliques no botão

        Returns:
            list: Valores padrão para todos os campos
        """
        if not n_clicks:
            raise PreventUpdate

        # Retornar valores padrão
        return [None, None, None, None, None, None, None, None, "18:00", "21:00"]
