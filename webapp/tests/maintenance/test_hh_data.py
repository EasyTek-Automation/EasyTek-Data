# -*- coding: utf-8 -*-
"""Testes da camada de dados do quadro semanal HH (B2) — helpers de semana e união/agregação.

Lógica pura, sem Mongo: monkeypatcha os carregadores de snapshot e o cruzamento com o
backlog. Cobre BR-09 (semana ISO Mon-first), BR-02/03 (união por operação, soma por ordem,
aderência por ordem — núcleo SP-04.5) e BR-07 (atribuível só se classificada).
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from src.utils import hh_data


# ---- semana (BR-09) ------------------------------------------------------------------

def test_iso_semana():
    assert hh_data.iso_semana(datetime(2026, 6, 30)) == "2026-W27"

def test_inicio_da_semana_eh_segunda():
    ini = hh_data.inicio_da_semana("2026-W27")
    assert ini.weekday() == 0          # segunda-feira
    assert ini == datetime(2026, 6, 29)

def test_semana_shift():
    assert hh_data.semana_shift("2026-W27", -1) == "2026-W26"
    assert hh_data.semana_shift("2026-W27", 1) == "2026-W28"

def test_datas_da_semana():
    dias = hh_data.datas_da_semana("2026-W27")
    assert len(dias) == 7
    assert dias[0] == datetime(2026, 6, 29)   # segunda
    assert dias[6] == datetime(2026, 7, 5)    # domingo

def test_semana_eh_futura():
    with patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 6, 30)):
        assert hh_data.semana_eh_futura("2026-W30") is True    # futura
        assert hh_data.semana_eh_futura("2026-W20") is False   # passada


# ---- união + agregação (BR-02/03, SP-04.5) -------------------------------------------

def _fake_snapshots():
    """Plan + real por operação para 2 ordens (uma com 2 operações)."""
    plan = {"docs": [
        {"ordem": "5018863", "operacao": "0010", "planejado_min": 120},
        {"ordem": "5018901", "operacao": "0010", "planejado_min": 300},
        {"ordem": "5018901", "operacao": "0020", "planejado_min": 180},   # 2ª op da mesma ordem
    ], "coleta_id": "p1", "coletado_em": datetime(2026, 6, 30, 4, 0)}
    real = {"docs": [
        {"ordem": "5018863", "operacao": "0010", "realizado_min": 110,
         "executores": ["CDAMASIO"], "status_sap": "LIB ENCE"},
        {"ordem": "5018901", "operacao": "0010", "realizado_min": 320,
         "executores": ["JSILVA"], "status_sap": "LIB"},
    ], "coleta_id": "r1", "coletado_em": datetime(2026, 6, 30, 4, 5)}
    return plan, real


def _fake_backlog_snap(ordens_list):
    """Snapshot cru do sap_backlog (universo da fila) como bd.carregar_snapshot devolveria."""
    return {"ordens": ordens_list, "coleta_id": "bl1", "coletado_em": None}


def _patch_backlog(bl_ordens):
    """Context manager tuple: injeta o backlog como universo, com enriquecimento identidade."""
    return (
        patch.object(hh_data.bd, "carregar_snapshot", return_value=_fake_backlog_snap(bl_ordens)),
        patch.object(hh_data.bd, "carregar_ativos", return_value={}),
        patch.object(hh_data.bd, "enriquecer_local", side_effect=lambda ordens, idx: ordens),
    )


def test_montar_ordens_agrega_e_calcula_aderencia():
    plan, real = _fake_snapshots()
    # universo agora vem do backlog (ordens abertas); IW37/IW47 só enriquecem por ordem
    bl = [
        {"ordem": "5018863", "descricao": "Ordem 5018863", "disciplina": "Eletrica",
         "categoria": "Corretiva", "data_criacao": None, "data_inicio": None, "local_instalacao": ""},
        {"ordem": "5018901", "descricao": "Ordem 5018901", "disciplina": "Mecanica",
         "categoria": "Corretiva", "data_criacao": None, "data_inicio": None, "local_instalacao": ""},
    ]
    def fake_load(coll, silent=True):
        return plan if coll == hh_data.COLL_PLAN else real
    p_snap, p_ativos, p_enr = _patch_backlog(bl)
    with patch.object(hh_data, "_carregar_snapshot", side_effect=fake_load), \
         p_snap, p_ativos, p_enr:
        res = hh_data.montar_ordens()
    ordens = res["ordens"]
    # ordem com 2 operações soma o planejado (300+180=480)
    assert ordens["5018901"]["planejado_min"] == 480
    assert ordens["5018901"]["realizado_min"] == 320
    # aderência por ordem (núcleo): 320/480
    assert abs(ordens["5018901"]["aderencia"] - 320/480) < 1e-9
    # ordem simples
    assert ordens["5018863"]["planejado_min"] == 120
    assert ordens["5018863"]["realizado_min"] == 110
    assert ordens["5018863"]["executores"] == ["CDAMASIO"]
    assert ordens["5018863"]["status_sap"] == "LIB ENCE"


def test_montar_ordens_universo_vem_do_backlog_nao_do_iw37():
    """Inversão de fonte: ordem aberta no backlog SEM operação na IW37 ainda aparece (tempo 0);
    e operação da IW37 de ordem que NÃO está no backlog é ignorada (não polui a fila)."""
    plan = {"docs": [
        {"ordem": "5018863", "operacao": "0010", "planejado_min": 120},   # está no backlog
        {"ordem": "9999_fora", "operacao": "0010", "planejado_min": 500},  # NÃO está no backlog
    ], "coleta_id": "p", "coletado_em": None}
    real = {"docs": [], "coleta_id": "r", "coletado_em": None}
    bl = [
        {"ordem": "5018863", "descricao": "Com IW37", "disciplina": "Eletrica",
         "categoria": "Corretiva", "data_criacao": None, "data_inicio": None, "local_instalacao": ""},
        {"ordem": "5006959", "descricao": "Velha sem IW37", "disciplina": "Mecanica",
         "categoria": "Corretiva", "data_criacao": None, "data_inicio": None, "local_instalacao": ""},
    ]
    def fake_load(coll, silent=True):
        return plan if coll == hh_data.COLL_PLAN else real
    p_snap, p_ativos, p_enr = _patch_backlog(bl)
    with patch.object(hh_data, "_carregar_snapshot", side_effect=fake_load), \
         p_snap, p_ativos, p_enr:
        res = hh_data.montar_ordens()
    ordens = res["ordens"]
    # as duas do backlog aparecem
    assert set(ordens.keys()) == {"5018863", "5006959"}
    # a ordem fora do backlog foi ignorada (não entra na fila)
    assert "9999_fora" not in ordens
    # ordem velha sem IW37: aparece com tempo 0 / aderência indefinida
    assert ordens["5006959"]["planejado_min"] == 0
    assert ordens["5006959"]["operacoes"] == 0
    assert ordens["5006959"]["aderencia"] is None
    # ordem com IW37: traz o tempo planejado
    assert ordens["5018863"]["planejado_min"] == 120


def test_montar_ordens_aderencia_none_sem_planejado():
    plan = {"docs": [], "coleta_id": "p", "coletado_em": None}
    real = {"docs": [{"ordem": "9000", "operacao": "0010", "realizado_min": 50,
                      "executores": [], "status_sap": None}],
            "coleta_id": "r", "coletado_em": None}
    bl = [{"ordem": "9000", "descricao": "Ordem 9000", "disciplina": "Mecanica",
           "categoria": "Corretiva", "data_criacao": None, "data_inicio": None, "local_instalacao": ""}]
    def fake_load(coll, silent=True):
        return plan if coll == hh_data.COLL_PLAN else real
    p_snap, p_ativos, p_enr = _patch_backlog(bl)
    with patch.object(hh_data, "_carregar_snapshot", side_effect=fake_load), \
         p_snap, p_ativos, p_enr:
        res = hh_data.montar_ordens()
    assert res["ordens"]["9000"]["aderencia"] is None   # sem planejado → indefinida


def test_montar_ordens_none_se_mongo_cair():
    with patch.object(hh_data, "_carregar_snapshot", return_value=None), \
         patch.object(hh_data.bd, "carregar_snapshot", return_value=None):
        assert hh_data.montar_ordens() is None


# ---- atribuível (BR-07) --------------------------------------------------------------

def test_aplicar_filtro_ordens():
    from src.pages.maintenance import hh_quadro
    lista = [
        {"ordem": "5001", "descricao": "Trocar rolamento", "realizado_min": 0,
         "_pendente": True, "_idade_dias": 100, "_carry_over": 0, "planejado_min": 50, "aderencia": None},
        {"ordem": "5002", "descricao": "Limpar painel", "realizado_min": 60,
         "_pendente": False, "_idade_dias": 10, "_carry_over": 2, "planejado_min": 120, "aderencia": 0.5},
        {"ordem": "5003", "descricao": "Revisar motor", "realizado_min": 30,
         "_pendente": True, "_idade_dias": 300, "_carry_over": 0, "planejado_min": 200, "aderencia": 0.9},
    ]
    # busca por descrição
    r = hh_quadro.aplicar_filtro_ordens(lista, {"busca": "motor"})
    assert [o["ordem"] for o in r] == ["5003"]
    # só com tempo lançado
    r = hh_quadro.aplicar_filtro_ordens(lista, {"com_realizado": True})
    assert {o["ordem"] for o in r} == {"5002", "5003"}
    # só pendentes
    r = hh_quadro.aplicar_filtro_ordens(lista, {"so_pendentes": True})
    assert {o["ordem"] for o in r} == {"5001", "5003"}
    # ordenar por mais antiga
    r = hh_quadro.aplicar_filtro_ordens(lista, {"ordenar": "antiga"})
    assert [o["ordem"] for o in r] == ["5003", "5001", "5002"]
    # ordenar por menor aderência (None por último)
    r = hh_quadro.aplicar_filtro_ordens(lista, {"ordenar": "aderencia"})
    assert [o["ordem"] for o in r][:2] == ["5002", "5003"]
    # planejado > 0: ordem sem plano some
    lista_p = lista + [{"ordem": "5004", "descricao": "sem plano", "realizado_min": 0,
                        "_pendente": False, "_idade_dias": 5, "_carry_over": 0,
                        "planejado_min": 0, "aderencia": None}]
    r = hh_quadro.aplicar_filtro_ordens(lista_p, {"planejado_pos": True})
    assert {o["ordem"] for o in r} == {"5001", "5002", "5003"}   # 5004 (plan 0) fora
    # nao_100 (parcialmente planejada: 0 < restante < planejado) → só a P1
    lista_r = [
        {"ordem": "P1", "planejado_min": 120, "_restante_min": 60, "descricao": "",
         "realizado_min": 0, "_pendente": False, "_idade_dias": 0, "_carry_over": 0, "aderencia": None},
        {"ordem": "P2", "planejado_min": 120, "_restante_min": 120, "descricao": "",   # não iniciada
         "realizado_min": 0, "_pendente": False, "_idade_dias": 0, "_carry_over": 0, "aderencia": None},
        {"ordem": "P3", "planejado_min": 0, "_restante_min": 0, "descricao": "",       # sem plano
         "realizado_min": 0, "_pendente": False, "_idade_dias": 0, "_carry_over": 0, "aderencia": None},
    ]
    r = hh_quadro.aplicar_filtro_ordens(lista_r, {"nao_100": True})
    assert {o["ordem"] for o in r} == {"P1"}


def test_filtro_linha_a_planejar():
    # B16: filtro por Linha/ativo restringe a fila por `_linha_id`
    from src.pages.maintenance import hh_quadro
    lista = [
        {"ordem": "5001", "_linha_id": "L-ENV01", "descricao": "a"},
        {"ordem": "5002", "_linha_id": "L-ENV02", "descricao": "b"},
        {"ordem": "5003", "_linha_id": None, "descricao": "c"},
    ]
    # nenhuma linha selecionada → passa tudo
    assert len(hh_quadro.aplicar_filtro_ordens(lista, {"linhas": []})) == 3
    # uma linha → só ela
    r = hh_quadro.aplicar_filtro_ordens(lista, {"linhas": ["L-ENV01"]})
    assert [o["ordem"] for o in r] == ["5001"]
    # multi-seleção → união
    r = hh_quadro.aplicar_filtro_ordens(lista, {"linhas": ["L-ENV01", "L-ENV02"]})
    assert {o["ordem"] for o in r} == {"5001", "5002"}
    # helper direto: ordem sem linha nunca passa quando há filtro
    assert hh_quadro._passa_linha({"_linha_id": None}, ["L-ENV01"]) is False
    assert hh_quadro._passa_linha({"_linha_id": None}, []) is True


def _lista_estados():
    """Amostra que cobre os 3 casos de rótulo: conhecido, código cru sem tradução e sem estado."""
    return [
        {"ordem": "5001", "_status_usuario_label": "Em Pausa", "descricao": "a"},
        {"ordem": "5002", "_status_usuario_label": "Aberta", "descricao": "b"},
        {"ordem": "5003", "_status_usuario_label": None, "descricao": "c"},        # sem estado
        {"ordem": "5004", "_status_usuario_label": "CBTN ENPA", "descricao": "d"},  # código cru
    ]


def test_filtro_estado_a_planejar():
    # B31: filtro por estado (status do usuário) restringe pelo rótulo `_status_usuario_label`
    from src.pages.maintenance import hh_quadro
    lista = _lista_estados()
    # B52: filtro nunca aplicado (chave ausente) → passa tudo
    assert len(hh_quadro.aplicar_filtro_ordens(lista, {})) == 4
    # um estado → só ele
    r = hh_quadro.aplicar_filtro_ordens(lista, {"estados": ["Em Pausa"]})
    assert [o["ordem"] for o in r] == ["5001"]
    # multi-seleção → união
    r = hh_quadro.aplicar_filtro_ordens(lista, {"estados": ["Em Pausa", "Aberta"]})
    assert {o["ordem"] for o in r} == {"5001", "5002"}
    # helper direto: ordem sem estado não passa quando o coringa não está marcado
    assert hh_quadro._passa_status({"_status_usuario_label": None}, ["Em Pausa"]) is False


def test_filtro_estado_default_nao_esconde_nenhuma_ordem():
    """B52: com todas as caixinhas marcadas (default), o quadro mostra o mesmo que mostrava com o
    filtro vazio antes — inclusive código cru sem tradução e ordem sem estado. Sem o coringa
    `ESTADO_OUTROS`, 1,8% do backlog do cliente sumiria da tela sem ninguém pedir."""
    from src.pages.maintenance import hh_quadro
    lista = _lista_estados()
    r = hh_quadro.aplicar_filtro_ordens(lista, {"estados": hh_quadro.ESTADOS_DEFAULT})
    assert {o["ordem"] for o in r} == {"5001", "5002", "5003", "5004"}
    # o default marca os 6 rótulos + o coringa
    assert hh_quadro.ESTADO_OUTROS in hh_quadro.ESTADOS_DEFAULT
    assert len(hh_quadro.ESTADOS_DEFAULT) == 7


def test_filtro_estado_coringa_outros():
    """B52: o coringa recolhe exatamente o que não cai nos 6 rótulos conhecidos."""
    from src.pages.maintenance import hh_quadro
    lista = _lista_estados()
    # só o coringa → só código cru e sem estado
    r = hh_quadro.aplicar_filtro_ordens(lista, {"estados": [hh_quadro.ESTADO_OUTROS]})
    assert {o["ordem"] for o in r} == {"5003", "5004"}
    # os 6 conhecidos SEM o coringa → derruba os dois
    seis = [e for e in hh_quadro.ESTADOS_DEFAULT if e != hh_quadro.ESTADO_OUTROS]
    r = hh_quadro.aplicar_filtro_ordens(lista, {"estados": seis})
    assert {o["ordem"] for o in r} == {"5001", "5002"}


def test_filtro_estado_tudo_desmarcado_nao_passa_nada():
    """B52: caixinha desmarcada significa 'não quero ver'. Desmarcar todas esvazia a lista —
    inversão deliberada da semântica do B31, onde lista vazia queria dizer 'passa tudo'."""
    from src.pages.maintenance import hh_quadro
    lista = _lista_estados()
    assert hh_quadro.aplicar_filtro_ordens(lista, {"estados": []}) == []
    assert hh_quadro._passa_status({"_status_usuario_label": "Aberta"}, []) is False


def test_filtra_localizacao_pendentes():
    # pendentes não são planejáveis mas devem ser LOCALIZÁVEIS por número/descrição e por linha
    from src.pages.maintenance import hh_quadro
    pend = [
        {"ordem": "9001", "descricao": "sem classe A", "_linha_id": "L1", "_pendente": True,
         "realizado_min": 0},
        {"ordem": "9002", "descricao": "sem classe B", "_linha_id": "L2", "_pendente": False,
         "realizado_min": 99},
    ]
    # busca por número isola a ordem
    assert [o["ordem"] for o in hh_quadro._filtra_localizacao(pend, {"busca": "9001"})] == ["9001"]
    # busca por descrição
    assert [o["ordem"] for o in hh_quadro._filtra_localizacao(pend, {"busca": "classe B"})] == ["9002"]
    # filtro de linha também vale aqui
    assert [o["ordem"] for o in hh_quadro._filtra_localizacao(pend, {"linhas": ["L2"]})] == ["9002"]
    # flags de planejamento NÃO se aplicam ao pendente (com_realizado/so_pendentes ignorados)
    assert len(hh_quadro._filtra_localizacao(pend, {"com_realizado": True})) == 2
    assert len(hh_quadro._filtra_localizacao(pend, {"so_pendentes": True})) == 2
    # sem filtro → lista completa (comportamento pré-mudança)
    assert len(hh_quadro._filtra_localizacao(pend, {})) == 2


def test_cabecalho_backlog_copia_linha_id():
    # B16: o cabeçalho precisa propagar `_linha_id` (não só `linha_nome`) para o filtro funcionar
    ordens = {"5001": {"_centros": {}, "_textos": {}}}
    idx_bl = {"5001": {"disciplina": "Mecanica", "_linha_id": "L-ENV01",
                       "_linha_nome": "Envase 01", "descricao": "troca"}}
    hh_data._aplicar_cabecalho_backlog(ordens, idx_bl)
    assert ordens["5001"]["_linha_id"] == "L-ENV01"
    assert ordens["5001"]["linha_nome"] == "Envase 01"


def test_disc_por_centros_fallback():
    # 0010 prioritário
    assert hh_data._disc_por_centros({"0010": "Z12", "0020": "Z22"}) == "Mecanica"
    assert hh_data._disc_por_centros({"0010": "Z22"}) == "Eletrica"
    # 0010 genérico (Z02) → cai na 1a operação com centro Z1x/Z2x
    assert hh_data._disc_por_centros({"0010": "Z02", "0020": "Z23"}) == "Eletrica"
    # nenhum centro classificável → NaoClassificado
    assert hh_data._disc_por_centros({"0010": "Z02", "0020": "MAN"}) == "NaoClassificado"
    assert hh_data._disc_por_centros({}) == "NaoClassificado"


def test_pertence_disciplina_none_vs_vazia():
    # campo ausente (None) → pertence às DUAS (retrocompat)
    assert hh_data.pertence_disciplina({}, "Mecanica") is True
    assert hh_data.pertence_disciplina({}, "Eletrica") is True
    # lista vazia → NENHUMA (ex.: ADM) — não reaparece nas duas (bug do bounce)
    assert hh_data.pertence_disciplina({"disciplinas": []}, "Mecanica") is False
    assert hh_data.pertence_disciplina({"disciplinas": []}, "Eletrica") is False
    # membership literal
    assert hh_data.pertence_disciplina({"disciplinas": ["Mecanica"]}, "Mecanica") is True
    assert hh_data.pertence_disciplina({"disciplinas": ["Mecanica"]}, "Eletrica") is False

def test_func_fora_disc_inclui_quem_nao_pertence():
    funcs = [
        {"_id": "a", "nome": "Ana", "ativo": True, "disciplinas": ["Eletrica"]},   # fora de Mec
        {"_id": "b", "nome": "Bia", "ativo": True, "disciplinas": []},              # fora de tudo
        {"_id": "c", "nome": "Cleber", "ativo": True},                             # None → nas duas
    ]
    fora_mec = {f["id"] for f in hh_data._func_fora_disc(funcs, "Mecanica")}
    assert fora_mec == {"a", "b"}        # Cleber (None) não está fora; Ana e Bia sim


def test_ordem_atribuivel():
    assert hh_data.ordem_atribuivel({"disciplina": "Mecanica"}) is True
    assert hh_data.ordem_atribuivel({"disciplina": "Eletrica"}) is True
    assert hh_data.ordem_atribuivel({"disciplina": "Terceiros"}) is True   # B15 (coringa)
    assert hh_data.ordem_atribuivel({"disciplina": "NaoClassificado"}) is False


def test_disc_classifica_terceiros_z03():
    # B15: centro Z03 → Terceiros; Z02 continua não-classificando; Z1x/Z2x inalterados
    assert hh_data._disc_classifica("Z03") == "Terceiros"
    assert hh_data._disc_classifica(" z03 ") == "Terceiros"
    assert hh_data._disc_classifica("Z02") is None
    assert hh_data._disc_classifica("Z12") == "Mecanica"
    assert hh_data._disc_classifica("Z22") == "Eletrica"


def test_aplicar_cabecalho_terceiros_por_centro_backlog():
    # o daemon carimba Z03 como NaoClassificado; o webapp deriva Terceiros pelo centro do backlog
    ordens = {"5001": {"_centros": {}, "_textos": {}}}
    idx_bl = {"5001": {"disciplina": "NaoClassificado", "centro_operacao_0010": "Z03",
                       "descricao": "troca de rolamento"}}
    hh_data._aplicar_cabecalho_backlog(ordens, idx_bl)
    assert ordens["5001"]["disciplina"] == "Terceiros"


def test_pode_atribuir_so_mesma_disciplina():
    base = {"ordens": {
        "ELE1": {"ordem": "ELE1", "disciplina": "Eletrica"},
        "NC1": {"ordem": "NC1", "disciplina": "NaoClassificado"},
    }}
    funcs = [
        {"_id": "m1", "disciplinas": ["Mecanica"]},     # só Mecânica
        {"_id": "e1", "disciplinas": ["Eletrica"]},     # só Elétrica
    ]
    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=funcs):
        # ordem Elétrica num técnico Mecânico → recusa (cross-disciplina)
        assert hh_data.pode_atribuir("ELE1", "m1") is False
        # ordem Elétrica num técnico Elétrico → ok
        assert hh_data.pode_atribuir("ELE1", "e1") is True
        # ordem não classificada → recusa sempre
        assert hh_data.pode_atribuir("NC1", "e1") is False


def test_pode_atribuir_terceiros_coringa():
    # B15: Terceiros aceita nos DOIS quadros; valida contra o quadro-destino (disc_quadro)
    base = {"ordens": {"TER1": {"ordem": "TER1", "disciplina": "Terceiros"}}}
    funcs = [
        {"_id": "m1", "disciplinas": ["Mecanica"]},
        {"_id": "e1", "disciplinas": ["Eletrica"]},
    ]
    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=funcs):
        # Terceiros no quadro Mecânica + técnico Mecânico → ok
        assert hh_data.pode_atribuir("TER1", "m1", "Mecanica") is True
        # Terceiros no quadro Elétrica + técnico Elétrico → ok
        assert hh_data.pode_atribuir("TER1", "e1", "Eletrica") is True
        # Terceiros no quadro Mecânica mas técnico é Elétrico → recusa
        assert hh_data.pode_atribuir("TER1", "e1", "Mecanica") is False
        # sem quadro-destino (coringa sem alvo) → recusa (blindagem do servidor)
        assert hh_data.pode_atribuir("TER1", "m1") is False


def test_pode_atribuir_disciplina_cruzada_com_quadro():
    """B33: com quadro-destino, valida contra o QUADRO (não a disciplina da ordem) → permite
    cruzada Elé→Mec. Não classificada segue bloqueada."""
    base = {"ordens": {
        "ELE1": {"ordem": "ELE1", "disciplina": "Eletrica"},
        "MEC1": {"ordem": "MEC1", "disciplina": "Mecanica"},
        "NC1": {"ordem": "NC1", "disciplina": "NaoClassificado"},
    }}
    funcs = [{"_id": "m1", "disciplinas": ["Mecanica"]},
             {"_id": "e1", "disciplinas": ["Eletrica"]}]
    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=funcs):
        # ordem Elétrica no quadro Mecânica + técnico Mecânico → OK (cruzada permitida, B33)
        assert hh_data.pode_atribuir("ELE1", "m1", "Mecanica") is True
        # ordem Mecânica no quadro Elétrica + técnico Elétrico → OK (cruzada inversa)
        assert hh_data.pode_atribuir("MEC1", "e1", "Eletrica") is True
        # o técnico ainda tem de ser do QUADRO: ordem Elé no quadro Mec + técnico Elé → recusa
        assert hh_data.pode_atribuir("ELE1", "e1", "Mecanica") is False
        # não classificada em qualquer quadro → recusa (BR-07 permanece)
        assert hh_data.pode_atribuir("NC1", "m1", "Mecanica") is False


def test_disciplina_da_ordem():
    base = {"ordens": {"E1": {"ordem": "E1", "disciplina": "Eletrica"}}}
    with patch.object(hh_data, "montar_ordens", return_value=base):
        assert hh_data.disciplina_da_ordem("E1") == "Eletrica"
        assert hh_data.disciplina_da_ordem("INEXISTENTE") is None


# ---- capacidade/disponibilidade (B3, DS-05/BR-08) ------------------------------------

def test_jornada_min_deriva_do_turno():
    # disponível LÍQUIDO (jornada − almoço): A=6h (sem almoço), B/C/ADM=8h (9h−1h) — SP-13
    assert hh_data.jornada_min({"turno_padrao": "A"}) == 360
    assert hh_data.jornada_min({"turno_padrao": "B"}) == 480

def test_jornada_min_override():
    assert hh_data.jornada_min({"turno_padrao": "B", "jornada_min": 360}) == 360

def test_indisponivel_no_dia_overlap():
    dia = datetime(2026, 6, 29)          # segunda
    # alocação cobrindo a segunda inteira
    assigns = [{"data_hora_entrada": datetime(2026, 6, 29, 8, 0),
                "data_hora_saida": datetime(2026, 6, 29, 17, 0)}]
    assert hh_data.indisponivel_no_dia(assigns, dia) is True

def test_indisponivel_no_dia_sem_overlap():
    dia = datetime(2026, 6, 29)
    assigns = [{"data_hora_entrada": datetime(2026, 7, 1, 8, 0),   # quarta
                "data_hora_saida": datetime(2026, 7, 1, 17, 0)}]
    assert hh_data.indisponivel_no_dia(assigns, dia) is False


# ---- comprometimentos (B32 / SP-05.6) --------------------------------------------------

def test_comprometimentos_lista_titulos_do_dia():
    """Técnico com alocação cobrindo o dia-alvo → devolve o título da atividade do Gantt."""
    from src.utils import gantt_db
    # W27 = 2026-06-29(seg)..07-05(dom); dia 3 = quinta 2026-07-02
    assigns = [{"atividade_id": "a1", "data_hora_entrada": datetime(2026, 7, 1),
                "data_hora_saida": datetime(2026, 7, 3)},           # cobre qua+qui
               {"atividade_id": "a2", "data_hora_entrada": datetime(2026, 6, 29, 8),
                "data_hora_saida": datetime(2026, 6, 29, 17)}]      # segunda (não toca quinta)
    with patch.object(gantt_db, "get_assignments_by_employee", return_value=assigns), \
         patch.object(gantt_db, "get_activity_by_id",
                      side_effect=lambda aid: {"a1": {"titulo": "Férias - 2026"},
                                               "a2": {"titulo": "Serviço X"}}.get(aid)):
        # quinta (dia 3) → só a atividade que sobrepõe
        assert hh_data.comprometimentos("f1", "2026-W27", 3) == ["Férias - 2026"]


def test_comprometimentos_vazio_quando_livre():
    """Técnico sem alocação tocando o dia → lista vazia (não abre modal no drop)."""
    from src.utils import gantt_db
    assigns = [{"atividade_id": "a2", "data_hora_entrada": datetime(2026, 6, 29, 8),
                "data_hora_saida": datetime(2026, 6, 29, 17)}]     # segunda
    with patch.object(gantt_db, "get_assignments_by_employee", return_value=assigns), \
         patch.object(gantt_db, "get_activity_by_id", return_value={"titulo": "Serviço X"}):
        assert hh_data.comprometimentos("f1", "2026-W27", 3) == []   # quinta livre


def test_comprometimentos_dedup_e_fallback_sem_titulo():
    """Títulos repetidos deduplicados; atividade sem título vira rótulo genérico."""
    from src.utils import gantt_db
    assigns = [{"atividade_id": "a1", "data_hora_entrada": datetime(2026, 6, 29),
                "data_hora_saida": datetime(2026, 6, 30)},
               {"atividade_id": "a1b", "data_hora_entrada": datetime(2026, 6, 29),
                "data_hora_saida": datetime(2026, 6, 30)},
               {"atividade_id": "a3", "data_hora_entrada": datetime(2026, 6, 29),
                "data_hora_saida": datetime(2026, 6, 30)}]
    with patch.object(gantt_db, "get_assignments_by_employee", return_value=assigns), \
         patch.object(gantt_db, "get_activity_by_id",
                      side_effect=lambda aid: {"a1": {"titulo": "Férias - 2026"},
                                               "a1b": {"titulo": "Férias - 2026"},
                                               "a3": {"titulo": ""}}.get(aid)):
        out = hh_data.comprometimentos("f1", "2026-W27", 0)          # segunda
        assert out == ["Comprometido no Gantt", "Férias - 2026"]     # dedup + fallback, ordenado

def test_capacidade_desconta_indisponivel_e_calcula():
    semana = "2026-W27"   # segunda = 29/06
    funcionarios = [
        {"_id": "c1", "turno_padrao": "B", "ativo": True},   # Carlos
        {"_id": "c2", "turno_padrao": "B", "ativo": True},   # João
    ]
    # João (c2) está alocado (férias/serviço) na segunda → indisponível
    assignments = {"c2": [{"data_hora_entrada": datetime(2026, 6, 29),
                           "data_hora_saida": datetime(2026, 6, 30)}]}
    atribuicoes = [
        {"ordem": "A", "funcionario_id": "c1", "dia": 0, "parcela_min": None},
    ]
    ordens = {"A": {"planejado_min": 120, "realizado_min": 60}}
    cap = hh_data.calcular_capacidade(semana, funcionarios, atribuicoes, ordens, assignments)
    seg = cap["B"][0]
    # disponível só do Carlos (João indisponível): 480 (8h líquido, não 960) — SP-13
    assert seg["disponivel"] == 480
    assert seg["programado"] == 120          # ordem inteira (parcela None → planejado)
    assert seg["executado"] == 60
    assert abs(seg["pct_programado"] - 120/480) < 1e-9
    assert abs(seg["aderencia"] - 60/120) < 1e-9

def test_capacidade_executado_rateado_em_split():
    semana = "2026-W27"
    funcionarios = [{"_id": "c1", "turno_padrao": "B", "ativo": True}]
    # ordem de 600 planejado / 300 realizado, dividida: 480 na segunda + 120 na terça
    atribuicoes = [
        {"ordem": "X", "funcionario_id": "c1", "dia": 0, "parcela_min": 480},
        {"ordem": "X", "funcionario_id": "c1", "dia": 1, "parcela_min": 120},
    ]
    ordens = {"X": {"planejado_min": 600, "realizado_min": 300}}
    cap = hh_data.calcular_capacidade(semana, funcionarios, atribuicoes, ordens, {})
    # executado rateado: 300*(480/600)=240 na seg, 300*(120/600)=60 na ter → soma 300 (reconcilia)
    assert cap["B"][0]["executado"] == 240
    assert cap["B"][1]["executado"] == 60

def test_capacidade_conta_so_ordens_da_disciplina():
    # técnico em ambas as disciplinas com 1 ordem Elétrica atribuída: a capacidade da
    # Mecânica NÃO deve contá-la (senão resumo conta sem card no slot — bug do turno B)
    semana = "2026-W27"
    funcs = [{"_id": "c1", "turno_padrao": "B", "ativo": True}]
    atribs = [{"ordem": "ELE1", "funcionario_id": "c1", "dia": 0, "parcela_min": None}]
    ordens = {"ELE1": {"planejado_min": 100, "realizado_min": 0, "disciplina": "Eletrica"}}
    cap_mec = hh_data.calcular_capacidade(semana, funcs, atribs, ordens, {}, disc="Mecanica")
    cap_ele = hh_data.calcular_capacidade(semana, funcs, atribs, ordens, {}, disc="Eletrica")
    assert cap_mec["B"][0]["n_ordens"] == 0          # Mecânica não conta a ordem Elétrica
    assert cap_mec["B"][0]["programado"] == 0
    assert cap_ele["B"][0]["n_ordens"] == 1          # Elétrica conta
    assert cap_ele["B"][0]["programado"] == 100


def test_capacidade_terceiros_conta_no_quadro_destino():
    # B15: ordem Terceiros atribuída ao quadro Mecânica (disciplina_quadro) conta na capacidade
    # da Mecânica — não na da Elétrica — mesmo tendo disciplina "Terceiros"
    semana = "2026-W27"
    funcs = [{"_id": "c1", "turno_padrao": "B", "ativo": True}]
    atribs = [{"ordem": "TER1", "funcionario_id": "c1", "dia": 0, "parcela_min": None,
               "disciplina_quadro": "Mecanica"}]
    ordens = {"TER1": {"planejado_min": 100, "realizado_min": 0, "disciplina": "Terceiros"}}
    cap_mec = hh_data.calcular_capacidade(semana, funcs, atribs, ordens, {}, disc="Mecanica")
    cap_ele = hh_data.calcular_capacidade(semana, funcs, atribs, ordens, {}, disc="Eletrica")
    assert cap_mec["B"][0]["n_ordens"] == 1          # conta no quadro-destino
    assert cap_mec["B"][0]["programado"] == 100
    assert cap_ele["B"][0]["n_ordens"] == 0          # não conta no outro quadro


def test_capacidade_disponivel_none_sem_jornada():
    semana = "2026-W27"
    funcionarios = [{"_id": "c1", "turno_padrao": "X", "ativo": True}]   # turno sem jornada
    cap = hh_data.calcular_capacidade(semana, funcionarios, [], {}, {})
    assert cap["X"][0]["disponivel"] is None


# ---- montagem do quadro (B5, DS-06/BR-07/19) -----------------------------------------

def test_montar_quadro_distribui_e_separa():
    semana = "2026-W27"
    base = {"ordens": {
        "MEC1": {"ordem": "MEC1", "disciplina": "Mecanica", "planejado_min": 120,
                 "realizado_min": 60, "data_criacao": None},
        "ELE1": {"ordem": "ELE1", "disciplina": "Eletrica", "planejado_min": 200,
                 "realizado_min": 0, "data_criacao": None},
        "NC1":  {"ordem": "NC1", "disciplina": "NaoClassificado", "centro_operacao_0010": "Z02",
                 "planejado_min": 0, "realizado_min": 0, "data_criacao": None},
        # B37: NaoClassificado sem centro classificável (MAN) fica fora da fila pendente
        "NCM":  {"ordem": "NCM", "disciplina": "NaoClassificado", "centro_operacao_0010": "MAN",
                 "planejado_min": 0, "realizado_min": 0, "data_criacao": None},
    }, "coletado_em": None}
    funcionarios = [
        {"_id": "c1", "nome": "Carlos", "turno_padrao": "B", "ativo": True},
        {"_id": "a1", "nome": "Ana", "turno_padrao": "A", "ativo": True},
    ]
    # MEC1 atribuída ao Carlos na segunda; ELE1 e NC1 não atribuídas
    atribs = [{"_id": "x1", "ordem": "MEC1", "funcionario_id": "c1", "dia": 0, "parcela_min": None}]

    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "listar_atribuicoes", return_value=atribs), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=funcionarios), \
         patch.object(hh_data, "_assignments_por_func", return_value={}), \
         patch.object(hh_data, "carry_over", return_value=0), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 6, 30)):
        q = hh_data.montar_quadro(semana)

    # MEC1 cai no slot Carlos/segunda da Mecânica
    carlos = next(t for t in q["disciplinas"]["Mecanica"]["tecnicos"] if t["funcionario_id"] == "c1")
    assert [o["ordem"] for o in carlos["dias"][0]] == ["MEC1"]
    # ELE1 (classificada, não atribuída) vai para "a planejar" da Elétrica
    assert [o["ordem"] for o in q["a_planejar"]["Eletrica"]] == ["ELE1"]
    # NC1 (não classificada, centro Z02) fica em pendentes (bloqueada — BR-07); NCM (centro MAN)
    # sai da fila (B37 — sem centro classificável)
    assert [o["ordem"] for o in q["pendentes_classificacao"]] == ["NC1"]

def test_montar_quadro_ferramentaria_fora_do_quadro():
    # B37: Ferramentaria (Z04) é classificada mas não vira card — some da fila e da pendência
    semana = "2026-W27"
    base = {"ordens": {
        "FER1": {"ordem": "FER1", "disciplina": "Ferramentaria", "centro_operacao_0010": "Z04",
                 "planejado_min": 0, "realizado_min": 0, "data_criacao": None},
        "MEC1": {"ordem": "MEC1", "disciplina": "Mecanica", "centro_operacao_0010": "Z10",
                 "planejado_min": 100, "realizado_min": 0, "data_criacao": None},
    }, "coletado_em": None}
    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "listar_atribuicoes", return_value=[]), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=[]), \
         patch.object(hh_data, "_assignments_por_func", return_value={}), \
         patch.object(hh_data, "carry_over", return_value=0), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 6, 30)):
        q = hh_data.montar_quadro(semana)
    todas_fila = ([o["ordem"] for o in q["pendentes_classificacao"]]
                  + [o["ordem"] for o in q["a_planejar"]["Mecanica"]]
                  + [o["ordem"] for o in q["a_planejar"]["Eletrica"]]
                  + [o["ordem"] for o in q["terceiros"]])
    assert "FER1" not in todas_fila            # ferramentaria não aparece em lugar nenhum da fila
    assert "MEC1" in q["a_planejar"]["Mecanica"][0]["ordem"] or \
           q["a_planejar"]["Mecanica"][0]["ordem"] == "MEC1"


def test_montar_quadro_terceiros_coringa():
    # B15: Terceiros atribuída pousa no quadro gravado (disciplina_quadro); não atribuída fica na
    # fila `terceiros` própria (não em pendentes nem em a_planejar)
    semana = "2026-W27"
    base = {"ordens": {
        "TER1": {"ordem": "TER1", "disciplina": "Terceiros", "planejado_min": 100,
                 "realizado_min": 0, "data_criacao": None},
        "TER2": {"ordem": "TER2", "disciplina": "Terceiros", "planejado_min": 50,
                 "realizado_min": 0, "data_criacao": None},
    }, "coletado_em": None}
    funcionarios = [{"_id": "c1", "nome": "Carlos", "turno_padrao": "B", "ativo": True}]
    # TER1 atribuída ao Carlos no quadro Mecânica; TER2 não atribuída
    atribs = [{"_id": "x1", "ordem": "TER1", "funcionario_id": "c1", "dia": 0,
               "parcela_min": None, "disciplina_quadro": "Mecanica"}]
    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "listar_atribuicoes", return_value=atribs), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=funcionarios), \
         patch.object(hh_data, "_assignments_por_func", return_value={}), \
         patch.object(hh_data, "carry_over", return_value=0), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 6, 30)):
        q = hh_data.montar_quadro(semana)
    # TER1 cai no slot Carlos/segunda do quadro Mecânica (via disciplina_quadro)
    carlos = next(t for t in q["disciplinas"]["Mecanica"]["tecnicos"] if t["funcionario_id"] == "c1")
    assert [o["ordem"] for o in carlos["dias"][0]] == ["TER1"]
    # TER2 (não atribuída) fica na fila terceiros
    assert [o["ordem"] for o in q["terceiros"]] == ["TER2"]
    assert q["pendentes_classificacao"] == []


def test_montar_quadro_none_se_mongo_cair():
    with patch.object(hh_data, "montar_ordens", return_value=None):
        assert hh_data.montar_quadro("2026-W27") is None


# ---- B30: status do usuário (USTXT) → rótulo rico -------------------------------------

def test_status_usuario_label_defaults():
    m = dict(hh_data._STATUS_USR_DEFAULT)
    assert hh_data.status_usuario_label("ENTR", m) == "Em Tratamento"
    assert hh_data.status_usuario_label("CERR", m) == "Encerrada"
    assert hh_data.status_usuario_label("abie", m) == "Aberta"        # case-insensitive
    assert hh_data.status_usuario_label("ENPA XYZ", m) == "Em Pausa"  # casa o 1º token
    assert hh_data.status_usuario_label("ZZZ", m) == "ZZZ"            # desconhecido → código cru
    assert hh_data.status_usuario_label(None, m) is None


def test_cor_status_usuario():
    # pedido PCM 2026-07-15: Aberta=vermelho, andamento=amarelo, Encerrada=verde, Cancelada=cinza.
    assert hh_data.cor_status_usuario("ABIE") == "aberta"
    assert hh_data.cor_status_usuario("ENTR") == "andamento"
    assert hh_data.cor_status_usuario("ENPA PRIO") == "andamento"   # combo casa pelo 1º token
    assert hh_data.cor_status_usuario("ESAC") == "andamento"
    assert hh_data.cor_status_usuario("CERR") == "encerrada"
    assert hh_data.cor_status_usuario("CANC SMTO") == "cancelada"
    assert hh_data.cor_status_usuario("XPTO") is None               # desconhecido → sem cor especial
    # sem código (snapshot legado) → mapeia pelo rótulo
    assert hh_data.cor_status_usuario(None, "Cancelada") == "cancelada"
    assert hh_data.cor_status_usuario(None, "Encerrada") == "encerrada"


def test_montar_quadro_status_usuario_vira_pill():
    # ordem aberta com USTXT=ENTR → o card ganha _status_usuario_label "Em Tratamento"
    base = {"ordens": {"MEC1": {"ordem": "MEC1", "disciplina": "Mecanica", "planejado_min": 120,
                                "realizado_min": 0, "status_usuario": "ENTR", "data_criacao": None}},
            "coletado_em": None}
    atribs = [{"_id": "x1", "ordem": "MEC1", "funcionario_id": "c1", "dia": 0, "parcela_min": None}]
    funcs = [{"_id": "c1", "nome": "Carlos", "turno_padrao": "B", "ativo": True,
              "disciplinas": ["Mecanica"]}]
    with patch.object(hh_data, "_mapa_status_usuario", return_value=dict(hh_data._STATUS_USR_DEFAULT)):
        q = _quadro_com(base, atribs, funcs)
    carlos = next(t for t in q["disciplinas"]["Mecanica"]["tecnicos"] if t["funcionario_id"] == "c1")
    assert carlos["dias"][0][0]["_status_usuario_label"] == "Em Tratamento"


# ---- BR-20: ordem entregue não some do quadro (snapshot / re-consulta dirigida) ------

def _quadro_com(base, atribs, funcionarios):
    """Helper de teste: monta o quadro com os carregadores monkeypatchados (padrão dos testes)."""
    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "listar_atribuicoes", return_value=atribs), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=funcionarios), \
         patch.object(hh_data, "_assignments_por_func", return_value={}), \
         patch.object(hh_data, "carry_over", return_value=0), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 6, 30)):
        return hh_data.montar_quadro("2026-W27")


_FUNCS_BR20 = [{"_id": "c1", "nome": "Carlos", "turno_padrao": "B", "ativo": True}]


def test_montar_quadro_entrega_encerrada_nao_some():
    # BR-20 revisado (2026-07-15): ordem atribuída que SAIU do universo de abertas NÃO some — render
    # do snapshot congelado no slot, com aderência final e o STATUS DO USUÁRIO (CERR→Encerrada).
    base = {"ordens": {}, "coletado_em": None}   # ordem MEC1 não está mais no universo (saiu)
    atribs = [{"_id": "x1", "ordem": "MEC1", "funcionario_id": "c1", "dia": 0,
               "parcela_min": None, "disciplina": "Mecanica",
               "entrega": {"status_saida": "encerrada", "status_usuario": "CERR",
                           "planejado_min": 120, "realizado_min": 110, "aderencia": 0.9167,
                           "status_sistema": "ENTE", "superado": False,
                           "cabecalho": {"disciplina": "Mecanica", "descricao": "Troca rolamento"}}}]
    q = _quadro_com(base, atribs, _FUNCS_BR20)
    carlos = next(t for t in q["disciplinas"]["Mecanica"]["tecnicos"] if t["funcionario_id"] == "c1")
    cards = carlos["dias"][0]
    assert [c["ordem"] for c in cards] == ["MEC1"]          # NÃO sumiu (era o bug)
    assert cards[0]["_entregue"] is True                    # encerrada = terminal "feito"
    assert cards[0]["_status_usuario_label"] == "Encerrada" # pill = status do usuário
    assert cards[0]["realizado_min"] == 110
    assert round(cards[0]["aderencia"], 3) == 0.917
    assert cards[0]["_pendente"] is False


def test_montar_quadro_fechada_naoclassificada_cai_no_quadro_do_tecnico():
    # B29: ordem fechada cuja classificação se perdeu (NaoClassificado) mas foi atribuída a um
    # técnico da Mecânica → cai no quadro do TÉCNICO (não some, não vira pendente de classificação).
    base = {"ordens": {}, "coletado_em": None}
    atribs = [{"_id": "x1", "ordem": "NC1", "funcionario_id": "c1", "dia": 0, "parcela_min": None,
               "entrega": {"status_saida": "encerrada", "status_usuario": "CERR",
                           "planejado_min": 60, "realizado_min": 60, "aderencia": 1.0, "superado": False,
                           "cabecalho": {"disciplina": "NaoClassificado", "categoria": "Corretiva",
                                         "local_instalacao": "BR02-0801", "centro_operacao_0010": "Z02"}}}]
    funcs_mec = [{"_id": "c1", "nome": "Carlos", "turno_padrao": "B", "ativo": True,
                  "disciplinas": ["Mecanica"]}]   # técnico só da Mecânica → fallback determinístico
    q = _quadro_com(base, atribs, funcs_mec)
    carlos = next(t for t in q["disciplinas"]["Mecanica"]["tecnicos"] if t["funcionario_id"] == "c1")
    cards = carlos["dias"][0]
    assert [c["ordem"] for c in cards] == ["NC1"]        # posicionado pelo quadro do técnico
    assert cards[0]["categoria"] == "Corretiva"          # cabeçalho congelado exposto (B29)
    assert cards[0]["_entregue"] is True


def test_card_de_entrega_reresolve_linha_quando_congelada_vazia():
    # Card congelado guardou o TPLNR mas NÃO a linha_nome (daemon antigo). _card_de_entrega
    # re-resolve a Linha ao vivo pela árvore oficial. Ex.: RECOLHEDOR (BR02-0901-0200) → LCL 8MM.
    a = {"_id": "x1", "ordem": "5018912", "funcionario_id": "c1", "dia": 1, "disciplina": "Mecanica",
         "entrega": {"status_saida": "encerrada", "status_usuario": "CERR", "superado": False,
                     "planejado_min": 120, "realizado_min": 100, "aderencia": 0.83,
                     "cabecalho": {"disciplina": "Mecanica", "descricao": "RECOLHEDOR DE RECORTES",
                                   "local_instalacao": "BR02-0901-0200", "linha_nome": None}}}
    linha_node = {"id": "BR02-0901", "descricao": "LINHA DE CORTE LONGITUDINAL 8MM"}
    with patch.object(hh_data.bd, "resolver_linha", return_value=linha_node) as mock_rl:
        card = hh_data._card_de_entrega(a)
    mock_rl.assert_called_once_with("BR02-0901-0200")
    assert card["linha_nome"] == "LINHA DE CORTE LONGITUDINAL 8MM"
    assert card["_linha_id"] == "BR02-0901"


def test_card_de_entrega_preserva_linha_congelada_quando_presente():
    # Se o snapshot JÁ tem linha_nome, não re-resolve (respeita o congelado).
    a = {"_id": "x2", "ordem": "5000001", "funcionario_id": "c1", "dia": 0, "disciplina": "Mecanica",
         "entrega": {"status_saida": "encerrada", "status_usuario": "CERR", "superado": False,
                     "cabecalho": {"disciplina": "Mecanica", "descricao": "x",
                                   "local_instalacao": "BR02-0700-0200", "linha_nome": "LINHA PRENSA 01",
                                   "_linha_id": "BR02-0700"}}}
    with patch.object(hh_data.bd, "resolver_linha") as mock_rl:
        card = hh_data._card_de_entrega(a)
    mock_rl.assert_not_called()
    assert card["linha_nome"] == "LINHA PRENSA 01"


def test_montar_quadro_sumida_sem_entrega_fica_aguardando():
    # Ordem atribuída, ausente do universo, ainda SEM snapshot (daemon hh_entregas não rodou):
    # placeholder "aguardando fechamento" — não some.
    base = {"ordens": {}, "coletado_em": None}
    atribs = [{"_id": "x1", "ordem": "MEC1", "funcionario_id": "c1", "dia": 0,
               "parcela_min": None, "disciplina": "Mecanica"}]   # sem `entrega`
    q = _quadro_com(base, atribs, _FUNCS_BR20)
    carlos = next(t for t in q["disciplinas"]["Mecanica"]["tecnicos"] if t["funcionario_id"] == "c1")
    cards = carlos["dias"][0]
    assert [c["ordem"] for c in cards] == ["MEC1"]
    assert cards[0]["_aguardando_fechamento"] is True
    assert cards[0].get("_status_saida") is None


def test_montar_quadro_entrega_superada_vira_placeholder():
    # SP-09.6f: snapshot superado (ordem reaberta) + ausente do backlog agora → placeholder.
    base = {"ordens": {}, "coletado_em": None}
    atribs = [{"_id": "x1", "ordem": "MEC1", "funcionario_id": "c1", "dia": 0,
               "parcela_min": None, "disciplina": "Mecanica",
               "entrega": {"status_saida": "concluida", "planejado_min": 120,
                           "realizado_min": 110, "superado": True}}]
    q = _quadro_com(base, atribs, _FUNCS_BR20)
    carlos = next(t for t in q["disciplinas"]["Mecanica"]["tecnicos"] if t["funcionario_id"] == "c1")
    assert carlos["dias"][0][0]["_aguardando_fechamento"] is True


def test_montar_quadro_entrega_cancelada_nao_conta_entrega():
    # Saída cancelada (USTXT CANC) exibe o status do usuário "Cancelada" e NÃO é entrega cumprida.
    base = {"ordens": {}, "coletado_em": None}
    atribs = [{"_id": "x1", "ordem": "MEC1", "funcionario_id": "c1", "dia": 0,
               "parcela_min": None, "disciplina": "Mecanica",
               "entrega": {"status_saida": "cancelada", "status_usuario": "CANC",
                           "planejado_min": 120, "realizado_min": 0, "aderencia": None,
                           "superado": False, "cabecalho": {"disciplina": "Mecanica"}}}]
    q = _quadro_com(base, atribs, _FUNCS_BR20)
    carlos = next(t for t in q["disciplinas"]["Mecanica"]["tecnicos"] if t["funcionario_id"] == "c1")
    card = carlos["dias"][0][0]
    assert card["_status_usuario_label"] == "Cancelada"
    assert card["_entregue"] is False


def test_montar_quadro_ordem_viva_atribuida_inalterada():
    # QA-B25.5: ordem atribuída AINDA aberta renderiza pelo caminho vivo (sem snapshot).
    base = {"ordens": {"MEC1": {"ordem": "MEC1", "disciplina": "Mecanica", "planejado_min": 120,
                                "realizado_min": 60, "data_criacao": None}}, "coletado_em": None}
    atribs = [{"_id": "x1", "ordem": "MEC1", "funcionario_id": "c1", "dia": 0,
               "parcela_min": None, "disciplina": "Mecanica"}]
    q = _quadro_com(base, atribs, _FUNCS_BR20)
    carlos = next(t for t in q["disciplinas"]["Mecanica"]["tecnicos"] if t["funcionario_id"] == "c1")
    card = carlos["dias"][0][0]
    assert card["ordem"] == "MEC1"
    assert "_entregue" not in card and "_aguardando_fechamento" not in card
    assert card["realizado_min"] == 60


def test_card_de_entrega_cancelada_legado_sem_ustxt():
    # retrocompat: snapshot ANTIGO (aplicar_faltantes) tem status_saida=cancelada mas SEM
    # status_usuario, e detectar não reprocessa terminal → o pill deriva "Cancelada" do status_saida
    # (não pode cair em "saiu do backlog", que foi o bug reportado 2026-07-15).
    card = hh_data._card_de_entrega({"ordem": "O1", "disciplina": "Mecanica",
        "entrega": {"status_saida": "cancelada", "superado": False, "cabecalho": {}}})
    assert card["_status_usuario_label"] == "Cancelada"
    assert not card.get("_saiu_backlog")
    # legado de sistema (concluida/teco) → "Encerrada" até reprocessar
    old = hh_data._card_de_entrega({"ordem": "O2", "disciplina": "Mecanica",
        "entrega": {"status_saida": "concluida", "superado": False, "cabecalho": {}}})
    assert old["_status_usuario_label"] == "Encerrada"


def test_card_de_entrega_helper_ramos():
    # unit do helper: encerrada (terminal do usuário), sem-entrega, superado
    concl = hh_data._card_de_entrega({"ordem": "O1", "disciplina": "Eletrica",
        "entrega": {"status_saida": "encerrada", "status_usuario": "CERR", "planejado_min": 10,
                    "realizado_min": 9, "aderencia": 0.9, "superado": False,
                    "cabecalho": {"disciplina": "Eletrica"}}})
    assert concl["_entregue"] is True and concl["disciplina"] == "Eletrica" and concl["_restante_min"] == 0
    aguard = hh_data._card_de_entrega({"ordem": "O2", "disciplina": "Mecanica"})
    assert aguard["_aguardando_fechamento"] is True and aguard["disciplina"] == "Mecanica"
    sup = hh_data._card_de_entrega({"ordem": "O3", "disciplina": "Mecanica",
        "entrega": {"status_saida": "encerrada", "superado": True}})
    assert sup["_aguardando_fechamento"] is True


# ---- cadastros de apoio + replanejamento (B6, DS-07/BR-16/17) ------------------------

def test_listar_motivos_default_quando_vazio():
    from unittest.mock import MagicMock
    col = MagicMock()
    cursor = MagicMock(); cursor.sort.return_value = []      # collection vazia
    col.find.return_value = cursor
    with patch.object(hh_data, "get_mongo_connection", return_value=col):
        motivos = hh_data.listar_motivos()
    assert motivos == hh_data.MOTIVOS_DEFAULT
    col.insert_many.assert_called_once()                     # semeou o default

def test_registrar_replanejamento_exige_categoria():
    r = hh_data.registrar_replanejamento("2026-W27", "X", "mover_semana", None, None,
                                         categoria=None, texto=None, por="pcm")
    assert r["ok"] is False and "categoria" in r["motivo"]

def test_registrar_replanejamento_outro_exige_texto():
    with patch.object(hh_data, "get_mongo_connection", return_value=None):
        r = hh_data.registrar_replanejamento("2026-W27", "X", "remover", None, None,
                                             categoria="Outro", texto="  ", por="pcm")
    assert r["ok"] is False and "texto" in r["motivo"]

def test_registrar_replanejamento_ok_grava():
    from unittest.mock import MagicMock
    col = MagicMock()
    with patch.object(hh_data, "get_mongo_connection", return_value=col), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 6, 30)):
        r = hh_data.registrar_replanejamento("2026-W27", "5018863", "trocar_tecnico",
                                             {"func": "c1"}, {"func": "c2"},
                                             categoria="Indisponibilidade do técnico",
                                             texto=None, por="pcm")
    assert r["ok"] is True
    doc = col.insert_one.call_args[0][0]
    assert doc["ordem"] == "5018863" and doc["tipo"] == "trocar_tecnico"
    assert doc["categoria"] == "Indisponibilidade do técnico" and doc["por"] == "pcm"

def test_detalhe_ordem_monta_operacoes_e_header():
    from unittest.mock import MagicMock
    base = {"ordens": {"5018863": {
        "ordem": "5018863", "descricao": "Trocar rolamento", "disciplina": "Eletrica",
        "categoria": "Corretiva", "planejado_min": 120, "realizado_min": 110,
        "aderencia": 110/120, "executores": ["CDAMASIO"], "status_sap": "LIB",
        "data_criacao": None, "data_inicio": None, "linha_nome": "Linha 2", "local_instalacao": "BR02-0700",
    }}}

    def fake_conn(coll=None, silent=True):
        c = MagicMock()
        if coll == hh_data.COLL_PLAN:
            c.find.return_value = [{"operacao": "0010", "planejado_min": 120, "centro_planejado": "Z210"}]
        elif coll == hh_data.COLL_REAL:
            c.find.return_value = [{"operacao": "0010", "realizado_min": 110,
                                    "executores": ["CDAMASIO"], "status_sap": "LIB"}]
        elif coll == hh_data.COLL_STATUS:
            c.find.return_value = []
            c.find_one.return_value = None
        elif coll == hh_data.COLL_REPLAN:
            cur = MagicMock(); cur.sort.return_value = []
            c.find.return_value = cur
        else:  # atribuição
            c.find.return_value = []
        return c

    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "get_mongo_connection", side_effect=fake_conn), \
         patch.object(hh_data, "_coll_atrib", return_value=fake_conn("atrib")), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=[]), \
         patch.object(hh_data, "carry_over", return_value=0), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 6, 30)):
        det = hh_data.detalhe_ordem("5018863")

    assert det["ordem"] == "5018863"
    assert det["header"]["descricao"] == "Trocar rolamento"
    assert det["header"]["disciplina"] == "Eletrica"
    assert det["header"]["pendente"] is True            # status LIB não mapeado como concluída
    assert det["totais"]["planejado_min"] == 120
    assert len(det["operacoes"]) == 1
    op = det["operacoes"][0]
    assert op["operacao"] == "0010" and op["planejado_min"] == 120 and op["realizado_min"] == 110
    assert abs(op["aderencia"] - 110/120) < 1e-9


def test_pendencia_derivada_do_status():
    from unittest.mock import MagicMock
    col = MagicMock()
    # de/para: 'TECO' = concluída, 'LIB' não mapeado
    col.find_one.side_effect = lambda q: ({"codigo_sap": "TECO", "concluida": True}
                                          if q.get("codigo_sap") == "TECO" else None)
    with patch.object(hh_data, "get_mongo_connection", return_value=col):
        assert hh_data.status_eh_concluida("TECO") is True
        assert hh_data.status_eh_concluida("LIB") is False        # sem de/para → não concluída
        assert hh_data.pendencia_derivada({"status_sap": "TECO"}) is False   # concluída → não pendente
        assert hh_data.pendencia_derivada({"status_sap": "LIB"}) is True     # não concluída → pendente


# ---- B18: divisão de ordem + capacidade líquida (SP-04/SP-13) -------------------------

def test_opcoes_parcela_passo_30_e_resto_quebrado():
    # múltiplos de 30 que deixam sobra 0 ou ≥30, mais o restante inteiro (SP-04.6)
    assert hh_data.opcoes_parcela(90) == [30, 60, 90]
    assert hh_data.opcoes_parcela(60) == [30, 60]
    assert hh_data.opcoes_parcela(82) == [30, 82]     # 60 deixaria 22 órfão → fora
    assert hh_data.opcoes_parcela(52) == [52]         # 30 deixaria 22 órfão → só o restante
    assert hh_data.opcoes_parcela(37) == [37]         # 30 deixaria 7 órfão → só o restante
    assert hh_data.opcoes_parcela(17) == [17]         # < 30 → só o restante
    assert hh_data.opcoes_parcela(30) == [30]
    assert hh_data.opcoes_parcela(0) == []
    assert hh_data.opcoes_parcela(-5) == []


def test_restante_ordem_regra_de_ouro_none():
    # None em qualquer parcela = ordem inteira (100%) → restante 0 (retrocompat B18)
    assert hh_data.restante_ordem([{"ordem": "A", "parcela_min": None}], "A", 600) == 0
    # sem atribuição → planejado inteiro
    assert hh_data.restante_ordem([], "A", 600) == 600
    # só numérico → planejado − Σ
    atribs = [{"ordem": "A", "parcela_min": 300}, {"ordem": "A", "parcela_min": 120}]
    assert hh_data.restante_ordem(atribs, "A", 600) == 180
    # mix None + numérico → None manda (0)
    assert hh_data.restante_ordem([{"ordem": "A", "parcela_min": 300},
                                   {"ordem": "A", "parcela_min": None}], "A", 600) == 0
    # nunca negativo
    assert hh_data.restante_ordem([{"ordem": "A", "parcela_min": 700}], "A", 600) == 0


def test_restante_ordem_exclui_proprio_slot():
    # ao reeditar a parcela do slot (c1, dia0), ela não deve descontar de si mesma
    atribs = [{"ordem": "A", "funcionario_id": "c1", "dia": 0, "parcela_min": 300},
              {"ordem": "A", "funcionario_id": "c2", "dia": 1, "parcela_min": 120}]
    # sem excluir: restante = 600−420 = 180
    assert hh_data.restante_ordem(atribs, "A", 600) == 180
    # excluindo (c1,0): restante = 600−120 = 480 (o slot que está sendo reescrito não conta)
    assert hh_data.restante_ordem(atribs, "A", 600, excluir_func_dia=("c1", 0)) == 480


def test_carga_tecnico_dia_soma_parcelas_e_none():
    ordens = {"A": {"planejado_min": 600}, "B": {"planejado_min": 120}}
    atribs = [
        {"ordem": "A", "funcionario_id": "c1", "dia": 0, "parcela_min": 240},  # parcela
        {"ordem": "B", "funcionario_id": "c1", "dia": 0, "parcela_min": None}, # inteira → 120
        {"ordem": "A", "funcionario_id": "c1", "dia": 1, "parcela_min": 360},  # outro dia
        {"ordem": "A", "funcionario_id": "c2", "dia": 0, "parcela_min": 100},  # outro técnico
    ]
    assert hh_data.carga_tecnico_dia(atribs, ordens, "c1", 0) == 360   # 240 + 120
    assert hh_data.carga_tecnico_dia(atribs, ordens, "c1", 1) == 360
    assert hh_data.carga_tecnico_dia(atribs, ordens, "c9", 0) == 0


def test_disponivel_map_precedencia():
    # override do técnico > config do turno > default
    cfg = {"B": 300}
    assert hh_data.jornada_min({"turno_padrao": "B", "jornada_min": 200}, cfg) == 200  # override
    assert hh_data.jornada_min({"turno_padrao": "B"}, cfg) == 300                       # config
    assert hh_data.jornada_min({"turno_padrao": "B"}, None) == 480                      # default 8h


def test_carregar_config_capacidade_defaults():
    # sem doc no banco → defaults (retrocompat, sistema nunca fica sem capacidade)
    with patch.object(hh_data, "get_mongo_connection", return_value=None):
        cfg = hh_data.carregar_config_capacidade()
    assert cfg["disponivel_min"] == {"A": 360, "B": 480, "C": 480, "ADM": 480}
    assert cfg["meta_pct"] == 0.70


def test_carregar_config_capacidade_merge():
    class _C:
        def find_one(self, *a, **k):
            return {"_id": "capacidade", "disponivel_min": {"b": 300}, "meta_pct": 0.6}
    with patch.object(hh_data, "get_mongo_connection", return_value=_C()):
        cfg = hh_data.carregar_config_capacidade()
    assert cfg["disponivel_min"]["B"] == 300     # sobrescreve (upper-case)
    assert cfg["disponivel_min"]["C"] == 480     # não informado → default
    assert cfg["meta_pct"] == 0.6


def test_atribuir_trava_no_planejado():
    ordens_base = {"ordens": {"A": {"planejado_min": 600}}}

    class _C:
        def __init__(self):
            self.upserts = 0
        def update_one(self, *a, **k):
            self.upserts += 1
    coll = _C()
    # já há 480 atribuídos → restante 120; tentar 240 deve REJEITAR
    atribs = [{"ordem": "A", "funcionario_id": "c1", "dia": 0, "parcela_min": 480}]
    with patch.object(hh_data, "_coll_atrib", return_value=coll), \
         patch.object(hh_data, "montar_ordens", return_value=ordens_base), \
         patch.object(hh_data, "listar_atribuicoes", return_value=atribs):
        r = hh_data.atribuir("2026-W27", "A", "c2", 1, 240, por="teste")
        assert r["ok"] is False and "excede" in r["motivo"]
        assert coll.upserts == 0
        # 120 (== restante) deve ACEITAR
        r2 = hh_data.atribuir("2026-W27", "A", "c2", 1, 120, por="teste")
        assert r2["ok"] is True
        assert coll.upserts == 1


def test_atribuir_ordem_inteira_sempre_aceita():
    # parcela_min=None (ordem inteira) nunca passa pela trava (retrocompat)
    class _C:
        def __init__(self): self.upserts = 0
        def update_one(self, *a, **k): self.upserts += 1
    coll = _C()
    with patch.object(hh_data, "_coll_atrib", return_value=coll), \
         patch.object(hh_data, "montar_ordens", return_value={"ordens": {}}):
        r = hh_data.atribuir("2026-W27", "A", "c1", 0, None, por="teste")
    assert r["ok"] is True and coll.upserts == 1


def test_montar_quadro_retrocompat_none_nao_volta_pra_fila():
    # RETROCOMPAT (gate B18): ordem já atribuída como inteira (parcela_min=None) NÃO reaparece
    # na fila; ordem parcial (restante > 0) FICA na fila com _restante_min.
    base = {"ordens": {
        "INTEIRA": {"ordem": "INTEIRA", "disciplina": "Mecanica", "planejado_min": 600},
        "PARCIAL": {"ordem": "PARCIAL", "disciplina": "Mecanica", "planejado_min": 600},
        "SEMPLAN": {"ordem": "SEMPLAN", "disciplina": "Mecanica", "planejado_min": 0},
    }}
    funcionarios = [{"_id": "c1", "turno_padrao": "B", "ativo": True, "nome": "Carlos"}]
    atribs = [
        {"_id": "a1", "ordem": "INTEIRA", "funcionario_id": "c1", "dia": 0, "parcela_min": None},
        {"_id": "a2", "ordem": "PARCIAL", "funcionario_id": "c1", "dia": 0, "parcela_min": 240},
    ]
    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "listar_atribuicoes", return_value=atribs), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=funcionarios), \
         patch.object(hh_data, "_assignments_por_func", return_value={}), \
         patch.object(hh_data, "carregar_config_capacidade",
                      return_value={"disponivel_min": hh_data.DISPONIVEL_DEFAULT, "meta_pct": 0.7}), \
         patch.object(hh_data, "carry_over", return_value=0), \
         patch.object(hh_data, "_status_concluidos", return_value=set()), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 6, 30)):
        q = hh_data.montar_quadro("2026-W27")
    fila = [o["ordem"] for o in q["a_planejar"]["Mecanica"]]
    assert "INTEIRA" not in fila           # 100% alocada → fora da fila (retrocompat)
    assert "PARCIAL" in fila               # restante 360 → segue na fila
    assert "SEMPLAN" in fila               # sem atribuição, planejado 0 → segue (não some)
    parcial = next(o for o in q["a_planejar"]["Mecanica"] if o["ordem"] == "PARCIAL")
    assert parcial["_restante_min"] == 360


def test_carry_over_map_equivale_ao_por_ordem():
    """Perf B24: o map em 1 query deve dar o MESMO carry-over que a versão por-ordem."""
    docs = [
        {"ordem": "A", "semana": "2026-W25"},
        {"ordem": "A", "semana": "2026-W26"},
        {"ordem": "A", "semana": "2026-W28"},   # >= semana-alvo: não conta
        {"ordem": "B", "semana": "2026-W26"},
        {"ordem": "B", "semana": "2026-W26"},   # duplicata na mesma semana → distinct
    ]
    class _C:
        def find(self, filtro, proj=None):
            lt = filtro["semana"]["$lt"]
            return [d for d in docs if d["semana"] < lt]
        def distinct(self, campo, filtro):
            o = str(filtro["ordem"])
            return list({d["semana"] for d in docs if str(d["ordem"]) == o})
    with patch.object(hh_data, "_coll_atrib", return_value=_C()):
        sem = "2026-W28"
        mp = hh_data.carry_over_map(sem)
        for o in ("A", "B"):
            assert mp.get(o, 0) == hh_data.carry_over(o, sem)   # equivalência
        assert mp["A"] == 2   # W25, W26 (< W28)
        assert mp["B"] == 1   # W26 distinct


# ---- cabeçalho-indicador por dia (B44) -----------------------------------------------

def test_planejado_por_dia_soma_parcelas_e_fallback():
    # parcela_min quando presente; senão o planejado da ordem. Soma por dia, qualquer disciplina.
    atribs = [
        {"ordem": "A", "dia": 0, "parcela_min": 120},
        {"ordem": "B", "dia": 0, "parcela_min": None},           # ordem inteira → planejado
        {"ordem": "C", "dia": 1, "parcela_min": 60},
        {"ordem": "Z", "dia": 5, "parcela_min": None},           # ordem ausente → 0
    ]
    ordens = {"A": {"planejado_min": 999}, "B": {"planejado_min": 200}, "C": {"planejado_min": 999}}
    r = hh_data.planejado_por_dia(atribs, ordens)
    assert r[0] == 320          # 120 (parcela) + 200 (planejado da B)
    assert r[1] == 60
    assert r[5] == 0            # ordem Z fora do universo
    assert r[2] == 0 and r[6] == 0

def test_disponivel_por_dia_conta_tecnico_uma_vez():
    # técnico nas DUAS disciplinas não pode contar 2× (ao contrário de somar capacidades por disc)
    semana = "2026-W27"     # segunda = 29/06
    funcs = [
        {"_id": "c1", "turno_padrao": "B", "ativo": True, "disciplinas": ["Mecanica", "Eletrica"]},
        {"_id": "c2", "turno_padrao": "B", "ativo": True},       # mesmo turno → mesma jornada
        {"_id": "x", "turno_padrao": "B", "ativo": False},       # inativo não conta
    ]
    # c2 indisponível na segunda (overlap Gantt)
    assignments = {"c2": [{"data_hora_entrada": datetime(2026, 6, 29),
                           "data_hora_saida": datetime(2026, 6, 30)}]}
    jm = hh_data.jornada_min(funcs[0], None)                     # jornada líquida do turno B
    r = hh_data.disponivel_por_dia(funcs, assignments, None, semana)
    assert r[0] == jm           # só c1 — c1 conta 1× (nas 2 disc), c2 indisponível, x inativo
    assert r[1] == 2 * jm       # terça: c1 + c2 disponíveis

def test_resumo_dias_cabecalho_delta_e_zona():
    planejado = {0: 96 * 60 // 60, 1: 0}     # usa minutos; simplifico com valores diretos
    planejado = {0: 5760, 1: 0}              # 96h na seg, 0 na ter
    disponivel = {0: 7200, 1: 7200}          # 120h disponível
    ant = {0: 4800, 1: 0}                    # semana passada: 80h na seg, 0 na ter
    r = hh_data.resumo_dias_cabecalho(planejado, disponivel, ant)
    assert abs(r[0]["pct_programado"] - 5760 / 7200) < 1e-9      # 80% ocupação
    assert abs(r[0]["delta_pct"] - (5760 - 4800) / 4800) < 1e-9  # +20% vs semana passada
    assert r[1]["delta_pct"] is None         # semana passada 0 → sem base (não divide por zero)
    assert r[1]["pct_programado"] == 0       # 0 planejado / 120 disp
    assert r[0]["programado_ant"] == 4800

def test_resumo_dias_cabecalho_disponivel_zero():
    r = hh_data.resumo_dias_cabecalho({0: 100}, {0: 0}, {0: 0})
    assert r[0]["disponivel"] is None        # 0 disponível → None (não força barra)
    assert r[0]["pct_programado"] is None


# ---- mão de obra da semana p/ relatório diário (KPIReport-v2 BR-11/12/13) ------------

def _resumo(disp_min, plan_min):
    """Helper: monta o dict resumo (dia→{disponivel,programado,pct}) p/ 5 dias iguais."""
    return {i: {"disponivel": disp_min, "programado": plan_min,
                "pct_programado": (plan_min / disp_min) if disp_min else None} for i in range(5)}


def test_dias_mao_de_obra_corte_de_borda():
    """Executado só aparece em dia ≤ dia avaliado (ref_date) e com apontamento; senão None."""
    datas = hh_data.datas_da_semana("2026-W30")            # seg..dom
    ref_date = datas[3].date()                             # quinta = dia avaliado (DatePicker)
    exec_min = {0: 6600, 1: 9300, 2: 8880, 3: 8400, 4: 5000}
    dias = hh_data._dias_mao_de_obra(_resumo(10080, 7200), exec_min, datas, ref_date)
    assert len(dias) == 5                                  # só seg..sex
    # seg: ≤ ref_date, com apontamento → executado 110h, aderência 6600/7200
    assert dias[0]["executado_h"] == 110.0
    assert round(dias[0]["aderencia"], 3) == round(6600 / 7200, 3)
    assert round(dias[0]["pct_plan"], 3) == round(7200 / 10080, 3)
    # qui: == ref_date (dia avaliado, inclusive) → conta
    assert dias[3]["executado_h"] == 140.0
    # sex: > ref_date (posterior ao dia avaliado) → None (nunca 0)
    assert dias[4]["executado_h"] is None
    assert dias[4]["aderencia"] is None


def test_dias_mao_de_obra_sem_apontamento_e_futuro():
    """Dia sem apontamento (exec 0) e dia futuro → executado None (nunca 0)."""
    datas = hh_data.datas_da_semana("2026-W30")
    ref_date = datas[4].date()                             # sexta = dia avaliado
    exec_min = {0: 6000, 1: 0, 2: 7000, 3: 6000, 4: 6000}  # terça sem apontamento
    dias = hh_data._dias_mao_de_obra(_resumo(10080, 7200), exec_min, datas, ref_date)
    assert dias[1]["executado_h"] is None                  # terça: sem apontamento → None, não 0
    assert dias[0]["executado_h"] == 100.0


def test_dias_mao_de_obra_aderencia_none_sem_planejado():
    """Planejado 0 → aderência None (evita divisão por zero)."""
    datas = hh_data.datas_da_semana("2026-W30")
    dias = hh_data._dias_mao_de_obra(_resumo(10080, 0), {i: 3000 for i in range(5)},
                                     datas, datas[4].date())
    assert dias[0]["executado_h"] == 50.0
    assert dias[0]["aderencia"] is None                    # exec÷plan indefinida sem plano
    assert dias[0]["pct_plan"] == 0.0                      # planejou 0% do disponível (fato válido)


def test_semana_mao_de_obra_integra_semana_e_executado():
    """Fiação: semana de ref_day + executado somado do realizado_por_dia do snapshot."""
    from unittest.mock import patch
    ref_day = datetime(2026, 7, 23)                        # quinta
    semana = hh_data.iso_semana(ref_day)                   # "2026-W30"
    datas = hh_data.datas_da_semana(semana)
    d_seg = datas[0].strftime("%Y-%m-%d")
    d_ter = datas[1].strftime("%Y-%m-%d")
    # dois docs de realizado com quebra por dia; um deles multi-dia
    snap = {"docs": [
        {"ordem": "1", "realizado_por_dia": {d_seg: 3000}},
        {"ordem": "2", "realizado_por_dia": {d_seg: 3600, d_ter: 9300}},
    ]}
    plan = {i: 7200 for i in range(7)}
    disp = {i: 10080 for i in range(7)}
    with patch.object(hh_data, "montar_ordens", return_value={"ordens": {}}), \
         patch.object(hh_data, "listar_atribuicoes", return_value=[]), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=[]), \
         patch.object(hh_data, "_assignments_por_func", return_value={}), \
         patch.object(hh_data, "carregar_config_capacidade",
                      return_value={"disponivel_min": {}, "meta_pct": 70}), \
         patch.object(hh_data, "planejado_por_dia", return_value=plan), \
         patch.object(hh_data, "disponivel_por_dia", return_value=disp), \
         patch.object(hh_data, "_carregar_snapshot", return_value=snap), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 8, 1)):
        res = hh_data.semana_mao_de_obra(ref_day)
    assert res["semana"] == semana
    assert res["sem_dados"] is False
    assert len(res["dias"]) == 5
    # seg = 3000+3600 = 6600 min → 110h ; ter = 9300 → 155h
    assert res["dias"][0]["executado_h"] == 110.0
    assert res["dias"][1]["executado_h"] == 155.0


def test_semana_mao_de_obra_sem_dados_se_mongo_cair():
    from unittest.mock import patch
    with patch.object(hh_data, "montar_ordens", return_value=None):
        res = hh_data.semana_mao_de_obra(datetime(2026, 7, 23))
    assert res["sem_dados"] is True
    assert res["dias"] == []


# ---- B45: planejado das fechadas não evapora (overlay do snapshot `entrega`) ----------

def test_overlay_entrega_recupera_planejado_de_ordem_fechada():
    # ordem fechada saiu do backlog (não está em `ordens`), mas a atribuição tem o snapshot
    ordens = {"ABERTA": {"planejado_min": 100, "realizado_min": 0}}
    atribs = [
        {"ordem": "ABERTA", "dia": 0, "parcela_min": None},
        {"ordem": "FECHADA", "dia": 0, "parcela_min": None,
         "entrega": {"planejado_min": 240, "realizado_min": 257}},
    ]
    cap = hh_data.overlay_entrega(ordens, atribs)
    assert cap["FECHADA"]["planejado_min"] == 240      # recuperado do snapshot
    assert cap["FECHADA"]["realizado_min"] == 257
    assert cap["ABERTA"]["planejado_min"] == 100       # aberta intacta
    # não muta o original (o laço dos cards depende de `ordens.get('FECHADA') is None`)
    assert "FECHADA" not in ordens

def test_overlay_entrega_ignora_snapshot_sem_planejado():
    ordens = {}
    atribs = [{"ordem": "X", "entrega": {"realizado_min": 50}},   # sem planejado_min → ignora
              {"ordem": "Y"}]                                       # sem entrega → ignora
    cap = hh_data.overlay_entrega(ordens, atribs)
    assert cap == {}

def test_planejado_por_dia_com_overlay_conta_ordem_fechada():
    # o bug: sem overlay, ordem fechada some do planejado; com overlay, volta
    ordens = {}   # backlog vivo não tem a ordem (fechou)
    atribs = [{"ordem": "5019093", "dia": 0, "parcela_min": None,
               "entrega": {"planejado_min": 240, "realizado_min": 257}}]
    sem_overlay = hh_data.planejado_por_dia(atribs, ordens)
    com_overlay = hh_data.planejado_por_dia(atribs, hh_data.overlay_entrega(ordens, atribs))
    assert sem_overlay[0] == 0        # evaporou (comportamento antigo)
    assert com_overlay[0] == 240      # recuperado (B45)

def test_disponivel_por_dia_exclui_fim_de_semana():
    semana = "2026-W27"
    funcs = [{"_id": "c1", "turno_padrao": "B", "ativo": True}]
    r = hh_data.disponivel_por_dia(funcs, {}, None, semana)
    jm = hh_data.jornada_min(funcs[0], None)
    assert r[0] == jm and r[4] == jm      # seg e sex contam
    assert r[5] == 0 and r[6] == 0        # sábado e domingo fora (BR-19)

def _ops_de(det):
    return {o["operacao"]: o for o in det["operacoes"]}

def test_rateio_realizado_proporcional_ao_planejado():
    """B54: o realizado é rateado na proporção do plano de cada operação, então toda operação
    exibe a aderência da ORDEM — o único número medido. Caso real da ordem 5015342: 12 operações,
    255 min de plano (uma de 200), 146 min apontados na 0010."""
    plan = {"0010": 5, "0020": 200}
    plan.update({f"00{n}": 5 for n in range(30, 130, 10)})
    real_total = 146
    plan_total = sum(plan.values())
    for vornr, p in plan.items():
        rateado = real_total * p / plan_total
        assert abs(rateado / p - real_total / plan_total) < 1e-9   # mesma aderência em todas

def test_rateio_nao_estoura_com_operacao_grande():
    """Contraprova do rateio em partes iguais, que foi descartado: 146/12 = 12,2 min em cada
    operação daria 243% nas de 5 min e 6% na de 200 min."""
    real_total, n = 146, 12
    igual = real_total / n
    assert igual / 5 > 2.4          # estouraria
    assert igual / 200 < 0.07       # e sumiria

def test_aderencia_recomposta_usa_o_total_das_operacoes(monkeypatch):
    """B54 no modal de detalhe: 100 min apontados sobre 15 min congelados davam 667%; sobre as 8
    operações reais (155 min) dão 65%. Caso real da ordem 5020001."""
    monkeypatch.setattr(hh_data, "plan_iw37_por_ordem", lambda silent=True: {"5020001": 155})
    ent = {"planejado_min": 15, "realizado_min": 100, "aderencia": 100 / 15}
    assert abs(hh_data._aderencia_recomposta(ent, "5020001") - 100 / 155) < 1e-9

def test_aderencia_recomposta_sem_iw37_preserva_congelada(monkeypatch):
    """Sem a ordem no IW37, o valor congelado é mantido — nunca piora o que já existe."""
    monkeypatch.setattr(hh_data, "plan_iw37_por_ordem", lambda silent=True: {})
    ent = {"planejado_min": 60, "realizado_min": 30, "aderencia": 0.5}
    assert abs(hh_data._aderencia_recomposta(ent, "999") - 0.5) < 1e-9

def test_planejado_de_entrega_recompoe_pelo_iw37():
    """B54: congelado veio do IW47 (1 operação apontada); o IW37 tem as 5 → vale o total."""
    ent = {"planejado_min": 30}
    assert hh_data.planejado_de_entrega(ent, "500123", {"500123": 150}) == 150

def test_planejado_de_entrega_nunca_rebaixa():
    """Se o IW37 vier menor (ou não vier), o congelado é preservado — o compromisso não encolhe."""
    ent = {"planejado_min": 240}
    assert hh_data.planejado_de_entrega(ent, "500123", {"500123": 60}) == 240
    assert hh_data.planejado_de_entrega(ent, "500123", {}) == 240
    assert hh_data.planejado_de_entrega(ent, "500123", None) == 240

def test_planejado_de_entrega_sem_congelado():
    """Snapshot com planejado zerado ainda recompõe pelo IW37 (era o caso das ordens com 0)."""
    assert hh_data.planejado_de_entrega({"planejado_min": 0}, "X", {"X": 120}) == 120

def test_overlay_entrega_usa_total_das_operacoes():
    """A ordem fechada entra na capacidade com o total do IW37, não com a operação apontada."""
    ordens = {}
    atribs = [{"ordem": "500123", "entrega": {"planejado_min": 30, "realizado_min": 145}}]
    r = hh_data.overlay_entrega(ordens, atribs, {"500123": 150})
    assert r["500123"]["planejado_min"] == 150
    assert r["500123"]["realizado_min"] == 145
    # sem o mapa do IW37 o comportamento antigo é preservado (retrocompat)
    assert hh_data.overlay_entrega(ordens, atribs)["500123"]["planejado_min"] == 30

def test_card_de_entrega_recalcula_aderencia_com_planejado_corrigido():
    """Aderência do card sai de 3.700% (145/30 sobre uma operação) para 97% (145/150)."""
    a = {"ordem": "500123", "disciplina": "Mecanica",
         "entrega": {"planejado_min": 30, "realizado_min": 145, "aderencia": 145 / 30,
                     "status_saida": "encerrada", "status_usuario": "CERR"}}
    card = hh_data._card_de_entrega(a, None, {"500123": 150})
    assert card["planejado_min"] == 150
    assert card["realizado_min"] == 145
    assert abs(card["aderencia"] - 145 / 150) < 1e-9

def test_disponivel_por_dia_fim_de_semana_com_servico_ganha_denominador():
    """B53: sáb/dom com atribuição contam a jornada de QUEM ESTÁ LANÇADO no dia (hora extra),
    não a fábrica inteira. Dia útil e fim de semana vazio ficam como estavam."""
    semana = "2026-W27"
    funcs = [
        {"_id": "c1", "turno_padrao": "B", "ativo": True},
        {"_id": "c2", "turno_padrao": "B", "ativo": True},
        {"_id": "c3", "turno_padrao": "B", "ativo": True},
    ]
    jm = hh_data.jornada_min(funcs[0], None)
    atribs = [{"ordem": "A", "dia": 5, "funcionario_id": "c1", "parcela_min": 60}]
    r = hh_data.disponivel_por_dia(funcs, {}, None, semana, atribs)
    assert r[5] == jm                # sábado: só c1, que é quem está lançado
    assert r[6] == 0                 # domingo sem nada marcado → segue sem denominador
    assert r[0] == 3 * jm            # dia útil inalterado: a fábrica toda

def test_disponivel_por_dia_fim_de_semana_soma_so_os_lancados():
    """Dois técnicos lançados no domingo somam; o terceiro, que não está escalado, fica fora."""
    semana = "2026-W27"
    funcs = [{"_id": f"c{i}", "turno_padrao": "B", "ativo": True} for i in (1, 2, 3)]
    jm = hh_data.jornada_min(funcs[0], None)
    atribs = [
        {"ordem": "A", "dia": 6, "funcionario_id": "c1", "parcela_min": 60},
        {"ordem": "B", "dia": 6, "funcionario_id": "c2", "parcela_min": None},
        {"ordem": "C", "dia": 6, "funcionario_id": "c1", "parcela_min": 30},   # mesmo técnico 2×
    ]
    r = hh_data.disponivel_por_dia(funcs, {}, None, semana, atribs)
    assert r[6] == 2 * jm            # c1 conta UMA vez, c2 conta; c3 fora

def test_disponivel_por_dia_fim_de_semana_conta_adm_lancado():
    """B53 regra 4: ADM fica fora do dia útil (não pega ordem), mas conta no fim de semana quando
    foi escalado — senão o dia voltaria ao traço que o bloco veio corrigir."""
    semana = "2026-W27"
    funcs = [{"_id": "adm1", "turno_padrao": "ADM", "ativo": True}]
    jm = hh_data.jornada_min(funcs[0], None)
    atribs = [{"ordem": "A", "dia": 5, "funcionario_id": "adm1", "parcela_min": 60}]
    r = hh_data.disponivel_por_dia(funcs, {}, None, semana, atribs)
    assert r[0] == 0                 # dia útil: ADM segue fora (BR-20)
    assert r[5] == jm                # sábado: escalado → conta

def test_disponivel_por_dia_fim_de_semana_degrada_sem_tecnico_valido():
    """B53 regra 5: lançado mas inativo/de folga → disponível 0, tela mostra '—' como hoje."""
    semana = "2026-W27"     # segunda = 29/06 → sábado = 04/07
    funcs = [
        {"_id": "off", "turno_padrao": "B", "ativo": False},
        {"_id": "ferias", "turno_padrao": "B", "ativo": True},
    ]
    assignments = {"ferias": [{"data_hora_entrada": datetime(2026, 7, 4),
                               "data_hora_saida": datetime(2026, 7, 5)}]}
    atribs = [{"ordem": "A", "dia": 5, "funcionario_id": "off", "parcela_min": 60},
              {"ordem": "B", "dia": 5, "funcionario_id": "ferias", "parcela_min": 60}]
    r = hh_data.disponivel_por_dia(funcs, assignments, None, semana, atribs)
    assert r[5] == 0

def test_disponivel_por_dia_sem_atribuicoes_mantem_comportamento_antigo():
    """Retrocompat: chamada sem o parâmetro novo se comporta exatamente como antes do B53."""
    semana = "2026-W27"
    funcs = [{"_id": "c1", "turno_padrao": "B", "ativo": True}]
    assert hh_data.disponivel_por_dia(funcs, {}, None, semana) == \
           hh_data.disponivel_por_dia(funcs, {}, None, semana, None)

def test_disponivel_por_dia_exclui_turno_adm():
    semana = "2026-W27"
    funcs = [
        {"_id": "b1", "turno_padrao": "B", "ativo": True},
        {"_id": "adm1", "turno_padrao": "ADM", "ativo": True},   # não é capacidade de execução
    ]
    r = hh_data.disponivel_por_dia(funcs, {}, None, semana)
    jm_b = hh_data.jornada_min(funcs[0], None)
    assert r[0] == jm_b                    # só o turno B; ADM fora (BR-20)


# ---- B48: card fantasma de 0h ---------------------------------------------------------

def test_atribuir_rejeita_parcela_zero():
    from unittest.mock import MagicMock
    fake = MagicMock()
    with patch.object(hh_data, "_coll_atrib", return_value=fake):
        r = hh_data.atribuir("2026-W27", "5019093", "c1", 0, parcela_min=0, por="tester")
    assert r["ok"] is False and "zero" in r["motivo"].lower()
    fake.update_one.assert_not_called()          # não gravou o fantasma

def test_montar_quadro_ignora_card_fantasma_zero():
    # ordem cheia: parcela=0 num técnico (fantasma) NÃO renderiza e a ordem volta pra fila
    semana = "2026-W27"
    base = {"ordens": {
        "MEC1": {"ordem": "MEC1", "disciplina": "Mecanica", "planejado_min": 120,
                 "realizado_min": 0, "data_criacao": None},
    }, "coletado_em": None}
    funcionarios = [{"_id": "c1", "nome": "Carlos", "turno_padrao": "B", "ativo": True}]
    atribs = [{"_id": "g1", "ordem": "MEC1", "funcionario_id": "c1", "dia": 0, "parcela_min": 0}]
    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "listar_atribuicoes", return_value=atribs), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=funcionarios), \
         patch.object(hh_data, "_assignments_por_func", return_value={}), \
         patch.object(hh_data, "carry_over", return_value=0), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 6, 30)):
        q = hh_data.montar_quadro(semana)
    carlos = next(t for t in q["disciplinas"]["Mecanica"]["tecnicos"] if t["funcionario_id"] == "c1")
    assert carlos["dias"][0] == []                                  # sem card fantasma
    assert [o["ordem"] for o in q["a_planejar"]["Mecanica"]] == ["MEC1"]   # volta pra fila (restante 120)


# ---- B48b: repartir ordem cheia (mover / dividir) -------------------------------------

def _rep(origens, planejado=120):
    """Helper: roda repartir_ordem com _coll_atrib/montar_ordens/listar_atribuicoes/atribuir mockados.
    Retorna (resultado, coll_mock, atribuir_mock)."""
    from unittest.mock import MagicMock
    coll = MagicMock()
    base = {"ordens": {"O1": {"planejado_min": planejado}}}
    def run(para):
        with patch.object(hh_data, "_coll_atrib", return_value=coll), \
             patch.object(hh_data, "montar_ordens", return_value=base), \
             patch.object(hh_data, "listar_atribuicoes", return_value=origens), \
             patch.object(hh_data, "atribuir", return_value={"ok": True}) as m_atrib, \
             patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 6, 30)):
            r = hh_data.repartir_ordem("2026-W27", "O1", "bob", 1, para, "Mecanica", "t")
        return r, coll, m_atrib
    return run

def test_repartir_mover_tudo_remove_origem_e_grava_inteira():
    origens = [{"_id": "a1", "ordem": "O1", "funcionario_id": "ana", "dia": 0, "parcela_min": None}]
    r, coll, m_atrib = _rep(origens)(120)      # mover tudo (== planejado)
    assert r["ok"]
    coll.delete_one.assert_called_once()                       # Ana esvaziou → removida
    coll.update_one.assert_not_called()
    assert m_atrib.call_args[0][4] is None                     # destino leva a ordem inteira (None)

def test_repartir_dividir_reduz_origem_e_da_parcela_ao_destino():
    origens = [{"_id": "a1", "ordem": "O1", "funcionario_id": "ana", "dia": 0, "parcela_min": None}]
    r, coll, m_atrib = _rep(origens)(30)       # 30 vem pro destino, 90 fica com Ana
    assert r["ok"]
    coll.delete_one.assert_not_called()                        # Ana continua (90)
    assert coll.update_one.call_args[0][1]["$set"]["parcela_min"] == 90
    assert m_atrib.call_args[0][4] == 30                       # destino recebe 30

def test_repartir_dividir_greedy_multi_origem():
    # duas origens (80 + 40 = 120). Tirar 100: zera a de 80 (remove) e reduz a de 40 p/ 20.
    origens = [
        {"_id": "a1", "ordem": "O1", "funcionario_id": "ana", "dia": 0, "parcela_min": 80},
        {"_id": "a2", "ordem": "O1", "funcionario_id": "eve", "dia": 1, "parcela_min": 40},
    ]
    r, coll, m_atrib = _rep(origens)(100)
    assert r["ok"]
    coll.delete_one.assert_called_once()                       # a de 80 zerou → removida
    assert coll.delete_one.call_args[0][0]["_id"] == "a1"
    assert coll.update_one.call_args[0][1]["$set"]["parcela_min"] == 20   # a de 40 → 20
    assert m_atrib.call_args[0][4] == 100                      # destino recebe 100
