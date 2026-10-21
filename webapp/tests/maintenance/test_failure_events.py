"""
Testes de src/utils/failure_events.py — agregação de apontamentos em eventos de falha.

As fixtures reproduzem apontamentos **reais** de `ZPP_Paradas` (LONGI002,
22/06/2026), o mesmo evento que originou o A3 "Quebra do motor da cisalha":
4 apontamentos, 2 ordens SAP, 732 min, entrecortados por refeição e DDS.

Cobre os casos obrigatórios 1 (listagem), 3 (nó raiz), 4 (primeira causa) e
19 (parada sem hora final). Módulo puro — não toca no Mongo.
"""

from datetime import date, datetime

from src.utils.failure_events import (
    FAIXA_25_A_60,
    FAIXA_ACIMA_60,
    FAIXA_ATE_25,
    FAIXAS_DURACAO,
    agrupar_eventos,
    ano_padrao,
    carregar_gatilho,
    ano_valido,
    anos_disponiveis,
    duracao_na_faixa,
    evento_atinge_gatilho,
    exibir_todas_as_paradas,
    faixa_duracao,
    faixas_ativas,
    montar_chave,
    normalizar_apontamento,
    parse_chave,
    titulo_sugerido,
)

TXT_QUEBRA = "quebra motor cisalaha 5019483"


def _doc(hora_ini, hora_fim, duracao, causa="201", texto=TXT_QUEBRA,
         ordem=10514832, dia=22, mes=6, equip="LONGI002", descricao="Paradas por quebra/falhas."):
    """Monta um doc cru de ZPP_Paradas no formato exato que o pymongo devolve."""
    return {
        "centro_de_trabalho": equip,
        "ordem": ordem,
        "inicio_execucao": datetime(2026, mes, dia, 0, 0),
        "fim_execucao": datetime(2026, mes, dia, 0, 0),
        "inicio_real_hora": hora_ini,
        "fim_real_hora": hora_fim,
        "causa_do_desvio": causa,
        "duration_min": duracao,
        "descricao": descricao,
        "texto_de_confirmacao": texto,
    }


def _evento_real():
    """Os 4 apontamentos reais da quebra do motor da cisalha em 22/06/2026."""
    return [
        _doc("09:11:00", "11:59:00", 168, ordem=10514832),
        _doc("13:01:00", "14:59:00", 118, ordem=10514832),
        _doc("15:31:00", "18:31:00", 180, ordem=10524790),
        _doc("19:33:00", "23:59:00", 266, ordem=10524790),
    ]


class TestNormalizarApontamento:
    """`duration_min` é a fonte única; `inicio_real_hora` é só exibição."""

    def test_combina_data_com_hora_real(self):
        a = normalizar_apontamento(_doc("09:11:00", "11:59:00", 168))
        assert a["inicio"] == datetime(2026, 6, 22, 9, 11)

    def test_usa_duration_min_como_duracao_oficial(self):
        a = normalizar_apontamento(_doc("09:11:00", "11:59:00", 168))
        assert a["duracao_min"] == 168

    def test_fim_vem_de_duration_min(self):
        a = normalizar_apontamento(_doc("09:11:00", "11:59:00", 168))
        assert a["fim"] == datetime(2026, 6, 22, 11, 59)  # 09:11 + 168 min

    def test_fim_real_hora_e_ignorado(self):
        # O teste que fixa a decisão: fim_real_hora contradiz duration_min de
        # propósito, e quem manda é duration_min.
        a = normalizar_apontamento(_doc("09:11:00", "23:00:00", 168))
        assert a["fim"] == datetime(2026, 6, 22, 11, 59)

    def test_sem_fim_real_hora_nao_faz_diferenca(self):
        a = normalizar_apontamento(_doc("09:11:00", None, 168))
        assert a["fim"] == datetime(2026, 6, 22, 11, 59)

    def test_cruzando_meia_noite_o_fim_passa_do_dia(self):
        # Agora por aritmética, não pelo ramo `fim < inicio`
        a = normalizar_apontamento(_doc("23:30:00", None, 75))
        assert a["inicio"] == datetime(2026, 6, 22, 23, 30)
        assert a["fim"] == datetime(2026, 6, 23, 0, 45)

    def test_expoe_o_dia_do_apontamento(self):
        # `dia` é a chave de agrupamento — vem de inicio_execucao, não da hora
        a = normalizar_apontamento(_doc("23:30:00", None, 75))
        assert a["dia"] == date(2026, 6, 22)

    def test_sem_duration_min_e_descartado(self):
        assert normalizar_apontamento(_doc("09:11:00", "11:59:00", None)) is None

    def test_duration_min_nao_numerico_e_descartado(self):
        # Com duration_min sendo fonte única, um valor sujo derrubaria o render
        # inteiro se não fosse descartado aqui.
        assert normalizar_apontamento(_doc("09:11:00", "11:59:00", "abc")) is None

    def test_duration_min_negativo_e_descartado(self):
        assert normalizar_apontamento(_doc("09:11:00", "11:59:00", -5)) is None

    def test_sem_hora_inicio_e_descartado(self):
        assert normalizar_apontamento(_doc(None, "11:59:00", 168)) is None

    def test_hora_malformada_e_descartada(self):
        assert normalizar_apontamento(_doc("99:99:99", "11:59:00", 168)) is None

    def test_duracao_zero_e_aceita(self):
        # Caso especial: duração igual a zero
        a = normalizar_apontamento(_doc("09:11:00", "09:11:00", 0))
        assert a["duracao_min"] == 0


