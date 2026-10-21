# src/callbacks_registers/failure_diagram_routes.py

"""
Rotas da imagem do diagrama (IM-AF3-08 do SDD analise-falhas-v3).

O navegador exporta o desenho do quadro (SVG + PNG de reserva) e manda para cá; a
imagem fica na pasta da análise e o slide a usa no lugar do redesenho do servidor.

- `GET  .../diagram/estado?versao=N` → `{"atual": bool}`: a imagem guardada ainda
  desenha a árvore do banco? Se sim, o navegador nem exporta (poupa o envio).
- `POST .../diagram` `{"svg", "png" (base64), "versao"}` → grava.

`versao` é a versão da análise que o navegador tem na tela. Se o banco já está em outra
(alguém salvou no meio), a imagem seria de uma árvore velha: recusa com 409.

Mesma guarda das fotos: login + acesso à página. Gravar a imagem não altera a análise
(nem `versao`), então vale também para análise concluída.
"""

import base64
import binascii

from flask import jsonify, request
from flask_login import current_user

from src.callbacks_registers.failure_photos_routes import _autorizar
from src.utils import failure_diagram_image as di
from src.utils import failure_photos_storage as storage


def register_failure_diagram_routes(server):
    """Registra as rotas da imagem do diagrama no servidor Flask."""

    base = "/api/failure-analysis/<analysis_id>/diagram"

    @server.route(base + "/estado")
    def fa_diagrama_estado(analysis_id):
        analise = _autorizar(analysis_id)
        versao = request.args.get("versao", type=int)
        if versao is not None and versao != analise.get("versao"):
            return jsonify(atual=False, versao_banco=analise.get("versao")), 200
        return jsonify(atual=di.atual(analise)), 200

    @server.route(base, methods=["POST"])
    def fa_diagrama_salvar(analysis_id):
        analise = _autorizar(analysis_id)
        corpo = request.get_json(silent=True) or {}
        if corpo.get("versao") != analise.get("versao"):
            return jsonify(erro="A análise mudou desde que a imagem foi gerada."), 409
        svg = (corpo.get("svg") or "").encode("utf-8")
        try:
            png = base64.b64decode(corpo.get("png") or "", validate=True)
        except (binascii.Error, ValueError):
            return jsonify(erro="PNG em base64 inválido."), 400
        try:
            ficha = di.salvar(analise, svg, png, getattr(current_user, "username", ""))
        except di.DiagramaInvalido as e:
            return jsonify(erro=str(e)), 400
        except storage.PhotosStorageError as e:
            return jsonify(erro=str(e)), 507
        return jsonify(ok=True, gerado_em=ficha["gerado_em"]), 201
