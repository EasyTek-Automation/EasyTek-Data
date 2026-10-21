"""
Testes de src/utils/failure_management.py — o quadro da Gestão das Análises.

Uma classe por regra de negócio (BR-01..BR-17 do SDD
`analise-falhas-acompanhamento`). Módulo puro: sem Dash, sem Mongo, sem browser.

`HOJE` é fixo de propósito — as regras de prazo e de espera ("vencida há 12 dias")
mudariam de resultado a cada dia se a data viesse de dentro do código.
"""

from datetime import date

from src.utils.failure_a3 import (
    ESTADO_ABERTA,
    ESTADO_ACEITA,
    ESTADO_DEVOLVIDA,
    ESTADO_ENTREGUE,
    analise_travada,
    estado_analise,
    pode_entregar,
)
from src.utils.failure_management import (
    PARADA_AGUARDANDO,
    PARADA_ANALISADA,
    PARADA_DEVOLVIDA,
    PARADA_EM_ELABORACAO,
    PARADA_NAO_ANALISADA,
    SEM_RESPONSAVEL,
    acao_em_aberto,
    acao_escrita,
    acao_sem_prazo,
    acao_sem_responsavel,
    acao_vencida,
    contexto_do_retorno,
    dias_de_atraso,
    estado_da_parada,
    fila_de_aceite,
    identidade_da_falha,
    indexar_por_identidade,
    mes_da_chave,
    meses_do_periodo,
    montar_quadro,
    pendencias,
    por_responsavel,
    repeticao_no_mes,
    somar_meses,
    tem_plano_de_acao,
    voltou_depois,
)

HOJE = date(2026, 8, 7)


# --- fábricas de dado -------------------------------------------------------

def _evento(chave="PRENS002_202606_201_abc123", minutos=204, dias=2, vezes=3):
    return {"chave": chave, "duracao_min": minutos, "n_dias": dias,
            "n_apontamentos": vezes, "equipamento": chave.split("_")[0],
            "equipamento_nome": "Prensa 02", "rotulo": "correia desalinhada"}


def _acao(descricao="trocar o rolamento", responsavel=None, prazo="2026-08-30",
          status=1, node_id="n1"):
    return {"id": "a1", "node_id": node_id, "descricao": descricao,
            "responsavel": responsavel if responsavel is not None else ["João"],
            "prazo": prazo, "status": status}


def _analise(chave="PRENS002_202606_201_abc123", acoes=None, status="aberta",
             aceite=None, nos=None, titulo="correia desalinhada"):
    return {"parada_chave": chave, "titulo": titulo, "status": status,
            "actions": acoes if acoes is not None else [_acao()],
            "nos": nos if nos is not None else [{"id": "n1", "is_root_cause": True,
                                                 "tipo": "CAUSE", "titulo": "correia"}],
            "aceite": aceite, "parada": {"equipamento_nome": "Prensa 02"}}


def _aceita(por="marinho", em="2026-07-15"):
    return {"aceito_por": por, "aceito_em": em,
            "passagens": [{"acao": "entregue", "por": "rodolfo", "em": "2026-07-10"},
                          {"acao": "aceita", "por": por, "em": em}]}


# --- BR-01 ------------------------------------------------------------------

class TestMesDeReferencia:
    """BR-01 — a análise conta no mês da PARADA, não no mês em que foi feita."""

    def test_mes_sai_da_chave_da_parada(self):
        assert mes_da_chave("PRENS002_202606_201_abc123") == "202606"

    def test_chave_estranha_nao_quebra(self):
        assert mes_da_chave("lixo") is None
        assert mes_da_chave(None) is None
        assert mes_da_chave("PRENS002_ABCDEF_201_x") is None

    def test_analise_feita_em_julho_sobre_parada_de_junho_conta_em_junho(self):
        # A análise não guarda o mês: ele vem da chave da parada que ela analisa.
        analise = _analise(chave="PRENS002_202606_201_abc123")
        analise["criado_em"] = "2026-07-15"
        assert mes_da_chave(analise["parada_chave"]) == "202606"

    def test_soma_de_meses_vira_o_ano(self):
        assert somar_meses("202611", 2) == "202701"
        assert somar_meses("202601", -1) == "202512"

    def test_periodo_tem_12_meses_terminando_no_corrente(self):
        meses = meses_do_periodo(HOJE)
        assert len(meses) == 12
        assert meses[-1] == "202608" and meses[0] == "202509"