class TestAgruparEventoReal:
    """O evento de referência: 4 apontamentos → 1 evento de 732 min."""

    def test_os_quatro_apontamentos_viram_um_unico_evento(self):
        eventos = agrupar_eventos(_evento_real())
        assert len(eventos) == 1

    def test_duracao_e_a_soma_dos_apontamentos_nao_o_intervalo(self):
        # 09:11→23:59 seriam 888 min de intervalo; a avaria durou 732.
        # A diferença é refeição (102N) e DDS (105), que não são avaria.
        ev = agrupar_eventos(_evento_real())[0]
        assert ev["duracao_min"] == 732

    def test_inicio_e_fim_do_evento(self):
        ev = agrupar_eventos(_evento_real())[0]
        assert ev["inicio"] == datetime(2026, 6, 22, 9, 11)
        assert ev["fim"] == datetime(2026, 6, 22, 23, 59)

    def test_agrega_as_duas_ordens_sap(self):
        ev = agrupar_eventos(_evento_real())[0]
        assert ev["ordens"] == [10514832, 10524790]

    def test_conta_os_apontamentos(self):
        assert agrupar_eventos(_evento_real())[0]["n_apontamentos"] == 4

    def test_rotulo_vem_do_relato_do_operador(self):
        assert agrupar_eventos(_evento_real())[0]["rotulo"] == TXT_QUEBRA

    def test_chave_deriva_do_grupo_nao_do_primeiro_apontamento(self):
        ev = agrupar_eventos(_evento_real())[0]
        assert ev["chave"] == montar_chave("LONGI002", date(2026, 6, 1), "201", TXT_QUEBRA)
        assert ev["chave"].startswith("LONGI002_202606_201_")

    def test_expoe_o_mes_do_evento(self):
        ev = agrupar_eventos(_evento_real())[0]
        assert ev["mes"] == date(2026, 6, 1)       # 1º dia do mês (carimbo mensal)
        assert ev["n_dias"] == 1                    # os 4 apontamentos são do mesmo dia
        assert [d["dia"] for d in ev["por_dia"]] == [date(2026, 6, 22)]

    def test_apontamentos_ficam_disponiveis_no_evento(self):
        ev = agrupar_eventos(_evento_real())[0]
        assert len(ev["apontamentos"]) == 4
        assert ev["apontamentos"][0]["inicio"] == datetime(2026, 6, 22, 9, 11)


