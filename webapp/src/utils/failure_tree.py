# src/utils/failure_tree.py

"""
Árvore de causas da Análise de Falhas: operações estruturais e distribuição de tempo.

Módulo **puro** (só stdlib) — sem Mongo, sem pandas, sem Dash. Toda a regra de
negócio testável vive aqui; `failure_analysis_db` só persiste o resultado.

Unidade canônica de tempo: **minutos inteiros**. A aritmética é toda inteira, de
propósito: a distribuição precisa fechar exatamente com a duração da parada, e
float introduz resíduo (0.1+0.2). A sobra da divisão vai para o último nó
automático (BR-AF2-07).

Vocabulário: no código o termo é **nó**; na interface, "etapa"/"causa".
"""

from __future__ import annotations

from typing import Iterable, Optional
import uuid

TIPO_RAIZ = "ROOT"      # evento de parada agregado — 1 por análise; tempo = duração
TIPO_ETAPA = "STEP"     # etapa principal, filha do ROOT
TIPO_CAUSA = "CAUSE"    # ramificação causal (filha de STEP ou CAUSE)

# O tempo é distribuído recursivamente por TODOS os níveis: os filhos de cada
# balão dividem o tempo dele (ver `distribuir_tempos`). Os tipos ROOT/STEP/CAUSE
# valem para hierarquia/6M, não para "quem rateia" — todos os não-ROOT têm tempo.
TIPOS = (TIPO_RAIZ, TIPO_ETAPA, TIPO_CAUSA)

MODO_AUTO = "AUTO"           # absorve a sobra do pai (rateio automático)
MODO_MANUAL = "MANUAL"       # tempo fixado à mão (pino)
MODO_EXPLICATIVO = "EXPLICATIVO"  # balão explicativo: não leva tempo, é transparente

PLACEHOLDER_CAUSA = "Descreva a causa"


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

def formatar_duracao(minutos: float | int | None) -> str:
    """Formata minutos para exibição: '70 h', '1 h 30 min', '45 min', '—'.

    Omite a parte de minutos quando é zero, para não poluir o card do diagrama
    com "70 h 0 min".
    """
    if minutos is None:
        return "—"
    total = int(round(float(minutos)))
    if total < 0:
        return "—"
    if total == 0:
        return "0 min"
    horas, mins = divmod(total, 60)
    if horas and mins:
        return f"{horas} h {mins} min"
    if horas:
        return f"{horas} h"
    return f"{mins} min"


# ---------------------------------------------------------------------------
# Construção de nós
# ---------------------------------------------------------------------------

def novo_id() -> str:
    """Gera um id de nó. uuid4 para não depender de contador no Mongo."""
    return uuid.uuid4().hex


def criar_no(
    analysis_id: str,
    parent_id: Optional[str],
    titulo: str = "",
    tipo: str = TIPO_CAUSA,
    descricao: str = "",
    categoria_6m: Optional[str] = None,
    sort_order: int = 0,
    no_id: Optional[str] = None,
    position_x: Optional[float] = None,
    position_y: Optional[float] = None,
) -> dict:
    """Cria um nó novo em modo AUTO (o tempo é recalculado pela distribuição)."""
    return {
        "id": no_id or novo_id(),
        "analysis_id": analysis_id,
        "parent_id": parent_id,
        "tipo": tipo,
        "titulo": titulo,
        "descricao": descricao,
        "categoria_6m": categoria_6m,
        "duration_mode": MODO_AUTO,
        "duration_min": 0,
        "sort_order": sort_order,
        "position_x": position_x,
        "position_y": position_y,
        "is_root_cause": False,
    }


def criar_etapa(analysis_id: str, root_id: str, titulo: str = "", **kw) -> dict:
    """Cria uma STEP ligada ao ROOT. Participa do rateio de tempo."""
    return criar_no(analysis_id, root_id, titulo, tipo=TIPO_ETAPA, **kw)


