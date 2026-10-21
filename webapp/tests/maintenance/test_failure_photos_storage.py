"""
Testes de src/utils/failure_photos_storage.py — camada de storage das fotos da
Análise de Falhas. Usa `tmp_path` como raiz (via env FAILURE_PHOTOS_ROOT), sem CIFS.

Requer Pillow (já no requirements).
"""

import io

import pytest
from PIL import Image

from src.utils import failure_photos_storage as st

OID = "507f1f77bcf86cd799439011"
MES = "202606"


@pytest.fixture(autouse=True)
def _raiz_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("FAILURE_PHOTOS_ROOT", str(tmp_path))
    return tmp_path


def _png(cor=(200, 30, 30), tam=(800, 600)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", tam, cor).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg(tam=(1000, 700)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", tam, (10, 120, 200)).save(buf, format="JPEG")
    return buf.getvalue()


class TestSalvar:
    def test_grava_original_e_thumb(self, _raiz_tmp):
        meta = st.salvar(OID, MES, _jpeg(), "image/jpeg")
        assert meta["arquivo"].endswith(".jpg")
        assert meta["largura"] == 1000 and meta["altura"] == 700
        orig = st.caminho(OID, MES, meta["arquivo"])
        thumb = st.caminho(OID, MES, meta["thumb"], thumb=True)
        assert orig is not None and orig.is_file()
        assert thumb is not None and thumb.is_file()
        # a miniatura é menor que o original em bytes
        assert thumb.stat().st_size < orig.stat().st_size

    def test_thumb_limitada_a_320(self, _raiz_tmp):
        meta = st.salvar(OID, MES, _jpeg(tam=(2000, 1000)), "image/jpeg")
        thumb = st.caminho(OID, MES, meta["thumb"], thumb=True)
        with Image.open(thumb) as im:
            assert max(im.size) <= st.THUMB_LADO

    def test_remove_exif(self, _raiz_tmp):
        meta = st.salvar(OID, MES, _jpeg(), "image/jpeg")
        orig = st.caminho(OID, MES, meta["arquivo"])
        with Image.open(orig) as im:
            assert not getattr(im, "_getexif", lambda: None)()  # sem EXIF

    def test_mime_invalido(self, _raiz_tmp):
        with pytest.raises(ValueError):
            st.salvar(OID, MES, _png(), "image/gif")

    def test_tamanho_excede(self, _raiz_tmp):
        grande = b"x" * (st.MAX_BYTES + 1)
        with pytest.raises(ValueError):
            st.salvar(OID, MES, grande, "image/jpeg")

    def test_png_preserva_formato(self, _raiz_tmp):
        meta = st.salvar(OID, MES, _png(), "image/png")
        assert meta["arquivo"].endswith(".png")


class TestSeguranca:
    def test_seguro_bloqueia_traversal(self, _raiz_tmp):
        base = st._pasta(OID, MES)
        assert st._seguro(base, "../../etc/passwd") is None
        assert st._seguro(base, "..") is None

    def test_seguro_aceita_thumb_subpasta(self, _raiz_tmp):
        base = st._pasta(OID, MES)
        assert st._seguro(base, ".thumbs/abc.jpg") is not None

    def test_caminho_inexistente_retorna_none(self, _raiz_tmp):
        assert st.caminho(OID, MES, "nao-existe.jpg") is None


class TestExcluir:
    def test_hard_delete_idempotente(self, _raiz_tmp):
        meta = st.salvar(OID, MES, _jpeg(), "image/jpeg")
        assert st.caminho(OID, MES, meta["arquivo"]) is not None
        st.excluir(OID, MES, meta["arquivo"], meta["thumb"])
        assert st.caminho(OID, MES, meta["arquivo"]) is None
        assert st.caminho(OID, MES, meta["thumb"], thumb=True) is None
        # segunda chamada não levanta
        st.excluir(OID, MES, meta["arquivo"], meta["thumb"])


class TestNomePasta:
    def _analise(self, equip_nome="PRENSA-02", causa="201", id_="6a59100e2b90ecf82ebef8de",
                 chave="PRENS002_202606_201_1bfe974d"):
        return {"id": id_, "parada_chave": chave,
                "parada": {"equipamento_nome": equip_nome, "causa": causa}}

    def test_slug_legivel_com_id_curto(self):
        assert st.nome_pasta_analise(self._analise()) == "PRENSA-02_201_6a59100e"

    def test_sanitiza_caracteres_inseguros(self):
        nome = st.nome_pasta_analise(self._analise(equip_nome="Prensa 02 /X", causa="S 201"))
        assert "/" not in nome and " " not in nome
        assert nome.endswith("_6a59100e")

    def test_fallback_sem_equip(self):
        a = {"id": "abcdef012345", "parada": {}}
        assert st.nome_pasta_analise(a) == "equip_causa_abcdef01"

    def test_subpasta_rel(self):
        assert st.subpasta_rel(self._analise()) == "2026/06/PRENSA-02_201_6a59100e"

    def test_mes_ref_da_chave(self):
        assert st.mes_ref(self._analise()) == "202606"


class TestRotacionar:
    def test_gira_90_troca_dimensoes_no_arquivo(self, _raiz_tmp):
        meta = st.salvar(OID, MES, _jpeg(tam=(1000, 600)), "image/jpeg")
        dims = st.rotacionar(OID, MES, meta["arquivo"], meta["thumb"], 90, "image/jpeg")
        assert dims["largura"] == 600 and dims["altura"] == 1000
        with Image.open(st.caminho(OID, MES, meta["arquivo"])) as im:
            assert im.size == (600, 1000)
        # thumbnail regenerada continua ≤ 320
        with Image.open(st.caminho(OID, MES, meta["thumb"], thumb=True)) as im:
            assert max(im.size) <= st.THUMB_LADO

    def test_gira_180_mantem_dimensoes(self, _raiz_tmp):
        meta = st.salvar(OID, MES, _jpeg(tam=(800, 500)), "image/jpeg")
        dims = st.rotacionar(OID, MES, meta["arquivo"], meta["thumb"], 180, "image/jpeg")
        assert dims["largura"] == 800 and dims["altura"] == 500

    def test_graus_invalido(self, _raiz_tmp):
        meta = st.salvar(OID, MES, _jpeg(), "image/jpeg")
        with pytest.raises(ValueError):
            st.rotacionar(OID, MES, meta["arquivo"], meta["thumb"], 45, "image/jpeg")

    def test_arquivo_ausente(self, _raiz_tmp):
        with pytest.raises(st.PhotosStorageError):
            st.rotacionar(OID, MES, "nao.jpg", "nao.jpg", 90, "image/jpeg")


class TestDisponivel:
    def test_disponivel_true_em_pasta_gravavel(self, _raiz_tmp):
        assert st.disponivel() is True

    def test_pasta_por_mes(self, _raiz_tmp):
        p = st._pasta(OID, "202606")
        assert p.parts[-3:] == ("2026", "06", OID)
