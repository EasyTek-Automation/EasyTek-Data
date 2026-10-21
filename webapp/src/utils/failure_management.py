"""
Gestão das Análises — o quadro do que a manutenção fez com as falhas que analisou.

Em linguagem simples: a aba responde "das falhas que pararam a fábrica, quantas foram
analisadas, quantas viraram ação, quem ficou responsável, o que venceu e se a falha
voltou". Este módulo faz **toda a conta** e não sabe nada de tela nem de banco — recebe
os eventos de parada e as análises já lidos, e devolve o quadro pronto.

Ser puro não é preciosismo: é o que permite provar cada regra num teste de menos de um
segundo, sem subir container nem clicar em nada. As regras vivem no SDD
`.dev-docs/projects/analise-falhas-acompanhamento/02-business-rules.md` (BR-01..BR-17), e
cada função abaixo cita a sua.

A data de hoje entra **por parâmetro** em tudo que depende dela ("vencida há 12 dias",
"esperando há 3 dias"). Lida de dentro, o mesmo teste passaria hoje e falharia amanhã.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional

from src.utils.failure_a3 import (
    ESTADO_ACEITA,
    ESTADO_DEVOLVIDA,
    ESTADO_ENTREGUE,
    STATUS_ACAO_PADRAO,
    estado_analise,
    lista_responsaveis,
    passagens,
)

# ---------------------------------------------------------------------------
# Constantes de regra
# ---------------------------------------------------------------------------

# Quantos meses depois do analisado ainda contam como "a falha voltou" (BR-10).
# Passou disso, é falha nova e pede análise nova.
JANELA_REINCIDENCIA_MESES = 3

# Status de ação que contam como trabalho ainda por fazer (BR-05).
STATUS_A_FAZER = 1
STATUS_EM_ANDAMENTO = 2
STATUS_CONCLUIDO = 3
STATUS_EFICACIA = 4
STATUS_EM_ABERTO = (STATUS_A_FAZER, STATUS_EM_ANDAMENTO)

# Em que pé está uma parada elegível (BR-03).
PARADA_NAO_ANALISADA = "nao_analisada"
PARADA_EM_ELABORACAO = "em_elaboracao"
PARADA_AGUARDANDO = "aguardando_aceite"
PARADA_DEVOLVIDA = "devolvida"
PARADA_ANALISADA = "analisada"

# Rótulo de quem não tem dono, para a linha própria da tabela (BR-07/BR-08).
SEM_RESPONSAVEL = "sem responsável"


# ---------------------------------------------------------------------------
# Mês e identidade da falha (BR-01, BR-10)
# ---------------------------------------------------------------------------

def mes_da_chave(chave: Optional[str]) -> Optional[str]:
    """Mês da parada, lido da própria chave — `PRENS002_202606_201_1bfe974d` → `202606`.

    O mês da **análise** é o mês da **parada** que ela analisa (BR-01): análise feita em
    julho sobre uma parada de junho conta em junho. Por isso o mês sai da chave, e nunca
    da data em que a análise foi criada.
    """
    partes = (chave or "").split("_")
    if len(partes) < 3:
        return None
    mes = partes[1]
    return mes if len(mes) == 6 and mes.isdigit() else None


def identidade_da_falha(chave: Optional[str]) -> Optional[str]:
    """A falha, sem o mês — `PRENS002_202606_201_1bfe974d` → `PRENS002_201_1bfe974d`.

    É o que permite reconhecer a **mesma** falha em outro mês (BR-10): mesmo
    equipamento, mesmo código de avaria, mesmo relato. O código sozinho não serviria —
    `201` quer dizer apenas "avaria" e cobre quase tudo que para a fábrica.
    """
    partes = (chave or "").split("_")
    if len(partes) < 3:
        return None
    return "_".join([partes[0]] + partes[2:])


def _mes_para_par(mes: str) -> tuple[int, int]:
    return int(mes[:4]), int(mes[4:])


def somar_meses(mes: str, n: int) -> str:
    """`202611` + 2 → `202701`. Usado na janela de reincidência e na régua de 12 meses."""
    ano, m = _mes_para_par(mes)
    total = (ano * 12 + (m - 1)) + n
    return f"{total // 12:04d}{total % 12 + 1:02d}"


def meses_do_periodo(hoje: date, quantidade: int = 12) -> list[str]:
    """Os N meses que a aba mostra, do mais antigo ao mês corrente (BR-12)."""
    atual = f"{hoje.year:04d}{hoje.month:02d}"
    return [somar_meses(atual, -i) for i in range(quantidade - 1, -1, -1)]


def mes_corrente(hoje: date) -> str:
    """O mês que ainda está acontecendo — o número dele vai crescer até o fim (BR-12)."""
    return f"{hoje.year:04d}{hoje.month:02d}"


# ---------------------------------------------------------------------------
# Ações do plano (BR-04 a BR-08)
# ---------------------------------------------------------------------------

def acao_escrita(row: dict) -> bool:
    """A linha do Plano de Ação tem ação escrita? (BR-04)

    Só a **descrição** conta. A linha nasce sozinha quando alguém marca a causa raiz
    com ★, então "existe linha" não quer dizer nada — o que interessa é se alguém
    escreveu o que precisa ser feito.

    Cuidado: existe `_acao_tem_conteudo` em `failure_a3`, que aceita descrição **ou**
    responsável **ou** prazo. Ela serve para decidir qual linha sobrevive à
    reconciliação com as causas raiz — propósito diferente, não reusar aqui.
    """
    return bool((row or {}).get("descricao", "").strip())


def acoes_escritas(analise: dict) -> list[dict]:
    """As linhas do Plano de Ação que são ação de verdade (BR-04)."""
    return [r for r in ((analise or {}).get("actions") or []) if acao_escrita(r)]


def status_acao(row: dict) -> int:
    """Status da ação, com o padrão para dado antigo sem o campo (BR-05)."""
    valor = (row or {}).get("status")
    try:
        return int(valor)
    except (TypeError, ValueError):
        return STATUS_ACAO_PADRAO


def acao_em_aberto(row: dict) -> bool:
    """Trabalho que ainda falta: "A fazer" ou "Em andamento" (BR-05).

    "Concluído" e "Eficácia comprovada" ficam de fora — o serviço foi feito. A diferença
    entre esses dois é sobre resultado, e resultado tem lugar próprio no quadro (a
    pergunta "a falha voltou?").
    """
    return status_acao(row) in STATUS_EM_ABERTO


def _para_data(valor) -> Optional[date]:
    """Prazo guardado como texto `AAAA-MM-DD` (ou data) → `date`; lixo → None."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def acao_vencida(row: dict, hoje: date) -> bool:
    """Passou do prazo e ainda não foi feita? (BR-06)

    Três coisas ao mesmo tempo: tem prazo, o prazo já passou e a ação está em aberto.

    A ação vence **no fim do dia do prazo** — com prazo 30/08 ela não está vencida no
    dia 30, e sim a partir do 31. Ação concluída em atraso **não** conta: terminou, e o
    quadro não cobra de novo quem já fez.
    """
    prazo = _para_data((row or {}).get("prazo"))
    return bool(prazo and prazo < hoje and acao_em_aberto(row))


