# -*- coding: utf-8 -*-
"""Camada de dados do Monitoramento de Ativos (Bloco B do SDD MonAtivo-Prototipo).

O que este arquivo protege:

* a tabela-verdade do filtro (BR-04) — as oito situações nos três escopos, 24 casos;
* a precedência de cor (BR-02) — o pior evento manda;
* a marcação do ativo (BR-03, revisada em 2026-08-05) — só o verde fica sem moldura;
* os quatro cenários (BR-07) — todo conjunto citado existe de verdade no desenho.
"""
import re
from collections import Counter
from datetime import datetime, timedelta

import pytest

from src.components.monitoring import color_style
from src.utils.monitoring import projection as pj
from src.utils.monitoring import scenarios as sc
from src.utils.monitoring.events import (
    Cor,
    Escopo,
    Evento,
    Gravidade,
    Origem,
    chaves_conhecidas,
    conjuntos_por_ativo,
    cor_de,
)

AGORA = datetime(2026, 8, 4, 12, 0)
CONJ = "LCP01.APLANADORA"

DEG, PAR, PLA = Gravidade.DEGRADACAO, Gravidade.PARADA, Gravidade.PLANEJADA
P, M = Origem.PRODUCAO, Origem.MANUTENCAO


def evento(origem, gravidade, conjunto=CONJ, ha_horas=2.0, durou=None, descricao="teste"):
    inicio = AGORA - timedelta(hours=ha_horas)
    return Evento(
        conjunto=conjunto,
        origem=origem,
        gravidade=gravidade,
        inicio=inicio,
        fim=None if durou is None else inicio + timedelta(hours=durou),
        descricao=descricao,
    )


def cor_no_escopo(eventos, escopo):
    return cor_de(pj.filtrar(eventos, escopo))


# --------------------------------------------------------------------------- #
# BR-04 — a tabela-verdade inteira: 8 situações × 3 escopos
# --------------------------------------------------------------------------- #

SITUACOES = {
    "sem evento": [],
    "degradação de produção": [evento(P, DEG)],
    "degradação de manutenção": [evento(M, DEG)],
    "degradação das duas origens": [evento(P, DEG), evento(M, DEG)],
    "parada de manutenção": [evento(M, PAR)],
    "parada de produção": [evento(P, PAR)],
    "planejada de manutenção": [evento(M, PLA)],
    "planejada de produção": [evento(P, PLA)],
}

TABELA_VERDADE = {
    # situação: (Ver tudo, Só Produção, Só Manutenção)
    "sem evento": (Cor.VERDE, Cor.VERDE, Cor.VERDE),
    "degradação de produção": (Cor.AMARELO, Cor.AMARELO, Cor.VERDE),
    "degradação de manutenção": (Cor.AMARELO, Cor.VERDE, Cor.AMARELO),
    "degradação das duas origens": (Cor.AMARELO, Cor.AMARELO, Cor.AMARELO),
    "parada de manutenção": (Cor.VERMELHO, Cor.VERMELHO, Cor.VERMELHO),
    "parada de produção": (Cor.VERMELHO, Cor.VERMELHO, Cor.VERMELHO),
    "planejada de manutenção": (Cor.CINZA, Cor.CINZA, Cor.CINZA),
    "planejada de produção": (Cor.CINZA, Cor.CINZA, Cor.CINZA),
}

ESCOPOS = (Escopo.TUDO, Escopo.PRODUCAO, Escopo.MANUTENCAO)


@pytest.mark.parametrize("situacao", list(SITUACOES))
@pytest.mark.parametrize("indice", range(3))
def test_tabela_verdade_do_filtro(situacao, indice):
    esperado = TABELA_VERDADE[situacao][indice]
    assert cor_no_escopo(SITUACOES[situacao], ESCOPOS[indice]) is esperado


def test_parada_nunca_e_filtrada():
    # A prensa quebra (manutenção). Quem filtrou "Só Produção" continua vendo vermelho:
    # a linha parou e deixou de produzir, mesmo que a causa seja mecânica.
    avaria = [evento(M, PAR)]
    assert pj.filtrar(avaria, Escopo.PRODUCAO) == avaria


