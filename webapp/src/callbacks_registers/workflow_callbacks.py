"""
Callbacks para o Dashboard de Pendências (Workflow).

Implementa:
- Toggle do painel de filtros
- Expansão/colapso de linhas com pattern-matching
- Aplicação de filtros
- Refresh de dados
"""

import pandas as pd
from dash import Input, Output, State, MATCH, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from src.pages.workflow.dashboard import (
    carregar_dados_csv,
    criar_tabela_pendencias,
    criar_cards_kpi,
    criar_timeline_historico
)


# ======================================================================================
# HELPERS
# ======================================================================================

def criar_conteudo_historico(pendencia_id, df_historico):
    """
    Cria o conteúdo do histórico para uma pendência específica.

    Args:
        pendencia_id: ID da pendência (ex: PEND-001)
        df_historico: DataFrame com todo o histórico

    Returns:
        html.Div: Timeline do histórico
    """
    # Filtrar histórico da pendência
    historico_pendencia = df_historico[df_historico['pendencia_id'] == pendencia_id].copy()

    # Ordenar por data
    historico_pendencia = historico_pendencia.sort_values('data')

    # Converter para lista de dicts
    historico_items = []
    for _, row in historico_pendencia.iterrows():
        historico_items.append({
            'descricao': row['descricao'],
            'responsavel': row['responsavel'],
            'data': row['data'].strftime("%d/%m/%Y %H:%M")
        })

    return criar_timeline_historico(historico_items)


def aplicar_filtros_dataframe(df, responsavel, status_list, busca):
    """
    Aplica filtros ao DataFrame de pendências.

    Args:
        df: DataFrame original
        responsavel: Responsável selecionado ou "todos"
        status_list: Lista de status selecionados ou None
        busca: Texto de busca ou None

    Returns:
        pd.DataFrame: DataFrame filtrado
    """
    df_filtrado = df.copy()

    # Filtro por responsável
    if responsavel and responsavel != "todos":
        df_filtrado = df_filtrado[df_filtrado['responsavel'] == responsavel]

    # Filtro por status (multi-select)
    if status_list and len(status_list) > 0:
        df_filtrado = df_filtrado[df_filtrado['status'].isin(status_list)]

    # Filtro por busca (ID ou descrição)
    if busca and busca.strip():
        busca_lower = busca.lower()
        mask = (
            df_filtrado['id'].str.lower().str.contains(busca_lower, na=False) |
            df_filtrado['descricao'].str.lower().str.contains(busca_lower, na=False)
        )
        df_filtrado = df_filtrado[mask]

    return df_filtrado


# ======================================================================================
# REGISTRO DE CALLBACKS
# ======================================================================================

def register_workflow_callbacks(app):
    """
    Registra todos os callbacks do módulo Workflow.

    Args:
        app: Instância do Dash app
    """

    # ==================================================================================
    # CALLBACK 1: Toggle do painel de filtros
    # ==================================================================================
    @app.callback(
        Output("collapse-filtros", "is_open"),
        Input("btn-toggle-filtros", "n_clicks"),
        State("collapse-filtros", "is_open"),
        prevent_initial_call=True
    )
    def toggle_filtros(n_clicks, is_open):
        """Toggle do painel de filtros."""
        if n_clicks:
            return not is_open
        return is_open


    # ==================================================================================
    # CALLBACK 2: Expansão/Colapso de linha individual (Pattern-Matching)
    # ==================================================================================
    @app.callback(
        Output({"type": "collapse-historico", "index": MATCH}, "is_open"),
        Output({"type": "chevron-icon", "index": MATCH}, "className"),
        Output({"type": "historico-content", "index": MATCH}, "children"),
        Input({"type": "btn-expand", "index": MATCH}, "n_clicks"),
        State({"type": "collapse-historico", "index": MATCH}, "is_open"),
        State("store-pendencias", "data"),
        State("store-historico", "data"),
        prevent_initial_call=True
    )
    def toggle_linha_historico(n_clicks, is_open, pendencias_data, historico_data):
        """
        Expande/colapsa uma linha individual e carrega o histórico.

        Usa pattern-matching (MATCH) para afetar apenas a linha clicada.
        """
        if not n_clicks:
            raise PreventUpdate

        # Converter dados para DataFrames
        df_pendencias = pd.DataFrame(pendencias_data)
        df_historico = pd.DataFrame(historico_data)

        # Converter datas (usar format='mixed' para suportar timestamps com microsegundos)
        if not df_historico.empty:
            df_historico['data'] = pd.to_datetime(df_historico['data'], format='mixed')

        # Obter o índice da linha clicada (extraído do callback context)
        from dash import callback_context
        triggered_id = callback_context.triggered[0]['prop_id']

        # Extrair o index do ID dinâmico
        import json
        id_dict = json.loads(triggered_id.split('.')[0])
        index = id_dict['index']

        # Obter ID da pendência
        if index >= len(df_pendencias):
            raise PreventUpdate

        pendencia_id = df_pendencias.iloc[index]['id']

        # Alternar estado
        new_is_open = not is_open

        # Rotacionar chevron
        if new_is_open:
            chevron_class = "fas fa-chevron-down"
        else:
            chevron_class = "fas fa-chevron-right"

        # Carregar histórico apenas se estiver abrindo
        if new_is_open:
            conteudo_historico = criar_conteudo_historico(pendencia_id, df_historico)
        else:
            conteudo_historico = html.Div()

        return new_is_open, chevron_class, conteudo_historico


    # ==================================================================================
    # CALLBACK 3: Aplicar filtros
    # ==================================================================================
    @app.callback(
        Output("container-tabela", "children"),
        Output("store-pendencias", "data"),
        Output("collapse-filtros", "is_open", allow_duplicate=True),
        Input("btn-aplicar-filtros", "n_clicks"),
        State("filtro-responsavel", "value"),
        State("filtro-status", "value"),
        State("filtro-busca", "value"),
        prevent_initial_call=True
    )
    def aplicar_filtros(n_clicks, responsavel, status_list, busca):
        """
        Aplica os filtros selecionados e reconstrói a tabela.
        """
        if not n_clicks:
            raise PreventUpdate

        # Carregar dados originais
        df_pendencias, _ = carregar_dados_csv()

        if df_pendencias is None or df_pendencias.empty:
            return html.Div("Erro ao carregar dados.", className="text-danger"), [], False

        # Aplicar filtros
        df_filtrado = aplicar_filtros_dataframe(df_pendencias, responsavel, status_list, busca)

        # Reconstruir tabela
        nova_tabela = criar_tabela_pendencias(df_filtrado)

        # Fechar painel de filtros após aplicar
        return nova_tabela, df_filtrado.to_dict('records'), False


    # ==================================================================================
    # CALLBACK 4: Refresh de dados
    # ==================================================================================
    @app.callback(
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data"),
        Input("btn-refresh", "n_clicks"),
        prevent_initial_call=True
    )
    def refresh_dados(n_clicks):
        """
        Recarrega os dados dos CSVs e reconstrói a tabela.
        """
        if not n_clicks:
            raise PreventUpdate

        # Recarregar CSVs
        df_pendencias, df_historico = carregar_dados_csv()

        if df_pendencias is None or df_historico is None:
            return html.Div("Erro ao carregar dados.", className="text-danger"), [], []

        # Reconstruir tabela
        nova_tabela = criar_tabela_pendencias(df_pendencias)

        return (
            nova_tabela,
            df_pendencias.to_dict('records'),
            df_historico.to_dict('records')
        )
