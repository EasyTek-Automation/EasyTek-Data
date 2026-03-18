"""
Schemas e funções auxiliares para logs de processamento
"""
from datetime import datetime
from typing import Dict, List, Optional
import uuid


def create_processing_log(
    job_id: str,
    trigger_type: str = "manual",
    triggered_by: Optional[str] = None
) -> Dict:
    """
    Cria um documento de log de processamento inicial

    Args:
        job_id: ID único do job
        trigger_type: "manual" ou "automatic"
        triggered_by: Username que iniciou (para manual)

    Returns:
        Documento de log para inserção no MongoDB
    """
    return {
        "job_id": job_id,
        "status": "running",
        "started_at": datetime.now(),
        "completed_at": None,
        "duration_seconds": None,
        "trigger_type": trigger_type,
        "triggered_by": triggered_by,
        "files_processed": [],
        "summary": {
            "total_files": 0,
            "total_uploaded_records": 0
        },
        "error_message": None
    }


def create_file_entry(
    filename: str,
    file_type: str,
    collection_name: str,
    uploaded_rows: int,
    status: str = "success",
    error_message: Optional[str] = None,
    replaced_rows: int = 0,
    skipped_rows: int = 0,
    warnings: Optional[List[str]] = None
) -> Dict:
    """
    Cria uma entrada de arquivo processado

    Args:
        filename: Nome do arquivo
        file_type: "zppprd" ou "zppparadas"
        collection_name: Nome da collection MongoDB
        uploaded_rows: Número de registros inseridos
        status: "success", "partial" ou "failed"
        error_message: Mensagem de erro (se houver)
        replaced_rows: Número de registros substituídos (delete+reinsert)
        skipped_rows: Número de registros ignorados (duplicatas)
        warnings: Lista de mensagens de aviso (ex: duplicatas ignoradas)

    Returns:
        Dicionário representando arquivo processado
    """
    entry = {
        "filename": filename,
        "type": file_type,
        "collection_name": collection_name,
        "uploaded_rows": uploaded_rows,
        "replaced_rows": replaced_rows,
        "skipped_rows": skipped_rows,
        "status": status
    }

    if error_message:
        entry["error_message"] = error_message

    if warnings:
        entry["warnings"] = warnings

    return entry


def update_processing_log(
    current_log: Dict,
    files_processed: List[Dict],
    status: str = None,
    error_message: Optional[str] = None
) -> Dict:
    """
    Atualiza o log de processamento ao final, derivando o status do job a partir dos arquivos.

    Status derivado: 'failed' se qualquer arquivo falhou, 'partial' se houve duplicatas
    ignoradas, 'success' apenas se todos os arquivos foram inseridos sem ressalvas.
    O parâmetro `status` é ignorado — use `error_message` para erros de job sem arquivos.
    """
    completed_at = datetime.now()
    duration_seconds = (completed_at - current_log["started_at"]).total_seconds()

    total_uploaded = sum(f.get("uploaded_rows", 0) for f in files_processed)
    total_skipped = sum(f.get("skipped_rows", 0) for f in files_processed)

    # Deriva status do job a partir dos arquivos
    file_statuses = {f.get("status") for f in files_processed}
    if not files_processed:
        derived_status = status
    elif "failed" in file_statuses:
        derived_status = "failed"
    elif "partial" in file_statuses:
        derived_status = "partial"
    else:
        derived_status = "success"

    update_data = {
        "status": derived_status,
        "completed_at": completed_at,
        "duration_seconds": round(duration_seconds, 2),
        "files_processed": files_processed,
        "summary": {
            "total_files": len(files_processed),
            "total_uploaded_records": total_uploaded,
            "total_skipped_records": total_skipped
        }
    }

    if error_message:
        update_data["error_message"] = error_message

    return update_data


def create_default_config() -> Dict:
    """
    Cria documento de configuração padrão

    Returns:
        Documento de configuração para MongoDB
    """
    return {
        "_id": "global",
        "auto_process": True,
        "interval_minutes": 60,
        "archive_enabled": True,
        "last_updated": datetime.now(),
        "updated_by": "system"
    }


def generate_job_id() -> str:
    """
    Gera um job ID único

    Returns:
        UUID string
    """
    return str(uuid.uuid4())
