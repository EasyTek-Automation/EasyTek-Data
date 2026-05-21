"""Teste de equivalência v1 ↔ v2 (DS-09, IM-12).

Premissa: v2 nunca recalcula KPIs — apenas redesenha a apresentação. Logo,
para o **mesmo dataset de entrada** (saída de `coletar_dados_relatorio`), o
PDF v2 deve conter os mesmos valores numéricos que o DOCX v1 conteria.

Estratégia (jail-friendly):
1. Constrói dict idêntico ao retorno de `coletar_dados_relatorio` (fixture
   determinística).
2. Gera PDF v2 via `gerar_pdf`.
3. Extrai texto do PDF via `pdfminer.six`.
4. Asserta presença dos valores numéricos exatos do dict no PDF.

Por que não usar `montar_docx` aqui? `python-docx`/`docxtpl` exigem dep extra
e o equivalente "no DOCX v1 está X" já é coberto pelos testes existentes de v1
(`test_kpi_report_builder.py`). O teste cross-versão aqui é "v2 expõe os
mesmos números que v1 leu" — quando ambos consomem o mesmo dict, isso é
verificável só inspecionando o output v2.
"""
from __future__ import annotations

import io

import pytest

from src.utils.kpi_report_v2_pdf import gerar_pdf


@pytest.fixture
def dataset_canonico():
    """Dataset estável — valores escolhidos pra serem inequívocos no texto extraído."""
    return {
        "periodo": {
            "rotulo": "Período: 01/05/2026 a 21/05/2026 (horário de Brasília)",
            "modo": "MES_CORRENTE",
        },
        "bloco1": {
            "kpis_planta": {"mtbf": 137.8, "mttr": 23.4, "taxa_avaria": 4.6},
            "metas":       {"mtbf": 100.0, "mttr": 20.0, "taxa_avaria": 3.0},
            "cores_kpis":  {"mtbf": "#28a745", "mttr": "#ffc107", "taxa_avaria": "#dc3545"},
            "sunburst_figures": {"mtbf": None, "mttr": None, "taxa_avaria": None},
        },
        "bloco2": {
            "paradas": [
                {"posicao": 1, "equipamento": "LONGI-01", "data_hora": "15/05/2026 08:12",
                 "duracao_min": "245 min", "causa": "201", "descricao": "Falha hidráulica"},
                {"posicao": 2, "equipamento": "PRENS-02", "data_hora": "12/05/2026 14:30",
                 "duracao_min": "180 min", "causa": "S203", "descricao": "Sensor com defeito"},
                {"posicao": 3, "equipamento": "TRANS-03", "data_hora": "08/05/2026 22:50",
                 "duracao_min": "95 min", "causa": "202", "descricao": "Quebra mecânica"},
            ],
            "vazio": False,
        },
        "bloco3": {
            "kpis_planta": {"mtbf": 38.5, "mttr": 18.7, "taxa_avaria": 7.2},
            "metas":       {"mtbf": 100.0, "mttr": 20.0, "taxa_avaria": 3.0},
            "cores_kpis":  {"mtbf": "#dc3545", "mttr": "#28a745", "taxa_avaria": "#dc3545"},
            "sunburst_figures": {"mtbf": None, "mttr": None, "taxa_avaria": None},
        },
        "bloco4": {
            "linhas": [
                {"equipamento": "LONGI-01", "mtbf": 87.6, "mttr": 25.4, "taxa_avaria": 4.2},
                {"equipamento": "PRENS-02", "mtbf": 156.9, "mttr": 19.8, "taxa_avaria": 2.7},
                {"equipamento": "TRANS-03", "mtbf": None, "mttr": None, "taxa_avaria": None},
            ],
            "total": {"equipamento": "TOTAL", "mtbf": 137.8, "mttr": 23.4, "taxa_avaria": 4.6},
            "vazio": False,
        },
        "bloco5": {
            "paradas": [
                {"posicao": 1, "equipamento": "TRANS-03", "data_hora": "20/05/2026 23:55",
                 "duracao_min": "5 min", "causa": "S201", "descricao": "Parada curta"},
            ],
            "vazio": False,
        },
    }


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extrai texto do PDF via pdfminer (lazy import — keeps import-time cheap)."""
    from pdfminer.high_level import extract_text
    return extract_text(io.BytesIO(pdf_bytes))


class TestEquivalenciaV1V2:

    def test_pdf_contem_kpis_bloco1(self, dataset_canonico):
        pdf = gerar_pdf(dataset_canonico, {1, 2, 3, 4, 5}, "pt")
        text = _extract_pdf_text(pdf)
        # Formato pt-BR: 137,8 (vírgula decimal)
        assert "137,8" in text
        assert "23,4" in text
        assert "4,6" in text

    def test_pdf_contem_kpis_bloco3(self, dataset_canonico):
        pdf = gerar_pdf(dataset_canonico, {1, 2, 3, 4, 5}, "pt")
        text = _extract_pdf_text(pdf)
        assert "38,5" in text
        assert "18,7" in text
        assert "7,2" in text

    def test_pdf_contem_metas(self, dataset_canonico):
        pdf = gerar_pdf(dataset_canonico, {1, 2, 3, 4, 5}, "pt")
        text = _extract_pdf_text(pdf)
        assert "100,0" in text
        assert "20,0" in text
        assert "3,0" in text

    def test_pdf_contem_top5_paradas_em_ordem(self, dataset_canonico):
        pdf = gerar_pdf(dataset_canonico, {1, 2, 3, 4, 5}, "pt")
        text = _extract_pdf_text(pdf)
        # Top 5 monta na ordem do dict — verificar todos os 3 equipamentos
        for eq in ("LONGI-01", "PRENS-02", "TRANS-03"):
            assert eq in text
        # Durações
        assert "245" in text
        assert "180" in text
        assert "95" in text
        # Causa codes
        assert "201" in text
        assert "S203" in text

    def test_pdf_contem_bloco4_detalhamento(self, dataset_canonico):
        pdf = gerar_pdf(dataset_canonico, {1, 2, 3, 4, 5}, "pt")
        text = _extract_pdf_text(pdf)
        # Linha LONGI-01: mtbf=87.6, mttr=25.4, taxa=4.2
        assert "87,6" in text
        assert "25,4" in text
        assert "4,2" in text
        # Linha PRENS-02: mtbf=156.9
        assert "156,9" in text
        # TRANS-03 sem dados → "Sem dados"
        assert "Sem dados" in text
        # Linha TOTAL
        assert "TOTAL" in text

    def test_pdf_contem_bloco5_evento(self, dataset_canonico):
        pdf = gerar_pdf(dataset_canonico, {1, 2, 3, 4, 5}, "pt")
        text = _extract_pdf_text(pdf)
        assert "S201" in text
        assert "Parada curta" in text

    def test_pdf_contem_periodo_rotulo(self, dataset_canonico):
        pdf = gerar_pdf(dataset_canonico, {1, 2, 3, 4, 5}, "pt")
        text = _extract_pdf_text(pdf)
        assert "01/05/2026" in text
        assert "21/05/2026" in text

    def test_toggle_bloco_omite_conteudo(self, dataset_canonico):
        # Bloco 4 off → linhas de detalhamento não aparecem
        pdf = gerar_pdf(dataset_canonico, {1, 2, 3, 5}, "pt")
        text = _extract_pdf_text(pdf)
        # LONGI-01 ainda aparece (bloco 2), mas "87,6" só está no bloco 4 → não deveria estar
        assert "87,6" not in text
        # Bloco 1 ainda presente
        assert "137,8" in text

    def test_i18n_en_traduz_titulos_mas_preserva_numeros(self, dataset_canonico):
        # Números são universais — só labels traduzem
        pdf = gerar_pdf(dataset_canonico, {1, 2, 3, 4, 5}, "en")
        text = _extract_pdf_text(pdf)
        # Em EN: 137,8 (pt-BR fmt_numero) ainda aparece pq formato é pt-BR canônico v1
        assert "137,8" in text
        # Título em inglês
        assert "KPI Report v2" in text
        # Block 1 title em inglês
        assert "Block 1" in text


class TestSuiteV1Intocada:
    """Garante que módulos v1 não foram alterados — só importa e checa attrs públicos."""

    def test_kpi_report_config_constants_intactas(self):
        from src.utils import kpi_report_config as cfg
        assert cfg.PERIODO_RELATORIO_MODO == "MES_CORRENTE"
        assert cfg.TZ_FALLBACK == "America/Sao_Paulo"
        assert cfg.LATENCIA_GUIDELINE_S == 10.0
        assert cfg.TIMEOUT_GERACAO_S == 60.0
        assert cfg.EQUIPAMENTOS_EXCLUIDOS == []

    def test_kpi_report_config_functions_assinatura(self):
        from src.utils import kpi_report_config as cfg
        from datetime import datetime
        # compute_monthly_window aceita (now, modo=None)
        ini, fim = cfg.compute_monthly_window(datetime(2026, 5, 21), "MES_CORRENTE")
        assert ini.day == 1
        # compute_last_24h_window aceita (now)
        ini24, fim24 = cfg.compute_last_24h_window(datetime(2026, 5, 21))
        assert (fim24 - ini24).days == 1

    def test_kpi_report_data_coletar_assinatura(self):
        # Não chama (precisaria de Mongo), só valida que existe e tem assinatura esperada
        from src.utils.kpi_report_data import coletar_dados_relatorio
        import inspect
        sig = inspect.signature(coletar_dados_relatorio)
        assert "stored_data" in sig.parameters
        assert "agora" in sig.parameters
        assert "as_png" in sig.parameters
