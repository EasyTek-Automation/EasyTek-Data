# src/utils/failure_analysis_db.py

"""
Persistência da Análise de Falhas (A3) no MongoDB.

Decisão de modelagem: a árvore é **embutida** no documento da análise (campo
`nos`), não numa collection separada. O modelo relacional sugerido na spec
(tabela `FailureAnalysisNode` com FK) não se traduz bem aqui — embutindo, o
salvamento da árvore inteira vira um único `update_one`, que é **atômico por
construção**. Isso satisfaz o requisito de "nós, relações e tempos nunca
parcialmente atualizados" sem depender de transação multi-documento (que exige
replica set e não está garantida no Mongo local).

Uma árvore de centenas de nós fica na casa das dezenas de KB — muito abaixo do
limite de 16 MB por documento.

Concorrência: cada análise carrega `versao`. A escrita é condicionada à versão
lida (`update_one({_id, versao})` + `$inc`), então dois usuários editando a
mesma análise não se sobrescrevem em silêncio — o segundo recebe conflito.

Convenções seguidas de `workflow_db.py`: funções soltas, `get_mongo_connection`
por chamada, writers devolvendo `(bool, str)`, campos de auditoria em português,
degradação silenciosa quando o Mongo está fora.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src.database.connection import get_mongo_connection
from src.utils.failure_tree import (
    TIPO_ETAPA,
    TIPO_RAIZ,
    criar_no,
    distribuir_tempos,
    validar_arvore,
)

COLLECTION_ANALISES = "FailureAnalysis"

STATUS_ABERTA = "aberta"
STATUS_CONCLUIDA = "concluida"

# Campos gerais editáveis do cabeçalho/A3. Whitelist explícita: o callback não
# escreve campo que não esteja aqui (evita injeção de chave arbitrária no doc).
CAMPOS_EDITAVEIS = {
    # `titulo` NÃO entra aqui de propósito: é derivado da parada e imutável.
    # O rótulo livre do usuário é `nome`.
    "nome",
    "tipo_analise",
    "responsavel",
    "participantes",
    # Área e subgrupo não existem em ZPP_Paradas — são preenchidos pelo usuário
    # em vez de derivados de um dado que a fonte não tem.
    "area",
    "subgrupo",
    "data_inicio_analise",
    "data_conclusao_analise",
    "observacoes",
}


def _colecao():
    """Handle da collection de análises, ou None se o Mongo estiver indisponível."""
    return get_mongo_connection(COLLECTION_ANALISES)


def ensure_indexes() -> bool:
    """Cria os índices da Análise de Falhas. Idempotente — roda a cada boot.

    O índice único em `parada_chave` é a garantia de "no máximo uma análise por
    parada" no nível do banco: sem ele, dois cliques simultâneos em "Abrir
    diagrama" criariam duas análises.
    """
    col = _colecao()
    if col is None:
        return False
    try:
        col.create_index("parada_chave", name="idx_fa_parada", unique=True)
        col.create_index([("atualizado_em", -1)], name="idx_fa_atualizacao")
        col.create_index("status", name="idx_fa_status")
        return True
    except Exception as e:
        print(f"[failure_analysis_db] falha ao criar índices: {e}")
        return False


def _arvore_inicial(analysis_id: str, evento: dict) -> list[dict]:
    """Monta a árvore inicial: ROOT do evento + primeira STEP (Seção 10.2).

    O ROOT representa a parada e não recebe tempo. A primeira **STEP** (não CAUSE)
    nasce preenchida com o relato do operador quando existe; senão fica vazia, com
    placeholder na UI. Como é a única STEP, recebe 100% da duração.
    """
    from src.utils.failure_events import texto_no_raiz

    raiz = criar_no(
        analysis_id,
        None,
        titulo=texto_no_raiz(evento),
        tipo=TIPO_RAIZ,
        no_id="raiz",
    )
    rotulo = (evento.get("rotulo") or "").strip()
    etapa = criar_no(
        analysis_id,
        "raiz",
        titulo=rotulo,  # vazio → a UI mostra o placeholder
        tipo=TIPO_ETAPA,
        sort_order=0,
    )
    nos = [raiz, etapa]
    return distribuir_tempos(nos, evento.get("duracao_min") or 0)


def _doc_para_analise(doc: dict) -> dict:
    """Converte o doc do Mongo em dict de aplicação (ObjectId → str em `id`).

    `backfill_secoes` garante que toda análise carregada tenha as seções A3, mesmo
    as antigas que foram criadas antes delas existirem (retrocompat, Seção 16).
    """
    from src.utils.failure_a3 import backfill_secoes

    d = dict(doc)
    d["id"] = str(d.pop("_id"))
    return backfill_secoes(d)


def carregar_analise(parada_chave: str) -> Optional[dict]:
    """Carrega a análise de uma parada, ou None se não existir / Mongo fora."""
    col = _colecao()
    if col is None:
        return None
    try:
        doc = col.find_one({"parada_chave": parada_chave})
    except Exception as e:
        print(f"[failure_analysis_db] falha ao carregar análise {parada_chave}: {e}")
        return None
    return _doc_para_analise(doc) if doc else None


def carregar_por_id(analysis_id: str) -> Optional[dict]:
    """Carrega a análise pelo `_id` (str), ou None. Usado pelas rotas de foto, que
    recebem o id na URL (a página carrega pela chave da parada)."""
    col = _colecao()
    if col is None:
        return None
    try:
        from bson import ObjectId
        doc = col.find_one({"_id": ObjectId(analysis_id)})
    except Exception as e:
        print(f"[failure_analysis_db] falha ao carregar análise por id {analysis_id}: {e}")
        return None
    return _doc_para_analise(doc) if doc else None


def _serializar_por_dia(por_dia) -> list:
    """Converte o `dia` (date) de cada item de `por_dia` para ISO string.

    `date` não é serializável em BSON (Mongo) nem em JSON (stores do Dash); o
    evento em memória mantém `date`, mas o snapshot persistido guarda a string."""
    saida = []
    for d in (por_dia or []):
        dia = d.get("dia")
        saida.append({
            "dia": dia.isoformat() if hasattr(dia, "isoformat") else dia,
            "duracao_min": d.get("duracao_min"),
            "n_apontamentos": d.get("n_apontamentos"),
        })
    return saida


def obter_ou_criar_analise(evento: dict, username: str) -> tuple[Optional[dict], bool]:
    """Retorna a análise da parada, criando-a na primeira abertura.

    Idempotente (caso obrigatório 5): reabrir a página **nunca** duplica a
    análise nem recria os nós iniciais. A corrida entre dois cliques é resolvida
    pelo índice único em `parada_chave` — quem perder relê o documento do
    vencedor em vez de estourar erro.

    Retorna (analise, criada_agora).
    """
    chave = evento.get("chave")
    if not chave:
        return None, False

    existente = carregar_analise(chave)
    if existente:
        return existente, False

    col = _colecao()
    if col is None:
        return None, False

    agora = datetime.now()
    from src.utils.failure_events import titulo_sugerido

    doc: dict[str, Any] = {
        "parada_chave": chave,
        # Título: identidade da parada, derivada do relato do ZPP. Gravado uma
        # vez na criação e nunca mais alterado — não está em CAMPOS_EDITAVEIS.
        "titulo": titulo_sugerido(evento),
        # Nome: rótulo livre do usuário para se referir à parada. Nasce vazio.
        "nome": "",
        "tipo_analise": "",
        "responsavel": username or "",
        "participantes": "",
        "status": STATUS_ABERTA,
        "versao": 1,
        # Snapshot da parada no momento da criação. Preserva o nome histórico do
        # equipamento e a duração oficial mesmo que o ZPP seja reprocessado ou o
        # equipamento saia de operação (caso especial da spec).
        "parada": {
            "equipamento": evento.get("equipamento"),
            "equipamento_nome": _nome_equip(evento.get("equipamento")),
            "causa": evento.get("causa"),
            "rotulo": evento.get("rotulo"),
            "inicio": evento.get("inicio"),
            "fim": evento.get("fim"),
            "duracao_min": evento.get("duracao_min"),
            "n_apontamentos": evento.get("n_apontamentos"),
            # Parada MENSAL (BR-AF2-02): nº de dias com avaria no mês + a composição
            # diária (`por_dia`), base do drill "1 grande vs várias pequenas". O `dia`
            # vai como ISO string — `date` não é serializável em BSON/JSON.
            "n_dias": evento.get("n_dias"),
            "por_dia": _serializar_por_dia(evento.get("por_dia")),
            "ordens": evento.get("ordens"),
        },
        "data_inicio_analise": agora,
        "data_conclusao_analise": None,
        "observacoes": "",
        "criado_por": username or "",
        "criado_em": agora,
        "atualizado_por": username or "",
        "atualizado_em": agora,
    }
    # Seções A3 (1,2,4,5,6), pré-preenchendo o que vem da parada.
    from src.utils.failure_a3 import secoes_iniciais
    doc.update(secoes_iniciais(evento))

    try:
        res = col.insert_one(doc)
        analysis_id = str(res.inserted_id)
        nos = _arvore_inicial(analysis_id, evento)
        col.update_one({"_id": res.inserted_id}, {"$set": {"nos": nos}})
        doc["_id"] = res.inserted_id
        doc["nos"] = nos
        return _doc_para_analise(doc), True
    except Exception as e:
        # DuplicateKeyError → outro request criou primeiro; relê o vencedor.
        existente = carregar_analise(chave)
        if existente:
            return existente, False
        print(f"[failure_analysis_db] falha ao criar análise {chave}: {e}")
        return None, False


def _nome_equip(equipamento: Optional[str]) -> str:
    """Nome de exibição do equipamento, tolerante a import indisponível."""
    if not equipamento:
        return ""
    try:
        from src.utils.failure_events import nome_equipamento
        return nome_equipamento(equipamento)
    except Exception:
        return equipamento


def salvar_arvore(
    analysis_id: str,
    versao: int,
    nos: list[dict],
    duracao_total_min: float,
    username: str,
) -> tuple[bool, str]:
    """Persiste a árvore inteira num único update atômico.

    Valida no backend antes de escrever (a spec exige não confiar no frontend):
    raiz única, sem ciclo, pai da mesma análise, duração não negativa. Os tempos
    são redistribuídos aqui também — o cliente não é fonte de verdade do rateio.

    Falha com mensagem de conflito se a análise mudou desde a leitura (`versao`).
    """
    col = _colecao()
    if col is None:
        return False, "Banco de dados indisponível."

    ok, msg = validar_arvore(nos, analysis_id)
    if not ok:
        return False, msg

    nos = distribuir_tempos(nos, duracao_total_min)

    try:
        from bson import ObjectId
        res = col.update_one(
            {"_id": ObjectId(analysis_id), "versao": versao, "status": STATUS_ABERTA},
            {
                "$set": {
                    "nos": nos,
                    "atualizado_por": username or "",
                    "atualizado_em": datetime.now(),
                },
                "$inc": {"versao": 1},
            },
        )
    except Exception as e:
        return False, f"Falha ao salvar: {e}"

    if res.matched_count == 0:
        return False, (
            "A análise foi alterada por outro usuário ou já está concluída. "
            "Recarregue a página para ver a versão atual."
        )
    return True, "Alterações salvas."


def atualizar_campos(
    analysis_id: str,
    versao: int,
    campos: dict,
    username: str,
) -> tuple[bool, str]:
    """Atualiza campos gerais do cabeçalho (whitelist `CAMPOS_EDITAVEIS`).

    Campo ausente do dict não é tocado — deixar um campo temporariamente vazio na
    edição não apaga o valor antigo de outro campo (caso especial da spec).
    """
    col = _colecao()
    if col is None:
        return False, "Banco de dados indisponível."

    updates = {k: v for k, v in campos.items() if k in CAMPOS_EDITAVEIS}
    if not updates:
        return False, "Nenhum campo válido para atualizar."

    updates["atualizado_por"] = username or ""
    updates["atualizado_em"] = datetime.now()

    try:
        from bson import ObjectId
        res = col.update_one(
            {"_id": ObjectId(analysis_id), "versao": versao, "status": STATUS_ABERTA},
            {"$set": updates, "$inc": {"versao": 1}},
        )
    except Exception as e:
        return False, f"Falha ao salvar: {e}"

    if res.matched_count == 0:
        return False, (
            "A análise foi alterada por outro usuário ou já está concluída. "
            "Recarregue a página."
        )
    return True, "Alterações salvas."


def salvar_secoes(
    analysis_id: str,
    versao: int,
    secoes: dict,
    username: str,
) -> tuple[bool, str]:
    """Persiste as seções A3 abaixo do diagrama (Seção 16), com trava de versão.

    Whitelist explícita (`failure_a3.SECOES`): só as chaves de seção conhecidas são
    gravadas — não se escreve chave arbitrária vinda do cliente. Condicionada à
    versão (concorrência otimista) e ao status aberto.
    """
    from src.utils.failure_a3 import SECOES

    col = _colecao()
    if col is None:
        return False, "Banco de dados indisponível."

    updates = {k: secoes[k] for k in SECOES if k in (secoes or {})}
    if not updates:
        return True, ""  # nada a gravar não é erro (análise sem seções tocadas)

    updates["atualizado_por"] = username or ""
    updates["atualizado_em"] = datetime.now()

    try:
        from bson import ObjectId
        res = col.update_one(
            {"_id": ObjectId(analysis_id), "versao": versao, "status": STATUS_ABERTA},
            {"$set": updates, "$inc": {"versao": 1}},
        )
    except Exception as e:
        return False, f"Falha ao salvar seções: {e}"

    if res.matched_count == 0:
        return False, (
            "A análise foi alterada por outro usuário ou já está concluída. "
            "Recarregue a página."
        )
    return True, "Seções salvas."


def entregar_analise(
    analysis_id: str,
    versao: int,
    nos: list[dict],
    acoes: list[dict],
    duracao_total_min: float,
    username: str,
) -> tuple[bool, str]:
    """Entrega a análise ao gestor, travando-a para edição (BR-13, BR-14).

    Em linguagem simples: quem fez diz "terminei". A partir daqui ninguém edita — a
    análise entra na fila do gestor, que aceita ou devolve com motivo. Se quem fez
    precisar corrigir alguma coisa, pede a devolução.

    Era o "concluir" de antes. A palavra mudou porque o significado mudou: concluída
    dava a entender que acabou, quando ainda falta o aceite.

    Bloqueia quando: (a) os tempos manuais não fecham com a duração da parada; ou
    (b) falta algum requisito da BR-14 — causa raiz marcada, toda causa com ação
    escrita, toda ação com responsável e prazo. A mensagem lista o que falta, item a
    item: a pessoa precisa saber o que corrigir, não apenas que não pode entregar.
    """
    from src.utils.failure_a3 import pode_entregar
    from src.utils.failure_tree import validar_tempos

    ok, msg = validar_tempos(nos, duracao_total_min)
    if not ok:
        return False, f"Não é possível entregar: {msg}"

    ok, faltas = pode_entregar(nos or [], acoes or [])
    if not ok:
        return False, "Não é possível entregar ainda: " + "; ".join(faltas)

    col = _colecao()
    if col is None:
        return False, "Banco de dados indisponível."

    agora = datetime.now()
    passagem = {"acao": "entregue", "por": username or "", "em": agora}
    try:
        from bson import ObjectId
        res = col.update_one(
            # O estado entra no FILTRO, e não numa leitura antes: dois cliques ao
            # mesmo tempo não podem gerar duas entregas.
            {"_id": ObjectId(analysis_id), "versao": versao, "status": STATUS_ABERTA},
            {
                "$set": {
                    "status": STATUS_CONCLUIDA,
                    "data_conclusao_analise": agora,
                    "concluido_por": username or "",
                    "atualizado_por": username or "",
                    "atualizado_em": agora,
                    "aceite.aceito_por": None,
                    "aceite.aceito_em": None,
                },
                "$push": {"aceite.passagens": passagem},
                "$inc": {"versao": 1},
            },
        )
    except Exception as e:
        return False, f"Falha ao entregar: {e}"

    if res.matched_count == 0:
        return False, "A análise já foi entregue ou foi alterada por outro usuário."
    return True, "Análise entregue ao gestor."


def aceitar_analise(analysis_id: str, username: str) -> tuple[bool, str]:
    """O gestor aceita a análise entregue (BR-15).

    A partir daqui ela conta como analisada no quadro e sai da fila. Segue travada:
    o que foi aceito precisa continuar sendo o que ele aceitou.

    Só aceita análise **entregue** — o estado vai no filtro da atualização, então dois
    gestores clicando junto não geram dois aceites.
    """
    col = _colecao()
    if col is None:
        return False, "Banco de dados indisponível."

    agora = datetime.now()
    try:
        from bson import ObjectId
        res = col.update_one(
            {"_id": ObjectId(analysis_id), "status": STATUS_CONCLUIDA,
             "aceite.aceito_em": None},
            {
                "$set": {
                    "aceite.aceito_por": username or "",
                    "aceite.aceito_em": agora,
                    "atualizado_por": username or "",
                    "atualizado_em": agora,
                },
                "$push": {"aceite.passagens": {"acao": "aceita", "por": username or "",
                                               "em": agora}},
                "$inc": {"versao": 1},
            },
        )
    except Exception as e:
        return False, f"Falha ao aceitar: {e}"

    if res.matched_count == 0:
        return False, "Esta análise não está aguardando aceite."
    return True, "Análise aceita."


def devolver_analise(analysis_id: str, username: str, motivo: str) -> tuple[bool, str]:
    """O gestor devolve a análise, com motivo, e ela volta a ser editável (BR-15).

    Devolver é o **único** jeito de destravar: quem quiser corrigir uma análise
    entregue ou aceita pede ao gestor. Assim toda mudança depois da entrega tem um
    responsável com nome e data.

    O motivo é obrigatório — devolução sem motivo obriga quem recebe a adivinhar, e
    adivinhação vira retrabalho às cegas. O histórico guarda todas as devoluções, não
    só a última: quem perguntar por que aquela análise levou dois meses vai querer ler
    as anteriores.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        return False, "Escreva o motivo da devolução."

    col = _colecao()
    if col is None:
        return False, "Banco de dados indisponível."

    agora = datetime.now()
    try:
        from bson import ObjectId
        res = col.update_one(
            {"_id": ObjectId(analysis_id), "status": STATUS_CONCLUIDA},
            {
                "$set": {
                    "status": STATUS_ABERTA,
                    "aceite.aceito_por": None,
                    "aceite.aceito_em": None,
                    "atualizado_por": username or "",
                    "atualizado_em": agora,
                },
                "$push": {"aceite.passagens": {"acao": "devolvida", "por": username or "",
                                               "em": agora, "motivo": motivo}},
                "$inc": {"versao": 1},
            },
        )
    except Exception as e:
        return False, f"Falha ao devolver: {e}"

    if res.matched_count == 0:
        return False, "Esta análise não está entregue nem aceita."
    return True, "Análise devolvida a quem a fez."