def criar_ramificacao(analysis_id: str, parent_id: str, titulo: str = "", **kw) -> dict:
    """Cria uma CAUSE (ramificação causal) filha de uma STEP ou CAUSE. Não rateia."""
    return criar_no(analysis_id, parent_id, titulo, tipo=TIPO_CAUSA, **kw)


def tipo_por_pai(nos: Iterable[dict], parent_id: Optional[str]) -> str:
    """Deriva o tipo de um nó pelo tipo do pai (regra de conversão da Seção 9.4).

    Filho direto do ROOT → STEP. Filho de STEP/CAUSE → CAUSE. Sem pai → o chamador
    provavelmente está criando o próprio ROOT.
    """
    if parent_id is None:
        return TIPO_RAIZ
    pai = indexar(nos).get(parent_id)
    if pai is not None and pai.get("tipo") == TIPO_RAIZ:
        return TIPO_ETAPA
    return TIPO_CAUSA


def sincronizar_tipos(nos: Iterable[dict]) -> list[dict]:
    """Reatribui os tipos varrendo a árvore a partir do ROOT (fonte da verdade).

    Percorre em largura: filhos diretos do ROOT viram STEP, o resto vira CAUSE. O
    ROOT é preservado. É a ponte de retrocompatibilidade — análises antigas só
    tinham ROOT/CAUSE, e aqui as CAUSE que eram filhas diretas do ROOT passam a
    ser STEP (e só elas rateiam). Também é o passo canônico após qualquer mudança
    estrutural (reparent, promoção de filhos), garantindo STEP/CAUSE coerentes.

    Nós inalcançáveis a partir do ROOT (órfãos) ficam como estão — a validação os
    reprova depois.
    """
    lista = [dict(n) for n in nos]
    r = raiz(lista)
    if r is None:
        return lista
    idx = indexar(lista)
    fila = [(r["id"], 0)]
    visto = {r["id"]}
    while fila:
        atual, nivel = fila.pop(0)
        for f in filhos(lista, atual):
            if f["id"] in visto:
                continue
            visto.add(f["id"])
            f["tipo"] = TIPO_ETAPA if nivel == 0 else TIPO_CAUSA
            fila.append((f["id"], nivel + 1))
    return [idx[n["id"]] for n in lista]


def etapas(nos: Iterable[dict]) -> list[dict]:
    """Nós STEP — os únicos que participam da distribuição de tempo."""
    return [n for n in nos if n.get("tipo") == TIPO_ETAPA]


# ---------------------------------------------------------------------------
# Consultas estruturais
# ---------------------------------------------------------------------------

def indexar(nos: Iterable[dict]) -> dict[str, dict]:
    """Indexa nós por id, para navegação sem varredura repetida."""
    return {n["id"]: n for n in nos}


def raiz(nos: Iterable[dict]) -> Optional[dict]:
    """Retorna o nó raiz (tipo ROOT), ou None se a árvore não tiver um."""
    for n in nos:
        if n.get("tipo") == TIPO_RAIZ:
            return n
    return None


def filhos(nos: Iterable[dict], parent_id: Optional[str]) -> list[dict]:
    """Filhos diretos de um nó, ordenados por `sort_order` e depois por id (desempate estável)."""
    return sorted(
        [n for n in nos if n.get("parent_id") == parent_id],
        key=lambda n: (n.get("sort_order") or 0, n["id"]),
    )


def descendentes(nos: Iterable[dict], no_id: str) -> list[dict]:
    """Todos os descendentes de um nó (busca em largura), sem incluir ele mesmo.

    Tolera ciclos: um nó já visitado não é reexpandido, então a função termina
    mesmo numa árvore corrompida.
    """
    lista = list(nos)
    resultado: list[dict] = []
    vistos = {no_id}
    fila = [no_id]
    while fila:
        atual = fila.pop(0)
        for n in lista:
            if n.get("parent_id") == atual and n["id"] not in vistos:
                vistos.add(n["id"])
                resultado.append(n)
                fila.append(n["id"])
    return resultado


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------

