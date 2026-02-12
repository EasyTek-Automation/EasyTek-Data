"""
API REST do ZPP Processor
Endpoints para processamento de planilhas ZPP
"""
from flask import Flask, request, jsonify
from pymongo import MongoClient, DESCENDING
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List

import config
from processor import ZPPProcessor
from scheduler import ZPPScheduler
from models.processing_log import (
    generate_job_id,
    create_processing_log,
    update_processing_log,
    create_default_config
)

# Configurar logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Criar aplicação Flask
app = Flask(__name__)

# Estado global
processing_jobs: Dict[str, dict] = {}  # job_id -> status info
scheduler: ZPPScheduler = None
_initialized = False


def get_db():
    """Retorna conexão MongoDB"""
    try:
        client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
        return client[config.DB_NAME]
    except Exception as e:
        logger.error(f"Erro ao conectar MongoDB: {e}")
        raise


def process_in_background(job_id: str, triggered_by: str = None):
    """
    Executa processamento em background thread

    Args:
        job_id: ID único do job
        triggered_by: Username que iniciou (para manual)
    """
    try:
        logger.info(f"\n[Job {job_id}] Iniciando processamento")

        # Criar log inicial
        log_doc = create_processing_log(
            job_id=job_id,
            trigger_type="manual",
            triggered_by=triggered_by
        )

        # Inserir no MongoDB
        db = get_db()
        db[config.LOGS_COLLECTION].insert_one(log_doc)

        # Atualizar estado global
        processing_jobs[job_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat()
        }

        # Inicializar processador
        processor = ZPPProcessor(
            mongo_uri=config.MONGO_URI,
            db_name=config.DB_NAME,
            archive_dir=config.OUTPUT_DIR
        )

        # Processar diretório
        results = processor.process_directory(
            directory=config.INPUT_DIR,
            batch_size=config.BATCH_SIZE,
            move_after_process=True
        )

        # Fechar processador
        processor.close()

        # Atualizar log
        log_update = update_processing_log(
            current_log=log_doc,
            files_processed=results,
            status="success" if results else "failed",
            error_message=None if results else "Nenhum arquivo encontrado para processar"
        )

        db[config.LOGS_COLLECTION].update_one(
            {"job_id": job_id},
            {"$set": log_update}
        )

        # Atualizar estado global
        processing_jobs[job_id] = {
            "status": log_update["status"],
            "started_at": log_doc["started_at"].isoformat(),
            "completed_at": log_update["completed_at"].isoformat(),
            "files_processed": len(results),
            "total_uploaded": log_update["summary"]["total_uploaded_records"]
        }

        logger.info(f"[Job {job_id}] Concluído: {len(results)} arquivo(s)")

    except Exception as e:
        logger.error(f"[Job {job_id}] Erro: {e}")

        # Atualizar log com erro
        db = get_db()
        db[config.LOGS_COLLECTION].update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "failed",
                "completed_at": datetime.now(),
                "error_message": str(e)
            }}
        )

        # Atualizar estado global
        processing_jobs[job_id] = {
            "status": "failed",
            "error": str(e)
        }


