from src.app import app, server, login_manager
# Importa as funções de usuário do banco de dados
from src.database.connection import get_user_by_id
# --- Configuração do User Loader para Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    if user_id is None:
        return None
    # Adicionando prints para depuração
    user = get_user_by_id(user_id)
    if user:
    else:
    return user