# test_mobile_detection.py
"""
Script de teste para validar detecção de mobile
"""

from src.middleware.mobile_detection import is_mobile_device

# Test cases
test_cases = [
    # Mobile
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)", True, "iPhone"),
    ("Mozilla/5.0 (Linux; Android 11; SM-G991B)", True, "Android Phone"),
    ("Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X)", True, "iPad"),

    # Desktop
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", False, "Windows Chrome"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", False, "Mac Safari"),
    ("Mozilla/5.0 (X11; Linux x86_64)", False, "Linux Firefox"),
]

print("Testando Detecao de Dispositivos Mobile\n")
print("-" * 60)

passed = 0
failed = 0

for user_agent, expected, description in test_cases:
    result = is_mobile_device(user_agent)
    status = "[PASS]" if result == expected else "[FAIL]"

    if result == expected:
        passed += 1
    else:
        failed += 1

    print(f"{status} | {description}")
    print(f"  Expected: {expected}, Got: {result}")
    print()

print("-" * 60)
print(f"\nResultado: {passed} passou, {failed} falhou")

if failed == 0:
    print("Todos os testes passaram!")
else:
    print("Alguns testes falharam")