# --- BR-03 ------------------------------------------------------------------

class TestEstadoDaParada:
    """BR-03 — "analisada" é só a que o gestor aceitou."""

    def test_sem_analise(self):
        assert estado_da_parada(None) == PARADA_NAO_ANALISADA

    def test_analise_aberta_e_em_elaboracao(self):
        assert estado_da_parada(_analise()) == PARADA_EM_ELABORACAO

    def test_entregue_aguarda_aceite(self):
        assert estado_da_parada(_analise(status="concluida")) == PARADA_AGUARDANDO

    def test_aceita_conta_como_analisada(self):
        analise = _analise(status="concluida", aceite=_aceita())
        assert estado_da_parada(analise) == PARADA_ANALISADA

    def test_devolvida(self):
        aceite = {"passagens": [{"acao": "entregue", "por": "r", "em": "2026-07-10"},
                                {"acao": "devolvida", "por": "m", "em": "2026-07-11",
                                 "motivo": "ação sem prazo"}]}
        assert estado_da_parada(_analise(aceite=aceite)) == PARADA_DEVOLVIDA

    def test_analise_antiga_sem_campo_de_aceite_se_comporta_sozinha(self):
        # Dado legado: `aberta` vira em elaboração; `concluida` cai na fila do gestor.
        velha = {"parada_chave": "X_202601_201_a", "status": "aberta", "actions": []}
        assert estado_da_parada(velha) == PARADA_EM_ELABORACAO
        velha["status"] = "concluida"
        assert estado_da_parada(velha) == PARADA_AGUARDANDO


# --- BR-04 ------------------------------------------------------------------

class TestAcaoEscrita:
    """BR-04 — a linha nasce sozinha do ★; só conta com descrição preenchida."""

    def test_linha_em_branco_nao_e_acao(self):
        assert acao_escrita(_acao(descricao="")) is False
        assert acao_escrita(_acao(descricao="   ")) is False

    def test_descricao_preenchida_conta(self):
        assert acao_escrita(_acao()) is True

    def test_acao_sem_dono_e_sem_prazo_ainda_conta_como_escrita(self):
        assert acao_escrita(_acao(responsavel=[], prazo=None)) is True

    def test_acao_com_dono_e_prazo_sem_descricao_nao_conta(self):
        assert acao_escrita(_acao(descricao="", responsavel=["João"],
                                  prazo="2026-08-30")) is False

    def test_analise_sem_acao_escrita_nao_tem_plano(self):
        assert tem_plano_de_acao(_analise(acoes=[_acao(descricao="")])) is False
        assert tem_plano_de_acao(_analise()) is True


# --- BR-05 ------------------------------------------------------------------

class TestStatusEmAberto:
    """BR-05 — em aberto é "A fazer" e "Em andamento"; feito não volta a cobrar."""

    def test_a_fazer_e_em_andamento_estao_em_aberto(self):
        assert acao_em_aberto(_acao(status=1)) is True
        assert acao_em_aberto(_acao(status=2)) is True

    def test_concluido_e_eficacia_nao_estao_em_aberto(self):
        assert acao_em_aberto(_acao(status=3)) is False
        assert acao_em_aberto(_acao(status=4)) is False

    def test_sem_status_e_lido_como_a_fazer(self):
        assert acao_em_aberto({"descricao": "x"}) is True
        assert acao_em_aberto(_acao(status=None)) is True


# --- BR-06 ------------------------------------------------------------------

class TestAcaoVencida:
    """BR-06 — vence no FIM do dia do prazo; concluída em atraso não conta."""

    def test_prazo_passado_e_em_aberto_esta_vencida(self):
        assert acao_vencida(_acao(prazo="2026-07-26"), HOJE) is True
        assert dias_de_atraso(_acao(prazo="2026-07-26"), HOJE) == 12

    def test_nao_vence_no_proprio_dia_do_prazo(self):
        assert acao_vencida(_acao(prazo="2026-08-07"), HOJE) is False

    def test_vence_no_dia_seguinte(self):
        assert acao_vencida(_acao(prazo="2026-08-06"), HOJE) is True

    def test_concluida_com_prazo_passado_nao_esta_vencida(self):
        assert acao_vencida(_acao(prazo="2026-07-15", status=3), HOJE) is False

    def test_sem_prazo_nao_vence(self):
        assert acao_vencida(_acao(prazo=None), HOJE) is False
        assert dias_de_atraso(_acao(prazo=None), HOJE) is None

    def test_prazo_com_lixo_nao_quebra(self):
        assert acao_vencida(_acao(prazo="ontem"), HOJE) is False


