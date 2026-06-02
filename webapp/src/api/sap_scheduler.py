"""Endpoints REST do sap-scheduler — trigger manual de job + status.

POST /api/v1/sap-scheduler/trigger?tipo=zppprd
  → insere doc 'pendente' em sap_jobs com agendado_para=now-1min
  → daemon claim em ≤ 30s no próximo polling
  → resposta: {_id, status:"pendente", agendado_para}

GET /api/v1/sap-scheduler/status?tipo=zppprd
  → retorna estado atual do job mais recente (qualquer status)

Requer auth + level >= 3 (admin) — operação manual em produção.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pytz
from bson import ObjectId
from flask import jsonify, request
from flask_login import current_user, login_required

from src.database.connection import get_mongo_connection
from src.sap_scheduler.config import load_config

from . import api_bp

TIPOS_VALIDOS = {"zppprd", "zpp_nt0001"}


def _check_admin():
    """Retorna None se ok, ou (response, status) se negado."""
    if not current_user.is_authenticated:
        return jsonify({"error": "unauthorized"}), 401
    if getattr(current_user, "level", 0) < 3:
        return jsonify({"error": "forbidden — requer level 3 (admin)"}), 403
    return None


@api_bp.route("/sap-scheduler/trigger", methods=["POST"])
@login_required
def trigger_job():
    """Dispara job manual — insere doc 'pendente'.

    Body (JSON) OU query string:
      - tipo: str — "zppprd" ou "zpp_nt0001"
      - delay_segundos: int (opcional, default 0) — agendado_para = now + delay
        (delay=0 → daemon claim imediato; delay>0 → claim depois do delay)
    """
    deny = _check_admin()
    if deny:
        return deny

    body = request.get_json(silent=True) or {}
    tipo = (body.get("tipo") or request.args.get("tipo") or "").strip().lower()
    delay = body.get("delay_segundos") or request.args.get("delay_segundos") or 0
    try:
        delay = int(delay)
    except (ValueError, TypeError):
        return jsonify({"error": "delay_segundos deve ser inteiro"}), 400

    if tipo not in TIPOS_VALIDOS:
        return jsonify({"error": f"tipo invalido. Aceita: {sorted(TIPOS_VALIDOS)}"}), 400

    try:
        cfg = load_config()
        coll = get_mongo_connection(cfg.collection)
        if coll is None:
            return jsonify({"error": "Mongo offline"}), 503

        agora_utc = datetime.now(tz=pytz.UTC)
        agendado_para = agora_utc + timedelta(seconds=delay)

        doc = {
            "tipo": tipo,
            "parametros": {
                "trigger_manual": True,
                "trigger_user": current_user.username if hasattr(current_user, "username") else "?",
            },
            "status": "pendente",
            "agendado_para": agendado_para,
            "criado_em": agora_utc,
            "iniciado_em": None,
            "concluido_em": None,
            "resultado": None,
            "erro": None,
        }
        result = coll.insert_one(doc)
        return jsonify({
            "_id": str(result.inserted_id),
            "tipo": tipo,
            "status": "pendente",
            "agendado_para": agendado_para.isoformat(),
            "delay_segundos": delay,
            "mensagem": (
                "job inserido — daemon claim em ate "
                f"{cfg.janela_tick_segundos}s (polling)"
            ),
        }), 201
    except Exception as e:
        return jsonify({"error": f"falha ao inserir job: {e}"}), 500


@api_bp.route("/sap-scheduler/status", methods=["GET"])
@login_required
def status_job():
    """Retorna estado do job mais recente.

    Query params:
      - tipo: str (opcional — sem filtro retorna mais recente de qualquer tipo)
      - _id: str (opcional — busca por _id específico)
    """
    deny = _check_admin()
    if deny:
        return deny

    tipo = (request.args.get("tipo") or "").strip().lower() or None
    _id_raw = request.args.get("_id")

    try:
        cfg = load_config()
        coll = get_mongo_connection(cfg.collection)
        if coll is None:
            return jsonify({"error": "Mongo offline"}), 503

        if _id_raw:
            try:
                doc = coll.find_one({"_id": ObjectId(_id_raw)})
            except Exception:
                return jsonify({"error": f"_id invalido: {_id_raw}"}), 400
        else:
            filtro = {"tipo": tipo} if tipo else {}
            doc = coll.find_one(filtro, sort=[("criado_em", -1)])

        if doc is None:
            return jsonify({"error": "nenhum job encontrado"}), 404

        # Serializar
        doc["_id"] = str(doc["_id"])
        for k in ("agendado_para", "criado_em", "iniciado_em", "concluido_em"):
            if doc.get(k):
                doc[k] = doc[k].isoformat()
        return jsonify(doc), 200
    except Exception as e:
        return jsonify({"error": f"falha consulta: {e}"}), 500


@api_bp.route("/sap-scheduler/recent", methods=["GET"])
@login_required
def recent_jobs():
    """Retorna últimos N jobs (max 50). Útil pra audit visual rápido.

    Query params:
      - limit: int (default 10, max 50)
    """
    deny = _check_admin()
    if deny:
        return deny

    try:
        limit = int(request.args.get("limit", 10))
    except (ValueError, TypeError):
        limit = 10
    limit = max(1, min(limit, 50))

    try:
        cfg = load_config()
        coll = get_mongo_connection(cfg.collection)
        if coll is None:
            return jsonify({"error": "Mongo offline"}), 503

        docs = list(coll.find({}, sort=[("criado_em", -1)], limit=limit))
        for d in docs:
            d["_id"] = str(d["_id"])
            for k in ("agendado_para", "criado_em", "iniciado_em", "concluido_em"):
                if d.get(k):
                    d[k] = d[k].isoformat()
        return jsonify({"count": len(docs), "jobs": docs}), 200
    except Exception as e:
        return jsonify({"error": f"falha consulta: {e}"}), 500
