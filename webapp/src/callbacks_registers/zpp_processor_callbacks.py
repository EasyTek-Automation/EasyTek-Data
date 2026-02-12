"""
ZPP Processor Callbacks
Callbacks para a página de processamento de planilhas ZPP
"""
import logging
import os
import requests
from dash import Output, Input, State, html, no_update, ctx
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from src.components.zpp_processor_components import (
    create_file_item,
    create_history_table_component
)

logger = logging.getLogger(__name__)

# URL da API do ZPP Processor (configurável via ambiente)
ZPP_API_URL = os.getenv('ZPP_PROCESSOR_URL', 'http://zpp-processor:5002')


def register_zpp_processor_callbacks(app):
    """
    Registra todos os callbacks da página de ZPP Processor

    Args:
        app: Instância do Dash app
    """

    # ============================================================
    # CALLBACK 1: Auto-load Inicial
    # ============================================================
    @app.callback(
        [
            Output('store-zpp-config', 'data'),
            Output('list-files-input', 'children'),
            Output('badge-count-input', 'children'),
            Output('list-files-output', 'children'),
            Output('badge-count-output', 'children'),
            Output('history-table-container', 'children'),
            Output('switch-auto-process', 'value'),
            Output('input-interval-minutes', 'value')
        ],
        Input('interval-zpp-autoload', 'n_intervals')
    )
    def autoload_data(n):
        """Auto-load: carrega configuração, arquivos e histórico na entrada da página"""
        if n is None or n == 0:
            raise PreventUpdate

        try:
            # 1. Carregar configuração
            config_response = requests.get(f"{ZPP_API_URL}/api/zpp/config", timeout=5)
            config = config_response.json() if config_response.ok else {}

            auto_process = config.get('auto_process', True)
            interval_min = config.get('interval_minutes', 60)

            # 2. Listar arquivos de input
            input_response = requests.get(f"{ZPP_API_URL}/api/zpp/files/input", timeout=5)
            input_data = input_response.json() if input_response.ok else {'count': 0, 'files': []}

            input_files = input_data.get('files', [])
            input_count = input_data.get('count', 0)

            if input_files:
                input_list = dbc.ListGroup([
                    create_file_item(f['filename'], f['size_mb'], f['modified_at'])
                    for f in input_files
                ])
            else:
                input_list = html.P("Nenhum arquivo pendente", className="text-muted text-center my-4")

            input_badge = f"{input_count} arquivo(s)"

            # 3. Listar arquivos de output
            output_response = requests.get(f"{ZPP_API_URL}/api/zpp/files/output", timeout=5)
            output_data = output_response.json() if output_response.ok else {'count': 0, 'files': []}

            output_files = output_data.get('files', [])
            output_count = output_data.get('count', 0)

            if output_files:
                output_list = dbc.ListGroup([
                    create_file_item(f['filename'], f['size_mb'], f['modified_at'])
                    for f in output_files[:10]  # Limitar a 10
                ])
            else:
                output_list = html.P("Nenhum arquivo processado", className="text-muted text-center my-4")

            output_badge = f"{output_count} arquivo(s)"

            # 4. Carregar histórico
            history_response = requests.get(f"{ZPP_API_URL}/api/zpp/history?limit=20", timeout=5)
            history_data = history_response.json() if history_response.ok else {'logs': []}

            logs = history_data.get('logs', [])
            history_table = create_history_table_component(logs)

            return (
                config,
                input_list, input_badge,
                output_list, output_badge,
                history_table,
                auto_process, interval_min
            )

        except Exception as e:
            logger.error(f"Erro no auto-load: {e}")
            error_msg = html.P(
                f"Erro ao conectar com o serviço: {str(e)}",
                className="text-danger text-center my-4"
            )
            return (
                {}, error_msg, "Erro", error_msg, "Erro", error_msg, True, 60
            )

    # ============================================================
    # CALLBACK 2: Processar Arquivos (Botão)
    # ============================================================
    @app.callback(
        [
            Output('store-zpp-job-id', 'data'),
            Output('interval-zpp-status', 'disabled'),
            Output('btn-process-zpp', 'disabled'),
            Output('process-status', 'children'),
            Output('toast-notification-zpp', 'is_open', allow_duplicate=True),
            Output('toast-notification-zpp', 'children', allow_duplicate=True),
            Output('toast-notification-zpp', 'icon', allow_duplicate=True)
        ],
        Input('btn-process-zpp', 'n_clicks'),
        prevent_initial_call=True
    )
    def trigger_processing(n_clicks):
        """Inicia processamento manual"""
        if not n_clicks:
            raise PreventUpdate

        try:
            # Chamar API
            response = requests.post(
                f"{ZPP_API_URL}/api/zpp/process",
                json={"triggered_by": "webapp_user"},
                timeout=10
            )

            if response.ok:
                data = response.json()
                job_id = data.get('job_id')

                status_msg = dbc.Alert([
                    html.I(className="bi bi-hourglass-split me-2"),
                    f"Processamento iniciado (Job ID: {job_id[:8]}...)"
                ], color="info", className="mb-0")

                toast_msg = "Processamento iniciado com sucesso!"

                return (
                    job_id,  # store job_id
                    False,   # habilitar interval
                    True,    # desabilitar botão
                    status_msg,
                    True,    # abrir toast
                    toast_msg,
                    "success"
                )
            else:
                error_msg = dbc.Alert([
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    f"Erro: {response.text}"
                ], color="danger", className="mb-0")

                return (
                    None, True, False, error_msg,
                    True, "Erro ao iniciar processamento", "danger"
                )

        except Exception as e:
            logger.error(f"Erro ao processar: {e}")
            error_msg = dbc.Alert([
                html.I(className="bi bi-x-circle me-2"),
                f"Erro de conexão: {str(e)}"
            ], color="danger", className="mb-0")

            return (
                None, True, False, error_msg,
                True, f"Erro: {str(e)}", "danger"
            )

    # ============================================================
    # CALLBACK 3: Polling de Status
    # ============================================================
    @app.callback(
        [
            Output('process-status', 'children', allow_duplicate=True),
            Output('interval-zpp-status', 'disabled', allow_duplicate=True),
            Output('btn-process-zpp', 'disabled', allow_duplicate=True),
            Output('history-table-container', 'children', allow_duplicate=True),
            Output('list-files-input', 'children', allow_duplicate=True),
            Output('badge-count-input', 'children', allow_duplicate=True),
            Output('toast-notification-zpp', 'is_open', allow_duplicate=True),
            Output('toast-notification-zpp', 'children', allow_duplicate=True),
            Output('toast-notification-zpp', 'icon', allow_duplicate=True)
        ],
        Input('interval-zpp-status', 'n_intervals'),
        State('store-zpp-job-id', 'data'),
        prevent_initial_call=True
    )
    def poll_job_status(n, job_id):
        """Polling de status do job em execução"""
        if not job_id:
            raise PreventUpdate

        try:
            response = requests.get(f"{ZPP_API_URL}/api/zpp/status/{job_id}", timeout=5)

            if not response.ok:
                raise PreventUpdate

            data = response.json()
            status = data.get('status')

            # Se ainda está rodando, manter polling
            if status == 'running':
                status_msg = dbc.Alert([
                    dbc.Spinner(size="sm", className="me-2"),
                    "Processamento em andamento..."
                ], color="info", className="mb-0")

                return (
                    status_msg,
                    False,  # manter interval ativo
                    True,   # manter botão desabilitado
                    no_update, no_update, no_update,
                    False, "", "success"
                )

            # Processamento concluído (success ou failed)
            files_processed = data.get('files_processed', 0)
            total_uploaded = data.get('total_uploaded', 0)

            if status == 'success':
                status_msg = dbc.Alert([
                    html.I(className="bi bi-check-circle me-2"),
                    f"✓ Processamento concluído: {files_processed} arquivo(s), {total_uploaded:,} registros"
                ], color="success", className="mb-0")

                toast_msg = f"Processamento concluído com sucesso! {total_uploaded:,} registros carregados."
                toast_icon = "success"
            else:
                error = data.get('error', 'Erro desconhecido')
                status_msg = dbc.Alert([
                    html.I(className="bi bi-x-circle me-2"),
                    f"✗ Processamento falhou: {error}"
                ], color="danger", className="mb-0")

                toast_msg = f"Processamento falhou: {error}"
                toast_icon = "danger"

            # Atualizar histórico e lista de arquivos
            history_response = requests.get(f"{ZPP_API_URL}/api/zpp/history?limit=20", timeout=5)
            history_data = history_response.json() if history_response.ok else {'logs': []}
            history_table = create_history_table_component(history_data.get('logs', []))

            input_response = requests.get(f"{ZPP_API_URL}/api/zpp/files/input", timeout=5)
            input_data = input_response.json() if input_response.ok else {'count': 0, 'files': []}
            input_files = input_data.get('files', [])
            input_count = input_data.get('count', 0)

            if input_files:
                input_list = dbc.ListGroup([
                    create_file_item(f['filename'], f['size_mb'], f['modified_at'])
                    for f in input_files
                ])
            else:
                input_list = html.P("Nenhum arquivo pendente", className="text-muted text-center my-4")

            input_badge = f"{input_count} arquivo(s)"

            return (
                status_msg,
                True,   # desabilitar interval
                False,  # reabilitar botão
                history_table,
                input_list,
                input_badge,
                True,   # abrir toast
                toast_msg,
                toast_icon
            )

        except Exception as e:
            logger.error(f"Erro no polling: {e}")
            raise PreventUpdate

    # ============================================================
    # CALLBACK 4: Refresh Manual
    # ============================================================
    @app.callback(
        [
            Output('list-files-input', 'children', allow_duplicate=True),
            Output('badge-count-input', 'children', allow_duplicate=True),
            Output('list-files-output', 'children', allow_duplicate=True),
            Output('badge-count-output', 'children', allow_duplicate=True),
            Output('history-table-container', 'children', allow_duplicate=True)
        ],
        [
            Input('btn-refresh-zpp', 'n_clicks'),
            Input('interval-zpp-refresh', 'n_intervals')
        ],
        prevent_initial_call=True
    )
    def refresh_data(n_clicks, n_intervals):
        """Refresh manual ou automático dos dados"""
        try:
            # Arquivos input
            input_response = requests.get(f"{ZPP_API_URL}/api/zpp/files/input", timeout=5)
            input_data = input_response.json() if input_response.ok else {'count': 0, 'files': []}
            input_files = input_data.get('files', [])
            input_count = input_data.get('count', 0)

            if input_files:
                input_list = dbc.ListGroup([
                    create_file_item(f['filename'], f['size_mb'], f['modified_at'])
                    for f in input_files
                ])
            else:
                input_list = html.P("Nenhum arquivo pendente", className="text-muted text-center my-4")

            # Arquivos output
            output_response = requests.get(f"{ZPP_API_URL}/api/zpp/files/output", timeout=5)
            output_data = output_response.json() if output_response.ok else {'count': 0, 'files': []}
            output_files = output_data.get('files', [])
            output_count = output_data.get('count', 0)

            if output_files:
                output_list = dbc.ListGroup([
                    create_file_item(f['filename'], f['size_mb'], f['modified_at'])
                    for f in output_files[:10]
                ])
            else:
                output_list = html.P("Nenhum arquivo processado", className="text-muted text-center my-4")

            # Histórico
            history_response = requests.get(f"{ZPP_API_URL}/api/zpp/history?limit=20", timeout=5)
            history_data = history_response.json() if history_response.ok else {'logs': []}
            history_table = create_history_table_component(history_data.get('logs', []))

            return (
                input_list, f"{input_count} arquivo(s)",
                output_list, f"{output_count} arquivo(s)",
                history_table
            )

        except Exception as e:
            logger.error(f"Erro no refresh: {e}")
            raise PreventUpdate

    # ============================================================
    # CALLBACK 5: Salvar Configuração
    # ============================================================
    @app.callback(
        [
            Output('config-save-status', 'children'),
            Output('store-zpp-config', 'data', allow_duplicate=True)
        ],
        Input('btn-save-config', 'n_clicks'),
        [
            State('switch-auto-process', 'value'),
            State('input-interval-minutes', 'value')
        ],
        prevent_initial_call=True
    )
    def save_config(n_clicks, auto_process, interval_minutes):
        """Salva configurações no serviço"""
        if not n_clicks:
            raise PreventUpdate

        try:
            response = requests.put(
                f"{ZPP_API_URL}/api/zpp/config",
                json={
                    "auto_process": auto_process,
                    "interval_minutes": interval_minutes,
                    "updated_by": "webapp_user"
                },
                timeout=5
            )

            if response.ok:
                return (
                    dbc.Alert(
                        [html.I(className="bi bi-check-circle me-2"), "Salvo!"],
                        color="success",
                        className="mb-0 py-1 px-2 small",
                        dismissable=True,
                        duration=3000
                    ),
                    response.json()
                )
            else:
                return (
                    dbc.Alert(
                        [html.I(className="bi bi-x-circle me-2"), "Erro ao salvar"],
                        color="danger",
                        className="mb-0 py-1 px-2 small",
                        dismissable=True
                    ),
                    no_update
                )

        except Exception as e:
            logger.error(f"Erro ao salvar config: {e}")
            return (
                dbc.Alert(
                    f"Erro: {str(e)}",
                    color="danger",
                    className="mb-0 py-1 px-2 small",
                    dismissable=True
                ),
                no_update
            )

    # ============================================================
    # CALLBACK 6: Toggle Painel de Configurações
    # ============================================================
    @app.callback(
        Output('collapse-config', 'is_open'),
        Input('collapse-config-button', 'n_clicks'),
        State('collapse-config', 'is_open')
    )
    def toggle_config_panel(n, is_open):
        """Toggle do painel de configurações"""
        if n:
            return not is_open
        return is_open

    # ============================================================
    # CALLBACK 7: Botão de Ajuda
    # ============================================================
    @app.callback(
        Output('toast-help-zpp', 'is_open'),
        Input('btn-help-zpp', 'n_clicks'),
        prevent_initial_call=True
    )
    def show_help(n):
        """Mostra toast de ajuda"""
        if n:
            return True
        raise PreventUpdate
