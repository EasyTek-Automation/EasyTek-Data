"""
Testes de src/utils/failure_tree.py — modelo ROOT/STEP/CAUSE e distribuição de tempo.

Modelo de tempo (recursivo): ROOT = duração da parada (fixa). O tempo de cada
balão é dividido entre seus filhos diretos (MANUAL fica fixo; AUTO divide por
igual o que sobra). Invariante: os filhos de um balão somam o tempo dele, em todos
os níveis. Módulo puro (stdlib).
"""

from src.utils.failure_tree import (
    MODO_AUTO,
    MODO_EXPLICATIVO,
    MODO_MANUAL,
    TIPO_CAUSA,
    TIPO_ETAPA,
    TIPO_RAIZ,
    criar_etapa,
    criar_no,
    criar_ramificacao,
    descendentes,
    marcar_explicativo,
    detectar_ciclo,
    distribuir_tempos,
    duplicar_subarvore,
    etapas,
    excluir_no,
    filhos,
    formatar_duracao,
    ids_manuais_em_excesso,
    marcar_causa_raiz,
    marcar_tempo_manual,
    pode_reparentar,
    proximo_sort_order,
    reparent_muda_tipo,
    reparentar,
    resetar_tempos,
    sincronizar_tipos,
    tipo_por_pai,
    tornar_tempo_auto,
    validar_arvore,
    validar_tempos,
)

H = 60  # minutos por hora — as regras são enunciadas em horas


def _raiz(analysis_id="A1"):
    return criar_no(analysis_id, None, "Parada", tipo=TIPO_RAIZ, no_id="raiz")


def _com_steps(n, analysis_id="A1"):
    """Árvore com 1 ROOT e `n` STEP filhas diretas, todas AUTO."""
    nos = [_raiz(analysis_id)]
    nos += [criar_etapa(analysis_id, "raiz", f"Etapa {i}", sort_order=i, no_id=f"s{i}")
            for i in range(n)]
    return nos


def _por_id(nos):
    return {n["id"]: n for n in nos}


class TestFormatarDuracao:
    def test_horas_exatas(self):
        assert formatar_duracao(70 * H) == "70 h"

    def test_horas_e_minutos(self):
        assert formatar_duracao(90) == "1 h 30 min"

    def test_evento_da_cisalha(self):
        assert formatar_duracao(732) == "12 h 12 min"

    def test_zero_e_none(self):
        assert formatar_duracao(0) == "0 min"
        assert formatar_duracao(None) == "—"


class TestDistribuicaoStepOnly:
    """Seção 21.1 casos 1–3, 12 — só STEP rateia; ROOT não entra no divisor."""

    def test_uma_step_recebe_tudo(self):  # caso 1
        r = distribuir_tempos(_com_steps(1), 700 * H)
        assert _por_id(r)["s0"]["duration_min"] == 700 * H

    def test_duas_steps_dividem(self):  # caso 2
        r = distribuir_tempos(_com_steps(2), 700 * H)
        assert _por_id(r)["s0"]["duration_min"] == 350 * H
        assert _por_id(r)["s1"]["duration_min"] == 350 * H

    def test_dez_steps_setenta_horas_cada(self):  # caso 3
        r = distribuir_tempos(_com_steps(10), 700 * H)
        assert all(n["duration_min"] == 70 * H for n in etapas(r))

    def test_root_recebe_o_total(self):  # o ROOT carrega a duração da parada
        r = distribuir_tempos(_com_steps(10), 700 * H)
        assert _por_id(r)["raiz"]["duration_min"] == 700 * H

    def test_soma_fecha_exatamente(self):
        r = distribuir_tempos(_com_steps(10), 700 * H)
        assert sum(n["duration_min"] for n in etapas(r)) == 700 * H

    def test_cisalha_duas_etapas_366_cada(self):  # Seção 23
        r = distribuir_tempos(_com_steps(2), 732)
        assert [_por_id(r)[f"s{i}"]["duration_min"] for i in (0, 1)] == [366, 366]

    def test_cisalha_tres_etapas_redistribui(self):  # Seção 23
        r = distribuir_tempos(_com_steps(3), 732)
        vals = [_por_id(r)[f"s{i}"]["duration_min"] for i in range(3)]
        assert sum(vals) == 732
        assert vals == [244, 244, 244]


