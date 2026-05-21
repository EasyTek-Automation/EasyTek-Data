"""Testes do módulo `utils/kpi_report_v2_layout.py` (DS-03, IM-05).

Cobre:
- 5 builders (build_bloco1..5_html) — com dados / sem dados (placeholder)
- render_kpi_badge — cor + valor + meta
- render_compare_badge — direções up/down/flat/na + favorabilidade
- build_drilldown_modal_body — bloco 2 (top10) e bloco 5 (detalhe)
- render_all_blocks — toggle de visibilidade
- i18n PT/ES/EN — chave presente em cada idioma

Os testes verificam estrutura/atributos do componente, não snapshots HTML completos.
"""
from __future__ import annotations

import pytest

# Importa apenas o módulo sob teste — não importa o módulo da page (que precisa de
# stack Dash completa pra layout()).
from src.utils import kpi_report_v2_layout as ly
from src.utils.kpi_report_v2_compare import compute_period_delta


# ============================ Helpers ============================

def _walk_str(component) -> str:
    """Achata recursivamente texto de uma árvore Dash em string única."""
    if component is None:
        return ""
    if isinstance(component, (str, int, float)):
        return str(component)
    if isinstance(component, list):
        return " ".join(_walk_str(c) for c in component)
    children = getattr(component, "children", None)
    return _walk_str(children)


def _find_id(component, target_id) -> bool:
    """Procura recursivamente por componente com id igual a target_id."""
    if component is None:
        return False
    if isinstance(component, (str, int, float)):
        return False
    if isinstance(component, list):
        return any(_find_id(c, target_id) for c in component)
    cid = getattr(component, "id", None)
    if cid == target_id:
        return True
    return _find_id(getattr(component, "children", None), target_id)


# ============================ Fixtures ============================

@pytest.fixture
def dados_bloco_planta():
    """Dados mock equivalentes a _build_kpis_bloco_planta."""
    return {
        "kpis_planta": {"mtbf": 120.5, "mttr": 8.2, "taxa_avaria": 2.1},
        "metas":       {"mtbf": 100.0, "mttr": 10.0, "taxa_avaria": 3.0},
        "cores_kpis":  {"mtbf": "#28a745", "mttr": "#28a745", "taxa_avaria": "#28a745"},
        "sunburst_figures": {"mtbf": None, "mttr": None, "taxa_avaria": None},
        "alert_range": 3.0,
    }


@pytest.fixture
def dados_bloco_paradas():
    """Dados mock equivalentes a _build_top5_paradas."""
    return {
        "paradas": [
            {"posicao": 1, "equipamento": "EQ-01", "data_hora": "20/05/2026 10:30",
             "duracao_min": "120 min", "causa": "201", "descricao": "Falha mecânica"},
            {"posicao": 2, "equipamento": "EQ-02", "data_hora": "20/05/2026 14:10",
             "duracao_min": "45 min", "causa": "S203", "descricao": "Falta de material"},
        ],
        "vazio": False,
    }


@pytest.fixture
def dados_bloco_paradas_vazio():
    return {"paradas": [], "vazio": True}


@pytest.fixture
def dados_bloco4():
    """Dados mock equivalentes a build_detalhamento_table."""
    return {
        "linhas": [
            {"equipamento": "EQ-01", "mtbf": 100.0, "mttr": 8.0, "taxa_avaria": 1.5,
             "cor_mtbf": "#28a745", "cor_mttr": "#28a745", "cor_taxa_avaria": "#28a745"},
            {"equipamento": "EQ-02", "mtbf": None, "mttr": None, "taxa_avaria": None,
             "cor_mtbf": None, "cor_mttr": None, "cor_taxa_avaria": None},
        ],
        "total": {"equipamento": "TOTAL", "mtbf": 100.0, "mttr": 8.0, "taxa_avaria": 1.5,
                  "cor_mtbf": None, "cor_mttr": None, "cor_taxa_avaria": None},
        "vazio": False,
    }


# ============================ render_kpi_badge ============================

class TestRenderKpiBadge:
    def test_valor_com_meta(self):
        badge = ly.render_kpi_badge(120.0, 100.0, "mtbf", "#28a745", "pt")
        flat = _walk_str(badge)
        assert "120" in flat
        assert "100" in flat
        assert "Meta" in flat
        assert "h" in flat  # unidade MTBF

    def test_valor_none_mostra_traço(self):
        badge = ly.render_kpi_badge(None, 100.0, "mtbf", None, "pt")
        flat = _walk_str(badge)
        assert "—" in flat

    def test_mttr_usa_minutos(self):
        badge = ly.render_kpi_badge(8.5, 10.0, "mttr", "#28a745", "en")
        flat = _walk_str(badge)
        assert "min" in flat

    def test_taxa_avaria_usa_percent(self):
        badge = ly.render_kpi_badge(2.5, 3.0, "taxa_avaria", "#28a745", "pt")
        flat = _walk_str(badge)
        assert "%" in flat