def detectar_ciclo(nos: Iterable[dict]) -> bool:
    """True se algum nó alcançar a si mesmo subindo por `parent_id`."""
    idx = indexar(nos)
    for inicio in idx:
        visto = set()
        atual = inicio
        while atual is not None and atual in idx:
            if atual in visto:
                return True
            visto.add(atual)
            atual = idx[atual].get("parent_id")
    return False


def validar_arvore(nos: Iterable[dict], analysis_id: Optional[str] = None) -> tuple[bool, str]:
    """Valida a árvore inteira antes de persistir. Retorna (ok, mensagem).

    Cobre as invariantes que o backend não pode delegar ao frontend: raiz única,
    raiz sem pai, pai existente e da mesma análise, ausência de ciclos e duração
    não negativa.
    """
    lista = list(nos)
    if not lista:
        return True, ""

    idx = indexar(lista)
    if len(idx) != len(lista):
        return False, "Há nós com id duplicado."

    raizes = [n for n in lista if n.get("tipo") == TIPO_RAIZ]
    if len(raizes) == 0:
        return False, "A árvore não tem nó raiz."
    if len(raizes) > 1:
        return False, "A árvore tem mais de um nó raiz."
    if raizes[0].get("parent_id") is not None:
        return False, "O nó raiz não pode ter pai."

    for n in lista:
        if analysis_id is not None and n.get("analysis_id") != analysis_id:
            return False, f"O nó {n['id']} não pertence a esta análise."
        if n.get("tipo") == TIPO_RAIZ and n.get("is_root_cause"):
            return False, "O evento de parada não pode ser causa raiz."
        pid = n.get("parent_id")
        if pid is not None:
            if pid not in idx:
                return False, f"O nó {n['id']} aponta para um pai inexistente."
            if pid == n["id"]:
                return False, f"O nó {n['id']} é pai de si mesmo."
            # Regra de conversão (Seção 9.4): filho do ROOT é STEP; filho de
            # STEP/CAUSE é CAUSE. Só STEP rateia, então um tipo errado aqui
            # distorceria a distribuição de tempo.
            esperado = tipo_por_pai(lista, pid)
            if n.get("tipo") != esperado:
                return False, (
                    f"O nó {n['id']} deveria ser {esperado} (é filho de "
                    f"{idx[pid].get('tipo')}), mas está como {n.get('tipo')}."
                )
        elif n.get("tipo") != TIPO_RAIZ:
            return False, f"O nó {n['id']} está solto (sem pai) e não é o ROOT."
        d = n.get("duration_min")
        if d is not None and float(d) < 0:
            return False, f"O nó {n['id']} tem duração negativa."

    if detectar_ciclo(lista):
        return False, "A árvore tem ciclo."

    return True, ""


def pode_reparentar(nos: Iterable[dict], no_id: str, novo_parent_id: Optional[str]) -> tuple[bool, str]:
    """Verifica se mover `no_id` para baixo de `novo_parent_id` é válido.

    Bloqueia os dois jeitos de criar ciclo: virar pai de si mesmo, ou descer para
    dentro da própria descendência.
    """
    if novo_parent_id is None:
        return False, "Só o nó raiz pode ficar sem pai."
    if no_id == novo_parent_id:
        return False, "Um nó não pode ser pai de si mesmo."
    idx = indexar(nos)
    if no_id not in idx:
        return False, "Nó não encontrado."
    if novo_parent_id not in idx:
        return False, "Nó de destino não encontrado."
    if idx[no_id].get("tipo") == TIPO_RAIZ:
        return False, "O nó raiz não pode ser movido."
    ids_desc = {d["id"] for d in descendentes(nos, no_id)}
    if novo_parent_id in ids_desc:
        return False, "Não é possível mover um nó para dentro da própria ramificação."
    return True, ""


