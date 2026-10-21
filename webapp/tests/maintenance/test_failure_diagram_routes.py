"""Rotas da imagem do diagrama (IM-AF3-08): guarda de acesso, versão e validação."""
import base64
import io
import sys
from pathlib import Path

import pytest
from flask import Flask
from PIL import Image

_RAIZ_SRC = Path(__file__).resolve().parents[2]
if str(_RAIZ_SRC) not in sys.path:
    sys.path.insert(0, str(_RAIZ_SRC))

from src.callbacks_registers import failure_diagram_routes as rotas  # noqa: E402
from src.callbacks_registers import failure_photos_routes as fotos  # noqa: E402
from src.utils import failure_diagram_image as di  # noqa: E402

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'
AID = "6a5f525ea933ebdb5110495d"


def _png_b64():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 255, 255)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class _Usuario:
    is_authenticated = True
    username = "rodolfo"
    level = 2


@pytest.fixture()
def estado(tmp_path, monkeypatch):
    monkeypatch.setenv("FAILURE_PHOTOS_ROOT", str(tmp_path))
    analise = {"id": AID, "parada_chave": "LONGI002_202607_201_144bf9f7", "versao": 5,
               "parada": {"equipamento_nome": "LCL-4,5", "causa": "201"},
               "nos": [{"id": "r", "tipo": "ROOT", "titulo": "Parada"}]}
    st = {"analise": analise, "acesso": True, "usuario": _Usuario()}
    monkeypatch.setattr(fotos, "current_user", st["usuario"])
    monkeypatch.setattr(rotas, "current_user", st["usuario"])
    monkeypatch.setattr(fotos, "check_access", lambda u, r: (st["acesso"], ""))
    monkeypatch.setattr(fotos.fdb, "carregar_por_id",
                        lambda i: st["analise"] if i == AID else None)
    return st


@pytest.fixture()
def cliente(estado):
    app = Flask(__name__)
    rotas.register_failure_diagram_routes(app)
    return app.test_client()


def _post(cliente, **kw):
    corpo = {"svg": SVG, "png": _png_b64(), "versao": 5}
    corpo.update(kw)
    return cliente.post(f"/api/failure-analysis/{AID}/diagram", json=corpo)


class TestPost:
    def test_grava_e_estado_fica_atual(self, cliente):
        assert cliente.get(f"/api/failure-analysis/{AID}/diagram/estado").json == {"atual": False}
        assert _post(cliente).status_code == 201
        assert cliente.get(f"/api/failure-analysis/{AID}/diagram/estado?versao=5").json == {"atual": True}

    def test_versao_velha_recusada(self, cliente):
        assert _post(cliente, versao=4).status_code == 409

    def test_svg_com_script_recusado(self, cliente):
        r = _post(cliente, svg=SVG.replace("<rect", "<script>alert(1)</script><rect"))
        assert r.status_code == 400

    def test_png_que_nao_e_base64(self, cliente):
        assert _post(cliente, png="@@@").status_code == 400

    def test_sem_acesso(self, cliente, estado):
        estado["acesso"] = False
        assert _post(cliente).status_code == 403

    def test_sem_login(self, cliente, estado):
        estado["usuario"].is_authenticated = False
        assert _post(cliente).status_code == 401

    def test_analise_inexistente(self, cliente):
        r = cliente.post("/api/failure-analysis/000000000000000000000000/diagram", json={})
        assert r.status_code == 404


class TestEstado:
    def test_versao_diferente_nao_e_atual(self, cliente):
        _post(cliente)
        r = cliente.get(f"/api/failure-analysis/{AID}/diagram/estado?versao=6").json
        assert r["atual"] is False

    def test_arvore_mudou_nao_e_atual(self, cliente, estado):
        _post(cliente)
        estado["analise"]["nos"] = estado["analise"]["nos"] + [{"id": "a", "parent_id": "r"}]
        assert cliente.get(f"/api/failure-analysis/{AID}/diagram/estado").json["atual"] is False
        assert di.carregar_valido(estado["analise"]) is None
