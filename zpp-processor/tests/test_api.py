"""
Testes automatizados da API do ZPP Processor
Testa todos os 8 endpoints REST
"""
import requests
import time
import sys
from datetime import datetime

# Configuração
BASE_URL = "http://localhost:5002"
TIMEOUT = 10


class Colors:
    """Cores ANSI para output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text):
    """Imprime cabeçalho de seção"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")


def print_test(test_name, passed, details=""):
    """Imprime resultado de teste"""
    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"{status} - {test_name}")
    if details:
        print(f"       {details}")


def test_health_check():
    """Teste 1: Health check"""
    print_header("TESTE 1: Health Check")

    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=TIMEOUT)
        data = response.json()

        passed = (
            response.status_code == 200 and
            data.get("status") == "healthy" and
            data.get("mongodb") == "connected"
        )

        print_test(
            "Health Check",
            passed,
            f"Status: {data.get('status')}, MongoDB: {data.get('mongodb')}"
        )

        return passed

    except Exception as e:
        print_test("Health Check", False, f"Erro: {str(e)}")
        return False


def test_get_config():
    """Teste 2: Obter configuração"""
    print_header("TESTE 2: Obter Configuração")

    try:
        response = requests.get(f"{BASE_URL}/api/zpp/config", timeout=TIMEOUT)
        data = response.json()

        passed = (
            response.status_code == 200 and
            "auto_process" in data and
            "interval_minutes" in data
        )

        print_test(
            "GET /api/zpp/config",
            passed,
            f"Auto-process: {data.get('auto_process')}, Interval: {data.get('interval_minutes')}min"
        )

        return passed, data

    except Exception as e:
        print_test("GET /api/zpp/config", False, f"Erro: {str(e)}")
        return False, {}


def test_update_config(original_config):
    """Teste 3: Atualizar configuração"""
    print_header("TESTE 3: Atualizar Configuração")

    try:
        # Atualizar para valores de teste
        test_config = {
            "auto_process": False,
            "interval_minutes": 120,
            "updated_by": "test_script"
        }

        response = requests.put(
            f"{BASE_URL}/api/zpp/config",
            json=test_config,
            timeout=TIMEOUT
        )

        passed = response.status_code == 200

        print_test(
            "PUT /api/zpp/config",
            passed,
            f"Configuração atualizada para teste"
        )

        # Restaurar configuração original
        if passed and original_config:
            restore_response = requests.put(
                f"{BASE_URL}/api/zpp/config",
                json={
                    "auto_process": original_config.get("auto_process", True),
                    "interval_minutes": original_config.get("interval_minutes", 60),
                    "updated_by": "test_script_restore"
                },
                timeout=TIMEOUT
            )
            print_test(
                "Restaurar configuração original",
                restore_response.status_code == 200,
                "Configuração restaurada"
            )

        return passed

    except Exception as e:
        print_test("PUT /api/zpp/config", False, f"Erro: {str(e)}")
        return False


def test_list_input_files():
    """Teste 4: Listar arquivos de input"""
    print_header("TESTE 4: Listar Arquivos de Input")

    try:
        response = requests.get(f"{BASE_URL}/api/zpp/files/input", timeout=TIMEOUT)
        data = response.json()

        passed = (
            response.status_code == 200 and
            "count" in data and
            "files" in data
        )

        print_test(
            "GET /api/zpp/files/input",
            passed,
            f"Encontrados {data.get('count', 0)} arquivo(s) pendente(s)"
        )

        # Listar arquivos
        if data.get('files'):
            print(f"\n       Arquivos encontrados:")
            for file in data['files'][:5]:
                print(f"       - {file['filename']} ({file['size_mb']} MB)")

        return passed, data.get('count', 0)

    except Exception as e:
        print_test("GET /api/zpp/files/input", False, f"Erro: {str(e)}")
        return False, 0


def test_list_output_files():
    """Teste 5: Listar arquivos de output"""
    print_header("TESTE 5: Listar Arquivos de Output")

    try:
        response = requests.get(f"{BASE_URL}/api/zpp/files/output", timeout=TIMEOUT)
        data = response.json()

        passed = (
            response.status_code == 200 and
            "count" in data and
            "files" in data
        )

        print_test(
            "GET /api/zpp/files/output",
            passed,
            f"Encontrados {data.get('count', 0)} arquivo(s) processado(s)"
        )

        return passed

    except Exception as e:
        print_test("GET /api/zpp/files/output", False, f"Erro: {str(e)}")
        return False


