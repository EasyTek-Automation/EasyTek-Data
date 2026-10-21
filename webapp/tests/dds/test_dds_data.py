"""Testes da config do DDS: histórico de acidentes, dias sem acidente, recorde e ritmo.

Duas invariantes guiam estes testes:

1. O telão não pode cair por causa de config. Sem banco, sem histórico ou com
   documento estragado, o painel continua exibindo o guia com o padrão.
2. Nenhum número de segurança é inventado. Sem registro de acidente, a resposta
   é `None` (o telão mostra um traço) — nunca um zero que pareça um fato.
"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.utils import dds_data


# --------------------------------------------------------------------- fixtures
def _col_config(doc):
    """`get_mongo_connection` devolve uma collection cujo find_one retorna `doc`."""
    col = MagicMock()
    col.find_one.return_value = doc
    return patch.object(dds_data, "get_mongo_connection", return_value=col), col


def _historico(datas):
    """Simula `dds_acidentes` com as datas dadas (mais recente primeiro)."""
    registros = [{"id": f"id{i}", "data": d, "observacao": "", "registrado_por": "eu",
                  "registrado_em": None}
                 for i, d in enumerate(sorted(datas, reverse=True))]
    return patch.object(dds_data, "listar_acidentes",
                        side_effect=lambda limite=50: registros[:limite])


# ------------------------------------------------------------------ ritmo (passos)
class TestRitmo:
    def test_le_os_minutos_salvos(self):
        ctx, _ = _col_config({"passos_min": [1, 3, 2, 2, 1, 1]})
        with ctx:
            assert dds_data.get_dds_config()["passos_min"] == [1, 3, 2, 2, 1, 1]

    def test_sem_documento_usa_padrao(self):
        ctx, _ = _col_config(None)
        with ctx:
            assert dds_data.get_dds_config()["passos_min"] == dds_data.PASSOS_PADRAO

    def test_banco_fora_nao_levanta(self):
        with patch.object(dds_data, "get_mongo_connection",
                          side_effect=ConnectionError("mongo fora")):
            assert dds_data.get_dds_config()["passos_min"] == dds_data.PASSOS_PADRAO

    @pytest.mark.parametrize("passos", [[1, 2, 3], "1,2,3", [1, 2, 2, 2, 2, "x"], None])
    def test_passos_malformados_caem_no_padrao(self, passos):
        ctx, _ = _col_config({"passos_min": passos})
        with ctx:
            assert dds_data.get_dds_config()["passos_min"] == dds_data.PASSOS_PADRAO

    def test_passo_zero_vira_um(self):
        """Um passo de 0 min nasceria estourado no primeiro segundo."""
        ctx, _ = _col_config({"passos_min": [0, 2, 2, 2, 2, 1]})
        with ctx:
            assert dds_data.get_dds_config()["passos_min"][0] == 1

    def test_salva_e_registra_quem_alterou(self):
        ctx, col = _col_config(None)
        with ctx:
            ok, msg = dds_data.salvar_passos([1, 2, 2, 2, 2, 1], usuario="rodolfo")
        assert ok and "10 min no total" in msg
        gravado = col.update_one.call_args[0][1]["$set"]
        assert gravado["passos_min"] == [1, 2, 2, 2, 2, 1]
        assert gravado["atualizado_por"] == "rodolfo"

    @pytest.mark.parametrize("passos,pedaco", [
        ([1, 2, 3], "exatamente 6"),
        ([1, 2, 2, 2, 2, 0], "1 a 60"),
        ([1, 2, 2, 2, 2, 61], "1 a 60"),
        (["a", 2, 2, 2, 2, 1], "números inteiros"),
    ])
    def test_recusa_ritmo_invalido(self, passos, pedaco):
        ctx, col = _col_config(None)
        with ctx:
            ok, msg = dds_data.salvar_passos(passos)
        assert not ok and pedaco in msg
        col.update_one.assert_not_called()


# --------------------------------------------------------------- dias sem acidente
class TestDiasSemAcidente:
    def test_conta_dias_inteiros(self):
        with _historico([date(2026, 8, 12)]):
            assert dds_data.dias_sem_acidente(hoje=date(2026, 8, 26)) == 14

    def test_acidente_hoje_e_zero(self):
        with _historico([date(2026, 8, 26)]):
            assert dds_data.dias_sem_acidente(hoje=date(2026, 8, 26)) == 0

    def test_sem_historico_devolve_none(self):
        """Sem registro o telão mostra '—', nunca um número inventado."""
        with _historico([]):
            assert dds_data.dias_sem_acidente(hoje=date(2026, 8, 26)) is None

    def test_usa_o_acidente_mais_recente(self):
        with _historico([date(2026, 1, 10), date(2026, 8, 12), date(2025, 5, 3)]):
            assert dds_data.dias_sem_acidente(hoje=date(2026, 8, 26)) == 14

    def test_data_no_futuro_nao_fica_negativa(self):
        with _historico([date(2026, 9, 10)]):
            assert dds_data.dias_sem_acidente(hoje=date(2026, 8, 26)) == 0


# ------------------------------------------------------------------------ recorde
class TestRecorde:
    def test_sem_historico(self):
        with _historico([]):
            assert dds_data.recorde_dias(hoje=date(2026, 8, 26)) == (None, False)

    def test_um_acidente_so_o_recorde_e_o_periodo_atual(self):
        with _historico([date(2026, 8, 12)]):
            assert dds_data.recorde_dias(hoje=date(2026, 8, 26)) == (14, True)

    def test_periodo_passado_maior_que_o_atual(self):
        """10/01 → 12/08 são 214 dias; o período em curso tem 14."""
        with _historico([date(2026, 1, 10), date(2026, 8, 12)]):
            assert dds_data.recorde_dias(hoje=date(2026, 8, 26)) == (214, False)

    def test_periodo_atual_bate_o_recorde(self):
        with _historico([date(2026, 1, 1), date(2026, 1, 11)]):   # melhor anterior: 10 dias
            recorde, batendo = dds_data.recorde_dias(hoje=date(2026, 3, 1))
        assert recorde == 49 and batendo is True

    def test_empate_nao_conta_como_batendo(self):
        """Igualar o recorde ainda não é bater — o telão só anuncia quando supera."""
        with _historico([date(2026, 1, 1), date(2026, 1, 11)]):   # anterior: 10 dias
            recorde, batendo = dds_data.recorde_dias(hoje=date(2026, 1, 21))
        assert recorde == 10 and batendo is False


# ---------------------------------------------------------------------- registro
class TestRegistrarAcidente:
    def test_registra_e_guarda_autor(self):
        ctx, col = _col_config(None)                  # find_one None = não é duplicata
        with ctx:
            ok, msg = dds_data.registrar_acidente(date(2026, 8, 12), usuario="rodolfo",
                                                  observacao="prensa 2")
        assert ok and "12/08/2026" in msg
        doc = col.insert_one.call_args[0][0]
        assert doc["data"] == datetime(2026, 8, 12, 0, 0)
        assert doc["registrado_por"] == "rodolfo" and doc["observacao"] == "prensa 2"

    def test_recusa_data_futura(self):
        ctx, col = _col_config(None)
        with ctx:
            ok, msg = dds_data.registrar_acidente(date(2099, 1, 1))
        assert not ok and "futuro" in msg
        col.insert_one.assert_not_called()

    def test_recusa_data_vazia(self):
        ctx, col = _col_config(None)
        with ctx:
            ok, _ = dds_data.registrar_acidente(None)
        assert not ok
        col.insert_one.assert_not_called()

    def test_recusa_duplicata(self):
        """Dois registros no mesmo dia só entram por engano de digitação."""
        ctx, col = _col_config({"_id": "ja-existe"})
        with ctx:
            ok, msg = dds_data.registrar_acidente(date(2026, 8, 12))
        assert not ok and "Já existe" in msg
        col.insert_one.assert_not_called()

    def test_aceita_data_em_texto(self):
        ctx, col = _col_config(None)
        with ctx:
            ok, _ = dds_data.registrar_acidente("2026-08-12")
        assert ok
        assert col.insert_one.call_args[0][0]["data"] == datetime(2026, 8, 12, 0, 0)


class TestRemoverAcidente:
    def test_remove(self):
        col = MagicMock()
        col.delete_one.return_value = MagicMock(deleted_count=1)
        with patch.object(dds_data, "get_mongo_connection", return_value=col):
            ok, msg = dds_data.remover_acidente("507f1f77bcf86cd799439011")
        assert ok and "recalculado" in msg

    def test_id_inexistente(self):
        col = MagicMock()
        col.delete_one.return_value = MagicMock(deleted_count=0)
        with patch.object(dds_data, "get_mongo_connection", return_value=col):
            ok, msg = dds_data.remover_acidente("507f1f77bcf86cd799439011")
        assert not ok and "não encontrado" in msg

    def test_id_invalido_nao_levanta(self):
        with patch.object(dds_data, "get_mongo_connection", return_value=MagicMock()):
            ok, _ = dds_data.remover_acidente("isto-nao-e-um-id")
        assert not ok