class TestCauseNaoRateia:
    """Modelo recursivo — filhos herdam o tempo do pai; mexer nos filhos de um
    balão não muda o tempo dele (nem dos tios)."""

    def _uma_step(self):
        nos = _com_steps(2)  # s0, s1 com 350h cada em 700h
        return distribuir_tempos(nos, 700 * H)

    def test_filho_unico_herda_tempo_do_pai(self):
        nos = self._uma_step()
        nos.append(criar_ramificacao("A1", "s0", "explicação", no_id="c1"))
        r = distribuir_tempos(nos, 700 * H)
        assert _por_id(r)["s0"]["duration_min"] == 350 * H   # tempo do pai não muda
        assert _por_id(r)["s1"]["duration_min"] == 350 * H
        assert _por_id(r)["c1"]["duration_min"] == 350 * H   # filho único herda tudo

    def test_excluir_cause_nao_altera(self):  # caso 5
        nos = self._uma_step()
        nos.append(criar_ramificacao("A1", "s0", "x", no_id="c1"))
        nos = excluir_no(nos, "c1")
        r = distribuir_tempos(nos, 700 * H)
        assert _por_id(r)["s0"]["duration_min"] == 350 * H

    def test_duplicar_cause_nao_altera(self):  # caso 6
        nos = self._uma_step()
        nos.append(criar_ramificacao("A1", "s0", "x", no_id="c1"))
        nos = nos + duplicar_subarvore(nos, "c1", com_descendentes=False)
        r = distribuir_tempos(nos, 700 * H)
        assert _por_id(r)["s0"]["duration_min"] == 350 * H
        assert _por_id(r)["s1"]["duration_min"] == 350 * H