def dias_de_atraso(row: dict, hoje: date) -> Optional[int]:
    """Há quantos dias a ação venceu — para ordenar e dar noção de tamanho (BR-06)."""
    prazo = _para_data((row or {}).get("prazo"))
    return (hoje - prazo).days if prazo and prazo < hoje else None


def acao_sem_responsavel(row: dict) -> bool:
    """Ninguém no campo de responsável (BR-07).

    Lista vazia, texto vazio e campo ausente são a mesma coisa — os três formatos
    convivem no banco porque o campo já foi um texto só.
    """
    return not lista_responsaveis((row or {}).get("responsavel"))


def acao_sem_prazo(row: dict) -> bool:
    """Sem data marcada (BR-07). Não vence nunca — por isso some do radar em silêncio."""
    return _para_data((row or {}).get("prazo")) is None


# ---------------------------------------------------------------------------
# Estado da parada (BR-03)
# ---------------------------------------------------------------------------

def estado_da_parada(analise: Optional[dict]) -> str:
    """Em que pé está o tratamento daquela parada (BR-03).

    "Analisada" é só a que o **gestor aceitou**. Não basta existir o documento: ele
    nasce quando alguém clica em "Abrir diagrama", e sair da página em seguida deixaria
    uma análise que ninguém fez.
    """
    if not analise:
        return PARADA_NAO_ANALISADA
    estado = estado_analise(analise)
    if estado == ESTADO_ACEITA:
        return PARADA_ANALISADA
    if estado == ESTADO_ENTREGUE:
        return PARADA_AGUARDANDO
    if estado == ESTADO_DEVOLVIDA:
        return PARADA_DEVOLVIDA
    return PARADA_EM_ELABORACAO


