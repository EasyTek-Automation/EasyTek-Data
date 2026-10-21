"""Testes das funções puras do Radar Lab (`/lab/radar`).

O valor destes testes está nos invariantes que a tela não deixa ver: toda camada
tem que ter um número para todo eixo (senão a figura sai com o polígono torto), e
estado salvo no navegador em versão antiga tem que continuar abrindo.
"""

import json

import plotly.graph_objects as go

from src.pages.lab import radar_lab as rl


def _ids(itens):
    return [i["id"] for i in itens]


class TestEstadoPadrao:

    def test_padrao_replica_o_radar_da_v1(self):
        estado = rl.default_state()
        assert [e["name"] for e in estado["axes"]] == ["MTBF", "MTTR", "Taxa de Avaria"]
        assert [c["name"] for c in estado["layers"]] == ["Meta", "Média Geral", "Equipamento"]

    def test_toda_camada_tem_valor_para_todo_eixo(self):
        estado = rl.default_state()
        ids_eixos = set(_ids(estado["axes"]))
        for camada in estado["layers"]:
            assert set(camada["values"]) == ids_eixos


class TestEixos:

    def test_adicionar_eixo_cria_valor_zero_em_todas_as_camadas(self):
        estado = rl.add_axis(rl.default_state(), name="Custo")
        novo_id = estado["axes"][-1]["id"]
        assert estado["axes"][-1]["name"] == "Custo"
        for camada in estado["layers"]:
            assert camada["values"][novo_id] == 0.0

    def test_id_novo_nao_colide_com_os_existentes(self):
        estado = rl.add_axis(rl.default_state())
        assert len(set(_ids(estado["axes"]))) == len(estado["axes"])

    def test_remover_eixo_limpa_o_valor_nas_camadas(self):
        estado = rl.remove_axis(rl.default_state(), "ax2")
        assert "ax2" not in _ids(estado["axes"])
        for camada in estado["layers"]:
            assert "ax2" not in camada["values"]

    def test_remover_eixo_inexistente_nao_quebra(self):
        estado = rl.remove_axis(rl.default_state(), "ax999")
        assert len(estado["axes"]) == 3

    def test_mover_eixo_troca_a_ordem(self):
        estado = rl.move_axis(rl.default_state(), "ax3", -1)
        assert _ids(estado["axes"]) == ["ax1", "ax3", "ax2"]

    def test_mover_alem_da_ponta_e_ignorado(self):
        estado = rl.move_axis(rl.default_state(), "ax1", -1)
        assert _ids(estado["axes"]) == ["ax1", "ax2", "ax3"]

    def test_renomear_eixo(self):
        estado = rl.update_axis(rl.default_state(), "ax1", "name", "Confiabilidade")
        assert estado["axes"][0]["name"] == "Confiabilidade"

    def test_editar_descricao_do_eixo(self):
        estado = rl.update_axis(rl.default_state(), "ax1", "desc", "explicação nova")
        assert estado["axes"][0]["desc"] == "explicação nova"

    def test_campo_desconhecido_nao_e_gravado(self):
        estado = rl.update_axis(rl.default_state(), "ax1", "cor", "#000")
        assert "cor" not in estado["axes"][0]


class TestCamadas:

    def test_adicionar_camada_vem_zerada_e_com_cor_da_paleta(self):
        estado = rl.add_layer(rl.default_state(), name="Meta 2027")
        camada = estado["layers"][-1]
        assert camada["name"] == "Meta 2027"
        assert camada["color"] in rl.PALETA
        assert set(camada["values"]) == set(_ids(estado["axes"]))
        assert all(v == 0.0 for v in camada["values"].values())

    def test_remover_camada(self):
        estado = rl.remove_layer(rl.default_state(), "ly2")
        assert "ly2" not in _ids(estado["layers"])
        assert len(estado["layers"]) == 2

    def test_opacidade_fora_da_faixa_e_limitada(self):
        estado = rl.update_layer(rl.default_state(), "ly1", "opacity", 5)
        assert estado["layers"][0]["opacity"] == 1.0

    def test_espessura_tem_minimo(self):
        estado = rl.update_layer(rl.default_state(), "ly1", "width", 0)
        assert estado["layers"][0]["width"] == 0.5

    def test_ocultar_camada_nao_apaga_os_valores(self):
        estado = rl.update_layer(rl.default_state(), "ly3", "visible", False)
        camada = [c for c in estado["layers"] if c["id"] == "ly3"][0]
        assert camada["visible"] is False
        assert camada["values"]["ax1"] == 118


