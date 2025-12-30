# pages/reports.py

from dash import html
import dash_bootstrap_components as dbc
from dash import dcc
from src.components.pagereport01 import folha1_content
from src.components.pagereport02 import folha2_content

# --- Layout da página com botão (para a navegação normal do app) ---
# Este layout permanece IGUAL ao que você já tem funcionando.
# Ele contém o botão para abrir a nova aba de impressão.'''
layout = dbc.Col([
    dbc.Row([

    
            html.H3("Página de Relatórios Personalizáveis", className="text-center my-5 display-6 text-primary"),
            html.P(
                "Esta página simula um relatório. Você pode abri-la em uma nova aba e usar as "
                "funções de impressão do seu navegador para gerar um PDF ou imprimir diretamente.",
                className="lead text-center mb-4 text-muted"
            ),

            # Botão para abrir a página de impressão em outra aba
            dcc.Link(
                dbc.Button(
                    "Gerar Relatório",
                    id="open-for-print-button",
                    color="light",
                    size="md",
                    class_name="mt-2 mb-2 ms-auto me-3 d-inline-block text-info border-info",
                ),
                href="/reports-print",  # <-- Redireciona para o layout otimizado para impressão
            ),
            html.Hr(className="my-5"),

            ]),
       
 

    # Conteúdo da impressão (apenas o main-print-container será usado na CSS @media print)
        dbc.Row([
            # Container com ID para impressão
            dbc.Col([
                
                    # Conteúdo da folha 1
                    dbc.Card([
                        dbc.CardBody([
                            folha1_content  # Inserir o conteúdo dinâmico da folha 1
                        ]),
                    ], className="mb-5  border-primary", id="main-print-container"),
                
            ], sm=12)
        ]),
         
 ])


print_layout = html.Div([ # Este é o container principal para a impressão
    html.Div( # Primeira "página"
        className="page",
        children=[
            html.Div(
                className="subpage",
                children=[
                    folha1_content # folha1_content já deve conter os componentes ajustados
                ]
            )
        ]
    ),
    # Se você tiver uma segunda folha, adicione-a aqui da mesma forma
    # html.Div( # Segunda "página" (exemplo)
    #     className="page",
    #     children=[
    #         html.Div(
    #             className="subpage",
    #             children=[
    #                 folha2_content
    #             ]
    #         )
    #     ]
    # ),
],
id="reports-print-page-wrapper" # Mantenha o ID para o wrapper geral
)