def reparent_muda_tipo(nos: Iterable[dict], no_id: str, novo_parent_id: str) -> bool:
    """True se mover o nó trocaria seu tipo entre STEP e CAUSE (Seção 9.4).

    Serve para o frontend pedir confirmação antes de reparentear — a troca muda se
    o nó passa (ou deixa de passar) a participar do rateio de tempo.
    """
    idx = indexar(nos)
    if no_id not in idx:
        return False
    atual = idx[no_id].get("tipo")
    return atual != tipo_por_pai(nos, novo_parent_id)


def reparentar(nos: Iterable[dict], no_id: str, novo_parent_id: str) -> list[dict]:
    """Move o nó para baixo de outro pai e ressincroniza os tipos da subárvore.

    Pressupõe `pode_reparentar` já validado. Depois de mover, `sincronizar_tipos`
    recalcula STEP/CAUSE de todo mundo — um nó que virou filho do ROOT vira STEP
    (e passa a ratear), e vice-versa. O chamador redistribui o tempo em seguida.
    """
    lista = [dict(n) for n in nos]
    idx = indexar(lista)
    alvo = idx.get(no_id)
    if alvo is None:
        return lista
    alvo["parent_id"] = novo_parent_id
    alvo["sort_order"] = proximo_sort_order(lista, novo_parent_id)
    return sincronizar_tipos(lista)


# ---------------------------------------------------------------------------
# Causa raiz (Seção 9.7) — fonte única da verdade é node.is_root_cause
# ---------------------------------------------------------------------------

def marcar_causa_raiz(nos: Iterable[dict], no_id: str, valor: bool = True) -> list[dict]:
    """Marca/desmarca um nó como causa raiz. O ROOT nunca é causa raiz.

    A flag `is_root_cause` no nó é a fonte única da verdade: destaca o balão no
    diagrama, habilita a conclusão da análise (`failure_a3.pode_concluir`) e liga
    as ações do Plano de Ação à causa por `node_id`. Não há tabela/seção separada.
    """
    lista = [dict(n) for n in nos]
    for n in lista:
        if n["id"] == no_id and n.get("tipo") != TIPO_RAIZ:
            n["is_root_cause"] = bool(valor)
    return lista




# ---------------------------------------------------------------------------
# Operações estruturais
# ---------------------------------------------------------------------------

def proximo_sort_order(nos: Iterable[dict], parent_id: Optional[str]) -> int:
    """Próximo `sort_order` livre entre os irmãos de um pai."""
    irmaos = filhos(nos, parent_id)
    return (max((i.get("sort_order") or 0) for i in irmaos) + 1) if irmaos else 0


PREFIXO_BALAO_NOVO = "novo_"


