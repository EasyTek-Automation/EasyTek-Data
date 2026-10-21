"""Reconciliação da árvore que vem do quadro de desenho (bloco 3 do SDD v3).

O balão desenhado chega cru — id provisório, sem análise dona, sem ordem. Se for
gravado assim, `validar_arvore` **recusa a árvore inteira** por causa dele. Estes
testes seguram cada etapa dessa preparação, e são puros: nada de Dash, nada de Mongo.
"""
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from src.utils.failure_tree import (  # noqa: E402
    MODO_AUTO,
    TIPO_CAUSA,
    TIPO_ETAPA,
    TIPO_RAIZ,
    conflitos_de_pai,
    descrever_no,
    mensagem_com_titulos,
    reconciliar_arvore,
    validar_arvore,
)

ANALISE = "analise-123"


def _raiz(**kw):
    base = {"id": "r1", "parent_id": None, "tipo": TIPO_RAIZ, "titulo": "Parada da Prensa 02",
            "analysis_id": ANALISE, "duration_min": 120, "duration_mode": MODO_AUTO,
            "sort_order": 0, "is_root_cause": False, "position_x": 60, "position_y": 60}
    base.update(kw)
    return base


def _balao_desenhado(id_, parent, x=300, y=100, titulo="Correia desalinhada"):
    """Como o quadro entrega um balão recém-desenhado: id provisório e quase nada mais."""
    return {"id": id_, "parent_id": parent, "tipo": TIPO_CAUSA, "titulo": titulo,
            "is_root_cause": False, "position_x": x, "position_y": y}


class TestIdProvisorio:
    def test_balao_novo_ganha_id_definitivo(self):
        nos = reconciliar_arvore([_raiz(), _balao_desenhado("novo_abc", "r1")], ANALISE)
        novo = [n for n in nos if n["id"] != "r1"][0]
        assert not novo["id"].startswith("novo_")
        assert len(novo["id"]) == 32  # uuid4().hex, como o resto do sistema

    def test_filho_acompanha_o_pai_renomeado(self):
        """Renomear o pai sem corrigir o filho deixaria o filho apontando para o vazio."""
        nos = reconciliar_arvore([
            _raiz(),
            _balao_desenhado("novo_pai", "r1"),
            _balao_desenhado("novo_filho", "novo_pai", y=200, titulo="Tensor gasto"),
        ], ANALISE)
        pai = next(n for n in nos if n["titulo"] == "Correia desalinhada")
        filho = next(n for n in nos if n["titulo"] == "Tensor gasto")
        assert filho["parent_id"] == pai["id"]
        assert not pai["id"].startswith("novo_")

    def test_balao_que_ja_existia_mantem_o_id(self):
        """Id de balão salvo não pode mudar: o Plano de Ação se liga a ele por esse id."""
        nos = reconciliar_arvore([_raiz(), {"id": "c9", "parent_id": "r1", "tipo": TIPO_CAUSA,
                                            "titulo": "Já existia", "analysis_id": ANALISE}], ANALISE)
        assert {n["id"] for n in nos} == {"r1", "c9"}


class TestAnaliseDona:
    def test_todo_balao_recebe_a_analise(self):
        nos = reconciliar_arvore([_raiz(), _balao_desenhado("novo_a", "r1")], ANALISE)
        assert all(n["analysis_id"] == ANALISE for n in nos)

    def test_arvore_reconciliada_passa_na_validacao(self):
        """O ponto de tudo: sem reconciliar, a gravação recusa; com, aceita."""
        crua = [_raiz(), _balao_desenhado("novo_a", "r1")]
        ok_antes, msg = validar_arvore(crua, ANALISE)
        assert not ok_antes and "não pertence a esta análise" in msg

        ok_depois, msg2 = validar_arvore(reconciliar_arvore(crua, ANALISE), ANALISE)
        assert ok_depois, msg2


class TestTipos:
    def test_filho_da_raiz_vira_etapa(self):
        nos = reconciliar_arvore([_raiz(), _balao_desenhado("novo_a", "r1")], ANALISE)
        assert next(n for n in nos if n["id"] != "r1")["tipo"] == TIPO_ETAPA

    def test_neto_vira_causa(self):
        nos = reconciliar_arvore([
            _raiz(),
            _balao_desenhado("novo_a", "r1"),
            _balao_desenhado("novo_b", "novo_a", titulo="Tensor gasto"),
        ], ANALISE)
        assert next(n for n in nos if n["titulo"] == "Tensor gasto")["tipo"] == TIPO_CAUSA

    def test_tipo_errado_vindo_do_desenho_e_corrigido(self):
        """O desenho chuta o tipo pela profundidade; aqui a árvore manda."""
        nos = reconciliar_arvore([
            _raiz(), _balao_desenhado("novo_a", "r1") | {"tipo": TIPO_CAUSA},
        ], ANALISE)
        assert next(n for n in nos if n["id"] != "r1")["tipo"] == TIPO_ETAPA