def tem_plano_de_acao(analise: Optional[dict]) -> bool:
    """A análise virou ação de verdade? (BR-04) Diagrama sem ação não muda nada."""
    return bool(acoes_escritas(analise or {}))


# ---------------------------------------------------------------------------
# Repetição dentro do mês (BR-09)
# ---------------------------------------------------------------------------

def repeticao_no_mes(evento: dict) -> dict:
    """Quanto aquela falha doeu no mês: tempo, dias e vezes (BR-09).

    Os três juntos, sempre. Vinte paradas de 5 minutos somam 100 e estouram um gatilho
    de 90 — o problema é real mesmo sem nenhuma parada grande. Só o tempo não distingue
    uma quebra de 5 horas de vinte paradas curtas; só os dias não enxerga as vinte se
    caíram no mesmo dia; só as vezes não diz o tamanho do estrago.

    Ressalva: **vezes pode inflar**, porque o sistema de origem quebra em dois
    apontamentos a parada que atravessa refeição ou reunião de segurança. Por isso as
    vezes nunca aparecem sozinhas — o tempo total é imune a esse fracionamento.
    """
    e = evento or {}
    return {
        "minutos": float(e.get("duracao_min") or 0),
        "dias": int(e.get("n_dias") or 1),
        "vezes": int(e.get("n_apontamentos") or 1),
    }


# ---------------------------------------------------------------------------
# A falha voltou (BR-10, BR-11)
# ---------------------------------------------------------------------------

def indexar_por_identidade(eventos: Iterable[dict]) -> dict[str, dict[str, dict]]:
    """`{identidade da falha: {mês: evento}}` — o índice que evita uma consulta por análise.

    A reincidência cruza cada análise com as paradas dos meses seguintes. Consultando o
    banco por análise, 40 análises virariam 40 idas ao banco; com este índice, é uma
    passada só sobre o que já foi buscado (DS-10).
    """
    indice: dict[str, dict[str, dict]] = {}
    for ev in eventos or []:
        chave = ev.get("chave")
        ident, mes = identidade_da_falha(chave), mes_da_chave(chave)
        if ident and mes:
            indice.setdefault(ident, {})[mes] = ev
    return indice


def data_do_aceite(analise: dict) -> Optional[date]:
    """Quando o gestor aceitou — o único marco com data na linha do tratamento (BR-11)."""
    valor = ((analise or {}).get("aceite") or {}).get("aceito_em")
    return _para_data(valor)


