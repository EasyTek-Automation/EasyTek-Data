# -*- coding: utf-8 -*-
"""Testes das funções puras do enriquecimento de custo (IM-29 / BR-13/14/16).

Sem SAP, sem Mongo: exercita a classificação de família (BR-13), o descritor por cascata
(BR-13) e o mapeamento linha-da-grade -> doc (campos novos + retrocompat). Pacote do daemon
tem hífen (`sap-scheduler`) -> carregado via importlib com o parent (`AMG_Data/`) no sys.path,
igual a test_hh_coleta.py.
"""
import importlib
import sys
from datetime import datetime
from pathlib import Path

_PARENT = Path(__file__).resolve().parents[2]  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

cc = importlib.import_module("sap-scheduler.trabalhos.custos_manut.custo_collect")


# ---- família (BR-13): keyed em PRTAU, não em tipo_doc ---------------------------------

def test_familia_liquidacao_por_ordem():
    # tem ordem emissora -> liquidação, mesmo com tipo_doc SA e sem pedido
    assert cc._familia({"PRTAU": "5019483", "BLART": "SA"}) == "liquidacao"

def test_familia_compra_por_pedido():
    assert cc._familia({"EBELN": "4300008553", "BLART": "RE"}) == "compra"

def test_familia_estoque_default():
    # sem ordem e sem pedido -> estoque (inclui a reclass SA manual, que não tem PRTAU)
    assert cc._familia({"BLART": "WA"}) == "estoque"
    assert cc._familia({"BLART": "SA"}) == "estoque"   # SA de reclass, sem PRTAU

def test_familia_ordem_vence_pedido():
    # se tiver os dois, ordem emissora manda (é liquidação de ordem)
    assert cc._familia({"PRTAU": "5019483", "EBELN": "4300008553"}) == "liquidacao"


# ---- descritor por cascata (BR-13) ---------------------------------------------------

def test_descritor_prefere_pedido():
    r = {"EBTXT": "SERV INSPECAO", "MAT_TXT": "CORREIA", "POB_TXT": "ORDEM X"}
    assert cc._descritor(r) == "SERV INSPECAO"

def test_descritor_fallback_material():
    r = {"EBTXT": "", "MAT_TXT": "CORREIA 1180", "POB_TXT": "ORDEM X"}
    assert cc._descritor(r) == "CORREIA 1180"

def test_descritor_fallback_ordem():
    # o buraco antigo: sem pedido e sem material -> descrição da ordem (antes vinha vazio)
    r = {"EBTXT": "", "MAT_TXT": "", "POB_TXT": "CISALHA ALARME MOTOR PREPARADO"}
    assert cc._descritor(r) == "CISALHA ALARME MOTOR PREPARADO"

def test_descritor_vazio_nao_inventa():
    assert cc._descritor({"EBTXT": "", "MAT_TXT": "", "POB_TXT": ""}) == ""
    assert cc._descritor({}) == ""


# ---- mapeamento linha -> doc ---------------------------------------------------------

def _linha_liquidacao():
    return {
        "KSTAR": "33102101", "CEL_KTXT": "CONSUMO MAT. MANUT", "KOSTL": "205002",
        "OBJ_TXT": "CIZALHA GUILHOTINA", "WRGBTR": "43.855,11", "BUDAT": "30.06.2026",
        "EBTXT": "", "MAT_TXT": "", "POB_TXT": "CISALHA ALARME MOTOR PREPARADO",
        "PRTAU": "5019483", "REFBN": "5743505", "MATNR": "16888", "USNAM": "40MASSIS",
        "WERKS": "BR02", "BLART": "SA", "BELNR": "0100057431", "EBELN": "",
    }

def test_map_liquidacao_campos_novos():
    d = cc._map_lancamento(_linha_liquidacao())
    assert d["conta"] == "33102101"
    assert d["familia"] == "liquidacao"
    assert d["ordem_emissora"] == "5019483"       # BR-14 chave de rastreio
    assert d["descritor"] == "CISALHA ALARME MOTOR PREPARADO"   # cascata caiu na ordem
    assert d["valor"] == 43855.11
    assert d["doc_ref"] == "5743505"
    assert d["material"] == "16888"
    assert d["usuario"] == "40MASSIS"
    assert d["planta"] == "BR02"
    assert d["mes_referencia"] == "2026-06"
    assert d["data_lancamento"] == datetime(2026, 6, 30)