def reconciliar_arvore(nos: Iterable[dict], analysis_id: str) -> list[dict]:
    """Prepara para o banco a árvore que veio do quadro de desenho.

    O balão que a pessoa acabou de desenhar chega cru: sem id definitivo (nasce com
    um id provisório do próprio desenho), sem saber a que análise pertence e sem
    posição na ordem dos irmãos. Do jeito que chega, a gravação **recusa a árvore
    inteira** — `validar_arvore` reprova um único balão sem `analysis_id` com "o nó X
    não pertence a esta análise", e a análise toda deixa de salvar.

    O que esta função faz, nesta ordem (a ordem importa):

    1. **Id definitivo** para cada balão desenhado, corrigindo junto quem apontava
       para o id provisório — senão o filho ficaria apontando para um pai que não
       existe mais.
    2. **`analysis_id`** em todos, inclusive nos que vieram do banco (defesa barata
       contra balão que perdeu o campo no caminho).
    3. **Tipos** normalizados a partir da raiz (`sincronizar_tipos`): filho da raiz é
       etapa, o resto é causa. A validação exige que o tipo bata com o pai.
    4. **Ordem entre irmãos** pela posição na tela: de cima para baixo, desempatando
       pela esquerda. É o que faz a ordem do desenho virar a ordem do relatório.
    5. **Campos que faltam** ganham o padrão de um balão novo (modo automático, sem
       tempo fixado, não é causa raiz).

    Não valida nada: quem reprova é `validar_arvore`, no momento de gravar.
    """
    lista = [dict(n) for n in nos]
    if not lista:
        return lista

    # 1. id provisório -> definitivo (e conserta as referências de pai)
    traducao = {
        n["id"]: novo_id()
        for n in lista
        if str(n.get("id", "")).startswith(PREFIXO_BALAO_NOVO)
    }
    for n in lista:
        if n["id"] in traducao:
            n["id"] = traducao[n["id"]]
        pai = n.get("parent_id")
        if pai in traducao:
            n["parent_id"] = traducao[pai]

    # 2. e 5. análise dona + campos que o desenho não preenche
    padrao = criar_no(analysis_id, None)
    for n in lista:
        n["analysis_id"] = analysis_id
        for campo, valor in padrao.items():
            if campo in ("id", "parent_id", "tipo", "analysis_id"):
                continue
            n.setdefault(campo, valor)

    # 3. tipos coerentes com o pai
    lista = sincronizar_tipos(lista)

    # 4. ordem entre irmãos pela posição na tela (cima→baixo, depois esquerda→direita)
    por_pai: dict = {}
    for n in lista:
        por_pai.setdefault(n.get("parent_id"), []).append(n)
    for irmaos in por_pai.values():
        ordenados = sorted(
            irmaos,
            key=lambda x: (x.get("position_y") if x.get("position_y") is not None else 0,
                           x.get("position_x") if x.get("position_x") is not None else 0),
        )
        for ordem, n in enumerate(ordenados):
            n["sort_order"] = ordem

    return lista


def conflitos_de_pai(conflitos: Iterable[dict], nos: Iterable[dict]) -> list[str]:
    """Traduz os conflitos apontados pelo desenho em frases para o usuário.

    No modelo, um balão tem **um** pai. No quadro, nada impede puxar duas setas para o
    mesmo balão — e aí a última simplesmente vencia, em silêncio. O desenho passa a
    avisar, e aqui a mensagem ganha o **título** do balão: id interno não diz nada a
    quem está olhando a tela.
    """
    idx = indexar(nos)
    frases = []
    for c in conflitos or []:
        no = idx.get(c.get("id"))
        titulo = (no or {}).get("titulo") or c.get("titulo") or ""
        titulo = titulo.strip() or "um balão sem texto"
        frases.append(
            f"O balão “{titulo}” tem mais de uma seta chegando. Deixe só uma."
        )
    return frases


def descrever_no(nos: Iterable[dict], no_id: str) -> str:
    """Nome do balão para mensagens — título, ou algo legível quando está vazio."""
    no = indexar(nos).get(no_id)
    if no is None:
        return "um balão que não está mais no diagrama"
    titulo = (no.get("titulo") or "").strip()
    return f"“{titulo}”" if titulo else "um balão sem texto"


def mensagem_com_titulos(mensagem: str, nos: Iterable[dict]) -> str:
    """Troca os ids internos de uma mensagem de validação pelos títulos dos balões.

    `validar_arvore` fala a língua do banco ("O nó a1b2c3… está solto"). Na tela isso
    não ajuda ninguém: quem desenhou reconhece o balão pelo texto que escreveu nele.
    """
    texto = mensagem or ""
    for no in nos or []:
        ident = str(no.get("id") or "")
        if ident and ident in texto:
            texto = texto.replace(f"O nó {ident}", f"O balão {descrever_no(nos, ident)}")
            texto = texto.replace(ident, descrever_no(nos, ident))
    return texto


