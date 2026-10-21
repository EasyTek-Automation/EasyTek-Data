# -*- coding: utf-8 -*-
"""Mão de obra temporária — períodos de presença no quadro (GantManagement BR-25 / DS-18 §1–2)."""
from src.utils import periodos_quadro as pq


# ---- semana ---------------------------------------------------------------------------

def test_semana_shift_virada_de_ano():
    assert pq.semana_shift("2026-W53", 1) == "2027-W01"
    assert pq.semana_shift("2027-W01", -1) == "2026-W53"
    assert pq.semana_shift("2026-W41", -1) == "2026-W40"


def test_semana_cmp():
    assert pq.semana_cmp("2026-W09", "2026-W10") == -1
    assert pq.semana_cmp("2027-W01", "2026-W53") == 1
    assert pq.semana_cmp("2026-W41", "2026-W41") == 0


# ---- conta_na_semana: tabela do DS-18 §1 ----------------------------------------------

def test_fixo_de_sempre_conta_sempre():
    f = {"nome": "Carlos"}
    assert pq.conta_na_semana(f, "2026-W40") and pq.conta_na_semana(f, "2026-W45")


def test_temporario_recem_cadastrado_nunca_conta():
    f = {"temporario": True, "periodos_quadro": []}
    assert not pq.conta_na_semana(f, "2026-W40")
    assert not pq.conta_na_semana(f, "2026-W45")


def test_temporario_incluido_e_retirado():
    f = {"temporario": True, "periodos_quadro": [{"de": "2026-W42", "ate": "2026-W48"}]}
    assert not pq.conta_na_semana(f, "2026-W41")
    assert pq.conta_na_semana(f, "2026-W42")
    assert pq.conta_na_semana(f, "2026-W48")
    assert not pq.conta_na_semana(f, "2026-W49")


def test_era_fixo_marcado_temporario():
    f = {"temporario": True, "periodos_quadro": [{"de": None, "ate": "2026-W40"}]}
    assert pq.conta_na_semana(f, "2020-W01")
    assert pq.conta_na_semana(f, "2026-W40")
    assert not pq.conta_na_semana(f, "2026-W41")


def test_temporario_desmarcado():
    f = {"temporario": False,
         "periodos_quadro": [{"de": "2026-W42", "ate": "2026-W44"}, {"de": "2026-W45", "ate": None}]}
    assert not pq.conta_na_semana(f, "2026-W40")
    assert pq.conta_na_semana(f, "2026-W45")
    assert pq.conta_na_semana(f, "2030-W10")


def test_inativo_nunca_conta():
    assert not pq.conta_na_semana({"ativo": False}, "2026-W41")
    assert not pq.conta_na_semana(
        {"ativo": False, "temporario": True, "periodos_quadro": [{"de": None, "ate": None}]}, "2026-W41")


# ---- transições ------------------------------------------------------------------------

def test_marcar_temporario_fixo_de_sempre():
    assert pq.periodos_ao_marcar_temporario([], "2026-W41") == [{"de": None, "ate": "2026-W40"}]


def test_marcar_temporario_fixo_com_historico_preserva_passado():
    ps = [{"de": "2026-W42", "ate": "2026-W44"}, {"de": "2026-W45", "ate": None}]
    out = pq.periodos_ao_marcar_temporario(ps, "2026-W50")
    assert out == [{"de": "2026-W42", "ate": "2026-W49"}]


def test_desmarcar_temporario_sem_periodos():
    out = pq.periodos_ao_desmarcar([], "2026-W45")
    assert out == [{"de": "2026-W45", "ate": None}]
    f = {"temporario": False, "periodos_quadro": out}
    assert not pq.conta_na_semana(f, "2026-W40")      # passado preservado (item 8 revisado)
    assert pq.conta_na_semana(f, "2026-W45")


def test_desmarcar_temporario_ja_incluido_funde():
    out = pq.periodos_ao_desmarcar([{"de": "2026-W42", "ate": None}], "2026-W45")
    assert out == [{"de": "2026-W42", "ate": None}]


def test_desmarcar_apos_retirada_mantem_buraco():
    out = pq.periodos_ao_desmarcar([{"de": "2026-W42", "ate": "2026-W44"}], "2026-W48")
    assert out == [{"de": "2026-W42", "ate": "2026-W44"}, {"de": "2026-W48", "ate": None}]


def test_incluir():
    assert pq.periodos_ao_incluir([], "2026-W42") == [{"de": "2026-W42", "ate": None}]


def test_reincluir_cria_novo_periodo():
    out = pq.periodos_ao_incluir([{"de": "2026-W42", "ate": "2026-W48"}], "2026-W52")
    assert out == [{"de": "2026-W42", "ate": "2026-W48"}, {"de": "2026-W52", "ate": None}]


def test_reincluir_semana_seguinte_funde():
    out = pq.periodos_ao_incluir([{"de": "2026-W42", "ate": "2026-W48"}], "2026-W49")
    assert out == [{"de": "2026-W42", "ate": None}]


def test_retirar():
    out = pq.periodos_ao_retirar([{"de": "2026-W42", "ate": None}], "2026-W49")
    assert out == [{"de": "2026-W42", "ate": "2026-W48"}]


def test_retirar_na_mesma_semana_da_inclusao_descarta_periodo():
    assert pq.periodos_ao_retirar([{"de": "2026-W42", "ate": None}], "2026-W42") == []


def test_retirar_descarta_periodo_futuro_preserva_passado():
    ps = [{"de": "2026-W30", "ate": "2026-W35"}, {"de": "2026-W45", "ate": None}]
    assert pq.periodos_ao_retirar(ps, "2026-W41") == [{"de": "2026-W30", "ate": "2026-W35"}]


def test_retirar_virada_de_ano():
    assert pq.periodos_ao_retirar([{"de": "2026-W50", "ate": None}], "2027-W01") == \
        [{"de": "2026-W50", "ate": "2026-W53"}]


def test_normalizar_ordena_e_funde():
    ps = [{"de": "2026-W45", "ate": None}, {"de": "2026-W30", "ate": "2026-W44"}]
    assert pq.normalizar(ps) == [{"de": "2026-W30", "ate": None}]
    ps = [{"de": "2026-W30", "ate": "2026-W40"}, {"de": "2026-W35", "ate": "2026-W38"}]
    assert pq.normalizar(ps) == [{"de": "2026-W30", "ate": "2026-W40"}]


# ---- BR-26: fixo novo nasce com período {de: semana do cadastro} -------------------------

def test_fixo_novo_nao_conta_antes_da_semana_do_cadastro():
    f = {"periodos_quadro": [{"de": "2026-W41", "ate": None}]}
    assert pq.conta_na_semana(f, "2026-W40") is False
    assert pq.conta_na_semana(f, "2026-W41") is True
    assert pq.conta_na_semana(f, "2026-W50") is True


def test_cadastro_fixo_por_engano_corrigido_na_mesma_semana_nunca_conta():
    assert pq.periodos_ao_marcar_temporario([{"de": "2026-W41", "ate": None}], "2026-W41") == []


def test_cadastro_fixo_por_engano_corrigido_depois_preserva_semana_em_que_contou():
    assert pq.periodos_ao_marcar_temporario([{"de": "2026-W41", "ate": None}], "2026-W42") == \
        [{"de": "2026-W41", "ate": "2026-W41"}]
