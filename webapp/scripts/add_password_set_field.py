"""
Script para adicionar campo password_set aos usuários existentes.

Executa UMA VEZ para migrar usuários antigos.

Uso:
    python webapp/scripts/add_password_set_field.py
"""
import sys
from pathlib import Path

# Adicionar caminho do projeto
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from webapp.src.database.connection import get_mongo_connection
from werkzeug.security import check_password_hash


def migrar_usuarios():
    """Adiciona campo password_set aos usuários existentes."""
    print("\n" + "="*70)
    print("🔧 MIGRAÇÃO: Adicionar campo password_set")
    print("="*70)

    try:
        usuarios = get_mongo_connection("usuarios")

        # Contar usuários sem o campo
        sem_campo = usuarios.count_documents({"password_set": {"$exists": False}})

        if sem_campo == 0:
            print("\n✅ Todos os usuários já têm o campo password_set!")
            print("   Nada a fazer.")
            return 0

        print(f"\n📊 Encontrados {sem_campo} usuários sem o campo password_set")
        print("   Analisando senhas...")

        # Buscar usuários sem o campo
        users_cursor = usuarios.find({"password_set": {"$exists": False}})

        atualizados = 0
        erros = 0

        for user in users_cursor:
            username = user.get("username", "N/A")
            password_hash = user.get("password", "")

            try:
                # Verificar se senha está em branco (lento, mas é UMA VEZ só)
                is_blank = check_password_hash(password_hash, "")
                password_set = not is_blank  # Se não está em branco, foi definida

                # Atualizar usuário
                usuarios.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"password_set": password_set}}
                )

                status = "🔶 senha temporária" if not password_set else "🟢 senha definida"
                print(f"   ✓ {username:20} → password_set: {password_set} ({status})")
                atualizados += 1

            except Exception as e:
                print(f"   ✗ {username:20} → ERRO: {e}")
                erros += 1

        print("\n" + "="*70)
        print(f"✅ MIGRAÇÃO CONCLUÍDA!")
        print(f"   Atualizados: {atualizados}")
        if erros > 0:
            print(f"   ⚠️  Erros: {erros}")
        print("="*70)

        return 0

    except Exception as e:
        print(f"\n❌ ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(migrar_usuarios())
