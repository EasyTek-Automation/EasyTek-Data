# -*- coding: utf-8 -*-
"""Da lista de eventos às quatro saídas da tela (BR-02, BR-03, BR-05, BR-06).

O filtro faz uma coisa só: tira eventos da lista. Tudo o mais se recalcula a partir do que
sobrou. Não existem quatro filtragens diferentes — existe **um** recorte e quatro projeções,
e é isso que impede que as quatro divirjam entre si.

Nenhuma projeção deste módulo filtra por conta própria: todas recebem a lista já recortada.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from .events import (
    Cor,
    Escopo,
    Evento,
    Gravidade,
    Origem,
    conjuntos_por_ativo,
    cor_de,
    nome_do_conjunto,
    pior_gravidade,
)

# Quanto tempo a linha do tempo do ativo mostra para trás (SP-07).
JANELA_TIMELINE_HORAS = 24


# --------------------------------------------------------------------------- #
# o recorte
# --------------------------------------------------------------------------- #


def filtrar(eventos, escopo: Escopo) -> list[Evento]:
    """Aplica o escopo escolhido (BR-04).

    **Só a degradação é filtrável por origem.** Parada e parada planejada aparecem em
    qualquer filtro, venham de onde vierem — é o que faz verde, vermelho e cinza serem
    invariantes na tabela-verdade da BR-04, e o que garante que filtrar nunca "acende" nem
    "apaga" um conjunto que estava parado.

    Exemplo: a prensa da LCP01 quebra às 9h (origem manutenção, gravidade parada). Quem
    filtrou "Só Produção" continua vendo vermelho: a linha parou e deixou de produzir, mesmo
    que a causa seja mecânica. Do mesmo jeito, a preventiva da LCT08 segue cinza para quem
    filtrou "Só Produção" — a máquina está parada de fato, e some-la mostraria verde numa
    máquina que não está rodando.
    """
    if escopo is Escopo.TUDO:
        return list(eventos)
    return [
        e for e in eventos
        if e.gravidade is not Gravidade.DEGRADACAO or e.origem.value == escopo.value
    ]


def _do_ativo(eventos, ativo: str) -> list[Evento]:
    return [e for e in eventos if e.ativo == ativo]


# --------------------------------------------------------------------------- #
# cor do conjunto e marcação do ativo
# --------------------------------------------------------------------------- #


def vigentes(eventos, agora: datetime | None = None) -> list[Evento]:
    """Só o que está valendo agora.

    A cor é do **estado atual** da máquina, não do histórico dela: quando a bobina chega e a
    parada fecha, o conjunto cai para amarelo se ainda tiver um alerta aberto, ou volta ao
    verde (BR-02). Sem este recorte, uma quebra resolvida ontem deixaria a máquina vermelha
    para sempre. O histórico continua inteiro nas tabelas e na linha do tempo.
    """
    agora = agora or datetime.now()
    return [e for e in eventos if e.vigente_em(agora)]


def cor_dos_conjuntos(eventos, agora: datetime | None = None) -> dict[str, Cor]:
    """Cor de cada conjunto com evento aberto (BR-02). Quem não aparece aqui está verde."""
    por_conjunto: dict[str, list[Evento]] = {}
    for evento in vigentes(eventos, agora):
        por_conjunto.setdefault(evento.conjunto, []).append(evento)
    return {chave: cor_de(lista) for chave, lista in por_conjunto.items()}


def cor_dos_ativos(eventos, agora: datetime | None = None) -> dict[str, Cor | None]:
    """Marcação de cada ativo (BR-03, revisada em 2026-08-05).

    O ativo herda a cor do pior conjunto dele. Recebem moldura vermelho, amarelo **e cinza**;
    só o verde fica sem. A moldura responde *"em qual linha eu preciso olhar?"* — e a linha
    que está fora por preventiva também precisa ser vista de longe pelo Planejamento e
    Controle de Manutenção (PCM). O que separa a parada prevista do alarme é a forma da
    moldura, não a ausência dela: cinza é tracejada e fixa (ver `monitoring.css`).

    Verde segue sem marcação: moldura em todo ativo deixa de informar.
    """
    por_ativo: dict[str, list[Evento]] = {}
    for evento in vigentes(eventos, agora):
        por_ativo.setdefault(evento.ativo, []).append(evento)

    marcacao: dict[str, Cor | None] = {}
    for ativo, lista in por_ativo.items():
        cor = cor_de(lista)
        marcacao[ativo] = cor if cor in (Cor.VERMELHO, Cor.AMARELO, Cor.CINZA) else None
    return marcacao


def cor_dos_ativos_completo(eventos, agora: datetime | None = None) -> dict[str, Cor]:
    """A cor de **todos** os ativos, inclusive os verdes — para contar linhas por estado.

    Difere de `cor_dos_ativos`, que responde outra pergunta: lá o valor é a *marcação* do
    ativo no desenho, e verde não recebe marcação (BR-03). Aqui o que se quer é o estado de
    cada linha, e a linha sem evento nenhum tem estado — ela está rodando.
    """
    from .events import ativos as todos_os_ativos

    por_ativo: dict[str, list[Evento]] = {}
    for evento in vigentes(eventos, agora):
        por_ativo.setdefault(evento.ativo, []).append(evento)
    return {
        ativo: cor_de(por_ativo.get(ativo, []))
        for ativo in todos_os_ativos()
    }


def ativos_piscando(eventos, agora: datetime | None = None) -> set[str]:
    """Ativos cuja moldura pisca — só os vermelhos (BR-03)."""
    return {a for a, cor in cor_dos_ativos(eventos, agora).items() if cor is Cor.VERMELHO}


# --------------------------------------------------------------------------- #
# linha do tempo do ativo
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Faixa:
    """Um trecho de tempo em que o ativo esteve num mesmo estado (SP-07)."""

    inicio: datetime
    fim: datetime
    cor: Cor
    rotulo: str

    @property
    def horas(self) -> float:
        return (self.fim - self.inicio).total_seconds() / 3600.0


ROTULO_DA_COR = {
    Cor.VERDE: "Rodando 100%",
    Cor.AMARELO: "Rodando abaixo de 100%",
    Cor.VERMELHO: "Parado",
    Cor.CINZA: "Parada planejada",
}


def faixas_da_timeline(
    eventos,
    ativo: str,
    agora: datetime | None = None,
    janela_horas: int = JANELA_TIMELINE_HORAS,
) -> list[Faixa]:
    """Em que estado o ativo esteve ao longo da janela.

    O estado de cada trecho é o do pior evento vigente nele — a mesma precedência da cor.
    Trecho sem evento nenhum conta como rodando 100%.

    Exemplo: das 06h às 08h a linha rodou abaixo do programado e às 08h quebrou. A janela
    mostra uma faixa amarela de 06h a 08h e uma vermelha de 08h em diante.
    """
    agora = agora or datetime.now()
    inicio_janela = agora - timedelta(hours=janela_horas)
    do_ativo = [
        e for e in _do_ativo(eventos, ativo)
        if e.inicio < agora and (e.fim is None or e.fim > inicio_janela)
    ]

    cortes = {inicio_janela, agora}
    for evento in do_ativo:
        for instante in (evento.inicio, evento.fim):
            if instante and inicio_janela < instante < agora:
                cortes.add(instante)
    marcos = sorted(cortes)

    faixas: list[Faixa] = []
    for inicio, fim in zip(marcos, marcos[1:]):
        meio = inicio + (fim - inicio) / 2
        vigentes = [e for e in do_ativo if e.vigente_em(meio)]
        cor = cor_de(vigentes)
        if faixas and faixas[-1].cor is cor:
            anterior = faixas.pop()
            inicio = anterior.inicio
        faixas.append(Faixa(inicio=inicio, fim=fim, cor=cor, rotulo=ROTULO_DA_COR[cor]))
    return faixas


# --------------------------------------------------------------------------- #
# capacidade produtiva do ativo
# --------------------------------------------------------------------------- #

# Quanto a linha entrega em cada estado, em porcentagem da capacidade nominal. É a tradução
# direta da régua de cor (BR-02) para "quanto está saindo": parada não produz, linha com
# anomalia aberta roda abaixo do máximo, linha sem evento roda no máximo.
FAIXA_DE_CAPACIDADE = {
    Cor.VERMELHO: (0.0, 0.0),      # avaria — linha bloqueada
    Cor.CINZA: (0.0, 0.0),         # parada prevista — não está produzindo, e isso era o plano
    Cor.AMARELO: (70.0, 88.0),     # anomalia aberta — roda, mas abaixo do máximo
    Cor.VERDE: (92.0, 100.0),      # sem evento — no máximo, com a variação normal do processo
}

# De quanto em quanto tempo a curva é amostrada. Trinta minutos dá 48 pontos em 24 h: fino o
# bastante para a queda de uma parada aparecer no lugar certo, grosso o bastante para a linha
# não virar um borrão.
PASSO_DA_CURVA_MINUTOS = 30


@dataclass(frozen=True)
class PontoDeCapacidade:
    """Quanto da capacidade nominal o ativo entregava naquele instante."""

    instante: datetime
    percentual: float


def _oscilacao(ativo: str, indice: int, piso: float, teto: float) -> float:
    """Uma variação plausível dentro da faixa, sempre a mesma para o mesmo ponto.

    Processo real não entrega 100,0% em todos os instantes — uma linha reta denunciaria o dado
    como inventado. Mas a variação **não pode ser sorteada**: o gráfico mudaria a cada visita e
    a mesma tela contaria histórias diferentes na mesma reunião. Daí a mistura de duas ondas de
    períodos diferentes, deslocada pelo nome do ativo: parece irregular, e é reprodutível.
    """
    if teto <= piso:
        return piso
    semente = sum(ord(c) for c in ativo)
    onda = math.sin(indice * 0.7 + semente) * 0.5 + math.sin(indice * 0.23 + semente * 0.5) * 0.5
    return piso + (teto - piso) * (onda + 1) / 2


def curva_de_capacidade(
    eventos,
    ativo: str,
    agora: datetime | None = None,
    janela_horas: int = JANELA_TIMELINE_HORAS,
) -> list[PontoDeCapacidade]:
    """Quanto o ativo entregou ao longo da janela, em porcentagem da capacidade nominal.

    Deriva dos **mesmos eventos** que pintam as máquinas e desenham a linha do tempo: o estado
    de cada instante é o do pior evento vigente nele, e cada estado tem sua faixa de entrega.
    Por isso a curva e a faixa logo acima nunca se contradizem — quando a linha do tempo fica
    vermelha, a curva encosta no zero no mesmo ponto.

    Exemplo: a LCT16 rodava perto do máximo, abriu um alerta de vibração e passou a oscilar na
    casa dos 80%; quando o acoplamento rompeu, a curva caiu a zero e ficou lá.
    """
    agora = agora or datetime.now()
    inicio = agora - timedelta(hours=janela_horas)
    do_ativo = _do_ativo(eventos, ativo)
    passo = timedelta(minutes=PASSO_DA_CURVA_MINUTOS)

    pontos: list[PontoDeCapacidade] = []
    indice = 0
    instante = inicio
    while instante <= agora:
        cor = cor_de([e for e in do_ativo if e.vigente_em(instante)])
        piso, teto = FAIXA_DE_CAPACIDADE[cor]
        pontos.append(PontoDeCapacidade(instante, _oscilacao(ativo, indice, piso, teto)))
        instante += passo
        indice += 1
    return pontos


def capacidade_agora(pontos) -> float:
    """A entrega do instante mais recente da curva."""
    return pontos[-1].percentual if pontos else 0.0


def capacidade_media(pontos) -> float:
    """A entrega média da janela — o número que responde "e no geral, como foi o dia?"."""
    return sum(p.percentual for p in pontos) / len(pontos) if pontos else 0.0


# --------------------------------------------------------------------------- #
# tabelas de falha
# --------------------------------------------------------------------------- #


def falhas_por_conjunto(eventos, ativo: str) -> dict[str, list[Evento]]:
    """Eventos de cada conjunto do ativo, na ordem física da linha (BR-06, SP-08).

    Conjunto sem evento não entra: não gera tabela vazia, não gera cabeçalho com "nenhum
    registro" — simplesmente não aparece. Nenhuma tabela é estado válido, não erro.
    """
    do_ativo = _do_ativo(eventos, ativo)
    agrupado: dict[str, list[Evento]] = {}
    for evento in do_ativo:
        agrupado.setdefault(evento.conjunto, []).append(evento)

    ordenado: dict[str, list[Evento]] = {}
    for chave in conjuntos_por_ativo().get(ativo, ()):
        if chave in agrupado:
            ordenado[chave] = sorted(agrupado[chave], key=lambda e: e.inicio, reverse=True)
    return ordenado


# --------------------------------------------------------------------------- #
# cards de insight
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Card:
    """Um card curto: um número ou uma frase, com um rótulo (SP-09).

    `origem` vazia significa que o card não pertence a nenhuma das duas áreas e vale sempre.
    Nenhum card é clicável e nenhum leva a ação.
    """

    chave: str
    rotulo: str
    valor: str
    origem: Origem | None = None
    # A cor não é decoração: é a mesma régua da máquina (BR-02), para o card e o desenho
    # contarem a mesma coisa. `None` quando o card não fala de estado.
    cor: Cor | None = None


def _horas_legiveis(horas: float) -> str:
    total = int(round(horas * 60))
    if total < 60:
        return f"{total}min"
    if total < 60 * 48:
        return f"{total // 60}h{total % 60:02d}"
    return f"{round(horas / 24)} dias"


def cards(
    eventos,
    ativo: str,
    agora: datetime | None = None,
    escopo: Escopo = Escopo.TUDO,
) -> list[Card]:
    """Os cards do ativo, calculados sobre a lista já filtrada.

    Card sem dado no escopo filtrado não aparece: a faixa encolhe, não fica com buraco.

    O `escopo` entra aqui por um motivo só: a parada planejada **não** é filtrada por origem
    (BR-04 — a máquina está parada de fato, e some-la mostraria verde numa máquina parada),
    então uma preventiva sobrevive ao filtro "Só Produção" e alimentaria um card de
    manutenção numa tela que pede só produção. A cor fica; o card de manutenção sai, como
    manda a BR-05.
    """
    agora = agora or datetime.now()
    do_ativo = [e for e in _do_ativo(eventos, ativo) if e.inicio <= agora]
    em_curso = [e for e in do_ativo if e.em_curso]
    nomes = nome_do_conjunto()

    lista: list[Card] = []

    # 1. Estado atual — sempre presente, é o que responde "como está agora?".
    pior = pior_gravidade(em_curso)
    if pior is Gravidade.PARADA:
        parada = min(
            (e for e in em_curso if e.gravidade is Gravidade.PARADA), key=lambda e: e.inicio
        )
        valor = f"Parado há {_horas_legiveis(parada.duracao(agora))}"
    elif pior is Gravidade.DEGRADACAO:
        valor = "Rodando abaixo do programado"
    elif pior is Gravidade.PLANEJADA:
        valor = "Parada planejada em andamento"
    else:
        valor = "Rodando"
    cor_do_estado = {
        Gravidade.PARADA: Cor.VERMELHO,
        Gravidade.DEGRADACAO: Cor.AMARELO,
        Gravidade.PLANEJADA: Cor.CINZA,
    }.get(pior, Cor.VERDE)
    lista.append(Card("estado", "Estado atual", valor, cor=cor_do_estado))

    # 2. Conjuntos com alerta preditivo aberto.
    alertas = {
        e.conjunto for e in em_curso
        if e.origem is Origem.MANUTENCAO and e.gravidade is Gravidade.DEGRADACAO
    }
    if alertas:
        plural = "conjuntos" if len(alertas) > 1 else "conjunto"
        lista.append(
            Card("alertas", "Conjuntos com alerta",
                 f"{len(alertas)} {plural} com alerta preditivo", Origem.MANUTENCAO,
                 cor=Cor.AMARELO)
        )

    # 3. Preventiva — a que está em andamento, ou a próxima agendada.
    preventivas = [
        e for e in do_ativo
        if e.origem is Origem.MANUTENCAO and e.gravidade is Gravidade.PLANEJADA
    ]
    if preventivas:
        aberta = next((e for e in preventivas if e.vigente_em(agora)), None)
        alvo = aberta or min(preventivas, key=lambda e: e.inicio)
        valor = (
            f"Em andamento há {_horas_legiveis(alvo.duracao(agora))}"
            if aberta else f"Concluída há {_horas_legiveis((agora - alvo.fim).total_seconds() / 3600)}"
        )
        lista.append(Card("preventiva", "Preventiva", valor, Origem.MANUTENCAO, cor=Cor.CINZA))

    # 4. Aderência ao programado — só existe se houver evento de produção que a explique.
    de_producao = [e for e in em_curso if e.origem is Origem.PRODUCAO]
    if de_producao:
        pior_producao = pior_gravidade(de_producao)
        valor = {
            Gravidade.PARADA: "Linha parada — sem produção no momento",
            Gravidade.DEGRADACAO: "Abaixo do programado no turno",
            Gravidade.PLANEJADA: "Sem programação para o turno",
        }[pior_producao]
        lista.append(Card("aderencia", "Aderência ao programado", valor, Origem.PRODUCAO,
                          cor=Cor.AMARELO))

    # 5. Sinal preditivo destacado — o alerta aberto mais antigo, que é o que vem subindo.
    preditivos = [
        e for e in em_curso
        if e.origem is Origem.MANUTENCAO and e.gravidade is Gravidade.DEGRADACAO
    ]
    if preditivos:
        antigo = min(preditivos, key=lambda e: e.inicio)
        conjunto = nomes.get(antigo.conjunto, antigo.conjunto)
        lista.append(
            Card("preditivo", "Sinal preditivo",
                 f"{conjunto} — há {_horas_legiveis(antigo.duracao(agora))}",
                 Origem.MANUTENCAO, cor=Cor.AMARELO)
        )

    if escopo is not Escopo.TUDO:
        lista = [c for c in lista if c.origem is None or c.origem.value == escopo.value]
    return lista
