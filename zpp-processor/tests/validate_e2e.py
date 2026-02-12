"""
Validação End-to-End do ZPP Processor
Testa todo o fluxo: API + MongoDB + Volumes
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

# Carregar variáveis de ambiente
load_dotenv()

# Configuração
API_URL = "http://localhost:5002"
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')
BASE_DATA_DIR = Path("/data")  # Dentro do container


class Validator:
    """Validador End-to-End"""

    def __init__(self):
        self.results = {}
        self.db = None

    def print_header(self, text):
        """Imprime cabeçalho"""
        print(f"\n{'='*80}")
        print(f"{text}")
        print(f"{'='*80}\n")

    def print_result(self, test_name, passed, details=""):
        """Imprime resultado"""
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")
        if details:
            print(f"       {details}")
        self.results[test_name] = passed

    def validate_mongodb_connection(self):
        """Valida conexão com MongoDB"""
        self.print_header("VALIDAÇÃO 1: Conexão MongoDB")

        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.server_info()
            self.db = client[DB_NAME]

            self.print_result(
                "Conexão MongoDB",
                True,
                f"Conectado a: {DB_NAME}"
            )
            return True

        except Exception as e:
            self.print_result("Conexão MongoDB", False, f"Erro: {str(e)}")
            return False

    def validate_mongodb_collections(self):
        """Valida collections MongoDB"""
        self.print_header("VALIDAÇÃO 2: Collections MongoDB")

        if not self.db:
            self.print_result("Collections MongoDB", False, "MongoDB não conectado")
            return False

        try:
            collections = self.db.list_collection_names()

            required = ['zpp_processing_logs', 'zpp_processor_config']
            all_exist = all(col in collections for col in required)

            details = []
            for col in required:
                exists = col in collections
                status = "✓" if exists else "✗"
                count = self.db[col].count_documents({}) if exists else 0
                details.append(f"{status} {col} ({count} docs)")

            self.print_result(
                "Collections MongoDB",
                all_exist,
                "\n       ".join(details)
            )

            return all_exist

        except Exception as e:
            self.print_result("Collections MongoDB", False, f"Erro: {str(e)}")
            return False

    def validate_mongodb_indexes(self):
        """Valida índices MongoDB"""
        self.print_header("VALIDAÇÃO 3: Índices MongoDB")

        if not self.db:
            self.print_result("Índices MongoDB", False, "MongoDB não conectado")
            return False

        try:
            collection = self.db['zpp_processing_logs']
            indexes = list(collection.list_indexes())

            expected = [
                'idx_job_id_unique',
                'idx_started_at_desc',
                'idx_status_started',
                'idx_trigger_started'
            ]

            found = {idx['name']: idx for idx in indexes}
            all_exist = all(idx_name in found for idx_name in expected)

            details = []
            for idx_name in expected:
                exists = idx_name in found
                status = "✓" if exists else "✗"
                details.append(f"{status} {idx_name}")

            self.print_result(
                "Índices MongoDB",
                all_exist,
                "\n       ".join(details)
            )

            return all_exist

        except Exception as e:
            self.print_result("Índices MongoDB", False, f"Erro: {str(e)}")
            return False

    def validate_api_health(self):
        """Valida health da API"""
        self.print_header("VALIDAÇÃO 4: API Health")

        try:
            response = requests.get(f"{API_URL}/api/health", timeout=5)
            data = response.json()

            passed = (
                response.status_code == 200 and
                data.get("status") == "healthy" and
                data.get("mongodb") == "connected"
            )

            self.print_result(
                "API Health",
                passed,
                f"Status: {data.get('status')}, MongoDB: {data.get('mongodb')}, Volumes: {data.get('volumes')}"
            )

            return passed

        except Exception as e:
            self.print_result("API Health", False, f"Erro: {str(e)}")
            return False

    def validate_api_endpoints(self):
        """Valida endpoints da API"""
        self.print_header("VALIDAÇÃO 5: Endpoints da API")

        endpoints = [
            ("GET", "/api/health"),
            ("GET", "/api/zpp/config"),
            ("GET", "/api/zpp/files/input"),
            ("GET", "/api/zpp/files/output"),
            ("GET", "/api/zpp/history")
        ]

        all_ok = True

        for method, endpoint in endpoints:
            try:
                if method == "GET":
                    response = requests.get(f"{API_URL}{endpoint}", timeout=5)
                else:
                    response = requests.post(f"{API_URL}{endpoint}", timeout=5)

                passed = response.status_code in [200, 202]
                all_ok = all_ok and passed

                self.print_result(
                    f"{method} {endpoint}",
                    passed,
                    f"Status: {response.status_code}"
                )

            except Exception as e:
                self.print_result(f"{method} {endpoint}", False, f"Erro: {str(e)}")
                all_ok = False

        return all_ok

    def validate_configuration(self):
        """Valida configuração do serviço"""
        self.print_header("VALIDAÇÃO 6: Configuração do Serviço")

        try:
            # Via API
            api_response = requests.get(f"{API_URL}/api/zpp/config", timeout=5)
            api_config = api_response.json()

            # Via MongoDB
            db_config = self.db['zpp_processor_config'].find_one({'_id': 'global'})

            api_ok = all(k in api_config for k in ['auto_process', 'interval_minutes'])
            db_ok = db_config is not None

            self.print_result(
                "Configuração via API",
                api_ok,
                f"Auto-process: {api_config.get('auto_process')}, Intervalo: {api_config.get('interval_minutes')}min"
            )

            self.print_result(
                "Configuração via MongoDB",
                db_ok,
                f"Documento encontrado: {db_ok}"
            )

            return api_ok and db_ok

        except Exception as e:
            self.print_result("Configuração", False, f"Erro: {str(e)}")
            return False

    def validate_processing_logs(self):
        """Valida logs de processamento"""
        self.print_header("VALIDAÇÃO 7: Logs de Processamento")

        if not self.db:
            self.print_result("Logs de Processamento", False, "MongoDB não conectado")
            return False

        try:
            collection = self.db['zpp_processing_logs']
            total_logs = collection.count_documents({})

            # Estatísticas
            success_count = collection.count_documents({'status': 'success'})
            failed_count = collection.count_documents({'status': 'failed'})
            running_count = collection.count_documents({'status': 'running'})

            self.print_result(
                "Logs de Processamento",
                True,
                f"Total: {total_logs}, Sucesso: {success_count}, Falhas: {failed_count}, Rodando: {running_count}"
            )

            # Último log
            last_log = collection.find_one(sort=[('started_at', -1)])
            if last_log:
                print(f"       Último: {last_log.get('job_id', 'N/A')[:8]}... | {last_log.get('status')} | {last_log.get('trigger_type')}")

            return True

        except Exception as e:
            self.print_result("Logs de Processamento", False, f"Erro: {str(e)}")
            return False

    def run_all_validations(self):
        """Executa todas as validações"""
        print(f"\n{'='*80}")
        print(f"ZPP PROCESSOR - VALIDAÇÃO END-TO-END")
        print(f"{'='*80}")
        print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"API URL: {API_URL}")
        print(f"MongoDB: {DB_NAME}")

        # Executar validações
        self.validate_mongodb_connection()
        self.validate_mongodb_collections()
        self.validate_mongodb_indexes()
        self.validate_api_health()
        self.validate_api_endpoints()
        self.validate_configuration()
        self.validate_processing_logs()

        # Resumo
        self.print_header("RESUMO DAS VALIDAÇÕES")

        passed = sum(1 for r in self.results.values() if r)
        total = len(self.results)

        for name, result in self.results.items():
            status = "✓" if result else "✗"
            print(f"{status} {name}")

        print(f"\nTotal: {passed}/{total} validações passaram")

        if passed == total:
            print(f"\n✓ TODAS AS VALIDAÇÕES PASSARAM")
            print(f"\nO sistema está funcionando corretamente!\n")
            return 0
        else:
            print(f"\n✗ {total - passed} VALIDAÇÃO(ÕES) FALHARAM")
            print(f"\nVerifique os erros acima e corrija antes de usar em produção.\n")
            return 1


def main():
    """Função principal"""
    if not MONGO_URI or not DB_NAME:
        print("\n✗ ERRO: Variáveis MONGO_URI e DB_NAME não configuradas")
        print("Configure no arquivo .env antes de executar\n")
        return 1

    validator = Validator()
    return validator.run_all_validations()


if __name__ == '__main__':
    exit(main())
