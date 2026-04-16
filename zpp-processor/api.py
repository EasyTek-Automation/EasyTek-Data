"""
API REST do ZPP Processor.
Endpoints: POST /upload/retroativo, GET /logs, GET /api/health.
"""
import io
import logging
import tempfile
import traceback
from datetime import datetime
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, request, jsonify
from pymongo import MongoClient, DESCENDING

import auth
import config
from auth import validate_internal_headers
from models.processing_log import BRTFormatter
from pipeline import process_file, RejectionError
from locks import LockActiveError
from scheduler import ZPPScheduler

app = Flask(__name__)
_client: MongoClient | None = None
_scheduler: ZPPScheduler | None = None
_BRT = ZoneInfo("America/Sao_Paulo")


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    handler = logging.FileHandler(
        config.LOGS_DIR / "zpp-processor.log", encoding="utf-8"
    )
    handler.setFormatter(BRTFormatter("%(asctime)s | %(levelname)-7s | %(message)s"))
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    root.addHandler(handler)
    # Console handler para docker logs
    console = logging.StreamHandler()
    console.setFormatter(BRTFormatter("%(asctime)s | %(levelname)-7s | %(message)s"))
    root.addHandler(console)


def _verify_replica_set(client: MongoClient) -> None:
    try:
        status = client.admin.command("replSetGetStatus")
        if status.get("myState") != 1:
            raise RuntimeError("MongoDB não está em estado PRIMARY.")
        logging.getLogger(__name__).info("MongoDB replica set: PRIMARY ✓")
    except Exception as e:
        raise RuntimeError(
            "ERRO CRÍTICO: MongoDB não está configurado como replica set. "
            f"Transactions não disponíveis. Detalhe: {e}"
        )


def _ensure_indexes(client: MongoClient) -> None:
    from pipeline import ensure_indexes
    from pymongo.errors import OperationFailure

    db = client[config.DB_NAME]
    logger = logging.getLogger(__name__)

    # Dropar índices antigos que mudaram de estrutura (migration única)
    _old_indexes = {
        "ZPP_Producao": ["idx_equipamento_data", "idx_equipamento_producao",
                         "idx_ordem_unique", "idx_range_datas"],
        "ZPP_Paradas":  ["idx_parada_unique", "idx_linha_data", "idx_range_datas"],
    }
    for col_name, idx_names in _old_indexes.items():
        col = db[col_name]
        for idx in idx_names:
            try:
                col.drop_index(idx)
                logger.info(f"  Índice antigo removido: {col_name}.{idx}")
            except OperationFailure:
                pass  # índice não existe — tudo bem

    ensure_indexes(db, "ZPP_Producao", "zppprd")
    ensure_indexes(db, "ZPP_Paradas", "zppparadas")
    db[config.LOGS_COLLECTION].create_index(
        [("iniciado_em", DESCENDING)], name="idx_iniciado_em"
    )
    logger.info("Índices MongoDB verificados ✓")


