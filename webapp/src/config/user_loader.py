from src.app import app, server, login_manager
# Importa as funções de usuário do banco de dados
from src.database.connection import get_user_by_id
# --- Configuração do User Loader para Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    if user_id is None:
        return None
    # Adicionando prints para depuração
    print(f"--- DEBUG: Tentando carregar usuário com ID: {user_id} ---")
    user = get_user_by_id(user_id)
    if user:
        print(f"--- DEBUG: Usuário '{user.username}' (Nível {user.level}) carregado com sucesso da sessão. ---")
    else:
        print(f"--- DEBUG: Nenhum usuário encontrado para o ID: {user_id}. ---")
    return user