def voltou_depois(chave: str, indice: dict, hoje: date,
                  janela: int = JANELA_REINCIDENCIA_MESES) -> dict:
    """A mesma falha reapareceu nos meses seguintes? (BR-10)

    Olha os `janela` meses após o mês analisado. Se ainda não passaram todos, a resposta
    **não** é "não voltou": é **ainda observando** — a análise de julho não teve três
    meses para voltar, e juntar as duas coisas faria a análise mais recente parecer a
    mais bem-sucedida.

    A volta conta em **qualquer tamanho**: o gatilho serve para decidir o que merece
    análise, e aqui a pergunta é outra — o problema continua acontecendo?

    Voltar em dois meses conta **uma vez** (o quadro não multiplica o problema); o
    detalhe traz os meses e a soma.
    """
    mes = mes_da_chave(chave)
    ident = identidade_da_falha(chave)
    vazio = {"voltou": False, "ainda_observando": False, "meses": [],
             "minutos": 0.0, "vezes": 0, "meses_faltando": 0}
    if not mes or not ident:
        return vazio

    limite = mes_corrente(hoje)
    ocorrencias = (indice or {}).get(ident) or {}
    meses_alvo = [somar_meses(mes, i) for i in range(1, janela + 1)]
    observados = [m for m in meses_alvo if m <= limite]

    achados = [(m, ocorrencias[m]) for m in observados if m in ocorrencias]
    if achados:
        return {
            "voltou": True,
            "ainda_observando": False,
            "meses": [m for m, _ in achados],
            "minutos": sum(float(e.get("duracao_min") or 0) for _, e in achados),
            "vezes": sum(int(e.get("n_apontamentos") or 1) for _, e in achados),
            "meses_faltando": len(meses_alvo) - len(observados),
        }
    faltando = len(meses_alvo) - len(observados)
    return {**vazio, "ainda_observando": faltando > 0, "meses_faltando": faltando}


def contexto_do_retorno(analise: Optional[dict], meses_da_volta: list[str]) -> str:
    """A falha voltou antes ou depois de o gestor aceitar? (BR-11)

    Sem isto, o número acusa a manutenção de algo que ela talvez nem tenha tido chance
    de fazer. O marco é o **aceite** — o único momento com data — e o texto na tela diz
    exatamente isso: "depois do aceite", nunca "depois do conserto". A ação do plano não
    guarda a data em que foi concluída.
    """
    aceite = data_do_aceite(analise or {})
    if not aceite or not meses_da_volta:
        return "antes_do_aceite"
    mes_aceite = f"{aceite.year:04d}{aceite.month:02d}"
    return "depois_do_aceite" if min(meses_da_volta) >= mes_aceite else "antes_do_aceite"


# ---------------------------------------------------------------------------
# Contagem por responsável (BR-08)
# ---------------------------------------------------------------------------

def por_responsavel(analises: Iterable[dict], hoje: date) -> list[dict]:
    """Uma linha por pessoa: ações, vencidas, em aberto e feitas (BR-08).

    Ação com **mais de um responsável conta para cada um** — é uma ação só no plano, mas
    está na mão dos dois. Por isso a soma da coluna passa do total de ações, e a tela
    precisa dizer isso; sem o aviso, a divergência volta como relato de bug.

    Ação sem dono não some: vai para a linha "sem responsável", para a soma fechar.
    """
    linhas: dict[str, dict] = {}
    for analise in analises or []:
        for row in acoes_escritas(analise):
            nomes = lista_responsaveis(row.get("responsavel")) or [SEM_RESPONSAVEL]
            for nome in nomes:
                alvo = linhas.setdefault(nome, {"pessoa": nome, "acoes": 0, "vencidas": 0,
                                                "em_aberto": 0, "feitas": 0})
                alvo["acoes"] += 1
                if acao_vencida(row, hoje):
                    alvo["vencidas"] += 1
                elif acao_em_aberto(row):
                    alvo["em_aberto"] += 1
                else:
                    alvo["feitas"] += 1

    def ordem(l):
        # Mais vencidas primeiro; empate, mais ações; empate, ordem alfabética. "Sem
        # responsável" fica sempre por último, por ser um balde e não uma pessoa.
        return (l["pessoa"] == SEM_RESPONSAVEL, -l["vencidas"], -l["acoes"], l["pessoa"])

    return sorted(linhas.values(), key=ordem)