def garantir_opcao_atual(opcoes: list[dict], valor) -> list[dict]:
    """Garante que o(s) valor(es) já gravado(s) apareçam nas opções do select.

    Sem isso, um responsável que saiu da collection `usuarios` (ou que é de outro
    perfil) sumiria do dropdown; como o dropdown não exibe valor fora das opções,
    o campo renderizaria vazio e o próximo "Salvar" apagaria em silêncio quem era
    o responsável. Preserva o nome histórico, marcando-o como indisponível.

    Aceita um nome (campos de responsável único, como o do cabeçalho) ou uma lista
    de nomes — cada ação do Plano de Ação pode ter mais de um responsável.
    """
    valores = valor if isinstance(valor, (list, tuple)) else [valor]
    faltantes = []
    conhecidos = {o.get("value") for o in opcoes}
    for v in valores:
        if v and v not in conhecidos and v not in faltantes:
            faltantes.append(v)
    if not faltantes:
        return opcoes
    return [{"label": f"{v} (inativo)", "value": v} for v in faltantes] + list(opcoes)


def opcoes_responsaveis(perfil: str, valor_atual=None) -> list[dict]:
    """Opções de responsável a partir da collection `usuarios`.

    Reusa `workflow_db.get_usuarios_por_perfil`, que já implementa a regra do
    projeto: admin enxerga todos os usuários; os demais, só o próprio perfil.
    """
    from src.utils.workflow_db import get_usuarios_por_perfil

    try:
        opcoes = get_usuarios_por_perfil(perfil) or []
    except Exception as e:
        print(f"[failure_analysis_db] falha ao listar usuários: {e}")
        opcoes = []
    return garantir_opcao_atual(opcoes, valor_atual)


