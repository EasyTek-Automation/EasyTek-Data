"""Smoke test pos-instalacao do daemon sap-scheduler (DS-05 + IM-F3).

Roda manualmente apos passo 11 do RUNBOOK. Saida:
  exit 0 = tudo verde
  exit > 0 = problema detectado (codigo do FAIL)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def fail(code: int, msg: str) -> None:
    print(f"[FAIL #{code}] {msg}", file=sys.stderr)
    sys.exit(code)


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def main() -> int:
    userprofile = os.environ.get("USERPROFILE") or str(Path.home())
    root = Path(userprofile) / "sap-scheduler"

    # 1. Estrutura
    if not root.exists():
        fail(1, f"{root} nao existe")
    ok(f"estrutura raiz: {root}")

    for sub in (".venv", "sap-gate", "logs"):
        if not (root / sub).exists():
            fail(2, f"{root/sub} ausente")
    ok("subpastas presentes (.venv, sap-gate, logs)")

    # 2. Python venv
    if sys.platform == "win32":
        python_exe = root / ".venv" / "Scripts" / "python.exe"
    else:
        python_exe = root / ".venv" / "bin" / "python"
    if not python_exe.exists():
        fail(3, f"venv python ausente em {python_exe}")
    ok(f"venv python: {python_exe}")

    # 3. Deps instaladas
    res = subprocess.run(
        [str(python_exe), "-c", "import pymongo, dotenv, pytz; print('OK')"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if res.returncode != 0 or "OK" not in res.stdout:
        fail(4, f"deps faltando: stderr={res.stderr.strip()}")
    if sys.platform == "win32":
        res_w = subprocess.run(
            [str(python_exe), "-c", "import win32com; print('OK')"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if res_w.returncode != 0:
            fail(4, f"pywin32 nao instalado: {res_w.stderr.strip()}")
    ok("deps instaladas (pymongo, dotenv, pytz, pywin32)")

    # 4. .env existe e nao tem placeholders
    env_path = root / ".env"
    if not env_path.exists():
        fail(5, ".env ausente")
    env_content = env_path.read_text(encoding="utf-8")
    placeholders = ["<MONGO_URI", "<PASTA_INPUT_ZPP_PROCESSOR", "<host>"]
    for ph in placeholders:
        if ph in env_content:
            fail(6, f".env contem placeholder nao preenchido: {ph}")
    ok(".env configurado (sem placeholders)")

    # 5. Task registrada (somente Windows)
    if sys.platform == "win32":
        res = subprocess.run(
            ["schtasks", "/Query", "/TN", "SAP Job Scheduler", "/FO", "LIST"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode != 0:
            fail(7, "task 'SAP Job Scheduler' nao encontrada (rode `schtasks /Create /XML task.xml /TN \"SAP Job Scheduler\" /F`)")
        ok("task 'SAP Job Scheduler' registrada")
    else:
        warn("schtasks check pulado (nao-Windows — provavelmente jail/CI)")

    # 6. Daemon vivo (lockfile + PID check)
    lock_path = root / "daemon.lock"
    if not lock_path.exists():
        warn("daemon.lock ausente — daemon talvez nao iniciado ainda. Rode `schtasks /Run /TN \"SAP Job Scheduler\"` (Windows) ou `python daemon.py` (dev). Tente healthcheck de novo em 30s.")
        return 0
    pid_str = lock_path.read_text(encoding="utf-8").splitlines()[0].strip()
    try:
        pid = int(pid_str)
    except ValueError:
        fail(8, f"daemon.lock corrompido: {pid_str!r}")

    if sys.platform == "win32":
        res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, timeout=10)
        if str(pid) not in res.stdout:
            fail(8, f"PID {pid} no lockfile, mas processo nao esta vivo")
    else:
        try:
            os.kill(pid, 0)
        except OSError:
            fail(8, f"PID {pid} no lockfile, mas processo nao esta vivo")
    ok(f"daemon vivo (PID {pid})")

    # 7. Log recente
    log_files = list((root / "logs").glob("daemon.log*"))
    if not log_files:
        warn("nenhum log gerado ainda — daemon talvez recem-iniciado")
    else:
        latest = max(log_files, key=lambda p: p.stat().st_mtime)
        age_s = time.time() - latest.stat().st_mtime
        if age_s > 600:
            warn(f"log mais recente tem {age_s:.0f}s de idade — pode estar sem heartbeat (esperado se HEARTBEAT_INTERVAL > 10min)")
        else:
            ok(f"log recente: {latest.name} (idade={age_s:.0f}s)")

    print("\n=== HEALTHCHECK OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