# ---------------------------------------------------------------------------
# Pendências (BR-06, BR-07, BR-03)
# ---------------------------------------------------------------------------

# Ordem em que as pendências aparecem: quem já teve mais chance de ser resolvido
# primeiro (SP-06).
_PESO_ATENCAO = {"vencida": 0, "devolvida": 1, "sem_responsavel": 2,
                 "sem_prazo": 2, "em_elaboracao": 3}


def _rotulo_equip(evento: dict, analise: Optional[dict]) -> str:
    """Nome do equipamento para leitura humana — "Prensa 02", não `PRENS002`."""
    parada = (analise or {}).get("parada") or {}
    return (parada.get("equipamento_nome") or (evento or {}).get("equipamento_nome")
            or parada.get("equipamento") or (evento or {}).get("equipamento") or "")


def pendencias(analise: dict, evento: Optional[dict], hoje: date) -> list[dict]:
    """As pendências concretas de uma análise, com o motivo (BR-06, BR-07, BR-03).

    Uma ação com dois problemas — sem dono **e** sem prazo — aparece **uma vez só**, com
    os dois motivos. Duas linhas para a mesma ação fariam a lista parecer maior do que o
    problema é.
    """
    itens: list[dict] = []
    chave = analise.get("parada_chave")
    base = {"chave": chave, "mes": mes_da_chave(chave),
            "equipamento": _rotulo_equip(evento or {}, analise)}
    estado = estado_da_parada(analise)

    for row in acoes_escritas(analise):
        motivos = []
        if acao_vencida(row, hoje):
            motivos.append("vencida")
        if acao_sem_responsavel(row):
            motivos.append("sem_responsavel")
        if acao_sem_prazo(row):
            motivos.append("sem_prazo")
        if not motivos:
            continue
        itens.append({**base, "tipo": "acao", "motivos": motivos,
                      "descricao": (row.get("descricao") or "").strip(),
                      "responsaveis": lista_responsaveis(row.get("responsavel")),
                      "dias_atraso": dias_de_atraso(row, hoje),
                      "peso": min(_PESO_ATENCAO[m] for m in motivos)})

    if estado == PARADA_DEVOLVIDA:
        ultima = passagens(analise)[-1] if passagens(analise) else {}
        itens.append({**base, "tipo": "analise", "motivos": ["devolvida"],
                      "motivo_devolucao": (ultima.get("motivo") or "").strip(),
                      "por": ultima.get("por", ""), "em": ultima.get("em"),
                      "peso": _PESO_ATENCAO["devolvida"]})
    elif estado == PARADA_EM_ELABORACAO:
        itens.append({**base, "tipo": "analise", "motivos": ["em_elaboracao"],
                      "peso": _PESO_ATENCAO["em_elaboracao"]})
    return itens


# ---------------------------------------------------------------------------
# Fila de aceite (BR-17)
# ---------------------------------------------------------------------------

def _ultima_entrega(analise: dict) -> Optional[date]:
    """Quando a análise foi entregue pela última vez.

    Análise antiga não tem registro de passagem — aí vale a data de conclusão que já
    está gravada, que é o que existe de mais próximo (BR-13/BR-17).
    """
    for p in reversed(passagens(analise)):
        if p.get("acao") == "entregue":
            return _para_data(p.get("em"))
    return _para_data(analise.get("data_conclusao_analise"))