def duplicar_subarvore(nos: Iterable[dict], no_id: str, com_descendentes: bool = True) -> list[dict]:
    """Duplica um nó (opcionalmente com a ramificação) devolvendo **nós novos**.

    Ids são regerados e o `parent_id` das cópias é remapeado para dentro da
    cópia — nunca se reaproveita id do original. Os tempos das cópias voltam para
    AUTO, para que a distribuição os recalcule (BR-AF2-07).
    A cópia do nó de topo vira irmã do original.
    """
    lista = list(nos)
    idx = indexar(lista)
    if no_id not in idx:
        return []
    original = idx[no_id]
    if original.get("tipo") == TIPO_RAIZ:
        return []  # a raiz é o evento de parada, não se duplica

    alvos = [original] + (descendentes(lista, no_id) if com_descendentes else [])
    mapa = {n["id"]: novo_id() for n in alvos}

    copias: list[dict] = []
    for n in alvos:
        c = dict(n)
        c["id"] = mapa[n["id"]]
        if n["id"] == no_id:
            c["parent_id"] = original.get("parent_id")
            c["sort_order"] = proximo_sort_order(lista, original.get("parent_id"))
        else:
            c["parent_id"] = mapa.get(n.get("parent_id"), original.get("parent_id"))
        c["duration_mode"] = MODO_AUTO
        c["duration_min"] = 0
        c["is_root_cause"] = False  # a validação da causa raiz não se copia
        c["position_x"] = None
        c["position_y"] = None
        copias.append(c)
    return copias


def excluir_no(nos: Iterable[dict], no_id: str, promover_filhos: bool = False) -> list[dict]:
    """Remove um nó, em cascata ou promovendo os filhos ao nível anterior.

    `promover_filhos=True` religa os filhos diretos ao avô, preservando a
    ramificação. A raiz nunca é removida — sem ela a análise perde o evento.
    """
    lista = [dict(n) for n in nos]
    idx = indexar(lista)
    if no_id not in idx:
        return lista
    alvo = idx[no_id]
    if alvo.get("tipo") == TIPO_RAIZ:
        return lista

    if promover_filhos:
        avo = alvo.get("parent_id")
        for n in lista:
            if n.get("parent_id") == no_id:
                n["parent_id"] = avo
        restante = [n for n in lista if n["id"] != no_id]
        # Filho de CAUSE promovido a filho do ROOT vira STEP (e passa a ratear).
        return sincronizar_tipos(restante)

    remover = {no_id} | {d["id"] for d in descendentes(lista, no_id)}
    return [n for n in lista if n["id"] not in remover]


# ---------------------------------------------------------------------------
# Distribuição de tempo (Seção 10) — top-down, ancestrais fixos
# ---------------------------------------------------------------------------

def _mapa_filhos(lista: list[dict]) -> tuple[dict, Optional[dict]]:
    """Índice parent_id → filhos + o nó ROOT (usado pela distribuição recursiva)."""
    filhos_de: dict = {}
    root = None
    for n in lista:
        filhos_de.setdefault(n.get("parent_id"), []).append(n)
        if n.get("tipo") == TIPO_RAIZ:
            root = n
    return filhos_de, root


def _pino_val(node: dict) -> int:
    """Valor do pino manual do balão, em minutos inteiros não negativos."""
    return max(0, int(round(float(node.get("duration_min") or 0))))


def _compete_por_sobra(node: dict) -> bool:
    """True se o balão disputa a sobra do pai (AUTO ou EXPLICATIVO).

    O explicativo disputa **como um auto** — ele fica com a própria fatia e a
    repassa **aos filhos dele**. NÃO é achatado no pai: os irmãos não mudam quando
    um balão vira explicativo. MANUAL não disputa (tem valor fixado)."""
    return node.get("duration_mode", MODO_AUTO) in (MODO_AUTO, MODO_EXPLICATIVO)