class TestSeparacaoDeEventos:
    """O que NÃO deve ser colado."""

    def test_texto_diferente_no_mesmo_dia_e_outro_evento(self):
        # Real: às 05:00 houve outro 201 na LONGI002, com relato distinto
        docs = _evento_real() + [
            _doc("05:00:00", "05:15:00", 15, texto="Falha no recuo da arvore porta ferrament",
                 ordem=10513795)
        ]
        eventos = agrupar_eventos(docs)
        assert len(eventos) == 2
        assert {e["duracao_min"] for e in eventos} == {732, 15}

    def test_equipamentos_diferentes_nao_se_misturam(self):
        docs = _evento_real() + [_doc("09:11:00", "11:59:00", 168, equip="LONGI001")]
        assert len(agrupar_eventos(docs)) == 2

    def test_causas_diferentes_nao_se_misturam(self):
        docs = [_doc("09:11:00", "11:59:00", 168, causa="201"),
                _doc("12:00:00", "12:30:00", 30, causa="S201")]
        assert len(agrupar_eventos(docs)) == 2

    def test_apontamentos_distantes_no_mesmo_dia_agrupam(self):
        # Sem heurística de intervalo: o relato é que identifica a falha. 22 h
        # separando os dois não importa — mesmo dia, mesmo relato, mesma falha.
        docs = [_doc("00:10:00", "00:20:00", 10), _doc("23:00:00", "23:30:00", 30)]
        assert len(agrupar_eventos(docs)) == 1

    def test_apontamentos_do_mesmo_dia_agrupam(self):
        # 62 min de refeição entre os dois — mesmo evento
        docs = [_doc("09:11:00", "11:59:00", 168), _doc("13:01:00", "14:59:00", 118)]
        assert len(agrupar_eventos(docs)) == 1

    def test_mesmo_relato_em_dias_distintos_do_mesmo_mes_cola(self):
        # MENSAL (BR-AF2-02): a mesma falha em dias diferentes do mês é UMA parada.
        docs = [_doc("09:11:00", "11:59:00", 168, dia=22),
                _doc("09:11:00", "11:59:00", 168, dia=28)]
        eventos = agrupar_eventos(docs)
        assert len(eventos) == 1
        assert eventos[0]["duracao_min"] == 336      # soma do mês
        assert eventos[0]["n_dias"] == 2

    def test_mesmo_relato_em_meses_distintos_nao_cola(self):
        # Reincidiu no mês seguinte → nova parada (nova análise).
        docs = [_doc("09:11:00", "11:59:00", 168, dia=22, mes=6),
                _doc("09:11:00", "11:59:00", 168, dia=3, mes=7)]
        assert len(agrupar_eventos(docs)) == 2

    def test_falha_que_cruza_a_meia_noite_no_mesmo_mes_cola(self):
        # Antes o corte por dia partia em dois; no mensal fica UMA parada (mesmo mês).
        docs = [_doc("23:30:00", None, 40, dia=22), _doc("00:10:00", None, 40, dia=23)]
        eventos = agrupar_eventos(docs)
        assert len(eventos) == 1
        assert eventos[0]["n_dias"] == 2

    def test_soma_mensal_dispara_gatilho_que_o_dia_perdia(self):
        # 20 min × vários dias: nenhum dia passa de 30, mas o mês soma bem mais.
        docs = [_doc("09:00:00", None, 20, dia=d) for d in (1, 5, 10, 15)]
        ev = agrupar_eventos(docs)[0]
        assert ev["duracao_min"] == 80 and ev["n_dias"] == 4  # 20×4, um único evento

    def test_texto_normalizado_ignora_caixa_e_acento(self):
        docs = [_doc("09:11:00", "11:59:00", 168, texto="Quebra Motor"),
                _doc("13:01:00", "14:59:00", 118, texto="quebra  motór")]
        assert len(agrupar_eventos(docs)) == 1

    def test_sem_texto_agrupa_por_contiguidade_e_causa(self):
        docs = [_doc("09:11:00", "11:59:00", 168, texto=None),
                _doc("13:01:00", "14:59:00", 118, texto=None)]
        assert len(agrupar_eventos(docs)) == 1