def fila_de_aceite(analises: Iterable[dict], eventos_por_chave: dict, hoje: date) -> list[dict]:
    """As análises entregues que ainda esperam o gestor (BR-17).

    Ordenada de quem **espera há mais tempo** para a mais recente: a fila existe para
    não deixar nada envelhecer, e o mais velho é o que corre mais risco de ser
    esquecido.

    A fila **ignora o mês em foco** — pendência não tem mês. Se o gestor está olhando
    junho, uma análise de março esperando há quatro meses não pode sumir da tela.
    """
    fila = []
    for analise in analises or []:
        if estado_da_parada(analise) != PARADA_AGUARDANDO:
            continue
        chave = analise.get("parada_chave")
        entrega = _ultima_entrega(analise)
        devolucoes = sum(1 for p in passagens(analise) if p.get("acao") == "devolvida")
        raizes = [n for n in (analise.get("nos") or []) if n.get("is_root_cause")]
        entregue_por = ""
        for p in reversed(passagens(analise)):
            if p.get("acao") == "entregue":
                entregue_por = p.get("por", "")
                break
        fila.append({
            "chave": chave, "mes": mes_da_chave(chave),
            "equipamento": _rotulo_equip(eventos_por_chave.get(chave) or {}, analise),
            "falha": (analise.get("titulo") or "").strip(),
            "entregue_por": entregue_por or analise.get("atualizado_por", ""),
            "entregue_em": entrega,
            "dias_esperando": (hoje - entrega).days if entrega else None,
            "causas": len(raizes), "acoes": len(acoes_escritas(analise)),
            "devolvida_vezes": devolucoes,
        })
    return sorted(fila, key=lambda f: (-(f["dias_esperando"] or 0), f["chave"] or ""))


# ---------------------------------------------------------------------------
# O quadro inteiro
# ---------------------------------------------------------------------------

def montar_quadro(eventos_elegiveis: Iterable[dict], eventos_todos: Iterable[dict],
                  analises: Iterable[dict], hoje: date,
                  meses: Optional[list[str]] = None) -> dict:
    """Monta o quadro da aba a partir do que já foi lido do banco.

    `eventos_elegiveis` são as paradas acima do gatilho (BR-02) — a fila de candidatas a
    análise. `eventos_todos` são as paradas de qualquer tamanho, usadas só para saber se
    a falha voltou (BR-10), porque a volta conta mesmo pequena.

    `hoje` vem por parâmetro para as regras de prazo e de espera serem reprodutíveis.
    """
    meses = meses or meses_do_periodo(hoje)
    conjunto_meses = set(meses)
    elegiveis = [e for e in (eventos_elegiveis or []) if mes_da_chave(e.get("chave")) in conjunto_meses]
    por_chave = {e.get("chave"): e for e in elegiveis}
    analise_por_chave = {a.get("parada_chave"): a for a in (analises or [])}
    indice_voltas = indexar_por_identidade(eventos_todos or [])

    # -- por mês (as barras) -------------------------------------------------
    # `tem_dado` separa "mês sem nenhuma parada acima do gatilho" (mês bom) de "mês
    # que o sistema não carregou" (investigar) — BR-12. Sem essa marca, os dois
    # aparecem como barra vazia, e a diferença é comemorar ou investigar.
    meses_com_dado = {mes_da_chave(e.get("chave")) for e in (eventos_todos or [])}
    por_mes = {m: {"mes": m, "elegiveis": 0, "analisadas": 0, "com_plano": 0,
                   "aguardando": 0, "em_elaboracao": 0, "devolvidas": 0,
                   "nao_analisadas": 0, "tem_dado": m in meses_com_dado} for m in meses}
    for ev in elegiveis:
        mes = mes_da_chave(ev.get("chave"))
        linha = por_mes[mes]
        linha["elegiveis"] += 1
        analise = analise_por_chave.get(ev.get("chave"))
        estado = estado_da_parada(analise)
        if estado == PARADA_ANALISADA:
            linha["analisadas"] += 1
        elif estado == PARADA_AGUARDANDO:
            linha["aguardando"] += 1
        elif estado == PARADA_DEVOLVIDA:
            linha["devolvidas"] += 1
        elif estado == PARADA_EM_ELABORACAO:
            linha["em_elaboracao"] += 1
        else:
            linha["nao_analisadas"] += 1
        if tem_plano_de_acao(analise):
            linha["com_plano"] += 1

    # -- reincidência --------------------------------------------------------
    reincidencia = []
    for ev in elegiveis:
        chave = ev.get("chave")
        analise = analise_por_chave.get(chave)
        if estado_da_parada(analise) == PARADA_NAO_ANALISADA:
            continue                      # sem análise, não há o que observar
        volta = voltou_depois(chave, indice_voltas, hoje)
        if not (volta["voltou"] or volta["ainda_observando"]):
            continue
        reincidencia.append({
            "chave": chave, "mes": mes_da_chave(chave),
            "equipamento": _rotulo_equip(ev, analise),
            "falha": (ev.get("rotulo") or "").strip(),
            "repeticao": repeticao_no_mes(ev),
            **volta,
            "contexto": contexto_do_retorno(analise, volta["meses"]),
            "acoes": len(acoes_escritas(analise or {})),
            "acoes_feitas": sum(1 for r in acoes_escritas(analise or {})
                                if not acao_em_aberto(r)),
        })

    # -- pendências ----------------------------------------------------------
    atencao = []
    for chave, analise in analise_por_chave.items():
        if mes_da_chave(chave) not in conjunto_meses:
            continue
        atencao.extend(pendencias(analise, por_chave.get(chave), hoje))
    atencao.sort(key=lambda i: (i["peso"], -(i.get("dias_atraso") or 0)))

    quadro_analises = [a for a in (analises or [])
                       if mes_da_chave(a.get("parada_chave")) in conjunto_meses]

    return {
        "meses": meses,
        "mes_corrente": mes_corrente(hoje),
        "por_mes": [por_mes[m] for m in meses],
        "fila": fila_de_aceite(analises, por_chave, hoje),
        "responsaveis": por_responsavel(quadro_analises, hoje),
        "atencao": atencao,
        "reincidencia": reincidencia,
        "cartoes": resumo(por_mes.values(), quadro_analises, atencao, reincidencia, hoje,
                          analises_existentes=len(quadro_analises)),
    }