# ============================================================================
# ENDPOINTS REST
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Verificar MongoDB
        db = get_db()
        db.command('ping')

        # Verificar volumes
        volumes_ok = all([
            config.INPUT_DIR.exists(),
            config.OUTPUT_DIR.exists(),
            config.LOGS_DIR.exists()
        ])

        return jsonify({
            "status": "healthy",
            "mongodb": "connected",
            "volumes": "ok" if volumes_ok else "error",
            "scheduler": "running" if (scheduler and scheduler.running) else "stopped"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


@app.route('/api/zpp/process', methods=['POST'])
def trigger_processing():
    """
    Inicia processamento manual de planilhas

    Request Body (opcional):
        {
            "triggered_by": "username@email.com"
        }

    Response:
        {
            "status": "success",
            "job_id": "uuid-v4",
            "message": "Processamento iniciado"
        }
    """
    try:
        data = request.get_json() or {}
        triggered_by = data.get('triggered_by', 'anonymous')

        # Gerar job ID
        job_id = generate_job_id()

        # Iniciar processamento em background
        thread = threading.Thread(
            target=process_in_background,
            args=(job_id, triggered_by),
            daemon=True
        )
        thread.start()

        return jsonify({
            "status": "success",
            "job_id": job_id,
            "message": "Processamento iniciado em background"
        }), 202

    except Exception as e:
        logger.error(f"Erro ao iniciar processamento: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/zpp/status/<job_id>', methods=['GET'])
def get_job_status(job_id: str):
    """
    Consulta status de um job

    Response:
        {
            "job_id": "uuid",
            "status": "running" | "success" | "failed",
            "started_at": "ISO8601",
            "completed_at": "ISO8601" (se concluído),
            "files_processed": 2,
            "total_uploaded": 15000
        }
    """
    try:
        # Verificar estado global primeiro (mais rápido)
        if job_id in processing_jobs:
            return jsonify({
                "job_id": job_id,
                **processing_jobs[job_id]
            }), 200

        # Se não encontrou em memória, buscar no MongoDB
        db = get_db()
        log_doc = db[config.LOGS_COLLECTION].find_one({"job_id": job_id})

        if not log_doc:
            return jsonify({
                "status": "error",
                "message": "Job não encontrado"
            }), 404

        # Formatar resposta
        response = {
            "job_id": job_id,
            "status": log_doc["status"],
            "started_at": log_doc["started_at"].isoformat(),
            "trigger_type": log_doc.get("trigger_type", "manual"),
            "triggered_by": log_doc.get("triggered_by", "unknown")
        }

        if log_doc.get("completed_at"):
            response["completed_at"] = log_doc["completed_at"].isoformat()
            response["duration_seconds"] = log_doc.get("duration_seconds")
            response["files_processed"] = log_doc.get("summary", {}).get("total_files", 0)
            response["total_uploaded"] = log_doc.get("summary", {}).get("total_uploaded_records", 0)

        if log_doc.get("error_message"):
            response["error"] = log_doc["error_message"]

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Erro ao consultar status: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/zpp/history', methods=['GET'])
def get_processing_history():
    """
    Lista histórico de processamentos

    Query Params:
        limit: Número de registros (default: 50)
        offset: Offset para paginação (default: 0)

    Response:
        {
            "total": 100,
            "limit": 50,
            "offset": 0,
            "logs": [...]
        }
    """
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        db = get_db()
        collection = db[config.LOGS_COLLECTION]

        # Contar total
        total = collection.count_documents({})

        # Buscar logs ordenados por data
        logs_cursor = collection.find().sort("started_at", DESCENDING).skip(offset).limit(limit)

        logs = []
        for log in logs_cursor:
            log_data = {
                "job_id": log["job_id"],
                "status": log["status"],
                "started_at": log["started_at"].isoformat(),
                "trigger_type": log.get("trigger_type", "manual"),
                "triggered_by": log.get("triggered_by", "unknown")
            }

            if log.get("completed_at"):
                log_data["completed_at"] = log["completed_at"].isoformat()
                log_data["duration_seconds"] = log.get("duration_seconds")
                log_data["summary"] = log.get("summary", {})

            if log.get("files_processed"):
                log_data["files"] = log["files_processed"]

            if log.get("error_message"):
                log_data["error"] = log["error_message"]

            logs.append(log_data)

        return jsonify({
            "total": total,
            "limit": limit,
            "offset": offset,
            "logs": logs
        }), 200

    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/zpp/files/input', methods=['GET'])
def list_input_files():
    """
    Lista arquivos pendentes no diretório input

    Response:
        {
            "count": 3,
            "files": [
                {
                    "filename": "zppprd_202601.xlsx",
                    "size_mb": 2.5,
                    "modified_at": "ISO8601"
                }
            ]
        }
    """
    try:
        files = []

        if config.INPUT_DIR.exists():
            # Buscar .xlsx e .XLSX (case-insensitive)
            seen_files = set()
            for pattern in ['*.xlsx', '*.XLSX']:
                for file_path in config.INPUT_DIR.glob(pattern):
                    # Evitar duplicatas e arquivos temporários
                    if file_path.name not in seen_files and not file_path.name.startswith('~$'):
                        seen_files.add(file_path.name)
                        stat = file_path.stat()
                        files.append({
                            "filename": file_path.name,
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })

        # Ordenar por data de modificação (mais recente primeiro)
        files.sort(key=lambda x: x["modified_at"], reverse=True)

        return jsonify({
            "count": len(files),
            "files": files
        }), 200

    except Exception as e:
        logger.error(f"Erro ao listar arquivos: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/zpp/files/output', methods=['GET'])
def list_output_files():
    """
    Lista arquivos processados no diretório output

    Response: Mesmo formato de /api/zpp/files/input
    """
    try:
        files = []

        if config.OUTPUT_DIR.exists():
            # Buscar .xlsx e .XLSX (case-insensitive)
            seen_files = set()
            for pattern in ['*.xlsx', '*.XLSX']:
                for file_path in config.OUTPUT_DIR.glob(pattern):
                    # Evitar duplicatas e arquivos temporários
                    if file_path.name not in seen_files and not file_path.name.startswith('~$'):
                        seen_files.add(file_path.name)
                        stat = file_path.stat()
                        files.append({
                            "filename": file_path.name,
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })

        files.sort(key=lambda x: x["modified_at"], reverse=True)

        return jsonify({
            "count": len(files),
            "files": files
        }), 200

    except Exception as e:
        logger.error(f"Erro ao listar arquivos: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/zpp/config', methods=['GET'])
def get_config():
    """
    Retorna configurações atuais

    Response:
        {
            "auto_process": true,
            "interval_minutes": 60,
            "archive_enabled": true,
            "last_updated": "ISO8601",
            "updated_by": "user@email.com"
        }
    """
    try:
        db = get_db()
        config_doc = db[config.CONFIG_COLLECTION].find_one({"_id": "global"})

        if not config_doc:
            # Criar configuração padrão
            config_doc = create_default_config()
            db[config.CONFIG_COLLECTION].insert_one(config_doc)

        # Remover _id antes de retornar
        config_doc.pop('_id', None)

        # Converter datetime para ISO
        if config_doc.get('last_updated'):
            config_doc['last_updated'] = config_doc['last_updated'].isoformat()

        return jsonify(config_doc), 200

    except Exception as e:
        logger.error(f"Erro ao buscar config: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/zpp/config', methods=['PUT'])
def update_config():
    """
    Atualiza configurações

    Request Body:
        {
            "auto_process": true,
            "interval_minutes": 60,
            "updated_by": "admin@email.com"
        }

    Response:
        {
            "status": "success",
            "message": "Configuração atualizada"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "message": "Body vazio"
            }), 400

        # Validar campos
        update_fields = {}

        if "auto_process" in data:
            update_fields["auto_process"] = bool(data["auto_process"])

        if "interval_minutes" in data:
            interval = int(data["interval_minutes"])
            if interval < 1 or interval > 1440:  # 1 min a 24h
                return jsonify({
                    "status": "error",
                    "message": "Intervalo deve estar entre 1 e 1440 minutos"
                }), 400
            update_fields["interval_minutes"] = interval

        if "archive_enabled" in data:
            update_fields["archive_enabled"] = bool(data["archive_enabled"])

        # Adicionar metadados
        update_fields["last_updated"] = datetime.now()
        update_fields["updated_by"] = data.get("updated_by", "anonymous")

        # Atualizar MongoDB
        db = get_db()
        result = db[config.CONFIG_COLLECTION].update_one(
            {"_id": "global"},
            {"$set": update_fields},
            upsert=True
        )

        return jsonify({
            "status": "success",
            "message": "Configuração atualizada",
            "modified": result.modified_count > 0
        }), 200

    except Exception as e:
        logger.error(f"Erro ao atualizar config: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================================
# INICIALIZAÇÃO
# ============================================================================

def initialize_app():
    """Inicializa aplicação e serviços"""
    global scheduler, _initialized

    # Prevenir inicialização múltipla (importante para Gunicorn com múltiplos workers)
    if _initialized:
        logger.info("App já inicializado, pulando...")
        return

    _initialized = True

    logger.info("\n" + "="*80)
    logger.info("ZPP PROCESSOR - Inicializando")
    logger.info("="*80 + "\n")

    # Validar configuração
    errors = config.validate_config()
    if errors:
        logger.error("Erros de configuração:")
        for err in errors:
            logger.error(f"  - {err}")
        raise RuntimeError("Configuração inválida")

    # Criar diretórios se não existirem
    for directory in [config.INPUT_DIR, config.OUTPUT_DIR, config.LOGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Diretório: {directory}")

    # Verificar conexão MongoDB
    try:
        db = get_db()
        db.command('ping')
        logger.info(f"MongoDB: {config.DB_NAME} ✓")
    except Exception as e:
        logger.error(f"MongoDB: Erro - {e}")
        raise

    # Inicializar scheduler
    try:
        scheduler = ZPPScheduler(config.MONGO_URI, config.DB_NAME)
        scheduler.start()
        logger.info("Scheduler: Iniciado ✓")
    except Exception as e:
        logger.error(f"Scheduler: Erro - {e}")
        # Não falhar se scheduler não iniciar
        scheduler = None

    logger.info("\n" + "="*80)
    logger.info("ZPP PROCESSOR - Pronto")
    logger.info(f"Porta: {config.PORT}")
    logger.info("="*80 + "\n")


# Inicializar aplicação automaticamente quando módulo é importado
# (necessário para Gunicorn, que não executa __main__)
initialize_app()


if __name__ == '__main__':
    # Se rodar diretamente, apenas iniciar o servidor
    app.run(host='0.0.0.0', port=config.PORT, debug=False)
