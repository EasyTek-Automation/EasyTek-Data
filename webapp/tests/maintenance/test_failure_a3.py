"""
Testes de src/utils/failure_a3.py — seções A3 abaixo do diagrama.

Cobre estrutura inicial, retrocompat (análise antiga sem as seções), causas raiz
derivadas de is_root_cause (fonte única), órfãos ao desmarcar, itens de lista e a
regra de conclusão. Módulo puro (stdlib).
"""

from src.utils.failure_a3 import (
    ADICIONADA,
    ALTURA_MAX_PX,
    ALTURA_MIN_PX,
    SECOES,
    adicionar_acao,
    alturas_salvas,
    lista_responsaveis,
    backfill_secoes,
    mesclar_alturas,
    nova_acao,
    pode_concluir,
    remover_acao,
    instantaneo_secoes,
    secoes_alteradas,
    SECOES_COMPARADAS,
    texto_responsaveis,
    secoes_iniciais,
    sincronizar_acoes,
)
from src.utils.failure_tree import TIPO_ETAPA, TIPO_RAIZ, criar_etapa, criar_no


def _evento(equip="LONGI002"):
    return {"equipamento": equip, "duracao_min": 732, "rotulo": "quebra"}


def _no(id_, tipo=TIPO_ETAPA, raiz=False, titulo="", cat=None):
    n = criar_no("A1", "raiz", titulo, tipo=tipo, no_id=id_)
    n["is_root_cause"] = raiz
    n["categoria_6m"] = cat
    return n


class TestSecoesIniciais:
    def test_todas_as_secoes_presentes(self):
        s = secoes_iniciais(_evento())
        assert set(s) == set(SECOES)

    def test_problema_prefill_equipamento(self):
        # LONGI002 → LCL-4,5 via EQUIPAMENTO_NOMES
        s = secoes_iniciais(_evento("LONGI002"))
        assert s["problema"]["equipamento"] == "LCL-4,5"

    def test_area_e_subgrupo_nascem_vazios(self):
        s = secoes_iniciais(_evento())
        assert s["problema"]["area"] == ""
        assert s["problema"]["subgrupo"] == ""

    def test_actions_lista_vazia(self):
        assert secoes_iniciais(_evento())["actions"] == []

    def test_licoes_um_campo(self):
        # Seção 5 = só "Lições Aprendidas" (um campo), não mais lista de itens.
        assert secoes_iniciais(_evento())["sustainability"] == {"licoes": ""}

    def test_closing_enxuto(self):
        # Seção 6 = assinatura final do responsável + data (só isso).
        s = secoes_iniciais(_evento())
        assert s["closing"] == {"responsavel": "", "data": None}


class TestBackfill:
    """Análise antiga (sem as seções) ganha os vazios sem perder o que tinha."""

    def test_analise_antiga_ganha_todas_as_secoes(self):
        antiga = {"titulo": "x", "nos": []}
        a = backfill_secoes(antiga)
        assert set(SECOES).issubset(a)
        assert a["actions"] == []
        assert a["problema"]["descricao"] == ""

    def test_nao_sobrescreve_o_que_existe(self):
        a = backfill_secoes({"problema": {"quem": "Fulano"}, "actions": [{"id": "1"}]})
        assert a["problema"]["quem"] == "Fulano"
        assert a["actions"] == [{"id": "1"}]

    def test_completa_chaves_internas_faltantes(self):
        # problema só com 'quem' → ganha o resto das chaves
        a = backfill_secoes({"problema": {"quem": "Fulano"}})
        assert "descricao" in a["problema"]
        assert a["problema"]["descricao"] == ""

    def test_nao_muta_entrada(self):
        orig = {"titulo": "x"}
        backfill_secoes(orig)
        assert "actions" not in orig

    def test_none_passa(self):
        assert backfill_secoes(None) is None

    def test_sustainability_lista_antiga_vira_dict(self):
        # Migração: análise antiga tinha sustainability como LISTA de itens; agora é o
        # dict {licoes}. O tipo incompatível é substituído pelo default.
        a = backfill_secoes({"sustainability": [{"acao": "x"}], "closing": {"data": "2026"}})
        assert a["sustainability"] == {"licoes": ""}
        assert a["closing"]["responsavel"] == "" and a["closing"]["data"] == "2026"