def test_filtrar_nunca_acende_o_que_estava_apagado():
    for situacao, eventos in SITUACOES.items():
        tudo, producao, manutencao = (cor_no_escopo(eventos, e) for e in ESCOPOS)
        ordem = [Cor.VERDE, Cor.CINZA, Cor.AMARELO, Cor.VERMELHO]
        assert ordem.index(producao) <= ordem.index(tudo), situacao
        assert ordem.index(manutencao) <= ordem.index(tudo), situacao


# --------------------------------------------------------------------------- #
# BR-02 — precedência
# --------------------------------------------------------------------------- #


def test_o_pior_evento_manda():
    # A cisalha tem um alerta preditivo e uma parada por falta de bobina: fica vermelha.
    assert cor_de([evento(M, DEG), evento(P, PAR)]) is Cor.VERMELHO
    # Fechada a parada, cai para amarelo — o alerta continua lá.
    assert cor_de([evento(M, DEG)]) is Cor.AMARELO
    assert cor_de([evento(M, DEG), evento(M, PLA)]) is Cor.AMARELO
    assert cor_de([evento(P, PLA)]) is Cor.CINZA
    assert cor_de([]) is Cor.VERDE


def test_cor_dos_conjuntos_so_lista_quem_tem_evento():
    cores = pj.cor_dos_conjuntos([evento(M, PAR), evento(P, DEG, conjunto="LCP01.PRENSA_FAGOR")])
    assert cores == {CONJ: Cor.VERMELHO, "LCP01.PRENSA_FAGOR": Cor.AMARELO}


# --------------------------------------------------------------------------- #
# BR-03 — marcação do ativo
# --------------------------------------------------------------------------- #


def test_ativo_herda_a_cor_do_pior_conjunto():
    eventos = [evento(M, DEG), evento(P, PAR, conjunto="LCP01.CARGA_DE_BOBINAS")]
    assert pj.cor_dos_ativos(eventos)["LCP01"] is Cor.VERMELHO


def test_so_o_verde_nao_recebe_marcacao():
    # BR-03 revisada em 2026-08-05: a parada prevista passou a receber moldura — a linha que
    # está fora por preventiva também precisa ser vista de longe. O que a separa do alarme é
    # a forma (tracejada, fixa), não a ausência de moldura.
    assert pj.cor_dos_ativos([]) == {}
    assert pj.cor_dos_ativos([evento(M, PLA)])["LCP01"] is Cor.CINZA


def test_parada_prevista_marca_mas_nao_pisca():
    assert pj.cor_dos_ativos([evento(M, PLA)])["LCP01"] is Cor.CINZA
    assert pj.ativos_piscando([evento(M, PLA)]) == set()


def test_so_o_vermelho_pisca():
    assert pj.ativos_piscando([evento(M, PAR)]) == {"LCP01"}
    assert pj.ativos_piscando([evento(M, DEG)]) == set()


def test_a_marcacao_responde_ao_filtro():
    # Ativo cuja única degradação é de manutenção perde a moldura sob "Só Produção".
    eventos = [evento(M, DEG)]
    assert pj.cor_dos_ativos(pj.filtrar(eventos, Escopo.TUDO))["LCP01"] is Cor.AMARELO
    assert pj.cor_dos_ativos(pj.filtrar(eventos, Escopo.PRODUCAO)) == {}


# --------------------------------------------------------------------------- #
# SP-07 — linha do tempo
# --------------------------------------------------------------------------- #


def test_ativo_sem_evento_e_uma_faixa_verde_so():
    faixas = pj.faixas_da_timeline([], "LCP01", agora=AGORA)
    assert len(faixas) == 1
    assert faixas[0].cor is Cor.VERDE
    assert round(faixas[0].horas) == pj.JANELA_TIMELINE_HORAS


