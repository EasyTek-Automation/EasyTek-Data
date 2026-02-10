# src/database/connection.py

import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError, ServerSelectionTimeoutError

from bson import ObjectId
from werkzeug.security import generate_password_hash


# Variáveis globais para cliente e banco de dados, para reutilizar a conexão
client = None
db = None
MONGO_AVAILABLE = False  # Flag para rastrear se o MongoDB está disponível
LAST_ERROR = None  # Armazena a última mensagem de erro


def check_mongo_health():
    """
    Verifica se o MongoDB está acessível.

    Returns:
        bool: True se o MongoDB está disponível, False caso contrário
    """
    global MONGO_AVAILABLE, LAST_ERROR

    if client is None:
        return False

    try:
        client.admin.command('ping')
        MONGO_AVAILABLE = True
        LAST_ERROR = None
        return True
    except Exception as e:
        MONGO_AVAILABLE = False
        LAST_ERROR = str(e)
        return False


def get_mongo_connection(collection_name=None, silent=False):
    """
    Obtém conexão com o MongoDB.

    Args:
        collection_name (str, optional): Nome da coleção a acessar
        silent (bool): Se True, não imprime mensagens (útil para health checks)

    Returns:
        Collection/Database: Objeto de coleção ou banco, ou None se não conectado
    """
    global client, db, MONGO_AVAILABLE, LAST_ERROR

    if client is None:
        mongo_uri = os.getenv('MONGO_URI')
        db_name = os.getenv('DB_NAME')

        if not mongo_uri or not db_name:
            error_msg = "As variáveis de ambiente MONGO_URI e DB_NAME devem ser definidas."
            if not silent:
            MONGO_AVAILABLE = False
            LAST_ERROR = error_msg
            return None

        try:
            if not silent:

            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
            client.admin.command('ping')
            db = client[db_name]

            MONGO_AVAILABLE = True
            LAST_ERROR = None

            if not silent:

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            error_msg = f"Falha na conexão: {e}"
            if not silent:
            client = None
            db = None
            MONGO_AVAILABLE = False
            LAST_ERROR = error_msg
            return None

        except Exception as e:
            error_msg = f"Erro inesperado: {e}"
            if not silent:
            client = None
            db = None
            MONGO_AVAILABLE = False
            LAST_ERROR = error_msg
            return None

    # Verifica se a conexão ainda está válida
    if not check_mongo_health():
        if not silent:
        client = None
        db = None
        return get_mongo_connection(collection_name, silent)

    if db is not None:
        return db[collection_name] if collection_name else db

    return None


def reconnect_mongodb():
    """
    Força reconexão ao MongoDB.

    Returns:
        bool: True se reconectou com sucesso, False caso contrário
    """
    global client, db

    client = None
    db = None

    result = get_mongo_connection()
    return result is not None


def get_connection_status():
    """
    Retorna o status atual da conexão MongoDB.

    Returns:
        dict: Dicionário com 'available' (bool) e 'error' (str ou None)
    """
    return {
        "available": MONGO_AVAILABLE,
        "error": LAST_ERROR
    }


# --- Lógica de Usuários para Flask-Login ---

class User:
    """
    Classe de usuário para Flask-Login.
    
    Atributos:
        id (str): ID único do usuário no MongoDB
        username (str): Nome de usuário
        email (str): E-mail do usuário
        password (str): Senha hasheada
        level (int): Nível de acesso vertical (1=básico, 2=avançado, 3=admin)
        perfil (str): Perfil de acesso horizontal (manutencao, qualidade, producao, etc.)
    """
    
    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.username = user_data["username"]
        self.email = user_data.get("email")
        self.password = user_data["password"]
        self.level = int(user_data.get("level", 1))
        # NOVO: Campo perfil para controle de acesso horizontal
        self.perfil = user_data.get("perfil", "manutencao")  # Default: manutencao

    def is_authenticated(self): 
        return True
    
    def is_active(self): 
        return True
    
    def is_anonymous(self): 
        return False
    
    def get_id(self): 
        return self.id
    
    def __repr__(self):
        return f"<User {self.username} (level={self.level}, perfil={self.perfil})>"


def get_user_by_id(user_id):
    """
    Busca usuário por ID no MongoDB.

    Returns:
        User ou None: Objeto User se encontrado, None se não encontrado ou se MongoDB estiver offline
    """
    if not ObjectId.is_valid(user_id):
        return None
    try:
        user_collection = get_mongo_connection(collection_name="usuarios")

        # ⚠️ Verificar se conexão está disponível
        if user_collection is None:
            return None

        user_data = user_collection.find_one({"_id": ObjectId(user_id)})
        return User(user_data) if user_data else None
    except Exception as e:
        return None


def get_user_by_username(username):
    """
    Busca usuário por username no MongoDB.

    Returns:
        User ou None: Objeto User se encontrado, None se não encontrado ou se MongoDB estiver offline
    """
    try:
        user_collection = get_mongo_connection(collection_name="usuarios")

        # ⚠️ Verificar se conexão está disponível
        if user_collection is None:
            return None

        user_data = user_collection.find_one({"username": username})
        return User(user_data) if user_data else None
    except Exception as e:
        return None


def get_user_by_email(email):
    """
    Busca usuário por email no MongoDB.

    Returns:
        User ou None: Objeto User se encontrado, None se não encontrado ou se MongoDB estiver offline
    """
    try:
        user_collection = get_mongo_connection(collection_name="usuarios")

        # ⚠️ Verificar se conexão está disponível
        if user_collection is None:
            return None

        user_data = user_collection.find_one({"email": email})
        return User(user_data) if user_data else None
    except Exception as e:
        return None


def save_user(username, email, password, level, perfil="manutencao"):
    """
    Salva um novo usuário no banco de dados.

    Args:
        username (str): Nome de usuário
        email (str): E-mail
        password (str): Senha (será hasheada)
        level (int): Nível de acesso (1, 2 ou 3)
        perfil (str): Perfil de acesso horizontal (default: manutencao)

    Returns:
        bool: True se salvou com sucesso, False caso contrário
    """
    try:
        user_collection = get_mongo_connection(collection_name="usuarios")

        # ⚠️ Verificar se conexão está disponível
        if user_collection is None:
            return False

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        user_collection.insert_one({
            "username": username,
            "email": email,
            "password": hashed_password,
            "level": int(level),
            "perfil": perfil  # NOVO: Campo perfil
        })
        return True
    except Exception as e:
        return False