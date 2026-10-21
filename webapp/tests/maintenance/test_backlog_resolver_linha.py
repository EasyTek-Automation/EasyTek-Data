# -*- coding: utf-8 -*-
"""Helper público `resolver_linha` (backlog_data): dado o TPLNR (local de instalação) de uma
ordem, sobe a árvore oficial (`sap_ativos`) e devolve o nó Linha. Usado por `hh_data` para
re-resolver a Linha de cards congelados que guardaram só o TPLNR, não a `linha_nome`.
"""
from src.utils import backlog_data as bd

# mini árvore: PLANTA → LINHA → CONJUNTO (TPLNR da ordem amarra no conjunto)
_IDX = {
    "BR02": {"id": "BR02", "nivel": "PLANTA", "descricao": "USINA", "pai": None},
    "BR02-0901": {"id": "BR02-0901", "nivel": "LINHA",
                  "descricao": "LINHA DE CORTE LONGITUDINAL 8MM", "pai": "BR02"},
    "BR02-0901-0200": {"id": "BR02-0901-0200", "nivel": "CONJUNTO",
                       "descricao": "RECOLHEDOR DE RECORTES", "pai": "BR02-0901"},
}


def test_resolver_linha_sobe_do_conjunto_ate_a_linha():
    linha = bd.resolver_linha("BR02-0901-0200", _IDX)
    assert linha is not None
    assert linha["descricao"] == "LINHA DE CORTE LONGITUDINAL 8MM"
    assert linha["id"] == "BR02-0901"


def test_resolver_linha_no_proprio_nivel_linha():
    linha = bd.resolver_linha("BR02-0901", _IDX)
    assert linha and linha["id"] == "BR02-0901"


def test_resolver_linha_tplnr_vazio_ou_ausente_retorna_none():
    assert bd.resolver_linha("", _IDX) is None
    assert bd.resolver_linha(None, _IDX) is None
    assert bd.resolver_linha("NAO-EXISTE", _IDX) is None