def test_degradacao_que_virou_parada_gera_duas_faixas():
    eventos = [
        evento(P, DEG, ha_horas=6, durou=2),   # das 06h às 08h
        evento(M, PAR, ha_horas=4),            # das 08h em diante, em curso
    ]
    faixas = pj.faixas_da_timeline(eventos, "LCP01", agora=AGORA)
    assert [f.cor for f in faixas] == [Cor.VERDE, Cor.AMARELO, Cor.VERMELHO]
    assert round(faixas[1].horas) == 2
    assert round(faixas[2].horas) == 4


def test_faixa_de_producao_some_sob_so_manutencao():
    eventos = [evento(P, DEG, ha_horas=6, durou=2)]
    filtrados = pj.filtrar(eventos, Escopo.MANUTENCAO)
    faixas = pj.faixas_da_timeline(filtrados, "LCP01", agora=AGORA)
    assert [f.cor for f in faixas] == [Cor.VERDE]


def test_timeline_ignora_ativo_vizinho():
    eventos = [evento(M, PAR, conjunto="LCT16.APLANADORA")]
    assert [f.cor for f in pj.faixas_da_timeline(eventos, "LCP01", agora=AGORA)] == [Cor.VERDE]


# --------------------------------------------------------------------------- #
# BR-06 / SP-08 — tabelas
# --------------------------------------------------------------------------- #


def test_conjunto_sem_evento_nao_gera_tabela():
    tabelas = pj.falhas_por_conjunto([evento(M, PAR)], "LCP01")
    assert list(tabelas) == [CONJ]


def test_nenhuma_tabela_e_estado_valido():
    assert pj.falhas_por_conjunto([], "LCP01") == {}


def test_tabelas_seguem_a_ordem_fisica_da_linha():
    # O desbobinador vem antes da aplanadora na linha; a ordem da lista de eventos não importa.
    eventos = [evento(M, DEG), evento(P, DEG, conjunto="LCP01.DESBOBINADOR")]
    ordem = list(pj.falhas_por_conjunto(eventos, "LCP01"))
    fisicos = conjuntos_por_ativo()["LCP01"]
    assert ordem == sorted(ordem, key=fisicos.index)


def test_tabela_inteira_some_ao_filtrar():
    # Duas falhas na LCP01, uma de cada origem: sob "Só Produção" resta uma tabela.
    eventos = [evento(M, DEG), evento(P, DEG, conjunto="LCP01.DESBOBINADOR")]
    filtrados = pj.filtrar(eventos, Escopo.PRODUCAO)
    assert list(pj.falhas_por_conjunto(filtrados, "LCP01")) == ["LCP01.DESBOBINADOR"]


# --------------------------------------------------------------------------- #
# SP-09 — cards
# --------------------------------------------------------------------------- #


def test_estado_atual_existe_mesmo_sem_evento():
    lista = pj.cards([], "LCP01", agora=AGORA)
    assert [c.chave for c in lista] == ["estado"]
    assert lista[0].valor == "Rodando"


def test_card_de_estado_conta_ha_quanto_tempo_esta_parado():
    lista = pj.cards([evento(M, PAR, ha_horas=2.25)], "LCP01", agora=AGORA)
    estado = next(c for c in lista if c.chave == "estado")
    assert estado.valor == "Parado há 2h15"


def test_cards_de_manutencao_somem_sob_so_producao():
    eventos = [evento(M, DEG), evento(P, DEG, conjunto="LCP01.DESBOBINADOR")]
    completos = {c.chave for c in pj.cards(eventos, "LCP01", agora=AGORA)}
    assert {"alertas", "preditivo", "aderencia"} <= completos

    filtrados = pj.filtrar(eventos, Escopo.PRODUCAO)
    so_producao = {c.chave for c in pj.cards(filtrados, "LCP01", agora=AGORA)}
    assert "alertas" not in so_producao and "preditivo" not in so_producao
    assert "aderencia" in so_producao