class TestOrdenacaoEBordas:
    def test_eventos_saem_do_mais_recente_para_o_mais_antigo(self):
        docs = [_doc("09:11:00", "09:30:00", 19, dia=22, texto="a"),
                _doc("09:11:00", "09:30:00", 19, dia=25, texto="b"),
                _doc("09:11:00", "09:30:00", 19, dia=23, texto="c")]
        eventos = agrupar_eventos(docs)
        assert [e["inicio"].day for e in eventos] == [25, 23, 22]

    def test_lista_vazia(self):
        assert agrupar_eventos([]) == []

    def test_docs_invalidos_sao_ignorados_sem_quebrar(self):
        docs = _evento_real() + [{"centro_de_trabalho": "LONGI002"}, {}]
        assert len(agrupar_eventos(docs)) == 1

    def test_doc_sem_equipamento_e_ignorado(self):
        assert agrupar_eventos([_doc("09:11:00", "09:30:00", 19, equip=None)]) == []


class TestChave:
    """A chave é a identidade do evento — ZPP_Paradas não expõe _id."""

    def test_formato(self):
        chave = montar_chave("LONGI002", date(2026, 6, 22), "201", "quebra motor")
        assert chave.startswith("LONGI002_202606_201_")   # carimbo mensal YYYYMM
        assert len(chave.rsplit("_", 1)[1]) == 8  # hash sha1 truncado

    def test_parse_devolve_as_quatro_partes(self):
        chave = montar_chave("LONGI002", date(2026, 6, 22), "201", "quebra motor")
        equip, mes, causa, h = parse_chave(chave)
        assert (equip, mes, causa) == ("LONGI002", date(2026, 6, 1), "201")  # 1º do mês
        assert len(h) == 8  # o hash não é reversível — só reencontra o grupo

    def test_causa_com_letra(self):
        chave = montar_chave("SOLDA001", date(2026, 6, 22), "S201", "falha")
        assert parse_chave(chave)[:3] == ("SOLDA001", date(2026, 6, 1), "S201")

    def test_aceita_datetime_alem_de_date(self):
        a = montar_chave("LONGI002", date(2026, 6, 22), "201", "x")
        b = montar_chave("LONGI002", datetime(2026, 6, 22, 9, 11), "201", "x")
        assert a == b  # a hora não entra na chave

    def test_relatos_distintos_no_mesmo_dia_geram_chaves_distintas(self):
        # O bug que motivou o formato: sem o relato, LONGI002+23/02+201 tinha 3
        # falhas distintas colidindo numa única análise.
        a = montar_chave("LONGI002", date(2026, 2, 23), "201", "manometro rolo desbar")
        b = montar_chave("LONGI002", date(2026, 2, 23), "201", "falha sensor sep de banda")
        c = montar_chave("LONGI002", date(2026, 2, 23), "201", "falha marcador penetracao")
        assert len({a, b, c}) == 3

    def test_relato_com_caixa_e_acento_diferentes_da_a_mesma_chave(self):
        docs = [_doc("09:11:00", None, 168, texto="Quebra Motór"),
                _doc("13:01:00", None, 118, texto="quebra  motor")]
        assert len(agrupar_eventos(docs)) == 1

    def test_relato_vazio_gera_chave_estavel(self):
        a = montar_chave("LONGI002", date(2026, 6, 22), "201", "")
        b = montar_chave("LONGI002", date(2026, 6, 22), "201", "")
        assert a == b

    def test_chave_e_deterministica(self):
        a = agrupar_eventos(_evento_real())[0]["chave"]
        b = agrupar_eventos(list(reversed(_evento_real())))[0]["chave"]
        assert a == b

    def test_apontamento_mais_cedo_nao_muda_a_chave(self):
        # A chave antiga vinha do início do primeiro apontamento: uma importação
        # tardia do SAP trazendo um apontamento anterior mudava a chave e órfãava
        # a análise já salva. Chavear por dia elimina esse modo de falha.
        antes = agrupar_eventos(_evento_real())[0]["chave"]
        depois = agrupar_eventos(_evento_real() + [_doc("06:00:00", None, 20)])[0]["chave"]
        assert antes == depois

    def test_chaves_malformadas_retornam_none(self):
        ruins = [
            "", None, "lixo", "A_B",
            "A_naoehdata_201_abc123",
            "A_20260622_201",              # formato antigo: 3 partes
            "LONGI002_202606220911_201",   # formato antigo: carimbo de 12 dígitos
            "A_20260622_201_abc_extra",    # partes demais
        ]
        for r in ruins:
            assert parse_chave(r) is None, r