# --- BR-07 ------------------------------------------------------------------

class TestSemDonoSemPrazo:
    """BR-07 — os três formatos de responsável contam como vazio do mesmo jeito."""

    def test_lista_vazia_texto_vazio_e_ausente_sao_sem_responsavel(self):
        assert acao_sem_responsavel(_acao(responsavel=[])) is True
        assert acao_sem_responsavel(_acao(responsavel="")) is True
        assert acao_sem_responsavel({"descricao": "x"}) is True

    def test_texto_legado_com_nome_tem_responsavel(self):
        assert acao_sem_responsavel(_acao(responsavel="João")) is False

    def test_sem_prazo(self):
        assert acao_sem_prazo(_acao(prazo=None)) is True
        assert acao_sem_prazo(_acao(prazo="")) is True
        assert acao_sem_prazo(_acao()) is False

    def test_acao_com_dois_problemas_aparece_uma_vez_com_dois_motivos(self):
        analise = _analise(acoes=[_acao(responsavel=[], prazo=None)])
        itens = [i for i in pendencias(analise, _evento(), HOJE) if i["tipo"] == "acao"]
        assert len(itens) == 1
        assert set(itens[0]["motivos"]) == {"sem_responsavel", "sem_prazo"}


# --- BR-08 ------------------------------------------------------------------

class TestPorResponsavel:
    """BR-08 — ação com dois donos conta para os dois; a soma passa do total."""

    def _cenario(self):
        return [_analise(acoes=[
            {**_acao(descricao="trocar rolamento", responsavel=["João", "Thiago"],
                     prazo="2026-07-26"), "id": "a1"},
            {**_acao(descricao="alinhar correia", responsavel=["João"]), "id": "a2"},
            {**_acao(descricao="revisar esticador", responsavel=["Thiago"],
                     status=3), "id": "a3"},
            {**_acao(descricao="trocar sensor", responsavel=["João"]), "id": "a4"},
            {**_acao(descricao="comprar peça", responsavel=[], prazo=None), "id": "a5"},
        ])]

    def test_soma_passa_do_total_por_causa_da_acao_com_dois_donos(self):
        linhas = por_responsavel(self._cenario(), HOJE)
        assert sum(l["acoes"] for l in linhas) == 6      # 5 ações, uma com 2 donos

    def test_contagem_por_pessoa(self):
        por_pessoa = {l["pessoa"]: l for l in por_responsavel(self._cenario(), HOJE)}
        assert por_pessoa["João"]["acoes"] == 3
        assert por_pessoa["João"]["vencidas"] == 1
        assert por_pessoa["João"]["em_aberto"] == 2
        assert por_pessoa["Thiago"]["acoes"] == 2
        assert por_pessoa["Thiago"]["feitas"] == 1

    def test_sem_responsavel_vira_linha_propria_no_fim(self):
        linhas = por_responsavel(self._cenario(), HOJE)
        assert linhas[-1]["pessoa"] == SEM_RESPONSAVEL
        assert linhas[-1]["acoes"] == 1

    def test_ordem_mais_vencidas_primeiro(self):
        linhas = por_responsavel(self._cenario(), HOJE)
        assert linhas[0]["pessoa"] == "João"          # 1 vencida e mais ações

    def test_linha_em_branco_nao_entra_na_contagem(self):
        analises = [_analise(acoes=[_acao(descricao=""), _acao(descricao="x")])]
        assert sum(l["acoes"] for l in por_responsavel(analises, HOJE)) == 1

    def test_nome_repetido_na_mesma_acao_conta_uma_vez(self):
        analises = [_analise(acoes=[_acao(responsavel=["João", "João"])])]
        linhas = por_responsavel(analises, HOJE)
        assert len(linhas) == 1 and linhas[0]["acoes"] == 1