def test_nenhum_card_de_producao_sob_so_manutencao():
    eventos = [evento(P, DEG)]
    filtrados = pj.filtrar(eventos, Escopo.MANUTENCAO)
    assert [c.chave for c in pj.cards(filtrados, "LCP01", agora=AGORA)] == ["estado"]


# --------------------------------------------------------------------------- #
# BR-07 — os cenários
# --------------------------------------------------------------------------- #


def test_os_cenarios_estao_na_ordem_combinada():
    # A ordem é o roteiro de quem apresenta: começa na fábrica inteira verde e vai subindo em
    # severidade até as duas linhas paradas, fechando na retomada. O botão da faixa de tela
    # cheia percorre esta mesma lista, um clique por cenário.
    assert [c.chave for c in sc.CENARIOS] == [
        "tudo-rodando",
        "turno-normal",
        "alertas-preditivos",
        "parada-programada",
        "parada-geral",
        "avaria-em-curso",
        "avaria-eletrica",
        "duas-linhas-paradas",
        "pos-avaria",
    ]


def test_todo_evento_e_de_manutencao():
    # BR-07 revisada em 2026-08-05: a tela é de manutenção. Evento de produção aqui voltaria a
    # disputar a atenção com o vermelho que exige ferramenta na mão.
    for cenario in sc.CENARIOS:
        origens = {e.origem for e in cenario.resolver(AGORA)}
        assert origens <= {Origem.MANUTENCAO}, cenario.chave


def test_os_tres_tipos_de_evento_aparecem_na_fabrica():
    # Avaria, alerta preditivo e serviço programado precisam existir no conjunto dos
    # cenários — é o que faz a régua de cor inteira ter o que mostrar.
    gravidades = {
        e.gravidade for cenario in sc.CENARIOS for e in cenario.resolver(AGORA)
    }
    assert gravidades == {Gravidade.PARADA, Gravidade.DEGRADACAO, Gravidade.PLANEJADA}


def test_tudo_rodando_e_a_lista_vazia():
    assert sc.TUDO_RODANDO.resolver(AGORA) == []
    assert pj.cor_dos_conjuntos(sc.TUDO_RODANDO.resolver(AGORA)) == {}


def test_todo_conjunto_citado_existe_no_desenho():
    conhecidas = chaves_conhecidas()
    for cenario in sc.CENARIOS:
        for e in cenario.eventos:
            assert e.conjunto in conhecidas, f"{cenario.chave}: {e.conjunto}"


def test_cenario_desconhecido_cai_no_de_entrada():
    assert sc.cenario(None).chave == sc.CENARIO_PADRAO
    assert sc.cenario("nao-existe").chave == sc.CENARIO_PADRAO


def test_datas_sao_relativas_ao_momento_da_visita():
    outro = AGORA + timedelta(days=30)
    primeiro = sc.AVARIA_EM_CURSO.resolver(AGORA)[0]
    depois = sc.AVARIA_EM_CURSO.resolver(outro)[0]
    assert depois.inicio - primeiro.inicio == timedelta(days=30)


def test_turno_normal_abre_com_atencao_e_sem_parada():
    # É o cenário de entrada: precisa mostrar que a tela tem o que dizer sem nada quebrado —
    # alertas abertos em linhas diferentes e nenhum vermelho.
    cores = pj.cor_dos_ativos(sc.TURNO_NORMAL.resolver(AGORA), AGORA)
    assert Cor.VERMELHO not in cores.values()
    assert len([c for c in cores.values() if c is Cor.AMARELO]) >= 3


def test_nenhum_cenario_pinta_a_fabrica_inteira():
    # Precisa sobrar verde para contraste (BR-07).
    for cenario in sc.CENARIOS:
        com_evento = {e.ativo for e in cenario.resolver(AGORA)}
        assert len(com_evento) < len(conjuntos_por_ativo()), cenario.chave


COM_PARADA = {"avaria-em-curso", "avaria-eletrica", "duas-linhas-paradas"}


