"""Testes do montador de dados do material mensal (S1 do slide da Análise de Falhas).

Camada pura: recebe dicionários de análise e devolve o conteúdo dos slides. Nada de
Mongo aqui — o acesso ao banco vive em `failure_analysis_db.listar_analises_do_mes`.
"""

import unittest

from src.utils.failure_slides import (
    MAX_FOTOS_SLIDE,
    acoes,
    arvore_em_niveis,
    cabecalho,
    esta_iniciada,
    montar_mes,
    montar_slide,
)


def _no(id_, parent, tipo, titulo="", ordem=0, minutos=None, raiz=False):
    return {"id": id_, "parent_id": parent, "tipo": tipo, "titulo": titulo,
            "sort_order": ordem, "duration_min": minutos, "is_root_cause": raiz}


def _analise(**kw):
    """Análise recém-criada: dois balões, nenhum texto — o estado 'não iniciada'."""
    base = {
        "id": "6a59204d9bd97f1b60a3c0fe",
        "parada_chave": "LONGI002_202606_201_a4c2d07b",
        "titulo": "quebra motor cisalha 5019483",
        "status": "aberta",
        "responsavel": "Rodolfo J. Silva",
        "parada": {"equipamento": "LONGI002", "equipamento_nome": "LCL-4,5",
                   "causa": "201", "duracao_min": 732, "n_apontamentos": 4,
                   "ordens": [10514832, 10524790], "n_dias": 1},
        "nos": [_no("raiz", None, "ROOT", "Parada da LCL-4,5"),
                _no("s1", "raiz", "STEP", "quebra motor cisalha", minutos=244)],
        "problema": {"descricao": "", "area": "", "observacoes": ""},
        "contencao": {"acoes": ""},
        "actions": [],
        "sustainability": {"licoes": ""},
        "closing": {"responsavel": "", "data": None},
        "fotos": [],
    }
    base.update(kw)
    return base


class TestEstaIniciada(unittest.TestCase):
    def test_analise_recem_criada_nao_esta_iniciada(self):
        self.assertFalse(esta_iniciada(_analise()))

    def test_balao_a_mais_ja_conta_como_iniciada(self):
        a = _analise()
        a["nos"].append(_no("c1", "s1", "CAUSE", "rolamento travado"))
        self.assertTrue(esta_iniciada(a))

    def test_texto_em_qualquer_secao_conta(self):
        for secao, campo in (("problema", "descricao"), ("problema", "observacoes"),
                             ("contencao", "acoes"), ("sustainability", "licoes")):
            a = _analise()
            a[secao] = dict(a[secao], **{campo: "algo escrito"})
            self.assertTrue(esta_iniciada(a), f"{secao}.{campo} deveria contar")

    def test_espaco_em_branco_nao_conta_como_texto(self):
        a = _analise()
        a["problema"] = dict(a["problema"], descricao="   \n  ")
        self.assertFalse(esta_iniciada(a))

    def test_acao_registrada_conta(self):
        a = _analise(actions=[{"node_id": "s1", "descricao": "trocar rolamento"}])
        self.assertTrue(esta_iniciada(a))


class TestCabecalho(unittest.TestCase):
    def test_duracao_em_horas_e_minutos(self):
        self.assertEqual(cabecalho(_analise())["duracao_texto"], "12 h 12 min")

    def test_parada_curta_sai_so_em_minutos(self):
        a = _analise(parada={"equipamento_nome": "LWB", "duracao_min": 45})
        self.assertEqual(cabecalho(a)["duracao_texto"], "45 min")

    def test_usa_nome_do_equipamento_e_cai_para_o_codigo(self):
        self.assertEqual(cabecalho(_analise())["equipamento"], "LCL-4,5")
        a = _analise(parada={"equipamento": "LONGI002", "duracao_min": 10})
        self.assertEqual(cabecalho(a)["equipamento"], "LONGI002")

    def test_conta_ordens_da_parada(self):
        self.assertEqual(cabecalho(_analise())["n_ordens"], 2)