# --- BR-09 ------------------------------------------------------------------

class TestRepeticaoNoMes:
    """BR-09 — impacto medido em tempo, dias e vezes, sempre os três."""

    def test_tres_numeros_juntos(self):
        r = repeticao_no_mes(_evento(minutos=304, dias=4, vezes=21))
        assert r == {"minutos": 304.0, "dias": 4, "vezes": 21}

    def test_evento_sem_os_campos_nao_quebra(self):
        assert repeticao_no_mes({}) == {"minutos": 0.0, "dias": 1, "vezes": 1}

    def test_vinte_paradas_curtas_no_mesmo_dia_aparecem_nas_vezes(self):
        # O caso que motivou a revisão da regra: 20 paradas de 5 min num dia só.
        r = repeticao_no_mes(_evento(minutos=100, dias=1, vezes=20))
        assert r["dias"] == 1 and r["vezes"] == 20 and r["minutos"] == 100.0


# --- BR-10 ------------------------------------------------------------------

class TestFalhaQueVoltou:
    """BR-10 — mesma falha (equipamento+código+relato) nos 3 meses seguintes."""

    def test_identidade_ignora_o_mes(self):
        assert identidade_da_falha("PRENS002_202606_201_abc") == "PRENS002_201_abc"

    def test_mesma_falha_em_outro_mes_tem_a_mesma_identidade(self):
        a = identidade_da_falha("PRENS002_202606_201_abc")
        b = identidade_da_falha("PRENS002_202608_201_abc")
        assert a == b

    def test_relato_diferente_e_outra_falha(self):
        a = identidade_da_falha("PRENS002_202606_201_abc")
        b = identidade_da_falha("PRENS002_202608_201_xyz")
        assert a != b

    def test_voltou_dentro_da_janela(self):
        indice = indexar_por_identidade([_evento("PRENS002_202608_201_abc123",
                                                 minutos=210, dias=2, vezes=2)])
        r = voltou_depois("PRENS002_202606_201_abc123", indice, HOJE)
        assert r["voltou"] is True and r["meses"] == ["202608"] and r["minutos"] == 210.0

    def test_fora_da_janela_e_falha_nova(self):
        indice = indexar_por_identidade([_evento("PRENS002_202610_201_abc123")])
        r = voltou_depois("PRENS002_202606_201_abc123", indice, date(2026, 12, 1))
        assert r["voltou"] is False

    def test_volta_pequena_conta(self):
        # A volta não precisa passar do gatilho: a pergunta é se o problema continua.
        indice = indexar_por_identidade([_evento("PRENS002_202607_201_abc123",
                                                 minutos=30, dias=1, vezes=1)])
        assert voltou_depois("PRENS002_202606_201_abc123", indice, HOJE)["voltou"] is True

    def test_voltou_em_dois_meses_conta_uma_vez_e_soma(self):
        indice = indexar_por_identidade([
            _evento("PRENS002_202607_201_abc123", minutos=100),
            _evento("PRENS002_202608_201_abc123", minutos=110)])
        r = voltou_depois("PRENS002_202606_201_abc123", indice, HOJE)
        assert r["voltou"] is True and len(r["meses"]) == 2 and r["minutos"] == 210.0

    def test_ainda_observando_nao_e_nao_voltou(self):
        # Análise de agosto lida em agosto: setembro a novembro nem aconteceram.
        r = voltou_depois("PRENS002_202608_201_abc123", {}, HOJE)
        assert r["voltou"] is False
        assert r["ainda_observando"] is True and r["meses_faltando"] == 3

    def test_janela_vencida_sem_volta_e_nao_voltou(self):
        r = voltou_depois("PRENS002_202601_201_abc123", {}, HOJE)
        assert r["voltou"] is False and r["ainda_observando"] is False


# --- BR-11 ------------------------------------------------------------------

