# src/utils/failure_a3.py

"""
Seções do A3 exibidas **abaixo do diagrama** na Análise de Falhas.

Módulo **puro** (stdlib) — estrutura, defaults, retrocompat e helpers das seções.
A UI só liga campos; `failure_analysis_db` só persiste.

Seções (numeração da UI; 3 = diagrama, que não tem chave de seção):
  1. Esclareça o Problema      → `problema`
  2. Ação de Contenção         → `contencao`
  4. Plano de Ação             → `actions`
  5. Sustentabilidade/Lições   → `sustainability`
  6. Encerramento              → `closing`

Retrocompat (Seção 16 do prompt): `backfill_secoes` garante que uma análise
antiga — que não tinha esses campos — ganhe as seções vazias no load, sem quebrar.
"""

from __future__ import annotations

from typing import Iterable, Optional
import uuid

# Status do Plano de Ação — os 4 boxes do A3. Persistidos como int; exibidos pelo
# nome completo (Seção 7 do prompt: "usar nomes completos, não números").
# Rótulos do status da ação. Lidos pelas TRÊS telas — o quadro de gestão, o editor A3
# e o material mensal em PowerPoint. Trocar aqui muda as três de uma vez, que é o
# comportamento desejado: um rótulo local em qualquer uma delas faria o slide dizer
# uma coisa e a tela outra.
#
# O primeiro era "Aprovado" e virou "A fazer" em 2026-08-07: "18 ações aprovadas"
# lia-se como ação já autorizada por alguém, quando é ação que ninguém começou. O
# valor gravado continua 1 — análise antiga abre igual, sem migração.
STATUS_ACAO = {
    1: "A fazer",
    2: "Em andamento",
    3: "Concluído",
    4: "Eficácia comprovada",
}
STATUS_ACAO_PADRAO = 1

# Chaves de seção que `salvar_secoes` aceita — whitelist explícita (não grava
# chave arbitrária vinda do cliente). `alturas` não é seção do A3: guarda a altura
# em pixels que o usuário deixou em cada campo de texto (ver `mesclar_alturas`).
SECOES = (
    "problema", "contencao", "actions", "sustainability", "closing", "alturas",
)

# Limites da altura de campo de texto guardada. O valor vem do navegador, então é
# tratado como entrada não confiável: fora da faixa, descarta.
ALTURA_MIN_PX = 24
ALTURA_MAX_PX = 2000

# Marca a linha do Plano de Ação que o usuário criou de propósito ("+ ação"), em
# oposição à que nasce sozinha ao marcar a causa raiz (★). Serve para separar uma
# 2ª ação legítima de uma duplicata em branco herdada do race antigo — o dado
# legado não tem esta marca. Ver `_preservar`.
ADICIONADA = "adicionada"