def distribuir_tempos(nos: Iterable[dict], duracao_total_min: float | int) -> list[dict]:
    """Distribui o tempo **top-down**, com ancestrais fixos (Seção 10).

    Regra (herança de cima pra baixo):
    - ROOT = a duração da parada (`duracao_total_min`), fixa.
    - O tempo de um balão é **repartido entre os filhos diretos**: os **MANUAL**
      mantêm o valor fixado; os **AUTO** e **EXPLICATIVO** dividem por igual a
      **sobra** (`tempo_do_pai − Σ manuais`). Um balão AUTO herda a sobra do pai
      direto; vários dividem-na.
    - Um balão **EXPLICATIVO fica com a própria fatia** (como um auto) e a repassa
      **só aos filhos dele** — ele não exibe tempo próprio (a UI mostra "sem
      tempo"), mas **não achata** no pai: marcar explicativo **não muda os irmãos**.
      Ex.: 3 irmãos de 35; marco 1 como explicativo → os outros 2 seguem 35, e os
      filhos do explicativo herdam os 35 dele.
    - **Ancestral nunca muda** ao editar/adicionar um descendente: o pai é um
      orçamento fixo (vem de cima); só os irmãos se reajustam para fechar a soma.
    - Vermelho (`validar_tempos`) quando não fecha: sobra sem nenhum AUTO/EXPLICATIVO
      para absorver, manuais que estouram o pai, ou **explicativo folha** (guarda
      tempo mas não tem causa abaixo para atribuí-lo — até adicionar um filho).

    Arredondamento inteiro: a sobra da divisão vai de +1 nos **últimos** filhos
    (ordem estável), então cada grupo fecha exato (100/3 → 33,33,34).

    Devolve lista nova; não muta a entrada.
    """
    lista = [dict(n) for n in nos]
    total = int(round(float(duracao_total_min or 0)))
    filhos_de, root = _mapa_filhos(lista)
    if root is None:
        return lista

    def _dist(node, budget):
        # Todo balão fica com o próprio budget (o explicativo também — ele guarda a
        # fatia e repassa aos filhos; a UI é que não exibe o número dele).
        node["duration_min"] = max(0, int(round(budget)))
        kids = filhos_de.get(node["id"], [])
        if not kids:
            return
        manuais = [c for c in kids if c.get("duration_mode") == MODO_MANUAL]
        autos = [c for c in kids if _compete_por_sobra(c)]
        sobra = node["duration_min"] - sum(_pino_val(c) for c in manuais)
        extra = {c["id"]: 0 for c in kids}
        if autos and sobra > 0:
            base, resto = divmod(sobra, len(autos))
            ordenados = sorted(autos, key=lambda c: (c.get("sort_order") or 0, c["id"]))
            for i, c in enumerate(ordenados):
                extra[c["id"]] = base + (1 if i >= len(ordenados) - resto else 0)
        for c in kids:
            _dist(c, _pino_val(c) if c.get("duration_mode") == MODO_MANUAL else extra[c["id"]])

    _dist(root, total)
    return lista


def _inconsistencias(nos: Iterable[dict], duracao_total_min: float | int) -> tuple[list[str], str]:
    """Balões cuja repartição não fecha → (ids para destacar em vermelho, mensagem).

    - **Estouro**: Σ manuais dos filhos > tempo do pai (sobra negativa).
    - **Sobra sem dono**: sobra positiva e nenhum filho AUTO/EXPLICATIVO para absorver.
    - **Explicativo folha**: guarda a própria fatia mas não tem nenhuma causa abaixo
      para atribuí-la — até adicionar um filho, fica em vermelho.
    """
    lista = list(nos)
    total = int(round(float(duracao_total_min or 0)))
    filhos_de, root = _mapa_filhos(lista)
    if root is None:
        return [], ""

    ids: list[str] = []
    msg = ""
    for node in lista:
        kids = filhos_de.get(node["id"], [])
        # Explicativo folha: herdou tempo (sua fatia) mas não tem onde atribuí-lo.
        if node.get("duration_mode") == MODO_EXPLICATIVO and not kids:
            if _pino_val(node) > 0:
                ids.append(node["id"])
                if not msg:
                    msg = ("Um balão explicativo herdou tempo mas não tem nenhuma causa "
                           "abaixo dele. Adicione uma causa ou desmarque-o como explicativo.")
            continue
        if not kids:
            continue
        pt = total if node.get("tipo") == TIPO_RAIZ else _pino_val(node)
        manuais = [c for c in kids if c.get("duration_mode") == MODO_MANUAL]
        autos = [c for c in kids if _compete_por_sobra(c)]
        sm = sum(_pino_val(c) for c in manuais)
        sobra = pt - sm
        if sobra < 0:
            ids.extend(c["id"] for c in manuais)
            if not msg:
                msg = (f"Os tempos manuais de um grupo somam {formatar_duracao(sm)} e passam do "
                       f"tempo do balão pai ({formatar_duracao(pt)}) em {formatar_duracao(-sobra)}.")
        elif sobra > 0 and not autos:
            ids.extend(c["id"] for c in kids)
            if not msg:
                msg = (f"Sobram {formatar_duracao(sobra)} sem nenhuma causa que leve tempo para "
                       f"absorvê-los (o balão pai tem {formatar_duracao(pt)}). Adicione uma causa "
                       f"ou desmarque alguma como explicativa.")
    return ids, msg