class TestGatilho:
    """Só paradas que atingem o gatilho do equipamento entram na aba (BR-AF2-06).

    Gatilhos passados prontos (`gatilhos=...`) mantêm o teste puro — o cadastro
    real vem de `breakdown_thresholds`, que fala com o Mongo.
    """

    GAT = {"LCL-4,5": 60, "PRENSA-01": 90, "LWB": 120}

    def _ev(self, duracao, equip="LONGI002"):
        return {"equipamento": equip, "duracao_min": duracao}

    def test_acima_do_gatilho_passa(self):
        assert evento_atinge_gatilho(self._ev(61), self.GAT) is True

    def test_abaixo_do_gatilho_nao_passa(self):
        assert evento_atinge_gatilho(self._ev(59), self.GAT) is False

    def test_exatamente_no_gatilho_passa(self):
        # A fronteira do `>=` — a única semântica documentada (envio_email/03-spec.md)
        assert evento_atinge_gatilho(self._ev(60), self.GAT) is True

    def test_traduz_codigo_para_nome_amigavel(self):
        # O cadastro é chaveado por "LCL-4,5"; ZPP_Paradas traz "LONGI002"
        assert evento_atinge_gatilho(self._ev(60, "LONGI002"), self.GAT) is True
        assert evento_atinge_gatilho(self._ev(60, "SOLDA001"), self.GAT) is False  # LWB=120

    def test_equipamento_sem_cadastro_cai_no_default(self):
        from src.utils.breakdown_thresholds import DEFAULT_THRESHOLD_MIN
        assert evento_atinge_gatilho(self._ev(DEFAULT_THRESHOLD_MIN, "PRENS002"), {}) is True
        assert evento_atinge_gatilho(self._ev(DEFAULT_THRESHOLD_MIN - 1, "PRENS002"), {}) is False

    def test_equipamento_desconhecido_cai_no_default_sem_quebrar(self):
        from src.utils.breakdown_thresholds import DEFAULT_THRESHOLD_MIN
        assert carregar_gatilho("EQUIP_INEXISTENTE", self.GAT) == DEFAULT_THRESHOLD_MIN

    def test_duracao_invalida_nao_passa(self):
        assert evento_atinge_gatilho({"equipamento": "LONGI002", "duracao_min": "abc"},
                                     self.GAT) is False

    def test_evento_do_a3_passa(self):
        # 732 min na LCL-4,5 (gatilho 60) — o caso que motivou a feature
        ev = agrupar_eventos(_evento_real())[0]
        assert evento_atinge_gatilho(ev, self.GAT) is True

    def test_gatilho_vale_sobre_o_agregado_nao_sobre_o_apontamento(self):
        # 2 apontamentos de 40 min na LCL-4,5: nenhum passa sozinho (40 < 60),
        # mas o evento soma 80 e passa.
        docs = [_doc("09:00:00", None, 40), _doc("14:00:00", None, 40)]
        ev = agrupar_eventos(docs)[0]
        assert ev["duracao_min"] == 80
        assert evento_atinge_gatilho(ev, self.GAT) is True


class TestExibirTodasAsParadas:
    """O filtro persiste em `local`; ausente tem que significar o padrão."""

    def test_sem_filtros_e_o_padrao(self):
        assert exibir_todas_as_paradas(None) is False
        assert exibir_todas_as_paradas({}) is False

    def test_chave_ausente_e_o_padrao(self):
        # O caso real: store-af-filters já gravado no navegador, sem a chave nova
        assert exibir_todas_as_paradas({"year": 2026, "codes": ["201"]}) is False

    def test_todas(self):
        assert exibir_todas_as_paradas({"gatilho": "todas"}) is True

    def test_acima(self):
        assert exibir_todas_as_paradas({"gatilho": "acima"}) is False

    def test_valor_invalido_cai_no_padrao(self):
        assert exibir_todas_as_paradas({"gatilho": "lixo"}) is False
        assert exibir_todas_as_paradas({"gatilho": None}) is False