def initialize_app() -> None:
    global _client, _scheduler

    _setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("ZPP PROCESSOR — Inicializando")
    logger.info("=" * 60)

    errors = config.validate_config()
    if errors:
        for e in errors:
            logger.error(f"  Config: {e}")
        raise RuntimeError("Configuração inválida")

    for d in [config.INPUT_DIR, config.OUTPUT_DIR, config.REJECTED_DIR, config.LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    _client[config.DB_NAME].command("ping")
    logger.info(f"MongoDB: {config.DB_NAME} ✓")

    _verify_replica_set(_client)
    _ensure_indexes(_client)

    _scheduler = ZPPScheduler(config.MONGO_URI, config.DB_NAME)
    _scheduler.start()

    logger.info(f"Porta: {config.PORT}")
    logger.info("ZPP PROCESSOR — Pronto")


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def require_level(min_level: int):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ok, user = validate_internal_headers(request.headers, min_level)
            if not ok:
                return jsonify({"status": "error", "motivo": "Não autenticado ou acesso negado."}), 401
            return f(*args, user=user, **kwargs)
        return wrapped
    return decorator


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health_check():
    try:
        _client[config.DB_NAME].command("ping")
        return jsonify({
            "status": "healthy",
            "mongodb": "connected",
            "scheduler": "running" if (_scheduler and _scheduler.running) else "stopped",
        }), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route("/upload/retroativo", methods=["POST"])
@require_level(3)
def upload_retroativo(user: dict):
    # Validar campos obrigatórios
    for campo in ("ano", "mes", "justificativa"):
        if not request.form.get(campo):
            return jsonify({
                "status": "error",
                "motivo": f"Campo obrigatório ausente: {campo}."
            }), 400

    if "file" not in request.files or request.files["file"].filename == "":
        return jsonify({"status": "error", "motivo": "Campo obrigatório ausente: file."}), 400

    file = request.files["file"]

    # Limite de tamanho: 50 MB
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 50 * 1024 * 1024:
        return jsonify({"status": "error", "motivo": "Arquivo excede o limite de 50 MB."}), 413

    try:
        ano = int(request.form["ano"])
        mes = int(request.form["mes"])
    except ValueError:
        return jsonify({"status": "error", "motivo": "Campos 'ano' e 'mes' devem ser inteiros."}), 400

    justificativa = request.form["justificativa"]
    mes_referencia = f"{ano}-{mes:02d}"
    operador = user.get("username", "desconhecido")

    # Salvar arquivo temporariamente para o pipeline
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        result = process_file(
            file_path=tmp_path,
            client=_client,
            canal="retroativo",
            operador=operador,
            mes_referencia_override=mes_referencia,
            justificativa=justificativa,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    # Inserir log
    try:
        _client[config.DB_NAME][config.LOGS_COLLECTION].insert_one(result.to_log_doc())
    except Exception as e:
        logging.getLogger(__name__).error(f"Falha ao inserir log: {e}")

    if result.status == "rejected":
        return jsonify({
            "status": "rejected",
            "motivo": result.motivo_rejeicao,
        }), 422

    if result.status == "failed":
        return jsonify({
            "status": "error",
            "motivo": "Erro interno durante o processamento.",
            "erro": result.erro,
        }), 500

    # Aviso de volume (se houver)
    aviso = None
    if result.registros_deletados > 0 and result.registros_inseridos < result.registros_deletados:
        pct = (1 - result.registros_inseridos / result.registros_deletados) * 100
        aviso = (
            f"Atenção: arquivo contém {result.registros_inseridos} registros; "
            f"substituindo {result.registros_deletados} existentes (redução de {pct:.0f}%)."
        )

    return jsonify({
        "status": "success",
        "tipo": result.tipo,
        "mes_referencia": result.mes_referencia,
        "registros_inseridos": result.registros_inseridos,
        "registros_deletados": result.registros_deletados,
        "strays_descartados": result.strays_descartados,
        "duplicatas_ignoradas": result.duplicatas_ignoradas,
        "inconsistencias": result.inconsistencias,
        "aviso": aviso,
    }), 200


@app.route("/logs", methods=["GET"])
@require_level(1)
def get_logs(user: dict):
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = min(int(request.args.get("per_page", 20)), 100)
        offset = (page - 1) * per_page

        filtro = {}
        if request.args.get("tipo"):
            filtro["tipo"] = request.args["tipo"]
        if request.args.get("canal"):
            filtro["canal"] = request.args["canal"]
        if request.args.get("status"):
            filtro["status"] = request.args["status"]
        if request.args.get("mes"):
            filtro["mes_referencia"] = request.args["mes"]

        col = _client[config.DB_NAME][config.LOGS_COLLECTION]
        total = col.count_documents(filtro)
        cursor = col.find(filtro).sort("iniciado_em", DESCENDING).skip(offset).limit(per_page)

        nivel = user.get("level", 1)
        items = []
        for doc in cursor:
            doc.pop("_id", None)
            if nivel < 3:
                doc["inconsistencias"] = None
                doc["erro"] = None
            items.append(doc)

        return jsonify({"page": page, "per_page": per_page, "total": total, "items": items}), 200

    except Exception as e:
        logging.getLogger(__name__).error(f"Erro em GET /logs: {e}")
        return jsonify({"status": "error", "motivo": str(e)}), 500


@app.route("/api/zpp/files/input", methods=["GET"])
def list_input_files():
    return _list_files(config.INPUT_DIR)


@app.route("/api/zpp/files/output", methods=["GET"])
def list_output_files():
    return _list_files(config.OUTPUT_DIR)


def _list_files(directory: Path):
    try:
        files = []
        if directory.exists():
            seen = set()
            for pattern in ["*.xlsx", "*.XLSX", "*.xls", "*.XLS"]:
                for fp in directory.glob(pattern):
                    if fp.name not in seen and not fp.name.startswith("~$"):
                        seen.add(fp.name)
                        stat = fp.stat()
                        files.append({
                            "filename": fp.name,
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        })
        files.sort(key=lambda x: x["modified_at"], reverse=True)
        return jsonify({"count": len(files), "files": files}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# Inicialização automática (necessária para Gunicorn)
# ---------------------------------------------------------------------------

initialize_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
