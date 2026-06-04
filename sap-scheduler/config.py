"""Config do daemon sap-scheduler (DS-04 + IM-D1).

Carrega `.env` em `%USERPROFILE%\\sap-scheduler\\.env` (ou local), retorna
dataclass imutável `DaemonConfig` com 12 campos. Falha fail-fast se obrigatório
ausente ou inválido — daemon não roda com config errada (SP-03 RF-03-05).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):  # type: ignore[misc]
        return False  # graceful fallback — env vars vivem no os.environ direto


def _root_dir() -> Path:
    """Retorna `%USERPROFILE%\\sap-scheduler\\` (Windows) ou `~/sap-scheduler` (Linux/CI)."""
    base = os.environ.get("SAP_SCHEDULER_ROOT") or os.environ.get("USERPROFILE") or str(Path.home())
    if base.endswith("sap-scheduler") or base.endswith("sap-scheduler\\"):
        return Path(base)
    return Path(base) / "sap-scheduler"


@dataclass(frozen=True)
class DaemonConfig:
    """Config imutável do daemon. Carregada 1× no boot."""

    mongo_uri: str
    db_name: str
    collection: str = "sap_jobs"
    tipos_suportados: List[str] = field(default_factory=lambda: ["zppprd", "zpp_nt0001"])
    polling_segundos: int = 30
    log_level: str = "INFO"
    log_dir: Path = field(default_factory=lambda: _root_dir() / "logs")
    log_backup_count: int = 30
    pasta_input: Optional[Path] = None  # PASTA_INPUT_ZPP_PROCESSOR
    sap_gate_dir: Path = field(default_factory=lambda: _root_dir() / "sap-gate")
    heartbeat_segundos: int = 3600
    lockfile_path: Path = field(default_factory=lambda: _root_dir() / "daemon.lock")
    mock_sap: bool = False  # IM-E6 — modo de teste E2E local sem SAP real
    audit_maio_dir: Optional[Path] = None  # IM-E6 — fonte dos .xlsx pra mock copiar
    max_tentativas_job: int = 3  # Bloco K — retry in-run em falhas transientes (1 = sem retry)


def _parse_csv_list(raw: str) -> List[str]:
    return [s.strip() for s in raw.split(",") if s.strip()]


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in ("true", "1", "yes", "y")


def load() -> DaemonConfig:
    """Lê `.env` + defaults; valida obrigatórios.

    Levanta `RuntimeError` se MONGO_URI/DB_NAME ausentes ou PASTA_INPUT_ZPP_PROCESSOR
    ausente (fail-fast — não roda com config errada).
    """
    # Carrega .env da raiz do daemon (se existir); env vars já no ambiente vencem.
    env_path = _root_dir() / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)

    mongo_uri = os.getenv("MONGO_URI", "").strip()
    if not mongo_uri:
        raise RuntimeError("MONGO_URI obrigatorio (env ou .env do daemon)")

    db_name = os.getenv("DB_NAME", "").strip()
    if not db_name:
        raise RuntimeError("DB_NAME obrigatorio")

    pasta_input_raw = os.getenv("PASTA_INPUT_ZPP_PROCESSOR", "").strip()
    if not pasta_input_raw:
        raise RuntimeError("PASTA_INPUT_ZPP_PROCESSOR obrigatorio (caminho do input/ do zpp-processor)")

    tipos = _parse_csv_list(os.getenv("SAP_JOBS_TIPOS_SUPORTADOS", "zppprd,zpp_nt0001"))
    if not tipos:
        raise RuntimeError("SAP_JOBS_TIPOS_SUPORTADOS vazio")

    try:
        polling = int(os.getenv("POLLING_INTERVAL_SEGUNDOS", "30"))
    except ValueError as e:
        raise RuntimeError(f"POLLING_INTERVAL_SEGUNDOS nao e inteiro: {e}") from e
    if polling < 5:
        raise RuntimeError(f"POLLING_INTERVAL_SEGUNDOS deve ser >= 5; veio {polling}")

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        raise RuntimeError(f"LOG_LEVEL invalido: {log_level}")

    log_dir = Path(os.getenv("LOG_DIR", str(_root_dir() / "logs")))

    try:
        log_backup = int(os.getenv("LOG_BACKUP_COUNT", "30"))
    except ValueError as e:
        raise RuntimeError(f"LOG_BACKUP_COUNT nao e inteiro: {e}") from e

    sap_gate = Path(os.getenv("SAP_GATE_DIR", str(_root_dir() / "sap-gate")))

    try:
        heartbeat = int(os.getenv("HEARTBEAT_INTERVAL_SEGUNDOS", "3600"))
    except ValueError as e:
        raise RuntimeError(f"HEARTBEAT_INTERVAL_SEGUNDOS nao e inteiro: {e}") from e

    lockfile = Path(os.getenv("LOCKFILE_PATH", str(_root_dir() / "daemon.lock")))

    try:
        max_tentativas = int(os.getenv("MAX_TENTATIVAS_JOB", "3"))
    except ValueError as e:
        raise RuntimeError(f"MAX_TENTATIVAS_JOB nao e inteiro: {e}") from e
    if max_tentativas < 1:
        raise RuntimeError(f"MAX_TENTATIVAS_JOB deve ser >= 1; veio {max_tentativas}")

    mock = _parse_bool(os.getenv("MOCK_SAP", "false"))
    audit_dir = os.getenv("AUDIT_MAIO_DIR", "").strip()
    audit_path = Path(audit_dir) if audit_dir else None

    return DaemonConfig(
        mongo_uri=mongo_uri,
        db_name=db_name,
        collection=os.getenv("SAP_JOBS_COLLECTION", "sap_jobs"),
        tipos_suportados=tipos,
        polling_segundos=polling,
        log_level=log_level,
        log_dir=log_dir,
        log_backup_count=log_backup,
        pasta_input=Path(pasta_input_raw),
        sap_gate_dir=sap_gate,
        heartbeat_segundos=heartbeat,
        lockfile_path=lockfile,
        mock_sap=mock,
        audit_maio_dir=audit_path,
        max_tentativas_job=max_tentativas,
    )