class TestFaixaDuracao:
    """Filtro de faixa de duração — limites fechados à direita."""

    def test_tres_faixas_disponiveis(self):
        assert [f["value"] for f in FAIXAS_DURACAO] == [FAIXA_ATE_25, FAIXA_25_A_60, FAIXA_ACIMA_60]

    def test_ate_25_minutos(self):
        assert faixa_duracao(1) == FAIXA_ATE_25
        assert faixa_duracao(15) == FAIXA_ATE_25
        assert faixa_duracao(25) == FAIXA_ATE_25  # 25 é o limite fechado

    def test_entre_25_e_60(self):
        assert faixa_duracao(25.5) == FAIXA_25_A_60
        assert faixa_duracao(26) == FAIXA_25_A_60
        assert faixa_duracao(60) == FAIXA_25_A_60  # 60 é o limite fechado

    def test_fronteira_dos_25_minutos(self):
        # A fronteira que mudou de 15 para 25 — um setup de 20 min agora é curto
        assert faixa_duracao(20) == FAIXA_ATE_25
        assert faixa_duracao(24.9) == FAIXA_ATE_25
        assert faixa_duracao(25) == FAIXA_ATE_25
        assert faixa_duracao(25.1) == FAIXA_25_A_60

    def test_acima_de_60(self):
        assert faixa_duracao(61) == FAIXA_ACIMA_60
        assert faixa_duracao(732) == FAIXA_ACIMA_60  # o evento da cisalha

    def test_zero_cai_na_primeira_faixa(self):
        assert faixa_duracao(0) == FAIXA_ATE_25

    def test_valores_invalidos(self):
        for v in (None, "abc", [], {}):
            assert faixa_duracao(v) is None


class TestFaixasAtivas:
    """Vazio = todas, seguindo a convenção do filtro de códigos da mesma página."""

    def test_vazio_significa_todas(self):
        assert faixas_ativas([]) == [FAIXA_ATE_25, FAIXA_25_A_60, FAIXA_ACIMA_60]
        assert faixas_ativas(None) == [FAIXA_ATE_25, FAIXA_25_A_60, FAIXA_ACIMA_60]

    def test_selecao_de_uma_faixa(self):
        assert faixas_ativas([FAIXA_ATE_25]) == [FAIXA_ATE_25]

    def test_selecao_de_duas_faixas(self):
        assert faixas_ativas([FAIXA_ATE_25, FAIXA_ACIMA_60]) == [FAIXA_ATE_25, FAIXA_ACIMA_60]

    def test_valores_desconhecidos_sao_descartados(self):
        assert faixas_ativas([FAIXA_ATE_25, "lixo"]) == [FAIXA_ATE_25]

    def test_so_lixo_cai_para_todas(self):
        assert len(faixas_ativas(["lixo"])) == 3


class TestDuracaoNaFaixa:
    def test_sem_restricao_aceita_tudo(self):
        for v in (0, 15, 60, 732, None):
            assert duracao_na_faixa(v, []) is True

    def test_somente_ate_25(self):
        assert duracao_na_faixa(10, [FAIXA_ATE_25]) is True
        assert duracao_na_faixa(25, [FAIXA_ATE_25]) is True
        assert duracao_na_faixa(30, [FAIXA_ATE_25]) is False
        assert duracao_na_faixa(732, [FAIXA_ATE_25]) is False

    def test_somente_a_faixa_do_meio(self):
        assert duracao_na_faixa(25, [FAIXA_25_A_60]) is False
        assert duracao_na_faixa(40, [FAIXA_25_A_60]) is True
        assert duracao_na_faixa(60, [FAIXA_25_A_60]) is True
        assert duracao_na_faixa(61, [FAIXA_25_A_60]) is False

    def test_somente_acima_60(self):
        assert duracao_na_faixa(732, [FAIXA_ACIMA_60]) is True
        assert duracao_na_faixa(60, [FAIXA_ACIMA_60]) is False

    def test_duas_faixas(self):
        sel = [FAIXA_ATE_25, FAIXA_ACIMA_60]
        assert duracao_na_faixa(10, sel) is True
        assert duracao_na_faixa(30, sel) is False   # a faixa do meio ficou de fora
        assert duracao_na_faixa(100, sel) is True

    def test_duracao_invalida_com_filtro_ativo_e_descartada(self):
        assert duracao_na_faixa(None, [FAIXA_ATE_25]) is False

    def test_evento_real_da_cisalha_com_filtro_de_avarias_longas(self):
        ev = agrupar_eventos(_evento_real())[0]
        assert duracao_na_faixa(ev["duracao_min"], [FAIXA_ACIMA_60]) is True
        assert duracao_na_faixa(ev["duracao_min"], [FAIXA_ATE_25]) is False


