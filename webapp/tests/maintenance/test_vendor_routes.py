"""Rota estática das bibliotecas vendorizadas (`/vendor/...`).

O que estes testes seguram:

1. **O bundle do Excalidraw é servido localmente.** Se alguém apagar a pasta do vendor
   ou mudar o caminho da rota, o diagrama abre em branco na fábrica — que é offline —
   e o defeito só apareceria lá.
2. **Nada fora de `src/vendor/` sai pela rota.** Um caminho com `..` não pode alcançar
   o código-fonte do webapp.
"""
import sys
from pathlib import Path

import pytest
from flask import Flask

_RAIZ_SRC = Path(__file__).resolve().parents[2]
if str(_RAIZ_SRC) not in sys.path:
    sys.path.insert(0, str(_RAIZ_SRC))

from src.callbacks_registers.vendor_routes import register_vendor_routes  # noqa: E402


@pytest.fixture()
def cliente():
    app = Flask(__name__)
    register_vendor_routes(app)
    return app.test_client()


class TestVendorEstatico:
    def test_entry_do_excalidraw_e_servido(self, cliente):
        """O ponto de entrada do bundle responde — é o que o diagrama importa."""
        r = cliente.get("/vendor/excalidraw/entry.js")
        assert r.status_code == 200
        assert "javascript" in r.headers["Content-Type"]

    def test_css_do_excalidraw_e_servido(self, cliente):
        r = cliente.get("/vendor/excalidraw/index.css")
        assert r.status_code == 200
        assert "text/css" in r.headers["Content-Type"]

    def test_cache_longo(self, cliente):
        """Os nomes dos arquivos carregam o hash do conteúdo, então cache longo é seguro."""
        r = cliente.get("/vendor/excalidraw/entry.js")
        assert "max-age=31536000" in r.headers.get("Cache-Control", "")

    @pytest.mark.parametrize("caminho", [
        "/vendor/../app.py",
        "/vendor/excalidraw/../../app.py",
        "/vendor/excalidraw/../../callbacks.py",
    ])
    def test_nao_escapa_da_pasta_do_vendor(self, cliente, caminho):
        assert cliente.get(caminho).status_code == 404

    def test_arquivo_inexistente(self, cliente):
        assert cliente.get("/vendor/excalidraw/nao-existe.js").status_code == 404


class TestVendorOffline:
    """O vendor existe para a fábrica funcionar sem internet (BR-AF3-08)."""

    # Só o iframe ficou (ver 05-design DS-AF3-01): o mount nativo saiu de `assets/`
    # porque o Dash injeta essa pasta em todas as páginas, e ele carregaria em telas
    # que não têm diagrama nenhum. Segue preservado em .dev-docs, fora do app.
    ASSETS = ("src/assets/fa_excalidraw.html",)

    @pytest.mark.parametrize("relativo", ASSETS)
    def test_asset_nao_aponta_para_cdn(self, relativo):
        texto = (_RAIZ_SRC / relativo).read_text(encoding="utf-8")
        for cdn in ("esm.sh", "unpkg.com", "cdn.jsdelivr.net"):
            assert cdn not in texto, f"{relativo} ainda busca do CDN {cdn}"

    @pytest.mark.parametrize("relativo", ASSETS)
    def test_asset_aponta_para_o_vendor_local(self, relativo):
        texto = (_RAIZ_SRC / relativo).read_text(encoding="utf-8")
        assert "/vendor/excalidraw/entry.js" in texto

    def test_fontes_do_excalidraw_presentes(self):
        """Sem as fontes, o texto dos balões sai na fonte errada."""
        fontes = _RAIZ_SRC / "src/vendor/excalidraw/fonts"
        assert (fontes / "Excalifont").is_dir()
        assert (fontes / "Nunito").is_dir()