def listar_analises_do_mes(mes_ref: str) -> list[dict]:
    """Todas as análises de um mês (`mes_ref` = 'AAAAMM'), da parada mais longa para a
    mais curta.

    Parte das **análises**, não da lista de paradas da tela: uma análise cuja parada
    saiu da agregação (relato editado no SAP muda o hash da chave) some da listagem mas
    continua existindo — e precisa aparecer no material mensal. Ver o exportador de
    slides (`failure_slides`).
    """
    col = _colecao()
    if col is None or not (mes_ref or "").isdigit():
        return []
    try:
        docs = list(col.find({"parada_chave": {"$regex": f"_{mes_ref}_"}}))
    except Exception as e:
        print(f"[failure_analysis_db] falha ao listar análises de {mes_ref}: {e}")
        return []
    analises = [_doc_para_analise(d) for d in docs]
    analises.sort(key=lambda a: -((a.get("parada") or {}).get("duracao_min") or 0))
    return analises


def contar_analises_do_mes(mes_ref: str) -> int:
    """Quantas análises existem num mês (`mes_ref` = 'AAAAMM'), sem carregar os documentos.

    Serve ao botão "Exportar slides do mês": ele precisa enxergar o mesmo universo do
    exportador — as **análises**, não as paradas listadas na tela. A análise órfã (cuja
    parada saiu da agregação) não aparece na lista mas entra no material, então contar
    pela tabela deixaria o botão apagado com trabalho para exportar.
    """
    col = _colecao()
    if col is None or not (mes_ref or "").isdigit():
        return 0
    try:
        return int(col.count_documents({"parada_chave": {"$regex": f"_{mes_ref}_"}}))
    except Exception as e:
        print(f"[failure_analysis_db] falha ao contar análises de {mes_ref}: {e}")
        return 0