class TestTabelaDeValores:

    def test_ida_e_volta_pela_tabela_preserva_os_valores(self):
        estado = rl.default_state()
        de_volta = rl.set_values_from_table(estado, rl.table_data(estado))
        assert de_volta == estado

    def test_edicao_de_celula_entra_no_estado(self):
        estado = rl.default_state()
        linhas = rl.table_data(estado)
        linhas[0]["ly3"] = 42
        novo = rl.set_values_from_table(estado, linhas)
        assert novo["layers"][2]["values"]["ax1"] == 42.0

    def test_celula_vazia_ou_com_texto_vira_zero(self):
        estado = rl.default_state()
        linhas = rl.table_data(estado)
        linhas[0]["ly1"] = ""
        linhas[1]["ly1"] = "abc"
        novo = rl.set_values_from_table(estado, linhas)
        assert novo["layers"][0]["values"]["ax1"] == 0.0
        assert novo["layers"][0]["values"]["ax2"] == 0.0

    def test_virgula_decimal_e_aceita(self):
        estado = rl.default_state()
        linhas = rl.table_data(estado)
        linhas[0]["ly1"] = "12,5"
        novo = rl.set_values_from_table(estado, linhas)
        assert novo["layers"][0]["values"]["ax1"] == 12.5

    def test_colunas_seguem_as_camadas(self):
        estado = rl.add_layer(rl.default_state(), name="Extra")
        colunas = rl.table_columns(estado)
        assert colunas[0]["id"] == "__axis" and colunas[0]["editable"] is False
        assert [c["id"] for c in colunas[1:]] == _ids(estado["layers"])


class TestNormalizacao:

    def test_estado_antigo_sem_campos_novos_e_completado(self):
        antigo = {
            "axes": [{"id": "ax1", "name": "A"}],
            "layers": [{"id": "ly1", "name": "L"}],
        }
        estado = rl.normalize_state(antigo)
        assert estado["layers"][0]["values"] == {"ax1": 0.0}
        assert estado["layers"][0]["color"] in rl.PALETA
        assert estado["opts"]["range_mode"] == "auto"

    def test_lixo_no_lugar_do_estado_vira_estado_vazio_valido(self):
        estado = rl.normalize_state("não sou um estado")
        assert estado["axes"] == [] and estado["layers"] == []
        assert estado["opts"]["range_max"] == rl.RANGE_MAX_PADRAO

    def test_valor_de_eixo_removido_nao_sobrevive(self):
        sujo = {
            "axes": [{"id": "ax1", "name": "A"}],
            "layers": [{"id": "ly1", "name": "L", "values": {"ax1": 1, "ax_zumbi": 9}}],
        }
        estado = rl.normalize_state(sujo)
        assert estado["layers"][0]["values"] == {"ax1": 1.0}

    def test_normalizar_e_idempotente(self):
        uma = rl.normalize_state(rl.default_state())
        assert rl.normalize_state(uma) == uma


class TestImportExport:

    def test_exportar_e_importar_fecha_o_ciclo(self):
        estado = rl.add_axis(rl.default_state(), name="Custo")
        texto = rl.state_to_json(estado)
        assert rl.state_from_json(texto) == rl.normalize_state(estado)

    def test_json_invalido_devolve_o_fallback(self):
        atual = rl.default_state()
        assert rl.state_from_json("{isso não é json", fallback=atual) == atual

    def test_json_invalido_sem_fallback_devolve_none(self):
        assert rl.state_from_json("[]") is None

    def test_export_e_json_valido_e_legivel(self):
        carregado = json.loads(rl.state_to_json(rl.default_state()))
        assert carregado["axes"][0]["name"] == "MTBF"


class TestOpcoes:

    def test_escala_fixa_manda_no_teto_do_eixo(self):
        estado = rl.set_option(rl.default_state(), "range_mode", "fixed")
        estado = rl.set_option(estado, "range_max", 200)
        fig = rl.build_figure(estado)
        assert fig.layout.polar.radialaxis.range == (0, 200)

    def test_escala_automatica_usa_o_maior_valor_com_folga(self):
        fig = rl.build_figure(rl.default_state())
        assert fig.layout.polar.radialaxis.range[1] == 118 * 1.1

    def test_modo_de_escala_desconhecido_cai_em_auto(self):
        estado = rl.set_option(rl.default_state(), "range_mode", "seja_o_que_for")
        assert estado["opts"]["range_mode"] == "auto"

    def test_legenda_pode_ser_desligada(self):
        estado = rl.set_option(rl.default_state(), "legend", False)
        assert rl.build_figure(estado).layout.showlegend is False


