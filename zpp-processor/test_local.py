"""
Script de teste local do ZPP Processor
Testa endpoints da API sem precisar de Docker
"""
import requests
import time
from pathlib import Path

BASE_URL = "http://localhost:5002"


def test_health():
    """Testa health check"""
    print("\n1. Testando Health Check...")
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200


def test_list_input_files():
    """Testa listagem de arquivos de input"""
    print("\n2. Testando Listagem de Arquivos (Input)...")
    response = requests.get(f"{BASE_URL}/api/zpp/files/input")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Arquivos encontrados: {data['count']}")
    for file in data.get('files', []):
        print(f"  - {file['filename']} ({file['size_mb']} MB)")
    return response.status_code == 200


def test_get_config():
    """Testa obtenção de configuração"""
    print("\n3. Testando Obtenção de Configuração...")
    response = requests.get(f"{BASE_URL}/api/zpp/config")
    print(f"Status: {response.status_code}")
    print(f"Config: {response.json()}")
    return response.status_code == 200


def test_process():
    """Testa processamento manual"""
    print("\n4. Testando Processamento Manual...")
    response = requests.post(
        f"{BASE_URL}/api/zpp/process",
        json={"triggered_by": "test_script"}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {data}")

    if response.status_code != 202:
        return False

    job_id = data.get('job_id')
    print(f"\nJob ID: {job_id}")

    # Polling de status
    print("\nAguardando conclusão...")
    for i in range(30):  # Esperar até 60 segundos (30 * 2s)
        time.sleep(2)
        status_response = requests.get(f"{BASE_URL}/api/zpp/status/{job_id}")
        status_data = status_response.json()
        status = status_data.get('status')

        print(f"  [{i+1}] Status: {status}")

        if status in ['success', 'failed']:
            print(f"\n✓ Processamento concluído: {status}")
            print(f"Arquivos processados: {status_data.get('files_processed', 0)}")
            print(f"Registros carregados: {status_data.get('total_uploaded', 0)}")
            return status == 'success'

    print("\n✗ Timeout esperando processamento")
    return False


def test_history():
    """Testa histórico"""
    print("\n5. Testando Histórico...")
    response = requests.get(f"{BASE_URL}/api/zpp/history?limit=5")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Total de logs: {data['total']}")
    print(f"Logs retornados: {len(data.get('logs', []))}")
    for log in data.get('logs', [])[:3]:
        print(f"  - Job {log['job_id'][:8]}... | {log['status']} | {log.get('trigger_type', 'manual')}")
    return response.status_code == 200


def test_update_config():
    """Testa atualização de configuração"""
    print("\n6. Testando Atualização de Configuração...")
    response = requests.put(
        f"{BASE_URL}/api/zpp/config",
        json={
            "auto_process": False,  # Desativar para teste
            "interval_minutes": 120,
            "updated_by": "test_script"
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    # Verificar se foi atualizado
    response = requests.get(f"{BASE_URL}/api/zpp/config")
    config = response.json()
    print(f"Configuração após update: {config}")

    return config['interval_minutes'] == 120


def main():
    """Executa todos os testes"""
    print("="*80)
    print("ZPP PROCESSOR - TESTE LOCAL")
    print("="*80)

    tests = [
        ("Health Check", test_health),
        ("Listar Arquivos Input", test_list_input_files),
        ("Obter Configuração", test_get_config),
        ("Histórico", test_history),
        ("Atualizar Configuração", test_update_config),
        # ("Processamento Manual", test_process),  # Comentado por padrão
    ]

    results = {}

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n✗ Erro em '{name}': {e}")
            results[name] = False

    # Resumo
    print("\n" + "="*80)
    print("RESUMO DOS TESTES")
    print("="*80)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {name}")

    print(f"\n{passed}/{total} testes passaram")

    if passed == total:
        print("\n✓ Todos os testes passaram!")
        return 0
    else:
        print(f"\n✗ {total - passed} teste(s) falharam")
        return 1


if __name__ == "__main__":
    exit(main())
