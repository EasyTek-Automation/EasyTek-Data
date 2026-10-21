"""
Testes de src/utils/failure_analysis_db.py — persistência da Análise de Falhas.

Cobre os casos obrigatórios 2 (abrir parada sem análise), 3 (nó raiz automático),
4 (primeira causa preenchida), 5 (reabrir sem duplicar), 15 (persistir e
recarregar) e 18 (editar análise concluída).

Segue a convenção de webapp/tests/workflow/test_workflow_db.py: MagicMock +
patch de `get_mongo_connection` no módulo sob teste, sem mongomock.

NOTA: requer pymongo instalado (o módulo importa `get_mongo_connection` no topo,
como workflow_db.py). Rodar com o stack: `cd webapp && pytest tests/maintenance/`.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from src.utils.failure_tree import MODO_MANUAL, TIPO_ETAPA, TIPO_RAIZ, criar_no

MODULO = "src.utils.failure_analysis_db"

# ObjectId válido usado como analysis_id nos testes. Precisa ser um hex de 24
# chars porque `salvar_arvore`/`concluir_analise` fazem `ObjectId(analysis_id)`;
# e os nós da árvore precisam carregar ESTE mesmo id, senão a validação de posse
# (`validar_arvore`) rejeita com "não pertence a esta análise".
OID = "507f1f77bcf86cd799439011"


def _evento(duracao=732):
    """Evento de falha equivalente ao da quebra do motor da cisalha (22/06/2026)."""
    return {
        "chave": "LONGI002_202606220911_201",
        "equipamento": "LONGI002",
        "causa": "201",
        "rotulo": "quebra motor cisalaha 5019483",
        "inicio": datetime(2026, 6, 22, 9, 11),
        "fim": datetime(2026, 6, 22, 23, 59),
        "duracao_min": duracao,
        "n_apontamentos": 4,
        "ordens": [10514832, 10524790],
    }


def _mock_col(find_one_result=None):
    col = MagicMock()
    col.find_one.return_value = find_one_result
    col.insert_one.return_value = MagicMock(inserted_id="fake_oid")
    col.update_one.return_value = MagicMock(matched_count=1, modified_count=1)
    return col


class TestEnsureIndexes:
    """Índices idempotentes criados no boot; o único em parada_chave é a trava."""

    def test_cria_tres_indices(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import ensure_indexes
            assert ensure_indexes() is True
        assert col.create_index.call_count == 3

    def test_parada_chave_e_unico(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import ensure_indexes
            ensure_indexes()
        args, kwargs = col.create_index.call_args_list[0]
        assert args[0] == "parada_chave"
        assert kwargs["unique"] is True

    def test_mongo_offline_retorna_false_sem_quebrar(self):
        with patch(f"{MODULO}.get_mongo_connection", return_value=None):
            from src.utils.failure_analysis_db import ensure_indexes
            assert ensure_indexes() is False


class TestObterOuCriarAnalise:
    """Casos 2, 3, 4 e 5."""

    def test_cria_analise_quando_nao_existe(self):
        col = _mock_col(find_one_result=None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, criada = obter_ou_criar_analise(_evento(), "marcio")
        assert criada is True
        assert analise["parada_chave"] == "LONGI002_202606220911_201"
        col.insert_one.assert_called_once()

    def test_analise_nasce_aberta_na_versao_1(self):
        col = _mock_col(find_one_result=None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise, STATUS_ABERTA
            analise, _ = obter_ou_criar_analise(_evento(), "marcio")
        assert analise["status"] == STATUS_ABERTA
        assert analise["versao"] == 1

    def test_titulo_inicial_vem_do_relato_do_operador(self):
        col = _mock_col(find_one_result=None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, _ = obter_ou_criar_analise(_evento(), "marcio")
        assert analise["titulo"] == "quebra motor cisalaha 5019483"

    def test_nome_nasce_vazio(self):
        # Nome é o rótulo livre do usuário — só ele preenche
        col = _mock_col(find_one_result=None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, _ = obter_ou_criar_analise(_evento(), "marcio")
        assert analise["nome"] == ""

    def test_snapshot_da_parada_preserva_duracao_e_ordens(self):
        # Caso especial: equipamento inativo/reprocessado — o nome histórico fica
        col = _mock_col(find_one_result=None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, _ = obter_ou_criar_analise(_evento(), "marcio")
        assert analise["parada"]["duracao_min"] == 732
        assert analise["parada"]["ordens"] == [10514832, 10524790]
        assert analise["parada"]["equipamento"] == "LONGI002"

    def test_cria_no_raiz_automaticamente(self):
        # Caso 3
        col = _mock_col(find_one_result=None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, _ = obter_ou_criar_analise(_evento(), "marcio")
        raizes = [n for n in analise["nos"] if n["tipo"] == TIPO_RAIZ]
        assert len(raizes) == 1
        assert raizes[0]["parent_id"] is None

    def test_texto_do_no_raiz_traz_equipamento_e_duracao(self):
        col = _mock_col(find_one_result=None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, _ = obter_ou_criar_analise(_evento(), "marcio")
        raiz = [n for n in analise["nos"] if n["tipo"] == TIPO_RAIZ][0]
        assert raiz["titulo"] == "Parada da LCL-4,5 por 12 h 12 min"

    def test_primeira_causa_preenchida_com_a_causa_da_parada(self):
        # Caso 4
        col = _mock_col(find_one_result=None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, _ = obter_ou_criar_analise(_evento(), "marcio")
        causas = [n for n in analise["nos"] if n["tipo"] == TIPO_ETAPA]
        assert len(causas) == 1
        assert causas[0]["titulo"] == "quebra motor cisalaha 5019483"
        assert causas[0]["parent_id"] == "raiz"

    def test_parada_sem_causa_cria_no_vazio(self):
        # Caso especial: parada sem causa → placeholder na UI
        ev = _evento()
        ev["rotulo"] = ""
        col = _mock_col(find_one_result=None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, _ = obter_ou_criar_analise(ev, "marcio")
        causas = [n for n in analise["nos"] if n["tipo"] == TIPO_ETAPA]
        assert causas[0]["titulo"] == ""

    def test_primeira_causa_recebe_toda_a_duracao(self):
        col = _mock_col(find_one_result=None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, _ = obter_ou_criar_analise(_evento(), "marcio")
        causa = [n for n in analise["nos"] if n["tipo"] == TIPO_ETAPA][0]
        assert causa["duration_min"] == 732

    def test_reabrir_nao_duplica_a_analise(self):
        # Caso 5 — o coração da idempotência
        existente = {
            "_id": "oid-1",
            "parada_chave": "LONGI002_202606220911_201",
            "titulo": "já existia",
            "versao": 7,
            "nos": [],
        }
        col = _mock_col(find_one_result=existente)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, criada = obter_ou_criar_analise(_evento(), "marcio")
        assert criada is False
        assert analise["titulo"] == "já existia"
        col.insert_one.assert_not_called()

    def test_reabrir_nao_recria_os_nos_iniciais(self):
        existente = {"_id": "oid-1", "parada_chave": "LONGI002_202606220911_201",
                     "versao": 7, "nos": [{"id": "x", "tipo": TIPO_RAIZ}]}
        col = _mock_col(find_one_result=existente)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, _ = obter_ou_criar_analise(_evento(), "marcio")
        assert analise["nos"] == [{"id": "x", "tipo": TIPO_RAIZ}]

    def test_corrida_de_insert_relê_o_vencedor_em_vez_de_estourar(self):
        # Dois cliques simultâneos: o índice único rejeita o segundo insert
        col = MagicMock()
        col.find_one.side_effect = [None, {"_id": "oid-1", "parada_chave": "k", "versao": 1}]
        col.insert_one.side_effect = Exception("E11000 duplicate key")
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            analise, criada = obter_ou_criar_analise(_evento(), "marcio")
        assert criada is False
        assert analise is not None

    def test_evento_sem_chave_e_rejeitado(self):
        with patch(f"{MODULO}.get_mongo_connection", return_value=_mock_col()):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            assert obter_ou_criar_analise({}, "marcio") == (None, False)

    def test_mongo_offline_degrada(self):
        with patch(f"{MODULO}.get_mongo_connection", return_value=None):
            from src.utils.failure_analysis_db import obter_ou_criar_analise
            assert obter_ou_criar_analise(_evento(), "marcio") == (None, False)


class TestCarregarAnalise:
    """Caso 15 — recarregar traz o diagrama salvo."""

    def test_converte_object_id_em_id_string(self):
        col = _mock_col(find_one_result={"_id": "oid-1", "parada_chave": "k", "nos": []})
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import carregar_analise
            a = carregar_analise("k")
        assert a["id"] == "oid-1"
        assert "_id" not in a

    def test_inexistente_retorna_none(self):
        with patch(f"{MODULO}.get_mongo_connection", return_value=_mock_col(None)):
            from src.utils.failure_analysis_db import carregar_analise
            assert carregar_analise("nao-existe") is None

    def test_erro_de_banco_retorna_none(self):
        col = MagicMock()
        col.find_one.side_effect = Exception("Erro DB")
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import carregar_analise
            assert carregar_analise("k") is None


class TestSalvarArvore:
    """Caso 15 e 18 — escrita atômica, validada no backend, com trava de versão."""

    def _nos(self):
        return [
            criar_no(OID, None, "Parada", tipo=TIPO_RAIZ, no_id="raiz"),
            criar_no(OID, "raiz", "Etapa", tipo=TIPO_ETAPA, no_id="c0"),
        ]

    def test_salva_e_incrementa_a_versao(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import salvar_arvore
            ok, _ = salvar_arvore("507f1f77bcf86cd799439011", 3, self._nos(), 732, "marcio")
        assert ok is True
        _, update = col.update_one.call_args[0]
        assert update["$inc"] == {"versao": 1}

    def test_a_escrita_e_condicionada_a_versao_e_ao_status_aberta(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import salvar_arvore, STATUS_ABERTA
            salvar_arvore("507f1f77bcf86cd799439011", 3, self._nos(), 732, "marcio")
        filtro, _ = col.update_one.call_args[0]
        assert filtro["versao"] == 3
        assert filtro["status"] == STATUS_ABERTA

    def test_tempos_sao_redistribuidos_no_backend(self):
        # O cliente não é fonte de verdade do rateio
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import salvar_arvore
            salvar_arvore("507f1f77bcf86cd799439011", 1, self._nos(), 732, "marcio")
        _, update = col.update_one.call_args[0]
        causa = [n for n in update["$set"]["nos"] if n["tipo"] == TIPO_ETAPA][0]
        assert causa["duration_min"] == 732

    def test_arvore_com_ciclo_e_rejeitada_antes_de_escrever(self):
        # Caso 9 no nível do backend
        nos = self._nos()
        nos.append(criar_no(OID, "c1", "x", no_id="c1"))
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import salvar_arvore
            ok, msg = salvar_arvore(OID, 1, nos, 732, "marcio")
        assert ok is False
        col.update_one.assert_not_called()

    def test_no_de_outra_analise_e_rejeitado(self):
        nos = self._nos()
        nos[1]["analysis_id"] = "OUTRA"
        with patch(f"{MODULO}.get_mongo_connection", return_value=_mock_col()):
            from src.utils.failure_analysis_db import salvar_arvore
            ok, msg = salvar_arvore(OID, 1, nos, 732, "marcio")
        assert ok is False
        assert "não pertence" in msg

    def test_versao_defasada_gera_conflito(self):
        # Caso especial: concorrência entre dois usuários
        col = _mock_col()
        col.update_one.return_value = MagicMock(matched_count=0, modified_count=0)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import salvar_arvore
            ok, msg = salvar_arvore("507f1f77bcf86cd799439011", 1, self._nos(), 732, "marcio")
        assert ok is False
        assert "outro usuário" in msg

    def test_analise_concluida_nao_aceita_escrita(self):
        # Caso 18 — o filtro exige status aberta, então matched_count = 0
        col = _mock_col()
        col.update_one.return_value = MagicMock(matched_count=0)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import salvar_arvore
            ok, _ = salvar_arvore("507f1f77bcf86cd799439011", 1, self._nos(), 732, "marcio")
        assert ok is False

    def test_mongo_offline(self):
        # Caso especial: falha de rede durante salvamento
        with patch(f"{MODULO}.get_mongo_connection", return_value=None):
            from src.utils.failure_analysis_db import salvar_arvore
            ok, msg = salvar_arvore("A1", 1, self._nos(), 732, "marcio")
        assert ok is False
        assert "indisponível" in msg


class TestAtualizarCampos:
    def test_campo_fora_da_whitelist_e_ignorado(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import atualizar_campos
            atualizar_campos("507f1f77bcf86cd799439011", 1,
                             {"nome": "Quebra da cisalha", "status": "concluida",
                              "versao": 999}, "marcio")
        _, update = col.update_one.call_args[0]
        assert update["$set"]["nome"] == "Quebra da cisalha"
        assert "status" not in update["$set"]  # não se muda status por aqui
        assert "versao" not in update["$set"]

    def test_titulo_e_imutavel(self):
        # Mesmo que alguém mande `titulo`, a whitelist descarta
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import atualizar_campos
            atualizar_campos("507f1f77bcf86cd799439011", 1,
                             {"nome": "meu nome", "titulo": "tentativa de troca"}, "marcio")
        _, update = col.update_one.call_args[0]
        assert "titulo" not in update["$set"]

    def test_apenas_titulo_nao_escreve_nada(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import atualizar_campos
            ok, _ = atualizar_campos("507f1f77bcf86cd799439011", 1,
                                     {"titulo": "tentativa"}, "marcio")
        assert ok is False
        col.update_one.assert_not_called()

    def test_nome_pode_ser_limpo(self):
        # Apagar o nome é uma edição legítima — volta a exibir o título fixo
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import atualizar_campos
            atualizar_campos("507f1f77bcf86cd799439011", 1, {"nome": ""}, "marcio")
        _, update = col.update_one.call_args[0]
        assert update["$set"]["nome"] == ""

    def test_apenas_campos_invalidos_nao_escreve(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import atualizar_campos
            ok, _ = atualizar_campos("A1", 1, {"hack": 1}, "marcio")
        assert ok is False
        col.update_one.assert_not_called()

    def test_campo_ausente_nao_e_apagado(self):
        # Editar só um campo (nome) não inclui os demais no $set — logo não os apaga.
        # (titulo não serve de cobaia: está fora da whitelist e não escreve nada.)
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import atualizar_campos
            atualizar_campos(OID, 1, {"nome": "só o nome"}, "marcio")
        _, update = col.update_one.call_args[0]
        assert "participantes" not in update["$set"]

    def test_registra_auditoria(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import atualizar_campos
            atualizar_campos(OID, 1, {"nome": "x"}, "marcio")
        _, update = col.update_one.call_args[0]
        assert update["$set"]["atualizado_por"] == "marcio"
        assert isinstance(update["$set"]["atualizado_em"], datetime)


class TestConcluirEReabrir:
    """Caso 14/18 — divergência de tempo impede concluir; concluída fica read-only."""

    def _nos_ok(self):
        nos = [
            criar_no(OID, None, "Parada", tipo=TIPO_RAIZ, no_id="raiz"),
            criar_no(OID, "raiz", "Etapa", tipo=TIPO_ETAPA, no_id="c0"),
        ]
        # Concluir exige ≥1 causa raiz marcada (★) — `pode_concluir`. Sem isso a
        # conclusão é (corretamente) recusada, então o cenário "tempos fecham" nem
        # chegaria ao update. Marca a etapa como causa raiz.
        nos[1]["is_root_cause"] = True
        return nos

    def _acoes_ok(self):
        """Plano completo: causa raiz tratada, com responsável e prazo (BR-14)."""
        return [{"id": "a1", "node_id": "c0", "descricao": "trocar o rolamento",
                 "responsavel": ["João"], "prazo": "2026-09-30", "status": 1}]

    def test_entrega_quando_os_tempos_fecham_e_o_plano_esta_completo(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import entregar_analise, STATUS_CONCLUIDA
            ok, _ = entregar_analise("507f1f77bcf86cd799439011", 1, self._nos_ok(),
                                     self._acoes_ok(), 732, "marcio")
        assert ok is True
        _, update = col.update_one.call_args[0]
        assert update["$set"]["status"] == STATUS_CONCLUIDA
        assert update["$push"]["aceite.passagens"]["acao"] == "entregue"
        assert update["$push"]["aceite.passagens"]["por"] == "marcio"

    def test_entrega_nasce_sem_aceite(self):
        # Entregar não aceita: são duas pessoas dizendo duas coisas diferentes.
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import entregar_analise
            entregar_analise("507f1f77bcf86cd799439011", 1, self._nos_ok(),
                             self._acoes_ok(), 732, "marcio")
        _, update = col.update_one.call_args[0]
        assert update["$set"]["aceite.aceito_em"] is None

    def test_divergencia_de_tempo_impede_entregar(self):
        nos = self._nos_ok()
        nos[1].update(duration_mode=MODO_MANUAL, duration_min=100)
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import entregar_analise
            ok, msg = entregar_analise("507f1f77bcf86cd799439011", 1, nos,
                                       self._acoes_ok(), 732, "marcio")
        assert ok is False
        assert "Não é possível entregar" in msg
        col.update_one.assert_not_called()

    def test_causa_raiz_sem_acao_impede_entregar_e_diz_qual(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import entregar_analise
            ok, msg = entregar_analise("507f1f77bcf86cd799439011", 1, self._nos_ok(),
                                       [], 732, "marcio")
        assert ok is False and "sem ação escrita" in msg
        col.update_one.assert_not_called()

    def test_acao_sem_prazo_impede_entregar(self):
        acoes = [{**self._acoes_ok()[0], "prazo": None}]
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import entregar_analise
            ok, msg = entregar_analise("507f1f77bcf86cd799439011", 1, self._nos_ok(),
                                       acoes, 732, "marcio")
        assert ok is False and "sem prazo" in msg

    def test_o_estado_esperado_vai_no_filtro_da_atualizacao(self):
        # Dois cliques ao mesmo tempo não podem gerar duas entregas: o segundo não
        # encontra o documento no estado esperado.
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import entregar_analise, STATUS_ABERTA
            entregar_analise("507f1f77bcf86cd799439011", 1, self._nos_ok(),
                             self._acoes_ok(), 732, "marcio")
        filtro, _ = col.update_one.call_args[0]
        assert filtro["status"] == STATUS_ABERTA and filtro["versao"] == 1


class TestAceiteEDevolucao:
    """BR-15 — o gestor aceita ou devolve com motivo; devolver é o único destravar."""

    def test_aceitar_grava_quem_e_quando(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import aceitar_analise
            ok, _ = aceitar_analise("507f1f77bcf86cd799439011", "marinho")
        assert ok is True
        filtro, update = col.update_one.call_args[0]
        assert update["$set"]["aceite.aceito_por"] == "marinho"
        assert update["$set"]["aceite.aceito_em"] is not None
        # Só aceita o que está entregue e ainda não aceito.
        assert filtro["aceite.aceito_em"] is None

    def test_aceitar_o_que_nao_esta_entregue_falha(self):
        col = _mock_col()
        col.update_one.return_value = MagicMock(matched_count=0)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import aceitar_analise
            ok, msg = aceitar_analise("507f1f77bcf86cd799439011", "marinho")
        assert ok is False and "aguardando aceite" in msg

    def test_devolver_sem_motivo_e_recusado_antes_de_tocar_no_banco(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import devolver_analise
            ok, msg = devolver_analise("507f1f77bcf86cd799439011", "marinho", "   ")
        assert ok is False and "motivo" in msg.lower()
        col.update_one.assert_not_called()

    def test_devolver_destrava_e_guarda_o_motivo(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import devolver_analise, STATUS_ABERTA
            ok, _ = devolver_analise("507f1f77bcf86cd799439011", "marinho",
                                     "ação sem prazo")
        assert ok is True
        _, update = col.update_one.call_args[0]
        assert update["$set"]["status"] == STATUS_ABERTA
        assert update["$set"]["aceite.aceito_em"] is None
        assert update["$push"]["aceite.passagens"]["motivo"] == "ação sem prazo"

    def test_devolucao_empilha_no_historico(self):
        # `$push` e não `$set`: a terceira devolução não pode apagar as duas
        # primeiras (BR-15).
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import devolver_analise
            devolver_analise("507f1f77bcf86cd799439011", "marinho", "refazer")
        _, update = col.update_one.call_args[0]
        assert "aceite.passagens" in update["$push"]


class TestGarantirOpcaoAtual:
    """O responsável gravado nunca some do select — senão o próximo save o apaga."""

    def _opcoes(self):
        return [{"label": "marcio (Nível 2)", "value": "marcio"},
                {"label": "alex (Nível 1)", "value": "alex"}]

    def test_valor_presente_nao_altera_a_lista(self):
        from src.utils.failure_analysis_db import garantir_opcao_atual
        assert garantir_opcao_atual(self._opcoes(), "marcio") == self._opcoes()

    def test_valor_ausente_e_adicionado_como_inativo(self):
        from src.utils.failure_analysis_db import garantir_opcao_atual
        r = garantir_opcao_atual(self._opcoes(), "joao_demitido")
        assert r[0] == {"label": "joao_demitido (inativo)", "value": "joao_demitido"}
        assert len(r) == 3

    def test_valor_vazio_nao_adiciona_nada(self):
        from src.utils.failure_analysis_db import garantir_opcao_atual
        assert garantir_opcao_atual(self._opcoes(), None) == self._opcoes()
        assert garantir_opcao_atual(self._opcoes(), "") == self._opcoes()

    def test_lista_vazia_com_valor_historico(self):
        from src.utils.failure_analysis_db import garantir_opcao_atual
        assert garantir_opcao_atual([], "marcio") == [
            {"label": "marcio (inativo)", "value": "marcio"}]


class TestOpcoesResponsaveis:
    """Reusa a regra de atribuição do workflow: admin vê todos; demais, seu perfil."""

    def test_delega_para_o_helper_do_workflow(self):
        with patch("src.utils.workflow_db.get_usuarios_por_perfil") as mock:
            mock.return_value = [{"label": "marcio (Nível 2)", "value": "marcio"}]
            from src.utils.failure_analysis_db import opcoes_responsaveis
            r = opcoes_responsaveis("manutencao")
        mock.assert_called_once_with("manutencao")
        assert r == [{"label": "marcio (Nível 2)", "value": "marcio"}]

    def test_mantem_o_responsavel_atual_fora_do_perfil(self):
        with patch("src.utils.workflow_db.get_usuarios_por_perfil") as mock:
            mock.return_value = [{"label": "marcio (Nível 2)", "value": "marcio"}]
            from src.utils.failure_analysis_db import opcoes_responsaveis
            r = opcoes_responsaveis("manutencao", valor_atual="marinho")
        assert r[0]["value"] == "marinho"

    def test_erro_ao_listar_degrada_para_vazio(self):
        with patch("src.utils.workflow_db.get_usuarios_por_perfil",
                   side_effect=Exception("Erro DB")):
            from src.utils.failure_analysis_db import opcoes_responsaveis
            assert opcoes_responsaveis("manutencao") == []

    def test_erro_preserva_o_responsavel_atual(self):
        with patch("src.utils.workflow_db.get_usuarios_por_perfil",
                   side_effect=Exception("Erro DB")):
            from src.utils.failure_analysis_db import opcoes_responsaveis
            assert opcoes_responsaveis("manutencao", "marcio") == [
                {"label": "marcio (inativo)", "value": "marcio"}]


class TestChavesComAnalise:
    """A listagem marca as paradas já analisadas numa query só."""

    def test_mapeia_chave_para_status(self):
        col = MagicMock()
        col.find.return_value = [
            {"parada_chave": "k1", "status": "aberta"},
            {"parada_chave": "k2", "status": "concluida"},
        ]
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import chaves_com_analise
            assert chaves_com_analise(["k1", "k2", "k3"]) == {"k1": "aberta", "k2": "concluida"}

    def test_lista_vazia_nao_consulta(self):
        col = MagicMock()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import chaves_com_analise
            assert chaves_com_analise([]) == {}
        col.find.assert_not_called()

    def test_erro_de_banco_degrada_para_vazio(self):
        col = MagicMock()
        col.find.side_effect = Exception("Erro DB")
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import chaves_com_analise
            assert chaves_com_analise(["k1"]) == {}


class TestFotos:
    """Fotos da galeria — adicionar/remover/editar (BR-05/07/08)."""

    def _foto_meta(self):
        return {"arquivo": "a.jpg", "thumb": "a.jpg", "largura": 800, "altura": 600,
                "bytes": 12000, "mime": "image/jpeg"}

    def test_adicionar_em_analise_aberta(self):
        col = _mock_col({"status": "aberta", "fotos": []})
        col.update_one.return_value = MagicMock(modified_count=1)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import adicionar_foto
            ok, _, item = adicionar_foto(OID, self._foto_meta(), "marcio")
        assert ok is True
        assert item["enviada_por"] == "marcio" and item["id"]
        _, update = col.update_one.call_args[0]
        assert "$push" in update and update["$push"]["fotos"]["arquivo"] == "a.jpg"

    def test_adicionar_bloqueado_se_concluida(self):
        col = _mock_col({"status": "concluida", "fotos": []})
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import adicionar_foto
            ok, msg, _ = adicionar_foto(OID, self._foto_meta(), "marcio")
        assert ok is False
        col.update_one.assert_not_called()

    def test_adicionar_bloqueado_no_limite(self):
        col = _mock_col({"status": "aberta", "fotos": [{"id": str(i)} for i in range(30)]})
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import adicionar_foto
            ok, msg, _ = adicionar_foto(OID, self._foto_meta(), "marcio")
        assert ok is False and "Limite" in msg
        col.update_one.assert_not_called()

    def test_remover_pelo_autor(self):
        col = _mock_col({"status": "aberta",
                         "fotos": [{"id": "f1", "enviada_por": "marcio",
                                    "arquivo": "a.jpg", "thumb": "a.jpg"}]})
        col.update_one.return_value = MagicMock(modified_count=1)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import remover_foto
            ok, _, item = remover_foto(OID, "f1", "marcio", nivel=2)
        assert ok is True and item["arquivo"] == "a.jpg"

    def test_remover_negado_para_nao_autor_sem_nivel(self):
        col = _mock_col({"status": "aberta",
                         "fotos": [{"id": "f1", "enviada_por": "outro"}]})
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import remover_foto
            ok, msg, _ = remover_foto(OID, "f1", "marcio", nivel=2)
        assert ok is False
        col.update_one.assert_not_called()

    def test_remover_permitido_para_nivel_3(self):
        col = _mock_col({"status": "aberta",
                         "fotos": [{"id": "f1", "enviada_por": "outro",
                                    "arquivo": "a.jpg", "thumb": "a.jpg"}]})
        col.update_one.return_value = MagicMock(modified_count=1)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import remover_foto
            ok, _, _ = remover_foto(OID, "f1", "marcio", nivel=3)
        assert ok is True

    def test_editar_legenda(self):
        col = _mock_col()
        col.update_one.return_value = MagicMock(matched_count=1)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import editar_legenda_foto
            ok, _ = editar_legenda_foto(OID, "f1", "correia rompida", "marcio")
        assert ok is True
        _, update = col.update_one.call_args[0]
        assert update["$set"]["fotos.$.legenda"] == "correia rompida"

    def test_listar_fotos_vazio_sem_doc(self):
        col = _mock_col(None)
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import listar_fotos
            assert listar_fotos(OID) == []


class TestContarAnalisesDoMes:
    """Contagem que decide se o botão "Exportar slides do mês" fica ativo (S4)."""

    def test_conta_pelo_mes_da_chave(self):
        col = _mock_col()
        col.count_documents.return_value = 13
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import contar_analises_do_mes
            assert contar_analises_do_mes("202607") == 13
        filtro = col.count_documents.call_args[0][0]
        assert filtro == {"parada_chave": {"$regex": "_202607_"}}

    def test_mes_sem_analise_devolve_zero(self):
        col = _mock_col()
        col.count_documents.return_value = 0
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import contar_analises_do_mes
            assert contar_analises_do_mes("202602") == 0

    def test_mes_invalido_nao_consulta_o_banco(self):
        col = _mock_col()
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import contar_analises_do_mes
            assert contar_analises_do_mes("") == 0
            assert contar_analises_do_mes("julho") == 0
        col.count_documents.assert_not_called()

    def test_banco_fora_do_ar_devolve_zero(self):
        with patch(f"{MODULO}.get_mongo_connection", return_value=None):
            from src.utils.failure_analysis_db import contar_analises_do_mes
            assert contar_analises_do_mes("202607") == 0

    def test_falha_na_query_nao_propaga(self):
        col = _mock_col()
        col.count_documents.side_effect = RuntimeError("mongo caiu")
        with patch(f"{MODULO}.get_mongo_connection", return_value=col):
            from src.utils.failure_analysis_db import contar_analises_do_mes
            assert contar_analises_do_mes("202607") == 0