class TestFigura:

    def test_uma_trace_por_camada_visivel(self):
        estado = rl.update_layer(rl.default_state(), "ly2", "visible", False)
        fig = rl.build_figure(estado)
        assert len(fig.data) == 2
        assert all(isinstance(t, go.Scatterpolar) for t in fig.data)

    def test_poligono_e_fechado(self):
        fig = rl.build_figure(rl.default_state())
        trace = fig.data[0]
        assert len(trace.r) == 4  # 3 eixos + repetição do primeiro
        assert trace.r[0] == trace.r[-1]
        assert trace.theta[0] == trace.theta[-1]

    def test_descricao_do_eixo_viaja_no_hover(self):
        estado = rl.update_axis(rl.default_state(), "ax1", "desc", "explicação")
        trace = rl.build_figure(estado).data[0]
        assert trace.customdata[0][0] == "explicação"
        assert "customdata[0]" in trace.hovertemplate

    def test_sem_eixos_desenha_aviso_em_vez_de_quebrar(self):
        estado = rl.normalize_state({})
        fig = rl.build_figure(estado)
        assert len(fig.data) == 0
        assert "Sem eixos" in fig.layout.annotations[0].text

    def test_radar_com_dois_eixos_e_permitido(self):
        estado = rl.remove_axis(rl.default_state(), "ax3")
        fig = rl.build_figure(estado)
        assert len(fig.data[0].r) == 3

    def test_preenchimento_desligado_nao_fecha_a_area(self):
        estado = rl.update_layer(rl.default_state(), "ly1", "fill", False)
        assert rl.build_figure(estado).data[0].fill == "none"

    def test_tema_escuro_muda_o_fundo_do_polar(self):
        claro = rl.build_figure(rl.default_state(), template="minty")
        escuro = rl.build_figure(rl.default_state(), template="darkly")
        assert claro.layout.polar.bgcolor == "#ffffff"
        assert escuro.layout.polar.bgcolor == "#2c2c2c"

    def test_cor_da_camada_vira_rgba_no_preenchimento(self):
        fig = rl.build_figure(rl.default_state())
        assert fig.data[0].fillcolor == "rgba(220, 53, 69, 0.1)"


class TestIntervaloDosTracos:
    """`tick_step` existe para escala discreta — nota 0/1/2 não pode mostrar 0,5."""

    def test_padrao_e_automatico(self):
        assert rl.default_state()["opts"]["tick_step"] == 0
        assert rl.build_figure(rl.default_state()).layout.polar.radialaxis.dtick is None

    def test_intervalo_fixo_vai_para_o_eixo(self):
        estado = rl.set_option(rl.default_state(), "tick_step", 1)
        assert rl.build_figure(estado).layout.polar.radialaxis.dtick == 1

    def test_valor_negativo_vira_automatico(self):
        estado = rl.set_option(rl.default_state(), "tick_step", -3)
        assert estado["opts"]["tick_step"] == 0.0

    def test_estado_antigo_sem_o_campo_abre_em_automatico(self):
        antigo = rl.default_state()
        del antigo["opts"]["tick_step"]
        assert rl.normalize_state(antigo)["opts"]["tick_step"] == 0.0


class TestBuracoNoCentro:
    """`hole` afasta o zero do ponto central — em escala curta o zero fincado some."""

    def test_padrao_e_zero_no_centro(self):
        assert rl.default_state()["opts"]["hole"] == 0.0
        assert rl.build_figure(rl.default_state()).layout.polar.hole == 0.0

    def test_buraco_vai_para_o_polar(self):
        estado = rl.set_option(rl.default_state(), "hole", 0.2)
        assert rl.build_figure(estado).layout.polar.hole == 0.2

    def test_buraco_tem_teto(self):
        estado = rl.set_option(rl.default_state(), "hole", 0.95)
        assert estado["opts"]["hole"] == 0.6

    def test_negativo_vira_zero(self):
        estado = rl.set_option(rl.default_state(), "hole", -1)
        assert estado["opts"]["hole"] == 0.0

    def test_estado_antigo_sem_o_campo_abre_sem_buraco(self):
        antigo = rl.default_state()
        del antigo["opts"]["hole"]
        assert rl.normalize_state(antigo)["opts"]["hole"] == 0.0