class TestOrdemDosIrmaos:
    def test_ordem_segue_a_posicao_na_tela(self):
        """Quem está mais acima no desenho vem primeiro no relatório."""
        nos = reconciliar_arvore([
            _raiz(),
            _balao_desenhado("novo_baixo", "r1", y=400, titulo="Terceiro"),
            _balao_desenhado("novo_meio", "r1", y=250, titulo="Segundo"),
            _balao_desenhado("novo_topo", "r1", y=100, titulo="Primeiro"),
        ], ANALISE)
        filhos = sorted([n for n in nos if n["parent_id"]], key=lambda n: n["sort_order"])
        assert [n["titulo"] for n in filhos] == ["Primeiro", "Segundo", "Terceiro"]

    def test_empate_na_altura_desempata_pela_esquerda(self):
        nos = reconciliar_arvore([
            _raiz(),
            _balao_desenhado("novo_dir", "r1", x=800, y=100, titulo="Direita"),
            _balao_desenhado("novo_esq", "r1", x=300, y=100, titulo="Esquerda"),
        ], ANALISE)
        filhos = sorted([n for n in nos if n["parent_id"]], key=lambda n: n["sort_order"])
        assert [n["titulo"] for n in filhos] == ["Esquerda", "Direita"]


class TestCamposPreservados:
    def test_nao_sobrescreve_o_que_ja_existe(self):
        """Tempo e modo do balão salvo não podem ser reescritos pelo desenho."""
        salvo = {"id": "c1", "parent_id": "r1", "tipo": TIPO_CAUSA, "titulo": "Antiga",
                 "analysis_id": ANALISE, "duration_min": 45, "duration_mode": "MANUAL",
                 "is_root_cause": True}
        nos = reconciliar_arvore([_raiz(), salvo], ANALISE)
        c1 = next(n for n in nos if n["id"] == "c1")
        assert c1["duration_min"] == 45
        assert c1["duration_mode"] == "MANUAL"
        assert c1["is_root_cause"] is True

    def test_balao_novo_ganha_padrao(self):
        nos = reconciliar_arvore([_raiz(), _balao_desenhado("novo_a", "r1")], ANALISE)
        novo = next(n for n in nos if n["id"] != "r1")
        assert novo["duration_mode"] == MODO_AUTO
        assert novo["is_root_cause"] is False

    def test_lista_vazia_nao_quebra(self):
        assert reconciliar_arvore([], ANALISE) == []


class TestMensagensParaOUsuario:
    def test_conflito_de_pai_nomeia_o_balao(self):
        nos = [_raiz(), {"id": "c1", "parent_id": "r1", "titulo": "Rolamento travado"}]
        frases = conflitos_de_pai([{"id": "c1"}], nos)
        assert frases == ["O balão “Rolamento travado” tem mais de uma seta chegando. "
                          "Deixe só uma."]

    def test_conflito_em_balao_sem_texto(self):
        nos = [_raiz(), {"id": "c1", "parent_id": "r1", "titulo": "   "}]
        assert "um balão sem texto" in conflitos_de_pai([{"id": "c1"}], nos)[0]

    def test_sem_conflito_sem_frase(self):
        assert conflitos_de_pai([], [_raiz()]) == []

    def test_mensagem_de_validacao_troca_id_por_titulo(self):
        """Quem desenhou reconhece o balão pelo texto, não pelo id do banco."""
        nos = [_raiz(), {"id": "abc123", "parent_id": None, "tipo": TIPO_CAUSA,
                         "titulo": "Falha no tacogerador"}]
        bruta = "O nó abc123 está solto (sem pai) e não é o ROOT."
        assert mensagem_com_titulos(bruta, nos) == (
            "O balão “Falha no tacogerador” está solto (sem pai) e não é o ROOT.")

    def test_descrever_balao_que_sumiu(self):
        assert "não está mais no diagrama" in descrever_no([_raiz()], "fantasma")
