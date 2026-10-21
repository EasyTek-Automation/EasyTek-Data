# -*- coding: utf-8 -*-
"""Os retratos mockados da fábrica (BR-07).

Cada cenário é uma lista de eventos, e cada cenário tem um trabalho: mostrar uma situação
diferente da manutenção. O primeiro deles prova a mais simples — verde é ausência de evento, e
por isso "Tudo rodando" é literalmente a lista vazia.

#### Linguagem de sistema, não de nota

As descrições são escritas como o **monitoramento diria**, não como alguém preencheria uma
nota: identificação do componente pela marcação de projeto, natureza do desvio e valor medido
contra a referência. "Falha drive U31 desbobinador — F0002 sobrecorrente, bloqueio permanente"
em vez de "inversor com problema"; "Vibração rolamento LA motor M04 — 7,1 mm/s RMS (alarme
4,5), tendência +18% em 7 dias" em vez de "rolamento com vibração alta".

A marcação segue a convenção usual de projeto elétrico e de instrumentação:

| Prefixo | O que é |
|---------|---------|
| `M` | motor |
| `U` | drive / inversor |
| `B` | sensor, termopar, chave de posição |
| `G` | encoder |
| `S` | botoeira de emergência |
| `Q` | disjuntor |
| `K` | contator |
| `Y` | válvula |
| `F` | fluxostato |

Os códigos de falha (`F0001`, `F0002`, `F0007`) seguem o padrão de inversor de frequência —
sobrecorrente, sobrecarga e sobretensão de circuito intermediário.

#### Vários eventos no mesmo conjunto

Um conjunto com problema raramente gera **um** registro: o desvio aparece em mais de uma
grandeza, e o intertravamento entra depois da falha de origem. Por isso os cenários trazem, de
propósito, dois ou três eventos no mesmo conjunto — é o que faz a tabela do ativo parecer uma
lista de monitoramento e não um formulário preenchido uma vez.

#### Só manutenção

Desde 2026-08-05 todo evento aqui é de **manutenção**: avaria, alerta preditivo ou serviço
programado. A tela deixou de misturar as duas origens — e, sem essa mistura, o filtro "só
produção / só manutenção" perdeu o sentido e saiu da interface. Espera de bobina, falta de
programação e cadência comercial não aparecem mais: quem olha esta tela quer saber o que a
manutenção precisa fazer, e um vermelho de falta de material só disputaria a atenção com o
vermelho que exige ferramenta na mão.

#### Eventos abertos e histórico

Cada cenário tem duas camadas. Os eventos **abertos** são o que se vê na cor das máquinas
agora. Os **fechados** são o que aconteceu nas últimas horas: não pintam nada (BR-02 — a cor é
do estado atual), mas enchem a linha do tempo do ativo e as tabelas por conjunto. É o que faz
a página do ativo contar uma história em vez de mostrar uma linha só.

#### Datas relativas ao momento da visita

Os cenários não guardam data absoluta: guardam deslocamento em horas em relação a agora, e o
instante é resolvido quando a página é montada. Um protótipo com "avaria iniciada em
04/08/2026" fica visivelmente velho três semanas depois, e a demo precisa continuar
apresentável sem manutenção.

#### Validação na importação

Toda chave de conjunto citada aqui é conferida contra o inventário do desenho preparado. Chave
inexistente quebra a subida da aplicação, com mensagem clara: um evento apontando para
conjunto que não existe seria invisível — nenhuma máquina acenderia e nada acusaria o erro.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .events import Evento, Gravidade, Origem, chaves_conhecidas


class CenarioInvalido(RuntimeError):
    """Cenário citando conjunto que não existe no desenho."""


@dataclass(frozen=True)
class EventoMockado:
    """Um evento ainda sem data: guarda há quantas horas começou e quanto durou."""

    conjunto: str
    origem: Origem
    gravidade: Gravidade
    ha_horas: float                  # começou há quantas horas
    durou_horas: float | None        # None = ainda em curso
    descricao: str

    def resolver(self, agora: datetime) -> Evento:
        inicio = agora - timedelta(hours=self.ha_horas)
        fim = None if self.durou_horas is None else inicio + timedelta(hours=self.durou_horas)
        return Evento(
            conjunto=self.conjunto,
            origem=self.origem,
            gravidade=self.gravidade,
            inicio=inicio,
            fim=fim,
            descricao=self.descricao,
        )


@dataclass(frozen=True)
class Cenario:
    chave: str
    rotulo: str
    resumo: str
    eventos: tuple[EventoMockado, ...]

    def resolver(self, agora: datetime | None = None) -> list[Evento]:
        """A lista de eventos com data e hora, ancorada no momento da visita."""
        agora = agora or datetime.now()
        return [e.resolver(agora) for e in self.eventos]


P, M = Origem.PRODUCAO, Origem.MANUTENCAO
DEG, PAR, PLA = Gravidade.DEGRADACAO, Gravidade.PARADA, Gravidade.PLANEJADA


TUDO_RODANDO = Cenario(
    chave="tudo-rodando",
    rotulo="Tudo rodando",
    resumo="Nenhum evento aberto na fábrica — a planta inteira verde.",
    # Lista vazia de propósito (BR-07): verde é ausência de evento, e este cenário é a prova
    # de que isso não precisa de tratamento especial nenhum.
    eventos=(),
)

TURNO_NORMAL = Cenario(
    chave="turno-normal",
    rotulo="Turno normal",
    resumo="Nada parado: quatro conjuntos com anomalia de tendência aberta e o registro do "
           "que foi normalizado no turno da noite.",
    eventos=(
        # --- aberto agora ---
        EventoMockado(
            "LCP01.APLANADORA", M, DEG, ha_horas=74.0, durou_horas=None,
            descricao="Vibração rolamento LA motor M04 aplanadora — 7,1 mm/s RMS "
                      "(alarme 4,5 / trip 9,0), tendência +18% em 7 dias.",
        ),
        EventoMockado(
            "LCP01.APLANADORA", M, DEG, ha_horas=50.0, durou_horas=None,
            descricao="Temperatura mancal LOA sensor B12 — 71 °C, ΔT +9 °C sobre a linha de "
                      "base para a mesma carga.",
        ),
        EventoMockado(
            "LCT08.TRACIONADOR_MEDICAO", M, DEG, ha_horas=19.0, durou_horas=None,
            descricao="Encoder G21 rolo tracionador — desvio de contagem ±2,1 mm por ciclo, "
                      "fora da faixa de repetibilidade (±0,5).",
        ),
        EventoMockado(
            "LCT08.TRACIONADOR_MEDICAO", M, DEG, ha_horas=14.0, durou_horas=None,
            descricao="Drive U18 tracionador — corrente 92% da nominal em regime, escorregamento "
                      "estimado 3,4%.",
        ),
        EventoMockado(
            "LCT2,5.CISALHA_ROTATIVA", M, DEG, ha_horas=31.0, durou_horas=None,
            descricao="Contador de ciclos porta-facas em 92% do intervalo de troca "
                      "(184.000 de 200.000 golpes).",
        ),
        # --- normalizado nas últimas horas ---
        EventoMockado(
            "LCP02.PRENSA_FAGOR", M, PAR, ha_horas=21.0, durou_horas=1.8,
            descricao="Falha pressostato B31 circuito hidráulico — sinal intermitente, "
                      "intertravamento de ciclo atuado.",
        ),
        EventoMockado(
            "LCP02.PRENSA_FAGOR", M, DEG, ha_horas=24.0, durou_horas=3.0,
            descricao="Pressão de trabalho oscilando 148–172 bar (referência 165 ±5) antes do "
                      "bloqueio.",
        ),
        EventoMockado(
            "LCP02.ALIMENTADOR", M, DEG, ha_horas=27.0, durou_horas=3.5,
            descricao="Servo alimentador U07 — erro de posicionamento 0,8 mm acumulado a cada "
                      "12 avanços.",
        ),
        EventoMockado(
            "LCT08.FACA_DE_DESPONTE", M, PLA, ha_horas=27.0, durou_horas=1.5,
            descricao="Janela de manutenção programada — troca do jogo de facas de desponte, "
                      "plano semanal.",
        ),
        EventoMockado(
            "LWB.RYDI_DIMPLING", M, DEG, ha_horas=16.0, durou_horas=4.0,
            descricao="Pressão cilindro de estampagem 42 bar (setpoint 50) — reguladora Y09 "
                      "substituída.",
        ),
        EventoMockado(
            "LWB.ITAB", M, DEG, ha_horas=11.0, durou_horas=1.2,
            descricao="Sensor de presença B04 mesa — 1 falso negativo a cada 20 peças, "
                      "sinal abaixo do limiar.",
        ),
        EventoMockado(
            "LCL08.ENROLADOR_DE_APARAS", M, PAR, ha_horas=34.0, durou_horas=2.4,
            descricao="Falha drive U22 enrolador de aparas — F0002 sobrecorrente, eixo "
                      "travado por acúmulo de material.",
        ),
        EventoMockado(
            "LCL08.ENROLADOR_DE_APARAS", M, DEG, ha_horas=40.0, durou_horas=6.0,
            descricao="Torque médio do enrolador 22% acima da referência nas 6 h anteriores ao "
                      "bloqueio.",
        ),
    ),
)

ALERTAS_PREDITIVOS = Cenario(
    chave="alertas-preditivos",
    rotulo="Onda de alertas preditivos",
    resumo="Onze anomalias de tendência abertas em seis linhas — vibração, temperatura, "
           "óleo, corrente e potência ótica. Nada parou; é o momento de decidir onde entrar.",
    eventos=(
        # --- vibração ---
        EventoMockado(
            "LCT16.ENDIREITADEIRA", M, DEG, ha_horas=96.0, durou_horas=None,
            descricao="Vibração rolamento LA motor M11 — 5,8 mm/s RMS contra 3,2 de linha de "
                      "base na mesma carga.",
        ),
        EventoMockado(
            "LCT16.ENDIREITADEIRA", M, DEG, ha_horas=60.0, durou_horas=None,
            descricao="Envelope de aceleração (gE) da pista externa em 2,4 gE — banda de "
                      "defeito BPFO acima do limiar de 1,0.",
        ),
        EventoMockado(
            "LCP01.PINCH_ROLL", M, DEG, ha_horas=52.0, durou_horas=None,
            descricao="Espectro de vibração M06 com pico dominante em 2× RPM (29,6 Hz) — "
                      "assinatura de desalinhamento de acoplamento.",
        ),
        # --- temperatura ---
        EventoMockado(
            "LCT08.APLANADORA_2", M, DEG, ha_horas=40.0, durou_horas=None,
            descricao="Termopar B44 carcaça do redutor — 82 °C, ΔT +14 °C sobre a linha de "
                      "base para a mesma carga.",
        ),
        EventoMockado(
            "LCT08.APLANADORA_2", M, DEG, ha_horas=38.0, durou_horas=None,
            descricao="Nível de óleo do redutor em 61% do visor — sem queda brusca, tendência "
                      "de -3% ao dia.",
        ),
        EventoMockado(
            "LCL4,5.SEPARADOR_TENSAO", M, DEG, ha_horas=26.0, durou_horas=None,
            descricao="Temperatura de carcaça motor M17 em 78 °C (classe F, alarme 75) — "
                      "obstrução de ventilação suspeita.",
        ),
        EventoMockado(
            "LCL4,5.SEPARADOR_TENSAO", M, DEG, ha_horas=22.0, durou_horas=None,
            descricao="Corrente do drive U17 em 11,4 A contra 10,2 A de referência para a "
                      "mesma velocidade de linha.",
        ),
        # --- óleo, ótica e ar comprimido ---
        EventoMockado(
            "LCP02.DESBOBINADOR", M, DEG, ha_horas=13.0, durou_horas=None,
            descricao="Análise de óleo do redutor — Fe 42 ppm (coleta anterior 21), "
                      "viscosidade -8%, partículas ISO 20/18/15.",
        ),
        EventoMockado(
            "LWB.SSPEED_FIWI_SOLDA", M, DEG, ha_horas=64.0, durou_horas=None,
            descricao="Potência ótica de saída em 3,76 kW contra 4,00 de referência (-6%) — "
                      "atenuação na ótica de proteção.",
        ),
        EventoMockado(
            "LWB.SSPEED_FIWI_SOLDA", M, DEG, ha_horas=44.0, durou_horas=None,
            descricao="Vazão do gás de proteção 14,2 L/min (setpoint 16,0) — leitura do "
                      "fluxostato F02 em queda lenta.",
        ),
        EventoMockado(
            "LCT2,5.MESA_DE_ROLETES", M, DEG, ha_horas=34.0, durou_horas=None,
            descricao="Pressão de ar na linha da mesa em 5,1 bar (mínimo de operação 5,5) — "
                      "queda progressiva desde o turno anterior.",
        ),
        # --- histórico: as coletas que abriram os alertas ---
        EventoMockado(
            "LCT16.ENDIREITADEIRA", M, PLA, ha_horas=168.0, durou_horas=1.5,
            descricao="Rota de coleta preditiva semanal — pontos M11 LA/LOA; foi esta coleta "
                      "que abriu a anomalia de vibração.",
        ),
        EventoMockado(
            "LCP02.DESBOBINADOR", M, PLA, ha_horas=180.0, durou_horas=0.8,
            descricao="Coleta de amostra de óleo do redutor para análise laboratorial.",
        ),
        EventoMockado(
            "LCL4,5.CARRO_DE_ENFIAMENTO", M, DEG, ha_horas=44.0, durou_horas=8.0,
            descricao="Sensor fim de curso B08 com atuação intermitente — folga de batente "
                      "0,9 mm corrigida.",
        ),
        EventoMockado(
            "LWB.TUNICON", M, DEG, ha_horas=30.0, durou_horas=5.5,
            descricao="Desvio de posicionamento do transportador em 0,42 mm (tolerância "
                      "0,20) — guia reapertada e verificada com peça padrão.",
        ),
    ),
)

PARADA_PROGRAMADA = Cenario(
    chave="parada-programada",
    rotulo="Parada preventiva",
    resumo="Duas linhas em janela de manutenção programada, com as intervenções abertas "
           "conjunto a conjunto — parada prevista não é alarme.",
    eventos=(
        # --- janela aberta agora ---
        EventoMockado(
            "LCT08.TESOURA_ROTATIVA", M, PLA, ha_horas=3.0, durou_horas=None,
            descricao="Janela programada — troca do jogo de facas e lubrificação do conjunto "
                      "de corte; intervalo trimestral vencido em 2 dias.",
        ),
        EventoMockado(
            "LCT08.TESOURA_ROTATIVA", M, PLA, ha_horas=2.8, durou_horas=None,
            descricao="Inspeção do acoplamento e medição de folga do porta-facas com relógio "
                      "comparador.",
        ),
        EventoMockado(
            "LCT08.APLANADORA_1", M, PLA, ha_horas=3.0, durou_horas=None,
            descricao="Troca dos rolos de aplainamento do primeiro conjunto, aproveitando a "
                      "linha em janela.",
        ),
        EventoMockado(
            "LCT08.MESA_DE_ROLETES", M, PLA, ha_horas=2.5, durou_horas=None,
            descricao="Alinhamento da mesa e reaperto dos mancais dentro da mesma janela.",
        ),
        EventoMockado(
            "LWB.SSPEED_FIWI_SOLDA", M, PLA, ha_horas=2.0, durou_horas=None,
            descricao="Calibração da cabeça de solda e troca de bicos — intervalo semestral.",
        ),
        EventoMockado(
            "LWB.SSPEED_FIWI_SOLDA", M, PLA, ha_horas=1.8, durou_horas=None,
            descricao="Limpeza da ótica de proteção e aferição de potência com medidor "
                      "externo.",
        ),
        EventoMockado(
            "LWB.MARK_MARCACAO", M, PLA, ha_horas=2.0, durou_horas=None,
            descricao="Limpeza do cabeçote de marcação e troca do filtro de exaustão.",
        ),
        EventoMockado(
            "LWB.SUNI_STACKING", M, PLA, ha_horas=1.5, durou_horas=None,
            descricao="Troca das ventosas do empilhador — vida útil vencida (contador em "
                      "412.000 ciclos).",
        ),
        # --- o que motivou a janela, já fechado ---
        EventoMockado(
            "LCT08.DESBOBINADOR", M, DEG, ha_horas=30.0, durou_horas=26.0,
            descricao="Tempo de resposta do freio em 1,9 s (referência 0,8) — anomalia que "
                      "motivou antecipar a janela desta linha.",
        ),
        EventoMockado(
            "LCT08.DESBOBINADOR", M, DEG, ha_horas=54.0, durou_horas=20.0,
            descricao="Pressão do circuito de frenagem 12% abaixo do setpoint em três "
                      "acionamentos consecutivos.",
        ),
        EventoMockado(
            "LCP01.EMPILHADOR_1", M, DEG, ha_horas=20.0, durou_horas=5.0,
            descricao="Sensor fim de curso B15 da garra — perda de repetibilidade de 1,2 mm "
                      "entre ciclos; reposicionado.",
        ),
        EventoMockado(
            "LCT2,5.ESTEIRA_TRANSVERSAL", M, PAR, ha_horas=48.0, durou_horas=1.1,
            descricao="Falha drive U29 esteira transversal — F0007 sobretensão de circuito "
                      "intermediário na desaceleração; correia fora do rolete.",
        ),
    ),
)

PARADA_GERAL = Cenario(
    chave="parada-geral",
    rotulo="Parada geral programada",
    resumo="A grande janela do mês: quatro linhas em intervenção simultânea, com o histórico "
           "que justificou cada uma — nenhuma moldura de alarme na tela.",
    eventos=(
        # --- prensas ---
        EventoMockado(
            "LCP01.PRENSA_FAGOR", M, PLA, ha_horas=7.0, durou_horas=None,
            descricao="Revisão anual — troca do conjunto embreagem/freio e teste de tempo de "
                      "parada com cronômetro de segurança.",
        ),
        EventoMockado(
            "LCP01.PRENSA_FAGOR", M, PLA, ha_horas=6.8, durou_horas=None,
            descricao="Verificação das válvulas de segurança dupla e do bloco de "
                      "intertravamento hidráulico.",
        ),
        EventoMockado(
            "LCP01.FOSSO_DE_LACO", M, PLA, ha_horas=7.0, durou_horas=None,
            descricao="Limpeza do fosso e aferição dos sensores de laço B21–B24 com a linha "
                      "vazia.",
        ),
        EventoMockado(
            "LCP02.PRENSA_FAGOR", M, PLA, ha_horas=6.5, durou_horas=None,
            descricao="Revisão anual da segunda prensa, em paralelo com a LCP01.",
        ),
        EventoMockado(
            "LCP02.ESTEIRA_DE_SAIDA", M, PLA, ha_horas=6.0, durou_horas=None,
            descricao="Troca dos roletes de saída e do redutor do acionamento M23.",
        ),
        # --- LCT2,5 e LCL08 ---
        EventoMockado(
            "LCT2,5.APLANADORA", M, PLA, ha_horas=5.0, durou_horas=None,
            descricao="Retífica dos rolos de aplainamento — programada há dois meses, peças "
                      "em estoque reservado.",
        ),
        EventoMockado(
            "LCT2,5.DESBOBINADOR", M, PLA, ha_horas=5.0, durou_horas=None,
            descricao="Troca do redutor do desbobinador e alinhamento a laser do conjunto "
                      "motor/redutor.",
        ),
        EventoMockado(
            "LCL08.CABECOTE_DE_CORTE", M, PLA, ha_horas=4.0, durou_horas=None,
            descricao="Troca do jogo de facas circulares e ajuste de folga lateral em "
                      "0,06 mm.",
        ),
        EventoMockado(
            "LCL08.ENROLADOR", M, PLA, ha_horas=4.0, durou_horas=None,
            descricao="Inspeção do eixo expansível e troca das sapatas de aperto.",
        ),
        EventoMockado(
            "LCL08.SEPARADOR_TENSAO", M, PLA, ha_horas=3.5, durou_horas=None,
            descricao="Substituição das sapatas de fricção e teste de tensão de linha em "
                      "vazio.",
        ),
        # --- o que a janela foi resolver ---
        EventoMockado(
            "LCP01.PRENSA_FAGOR", M, DEG, ha_horas=200.0, durou_horas=193.0,
            descricao="Tempo de frenagem em 480 ms (limite de segurança 300) — anomalia que "
                      "puxou a revisão anual para esta janela.",
        ),
        EventoMockado(
            "LCT2,5.APLANADORA", M, DEG, ha_horas=150.0, durou_horas=145.0,
            descricao="Planicidade fora de faixa (I-Unit 28, limite 15) exigindo repasse — "
                      "desgaste de rolos confirmado na inspeção.",
        ),
        EventoMockado(
            "LCL08.CABECOTE_DE_CORTE", M, PAR, ha_horas=72.0, durou_horas=3.2,
            descricao="Quebra de faca circular no cabeçote 2 durante corte de material de "
                      "maior dureza — torque de corte 34% acima da referência no instante "
                      "da quebra.",
        ),
        EventoMockado(
            "LCL08.CABECOTE_DE_CORTE", M, DEG, ha_horas=96.0, durou_horas=24.0,
            descricao="Rebarba acima de 0,08 mm nas 24 h anteriores à quebra da faca.",
        ),
    ),
)

AVARIA_EM_CURSO = Cenario(
    chave="avaria-em-curso",
    rotulo="Avaria mecânica em curso",
    resumo="Acoplamento rompido na LCT16, com toda a cadeia de sinal que veio antes — e um "
           "empilhador bloqueado por emergência em outra linha.",
    eventos=(
        # --- a avaria e a cadeia que a precedeu ---
        EventoMockado(
            "LCT16.APLANADORA", M, PAR, ha_horas=2.2, durou_horas=None,
            descricao="Falha acionamento M09 aplanadora — drive U09 em F0001 sobrecorrente, "
                      "acoplamento do redutor rompido, linha bloqueada.",
        ),
        EventoMockado(
            "LCT16.APLANADORA", M, PAR, ha_horas=2.2, durou_horas=None,
            descricao="Intertravamento de linha atuado — sinal de rotação do encoder G09 "
                      "ausente com comando ativo.",
        ),
        EventoMockado(
            "LCT16.APLANADORA", M, DEG, ha_horas=120.0, durou_horas=117.8,
            descricao="Vibração rolamento LOA M09 — 9,4 mm/s RMS (trip 9,0), subindo há "
                      "5 dias.",
        ),
        EventoMockado(
            "LCT16.APLANADORA", M, DEG, ha_horas=96.0, durou_horas=93.8,
            descricao="Corrente do drive U09 com oscilação de ±14% em regime constante nas "
                      "últimas 96 h.",
        ),
        EventoMockado(
            "LCT16.APLANADORA", M, PLA, ha_horas=240.0, durou_horas=2.0,
            descricao="Rota de coleta preditiva — medição em 4,1 mm/s, dentro do limite de "
                      "alerta na ocasião.",
        ),
        EventoMockado(
            "LCT16.TRACIONADOR_MEDICAO", M, DEG, ha_horas=48.0, durou_horas=None,
            descricao="Termopar B31 redutor — 74 °C, ΔT +12 °C sobre a linha de base para a "
                      "mesma carga.",
        ),
        EventoMockado(
            "LCT16.MESA_DE_ROLETES", M, DEG, ha_horas=26.0, durou_horas=3.0,
            descricao="Folga axial de 1,4 mm nos roletes 7–9 (limite 0,5) — velocidade "
                      "reduzida até o acerto do guia.",
        ),
        # --- a segunda parada ---
        EventoMockado(
            "LCP02.EMPILHADOR_2", M, PAR, ha_horas=1.3, durou_horas=None,
            descricao="Emergência S14 empilhador 2 atuada — peça atravessada no berço, ciclo "
                      "bloqueado e área intertravada.",
        ),
        EventoMockado(
            "LCP02.EMPILHADOR_2", M, DEG, ha_horas=8.0, durou_horas=None,
            descricao="Sensor de posição B27 do berço com sinal instável nas 8 h anteriores "
                      "ao bloqueio.",
        ),
        EventoMockado(
            "LCP02.ALIMENTADOR", M, DEG, ha_horas=22.0, durou_horas=4.5,
            descricao="Servo alimentador U07 — perda de passo de 1,1 mm por avanço; corrente "
                      "de tração tensionada.",
        ),
        # --- o resto da fábrica ---
        EventoMockado(
            "LCP01.APLANADORA", M, DEG, ha_horas=74.0, durou_horas=None,
            descricao="Vibração rolamento LA M04 — 7,1 mm/s RMS (alarme 4,5), tendência de "
                      "alta há 3 dias.",
        ),
        EventoMockado(
            "LCL4,5.ENROLADOR", M, DEG, ha_horas=2.0, durou_horas=None,
            descricao="Pressão do eixo expansível oscilando 96–118 bar (setpoint 110) — "
                      "telescopagem leve na bobina.",
        ),
        EventoMockado(
            "LCT08.ESTEIRA_DE_SAIDA", M, DEG, ha_horas=15.0, durou_horas=2.5,
            descricao="Rolete 12 emperrado marcando a chapa — mancal substituído.",
        ),
        EventoMockado(
            "LWB.DBCON_DBPLA", M, DEG, ha_horas=9.0, durou_horas=5.0,
            descricao="Sensor de posição B18 da mesa oscilando entre 0 e 1 com a mesa parada; "
                      "conector reapertado.",
        ),
    ),
)

AVARIA_ELETRICA = Cenario(
    chave="avaria-eletrica",
    rotulo="Falha elétrica",
    resumo="Um barramento em falha derruba duas linhas: inversor bloqueado, disjuntor "
           "atuado, emergência acionada — e o alerta de corrente que ninguém tinha ligado.",
    eventos=(
        # --- as paradas ---
        EventoMockado(
            "LCL08.DESBOBINADOR", M, PAR, ha_horas=1.6, durou_horas=None,
            descricao="Falha drive U31 desbobinador — F0002 sobrecorrente com bloqueio "
                      "permanente, sem religamento automático.",
        ),
        EventoMockado(
            "LCL08.DESBOBINADOR", M, PAR, ha_horas=1.5, durou_horas=None,
            descricao="Falta de tensão de comando 24 Vcc no painel QP-08 — fonte em modo de "
                      "proteção.",
        ),
        EventoMockado(
            "LCL08.MESA_DE_INTRODUCAO", M, PAR, ha_horas=1.6, durou_horas=None,
            descricao="Mesa sem comando — alimentada pelo mesmo barramento do drive U31 em "
                      "falha.",
        ),
        EventoMockado(
            "LCL4,5.CARRO_DE_BOBINAS", M, PAR, ha_horas=0.8, durou_horas=None,
            descricao="Disjuntor Q12 do carro atuado por sobrecarga — rearme bloqueado até "
                      "teste de isolação do motor M12.",
        ),
        EventoMockado(
            "LCL4,5.CARRO_DE_BOBINAS", M, PAR, ha_horas=0.7, durou_horas=None,
            descricao="Emergência S03 zona do carro atuada pelo operador durante a atuação do "
                      "disjuntor.",
        ),
        # --- o sinal que ninguém tinha ligado ao painel ---
        EventoMockado(
            "LCL4,5.SEPARADOR_TENSAO", M, DEG, ha_horas=56.0, durou_horas=None,
            descricao="Corrente do motor M17 em 11,3 A contra 10,2 de referência (+11%) para "
                      "a mesma velocidade, há dois dias.",
        ),
        EventoMockado(
            "LWB.CONCONDL1_2", M, DEG, ha_horas=18.0, durou_horas=None,
            descricao="12 afundamentos de tensão (>10%, <200 ms) registrados no painel da "
                      "célula nas últimas 18 h.",
        ),
        EventoMockado(
            "LWB.CONCONDL1_2", M, DEG, ha_horas=12.0, durou_horas=None,
            descricao="Contator K07 com 3 rearmes automáticos no período — contagem acima do "
                      "esperado para o turno.",
        ),
        # --- histórico elétrico da semana ---
        EventoMockado(
            "LCL08.DESBOBINADOR", M, PAR, ha_horas=98.0, durou_horas=0.6,
            descricao="Mesma falha F0002 no drive U31 há 4 dias — rearmado no local, sem "
                      "registro de causa.",
        ),
        EventoMockado(
            "LCL08.DESBOBINADOR", M, DEG, ha_horas=120.0, durou_horas=22.0,
            descricao="Corrente de pico do U31 em 138% da nominal na partida, três "
                      "ocorrências no mesmo turno.",
        ),
        EventoMockado(
            "LCL08.CARRO_DE_ENFIAMENTO", M, DEG, ha_horas=70.0, durou_horas=6.0,
            descricao="Contator K15 com ruído de acionamento e queda de 3,2 V no fechamento; "
                      "contatos lixados como paliativo.",
        ),
        EventoMockado(
            "LCP01.DESBOBINADOR", M, PLA, ha_horas=120.0, durou_horas=3.0,
            descricao="Termografia de painéis da rota mensal — três pontos acima de 65 °C "
                      "registrados para correção.",
        ),
        EventoMockado(
            "LWB.NOKCON_NOKPLA_REJEITO", M, DEG, ha_horas=26.0, durou_horas=4.0,
            descricao="Detector de rejeito B52 com 9 falsos positivos no turno por "
                      "interferência — malha de aterramento do sensor refeita.",
        ),
    ),
)

DUAS_LINHAS_PARADAS = Cenario(
    chave="duas-linhas-paradas",
    rotulo="Duas linhas paradas",
    resumo="Duas paradas simultâneas por causas diferentes — trava de segurança na tesoura e "
           "gás de proteção na solda — com a equipe dividida e um alerta esperando.",
    eventos=(
        # --- primeira parada ---
        EventoMockado(
            "LCT08.TESOURA_ROTATIVA", M, PAR, ha_horas=3.4, durou_horas=None,
            descricao="Falha trava do porta-facas — chave de segurança B41 sem confirmação "
                      "com eixo em movimento; parada de segurança e área isolada.",
        ),
        EventoMockado(
            "LCT08.TESOURA_ROTATIVA", M, PAR, ha_horas=3.3, durou_horas=None,
            descricao="Emergência S21 zona de corte atuada em seguida ao alarme de trava.",
        ),
        EventoMockado(
            "LCT08.TRACIONADOR_MEDICAO", M, DEG, ha_horas=50.0, durou_horas=None,
            descricao="Encoder G21 com desvio de contagem ±1,8 mm desde antes da parada — a "
                      "investigar junto com a tesoura.",
        ),
        # --- segunda parada ---
        EventoMockado(
            "LWB.SSPEED_FIWI_SOLDA", M, PAR, ha_horas=1.1, durou_horas=None,
            descricao="Falha válvula de bloqueio Y04 do gás de proteção — vazão 0,0 L/min com "
                      "comando ativo; célula bloqueada.",
        ),
        EventoMockado(
            "LWB.SSPEED_FIWI_SOLDA", M, DEG, ha_horas=20.0, durou_horas=None,
            descricao="Vazão de gás em queda progressiva (16,0 → 11,4 L/min) nas 20 h "
                      "anteriores ao bloqueio.",
        ),
        EventoMockado(
            "LWB.BTOVER_STOVER_VIRADOR", M, DEG, ha_horas=36.0, durou_horas=None,
            descricao="Virador com repetibilidade de 2,3° na posição 2 (tolerância 0,5°).",
        ),
        # --- alerta que fica esperando ---
        EventoMockado(
            "LCP01.APLANADORA", M, DEG, ha_horas=74.0, durou_horas=None,
            descricao="Vibração rolamento LA M04 em 7,1 mm/s RMS (alarme 4,5) — sem equipe "
                      "disponível para atender.",
        ),
        # --- histórico ---
        EventoMockado(
            "LCT08.TESOURA_ROTATIVA", M, DEG, ha_horas=76.0, durou_horas=72.0,
            descricao="Ruído de impacto no porta-facas detectado na coleta de rota há 3 dias "
                      "— sem intervenção registrada.",
        ),
        EventoMockado(
            "LWB.SSPEED_FIWI_SOLDA", M, PLA, ha_horas=190.0, durou_horas=2.5,
            descricao="Janela preventiva da cabeça de solda há 8 dias — válvula Y04 fora do "
                      "escopo da rotina.",
        ),
        EventoMockado(
            "LCL08.SEPARADOR_TENSAO", M, PAR, ha_horas=28.0, durou_horas=1.7,
            descricao="Patinagem do separador com escorregamento de 6,8% — sapatas "
                      "substituídas.",
        ),
        EventoMockado(
            "LCT2,5.EMPILHADOR_2", M, DEG, ha_horas=20.0, durou_horas=6.0,
            descricao="Desalinhamento de pilha de 12 mm na saída — batente reposicionado.",
        ),
        EventoMockado(
            "LCP02.PINCH_ROLL", M, DEG, ha_horas=12.0, durou_horas=3.0,
            descricao="Marcas cíclicas a cada 380 mm na chapa — resíduo na superfície do rolo "
                      "superior.",
        ),
    ),
)

POS_AVARIA = Cenario(
    chave="pos-avaria",
    rotulo="Retomada após avaria",
    resumo="A linha voltou com solução provisória e carga limitada: o que ficou pendente "
           "aparece como anomalia aberta, não como parada.",
    eventos=(
        # --- aberto depois do conserto ---
        EventoMockado(
            "LCT16.APLANADORA", M, DEG, ha_horas=5.0, durou_horas=None,
            descricao="Acoplamento provisório instalado — drive U09 limitado a 70% de torque "
                      "até a peça definitiva.",
        ),
        EventoMockado(
            "LCT16.APLANADORA", M, DEG, ha_horas=4.5, durou_horas=None,
            descricao="Vibração rolamento LOA M09 em 5,2 mm/s RMS após a troca (alarme 4,5) — "
                      "em observação a cada turno.",
        ),
        EventoMockado(
            "LCT16.TRACIONADOR_MEDICAO", M, DEG, ha_horas=48.0, durou_horas=None,
            descricao="Termopar B31 redutor ainda em 71 °C, ΔT +9 °C sobre a linha de base.",
        ),
        EventoMockado(
            "LCT16.EMPILHADOR_1", M, DEG, ha_horas=4.0, durou_horas=None,
            descricao="Tempo de ciclo do empilhador em 12,4 s contra 11,5 de referência "
                      "(+8%) desde a retomada.",
        ),
        EventoMockado(
            "LCP02.EMPILHADOR_2", M, DEG, ha_horas=3.0, durou_horas=None,
            descricao="Batente do berço com deformação de 3 mm após o travamento de ontem — "
                      "substituição programada.",
        ),
        EventoMockado(
            "LCP02.EMPILHADOR_2", M, DEG, ha_horas=2.5, durou_horas=None,
            descricao="Sensor B27 do berço mantido em monitoração após o evento — sinal "
                      "estável nas últimas 2 h.",
        ),
        # --- a avaria de ontem, agora fechada ---
        EventoMockado(
            "LCT16.APLANADORA", M, PAR, ha_horas=27.0, durou_horas=21.5,
            descricao="Falha acionamento M09 — drive U09 em F0001 sobrecorrente, acoplamento "
                      "rompido; 21h30 de linha bloqueada.",
        ),
        EventoMockado(
            "LCT16.APLANADORA", M, DEG, ha_horas=145.0, durou_horas=118.0,
            descricao="Vibração rolamento LOA M09 subindo até 9,4 mm/s RMS — anomalia aberta "
                      "5 dias antes da quebra.",
        ),
        EventoMockado(
            "LCP02.EMPILHADOR_2", M, PAR, ha_horas=26.0, durou_horas=2.0,
            descricao="Emergência S14 empilhador 2 atuada — peça atravessada no berço; "
                      "liberação mecânica e teste em vazio.",
        ),
        EventoMockado(
            "LCT16.MESA_DE_ROLETES", M, PLA, ha_horas=24.0, durou_horas=4.0,
            descricao="Aproveitando a linha bloqueada: troca dos roletes 7–9 com folga axial "
                      "acima do limite.",
        ),
        EventoMockado(
            "LCT08.APLANADORA_2", M, DEG, ha_horas=40.0, durou_horas=9.0,
            descricao="Termopar B44 do redutor em 82 °C — óleo substituído, temperatura "
                      "normalizada em 68 °C.",
        ),
        EventoMockado(
            "LWB.SUNI_STACKING", M, DEG, ha_horas=15.0, durou_horas=3.5,
            descricao="Perda de vácuo na ventosa 3 (−28 kPa contra −60 de referência) — "
                      "ventosa substituída.",
        ),
    ),
)

CENARIOS: tuple[Cenario, ...] = (
    TUDO_RODANDO,
    TURNO_NORMAL,
    ALERTAS_PREDITIVOS,
    PARADA_PROGRAMADA,
    PARADA_GERAL,
    AVARIA_EM_CURSO,
    AVARIA_ELETRICA,
    DUAS_LINHAS_PARADAS,
    POS_AVARIA,
)

CENARIO_PADRAO = TURNO_NORMAL.chave

_POR_CHAVE = {c.chave: c for c in CENARIOS}


def cenario(chave: str | None) -> Cenario:
    """O cenário pedido; o de entrada quando a chave é desconhecida ou vazia."""
    return _POR_CHAVE.get(chave or "", _POR_CHAVE[CENARIO_PADRAO])


def _validar() -> None:
    conhecidas = chaves_conhecidas()
    for c in CENARIOS:
        desconhecidas = sorted({e.conjunto for e in c.eventos} - conhecidas)
        if desconhecidas:
            raise CenarioInvalido(
                f"o cenário '{c.chave}' cita conjuntos que não existem no desenho: "
                f"{desconhecidas}. Evento em conjunto inexistente é invisível — nenhuma "
                f"máquina acenderia e nada acusaria o erro."
            )
    if TUDO_RODANDO.eventos:
        raise CenarioInvalido("'tudo-rodando' precisa ter a lista de eventos vazia (BR-07)")


_validar()