def test_so_os_cenarios_de_avaria_tem_conjunto_parado():
    # Vermelho é o recurso mais forte da tela. Espalhá-lo por todo cenário faria a fábrica
    # parecer permanentemente quebrada e tiraria o peso justamente de quando ela está.
    for cenario in sc.CENARIOS:
        cores = pj.cor_dos_conjuntos(cenario.resolver(AGORA))
        vermelhos = [c for c in cores.values() if c is Cor.VERMELHO]
        if cenario.chave in COM_PARADA:
            assert vermelhos, cenario.chave
        else:
            assert not vermelhos, cenario.chave


def test_nenhum_cenario_para_mais_de_duas_linhas():
    # Três linhas paradas ao mesmo tempo já não é um dia ruim: é um evento de fábrica, e a
    # tela passaria a ilustrar uma situação que o protótipo não se propõe a contar.
    for cenario in sc.CENARIOS:
        cores = pj.cor_dos_ativos(cenario.resolver(AGORA), AGORA)
        parados = [a for a, c in cores.items() if c is Cor.VERMELHO]
        assert len(parados) <= 2, (cenario.chave, parados)


def test_avaria_mostra_os_sinais_que_a_precederam():
    # A página do ativo precisa mostrar a avaria e o que veio antes dela.
    eventos = sc.AVARIA_EM_CURSO.resolver(AGORA)
    tabelas = pj.falhas_por_conjunto(eventos, "LCT16")
    avaria = next(e for e in tabelas["LCT16.APLANADORA"] if e.gravidade is Gravidade.PARADA)
    anteriores = [e for e in tabelas["LCT16.APLANADORA"] if e.gravidade is Gravidade.DEGRADACAO]
    assert anteriores and all(e.inicio < avaria.inicio for e in anteriores)


def test_cenario_com_conjunto_inexistente_quebra_na_subida():
    ruim = sc.Cenario(
        chave="ruim", rotulo="Ruim", resumo="",
        eventos=(sc.EventoMockado("LCP01.NAO_EXISTE", P, DEG, 1.0, None, "x"),),
    )
    original = sc.CENARIOS
    try:
        sc.CENARIOS = original + (ruim,)
        with pytest.raises(sc.CenarioInvalido) as erro:
            sc._validar()
        assert "não existem no desenho" in str(erro.value)
    finally:
        sc.CENARIOS = original


# --------------------------------------------------------------------------- #
# BR-02 — a cor é do estado atual, não do histórico
# --------------------------------------------------------------------------- #


def test_evento_fechado_nao_pinta_mais_a_maquina():
    # A prensa quebrou ontem e foi consertada. Hoje ela está rodando: sem este recorte, uma
    # quebra resolvida deixaria a máquina vermelha para sempre.
    resolvida = evento(M, PAR, ha_horas=30, durou=2)
    assert pj.cor_dos_conjuntos([resolvida], agora=AGORA) == {}
    assert pj.cor_dos_ativos([resolvida], agora=AGORA) == {}
    assert pj.ativos_piscando([resolvida], agora=AGORA) == set()


def test_conjunto_cai_de_vermelho_para_amarelo_quando_a_parada_fecha():
    # Exemplo da própria BR-02: a bobina chega, a parada fecha, e o alerta preditivo que
    # continua aberto passa a mandar na cor.
    parada_fechada = evento(P, PAR, ha_horas=6, durou=4)
    alerta_aberto = evento(M, DEG, ha_horas=48)
    cores = pj.cor_dos_conjuntos([parada_fechada, alerta_aberto], agora=AGORA)
    assert cores[CONJ] is Cor.AMARELO


def test_historico_continua_na_tabela_e_na_linha_do_tempo():
    # O que saiu da cor não sai da história: a tabela e a faixa continuam mostrando.
    resolvida = evento(M, PAR, ha_horas=6, durou=2)
    assert list(pj.falhas_por_conjunto([resolvida], "LCP01")) == [CONJ]
    faixas = pj.faixas_da_timeline([resolvida], "LCP01", agora=AGORA)
    assert Cor.VERMELHO in [f.cor for f in faixas]
    assert faixas[-1].cor is Cor.VERDE   # e no fim da janela a linha já estava rodando