class TestArvoreEmNiveis(unittest.TestCase):
    def test_niveis_e_ordem_de_leitura(self):
        nos = [_no("raiz", None, "ROOT", "parada"),
               _no("s1", "raiz", "STEP", "etapa 1", ordem=0),
               _no("c1", "s1", "CAUSE", "causa A", ordem=0),
               _no("c2", "s1", "CAUSE", "causa B", ordem=1),
               _no("s2", "raiz", "STEP", "etapa 2", ordem=1)]
        saida = arvore_em_niveis(nos)
        self.assertEqual([n["id"] for n in saida], ["raiz", "s1", "c1", "c2", "s2"])
        self.assertEqual([n["nivel"] for n in saida], [0, 1, 2, 2, 1])
        self.assertEqual(saida[1]["n_filhos"], 2)

    def test_marca_a_causa_raiz(self):
        nos = [_no("raiz", None, "ROOT"), _no("c1", "raiz", "CAUSE", "x", raiz=True)]
        self.assertTrue(arvore_em_niveis(nos)[1]["causa_raiz"])

    def test_arvore_vazia_devolve_lista_vazia(self):
        self.assertEqual(arvore_em_niveis([]), [])

    def test_arvore_sem_raiz_nao_perde_balao(self):
        nos = [_no("a", "sumiu", "CAUSE", "orfao 1"), _no("b", "sumiu", "CAUSE", "orfao 2")]
        self.assertEqual(len(arvore_em_niveis(nos)), 2)


class TestAcoes(unittest.TestCase):
    def test_causa_vem_do_balao_e_status_por_extenso(self):
        a = _analise(actions=[{"node_id": "s1", "descricao": "trocar rolamento",
                               "responsavel": "Thiago", "prazo": "2026-08-30", "status": 2}])
        linha = acoes(a)[0]
        self.assertEqual(linha["causa"], "quebra motor cisalha")
        self.assertEqual(linha["status_texto"], "Em andamento")

    def test_linha_orfa_sobrevive_sem_causa(self):
        a = _analise(actions=[{"node_id": "balao-que-sumiu", "descricao": "x", "status": 1}])
        self.assertEqual(acoes(a)[0]["causa"], "")

    def test_status_desconhecido_nao_quebra(self):
        a = _analise(actions=[{"node_id": "s1", "status": 99}])
        self.assertEqual(acoes(a)[0]["status_texto"], "")


class TestMontarSlide(unittest.TestCase):
    def test_slide_traz_todos_os_blocos(self):
        a = _analise()
        a["problema"] = dict(a["problema"], descricao="motor queimado")
        s = montar_slide(a)
        for chave in ("cabecalho", "problema", "contencao", "arvore", "acoes",
                      "licoes", "encerramento", "fotos"):
            self.assertIn(chave, s)
        self.assertEqual(s["problema"]["descricao"], "motor queimado")

    def test_analise_concluida_e_sinalizada(self):
        self.assertTrue(montar_slide(_analise(status="concluida"))["concluida"])

    def test_sem_foto_no_file_server_nao_quebra(self):
        a = _analise(fotos=[{"arquivo": "nao-existe.jpg", "legenda": "x"}])
        f = montar_slide(a)["fotos"]
        self.assertEqual(f["itens"], [])
        self.assertEqual(f["total"], 1)
        self.assertEqual(f["ocultas"], 1)


class TestMontarMes(unittest.TestCase):
    def _iniciada(self, minutos, chave):
        a = _analise(parada={"equipamento_nome": "LCT-2,5", "duracao_min": minutos},
                     parada_chave=chave)
        a["problema"] = dict(a["problema"], descricao="texto qualquer")
        return a

    def test_separa_slides_das_nao_iniciadas(self):
        r = montar_mes([self._iniciada(100, "A_202607_201_a"), _analise()], 2026, 7)
        self.assertEqual(len(r["slides"]), 1)
        self.assertEqual(len(r["nao_iniciadas"]), 1)
        self.assertEqual(r["total_analises"], 2)

    def test_slides_saem_da_parada_mais_longa_para_a_mais_curta(self):
        r = montar_mes([self._iniciada(60, "A_202607_201_a"),
                        self._iniciada(600, "B_202607_201_b"),
                        self._iniciada(300, "C_202607_201_c")], 2026, 7)
        self.assertEqual([s["cabecalho"]["duracao_min"] for s in r["slides"]], [600, 300, 60])

    def test_titulo_do_material_em_portugues(self):
        self.assertEqual(montar_mes([], 2026, 7)["titulo"],
                         "Análises de Falha — julho de 2026")

    def test_mes_sem_analise_devolve_material_vazio(self):
        r = montar_mes([], 2026, 8)
        self.assertEqual(r["slides"], [])
        self.assertEqual(r["nao_iniciadas"], [])
        self.assertEqual(r["mes_ref"], "202608")

    def test_limite_de_fotos_por_slide_e_o_padrao(self):
        self.assertEqual(MAX_FOTOS_SLIDE, 4)


if __name__ == "__main__":
    unittest.main()
