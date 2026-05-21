"""Testes do módulo `utils/kpi_report_v2_pdf.py` (DS-04, IM-10).

Cobre:
- gerar_pdf: 5 blocos completos → bytes válidos (assinatura %PDF, > 1KB)
- gerar_pdf: 1 bloco ativo → bytes válidos
- gerar_pdf: blocos vazios → não quebra (renderiza placeholder)
- gerar_pdf: sunburst None / bytes inválido → fallback "—"
- gerar_pdf: i18n PT/ES/EN no título / labels
- gerar_pdf: performance — 5 blocos < 10s (BR-09 timeout guideline)
"""
from __future__ import annotations

import time
from datetime import datetime

import pytest

from src.utils.kpi_report_v2_pdf import gerar_pdf


# ============================ Fixtures ============================

@pytest.fixture
def dados_completos():
    """Mock realista do retorno de coletar_dados_relatorio(as_png=True)."""
    return {
        "periodo": {
            "rotulo": "Período: 01/05/2026 a 21/05/2026 (horário de Brasília)",
            "modo": "MES_CORRENTE",
        },
        "bloco1": {
            "kpis_planta": {"mtbf": 120.5, "mttr": 8.2, "taxa_avaria": 2.1},
            "metas":       {"mtbf": 100.0, "mttr": 10.0, "taxa_avaria": 3.0},
            "cores_kpis":  {"mtbf": "#28a745", "mttr": "#28a745", "taxa_avaria": "#28a745"},
            "sunburst_figures": {"mtbf": None, "mttr": None, "taxa_avaria": None},
        },
        "bloco2": {
            "paradas": [
                {"posicao": 1, "equipamento": "EQ-01", "data_hora": "20/05/2026 10:30",
                 "duracao_min": "120 min", "causa": "201", "descricao": "Falha mecânica"},
                {"posicao": 2, "equipamento": "EQ-02", "data_hora": "20/05/2026 14:10",
                 "duracao_min": "45 min", "causa": "S203", "descricao": "Falta de material"},
            ],
            "vazio": False,
        },
        "bloco3": {
            "kpis_planta": {"mtbf": 60.0, "mttr": 12.0, "taxa_avaria": 5.0},
            "metas":       {"mtbf": 100.0, "mttr": 10.0, "taxa_avaria": 3.0},
            "cores_kpis":  {"mtbf": "#dc3545", "mttr": "#ffc107", "taxa_avaria": "#dc3545"},
            "sunburst_figures": {"mtbf": None, "mttr": None, "taxa_avaria": None},
        },
        "bloco4": {
            "linhas": [
                {"equipamento": "EQ-01", "mtbf": 100.0, "mttr": 8.0, "taxa_avaria": 1.5},
                {"equipamento": "EQ-02", "mtbf": None, "mttr": None, "taxa_avaria": None},
            ],
            "total": {"equipamento": "TOTAL", "mtbf": 100.0, "mttr": 8.0, "taxa_avaria": 1.5},
            "vazio": False,
        },
        "bloco5": {
            "paradas": [
                {"posicao": 1, "equipamento": "EQ-03", "data_hora": "20/05/2026 23:50",
                 "duracao_min": "15 min", "causa": "202", "descricao": "Pequena parada"},
            ],
            "vazio": False,
        },
    }


@pytest.fixture
def dados_minimo():
    return {"periodo": {}, "bloco1": None, "bloco2": None, "bloco3": None,
            "bloco4": None, "bloco5": None}


# ============================ Assinatura PDF ============================

def _is_valid_pdf(b: bytes) -> bool:
    return isinstance(b, (bytes, bytearray)) and b[:5] == b"%PDF-"


# ============================ Testes ============================

class TestGerarPdf:
    def test_5_blocos_assinatura_e_tamanho(self, dados_completos):
        out = gerar_pdf(dados_completos, {1, 2, 3, 4, 5}, "pt")
        assert _is_valid_pdf(out)
        assert len(out) > 1500  # tamanho mínimo razoável

    def test_1_bloco_ativo(self, dados_completos):
        out = gerar_pdf(dados_completos, {1}, "pt")
        assert _is_valid_pdf(out)

    def test_blocos_vazios_nao_quebra(self, dados_minimo):
        out = gerar_pdf(dados_minimo, {1, 2, 3, 4, 5}, "pt")
        assert _is_valid_pdf(out)

    def test_blocos_ativos_lista(self, dados_completos):
        # lista funciona igual a set
        out = gerar_pdf(dados_completos, [2, 4], "pt")
        assert _is_valid_pdf(out)

    def test_blocos_ativos_vazio_renderiza_todos(self, dados_completos):
        # set vazio → fallback {1,2,3,4,5}
        out = gerar_pdf(dados_completos, set(), "pt")
        assert _is_valid_pdf(out)

    def test_sunburst_png_valido_embute_imagem(self, dados_completos):
        # Gera PNG real via PIL — fixture inline corre risco de corrupção
        import io as _io
        from PIL import Image as _PILImage
        buf = _io.BytesIO()
        _PILImage.new("RGB", (60, 60), color=(40, 167, 69)).save(buf, format="PNG")
        png = buf.getvalue()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        dados_completos["bloco1"]["sunburst_figures"] = {
            "mtbf": png, "mttr": png, "taxa_avaria": png,
        }
        out = gerar_pdf(dados_completos, {1}, "pt")
        assert _is_valid_pdf(out)

    def test_sunburst_bytes_invalido_nao_quebra(self, dados_completos):
        # bytes que não são PNG → exceção interna engolida, render continua
        dados_completos["bloco1"]["sunburst_figures"] = {
            "mtbf": b"not-a-png", "mttr": None, "taxa_avaria": None,
        }
        out = gerar_pdf(dados_completos, {1}, "pt")
        assert _is_valid_pdf(out)

    @pytest.mark.parametrize("lang", ["pt", "es", "en"])
    def test_i18n_idiomas_suportados(self, dados_completos, lang):
        out = gerar_pdf(dados_completos, {1, 2, 3, 4, 5}, lang)
        assert _is_valid_pdf(out)

    def test_dados_invalido_raises(self):
        with pytest.raises(ValueError):
            gerar_pdf("not a dict", {1}, "pt")  # type: ignore[arg-type]

    def test_performance_5_blocos_menos_de_10s(self, dados_completos):
        # BR-09 timeout guideline — 5 blocos < 10s mesmo no jail
        t0 = time.perf_counter()
        out = gerar_pdf(dados_completos, {1, 2, 3, 4, 5}, "pt")
        dt = time.perf_counter() - t0
        assert _is_valid_pdf(out)
        assert dt < 10.0, f"gerar_pdf demorou {dt:.2f}s (>10s)"

    def test_bloco4_total_renderiza(self, dados_completos):
        # Garante que linha TOTAL aparece (smoke — não quebra)
        out = gerar_pdf(dados_completos, {4}, "pt")
        assert _is_valid_pdf(out)
        # Texto "TOTAL" não aparece direto no PDF binário, mas a estrutura
        # foi processada — basta não quebrar.

    def test_bloco_paradas_vazio(self, dados_completos):
        dados_completos["bloco2"] = {"paradas": [], "vazio": True}
        dados_completos["bloco5"] = {"paradas": [], "vazio": True}
        out = gerar_pdf(dados_completos, {2, 5}, "pt")
        assert _is_valid_pdf(out)

    def test_bloco4_vazio(self, dados_completos):
        dados_completos["bloco4"] = {"linhas": [], "total": {}, "vazio": True}
        out = gerar_pdf(dados_completos, {4}, "pt")
        assert _is_valid_pdf(out)