def test_todo_cenario_com_evento_tem_historico_fechado():
    # É o histórico que dá o que ver na página do ativo — sem ele, a linha do tempo vira
    # uma faixa só e as tabelas, uma linha só.
    for cenario in sc.CENARIOS:
        if not cenario.eventos:
            continue
        fechados = [e for e in cenario.resolver(AGORA) if not e.em_curso]
        assert len(fechados) >= 3, cenario.chave


def test_todo_cenario_com_evento_cobre_mais_de_um_ativo():
    for cenario in sc.CENARIOS:
        if not cenario.eventos:
            continue
        assert len({e.ativo for e in cenario.resolver(AGORA)}) >= 3, cenario.chave


def test_card_de_preventiva_nao_aparece_sob_so_producao():
    # A preventiva sobrevive ao filtro para a máquina não aparecer verde estando parada
    # (BR-04), mas o card dela é de manutenção e sai da faixa (BR-05).
    preventiva = evento(M, PLA, ha_horas=3)
    filtrados = pj.filtrar([preventiva], Escopo.PRODUCAO)
    assert filtrados == [preventiva]                                    # a cor continua cinza
    chaves = [c.chave for c in pj.cards(filtrados, "LCP01", agora=AGORA, escopo=Escopo.PRODUCAO)]
    assert chaves == ["estado"]
    # sem filtro, o card está lá
    completos = [c.chave for c in pj.cards(filtrados, "LCP01", agora=AGORA)]
    assert "preventiva" in completos


# --------------------------------------------------------------------------- #
# o mapa que vai para o desenho — verde é afirmado, não ausência
# --------------------------------------------------------------------------- #


def test_mapa_de_estados_pinta_todo_conjunto_do_inventario():
    # Regressão: verde era omitido do mapa ("ausência de instrução") e a máquina ficava
    # branca — a carcaça do mockup — em vez de verde. Cenário "tudo rodando" saía sem cor.
    mapa = color_style.mapa_de_estados({})
    assert mapa["conjuntos"], "mapa vazio deixaria a planta inteira branca"
    assert set(mapa["conjuntos"]) == set(chaves_conhecidas())
    assert set(mapa["conjuntos"].values()) == {Cor.VERDE.value}


def test_mapa_de_estados_sobrescreve_o_verde_de_quem_tem_evento():
    mapa = color_style.mapa_de_estados({CONJ: Cor.VERMELHO})
    assert mapa["conjuntos"][CONJ] == Cor.VERMELHO.value
    outro = next(c for c in chaves_conhecidas() if c != CONJ)
    assert mapa["conjuntos"][outro] == Cor.VERDE.value


# --------------------------------------------------------------------------- #
# o texto dos eventos — linguagem de monitoramento, não de nota preenchida
# --------------------------------------------------------------------------- #


def test_evento_medido_traz_numero_na_descricao():
    # BR-07: a descrição é o que o monitoramento diria. Avaria e anomalia sempre têm grandeza
    # medida, código de falha ou marcação de projeto — "rolamento com vibração alta" é nota de
    # gente, "7,1 mm/s RMS (alarme 4,5)" é leitura de sistema.
    for cenario in sc.CENARIOS:
        for evento in cenario.resolver(AGORA):
            if evento.gravidade is Gravidade.PLANEJADA:
                continue
            assert re.search(r"\d", evento.descricao), (cenario.chave, evento.descricao)


def test_marcacao_de_projeto_aparece_na_maioria_dos_eventos():
    # Motor M04, drive U31, sensor B12, emergência S14: sem a marcação, a tela vira relato.
    eventos = [e for c in sc.CENARIOS for e in c.resolver(AGORA)]
    com_tag = [e for e in eventos if re.search(r"\b[A-Z]{1,2}\d{2}\b", e.descricao)]
    assert len(com_tag) >= len(eventos) * 0.4