def resumo(linhas_mes: Iterable[dict], analises: Iterable[dict],
           atencao: Iterable[dict], reincidencia: Iterable[dict], hoje: date,
           analises_existentes: int = 0) -> dict:
    """Os seis números dos cartões (SP-02).

    O percentual anda sempre junto do de-quanto: "64%" sozinho não diz se são 9 de 14 ou
    900 de 1400 — e num mês de 3 paradas, um terço vira 33% e parece estatística.

    `com_plano_de` é o total de **análises existentes**, não o de analisadas: uma análise
    ainda em elaboração pode ter plano de ação, e usar as aceitas como denominador
    produziria "2 de 0" enquanto ninguém tivesse aceitado nada — foi o que o dado real do
    cliente mostrou na primeira rodada.
    """
    linhas = list(linhas_mes or [])
    elegiveis = sum(l["elegiveis"] for l in linhas)
    analisadas = sum(l["analisadas"] for l in linhas)
    aguardando = sum(l["aguardando"] for l in linhas)
    com_plano = sum(l["com_plano"] for l in linhas)

    todas_acoes = [r for a in (analises or []) for r in acoes_escritas(a)]
    em_aberto = [r for r in todas_acoes if acao_em_aberto(r)]
    vencidas = [r for r in todas_acoes if acao_vencida(r, hoje)]
    voltaram = [r for r in (reincidencia or []) if r.get("voltou")]
    observando = [r for r in (reincidencia or []) if r.get("ainda_observando")]

    return {
        "elegiveis": elegiveis,
        "analisadas": analisadas,
        "analisadas_de": elegiveis,
        "aguardando_aceite": aguardando,
        "com_plano": com_plano,
        "com_plano_de": analises_existentes,
        "acoes_em_aberto": len(em_aberto),
        "acoes_vencidas": len(vencidas),
        "falhas_voltaram": len(voltaram),
        "ainda_observando": len(observando),
        "pendencias": len(list(atencao or [])),
    }
