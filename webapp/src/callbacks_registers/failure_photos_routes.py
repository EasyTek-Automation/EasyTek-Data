# src/callbacks_registers/failure_photos_routes.py

"""
Rotas Flask das fotos da Análise de Falhas (DS-04 do SDD analise-falhas-fotos).

Upload/serve/delete/legenda de binário não passam bem pelo protocolo do Dash, então
são rotas Flask no `app.server` (padrão dos exports de PDF do workflow/gantt).

Segurança: toda rota exige login + acesso à análise (perfil `manutencao` nível ≥ 2,
mesma regra da página); DELETE acrescenta autoria (autor da foto ou nível 3). O caminho
do arquivo nunca vem do cliente — usa-se o `foto_id` para achar a ficha no Mongo e ler
o nome real gravado (anti path traversal, reforçado por `storage._seguro`).
"""

from flask import abort, jsonify, request, send_file
from flask_login import current_user

from src.utils import failure_analysis_db as fdb
from src.utils import failure_photos_storage as storage
from src.utils.permissions import check_access

ROTA_ISHIKAWA = "/maintenance/analise-de-falhas/ishikawa"



def _autorizar(analysis_id: str) -> dict:
    """Login + acesso à análise; carrega a análise. Aborta com o status certo."""
    if not getattr(current_user, "is_authenticated", False):
        abort(401)
    permitido, _ = check_access(current_user, ROTA_ISHIKAWA)
    if not permitido:
        abort(403)
    analise = fdb.carregar_por_id(analysis_id)
    if not analise:
        abort(404)
    return analise


def _foto(analise: dict, foto_id: str) -> dict:
    """Acha a ficha da foto na análise, ou 404."""
    item = next((f for f in (analise.get("fotos") or []) if f.get("id") == foto_id), None)
    if not item:
        abort(404)
    return item


def register_failure_photos_routes(server):
    """Registra as rotas de foto no servidor Flask (chamado de callbacks.py)."""

    base = "/api/failure-analysis/<analysis_id>/photos"

    @server.route(base, methods=["POST"])
    def fa_foto_upload(analysis_id):
        analise = _autorizar(analysis_id)
        if not storage.disponivel():
            return jsonify(erro="Armazenamento de fotos indisponível."), 507

        arquivo = request.files.get("file")
        if arquivo is None or not arquivo.filename:
            return jsonify(erro="Nenhum arquivo enviado."), 400
        dados = arquivo.read()
        mime = arquivo.mimetype or ""
        try:
            meta = storage.salvar(storage.nome_pasta_analise(analise), storage.mes_ref(analise), dados, mime)
        except ValueError as e:
            # tipo inválido ou tamanho acima do teto
            codigo = 413 if "MB" in str(e) else 400
            return jsonify(erro=str(e)), codigo
        except storage.PhotosStorageError as e:
            return jsonify(erro=str(e)), 507

        meta["legenda"] = request.form.get("legenda") or ""
        ok, msg, item = fdb.adicionar_foto(
            analysis_id, meta, getattr(current_user, "username", ""))
        if not ok:
            # desfaz o arquivo órfão gravado no file server
            try:
                storage.excluir(storage.nome_pasta_analise(analise), storage.mes_ref(analise), meta["arquivo"], meta["thumb"])
            except storage.PhotosStorageError:
                pass
            return jsonify(erro=msg), 400
        return jsonify(item), 201

    @server.route(base + "/<foto_id>/thumb")
    def fa_foto_thumb(analysis_id, foto_id):
        analise = _autorizar(analysis_id)
        item = _foto(analise, foto_id)
        caminho = storage.caminho(storage.nome_pasta_analise(analise), storage.mes_ref(analise), item.get("thumb"), thumb=True)
        if caminho is None:
            abort(404)
        return send_file(caminho, mimetype=item.get("mime"), max_age=300)

    @server.route(base + "/<foto_id>/full")
    def fa_foto_full(analysis_id, foto_id):
        analise = _autorizar(analysis_id)
        item = _foto(analise, foto_id)
        caminho = storage.caminho(storage.nome_pasta_analise(analise), storage.mes_ref(analise), item.get("arquivo"))
        if caminho is None:
            abort(404)
        return send_file(caminho, mimetype=item.get("mime"), max_age=300)

    @server.route(base + "/<foto_id>", methods=["DELETE"])
    def fa_foto_delete(analysis_id, foto_id):
        analise = _autorizar(analysis_id)
        ok, msg, item = fdb.remover_foto(
            analysis_id, foto_id,
            getattr(current_user, "username", ""),
            nivel=int(getattr(current_user, "level", 0) or 0))
        if not ok:
            return jsonify(erro=msg), 403
        try:
            storage.excluir(storage.nome_pasta_analise(analise), storage.mes_ref(analise), item.get("arquivo"), item.get("thumb"))
        except storage.PhotosStorageError:
            pass  # ficha já removida; arquivo órfão não bloqueia a resposta
        return "", 204

    @server.route(base + "/<foto_id>", methods=["PATCH"])
    def fa_foto_legenda(analysis_id, foto_id):
        _autorizar(analysis_id)
        legenda = (request.get_json(silent=True) or {}).get("legenda", "")
        ok, msg = fdb.editar_legenda_foto(
            analysis_id, foto_id, legenda, getattr(current_user, "username", ""))
        if not ok:
            return jsonify(erro=msg), 400
        return jsonify(ok=True, legenda=legenda.strip()), 200

    @server.route(base + "/<foto_id>/rotate", methods=["POST"])
    def fa_foto_rotate(analysis_id, foto_id):
        """Persiste a rotação (múltiplo de 90, horário) no arquivo do file server e
        atualiza as dimensões/rev no Mongo. Edição → exige análise aberta (nível 2
        manutenção pela guarda comum)."""
        analise = _autorizar(analysis_id)
        if analise.get("status") != fdb.STATUS_ABERTA:
            return jsonify(erro="Análise concluída — reabra para editar fotos."), 403
        item = _foto(analise, foto_id)
        graus = int((request.get_json(silent=True) or {}).get("graus", 0)) % 360
        if graus == 0:
            return jsonify(ok=True), 200
        if not storage.disponivel():
            return jsonify(erro="Armazenamento de fotos indisponível."), 507
        try:
            dims = storage.rotacionar(
                storage.nome_pasta_analise(analise), storage.mes_ref(analise),
                item.get("arquivo"), item.get("thumb"), graus, item.get("mime"))
        except ValueError as e:
            return jsonify(erro=str(e)), 400
        except storage.PhotosStorageError as e:
            return jsonify(erro=str(e)), 507
        fdb.atualizar_dims_foto(analysis_id, foto_id, dims["largura"], dims["altura"])
        return jsonify(ok=True, **dims), 200