def test_todo_cenario_tem_conjunto_com_mais_de_um_evento():
    # Conjunto com problema raramente gera um registro só: o desvio aparece em mais de uma
    # grandeza e o intertravamento entra depois da falha de origem. Uma tabela de uma linha só
    # lê como formulário preenchido uma vez, não como monitoramento.
    for cenario in sc.CENARIOS:
        if not cenario.eventos:
            continue
        contagem = Counter(e.conjunto for e in cenario.resolver(AGORA))
        assert max(contagem.values()) >= 2, cenario.chave


# --------------------------------------------------------------------------- #
# capacidade produtiva — a curva abaixo da linha do tempo
# --------------------------------------------------------------------------- #


def test_capacidade_cai_a_zero_com_a_linha_parada():
    # Avaria em curso: a linha não entrega nada enquanto está bloqueada.
    eventos = [evento(M, PAR, ha_horas=2)]
    curva = pj.curva_de_capacidade(eventos, "LCP01", agora=AGORA)
    assert curva[-1].percentual == 0.0
    assert pj.capacidade_agora(curva) == 0.0


def test_parada_prevista_tambem_zera_a_entrega():
    # Estava previsto, mas a linha continua não produzindo — quem lê "quanto saiu" precisa ver
    # zero; que era previsto, a faixa de estados logo acima já diz.
    curva = pj.curva_de_capacidade([evento(M, PLA, ha_horas=2)], "LCP01", agora=AGORA)
    assert curva[-1].percentual == 0.0


def test_anomalia_aberta_roda_abaixo_do_maximo():
    curva = pj.curva_de_capacidade([evento(M, DEG, ha_horas=5)], "LCP01", agora=AGORA)
    piso, teto = pj.FAIXA_DE_CAPACIDADE[Cor.AMARELO]
    assert piso <= curva[-1].percentual <= teto
    assert curva[-1].percentual < pj.FAIXA_DE_CAPACIDADE[Cor.VERDE][0]


def test_linha_sem_evento_entrega_perto_do_maximo():
    curva = pj.curva_de_capacidade([], "LCP02", agora=AGORA)
    piso, teto = pj.FAIXA_DE_CAPACIDADE[Cor.VERDE]
    assert all(piso <= p.percentual <= teto for p in curva)
    assert pj.capacidade_media(curva) >= piso


def test_a_curva_nao_muda_entre_visitas():
    # A oscilação é calculada, não sorteada: a mesma tela precisa contar a mesma história duas
    # vezes seguidas — inclusive na mesma reunião.
    primeira = pj.curva_de_capacidade([], "LCT16", agora=AGORA)
    segunda = pj.curva_de_capacidade([], "LCT16", agora=AGORA)
    assert [p.percentual for p in primeira] == [p.percentual for p in segunda]


def test_ativos_diferentes_tem_curvas_diferentes():
    # Mesma condição, curvas distintas: duas linhas com o mesmo traçado denunciariam o dado.
    a = [p.percentual for p in pj.curva_de_capacidade([], "LCT16", agora=AGORA)]
    b = [p.percentual for p in pj.curva_de_capacidade([], "LCP01", agora=AGORA)]
    assert a != b


def test_capacidade_acompanha_a_linha_do_tempo():
    # As duas leem a mesma lista de eventos: onde a faixa está vermelha, a curva está no chão.
    eventos = sc.AVARIA_EM_CURSO.resolver(AGORA)
    curva = pj.curva_de_capacidade(eventos, "LCT16", agora=AGORA)
    faixas = pj.faixas_da_timeline(eventos, "LCT16", agora=AGORA)
    for ponto in curva:
        faixa = next((f for f in faixas if f.inicio <= ponto.instante < f.fim), None)
        if faixa is None:
            continue
        piso, teto = pj.FAIXA_DE_CAPACIDADE[faixa.cor]
        assert piso <= ponto.percentual <= teto, (faixa.cor, ponto)
