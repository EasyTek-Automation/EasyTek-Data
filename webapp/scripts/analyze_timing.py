"""
Analisa o log de timing de callbacks e exibe estatísticas por callback.

Uso:
    python webapp/scripts/analyze_timing.py
    python webapp/scripts/analyze_timing.py --top 20
    python webapp/scripts/analyze_timing.py --slow 500   # só callbacks > 500ms
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

LOG_FILE = Path("logs/callback_timing.log")
DEFAULT_TOP = 15
DEFAULT_SLOW_THRESHOLD = 0  # ms — mostrar todos por padrão


def parse_args():
    top = DEFAULT_TOP
    slow = DEFAULT_SLOW_THRESHOLD
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--top" and i + 1 < len(args):
            top = int(args[i + 1])
        if arg == "--slow" and i + 1 < len(args):
            slow = int(args[i + 1])
    return top, slow


def main():
    top_n, slow_threshold = parse_args()

    if not LOG_FILE.exists():
        print(f"[ERRO] Arquivo não encontrado: {LOG_FILE}")
        print("  → Certifique-se de que MEASURE_CALLBACKS=1 está no .env e que a aplicação foi usada.")
        return

    # Formato: HH:MM:SS 🟢/🟡/🔴   123.4ms  nome-do-callback
    pattern = re.compile(r"[\U0001F7E2\U0001F7E1\U0001F534]\s+([\d.]+)ms\s+(.+)")

    tempos = defaultdict(list)
    total_linhas = 0

    with open(LOG_FILE, encoding="utf-8") as f:
        for linha in f:
            m = pattern.search(linha)
            if m:
                ms = float(m.group(1))
                callback = m.group(2).strip()
                if ms >= slow_threshold:
                    tempos[callback].append(ms)
                    total_linhas += 1

    if not tempos:
        print("[AVISO] Nenhum dado encontrado no log.")
        return

    # Calcular estatísticas
    stats = []
    for callback, valores in tempos.items():
        stats.append({
            "callback": callback[:60],
            "chamadas": len(valores),
            "media": sum(valores) / len(valores),
            "max": max(valores),
            "min": min(valores),
            "total": sum(valores),
        })

    # Ordenar por média decrescente
    stats.sort(key=lambda x: x["media"], reverse=True)

    print(f"\n{'='*80}")
    print(f"  ANÁLISE DE PERFORMANCE — CALLBACKS DASH")
    print(f"  Arquivo: {LOG_FILE}")
    print(f"  Total de execuções capturadas: {total_linhas}")
    if slow_threshold > 0:
        print(f"  Filtro: apenas callbacks > {slow_threshold}ms")
    print(f"{'='*80}\n")

    header = f"{'CALLBACK':<45} {'CALLS':>5}  {'MÉDIA':>8}  {'MÁX':>8}  {'MÍN':>8}"
    print(header)
    print("-" * 80)

    for s in stats[:top_n]:
        media = s["media"]
        emoji = "🔴" if media >= 1000 else "🟡" if media >= 300 else "🟢"
        linha = (
            f"{s['callback']:<45} "
            f"{s['chamadas']:>5}  "
            f"{media:>7.0f}ms  "
            f"{s['max']:>7.0f}ms  "
            f"{s['min']:>7.0f}ms"
        )
        print(f"{emoji} {linha}")

    print(f"\n{'='*80}")
    print(f"  🔴 > 1000ms (lento)   🟡 300-1000ms (aceitável)   🟢 < 300ms (rápido)")

    # Resumo geral
    todas = [v for vals in tempos.values() for v in vals]
    print(f"\n  Média geral:  {sum(todas)/len(todas):.0f}ms")
    print(f"  Mais lento:   {max(todas):.0f}ms  ({stats[0]['callback'][:50]})")
    print(f"  Callbacks únicos: {len(tempos)}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