def test_map_retrocompat_campos_antigos():
    # BR-16: campos existentes preservados, nada removido
    d = cc._map_lancamento(_linha_liquidacao())
    for k in ("mes_referencia", "data_lancamento", "conta", "conta_nome", "centro_custo",
              "centro_nome", "valor", "descritor", "tipo_doc", "no_documento",
              "pedido_compra", "fonte"):
        assert k in d, f"campo {k} sumiu (retrocompat BR-16)"
    assert d["no_documento"] == "0100057431"      # BELNR segue coletado (só sai da UI)
    assert d["tipo_doc"] == "SA"
    assert d["fonte"] == "sap"

def test_map_compra_sem_ordem():
    r = {"KSTAR": "33102260", "WRGBTR": "29.400,00", "BUDAT": "05.01.2026",
         "EBTXT": "PLATAFORMA AEREA", "EBELN": "4300008553", "BLART": "WE"}
    d = cc._map_lancamento(r)
    assert d["familia"] == "compra"
    assert d["ordem_emissora"] == ""              # compra pura: coluna Ordem vazia (BR-14)
    assert d["descritor"] == "PLATAFORMA AEREA"
    assert d["pedido_compra"] == "4300008553"

def test_map_conta_nome_cel_ktxt_com_fallback():
    # /EASYTEK usa CEL_KTXT; se só vier CEL_LTXT (fallback runtime), usa esse
    assert cc._map_lancamento({"KSTAR": "33102101", "CEL_KTXT": "NOME K"})["conta_nome"] == "NOME K"
    assert cc._map_lancamento({"KSTAR": "33102101", "CEL_LTXT": "NOME L"})["conta_nome"] == "NOME L"

def test_map_ignora_linha_nao_classe():
    # linha de total/subtotal (KSTAR não começa com 3) -> None
    assert cc._map_lancamento({"KSTAR": "", "WRGBTR": "999,00"}) is None
    assert cc._map_lancamento({"KSTAR": "Total", "WRGBTR": "999,00"}) is None


# ---- componentes MB25 (BR-15): IM-30 -------------------------------------------------

def test_norm_ordem_tira_zeros_a_esquerda():
    assert cc._norm_ordem("000005019483") == "5019483"   # ACCOU (MB25) casa com PRTAU (KSB1)
    assert cc._norm_ordem("5019483") == "5019483"
    assert cc._norm_ordem("  0005019483 ") == "5019483"

def _linha_mb25_baixada():
    return {"ACCOU": "000005019483", "MATNR_I": "16888", "MAKTX": "MOTOR CC DMP180 137KW ABB",
            "BDMNG_I": "1", "DIFFMG": "0", "MEINS_I": "PC"}

def test_map_componente_baixado():
    d = cc._map_componente(_linha_mb25_baixada(), "2026-06")
    assert d["ordem"] == "5019483"          # normalizado p/ casar com ordem_emissora
    assert d["material"] == "16888"
    assert d["material_desc"] == "MOTOR CC DMP180 137KW ABB"
    assert d["quantidade"] == 1.0
    assert d["unidade"] == "PC"
    assert d["mes_referencia"] == "2026-06"
    assert d["fonte"] == "sap"

def test_map_componente_reserva_nao_baixada_fora():
    # DIFFMG != 0 -> saldo a retirar > 0 -> não foi baixado -> None (reservar ≠ consumir)
    r = _linha_mb25_baixada(); r["DIFFMG"] = "1"
    assert cc._map_componente(r) is None

def test_map_componente_sem_material_ou_ordem_fora():
    r = _linha_mb25_baixada(); r["MATNR_I"] = ""
    assert cc._map_componente(r) is None
    r2 = _linha_mb25_baixada(); r2["ACCOU"] = ""
    assert cc._map_componente(r2) is None

def test_map_componente_aliases_sem_sufixo_I():
    # a grade às vezes vem sem o sufixo _I — o alias resolve
    r = {"ACCOU": "5019483", "MATNR": "16888", "BDMNG": "2", "DIFFMG": "0", "MEINS": "PC"}
    d = cc._map_componente(r)
    assert d["material"] == "16888" and d["quantidade"] == 2.0 and d["unidade"] == "PC"