class TestItensDeLista:
    def test_nova_acao_liga_ao_no(self):
        a = nova_acao("Comprar motor", node_id="s0")
        assert a["node_id"] == "s0"
        assert a["status"] == 1
        assert a["id"]

    def test_acoes_tem_ids_distintos(self):
        assert nova_acao()["id"] != nova_acao()["id"]


class TestPodeConcluir:
    """Não conclui sem ao menos uma causa raiz marcada (★)."""

    def test_sem_causa_raiz_bloqueia(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("s0", raiz=False)]
        ok, msg = pode_concluir(nos)
        assert ok is False
        assert "causa raiz" in msg

    def test_com_causa_raiz_libera(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("s0", raiz=True)]
        ok, msg = pode_concluir(nos)
        assert ok is True

    def test_root_marcado_nao_conta(self):
        nos = [_no("raiz", TIPO_RAIZ, raiz=True)]
        ok, _ = pode_concluir(nos)
        assert ok is False


class TestSincronizarAcoes:
    """Plano de Ação (Seção 4) derivado das causas-raiz (★) — fonte única."""

    def test_marcar_causa_raiz_cria_linha(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("s0", raiz=True, titulo="Correia")]
        rows = sincronizar_acoes(nos, [])
        assert len(rows) == 1
        assert rows[0]["node_id"] == "s0" and rows[0]["descricao"] == ""

    def test_uma_linha_por_causa_raiz(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True), _no("b", raiz=True), _no("c", raiz=False)]
        rows = sincronizar_acoes(nos, [])
        assert {r["node_id"] for r in rows} == {"a", "b"}

    def test_preserva_conteudo_editado(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True), _no("b", raiz=True)]
        # 'a' já tem ação escrita; marcar 'b' não pode apagar 'a'.
        antes = [{**nova_acao(node_id="a"), "descricao": "trocar correia", "responsavel": "João"}]
        rows = sincronizar_acoes(nos, antes)
        a = next(r for r in rows if r["node_id"] == "a")
        assert a["descricao"] == "trocar correia" and a["responsavel"] == "João"
        assert any(r["node_id"] == "b" and r["descricao"] == "" for r in rows)

    def test_desmarcar_remove_a_linha(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=False)]   # 'a' desmarcada
        antes = [{**nova_acao(node_id="a"), "descricao": "algo"}]
        assert sincronizar_acoes(nos, antes) == []

    def test_descarta_linha_sem_causa_raiz_ou_sem_node(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = [
            {**nova_acao(node_id="a"), "descricao": "ok"},
            {**nova_acao(node_id="fantasma"), "descricao": "orfa"},  # node não existe
            {**nova_acao(node_id=None), "descricao": "manual"},       # sem vínculo
        ]
        rows = sincronizar_acoes(nos, antes)
        assert [r["node_id"] for r in rows] == ["a"]

    def test_idempotente(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        r1 = sincronizar_acoes(nos, [])
        r2 = sincronizar_acoes(nos, r1)
        assert r1 == r2

    def test_duplicata_mesmo_node_id_mantem_a_preenchida(self):
        # Regressão do race de load: a reconciliação com store vazio chegou a gravar
        # uma linha EM BRANCO por cima da preenchida (mesmo node_id). Ao reconciliar
        # de novo, a duplicata deve colapsar numa só — ficando a preenchida.
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = [
            {**nova_acao(node_id="a"), "descricao": "Realizar troca", "responsavel": "Ana"},
            nova_acao(node_id="a"),  # duplicata em branco (corrupção)
        ]
        rows = sincronizar_acoes(nos, antes)
        assert len(rows) == 1
        assert rows[0]["descricao"] == "Realizar troca" and rows[0]["responsavel"] == "Ana"

    def test_duplicata_ordem_branca_primeiro(self):
        # Mesma corrupção, ordem invertida (branca antes da preenchida): ainda fica a boa.
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = [
            nova_acao(node_id="a"),  # branca primeiro
            {**nova_acao(node_id="a"), "prazo": "2026-08-01"},
        ]
        rows = sincronizar_acoes(nos, antes)
        assert len(rows) == 1
        assert rows[0]["prazo"] == "2026-08-01"


class TestAlturasDosCampos:
    """Altura dos campos de texto — o tamanho fica salvo na análise, então vale
    para todos os usuários que a abrirem."""

    def test_analise_nova_nasce_sem_altura_nenhuma(self):
        # Sem altura salva, cada campo se ajusta ao texto (quem faz isso é o JS).
        assert secoes_iniciais(_evento())["alturas"] == {}

    def test_le_o_mapa_salvo(self):
        a = {"alturas": {"fa-sec-prob-obs": 260, "acao:abc": 90}}
        assert alturas_salvas(a) == {"fa-sec-prob-obs": 260, "acao:abc": 90}

    def test_analise_sem_nada_devolve_vazio(self):
        assert alturas_salvas({}) == {}
        assert alturas_salvas(None) == {}

    def test_retrocompat_licoes_do_formato_antigo(self):
        # Antes do mapa `alturas`, só as Lições tinham altura, dentro de
        # sustainability. Análise daquela época continua abrindo no tamanho certo.
        a = {"sustainability": {"licoes": "x", "licoes_altura": 180}}
        assert alturas_salvas(a) == {"fa-sec-licoes": 180}

    def test_mapa_novo_tem_prioridade_sobre_o_legado(self):
        a = {"alturas": {"fa-sec-licoes": 300},
             "sustainability": {"licoes_altura": 180}}
        assert alturas_salvas(a)["fa-sec-licoes"] == 300

    def test_descarta_valor_que_nao_e_numero(self):
        a = {"alturas": {"fa-sec-prob-obs": "alto", "fa-sec-cont-acoes": None}}
        assert alturas_salvas(a) == {}

    def test_descarta_altura_fora_da_faixa(self):
        # Valor vem do navegador: negativo, zero ou absurdo é ignorado.
        a = {"alturas": {"a": -5, "b": 0, "c": ALTURA_MAX_PX + 1,
                         "d": ALTURA_MIN_PX - 1, "e": ALTURA_MIN_PX}}
        assert alturas_salvas(a) == {"e": ALTURA_MIN_PX}

    def test_aceita_altura_como_texto_ou_float(self):
        # O navegador manda number; ser tolerante evita perder o ajuste do usuário.
        a = {"alturas": {"x": "260", "y": 90.4}}
        assert alturas_salvas(a) == {"x": 260, "y": 90}

    def test_mesclar_grava_a_altura_arrastada(self):
        s = mesclar_alturas({"problema": {"descricao": "x"}}, {"fa-sec-prob-obs": 260})
        assert s["alturas"] == {"fa-sec-prob-obs": 260}
        assert s["problema"] == {"descricao": "x"}   # não mexe no resto

    def test_mesclar_preserva_alturas_de_outros_campos(self):
        # O usuário ajustou só um campo nesta visita — o que já estava salvo fica.
        s = mesclar_alturas({"alturas": {"fa-sec-licoes": 180}}, {"fa-sec-prob-obs": 260})
        assert s["alturas"] == {"fa-sec-licoes": 180, "fa-sec-prob-obs": 260}

    def test_mesclar_sobrescreve_o_mesmo_campo(self):
        s = mesclar_alturas({"alturas": {"fa-sec-licoes": 180}}, {"fa-sec-licoes": 300})
        assert s["alturas"] == {"fa-sec-licoes": 300}

    def test_mesclar_ignora_valor_invalido_sem_perder_o_salvo(self):
        s = mesclar_alturas({"alturas": {"fa-sec-licoes": 180}}, {"fa-sec-licoes": "??"})
        assert s["alturas"] == {"fa-sec-licoes": 180}

    def test_mesclar_nao_muta_a_entrada(self):
        original = {"alturas": {"fa-sec-licoes": 180}}
        mesclar_alturas(original, {"fa-sec-prob-obs": 260})
        assert original == {"alturas": {"fa-sec-licoes": 180}}

    def test_mesclar_com_secoes_vazias(self):
        assert mesclar_alturas(None, {"fa-sec-licoes": 200})["alturas"] == {"fa-sec-licoes": 200}

    def test_alturas_esta_na_whitelist_de_salvamento(self):
        # Sem isto, `salvar_secoes` descartaria o mapa e nada seria persistido.
        assert "alturas" in SECOES

    def test_backfill_da_alturas_a_analise_antiga(self):
        a = backfill_secoes({"titulo": "x"})
        assert a["alturas"] == {}

    def test_backfill_preserva_alturas_existentes(self):
        a = backfill_secoes({"alturas": {"fa-sec-licoes": 180}})
        assert a["alturas"] == {"fa-sec-licoes": 180}


class TestVariasAcoesPorCausa:
    """Uma causa raiz pode precisar de mais de uma ação — responsáveis e prazos
    diferentes. A 2ª em diante nasce do "+ ação" e carrega a marca `adicionada`."""

    def test_adicionar_cria_segunda_linha_na_mesma_causa(self):
        rows = [nova_acao(node_id="a")]
        out = adicionar_acao(rows, "a")
        assert len(out) == 2
        assert [r["node_id"] for r in out] == ["a", "a"]

    def test_linha_adicionada_vem_marcada(self):
        out = adicionar_acao([nova_acao(node_id="a")], "a")
        assert out[1][ADICIONADA] is True

    def test_linha_automatica_nao_vem_marcada(self):
        # A que nasce do ★ não tem a marca — é o que distingue as duas origens.
        assert ADICIONADA not in nova_acao(node_id="a")

    def test_nova_fica_encostada_nas_da_mesma_causa(self):
        # Não pode ir para o fim da lista: embaralharia a leitura por causa.
        rows = [nova_acao(node_id="a"), nova_acao(node_id="b")]
        out = adicionar_acao(rows, "a")
        assert [r["node_id"] for r in out] == ["a", "a", "b"]

    def test_adicionar_em_causa_sem_linha_nenhuma(self):
        out = adicionar_acao([], "a")
        assert len(out) == 1 and out[0]["node_id"] == "a"

    def test_adicionar_sem_node_id_nao_faz_nada(self):
        rows = [nova_acao(node_id="a")]
        assert adicionar_acao(rows, "") == rows

    def test_adicionar_nao_muta_a_entrada(self):
        rows = [nova_acao(node_id="a")]
        adicionar_acao(rows, "a")
        assert len(rows) == 1

    def test_sincronizar_preserva_as_varias_acoes(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = adicionar_acao([{**nova_acao(node_id="a"), "descricao": "Trocar correia"}], "a")
        antes[1]["descricao"] = "Revisar tensor"
        antes[1]["responsavel"] = "Thiago"
        out = sincronizar_acoes(nos, antes)
        assert [r["descricao"] for r in out] == ["Trocar correia", "Revisar tensor"]
        assert out[1]["responsavel"] == "Thiago"

    def test_acao_adicionada_em_branco_sobrevive_a_reconciliacao(self):
        # Regressão: sem a marca, a linha recém-criada sumia no próximo redesenho
        # do diagrama, antes de o usuário ter tempo de preenchê-la.
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = adicionar_acao([{**nova_acao(node_id="a"), "descricao": "Trocar"}], "a")
        out = sincronizar_acoes(nos, antes)
        assert len(out) == 2 and out[1]["descricao"] == ""

    def test_desmarcar_causa_remove_todas_as_acoes_dela(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=False)]   # ★ retirado
        antes = adicionar_acao([{**nova_acao(node_id="a"), "descricao": "Trocar"}], "a")
        assert sincronizar_acoes(nos, antes) == []

    def test_varias_causas_com_varias_acoes_mantem_a_ordem_dos_nos(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True), _no("b", raiz=True)]
        antes = adicionar_acao([nova_acao(node_id="a"), nova_acao(node_id="b")], "b")
        out = sincronizar_acoes(nos, antes)
        assert [r["node_id"] for r in out] == ["a", "b", "b"]

    def test_remover_tira_a_acao_adicionada(self):
        rows = adicionar_acao([nova_acao(node_id="a")], "a")
        out = remover_acao(rows, rows[1]["id"])
        assert len(out) == 1 and out[0]["id"] == rows[0]["id"]

    def test_remover_nao_apaga_a_linha_automatica(self):
        # A primeira linha nasce do ★ e só sai desmarcando a causa — o guard vive
        # no modelo, não só no esconde-botão da tela.
        rows = [nova_acao(node_id="a")]
        assert remover_acao(rows, rows[0]["id"]) == rows

    def test_remover_id_inexistente_nao_quebra(self):
        rows = adicionar_acao([nova_acao(node_id="a")], "a")
        assert remover_acao(rows, "nao-existe") == rows
        assert remover_acao(rows, "") == rows

    def test_remover_nao_muta_a_entrada(self):
        rows = adicionar_acao([nova_acao(node_id="a")], "a")
        remover_acao(rows, rows[1]["id"])
        assert len(rows) == 2


class TestRetrocompatDuplicataLegada:
    """Documento salvo antes de 2026-07-22 pode ter uma linha EM BRANCO duplicando
    a preenchida (race no load). Sem a marca `adicionada`, ela continua sendo
    colapsada — a mudança para várias ações não pode ressuscitar aquele lixo."""

    def test_duplicata_em_branco_sem_marca_continua_colapsando(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = [
            {**nova_acao(node_id="a"), "descricao": "Realizar troca", "responsavel": "Ana"},
            nova_acao(node_id="a"),   # duplicata em branco (corrupção legada)
        ]
        out = sincronizar_acoes(nos, antes)
        assert len(out) == 1
        assert out[0]["descricao"] == "Realizar troca"

    def test_duplicata_legada_ordem_invertida(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = [nova_acao(node_id="a"),
                 {**nova_acao(node_id="a"), "prazo": "2026-08-01"}]
        out = sincronizar_acoes(nos, antes)
        assert len(out) == 1 and out[0]["prazo"] == "2026-08-01"

    def test_tres_em_branco_legadas_viram_uma(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = [nova_acao(node_id="a") for _ in range(3)]
        assert len(sincronizar_acoes(nos, antes)) == 1

    def test_legada_em_branco_nao_come_a_acao_adicionada(self):
        # Documento antigo com duplicata + o usuário adiciona uma ação de verdade:
        # colapsa a duplicata e mantém a adicionada.
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = [
            {**nova_acao(node_id="a"), "descricao": "Trocar"},
            nova_acao(node_id="a"),                       # lixo legado
            nova_acao(node_id="a", adicionada=True),      # 2ª ação de verdade
        ]
        out = sincronizar_acoes(nos, antes)
        assert len(out) == 2
        assert out[0]["descricao"] == "Trocar"
        assert out[1][ADICIONADA] is True

    def test_orfa_continua_descartada(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = [nova_acao(node_id="a"),
                 {**nova_acao(node_id=None), "descricao": "solta"},
                 {**nova_acao(node_id="fantasma"), "descricao": "orfa"}]
        out = sincronizar_acoes(nos, antes)
        assert [r["node_id"] for r in out] == ["a"]

    def test_idempotente_com_varias_acoes(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        r1 = sincronizar_acoes(nos, adicionar_acao([nova_acao(node_id="a")], "a"))
        assert sincronizar_acoes(nos, r1) == r1


class TestVariosResponsaveis:
    """Uma ação pode ter mais de um responsável. Análises antigas guardaram um
    nome só, em texto — os dois formatos precisam conviver, sem migração."""

    def test_acao_nova_nasce_sem_responsavel(self):
        assert nova_acao(node_id="a")["responsavel"] == []

    def test_lista_de_nomes_passa_direto(self):
        assert lista_responsaveis(["João", "Thiago"]) == ["João", "Thiago"]

    def test_retrocompat_nome_unico_em_texto(self):
        # Formato antigo do banco: um nome só, string.
        assert lista_responsaveis("João") == ["João"]

    def test_retrocompat_texto_com_virgulas(self):
        # Formato mais antigo ainda, digitado à mão.
        assert lista_responsaveis("João, Thiago") == ["João", "Thiago"]

    def test_vazio_de_todo_jeito(self):
        for v in ("", None, [], "   ", 42):
            assert lista_responsaveis(v) == []

    def test_descarta_repetidos_e_espacos(self):
        assert lista_responsaveis(["João", " João ", "", "Thiago"]) == ["João", "Thiago"]

    def test_texto_para_leitura(self):
        assert texto_responsaveis(["João", "Thiago"]) == "João, Thiago"
        assert texto_responsaveis("João") == "João"
        assert texto_responsaveis(None) == ""

    def test_acao_com_responsavel_conta_como_preenchida(self):
        # `_acao_tem_conteudo` decide se a linha sobrevive à reconciliação: a lista
        # vazia não pode contar como conteúdo, e a lista com nome tem de contar.
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        cheia = {**nova_acao(node_id="a"), "responsavel": ["João"]}
        antes = [cheia, nova_acao(node_id="a")]      # 2a em branco, sem marca
        out = sincronizar_acoes(nos, antes)
        assert len(out) == 1 and out[0]["responsavel"] == ["João"]

    def test_acao_com_lista_vazia_nao_conta_como_preenchida(self):
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = [{**nova_acao(node_id="a"), "responsavel": []},
                 {**nova_acao(node_id="a"), "responsavel": []}]
        assert len(sincronizar_acoes(nos, antes)) == 1

    def test_retrocompat_responsavel_em_texto_sobrevive_a_reconciliacao(self):
        # Documento legado: `responsavel` string. A linha não pode ser tratada como
        # vazia e descartada.
        nos = [_no("raiz", TIPO_RAIZ), _no("a", raiz=True)]
        antes = [{**nova_acao(node_id="a"), "responsavel": "João"}]
        out = sincronizar_acoes(nos, antes)
        assert len(out) == 1 and out[0]["responsavel"] == "João"


class TestSecoesAlteradas:
    """`secoes_alteradas` — arma o aviso de "alterações não salvas" para o texto do
    A3 (achado VF-06). O risco é o falso positivo: se a página nascer marcada como
    alterada, o usuário leva um aviso de saída sem ter tocado em nada."""

    def _base(self):
        return secoes_iniciais(_evento())

    def test_sem_edicao_nao_acusa_alteracao(self):
        base = self._base()
        assert secoes_alteradas(base, dict(base)) is False

    def test_texto_digitado_acusa_alteracao(self):
        base = self._base()
        atual = {**base, "sustainability": {"licoes": "trocar a correia a cada 6 meses"}}
        assert secoes_alteradas(base, atual) is True

    def test_campo_vazio_como_none_ou_texto_em_branco_e_a_mesma_coisa(self):
        # O banco devolve `None` num campo nunca preenchido; a tela devolve "". Se
        # isso contasse como diferença, a página nasceria suja (regressão C1.6).
        base = {"problema": {"descricao": None}, "contencao": {}, "actions": [],
                "sustainability": {}, "closing": {"data": None}}
        atual = {"problema": {"descricao": ""}, "contencao": {"acoes": ""},
                 "actions": [], "sustainability": {"licoes": ""},
                 "closing": {"data": None, "responsavel": ""}}
        assert secoes_alteradas(base, atual) is False

    def test_espaco_sobrando_na_ponta_nao_conta(self):
        base = {"sustainability": {"licoes": "revisar o tensor"}}
        atual = {"sustainability": {"licoes": "  revisar o tensor "}}
        assert secoes_alteradas(base, atual) is False

    def test_altura_de_caixa_de_texto_nao_conta_como_edicao(self):
        # `alturas` não é conteúdo do A3 e entra por outro caminho (store próprio,
        # mesclado só no Salvar) — arrastar a alça não pode marcar a página como suja.
        base = {"sustainability": {"licoes": "x"}, "alturas": {}}
        atual = {"sustainability": {"licoes": "x"}, "alturas": {"fa-sec-licoes": 260}}
        assert secoes_alteradas(base, atual) is False

    def test_campo_de_exibicao_da_tela_nao_conta(self):
        # `_causa` é pendurado na linha só para mostrar o texto do balão.
        base = {"actions": [{"id": "a1", "node_id": "n1", "descricao": "trocar"}]}
        atual = {"actions": [{"id": "a1", "node_id": "n1", "descricao": "trocar",
                              "_causa": "correia rompida"}]}
        assert secoes_alteradas(base, atual) is False

    def test_responsavel_em_texto_e_em_lista_sao_o_mesmo_conteudo(self):
        # Análise antiga guarda `"João"`; a tela devolve `["João"]`. Só abrir a
        # análise não pode marcar como alterada.
        base = {"actions": [{"id": "a1", "responsavel": "João"}]}
        atual = {"actions": [{"id": "a1", "responsavel": ["João"]}]}
        assert secoes_alteradas(base, atual) is False

    def test_responsavel_a_mais_acusa_alteracao(self):
        base = {"actions": [{"id": "a1", "responsavel": ["João"]}]}
        atual = {"actions": [{"id": "a1", "responsavel": ["João", "Thiago"]}]}
        assert secoes_alteradas(base, atual) is True

    def test_acao_nova_acusa_alteracao(self):
        base = {"actions": [{"id": "a1", "node_id": "n1"}]}
        atual = {"actions": [{"id": "a1", "node_id": "n1"},
                             {"id": "a2", "node_id": "n1", ADICIONADA: True}]}
        assert secoes_alteradas(base, atual) is True

    def test_prazo_e_status_editados_acusam_alteracao(self):
        base = {"actions": [{"id": "a1", "prazo": None, "status": 1}]}
        assert secoes_alteradas(base, {"actions": [{"id": "a1", "prazo": "2026-08-30",
                                                    "status": 1}]}) is True
        assert secoes_alteradas(base, {"actions": [{"id": "a1", "prazo": None,
                                                    "status": 3}]}) is True

    def test_analise_legada_com_texto_em_evidencias_nao_nasce_suja(self):
        # O campo "Desenho / foto / evidência" saiu da tela na v3 (DS-AF3-16): o texto
        # antigo continua no banco, mas a tela não o devolve mais. Análise legada com
        # texto ali não pode abrir "com alterações não salvas".
        base = {"problema": {"descricao": "correia rompeu", "evidencias": "ver foto 3"}}
        atual = {"problema": {"descricao": "correia rompeu"}}
        assert secoes_alteradas(base, atual) is False

    def test_evidencias_ignorado_nao_esconde_edicao_real_na_secao(self):
        base = {"problema": {"descricao": "correia rompeu", "evidencias": "ver foto 3"}}
        atual = {"problema": {"descricao": "correia rompeu no rolo 2",
                              "evidencias": "ver foto 3"}}
        assert secoes_alteradas(base, atual) is True

    def test_marca_de_linha_adicionada_ausente_ou_falsa_e_a_mesma_coisa(self):
        base = {"actions": [{"id": "a1"}]}
        atual = {"actions": [{"id": "a1", ADICIONADA: False}]}
        assert secoes_alteradas(base, atual) is False

    def test_assinatura_preenchida_sozinha_no_load_nao_conta(self):
        # A seção 6 abre com o nome de quem está logado já escolhido (é a única
        # opção do dropdown), e esse nome não está no banco enquanto a análise não
        # for concluída. Se contasse, TODA análise aberta nasceria avisando
        # "alterações não salvas" — foi o falso positivo pego no QA.
        base = {"closing": {"data": None}}
        atual = {"closing": {"responsavel": "rodolfo@tekmont.com.br", "data": None}}
        assert secoes_alteradas(base, atual) is False

    def test_data_do_encerramento_editada_acusa_alteracao(self):
        # Na mesma seção 6, a data É escolha do usuário e tem de contar.
        base = {"closing": {"responsavel": "rodolfo@tekmont.com.br", "data": None}}
        atual = {"closing": {"responsavel": "rodolfo@tekmont.com.br", "data": "2026-08-07"}}
        assert secoes_alteradas(base, atual) is True

    def test_store_vazio_contra_analise_com_conteudo_acusa(self):
        assert secoes_alteradas({}, {"sustainability": {"licoes": "algo"}}) is True

    def test_instantaneo_ignora_chave_fora_da_whitelist(self):
        # Chave que não é seção do A3 não entra na comparação nem no que se salva.
        foto = instantaneo_secoes({"sustainability": {"licoes": "x"}, "lixo": {"a": 1}})
        assert "lixo" not in foto
        assert set(foto) == set(SECOES_COMPARADAS)
