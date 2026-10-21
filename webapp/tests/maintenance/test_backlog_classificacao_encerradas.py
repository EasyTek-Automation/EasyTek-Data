# -*- coding: utf-8 -*-
"""B34/B35 — rosca por disciplina reconhece Terceiros (Z03) e Gestão (Z01); filtro de
encerradas/canceladas (status do usuário CERR/CANC) esconde da fila e da aba backlog."""
from src.utils import backlog_data as bd


def _o(ordem, disc, status_usuario=None):
    return {"ordem": ordem, "disciplina": disc, "status_usuario": status_usuario}


# ---- B34: rosca por disciplina ----------------------------------------------------------

def test_rosca_disciplina_inclui_terceiros_e_gestao():
    ordens = [_o("1", "Mecanica"), _o("2", "Eletrica"), _o("3", "Terceiros"),
              _o("4", "Terceiros"), _o("5", "Gestao"), _o("6", "NaoClassificado")]
    labels, valores = bd.dados_rosca_disciplina(ordens)
    d = dict(zip(labels, valores))
    assert d["Serviço de terceiros"] == 2
    assert d["Gestão"] == 1
    assert d["Mecânica"] == 1
    assert d["Elétrica"] == 1
    assert d["Não classificado"] == 1


# ---- B35: encerradas/canceladas ---------------------------------------------------------

def test_esta_encerrada_cerr_canc():
    assert bd.esta_encerrada(_o("1", "Mecanica", "CERR")) is True
    assert bd.esta_encerrada(_o("2", "Mecanica", "CANC")) is True
    assert bd.esta_encerrada(_o("3", "Mecanica", "CERR PRIO")) is True   # combo pela 1ª palavra
    assert bd.esta_encerrada(_o("4", "Mecanica", "ENTR")) is False       # em tratamento fica
    assert bd.esta_encerrada(_o("5", "Mecanica", "ABIE")) is False       # aberta fica
    assert bd.esta_encerrada(_o("6", "Mecanica", None)) is False         # sem status fica


def test_esconder_encerradas():
    ordens = [_o("1", "Mecanica", "ABIE"), _o("2", "Mecanica", "CERR"),
              _o("3", "Eletrica", "CANC"), _o("4", "Eletrica", "ENPA")]
    fora = bd.esconder_encerradas(ordens)
    assert [o["ordem"] for o in fora] == ["1", "4"]   # CERR e CANC saem; abertas/pausadas ficam


# ---- B37: Ferramentaria (Z04) na rosca + None/MAN fora da fila/backlog -------------------

def test_rosca_disciplina_inclui_ferramentaria():
    ordens = [_o("1", "Mecanica"), _o("2", "Ferramentaria"), _o("3", "Ferramentaria")]
    labels, valores = bd.dados_rosca_disciplina(ordens)
    d = dict(zip(labels, valores))
    assert d["Ferramentaria"] == 2
    assert d["Mecânica"] == 1


def _oc(ordem, centro):
    return {"ordem": ordem, "disciplina": "NaoClassificado", "centro_operacao_0010": centro}

def test_sem_centro_classificavel():
    assert bd.sem_centro_classificavel(_oc("1", None)) is True    # sem centro
    assert bd.sem_centro_classificavel(_oc("2", "")) is True      # vazio
    assert bd.sem_centro_classificavel(_oc("3", "MAN")) is True   # genérico
    assert bd.sem_centro_classificavel(_oc("4", " man ")) is True # trim + case
    assert bd.sem_centro_classificavel(_oc("5", "Z02")) is False  # pendência real fica
    assert bd.sem_centro_classificavel(_oc("6", "Z10")) is False  # classificável fica

def test_esconder_sem_centro():
    ordens = [_oc("1", "Z02"), _oc("2", None), _oc("3", "MAN"), _oc("4", "Z10")]
    fora = bd.esconder_sem_centro(ordens)
    assert [o["ordem"] for o in fora] == ["1", "4"]   # None/MAN saem; Z02 e Z10 ficam