class TestContextoDoRetorno:
    """BR-11 — o marco é o aceite (o único com data), nunca "depois do conserto"."""

    def test_voltou_depois_do_aceite(self):
        analise = _analise(status="concluida", aceite=_aceita(em="2026-07-15"))
        assert contexto_do_retorno(analise, ["202608"]) == "depois_do_aceite"

    def test_voltou_antes_do_aceite(self):
        analise = _analise(status="concluida", aceite=_aceita(em="2026-08-02"))
        assert contexto_do_retorno(analise, ["202607"]) == "antes_do_aceite"

    def test_sem_aceite_e_sempre_antes(self):
        assert contexto_do_retorno(_analise(), ["202608"]) == "antes_do_aceite"


# --- BR-13 / BR-14 / BR-16 --------------------------------------------------

class TestEstadoEEntrega:
    """BR-13, BR-14 e BR-16 — estado derivado, requisitos e trava."""

    def test_estado_derivado(self):
        assert estado_analise(_analise()) == ESTADO_ABERTA
        assert estado_analise(_analise(status="concluida")) == ESTADO_ENTREGUE
        assert estado_analise(_analise(status="concluida",
                                       aceite=_aceita())) == ESTADO_ACEITA

    def test_devolvida_pela_ultima_passagem(self):
        aceite = {"passagens": [{"acao": "entregue", "por": "r", "em": "2026-07-10"},
                                {"acao": "devolvida", "por": "m", "em": "2026-07-11",
                                 "motivo": "sem prazo"}]}
        assert estado_analise(_analise(aceite=aceite)) == ESTADO_DEVOLVIDA

    def test_trava_vale_para_entregue_e_aceita(self):
        assert analise_travada(_analise()) is False
        assert analise_travada(_analise(status="concluida")) is True
        assert analise_travada(_analise(status="concluida", aceite=_aceita())) is True

    def test_entrega_exige_causa_raiz(self):
        ok, faltas = pode_entregar([{"id": "n1", "tipo": "CAUSE"}], [])
        assert ok is False and "causa raiz" in faltas[0]

    def test_toda_causa_raiz_precisa_de_acao(self):
        nos = [{"id": "n1", "is_root_cause": True, "tipo": "CAUSE", "titulo": "correia"},
               {"id": "n2", "is_root_cause": True, "tipo": "CAUSE", "titulo": "tensor gasto"}]
        ok, faltas = pode_entregar(nos, [_acao(node_id="n1")])
        assert ok is False
        assert any("tensor gasto" in f and "sem ação escrita" in f for f in faltas)

    def test_acao_sem_responsavel_bloqueia_com_o_nome_da_acao(self):
        nos = [{"id": "n1", "is_root_cause": True, "tipo": "CAUSE", "titulo": "correia"}]
        ok, faltas = pode_entregar(nos, [_acao(responsavel=[])])
        assert ok is False and any("sem responsável" in f for f in faltas)

    def test_acao_sem_prazo_bloqueia(self):
        nos = [{"id": "n1", "is_root_cause": True, "tipo": "CAUSE", "titulo": "correia"}]
        ok, faltas = pode_entregar(nos, [_acao(prazo=None)])
        assert ok is False and any("sem prazo" in f for f in faltas)

    def test_completa_pode_entregar(self):
        nos = [{"id": "n1", "is_root_cause": True, "tipo": "CAUSE", "titulo": "correia"}]
        ok, faltas = pode_entregar(nos, [_acao()])
        assert ok is True and faltas == []

    def test_linha_em_branco_nao_conta_como_acao_da_causa(self):
        nos = [{"id": "n1", "is_root_cause": True, "tipo": "CAUSE", "titulo": "correia"}]
        ok, faltas = pode_entregar(nos, [_acao(descricao="")])
        assert ok is False and any("sem ação escrita" in f for f in faltas)


# --- BR-17 ------------------------------------------------------------------