def chaves_com_analise(chaves: list[str]) -> dict[str, str]:
    """Mapeia chave de parada → status da análise, para as chaves informadas.

    Serve para a listagem marcar quais paradas já têm análise, numa query só em
    vez de uma por linha.
    """
    col = _colecao()
    if col is None or not chaves:
        return {}
    try:
        docs = col.find(
            {"parada_chave": {"$in": list(chaves)}},
            {"_id": 0, "parada_chave": 1, "status": 1},
        )
        return {d["parada_chave"]: d.get("status", STATUS_ABERTA) for d in docs}
    except Exception as e:
        print(f"[failure_analysis_db] falha ao consultar análises existentes: {e}")
        return {}


# ---------------------------------------------------------------------------
# Fotos (galeria da análise) — campo `fotos` no topo do documento, independente
# de `secoes`. Só metadados aqui; os bytes vivem no file server (ver
# failure_photos_storage). SDD analise-falhas-fotos (BR-05/07/08).
# ---------------------------------------------------------------------------

MAX_FOTOS = 30  # por análise (BR-08)


def listar_fotos(analysis_id: str) -> list[dict]:
    """Lista de fichas de foto da análise (vazia se não houver ou em erro)."""
    col = _colecao()
    if col is None:
        return []
    try:
        from bson import ObjectId
        doc = col.find_one({"_id": ObjectId(analysis_id)}, {"_id": 0, "fotos": 1})
        return (doc or {}).get("fotos") or []
    except Exception as e:
        print(f"[failure_analysis_db] falha ao listar fotos: {e}")
        return []


