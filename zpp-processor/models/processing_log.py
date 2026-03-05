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
    replaced_rows: int = 0
) -> Dict:
    """
    Cria uma entrada de arquivo processado

    Args:
        filename: Nome do arquivo
        file_type: "zppprd" ou "zppparadas"
        collection_name: Nome da collection MongoDB
        uploaded_rows: Número de registros inseridos
        status: "success" ou "failed"
        error_message: Mensagem de erro (se houver)
        replaced_rows: Número de registros substituídos (delete+reinsert)

    Returns:
        Dicionário representando arquivo processado
    """
    entry = {
        "filename": filename,
        "type": file_type,
        "collection_name": collection_name,
        "uploaded_rows": uploaded_rows,
        "replaced_rows": replaced_rows,
        "status": status
    }

    if error_message:
        entry["error_message"] = error_message

    return entry


def update_processing_log(
    current_log: Dict,
    files_processed: List[Dict],
    status: str = "success",
    error_message: Optional[str] = None
) -> Dict:
    """
    Atualiza o log de processamento ao final

    Args:
        current_log: Log atual
        files_processed: Lista de arquivos processados
        status: "success" ou "failed"
        error_message: Mensagem de erro (se houver)

    Returns:
        Log atualizado para update no MongoDB
    """
    completed_at = datetime.now()
    duration_seconds = (completed_at - current_log["started_at"]).total_seconds()

    total_uploaded = sum(
        f.get("uploaded_rows", 0)
        for f in files_processed
        if f.get("status") == "success"
    )

    update_data = {
        "status": status,
        "completed_at": completed_at,
        "duration_seconds": round(duration_seconds, 2),
        "files_processed": files_processed,
        "summary": {
            "total_files": len(files_processed),
            "total_uploaded_records": total_uploaded
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
