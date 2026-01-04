# src/database/connection.py

import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError

from bson import ObjectId
from werkzeug.security import generate_password_hash


# Variáveis globais para cliente e banco de dados, para reutilizar a conexão
client = None
db = None

def get_mongo_connection(collection_name=None):
    global client, db

    if client is None:
        mongo_uri = os.getenv('MONGO_URI')
        db_name = os.getenv('DB_NAME')

        if not mongo_uri or not db_name:
            print("Erro: As variáveis de ambiente MONGO_URI e DB_NAME devem ser definidas.")
            raise ConfigurationError("MONGO_URI e DB_NAME não foram encontradas no ambiente.")

        try:
            print(f"Tentando conectar ao MongoDB (URI: {mongo_uri}, DB: {db_name})...")
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000) # Mantemos apenas um timeout generoso.
            
            client.admin.command('ping')
            db = client[db_name]
            print(f"Conexão com o MongoDB (DB: '{db_name}') estabelecida com sucesso!")

        except ConnectionFailure as e:
            print(f"Falha na conexão com o MongoDB: {e}")
            client = None
            db = None
            raise ConnectionError(f"Não foi possível conectar ao MongoDB: {e}")
        except Exception as e:
            print(f"Um erro inesperado ocorreu durante a conexão com o MongoDB: {e}")
            client = None
            db = None
            raise ConnectionError(f"Erro inesperado na conexão: {e}")

    if db is not None:
        return db[collection_name] if collection_name else db
    
    raise ConnectionError("A conexão com o MongoDB não está disponível.")

# --- Lógica de Usuários para Flask-Login ---
# O restante do arquivo permanece o mesmo, mas agora depende da função acima.

class User:
    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.username = user_data["username"]
        self.email = user_data.get("email")
        self.password = user_data["password"]
        self.level = int(user_data.get("level", 1))
        self.perfil = user_data.get("perfil", "manutencao")

    def is_authenticated(self): return True
    def is_active(self): return True
    def is_anonymous(self): return False
    def get_id(self): return self.id

def get_user_by_id(user_id):
    if not ObjectId.is_valid(user_id):
        return None
    try:
        user_collection = get_mongo_connection(collection_name="usuarios")
        user_data = user_collection.find_one({"_id": ObjectId(user_id)})
        return User(user_data) if user_data else None
    except ConnectionError:
        return None

def get_user_by_username(username):
    try:
        user_collection = get_mongo_connection(collection_name="usuarios")
        user_data = user_collection.find_one({"username": username})
        return User(user_data) if user_data else None
    except ConnectionError:
        return None

def get_user_by_email(email):
    try:
        user_collection = get_mongo_connection(collection_name="usuarios")
        user_data = user_collection.find_one({"email": email})
        return User(user_data) if user_data else None
    except ConnectionError:
        return None

def save_user(username, email, password, level):
    try:
        user_collection = get_mongo_connection(collection_name="usuarios")
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        user_collection.insert_one({
            "username": username,
            "email": email,
            "password": hashed_password,
            "level": int(level)
        })
        return True
    except ConnectionError:
        return False