class TestAnosDisponiveis:
    """O ano do filtro é derivado da data, não de uma lista fixa que envelhece."""

    def test_janela_de_tres_anos_terminando_no_atual(self):
        assert anos_disponiveis(datetime(2026, 7, 15)) == [2024, 2025, 2026]

    def test_ano_padrao_e_sempre_o_mais_recente(self):
        assert ano_padrao(datetime(2026, 7, 15)) == 2026

    def test_vira_o_ano_sozinho(self):
        # O bug da lista hardcoded: em 1º/jan o ano novo tem que aparecer
        assert anos_disponiveis(datetime(2027, 1, 1)) == [2025, 2026, 2027]
        assert ano_padrao(datetime(2027, 1, 1)) == 2027

    def test_padrao_e_sempre_o_ultimo_da_lista(self):
        for ano in (2024, 2026, 2030):
            hoje = datetime(ano, 6, 1)
            assert ano_padrao(hoje) == anos_disponiveis(hoje)[-1]

    def test_janela_configuravel(self):
        assert anos_disponiveis(datetime(2026, 7, 15), janela=5) == [2022, 2023, 2024, 2025, 2026]


class TestAnoValido:
    """Filtro persistido em `local` pode trazer ano que já saiu das opções."""

    HOJE = datetime(2026, 7, 15)  # opções: [2024, 2025, 2026]

    def test_ano_da_lista_e_mantido(self):
        for a in (2024, 2025, 2026):
            assert ano_valido(a, self.HOJE) == a

    def test_ano_antigo_cai_para_o_mais_recente(self):
        assert ano_valido(2019, self.HOJE) == 2026

    def test_ano_futuro_cai_para_o_mais_recente(self):
        assert ano_valido(2030, self.HOJE) == 2026

    def test_ano_que_saiu_da_lista_na_virada(self):
        # 2024 era válido em 2026; em 2027 as opções viram [2025, 2026, 2027]
        assert ano_valido(2024, datetime(2026, 12, 31)) == 2024
        assert ano_valido(2024, datetime(2027, 1, 1)) == 2027

    def test_string_numerica_e_aceita(self):
        assert ano_valido("2025", self.HOJE) == 2025

    def test_lixo_e_vazio_caem_para_o_padrao(self):
        for v in (None, "", "abc", [], {}):
            assert ano_valido(v, self.HOJE) == 2026


class TestTituloSugerido:
    """Caso 4 — a primeira causa é pré-preenchida com o relato da parada."""

    def test_usa_o_relato_do_operador_quando_existe(self):
        ev = agrupar_eventos(_evento_real())[0]
        assert titulo_sugerido(ev) == TXT_QUEBRA

    def test_cai_para_a_descricao_sap_sem_relato(self):
        docs = [_doc("09:11:00", "11:59:00", 168, texto=None)]
        ev = agrupar_eventos(docs)[0]
        assert titulo_sugerido(ev) == "Paradas por quebra/falhas."

    def test_sem_causa_informada_usa_o_equipamento(self):
        docs = [_doc("09:11:00", "11:59:00", 168, texto=None, descricao=None)]
        ev = agrupar_eventos(docs)[0]
        assert titulo_sugerido(ev) == "Análise de falha — LCL-4,5"

    def test_titulo_longo_e_truncado(self):
        docs = [_doc("09:11:00", "11:59:00", 168, texto="x" * 300)]
        assert len(titulo_sugerido(agrupar_eventos(docs)[0])) == 120