def test_get_history():
    """Teste 6: Obter histórico"""
    print_header("TESTE 6: Obter Histórico")

    try:
        response = requests.get(f"{BASE_URL}/api/zpp/history?limit=5", timeout=TIMEOUT)
        data = response.json()

        passed = (
            response.status_code == 200 and
            "total" in data and
            "logs" in data
        )

        print_test(
            "GET /api/zpp/history",
            passed,
            f"Total de {data.get('total', 0)} log(s), retornados {len(data.get('logs', []))}"
        )

        # Mostrar últimos logs
        if data.get('logs'):
            print(f"\n       Últimos processamentos:")
            for log in data['logs'][:3]:
                status = log.get('status', 'unknown')
                trigger = log.get('trigger_type', 'manual')
                files = log.get('summary', {}).get('total_files', 0)
                print(f"       - {log.get('job_id', 'N/A')[:8]}... | {status} | {trigger} | {files} arquivo(s)")

        return passed, data.get('logs', [])

    except Exception as e:
        print_test("GET /api/zpp/history", False, f"Erro: {str(e)}")
        return False, []


def test_process_files(has_files):
    """Teste 7: Processar arquivos (apenas se houver arquivos)"""
    print_header("TESTE 7: Processar Arquivos")

    if not has_files:
        print_test(
            "POST /api/zpp/process",
            True,
            f"{Colors.YELLOW}PULADO - Nenhum arquivo para processar{Colors.END}"
        )
        return True, None

    try:
        # Iniciar processamento
        response = requests.post(
            f"{BASE_URL}/api/zpp/process",
            json={"triggered_by": "test_script"},
            timeout=TIMEOUT
        )

        if response.status_code != 202:
            print_test("POST /api/zpp/process", False, f"Status code: {response.status_code}")
            return False, None

        data = response.json()
        job_id = data.get('job_id')

        print_test(
            "POST /api/zpp/process",
            True,
            f"Job iniciado: {job_id[:8]}..."
        )

        return True, job_id

    except Exception as e:
        print_test("POST /api/zpp/process", False, f"Erro: {str(e)}")
        return False, None


def test_job_status(job_id):
    """Teste 8: Consultar status de job"""
    print_header("TESTE 8: Consultar Status de Job")

    if not job_id:
        print_test(
            "GET /api/zpp/status/<job_id>",
            True,
            f"{Colors.YELLOW}PULADO - Nenhum job para consultar{Colors.END}"
        )
        return True

    try:
        # Polling de status (máximo 30 segundos)
        max_attempts = 15
        for attempt in range(max_attempts):
            response = requests.get(
                f"{BASE_URL}/api/zpp/status/{job_id}",
                timeout=TIMEOUT
            )

            if response.status_code != 200:
                print_test("GET /api/zpp/status/<job_id>", False, f"Status code: {response.status_code}")
                return False

            data = response.json()
            status = data.get('status')

            print(f"       [{attempt+1}/{max_attempts}] Status: {status}")

            if status in ['success', 'failed']:
                passed = status == 'success'

                details = []
                if passed:
                    details.append(f"Arquivos: {data.get('files_processed', 0)}")
                    details.append(f"Registros: {data.get('total_uploaded', 0):,}")
                    details.append(f"Duração: {data.get('duration_seconds', 0):.1f}s")
                else:
                    details.append(f"Erro: {data.get('error', 'Desconhecido')}")

                print_test(
                    "GET /api/zpp/status/<job_id>",
                    passed,
                    ", ".join(details)
                )

                return passed

            time.sleep(2)

        # Timeout
        print_test(
            "GET /api/zpp/status/<job_id>",
            False,
            f"{Colors.YELLOW}TIMEOUT - Job ainda em execução após 30s{Colors.END}"
        )
        return False

    except Exception as e:
        print_test("GET /api/zpp/status/<job_id>", False, f"Erro: {str(e)}")
        return False


def main():
    """Executa todos os testes"""
    print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}ZPP PROCESSOR - TESTE DA API{Colors.END}")
    print(f"{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"\nURL Base: {BASE_URL}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # Teste 1: Health Check
    results['health'] = test_health_check()

    if not results['health']:
        print(f"\n{Colors.RED}ERRO: Serviço não está saudável. Abortando testes.{Colors.END}\n")
        return 1

    # Teste 2: Obter configuração
    results['get_config'], original_config = test_get_config()

    # Teste 3: Atualizar configuração
    results['update_config'] = test_update_config(original_config)

    # Teste 4: Listar arquivos input
    results['list_input'], files_count = test_list_input_files()

    # Teste 5: Listar arquivos output
    results['list_output'] = test_list_output_files()

    # Teste 6: Histórico
    results['history'], logs = test_get_history()

    # Teste 7: Processar (apenas se houver arquivos)
    results['process'], job_id = test_process_files(files_count > 0)

    # Teste 8: Status de job
    results['job_status'] = test_job_status(job_id)

    # Resumo
    print_header("RESUMO DOS TESTES")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = f"{Colors.GREEN}✓{Colors.END}" if result else f"{Colors.RED}✗{Colors.END}"
        print(f"{status} {name}")

    print(f"\n{Colors.BOLD}Total: {passed}/{total} testes passaram{Colors.END}")

    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ TODOS OS TESTES PASSARAM{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ {total - passed} TESTE(S) FALHARAM{Colors.END}\n")
        return 1


if __name__ == '__main__':
    exit(main())