def adicionar_foto(
    analysis_id: str, foto: dict, username: str
) -> tuple[bool, str, Optional[dict]]:
    """Registra a ficha de uma foto na análise (`$push` em `fotos`).

    Só com a análise **aberta** (BR-05) e abaixo do limite de 30 (BR-08). Recebe o
    dict de metadados já gerado pelo storage (arquivo/thumb/dimensões/bytes/mime) e
    completa id/legenda/autoria. Devolve o item gravado (para o front exibir)."""
    col = _colecao()
    if col is None:
        return False, "Banco de dados indisponível.", None
    try:
        import uuid
        from bson import ObjectId
        doc = col.find_one({"_id": ObjectId(analysis_id)}, {"status": 1, "fotos": 1})
        if not doc:
            return False, "Análise não encontrada.", None
        if doc.get("status") != STATUS_ABERTA:
            return False, "Análise concluída — reabra para adicionar fotos.", None
        if len(doc.get("fotos") or []) >= MAX_FOTOS:
            return False, f"Limite de {MAX_FOTOS} fotos por análise atingido.", None

        item = {
            "id": uuid.uuid4().hex,
            "legenda": (foto.get("legenda") or "").strip(),
            "enviada_por": username or "",
            "enviada_em": datetime.now(),
        }
        for k in ("arquivo", "thumb", "largura", "altura", "bytes", "mime"):
            if k in foto:
                item[k] = foto[k]

        res = col.update_one(
            {"_id": ObjectId(analysis_id), "status": STATUS_ABERTA},
            {"$push": {"fotos": item}},
        )
        if res.modified_count == 0:
            return False, "Não foi possível adicionar a foto (análise alterada?).", None
        return True, "Foto adicionada.", item
    except Exception as e:
        print(f"[failure_analysis_db] falha ao adicionar foto: {e}")
        return False, "Falha ao registrar a foto.", None