class TestFilaDeAceite:
    """BR-17 — entra na entrega, sai no aceite; mais antiga primeiro."""

    def _entregue(self, chave, em="2026-07-26", devolucoes=0):
        passagens = []
        for _ in range(devolucoes):
            passagens += [{"acao": "entregue", "por": "rodolfo", "em": "2026-07-01"},
                          {"acao": "devolvida", "por": "marinho", "em": "2026-07-02",
                           "motivo": "ação sem prazo"}]
        passagens.append({"acao": "entregue", "por": "rodolfo", "em": em})
        return _analise(chave=chave, status="concluida",
                        aceite={"passagens": passagens})

    def test_so_entregues_entram(self):
        analises = [self._entregue("A_202606_201_a"), _analise("B_202606_201_b"),
                    _analise("C_202606_201_c", status="concluida", aceite=_aceita())]
        fila = fila_de_aceite(analises, {}, HOJE)
        assert [f["chave"] for f in fila] == ["A_202606_201_a"]

    def test_ordem_mais_antiga_primeiro(self):
        analises = [self._entregue("A_202606_201_a", em="2026-08-05"),
                    self._entregue("B_202603_201_b", em="2026-06-27")]
        fila = fila_de_aceite(analises, {}, HOJE)
        assert [f["chave"] for f in fila] == ["B_202603_201_b", "A_202606_201_a"]
        assert fila[0]["dias_esperando"] == 41

    def test_mostra_quem_entregou_e_quantas_devolucoes(self):
        fila = fila_de_aceite([self._entregue("A_202606_201_a", devolucoes=1)], {}, HOJE)
        assert fila[0]["entregue_por"] == "rodolfo"
        assert fila[0]["devolvida_vezes"] == 1

    def test_analise_antiga_concluida_entra_com_a_data_de_conclusao(self):
        velha = {"parada_chave": "X_202601_201_a", "status": "concluida",
                 "data_conclusao_analise": "2026-06-27", "actions": [], "nos": []}
        fila = fila_de_aceite([velha], {}, HOJE)
        assert len(fila) == 1 and fila[0]["dias_esperando"] == 41


# --- BR-12 + quadro inteiro -------------------------------------------------

