# pages/register.py

from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
from dash_bootstrap_templates import template_from_url
import dash

from src.app import app
from src.database.connection import get_user_by_username, get_user_by_email, save_user

from src.config.theme_config import URL_THEME_MINTY

def render_layout():
    card_style = {
        'width': '450px',  # ← Aumentado de 400px para 450px (mais espaço)
        'padding': '25px',
        'margin': '50px auto',
        'background-color': 'rgba(255, 255, 255, 0.1)',
        'border': '1px solid rgba(255, 255, 255, 0.2)',
        'border-radius': '15px',
        'box-shadow': '0 4px 30px rgba(0, 0, 0, 0.1)',
        'backdrop-filter': 'blur(5px)',
        '-webkit-backdrop-filter': 'blur(5px)',
    }

    # ========================================
    # OPÇÕES DE DEPARTAMENTOS
    # ========================================
    departamento_options = [
        {"label": "📊 Produção", "value": "producao"},
        {"label": "🔧 Manutenção", "value": "manutencao"},
        {"label": "✓ Qualidade", "value": "qualidade"},
        {"label": "🌿 Meio Ambiente", "value": "meio_ambiente"},
        {"label": "🛡️ Segurança", "value": "seguranca"},
        {"label": "🛠️ Engenharias", "value": "engenharias"},
    ]

    register_layout = dbc.Container([
        dcc.Location(id='register-url', refresh=True),
        dcc.Store(id='theme-store', storage_type='local'),
        dbc.Row(
            dbc.Col(
                dbc.Card([
                    html.Div(
                        [
                            html.Img(src="/assets/LogoAMG.png", style={"height": "40px"}),
                            # ThemeSwitchAIO removido
                        ],
                        className="d-flex justify-content-between align-items-center"
                    ),
                    html.Hr(className="my-4"),
                    
                    html.H2("Criar Conta", className="text-center mb-4"),
                    
                    # ========================================
                    # FORMULÁRIO DE REGISTRO
                    # ========================================
                    dbc.Input(
                        id="user_register", 
                        placeholder="Usuário", 
                        type="text", 
                        className="mb-3"
                    ),
                    
                    dbc.Input(
                        id="email_register", 
                        placeholder="E-mail", 
                        type="email", 
                        className="mb-3"
                    ),
                    
                    dbc.Input(
                        id="pwd_register", 
                        placeholder="Senha", 
                        type="password", 
                        className="mb-3"
                    ),
                    
                    # ========================================
                    # DROPDOWN DE DEPARTAMENTOS (NOVO!)
                    # ========================================
                    html.Label("Departamento:", className="mb-1", style={"fontSize": "0.9rem"}),
                    dcc.Dropdown(
                        id="departamento_register",
                        options=departamento_options,
                        placeholder="Selecione o departamento",
                        className="mb-3",
                        clearable=False,
                        searchable=False,
                        style={
                            "fontSize": "0.9rem"
                        }
                    ),
                    
                    # ========================================
                    # NÍVEL DE ACESSO
                    # ========================================
                    html.Label("Nível de Acesso:", className="mb-1", style={"fontSize": "0.9rem"}),
                    dcc.Dropdown(
                        id="level_register",
                        options=[
                            {"label": "Nível 1 - Visualizador", "value": 1},
                            {"label": "Nível 2 - Operador", "value": 2},
                            {"label": "Nível 3 - Administrador", "value": 3},
                        ],
                        placeholder="Selecione o nível",
                        className="mb-3",
                        clearable=False,
                        searchable=False,
                        style={
                            "fontSize": "0.9rem"
                        }
                    ),
                    
                    dbc.Button(
                        "Registrar", 
                        id='register-button', 
                        color="success", 
                        className="w-100 mt-2"
                    ),
                    
                    html.Div(
                        id="register-error-message", 
                        className="text-danger text-center mt-3"
                    ),
                    
                    # ========================================
                    # LINK PARA LOGIN (REMOVIDO - conforme pedido)
                    # ========================================
                    # html.Div([
                    #     dcc.Link("Já tem uma conta? Faça login", href="/login", className="text-muted"),
                    # ], className="text-center mt-3"),

                    html.Hr(className="mt-4"),
                    html.Div(
                        [
                            html.Span("Powered by:", style={'fontSize': '0.8rem', 'color': '#aaa', 'marginRight': '10px'}),
                            html.Img(src="/assets/LogoAMG.png", style={"height": "25px"})
                        ],
                        className="d-flex justify-content-end align-items-center"
                    )

                ], body=True, style=card_style),
                width=12
            )
        )
    ], fluid=True, className=template_from_url(URL_THEME_MINTY), id="register-container",
       style={"height": "100vh", "display": "flex", "align-items": "center", "justify-content": "center"})
    
    return register_layout


# ========================================
# CALLBACK DE REGISTRO ATUALIZADO
# ========================================
@app.callback(
    [Output('register-url', 'pathname'),
     Output('register-error-message', 'children')],
    Input('register-button', 'n_clicks'),
    [State('user_register', 'value'),
     State('pwd_register', 'value'),
     State('email_register', 'value'),
     State('departamento_register', 'value'),  # ← NOVO
     State('level_register', 'value')],
    prevent_initial_call=True
)
def successful_register(n_clicks, username, password, email, departamento, level):
    """
    Callback para processar o registro de novo usuário.
    
    IMPORTANTE: A função save_user() precisa ser atualizada para aceitar o parâmetro 'departamento'.
    Exemplo: save_user(username, email, password, level, departamento)
    """
    
    # Validação: todos os campos obrigatórios
    if not all([username, password, email, departamento, level]):
        return dash.no_update, "Todos os campos são obrigatórios."
    
    # Validação: username único
    if get_user_by_username(username):
        return dash.no_update, "Este nome de usuário já existe."
    
    # Validação: email único
    if get_user_by_email(email):
        return dash.no_update, "Este e-mail já está em uso."
    
    # ========================================
    # SALVAR USUÁRIO COM DEPARTAMENTO
    # ========================================
    # NOTA: Você precisa atualizar a função save_user() em src/database/connection.py
    # para aceitar o parâmetro 'departamento' e salvá-lo no banco de dados.
    #
    # Exemplo de atualização necessária:
    # def save_user(username, email, password, level, departamento):
    #     hashed_pwd = generate_password_hash(password)
    #     user_data = {
    #         "username": username,
    #         "email": email,
    #         "password": hashed_pwd,
    #         "level": level,
    #         "departamento": departamento,  # ← ADICIONAR
    #         "created_at": datetime.now()
    #     }
    #     users_collection.insert_one(user_data)
    
    # Por enquanto, mantendo compatibilidade com função antiga:
    try:
        # Tente salvar com departamento (se a função já foi atualizada)
        save_user(username, email, password, level, departamento)
    except TypeError:
        # Fallback: salve sem departamento (função antiga)
        # TODO: Atualizar save_user() para incluir departamento
        save_user(username, email, password, level)
        print(f"AVISO: Departamento '{departamento}' não foi salvo. Atualize a função save_user().")
    
    return '/login', "Registro bem-sucedido! Faça o login."