def remover_foto(
    analysis_id: str, foto_id: str, username: str, nivel: int
) -> tuple[bool, str, Optional[dict]]:
    """Remove a ficha de uma foto (`$pull`), devolvendo o item removido para o
    chamador apagar os arquivos no file server (BR-07 — hard delete).

    Só com a análise **aberta**; autorizado ao **autor** (`enviada_por`) ou a um
    **nível ≥ 3**."""
    col = _colecao()
    if col is None:
        return False, "Banco de dados indisponível.", None
    try:
        from bson import ObjectId
        doc = col.find_one({"_id": ObjectId(analysis_id)}, {"status": 1, "fotos": 1})
        if not doc:
            return False, "Análise não encontrada.", None
        if doc.get("status") != STATUS_ABERTA:
            return False, "Análise concluída — reabra para excluir fotos.", None
        item = next((f for f in (doc.get("fotos") or []) if f.get("id") == foto_id), None)
        if not item:
            return False, "Foto não encontrada.", None
        if item.get("enviada_por") != username and (nivel or 0) < 3:
            return False, "Só o autor da foto ou um administrador (nível 3) pode excluir.", None

        res = col.update_one(
            {"_id": ObjectId(analysis_id), "status": STATUS_ABERTA},
            {"$pull": {"fotos": {"id": foto_id}}},
        )
        if res.modified_count == 0:
            return False, "Não foi possível excluir a foto.", None
        return True, "Foto excluída.", item
    except Exception as e:
        print(f"[failure_analysis_db] falha ao remover foto: {e}")
        return False, "Falha ao excluir a foto.", None


