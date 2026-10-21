"""
Testes de src/utils/failure_diagram_image.py — imagem do diagrama (SVG + PNG) guardada
para o slide (IM-AF3-08). Raiz em `tmp_path` via FAILURE_PHOTOS_ROOT, sem CIFS.
"""

import io
import json

import pytest
from PIL import Image

from src.utils import failure_diagram_image as di

SVG = b'<svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _no(i, pai=None, **kw):
    base = {"id": i, "parent_id": pai, "titulo": f"balão {i}", "tipo": "CAUSE",
            "is_root_cause": False, "position_x": 10.2, "position_y": 20.7, "duration_min": 5}
    base.update(kw)
    return base


def _analise(nos=None):
    return {"id": "6a5f525ea933ebdb5110495d", "parada_chave": "LONGI002_202607_201_144bf9f7",
            "parada": {"equipamento_nome": "LCL-4,5", "causa": "201"}, "versao": 3,
            "nos": nos if nos is not None else [_no("r", tipo="ROOT"), _no("a", "r")]}


@pytest.fixture(autouse=True)
def _raiz_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("FAILURE_PHOTOS_ROOT", str(tmp_path))
    return tmp_path


class TestAssinatura:
    def test_mesma_arvore_mesma_assinatura_em_qualquer_ordem(self):
        a = [_no("r", tipo="ROOT"), _no("a", "r")]
        assert di.assinatura(a) == di.assinatura(list(reversed(a)))

    def test_mover_balao_muda(self):
        a = [_no("a")]
        assert di.assinatura(a) != di.assinatura([_no("a", position_x=60)])

    def test_meio_pixel_de_diferenca_nao_muda(self):
        # posição gravada como float — arredondar evita invalidar por ruído
        assert di.assinatura([_no("a", position_x=10.2)]) == di.assinatura([_no("a", position_x=10.4)])

    def test_texto_causa_raiz_ligacao_e_tempo_mudam(self):
        base = di.assinatura([_no("a", "r")])
        assert base != di.assinatura([_no("a", "r", titulo="outro")])
        assert base != di.assinatura([_no("a", "r", is_root_cause=True)])
        assert base != di.assinatura([_no("a", "x")])
        assert base != di.assinatura([_no("a", "r", duration_min=9)])

    def test_espaco_na_ponta_do_titulo_nao_muda(self):
        assert di.assinatura([_no("a", titulo="x ")]) == di.assinatura([_no("a", titulo="x")])

    def test_sem_posicao_e_aceito(self):
        assert di.assinatura([_no("a", position_x=None, position_y=None)])


class TestValidacao:
    def test_svg_valido(self):
        di.validar_svg(SVG)
        di.validar_svg(b'<?xml version="1.0"?>\n' + SVG)

    @pytest.mark.parametrize("ruim", [
        b"",
        b"<html><body>oi</body></html>",
        SVG.replace(b"<rect", b"<script>alert(1)</script><rect"),
        SVG.replace(b"<rect", b'<rect onload="alert(1)"'),
        SVG.replace(b"<rect", b'<a href="javascript:alert(1)"><rect'),
        SVG.replace(b"<rect", b"<foreignObject><div/></foreignObject><rect"),
    ])
    def test_svg_recusado(self, ruim):
        with pytest.raises(di.DiagramaInvalido):
            di.validar_svg(ruim)

    def test_svg_acima_do_teto(self):
        with pytest.raises(di.DiagramaInvalido):
            di.validar_svg(SVG + b" " * di.MAX_SVG)

    def test_png_recusado_se_nao_for_png(self):
        with pytest.raises(di.DiagramaInvalido):
            di.validar_png(b"GIF89a....")


class TestSalvarECarregar:
    def test_grava_e_carrega_quando_a_arvore_bate(self, _raiz_tmp):
        an = _analise()
        ficha = di.salvar(an, SVG, _png(), "rodolfo")
        assert ficha["assinatura"] == di.assinatura(an["nos"]) and ficha["gerado_por"] == "rodolfo"
        assert list(_raiz_tmp.glob("2026/07/*/.diagrama/diagrama.svg"))
        img = di.carregar_valido(an)
        assert img["svg"] == SVG and img["png"].startswith(b"\x89PNG")

    def test_arvore_mudou_depois_volta_none(self):
        an = _analise()
        di.salvar(an, SVG, _png())
        an["nos"] = an["nos"] + [_no("b", "r")]          # alguém salvou pela v2
        assert di.carregar_valido(an) is None
        assert di.atual(an) is False

    def test_sem_imagem_volta_none(self):
        assert di.carregar_valido(_analise()) is None

    def test_regravar_substitui(self):
        an = _analise()
        di.salvar(an, SVG, _png())
        novo = SVG.replace(b'width="10"', b'width="9"')
        an["nos"][1]["titulo"] = "novo"
        di.salvar(an, novo, _png())
        assert di.carregar_valido(an)["svg"] == novo

    def test_ficha_corrompida_volta_none(self, _raiz_tmp):
        an = _analise()
        di.salvar(an, SVG, _png())
        (next(_raiz_tmp.glob("2026/07/*/.diagrama")) / "diagrama.json").write_text("{quebrado")
        assert di.carregar_valido(an) is None

    def test_arquivo_invalido_nao_grava_nada(self, _raiz_tmp):
        with pytest.raises(di.DiagramaInvalido):
            di.salvar(_analise(), b"<script/>", _png())
        assert not list(_raiz_tmp.rglob("diagrama.*"))

    def test_ficha_guarda_versao(self, _raiz_tmp):
        di.salvar(_analise(), SVG, _png())
        ficha = json.loads(next(_raiz_tmp.rglob("diagrama.json")).read_text())
        assert ficha["versao"] == 3