def _novo_id() -> str:
    """Id de item de lista (ação, item de sustentabilidade...). Nunca índice de array."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Estruturas iniciais
# ---------------------------------------------------------------------------

def _problema_inicial(evento: dict) -> dict:
    """Seção 1 — pré-preenche área/equipamento a partir da parada quando dá.

    Área e subgrupo não existem em ZPP_Paradas → nascem vazios (editáveis).
    """
    from src.utils.failure_events import nome_equipamento

    equip = evento.get("equipamento") or ""
    return {
        "area": "", "equipamento": nome_equipamento(equip) if equip else "",
        "subgrupo": "", "descricao": "", "observacoes": "", "evidencias": "",
    }


def secoes_iniciais(evento: dict) -> dict:
    """Estrutura inicial de todas as seções, para uma análise nova."""
    return {
        "problema": _problema_inicial(evento),
        "contencao": {"acoes": "", "local": "", "responsavel": "", "inicio": None},
        "actions": [],
        # Seção 5 = só "Lições Aprendidas" (um campo), como o A3 oficial ("8. Lições
        # Aprendidas"). Seção 6 = só a assinatura final do responsável + data ("9.
        # Ass. Final do Responsável / Data").
        "sustainability": {"licoes": ""},
        "closing": {"responsavel": "", "data": None},
        # Altura (px) que o usuário deixou em cada campo de texto, por id do campo.
        # Vazio = cada campo se ajusta sozinho ao texto que tiver.
        "alturas": {},
    }


# ---------------------------------------------------------------------------
# Retrocompatibilidade
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "problema": lambda: {"area": "", "equipamento": "", "subgrupo": "", "descricao": "",
                         "observacoes": "", "evidencias": ""},
    "contencao": lambda: {"acoes": "", "local": "", "responsavel": "", "inicio": None},
    "actions": list,
    "sustainability": lambda: {"licoes": ""},
    "closing": lambda: {"responsavel": "", "data": None},
    "alturas": dict,
}


def backfill_secoes(analise: dict) -> dict:
    """Garante que a análise tenha todas as seções, sem sobrescrever o que existe.

    Análises antigas não tinham esses campos — aqui ganham os vazios. Dicts têm as
    chaves faltantes completadas; listas ausentes viram []. Se o TIPO mudou (ex.:
    `sustainability` era uma lista de itens e virou o dict `{licoes}`), o valor antigo
    incompatível é substituído pelo default. Não muta a entrada.
    """
    if not analise:
        return analise
    a = dict(analise)
    for chave, default in _DEFAULTS.items():
        atual = a.get(chave)
        base = default()
        if atual is None:
            a[chave] = base
        elif isinstance(base, dict):
            if isinstance(atual, dict):
                base.update(atual)  # completa chaves internas faltantes
                a[chave] = base
            else:
                a[chave] = base     # tipo antigo incompatível (ex.: lista → dict)
    return a


# ---------------------------------------------------------------------------
# Altura dos campos de texto
# ---------------------------------------------------------------------------

# Onde a altura do campo "Lições aprendidas" era guardada antes de existir o mapa
# `alturas`. Análises salvas naquele formato continuam abrindo no tamanho certo.
CAMPO_LICOES = "fa-sec-licoes"


def _altura_valida(valor) -> Optional[int]:
    """Altura em pixels vinda do navegador → int dentro da faixa, ou `None`.

    O valor chega do cliente, então é validado como entrada não confiável: texto
    que não é número, negativo, zero ou absurdo (ex: 99999) vira `None` e é
    simplesmente ignorado, deixando o campo se ajustar ao texto.
    """
    try:
        px = int(float(valor))
    except (TypeError, ValueError):
        return None
    if ALTURA_MIN_PX <= px <= ALTURA_MAX_PX:
        return px
    return None


def alturas_salvas(analise: dict) -> dict:
    """Alturas guardadas dos campos de texto, por id do campo (`{id: px}`).

    Em linguagem simples: devolve o tamanho que alguém deixou em cada caixa de
    texto daquela análise. Como fica salvo dentro da análise, **todos** que a
    abrirem veem o mesmo tamanho.

    Retrocompat: antes de existir o mapa `alturas`, só as "Lições aprendidas"
    tinham altura guardada, em `sustainability.licoes_altura`. Análises daquela
    época continuam funcionando — o valor legado é lido como se estivesse no mapa,
    e o mapa novo tem prioridade quando os dois existem.
    """
    a = analise or {}
    bruto = a.get("alturas")
    alturas = {}
    if isinstance(bruto, dict):
        for campo, valor in bruto.items():
            px = _altura_valida(valor)
            if px is not None and campo:
                alturas[str(campo)] = px
    if CAMPO_LICOES not in alturas:
        legado = _altura_valida((a.get("sustainability") or {}).get("licoes_altura"))
        if legado is not None:
            alturas[CAMPO_LICOES] = legado
    return alturas


def mesclar_alturas(secoes: dict, novas: dict) -> dict:
    """Dobra as alturas arrastadas pelo usuário dentro das seções, para salvar.

    Exemplo: o usuário puxa "Observações do primeiro atendimento" para 260px e
    salva; `novas` chega `{"fa-sec-prob-obs": 260}` e o resultado leva
    `alturas["fa-sec-prob-obs"] = 260`. Quem abrir a análise depois — qualquer
    usuário — encontra a caixa com 260px.

    Alturas já salvas de campos que não vieram em `novas` são preservadas (o
    usuário pode ter ajustado só um campo nesta visita). Valor fora da faixa
    aceitável é descartado. Não muta a entrada.
    """
    base = dict(secoes or {})
    atual = base.get("alturas")
    mapa = {k: v for k, v in atual.items()} if isinstance(atual, dict) else {}
    for campo, valor in (novas or {}).items():
        if not campo:
            continue
        px = _altura_valida(valor)
        if px is not None:
            mapa[str(campo)] = px
    base["alturas"] = mapa
    return base


# ---------------------------------------------------------------------------
# Itens de lista (novos)
# ---------------------------------------------------------------------------

def nova_acao(descricao: str = "", node_id: Optional[str] = None,
              adicionada: bool = False) -> dict:
    """Linha nova do Plano de Ação (Seção 4). `node_id` liga à causa (balão) de
    origem — o Plano de Ação é o único vínculo direto entre a ação e a causa raiz
    marcada no diagrama (★).

    `adicionada=True` marca a linha que o usuário criou de propósito no botão
    "+ ação" da causa, para distingui-la da que nasce sozinha ao marcar o ★. A
    diferença importa em `sincronizar_acoes` — ver a explicação de `ADICIONADA` lá.
    """
    row = {
        "id": _novo_id(), "node_id": node_id,
        # `responsavel` nasce como LISTA — uma ação pode ter mais de um
        # responsável. Análises antigas guardam um texto; `lista_responsaveis`
        # normaliza os dois formatos na leitura.
        "descricao": descricao, "responsavel": [], "prazo": None,
        "status": STATUS_ACAO_PADRAO, "observacoes": "",
    }
    if adicionada:
        row[ADICIONADA] = True
    return row


def adicionar_acao(rows, node_id: str) -> list[dict]:
    """Acrescenta mais uma ação à causa raiz `node_id`, logo abaixo das dela.

    Em linguagem simples: a mesma causa às vezes precisa de dois consertos, com
    responsáveis e prazos diferentes — trocar a correia até sexta com o João e
    revisar o tensor no mês seguinte com o Thiago. Esta função cria a segunda
    linha, encostada nas outras daquela causa para não embaralhar a leitura.

    Não muta a entrada. Sem `node_id`, devolve a lista como está — ação solta, sem
    causa, não existe no modelo (BR-AF2-14).
    """
    linhas = [dict(r) for r in (rows or [])]
    if not node_id:
        return linhas
    nova = nova_acao(node_id=node_id, adicionada=True)
    ultimo = -1
    for i, r in enumerate(linhas):
        if r.get("node_id") == node_id:
            ultimo = i
    if ultimo < 0:
        linhas.append(nova)          # causa ainda sem linha nenhuma
    else:
        linhas.insert(ultimo + 1, nova)
    return linhas


def remover_acao(rows, acao_id: str) -> list[dict]:
    """Tira uma ação do Plano de Ação pelo id da linha.

    Só faz sentido para as linhas adicionadas no "+ ação": a primeira linha de uma
    causa nasce do ★ e sai quando o balão deixa de ser causa raiz (BR-AF2-14). O
    guard está aqui, e não só na tela, para o modelo não depender de a UI esconder
    o botão. Não muta a entrada.
    """
    linhas = [dict(r) for r in (rows or [])]
    if not acao_id:
        return linhas
    alvo = next((r for r in linhas if r.get("id") == acao_id), None)
    if alvo is None or not alvo.get(ADICIONADA):
        return linhas
    return [r for r in linhas if r.get("id") != acao_id]


def lista_responsaveis(valor) -> list[str]:
    """Responsáveis de uma ação, sempre como lista de nomes.

    Uma ação pode ter **mais de um responsável** (dois mantenedores tocando o
    mesmo conserto). Retrocompat: antes o campo guardava **um nome só**, em texto —
    e análises antigas continuam assim no banco. Aqui o texto vira lista de um
    item, sem migração; se o texto veio com vírgulas (formato ainda mais antigo,
    digitado à mão), cada pedaço vira um nome.

    Exemplo: `"João"` → `["João"]`; `"João, Thiago"` → `["João", "Thiago"]`;
    `["João", "Thiago"]` → devolvido como está, sem vazios nem repetidos.
    """
    if isinstance(valor, (list, tuple)):
        brutos = [str(v).strip() for v in valor]
    elif isinstance(valor, str):
        brutos = [p.strip() for p in valor.split(",")]
    else:
        return []
    out: list[str] = []
    for nome in brutos:
        if nome and nome not in out:
            out.append(nome)
    return out


def texto_responsaveis(valor) -> str:
    """Os responsáveis de uma ação em uma linha só, para leitura (slide, PDF).

    Exemplo: `["João", "Thiago"]` → `"João, Thiago"`.
    """
    return ", ".join(lista_responsaveis(valor))


# ---------------------------------------------------------------------------
# "Tem alteração não salva?" — comparação com o que veio do banco
# ---------------------------------------------------------------------------

# Chaves de seção que entram na comparação. `alturas` fica de fora: não é conteúdo
# do A3, é o tamanho da caixa de texto, e chega por outro caminho (o store
# `store-fa-alturas`, mesclado só na hora de salvar).
SECOES_COMPARADAS = tuple(s for s in SECOES if s != "alturas")

# Campos que a própria tela preenche sozinha ao abrir a análise, sem ninguém
# digitar nada. Não podem contar como alteração: contariam em TODA análise aberta,
# e a página nasceria avisando "alterações não salvas".
#
# `closing.responsavel` é a assinatura final: o dropdown da seção 6 já abre com o
# nome de quem está logado (é a única opção — a assinatura é restrita ao próprio
# usuário), e esse nome não está no banco enquanto a análise não for concluída.
#
# `problema.evidencias` é o campo "Desenho / foto / evidência" que saiu da tela na v3:
# o texto antigo continua no banco, mas não é mais editável — ignorá-lo impede que a
# análise legada com texto ali nasça "com alterações não salvas".
_PREENCHIDOS_PELA_TELA = {"closing": ("responsavel",), "problema": ("evidencias",)}


def _vazio(valor) -> bool:
    """Valor que conta como "campo não preenchido" — para `None`, `""` e `[]`
    significarem a mesma coisa na comparação.

    Sem isto a página nasceria "com alterações não salvas": o banco devolve
    `None` num campo nunca preenchido e a tela devolve `""` para o mesmo campo.
    """
    if valor is None or valor is False:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    if isinstance(valor, (list, tuple, dict)):
        return not valor
    return False


def _canonico(valor):
    """Forma canônica de um valor de seção, para comparar conteúdo e não formato."""
    if isinstance(valor, str):
        return valor.strip()
    if isinstance(valor, (list, tuple)):
        return [_canonico(v) for v in valor if not _vazio(v)]
    if isinstance(valor, dict):
        return _dict_canonico(valor)
    return valor


def _dict_canonico(bruto) -> dict:
    """Dict sem campos vazios e sem chaves de uso interno (as que começam com `_`,
    como o `_causa` que a tela pendura na linha só para exibir)."""
    if not isinstance(bruto, dict):
        return {}
    return {
        str(k): _canonico(v)
        for k, v in bruto.items()
        if not str(k).startswith("_") and not _vazio(v)
    }


def _acao_canonica(row) -> dict:
    """Linha do Plano de Ação em forma canônica.

    O responsável passa por `lista_responsaveis` porque o mesmo conteúdo pode
    estar guardado de duas formas: `"João"` (análise antiga) e `["João"]` (a de
    hoje). Sem isto, só abrir uma análise antiga já marcaria a página como
    alterada.
    """
    canon = _dict_canonico(row)
    if "responsavel" in canon or row.get("responsavel"):
        resp = lista_responsaveis((row or {}).get("responsavel"))
        if resp:
            canon["responsavel"] = resp
        else:
            canon.pop("responsavel", None)
    return canon


def instantaneo_secoes(secoes) -> dict:
    """Foto comparável do conteúdo das seções do A3.

    Em linguagem simples: reduz as seções ao que o usuário de fato escreveu,
    jogando fora as diferenças que não são edição — campo vazio guardado como
    `None` num lado e como texto em branco no outro, espaço sobrando na ponta,
    altura de caixa de texto, campos que a tela usa só para exibir.
    """
    base = secoes or {}
    foto = {}
    for chave in SECOES_COMPARADAS:
        valor = base.get(chave)
        if chave == "actions":
            foto[chave] = [_acao_canonica(r) for r in (valor or [])]
            continue
        canon = _dict_canonico(valor)
        for campo in _PREENCHIDOS_PELA_TELA.get(chave, ()):
            canon.pop(campo, None)
        foto[chave] = canon
    return foto


def secoes_alteradas(base, atual) -> bool:
    """As seções na tela diferem do que veio do banco?

    Em linguagem simples: responde "essa pessoa mexeu em alguma coisa que ainda
    não foi salva?". Serve para o aviso de saída — quem digitou três parágrafos
    em "Lições Aprendidas" e clica em outro menu precisa ser avisado antes de
    perder o texto.

    Exemplo: a análise abre com a contenção em branco; a pessoa escreve
    "isolamos a linha" no campo de ações de contenção → `True`. Se apenas
    reabrir a mesma análise sem tocar em nada → `False`.
    """
    return instantaneo_secoes(base) != instantaneo_secoes(atual)


def _acao_tem_conteudo(row: dict) -> bool:
    """A linha do Plano de Ação foi preenchida pelo usuário? (ação/responsável/prazo)."""
    return bool(
        (row.get("descricao") or "").strip()
        or row.get("responsavel")
        or row.get("prazo")
    )


def _preservar(rows) -> dict:
    """Agrupa as linhas por causa, decidindo quais sobrevivem à reconciliação.

    Uma causa raiz pode ter **várias** ações (responsáveis e prazos diferentes),
    mas nem toda linha repetida é uma ação de verdade: análises salvas antes de
    2026-07-22 podem carregar uma linha **em branco** duplicando a preenchida —
    lixo de um race no load, que a reconciliação cura colapsando o par.

    Como separar as duas coisas, se ambas nascem em branco e no mesmo `node_id`:

    - linha **com conteúdo** → sempre fica (é trabalho do usuário);
    - linha **marcada** `ADICIONADA` → fica mesmo em branco (foi criada de
      propósito no "+ ação"; sem isto ela sumiria no próximo redesenho do
      diagrama, antes de ser preenchida);
    - entre as linhas **em branco e sem marca** da mesma causa → fica **uma só**.
      É exatamente a regra que valia antes das ações múltiplas, preservada para o
      dado antigo: documento legado não tem a marca e se comporta como sempre.
    """
    grupos: dict = {}
    for r in (rows or []):
        nid = r.get("node_id")
        if not nid:
            continue          # linha órfã (sem vínculo com balão) — descartada
        grupos.setdefault(nid, []).append(r)

    por_node: dict = {}
    for nid, grupo in grupos.items():
        com_conteudo = [r for r in grupo if _acao_tem_conteudo(r)]
        brancas_sem_marca = [r for r in grupo
                             if not _acao_tem_conteudo(r) and not r.get(ADICIONADA)]
        manter = {id(r) for r in grupo if _acao_tem_conteudo(r) or r.get(ADICIONADA)}
        # A branca sem marca é a linha automática do ★ ainda não preenchida —
        # legítima **enquanto a causa não tiver nenhuma linha preenchida**. Se já
        # houver conteúdo, ela só pode ser a duplicata do race antigo: cai fora.
        # Havendo várias, fica a primeira.
        if brancas_sem_marca and not com_conteudo:
            manter.add(id(brancas_sem_marca[0]))
        por_node[nid] = [r for r in grupo if id(r) in manter]
    return por_node


def sincronizar_acoes(nos: Iterable[dict], rows) -> list[dict]:
    """Reconcilia o Plano de Ação (Seção 4) com as causas-raiz marcadas (★).

    O Plano de Ação é **derivado** das causas-raiz: marcar ★ num balão cria a
    primeira linha, desmarcar remove as linhas daquela causa. Uma mesma causa pode
    ter **mais de uma ação** — o usuário as cria no "+ ação" da causa, para quando
    o conserto exige responsáveis ou prazos diferentes. Regras:

    - Balão marcado ★ sem nenhuma linha → cria a primeira (`nova_acao`).
    - Balão marcado ★ que já tem linhas → **preserva o conteúdo** editado de cada
      uma (ação/responsável/prazo/status), casando por `node_id` e mantendo a ordem
      em que foram criadas.
    - Linha cujo `node_id` não é mais causa raiz (ou sem `node_id`) → **descartada**.
    - Duplicata em branco herdada do race antigo → colapsada (ver `_preservar`).

    A ordem segue a dos nós; dentro da causa, a ordem das linhas. Não devolve a
    coluna auxiliar `_causa` (só exibição).
    """
    from src.utils.failure_tree import TIPO_RAIZ

    por_node = _preservar(rows)
    out: list[dict] = []
    for n in (nos or []):
        if not (n.get("is_root_cause") and n.get("tipo") != TIPO_RAIZ):
            continue
        atuais = por_node.get(n["id"])
        if atuais:
            out.extend(dict(r) for r in atuais)
        else:
            out.append(nova_acao(descricao="", node_id=n["id"]))
    return out


# ---------------------------------------------------------------------------
# Validação de encerramento (Seção 6)
# ---------------------------------------------------------------------------

def pode_concluir(nos: Iterable[dict]) -> tuple[bool, str]:
    """Regras que impedem concluir a análise. Não pode concluir sem ao menos uma
    causa raiz marcada (★). Rateio inconsistente é checado por
    `failure_tree.validar_tempos`; alterações não salvas, pela UI."""
    from src.utils.failure_tree import TIPO_RAIZ

    tem_raiz = any(n.get("is_root_cause") and n.get("tipo") != TIPO_RAIZ for n in nos)
    if not tem_raiz:
        return False, "Marque ao menos uma causa raiz antes de concluir."
    return True, ""


# ---------------------------------------------------------------------------
# Aceite do gestor — estado da análise e requisitos para entregar
# ---------------------------------------------------------------------------

# Estados por onde a análise passa (BR-13). "Entregue" e "aceita" são travadas
# (BR-16); "devolvida" é a mesma coisa que aberta, com um bilhete do gestor.
ESTADO_ABERTA = "aberta"
ESTADO_ENTREGUE = "entregue"
ESTADO_ACEITA = "aceita"
ESTADO_DEVOLVIDA = "devolvida"

# Nomes das passagens registradas em `aceite.passagens` (BR-15).
PASSAGEM_ENTREGUE = "entregue"
PASSAGEM_ACEITA = "aceita"
PASSAGEM_DEVOLVIDA = "devolvida"

# Valor de `status` no banco que significa "entregue ao gestor". O campo é o mesmo
# de sempre — o vocabulário é que mudou (BR-13): antes queria dizer "acabou", agora
# quer dizer "quem fez terminou e passou adiante".
_STATUS_ENTREGUE = "concluida"


def passagens(analise: dict) -> list[dict]:
    """Histórico de entregas, aceites e devoluções da análise, em ordem.

    Lista vazia em análise antiga — que é justamente o que a faz se comportar como
    "nunca entregue nem aceita", sem migração.
    """
    bruto = ((analise or {}).get("aceite") or {}).get("passagens")
    return [p for p in bruto if isinstance(p, dict)] if isinstance(bruto, list) else []


def estado_analise(analise: dict) -> str:
    """Em que pé está a análise: aberta, entregue ao gestor, aceita ou devolvida.

    Em linguagem simples: quem faz **entrega**, o gestor **aceita** ou **devolve**.
    Enquanto está entregue ou aceita, ninguém edita (BR-16).

    O estado é **derivado**, nunca guardado num campo próprio: dois campos dizendo a
    mesma coisa saem de sincronia na primeira escrita que falhar no meio. A fonte é o
    `status` que já existe mais o registro de aceite.

    Análise antiga não tem registro de aceite: as `aberta` viram **aberta** e as
    `concluida` viram **entregue** — e cair na fila do gestor é o comportamento certo,
    porque alguém precisa olhar para elas.
    """
    a = analise or {}
    if ((a.get("aceite") or {}).get("aceito_em")):
        return ESTADO_ACEITA
    if a.get("status") == _STATUS_ENTREGUE:
        return ESTADO_ENTREGUE
    hist = passagens(a)
    if hist and hist[-1].get("acao") == PASSAGEM_DEVOLVIDA:
        return ESTADO_DEVOLVIDA
    return ESTADO_ABERTA


def analise_travada(analise: dict) -> bool:
    """A análise está fechada para edição? (entregue ao gestor ou já aceita — BR-16)"""
    return estado_analise(analise) in (ESTADO_ENTREGUE, ESTADO_ACEITA)


def _rotulo_no(no: dict) -> str:
    """Texto curto de um balão, para citar numa mensagem de erro."""
    titulo = (no.get("titulo") or "").strip()
    return f'"{titulo}"' if titulo else "sem título"


def pode_entregar(nos: Iterable[dict], acoes: Iterable[dict]) -> tuple[bool, list[str]]:
    """A análise está pronta para ir ao gestor? (BR-14)

    Em linguagem simples: só entrega quem chegou a uma conclusão e escreveu o que vai
    ser feito, com dono e data. São três exigências:

    1. ao menos uma **causa raiz** marcada com ★;
    2. **toda** causa raiz com ao menos uma ação escrita — marcar três causas e tratar
       uma só deixaria duas sem conserto;
    3. **toda** ação escrita com responsável e prazo — sem dono e sem data, a ação não
       sai do papel.

    Devolve `(pode, faltas)`, com as faltas em português e citando o item: a pessoa
    precisa saber *o que* falta, não apenas que não pode entregar.

    Exemplo: a análise marcou "correia desalinhada" e "tensor gasto" como causas raiz,
    mas só escreveu ação para a correia → devolve
    `(False, ['a causa "tensor gasto" está sem ação escrita'])`.
    """
    from src.utils.failure_tree import TIPO_RAIZ

    nos = list(nos or [])
    linhas = list(acoes or [])
    faltas: list[str] = []

    raizes = [n for n in nos if n.get("is_root_cause") and n.get("tipo") != TIPO_RAIZ]
    if not raizes:
        return False, ["marque ao menos uma causa raiz (★) no diagrama"]

    escritas = [r for r in linhas if (r.get("descricao") or "").strip()]
    com_acao = {r.get("node_id") for r in escritas}
    for no in raizes:
        if no.get("id") not in com_acao:
            faltas.append(f"a causa {_rotulo_no(no)} está sem ação escrita")

    for r in escritas:
        titulo = (r.get("descricao") or "").strip()
        curto = titulo if len(titulo) <= 40 else titulo[:37] + "..."
        if not lista_responsaveis(r.get("responsavel")):
            faltas.append(f'a ação "{curto}" está sem responsável')
        if not r.get("prazo"):
            faltas.append(f'a ação "{curto}" está sem prazo')

    return (not faltas), faltas