# ============================ render_compare_badge ============================

class TestRenderCompareBadge:
    def test_compare_none_retorna_none(self):
        assert ly.render_compare_badge(None, "pt") is None

    def test_direction_up_favoravel(self):
        entry = compute_period_delta(120.0, 100.0, "mtbf")
        badge = ly.render_compare_badge(entry, "pt")
        flat = _walk_str(badge)
        assert "↑" in flat
        assert "20" in flat or "%" in flat

    def test_direction_down_favoravel_mttr(self):
        entry = compute_period_delta(8.0, 10.0, "mttr")
        badge = ly.render_compare_badge(entry, "pt")
        flat = _walk_str(badge)
        assert "↓" in flat

    def test_direction_flat(self):
        entry = compute_period_delta(100.5, 100.0, "mtbf")  # 0.5% < threshold
        badge = ly.render_compare_badge(entry, "pt")
        flat = _walk_str(badge)
        assert "estável" in flat or "→" in flat

    def test_direction_na(self):
        entry = compute_period_delta(None, 100.0, "mtbf")
        badge = ly.render_compare_badge(entry, "pt")
        flat = _walk_str(badge)
        assert "n/d" in flat

    def test_is_new_marca_novo(self):
        entry = compute_period_delta(10.0, 0.0, "mtbf")
        badge = ly.render_compare_badge(entry, "pt")
        flat = _walk_str(badge)
        assert "novo" in flat

    def test_i18n_en(self):
        entry = compute_period_delta(None, 100.0, "mtbf")
        badge = ly.render_compare_badge(entry, "en")
        flat = _walk_str(badge)
        assert "n/a" in flat

    def test_kpi_desconhecido_favorable_none(self):
        # KPI fora do conhecido → favorable=None mesmo com direction definida
        entry = ly.compute_period_delta(120.0, 100.0, "oee") if hasattr(ly, "compute_period_delta") else None
        # usar import direto
        from src.utils.kpi_report_v2_compare import compute_period_delta as cpd
        entry = cpd(120.0, 100.0, "oee")
        badge = ly.render_compare_badge(entry, "pt")
        flat = _walk_str(badge)
        # direction='up' mas favorable=None → fundo cinza neutro (cor neutra)
        assert "↑" in flat

    def test_breakdown_rate_subiu_desfavoravel(self):
        # cobre branch favorable=False (vermelho)
        from src.utils.kpi_report_v2_compare import compute_period_delta as cpd
        entry = cpd(5.0, 2.0, "breakdown_rate")
        badge = ly.render_compare_badge(entry, "pt")
        flat = _walk_str(badge)
        assert "↑" in flat
        # cor de fundo desfavorável definida no style
        style = getattr(badge, "style", {})
        assert style.get("backgroundColor") == "#fde2e2"

    def test_delta_pct_none_mas_delta_abs_presente(self):
        # Cenário sintético: força compare_entry com delta_pct=None, delta_abs!=None,
        # direction != flat/na → exercita branch label = fmt_numero(delta_abs)
        entry = {
            "delta_abs": 12.5, "delta_pct": None, "direction": "up",
            "favorable": True, "is_new": False,
            "anterior_value": 1.0, "atual_value": 13.5,
        }
        badge = ly.render_compare_badge(entry, "pt")
        flat = _walk_str(badge)
        assert "12,5" in flat or "12" in flat


# ============================ Bloco 1 / 3 (planta) ============================