class TestStepMudaRateio:
    """Seção 21.1 casos 7–8 — mexer em STEP redistribui."""

    def test_adicionar_step_redistribui(self):  # caso 7
        nos = distribuir_tempos(_com_steps(2), 700 * H)  # 350/350
        nos.append(criar_etapa("A1", "raiz", "nova", sort_order=2, no_id="s2"))
        r = distribuir_tempos(nos, 700 * H)
        assert all(n["duration_min"] == 700 * H // 3 for n in etapas(r))  # 14000 cada
        assert sum(n["duration_min"] for n in etapas(r)) == 700 * H

    def test_excluir_step_redistribui(self):  # caso 8
        nos = distribuir_tempos(_com_steps(2), 700 * H)
        nos = excluir_no(nos, "s1")
        r = distribuir_tempos(nos, 700 * H)
        assert _por_id(r)["s0"]["duration_min"] == 700 * H  # sobrou 1 STEP


class TestTempoManual:
    """Seção 21.1 casos 9–11 — manual respeitado, resto rateado, soma exata."""

    def test_manual_160h_nove_automaticas_dividem_540(self):  # caso 9
        nos = _com_steps(10)
        _por_id(nos)["s0"].update(duration_mode=MODO_MANUAL, duration_min=160 * H)
        r = distribuir_tempos(nos, 700 * H)
        assert _por_id(r)["s0"]["duration_min"] == 160 * H
        auto = [n for n in etapas(r) if n["duration_mode"] == MODO_AUTO]
        assert len(auto) == 9
        assert all(n["duration_min"] == 60 * H for n in auto)  # (700-160)/9 = 60

    def test_manual_acima_do_total_gera_erro(self):  # caso 10
        nos = _com_steps(2)
        _por_id(nos)["s0"].update(duration_mode=MODO_MANUAL, duration_min=800 * H)
        _por_id(nos)["s1"].update(duration_mode=MODO_MANUAL, duration_min=100 * H)
        ok, msg = validar_tempos(nos, 700 * H)
        assert ok is False
        assert "passam do" in msg

    def test_divisao_com_resto_mantem_soma(self):  # caso 11
        r = distribuir_tempos(_com_steps(3), 100)
        vals = sorted(_por_id(r)[f"s{i}"]["duration_min"] for i in range(3))
        assert vals == [33, 33, 34]  # resto na última
        assert sum(vals) == 100

    def test_resto_espalha_nas_ultimas(self):
        # 8/3 → 2,3,3 (resto de 2 nas duas últimas), não 2,2,4
        r = distribuir_tempos(_com_steps(3), 8)
        vals = [_por_id(r)[f"s{i}"]["duration_min"] for i in range(3)]
        assert vals == [2, 3, 3]
        assert sum(vals) == 8

    def test_manual_nao_e_sobrescrito(self):  # caso 13 (parte)
        nos = _com_steps(10)
        _por_id(nos)["s0"].update(duration_mode=MODO_MANUAL, duration_min=160 * H)
        nos = distribuir_tempos(nos, 700 * H)
        nos = excluir_no(nos, "s9")
        r = distribuir_tempos(nos, 700 * H)
        assert _por_id(r)["s0"]["duration_min"] == 160 * H  # intocado


class TestDistribuicaoTopDown:
    """Top-down, ancestrais fixos: o pai reparte; irmãos AUTO herdam a sobra; balão
    explicativo é transparente (não leva tempo)."""

    def _no(self, no_id, parent, tipo, modo=MODO_AUTO, minutos=0, ordem=0):
        n = criar_no("A1", parent, no_id, tipo=tipo, no_id=no_id, sort_order=ordem)
        n.update(duration_mode=modo, duration_min=minutos)
        return n

    def test_auto_herda_sobra_do_pai_direto(self):
        # Pai 40 (manual), um filho manual 27 → o filho AUTO herda 13 (40−27).
        nos = [
            _raiz(),
            self._no("s0", "raiz", TIPO_ETAPA, MODO_MANUAL, 40),
            self._no("a", "s0", TIPO_CAUSA, MODO_MANUAL, 27, ordem=0),
            self._no("b", "s0", TIPO_CAUSA, MODO_AUTO, ordem=1),
        ]
        r = _por_id(distribuir_tempos(nos, 700))
        assert r["s0"]["duration_min"] == 40    # ancestral fixo (manual)
        assert r["a"]["duration_min"] == 27
        assert r["b"]["duration_min"] == 13     # herda a sobra do pai direto

    def test_editar_folha_nao_muda_ancestral(self):
        # Fixar um neto redistribui só os irmãos; pai e avô intactos.
        nos = [
            _raiz(),
            self._no("s0", "raiz", TIPO_ETAPA, MODO_MANUAL, 60),
            self._no("a", "s0", TIPO_CAUSA, MODO_AUTO, ordem=0),
            self._no("b", "s0", TIPO_CAUSA, MODO_AUTO, ordem=1),
        ]
        nos = marcar_tempo_manual(nos, "a", 50)
        r = _por_id(distribuir_tempos(nos, 700))
        assert r["raiz"]["duration_min"] == 700  # avô intacto
        assert r["s0"]["duration_min"] == 60     # pai intacto
        assert r["a"]["duration_min"] == 50 and r["b"]["duration_min"] == 10  # irmão absorve

    def test_explicativo_folha_fica_vermelho(self):
        # nível1=54, filhos 27 (manual) e explicativo-folha → o explicativo fica com
        # sua fatia (27) mas não tem causa abaixo → vermelho, até adicionar um filho.
        nos = [
            _raiz(),
            self._no("a", "raiz", TIPO_ETAPA, MODO_MANUAL, 27, ordem=0),
            self._no("b", "raiz", TIPO_ETAPA, MODO_EXPLICATIVO, ordem=1),
        ]
        rl = distribuir_tempos(nos, 54)
        r = _por_id(rl)
        assert r["a"]["duration_min"] == 27      # irmão intacto
        assert r["b"]["duration_min"] == 27      # guarda a fatia (a UI mostra "sem tempo")
        ok, msg = validar_tempos(rl, 54)
        assert not ok and "explicativo" in msg
        assert "b" in ids_manuais_em_excesso(rl, 54)

    def test_marcar_explicativo_nao_muda_os_irmaos(self):
        # O bug: 3 irmãos de 35; marco 1 como explicativo → os outros 2 DEVEM ficar
        # em 35 (não podem ser reequilibrados). O explicativo guarda os 35 e, sem
        # filho, fica vermelho.
        nos = [
            _raiz(),
            self._no("a", "raiz", TIPO_ETAPA, MODO_AUTO, ordem=0),
            self._no("b", "raiz", TIPO_ETAPA, MODO_AUTO, ordem=1),
            self._no("x", "raiz", TIPO_ETAPA, MODO_AUTO, ordem=2),
        ]
        r0 = _por_id(distribuir_tempos(nos, 105))
        assert (r0["a"]["duration_min"], r0["b"]["duration_min"], r0["x"]["duration_min"]) == (35, 35, 35)
        nos = marcar_explicativo(nos, "x", True)
        rl = distribuir_tempos(nos, 105)
        r = _por_id(rl)
        assert r["a"]["duration_min"] == 35 and r["b"]["duration_min"] == 35  # INTACTOS
        assert r["x"]["duration_min"] == 35                                   # guarda a fatia
        assert "x" in ids_manuais_em_excesso(rl, 105)                         # vermelho (sem filho)

    def test_filho_de_explicativo_herda_a_fatia(self):
        # Adicionar um filho no explicativo → herda os 35 dele; irmãos seguem 35.
        nos = [
            _raiz(),
            self._no("a", "raiz", TIPO_ETAPA, MODO_AUTO, ordem=0),
            self._no("b", "raiz", TIPO_ETAPA, MODO_AUTO, ordem=1),
            self._no("x", "raiz", TIPO_ETAPA, MODO_EXPLICATIVO, ordem=2),
            self._no("c", "x", TIPO_CAUSA, MODO_AUTO),
        ]
        rl = distribuir_tempos(nos, 105)
        r = _por_id(rl)
        assert r["a"]["duration_min"] == 35 and r["b"]["duration_min"] == 35  # irmãos intactos
        assert r["c"]["duration_min"] == 35      # herda a fatia do explicativo
        assert r["x"]["duration_min"] == 35      # guarda a fatia (UI: "sem tempo")
        ok, _ = validar_tempos(rl, 105)
        assert ok                                # fecha (o filho absorveu)

    def test_irmaos_do_filho_do_explicativo_dividem(self):
        nos = [
            _raiz(),
            self._no("a", "raiz", TIPO_ETAPA, MODO_MANUAL, 27, ordem=0),
            self._no("b", "raiz", TIPO_ETAPA, MODO_EXPLICATIVO, ordem=1),
            self._no("c", "b", TIPO_CAUSA, MODO_AUTO, ordem=0),
            self._no("d", "b", TIPO_CAUSA, MODO_AUTO, ordem=1),
        ]
        r = _por_id(distribuir_tempos(nos, 54))
        assert r["c"]["duration_min"] == 13 and r["d"]["duration_min"] == 14  # dividem os 27 do explicativo

    def test_manual_estoura_gera_erro(self):
        nos = [
            _raiz(),
            self._no("a", "raiz", TIPO_ETAPA, MODO_MANUAL, 40, ordem=0),
            self._no("b", "raiz", TIPO_ETAPA, MODO_MANUAL, 30, ordem=1),
        ]
        rl = distribuir_tempos(nos, 54)
        ok, msg = validar_tempos(rl, 54)
        assert not ok and "passam do" in msg     # 70 > 54

    def test_marcar_tempo_manual_em_container(self):
        # Agora um container aceita pino (competidor de valor fixo).
        nos = [
            _raiz(),
            self._no("s0", "raiz", TIPO_ETAPA),
            self._no("a", "s0", TIPO_CAUSA, MODO_AUTO),
        ]
        r = _por_id(marcar_tempo_manual(nos, "s0", 99))
        assert r["s0"]["duration_mode"] == MODO_MANUAL and r["s0"]["duration_min"] == 99

    def test_marcar_e_desmarcar_explicativo(self):
        nos = _com_steps(1)
        r = _por_id(marcar_explicativo(nos, "s0", True))
        assert r["s0"]["duration_mode"] == MODO_EXPLICATIVO
        r2 = _por_id(marcar_explicativo(nos, "s0", False))
        assert r2["s0"]["duration_mode"] == MODO_AUTO


class TestSincronizarTipos:
    """A regra de conversão (Seção 9.4) — fonte da verdade dos tipos."""

    def test_filho_do_root_e_step(self):
        assert tipo_por_pai(_com_steps(1), "raiz") == TIPO_ETAPA

    def test_filho_de_step_e_cause(self):
        nos = _com_steps(1)
        assert tipo_por_pai(nos, "s0") == TIPO_CAUSA

    def test_sincroniza_arvore_antiga_root_cause(self):
        # Retrocompat: análise antiga só tinha ROOT/CAUSE. Filho direto do ROOT
        # deve virar STEP; neto deve continuar CAUSE.
        nos = [_raiz(),
               criar_no("A1", "raiz", "era cause", tipo=TIPO_CAUSA, no_id="a"),
               criar_no("A1", "a", "neto", tipo=TIPO_CAUSA, no_id="b")]
        r = sincronizar_tipos(nos)
        assert _por_id(r)["a"]["tipo"] == TIPO_ETAPA
        assert _por_id(r)["b"]["tipo"] == TIPO_CAUSA

    def test_sem_raiz_nao_quebra(self):
        assert sincronizar_tipos([]) == []


class TestArvoreEstrutura:
    """Seção 21.2 casos 13–16 — ciclos, ROOT único, conversão de tipos."""

    def test_arvore_sadia_valida(self):
        nos = sincronizar_tipos(_com_steps(3))
        assert validar_arvore(nos, "A1") == (True, "")

    def test_bloqueia_ciclo(self):  # caso 13
        nos = _com_steps(2)
        _por_id(nos)["s0"]["parent_id"] = "s1"
        _por_id(nos)["s1"]["parent_id"] = "s0"
        assert detectar_ciclo(nos) is True
        ok, msg = validar_arvore(nos, "A1")
        assert ok is False

    def test_nao_exclui_root(self):  # caso 14
        nos = _com_steps(2)
        assert len(excluir_no(nos, "raiz")) == len(nos)

    def test_mais_de_um_root_reprovado(self):  # caso 15
        nos = _com_steps(1)
        nos.append(criar_no("A1", None, "outra", tipo=TIPO_RAIZ, no_id="r2"))
        ok, msg = validar_arvore(nos, "A1")
        assert ok is False
        assert "mais de um" in msg

    def test_filho_do_root_precisa_ser_step(self):  # caso 16
        nos = _com_steps(1)
        _por_id(nos)["s0"]["tipo"] = TIPO_CAUSA  # errado: filho do ROOT
        ok, msg = validar_arvore(nos, "A1")
        assert ok is False
        assert "STEP" in msg

    def test_neto_precisa_ser_cause(self):  # caso 17
        nos = _com_steps(1)
        nos.append(criar_no("A1", "s0", "neto", tipo=TIPO_ETAPA, no_id="g1"))  # errado
        ok, msg = validar_arvore(nos, "A1")
        assert ok is False
        assert "CAUSE" in msg

    def test_root_nao_pode_ser_causa_raiz(self):
        nos = _com_steps(1)
        _por_id(nos)["raiz"]["is_root_cause"] = True
        ok, msg = validar_arvore(nos, "A1")
        assert ok is False
        assert "causa raiz" in msg

    def test_duracao_negativa_reprovada(self):
        nos = sincronizar_tipos(_com_steps(1))
        _por_id(nos)["s0"]["duration_min"] = -5
        ok, msg = validar_arvore(nos, "A1")
        assert ok is False
        assert "negativa" in msg


class TestReparent:
    """Seção 21.2 casos 16–18 — conectar muda tipo; reparent mantém consistência."""

    def _arvore(self):
        # raiz → s0 (STEP) → c1 (CAUSE); s1 (STEP)
        nos = _com_steps(2)
        nos.append(criar_ramificacao("A1", "s0", "sub", no_id="c1"))
        return sincronizar_tipos(nos)

    def test_conectar_ao_root_vira_step(self):  # caso 16
        nos = self._arvore()  # c1 é CAUSE sob s0
        assert reparent_muda_tipo(nos, "c1", "raiz") is True
        r = reparentar(nos, "c1", "raiz")
        assert _por_id(r)["c1"]["tipo"] == TIPO_ETAPA

    def test_conectar_step_abaixo_de_outro_vira_cause(self):  # caso 17
        nos = self._arvore()  # s1 é STEP sob raiz
        assert reparent_muda_tipo(nos, "s1", "s0") is True
        r = reparentar(nos, "s1", "s0")
        assert _por_id(r)["s1"]["tipo"] == TIPO_CAUSA

    def test_reparent_mantem_arvore_valida(self):  # caso 18
        nos = self._arvore()
        r = reparentar(nos, "s1", "s0")
        assert validar_arvore(r, "A1") == (True, "")

    def test_reparent_recalcula_recursivo(self):
        # s0,s1 = 350/350 (c1 já é filho de s0). Mover s1 para baixo de s0: s0 vira
        # único filho do ROOT (700h) e divide entre seus filhos c1 e s1 → 350 cada.
        nos = distribuir_tempos(self._arvore(), 700 * H)
        nos = reparentar(nos, "s1", "s0")
        r = distribuir_tempos(nos, 700 * H)
        assert _por_id(r)["s0"]["duration_min"] == 700 * H
        assert _por_id(r)["s1"]["duration_min"] == 350 * H
        assert _por_id(r)["c1"]["duration_min"] == 350 * H

    def test_nao_reparenteia_para_dentro_de_si(self):
        nos = self._arvore()
        ok, _ = pode_reparentar(nos, "s0", "c1")
        assert ok is False


class TestDuplicarEExcluir:
    """Seção 21.2 casos 19–20 — duplicar gera IDs novos; promover mantém conexões."""

    def _ramo(self):
        nos = _com_steps(1)
        nos.append(criar_ramificacao("A1", "s0", "filho", no_id="c1"))
        nos.append(criar_ramificacao("A1", "c1", "neto", no_id="c2"))
        return sincronizar_tipos(nos)

    def test_duplicar_gera_ids_novos(self):  # caso 19
        nos = self._ramo()
        copias = duplicar_subarvore(nos, "s0", com_descendentes=True)
        originais = {n["id"] for n in nos}
        assert originais.isdisjoint({c["id"] for c in copias})
        assert len(copias) == 3

    def test_duplicar_step_entra_no_rateio(self):
        nos = distribuir_tempos(_com_steps(1), 700 * H)  # s0 = 700h
        nos = nos + duplicar_subarvore(nos, "s0", com_descendentes=False)
        r = distribuir_tempos(nos, 700 * H)
        assert len(etapas(r)) == 2
        assert all(n["duration_min"] == 350 * H for n in etapas(r))

    def test_excluir_promovendo_religa_ao_avo(self):  # caso 20
        nos = self._ramo()
        r = excluir_no(nos, "c1", promover_filhos=True)
        assert "c1" not in _por_id(r)
        assert _por_id(r)["c2"]["parent_id"] == "s0"  # neto religado ao avô

    def test_excluir_step_promovendo_cause_vira_step(self):
        # Excluir s0 promovendo c1 (CAUSE): c1 vira filho do ROOT → STEP
        nos = self._ramo()
        r = excluir_no(nos, "s0", promover_filhos=True)
        assert _por_id(r)["c1"]["tipo"] == TIPO_ETAPA
        assert _por_id(r)["c1"]["parent_id"] == "raiz"

    def test_excluir_cascata_remove_ramo(self):
        r = excluir_no(self._ramo(), "s0", promover_filhos=False)
        assert {n["id"] for n in r} == {"raiz"}


class TestCausaRaiz:
    """Seção 21.3 casos 21–22, 26 — is_root_cause é a fonte única."""

    def test_marcar_atualiza_flag(self):  # caso 21
        nos = _com_steps(2)
        r = marcar_causa_raiz(nos, "s0", True)
        assert _por_id(r)["s0"]["is_root_cause"] is True

    def test_desmarcar(self):
        nos = marcar_causa_raiz(_com_steps(2), "s0", True)
        r = marcar_causa_raiz(nos, "s0", False)
        assert _por_id(r)["s0"]["is_root_cause"] is False

    def test_root_nunca_vira_causa_raiz(self):
        r = marcar_causa_raiz(_com_steps(1), "raiz", True)
        assert _por_id(r)["raiz"]["is_root_cause"] is False

    def test_cause_tambem_pode_ser_causa_raiz(self):
        nos = _com_steps(1)
        nos.append(criar_ramificacao("A1", "s0", "sub", no_id="c1"))
        r = marcar_causa_raiz(nos, "c1", True)
        assert _por_id(r)["c1"]["is_root_cause"] is True


class TestValidarTempos:
    """Seção 10.5 — estouro e divergência bloqueiam, nunca salvam em silêncio."""

    def test_ok_com_automaticas(self):
        nos = distribuir_tempos(_com_steps(10), 700 * H)
        assert validar_tempos(nos, 700 * H) == (True, "")

    def test_todas_manuais_divergentes(self):
        nos = _com_steps(2)
        _por_id(nos)["s0"].update(duration_mode=MODO_MANUAL, duration_min=100 * H)
        _por_id(nos)["s1"].update(duration_mode=MODO_MANUAL, duration_min=200 * H)
        ok, msg = validar_tempos(nos, 700 * H)
        assert ok is False
        assert "Sobram" in msg  # 300 h manuais < 700 h, sem AUTO para absorver

    def test_ids_em_excesso_destacam_steps(self):
        nos = _com_steps(2)
        _por_id(nos)["s0"].update(duration_mode=MODO_MANUAL, duration_min=800 * H)
        _por_id(nos)["s1"].update(duration_mode=MODO_MANUAL, duration_min=100 * H)
        assert set(ids_manuais_em_excesso(nos, 700 * H)) == {"s0", "s1"}

    def test_cause_manual_estoura_o_pai(self):
        # Agora a CAUSE tem tempo (modelo recursivo): um manual acima do tempo do
        # balão pai é estouro e bloqueia concluir.
        nos = _com_steps(1)  # s0 recebe 700h
        nos.append(criar_ramificacao("A1", "s0", "x", no_id="c1"))
        _por_id(nos)["c1"].update(duration_mode=MODO_MANUAL, duration_min=9999)
        nos = distribuir_tempos(nos, 700 * H)
        ok, _ = validar_tempos(nos, 700 * H)
        assert ok is False


class TestDistribuicaoRecursiva:
    """Modelo recursivo: filhos somam o tempo do pai em todos os níveis; manual
    fixa e os irmãos redistribuem; reset volta ao automático."""

    def _dois_niveis(self):
        # raiz → s0 (STEP) → a,b (CAUSE); s1 (STEP)
        nos = _com_steps(2)
        nos.append(criar_ramificacao("A1", "s0", "a", no_id="a"))
        nos.append(criar_ramificacao("A1", "s0", "b", no_id="b"))
        return sincronizar_tipos(nos)

    def test_filhos_dividem_o_tempo_do_pai(self):
        p = _por_id(distribuir_tempos(self._dois_niveis(), 720))
        assert p["s0"]["duration_min"] == 360 and p["s1"]["duration_min"] == 360
        assert p["a"]["duration_min"] == 180 and p["b"]["duration_min"] == 180  # 360/2

    def test_invariante_soma_por_nivel(self):
        p = _por_id(distribuir_tempos(self._dois_niveis(), 720))
        assert p["a"]["duration_min"] + p["b"]["duration_min"] == p["s0"]["duration_min"]
        assert p["s0"]["duration_min"] + p["s1"]["duration_min"] == p["raiz"]["duration_min"] == 720

    def test_manual_fixa_e_irmaos_redistribuem(self):
        r = distribuir_tempos(marcar_tempo_manual(_com_steps(3), "s0", 300), 900)
        p = _por_id(r)
        assert p["s0"]["duration_min"] == 300                       # fixo
        assert p["s1"]["duration_min"] == 300 and p["s2"]["duration_min"] == 300  # (900-300)/2

    def test_editar_nao_mexe_no_ancestral(self):
        p = _por_id(distribuir_tempos(marcar_tempo_manual(_com_steps(2), "s0", 200), 700))
        assert p["raiz"]["duration_min"] == 700   # ancestral intacto (total fixo)
        assert p["s0"]["duration_min"] == 200 and p["s1"]["duration_min"] == 500  # irmão absorve

    def test_pino_em_folha_borbulha_pro_container(self):
        # Modelo bottom-up: o pino vai na folha (a); o container s0 herda a soma dos filhos.
        nos = marcar_tempo_manual(self._dois_niveis(), "a", 200)  # folha a fixa 200; b auto
        p = _por_id(distribuir_tempos(nos, 700))
        assert p["a"]["duration_min"] == 200
        assert p["s0"]["duration_min"] == p["a"]["duration_min"] + p["b"]["duration_min"]
        assert p["s0"]["duration_min"] + p["s1"]["duration_min"] == 700

    def test_reset_volta_ao_automatico(self):
        nos = resetar_tempos(marcar_tempo_manual(_com_steps(2), "s0", 100))
        p = _por_id(distribuir_tempos(nos, 700))
        assert p["s0"]["duration_mode"] == MODO_AUTO
        assert p["s0"]["duration_min"] == 350 and p["s1"]["duration_min"] == 350

    def test_tornar_auto_de_um_no(self):
        nos = tornar_tempo_auto(marcar_tempo_manual(_com_steps(2), "s0", 100), "s0")
        p = _por_id(distribuir_tempos(nos, 700))
        assert p["s0"]["duration_mode"] == MODO_AUTO and p["s0"]["duration_min"] == 350

    def test_root_nao_vira_manual(self):
        nos = marcar_tempo_manual(_com_steps(1), "raiz", 5)
        assert _por_id(nos)["raiz"]["duration_mode"] != MODO_MANUAL


class TestFilhosEOrdem:
    def test_proximo_sort_order(self):
        assert proximo_sort_order(_com_steps(3), "raiz") == 3

    def test_filhos_ordenados(self):
        assert [n["id"] for n in filhos(_com_steps(3), "raiz")] == ["s0", "s1", "s2"]

    def test_descendentes_termina_com_ciclo(self):
        nos = _com_steps(2)
        _por_id(nos)["s0"]["parent_id"] = "s1"
        _por_id(nos)["s1"]["parent_id"] = "s0"
        assert len(descendentes(nos, "s0")) <= 2