def validar_tempos(nos: Iterable[dict], duracao_total_min: float | int) -> tuple[bool, str]:
    """Consistência dos tempos: nenhum grupo pode estourar/divergir do tempo do pai."""
    ids, msg = _inconsistencias(nos, duracao_total_min)
    return (not ids), msg


def ids_manuais_em_excesso(nos: Iterable[dict], duracao_total_min: float | int) -> list[str]:
    """Ids dos balões em grupos com tempo inconsistente — para destacar em vermelho."""
    ids, _ = _inconsistencias(nos, duracao_total_min)
    return ids


# -- Edição manual do tempo (pino) -----------------------------------------

def marcar_tempo_manual(nos: Iterable[dict], no_id: str, minutos) -> list[dict]:
    """Fixa o tempo de um balão (vira MANUAL, protegido do recálculo).

    Vale para qualquer balão (folha ou container): um container manual é um
    competidor de valor fixo que redistribui esse valor entre os próprios filhos.
    O ROOT não aceita — seu tempo é a duração da parada. Marcar manual tira um
    eventual estado explicativo. O chamador roda `distribuir_tempos` depois para
    redistribuir os irmãos AUTO."""
    m = max(0, int(round(float(minutos or 0))))
    lista = [dict(n) for n in nos]
    for n in lista:
        if n["id"] == no_id and n.get("tipo") != TIPO_RAIZ:
            n["duration_mode"] = MODO_MANUAL
            n["duration_min"] = m
    return lista


def marcar_explicativo(nos: Iterable[dict], no_id: str, valor: bool = True) -> list[dict]:
    """Marca/desmarca um balão como **explicativo** (não leva tempo).

    Um balão explicativo é transparente: não entra na conta de tempo e deixa a
    sobra do pai passar para os filhos dele. Desmarcar volta ao rateio automático
    (AUTO). O ROOT nunca é explicativo. O chamador roda `distribuir_tempos` depois."""
    lista = [dict(n) for n in nos]
    for n in lista:
        if n["id"] == no_id and n.get("tipo") != TIPO_RAIZ:
            n["duration_mode"] = MODO_EXPLICATIVO if valor else MODO_AUTO
    return lista


def tornar_tempo_auto(nos: Iterable[dict], no_id: str) -> list[dict]:
    """Tira o pino manual / marca explicativa de um balão — volta ao rateio automático."""
    lista = [dict(n) for n in nos]
    for n in lista:
        if n["id"] == no_id and n.get("tipo") != TIPO_RAIZ:
            n["duration_mode"] = MODO_AUTO
    return lista


def resetar_tempos(nos: Iterable[dict]) -> list[dict]:
    """Volta a árvore inteira ao rateio automático (limpa pinos e marcas explicativas)."""
    lista = [dict(n) for n in nos]
    for n in lista:
        if n.get("tipo") != TIPO_RAIZ:
            n["duration_mode"] = MODO_AUTO
    return lista