class TestQuadro:
    """BR-12 e a montagem completa — os números que a tela mostra."""

    def _cenario(self):
        elegiveis = [
            _evento("PRENS002_202606_201_abc123"),                       # aceita
            _evento("LONGI002_202606_201_def456"),                       # em elaboração
            _evento("SOLDA001_202606_201_ghi789"),                       # sem análise
        ]
        analises = [
            _analise("PRENS002_202606_201_abc123", status="concluida", aceite=_aceita()),
            _analise("LONGI002_202606_201_def456", acoes=[_acao(descricao="")]),
        ]
        return elegiveis, analises

    def test_conta_elegiveis_analisadas_e_com_plano(self):
        elegiveis, analises = self._cenario()
        q = montar_quadro(elegiveis, elegiveis, analises, HOJE)
        junho = [m for m in q["por_mes"] if m["mes"] == "202606"][0]
        assert junho["elegiveis"] == 3
        assert junho["analisadas"] == 1          # só a aceita
        assert junho["em_elaboracao"] == 1
        assert junho["nao_analisadas"] == 1
        assert junho["com_plano"] == 1           # a de linha em branco não conta

    def test_cartoes(self):
        elegiveis, analises = self._cenario()
        c = montar_quadro(elegiveis, elegiveis, analises, HOJE)["cartoes"]
        assert c["elegiveis"] == 3 and c["analisadas"] == 1
        assert c["analisadas_de"] == 3           # percentual nunca vai sozinho

    def test_com_plano_conta_contra_as_analises_existentes(self):
        # Achado do dado real: com o denominador nas aceitas, o cartão dizia "2 de 0"
        # enquanto ninguém tivesse aceitado nada.
        elegiveis, analises = self._cenario()
        c = montar_quadro(elegiveis, elegiveis, analises, HOJE)["cartoes"]
        assert c["analisadas"] == 1 and c["com_plano"] == 1
        assert c["com_plano_de"] == 2          # duas análises existem no período

    def test_periodo_tem_12_meses_e_marca_o_corrente(self):
        q = montar_quadro([], [], [], HOJE)
        assert len(q["por_mes"]) == 12
        assert q["mes_corrente"] == "202608"

    def test_mes_sem_parada_fica_zerado_mas_presente(self):
        # O mês precisa existir na lista para a tela poder dizer POR QUE está vazio.
        q = montar_quadro([], [], [], HOJE)
        assert all(m["elegiveis"] == 0 for m in q["por_mes"])

    def test_mes_sem_nenhuma_parada_e_marcado_como_sem_dado(self):
        # BR-12: barra vazia sozinha não distingue "mês bom" de "mês não carregado".
        elegiveis = [_evento("PRENS002_202606_201_abc123")]
        q = montar_quadro(elegiveis, elegiveis, [], HOJE)
        junho = [m for m in q["por_mes"] if m["mes"] == "202606"][0]
        vazio = [m for m in q["por_mes"] if m["mes"] == "202512"][0]
        assert junho["tem_dado"] is True
        assert vazio["tem_dado"] is False

    def test_mes_com_parada_abaixo_do_gatilho_tem_dado(self):
        # O mês teve parada, só nenhuma grande o bastante: é mês bom, não mês vazio.
        pequena = _evento("PRENS002_202605_201_zzz999", minutos=10)
        q = montar_quadro([], [pequena], [], HOJE)
        maio = [m for m in q["por_mes"] if m["mes"] == "202605"][0]
        assert maio["tem_dado"] is True and maio["elegiveis"] == 0

    def test_parada_fora_do_periodo_e_ignorada(self):
        antigo = _evento("PRENS002_202401_201_abc123")
        q = montar_quadro([antigo], [antigo], [], HOJE)
        assert sum(m["elegiveis"] for m in q["por_mes"]) == 0

    def test_parada_sem_analise_nao_entra_na_reincidencia(self):
        # Sem análise não há o que observar — o número fala do tratamento.
        elegiveis = [_evento("SOLDA001_202606_201_ghi789")]
        q = montar_quadro(elegiveis, elegiveis, [], HOJE)
        assert q["reincidencia"] == []

    def test_reincidencia_traz_repeticao_contexto_e_volta(self):
        elegiveis = [_evento("PRENS002_202606_201_abc123", minutos=204, dias=2, vezes=3)]
        todos = elegiveis + [_evento("PRENS002_202608_201_abc123", minutos=210,
                                     dias=2, vezes=2)]
        analises = [_analise("PRENS002_202606_201_abc123", status="concluida",
                             aceite=_aceita(em="2026-07-15"))]
        r = montar_quadro(elegiveis, todos, analises, HOJE)["reincidencia"][0]
        assert r["voltou"] is True and r["meses"] == ["202608"]
        assert r["repeticao"]["vezes"] == 3
        assert r["contexto"] == "depois_do_aceite"

    def test_fila_ignora_o_recorte_de_mes(self):
        # A fila é operacional: análise de março esperando há meses não pode sumir.
        antiga = _analise("A_202603_201_a", status="concluida",
                          aceite={"passagens": [{"acao": "entregue", "por": "r",
                                                 "em": "2026-06-27"}]})
        q = montar_quadro([], [], [antiga], HOJE)
        assert len(q["fila"]) == 1

    def test_pendencias_ordenadas_vencida_primeiro(self):
        analises = [
            _analise("A_202606_201_a", acoes=[_acao(descricao="vencida",
                                                    prazo="2026-07-26")]),
            _analise("B_202606_201_b", acoes=[_acao(descricao="sem dono",
                                                    responsavel=[])]),
        ]
        q = montar_quadro([_evento("A_202606_201_a"), _evento("B_202606_201_b")],
                          [], analises, HOJE)
        motivos = [i["motivos"][0] for i in q["atencao"] if i["tipo"] == "acao"]
        assert motivos[0] == "vencida"

    def test_analise_em_elaboracao_vira_pendencia(self):
        q = montar_quadro([_evento("A_202606_201_a")], [],
                          [_analise("A_202606_201_a")], HOJE)
        tipos = [i["motivos"][0] for i in q["atencao"] if i["tipo"] == "analise"]
        assert tipos == ["em_elaboracao"]

    def test_analise_devolvida_leva_o_motivo_junto(self):
        aceite = {"passagens": [{"acao": "entregue", "por": "r", "em": "2026-07-10"},
                                {"acao": "devolvida", "por": "marinho",
                                 "em": "2026-07-11", "motivo": "ação sem prazo"}]}
        q = montar_quadro([_evento("A_202606_201_a")], [],
                          [_analise("A_202606_201_a", aceite=aceite)], HOJE)
        item = [i for i in q["atencao"] if i["tipo"] == "analise"][0]
        assert item["motivos"] == ["devolvida"]
        assert item["motivo_devolucao"] == "ação sem prazo"