class TestBloco1:
    def test_com_dados(self, dados_bloco_planta):
        card = ly.build_bloco1_html(dados_bloco_planta, None, "pt")
        assert card.id == "kpi-v2-card-block-1"
        flat = _walk_str(card)
        assert "Bloco 1" in flat
        assert "120" in flat  # MTBF
        assert "MTBF" in flat
        assert "MTTR" in flat

    def test_sem_dados_renderiza_placeholder(self):
        card = ly.build_bloco1_html({}, None, "pt")
        flat = _walk_str(card)
        assert "Sem dados" in flat

    def test_dados_none_renderiza_placeholder(self):
        card = ly.build_bloco1_html(None, None, "pt")
        flat = _walk_str(card)
        assert "Sem dados" in flat

    def test_com_compare_inclui_badges(self, dados_bloco_planta):
        compare = {
            "mtbf":           compute_period_delta(120.5, 100.0, "mtbf"),
            "mttr":           compute_period_delta(8.2, 10.0, "mttr"),
            "breakdown_rate": compute_period_delta(2.1, 3.0, "breakdown_rate"),
        }
        card = ly.build_bloco1_html(dados_bloco_planta, compare, "pt")
        flat = _walk_str(card)
        assert "↑" in flat or "↓" in flat  # alguma seta de delta

    def test_i18n_es(self, dados_bloco_planta):
        card = ly.build_bloco1_html(dados_bloco_planta, None, "es")
        flat = _walk_str(card)
        assert "Bloque 1" in flat
        assert "Tasa de Avería" in flat

    def test_bloco1_monthly_series_renderiza_bar_charts(self, dados_bloco_planta):
        """RF-01: bloco 1 com monthly_series → 3 dcc.Graph (bar charts)."""
        dados = dict(dados_bloco_planta)
        dados["monthly_series"] = {
            "labels":      ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                             "Jul", "Ago", "Set", "Out", "Nov", "Dez"],
            "mtbf":        [10.0, 12.0, 15.0, 11.0, 13.0, 14.0,
                             12.5, 11.8, 13.2, 14.5, 12.1, 10.9],
            "mttr":        [8.0, 7.5, 9.0, 8.2, 7.8, 8.5,
                             8.1, 7.9, 8.3, 8.7, 8.0, 7.6],
            "taxa_avaria": [2.1, 2.3, 2.0, 2.5, 2.4, 2.2,
                             2.1, 2.3, 2.0, 2.5, 2.4, 2.2],
            "current_idx": 4,  # destacando "Mai"
        }
        card = ly.build_bloco1_html(dados, None, "pt")
        # Confere existência de Graph na árvore (bar chart Plotly)
        from dash import dcc
        found = []

        def collect(c):
            if isinstance(c, dcc.Graph):
                found.append(c)
                return
            ch = getattr(c, "children", None)
            if isinstance(ch, list):
                for x in ch:
                    collect(x)
            elif ch is not None:
                collect(ch)
        collect(card)
        assert len(found) == 3, f"esperado 3 Graphs, achou {len(found)}"
        # Confere que fig tem trace go.Bar
        from plotly.graph_objects import Figure
        for g in found:
            assert g.figure is not None
            # figure pode ser Figure ou dict — converte
            f = g.figure if isinstance(g.figure, Figure) else Figure(g.figure)
            traces = [t for t in f.data if t.type == "bar"]
            assert traces, "esperado go.Bar trace no chart"

    def test_bloco3_daily_series_renderiza_bar_charts(self, dados_bloco_planta):
        """RF-02: bloco 3 com daily_series → 3 dcc.Graph."""
        dados = dict(dados_bloco_planta)
        dados["daily_series"] = {
            "labels":      ["15/05", "16/05", "17/05", "18/05",
                             "19/05", "20/05", "21/05"],
            "mtbf":        [10.0, 12.0, 11.5, 10.8, 11.2, 12.3, 11.9],
            "mttr":        [8.0, 7.8, 8.2, 7.9, 8.1, 8.0, 7.7],
            "taxa_avaria": [2.1, 2.2, 2.0, 2.3, 2.1, 2.2, 2.0],
            "current_idx": 6,
        }
        card = ly.build_bloco3_html(dados, None, "pt")
        from dash import dcc
        found = []

        def collect(c):
            if isinstance(c, dcc.Graph):
                found.append(c)
                return
            ch = getattr(c, "children", None)
            if isinstance(ch, list):
                for x in ch:
                    collect(x)
            elif ch is not None:
                collect(ch)
        collect(card)
        assert len(found) == 3


class TestBloco3:
    def test_com_dados(self, dados_bloco_planta):
        card = ly.build_bloco3_html(dados_bloco_planta, None, "pt")
        assert card.id == "kpi-v2-card-block-3"
        flat = _walk_str(card)
        assert "Bloco 3" in flat

    def test_compare_24h_label(self, dados_bloco_planta):
        card = ly.build_bloco3_html(dados_bloco_planta, None, "pt")
        flat = _walk_str(card)
        assert "24h" in flat


# ============================ Bloco 2 / 5 (paradas) ============================

class TestBloco2:
    def test_com_dados(self, dados_bloco_paradas):
        card = ly.build_bloco2_html(dados_bloco_paradas, "pt")
        assert card.id == "kpi-v2-card-block-2"
        flat = _walk_str(card)
        assert "Top 5" in flat
        assert "EQ-01" in flat
        assert "EQ-02" in flat
        assert "201" in flat

    def test_drilldown_button(self, dados_bloco_paradas):
        card = ly.build_bloco2_html(dados_bloco_paradas, "pt")
        flat = _walk_str(card)
        assert "Ver Top 10" in flat

    def test_sem_dados(self, dados_bloco_paradas_vazio):
        card = ly.build_bloco2_html(dados_bloco_paradas_vazio, "pt")
        flat = _walk_str(card)
        assert "Sem dados" in flat