def editar_legenda_foto(
    analysis_id: str, foto_id: str, legenda: str, username: str
) -> tuple[bool, str]:
    """Atualiza a legenda de uma foto (`$set` em `fotos.$.legenda`). Só com a
    análise aberta."""
    col = _colecao()
    if col is None:
        return False, "Banco de dados indisponível."
    try:
        from bson import ObjectId
        res = col.update_one(
            {"_id": ObjectId(analysis_id), "status": STATUS_ABERTA, "fotos.id": foto_id},
            {"$set": {"fotos.$.legenda": (legenda or "").strip(),
                      "atualizado_por": username or "", "atualizado_em": datetime.now()}},
        )
        if res.matched_count == 0:
            return False, "Foto não encontrada ou análise concluída."
        return True, "Legenda salva."
    except Exception as e:
        print(f"[failure_analysis_db] falha ao editar legenda: {e}")
        return False, "Falha ao salvar a legenda."


def atualizar_dims_foto(analysis_id: str, foto_id: str, largura: int, altura: int) -> tuple[bool, str]:
    """Atualiza largura/altura de uma foto após edição (ex.: rotação 90°/270° troca
    os lados) e incrementa `rev` — a UI usa `rev` como cache-buster do `<img>` (mesmo
    nome de arquivo, conteúdo novo). Só com a análise aberta."""
    col = _colecao()
    if col is None:
        return False, "Banco de dados indisponível."
    try:
        from bson import ObjectId
        res = col.update_one(
            {"_id": ObjectId(analysis_id), "status": STATUS_ABERTA, "fotos.id": foto_id},
            {"$set": {"fotos.$.largura": int(largura), "fotos.$.altura": int(altura)},
             "$inc": {"fotos.$.rev": 1}},
        )
        if res.matched_count == 0:
            return False, "Foto não encontrada ou análise concluída."
        return True, "ok"
    except Exception as e:
        print(f"[failure_analysis_db] falha ao atualizar dimensões: {e}")
        return False, "Falha ao atualizar a foto."