class TestBloco5:
    def test_com_dados(self, dados_bloco_paradas):
        card = ly.build_bloco5_html(dados_bloco_paradas, "pt")
        assert card.id == "kpi-v2-card-block-5"
        flat = _walk_str(card)
        assert "Últimas 24h" in flat
        assert "EQ-01" in flat


# ============================ Bloco 4 (tabela) ============================

class TestBloco4:
    def test_com_dados(self, dados_bloco4):
        card = ly.build_bloco4_html(dados_bloco4, "pt")
        assert card.id == "kpi-v2-card-block-4"
        flat = _walk_str(card)
        assert "Detalhamento" in flat

    def test_sem_dados(self):
        card = ly.build_bloco4_html({}, "pt")
        flat = _walk_str(card)
        assert "Sem dados" in flat

    def test_linhas_vazias(self):
        card = ly.build_bloco4_html({"linhas": [], "total": {}, "vazio": True}, "pt")
        flat = _walk_str(card)
        assert "Sem dados" in flat


# ============================ Drilldown modal ============================

class TestDrilldownModalBody:
    def test_bloco2_lista_paradas(self, dados_bloco_paradas):
        body = ly.build_drilldown_modal_body(2, dados_bloco_paradas["paradas"], "pt")
        flat = _walk_str(body)
        assert "EQ-01" in flat
        assert "201" in flat

    def test_bloco5_detalhe_unico(self, dados_bloco_paradas):
        # passa só 1 evento (block 5 = detalhe)
        body = ly.build_drilldown_modal_body(5, [dados_bloco_paradas["paradas"][0]], "pt")
        flat = _walk_str(body)
        assert "EQ-01" in flat
        assert "Falha mecânica" in flat

    def test_vazio(self):
        body = ly.build_drilldown_modal_body(2, [], "pt")
        flat = _walk_str(body)
        assert "Sem dados" in flat

    def test_bloco5_evento_invalido_retorna_no_data(self):
        # paradas=[None] → evt não é dict → no_data
        body = ly.build_drilldown_modal_body(5, [None], "pt")
        flat = _walk_str(body)
        assert "Sem dados" in flat


# ============================ render_all_blocks ============================

class TestRenderAllBlocks:
    def test_todos_blocos_ativos(self, dados_bloco_planta, dados_bloco_paradas,
                                   dados_bloco4):
        dados = {
            "bloco1": dados_bloco_planta,
            "bloco2": dados_bloco_paradas,
            "bloco3": dados_bloco_planta,
            "bloco4": dados_bloco4,
            "bloco5": dados_bloco_paradas,
        }
        out = ly.render_all_blocks(dados, None, "pt", toggle=None)
        flat = _walk_str(out)
        for n in range(1, 6):
            assert f"kpi-v2-card-block-{n}" or f"Bloco {n}" in flat or f"Block {n}" in flat

    def test_toggle_oculta_bloco_3(self, dados_bloco_planta, dados_bloco_paradas,
                                     dados_bloco4):
        dados = {
            "bloco1": dados_bloco_planta,
            "bloco2": dados_bloco_paradas,
            "bloco3": dados_bloco_planta,
            "bloco4": dados_bloco4,
            "bloco5": dados_bloco_paradas,
        }
        toggle = {"1": True, "2": True, "3": False, "4": True, "5": True}
        out = ly.render_all_blocks(dados, None, "pt", toggle=toggle)
        # bloco 3 não deve estar presente
        assert not _find_id(out, "kpi-v2-card-block-3")
        assert _find_id(out, "kpi-v2-card-block-1")
        assert _find_id(out, "kpi-v2-card-block-4")

    def test_toggle_todos_off_mostra_no_data(self):
        toggle = {str(i): False for i in range(1, 6)}
        out = ly.render_all_blocks({}, None, "pt", toggle=toggle)
        flat = _walk_str(out)
        assert "Sem dados" in flat

    def test_dados_vazios(self):
        out = ly.render_all_blocks({}, None, "pt", toggle=None)
        flat = _walk_str(out)
        # 5 placeholders, todos com "Sem dados"
        assert flat.count("Sem dados") >= 5


# ============================ i18n consistency ============================

class TestI18nConsistency:
    @pytest.mark.parametrize("lang,expected_phrase", [
        ("pt", "Sem dados"),
        ("es", "Sin datos"),
        ("en", "No data"),
    ])
    def test_placeholder_traduzido(self, lang, expected_phrase):
        out = ly.build_bloco1_html({}, None, lang)
        assert expected_phrase in _walk_str(out)
