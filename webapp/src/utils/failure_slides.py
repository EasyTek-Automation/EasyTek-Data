# src/utils/failure_slides.py

"""
Montador de dados do material mensal da Análise de Falhas (bloco S1 da proposta
`analise-falhas-v2/PROPOSTA-slide-mensal.md`).

Recebe as análises de um mês e devolve, para cada uma, um dicionário já mastigado
para virar **um slide**: cabeçalho, textos das seções, árvore de causas achatada em
níveis, linhas do Plano de Ação com o nome da causa e o status por extenso, e os
caminhos das fotos.

Camada **pura**: não fala com o Mongo (quem busca é
`failure_analysis_db.listar_analises_do_mes`) e não desenha nada. Só o acesso ao
file server para resolver o caminho das fotos é externo, e é tolerante a falha —
file server fora do ar devolve slide sem foto, nunca exceção.

Decisões de negócio que moram aqui (da proposta, respondidas em 2026-08-05):
- entram **todas** as análises do mês, concluídas ou não;
- as **não iniciadas** (nenhum texto, nenhuma ação, árvore só com o balão da parada e o
  do relato) saem da sequência de slides e viram uma **lista** no fim do material;
- no máximo **4 fotos** por slide, com marcação de quantas ficaram de fora.
"""

from __future__ import annotations

from typing import Any, Optional

from src.utils.failure_a3 import STATUS_ACAO, texto_responsaveis
from src.utils.failure_tree import indexar

# Até 4 fotos por slide (média real do cliente é 2, pico 8 — medição de 2026-08-05).
MAX_FOTOS_SLIDE = 4

# Uma análise "não iniciada" tem, no máximo, o balão da parada (ROOT) e o do relato
# (o primeiro STEP, criado junto com a análise).
NOS_INICIAIS = 2

_MESES_PT = ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


# ---------------------------------------------------------------------------
# Leitura tolerante do documento
# ---------------------------------------------------------------------------

def _txt(valor: Any) -> str:
    """Texto limpo — `None`, número ou espaço em branco viram string vazia."""
    return str(valor).strip() if valor not in (None, "") else ""


def _sec(analise: dict, secao: str, campo: str) -> str:
    return _txt((analise.get(secao) or {}).get(campo))


def esta_iniciada(analise: dict) -> bool:
    """A análise saiu do papel?

    Em linguagem simples: alguém escreveu alguma coisa, montou algum balão além dos
    dois que nascem com a análise, ou registrou alguma ação. Uma análise aberta e nunca
    tocada responde `False` — e vai para a lista do fim do material, em vez de virar um
    slide em branco.
    """
    if len(analise.get("nos") or []) > NOS_INICIAIS:
        return True
    if analise.get("actions"):
        return True
    campos = (("problema", "descricao"), ("problema", "observacoes"),
              ("contencao", "acoes"), ("sustainability", "licoes"))
    return any(_sec(analise, s, c) for s, c in campos)


# ---------------------------------------------------------------------------
# Pedaços do slide
# ---------------------------------------------------------------------------

def cabecalho(analise: dict) -> dict:
    """Faixa do topo: equipamento, relato, duração e o contexto da parada."""
    parada = analise.get("parada") or {}
    dur = int(parada.get("duracao_min") or 0)
    return {
        "equipamento": _txt(parada.get("equipamento_nome")) or _txt(parada.get("equipamento")),
        "relato": _txt(analise.get("titulo")) or _txt(parada.get("rotulo")),
        "nome": _txt(analise.get("nome")),
        "duracao_min": dur,
        "duracao_texto": f"{dur // 60} h {dur % 60} min" if dur >= 60 else f"{dur} min",
        "n_apontamentos": int(parada.get("n_apontamentos") or 0),
        "n_ordens": len(parada.get("ordens") or []),
        "n_dias": int(parada.get("n_dias") or 0),
        "status": _txt(analise.get("status")),
        "responsavel": _txt(analise.get("responsavel")),
        "chave": _txt(analise.get("parada_chave")),
    }


def arvore_em_niveis(nos: list[dict]) -> list[dict]:
    """Achata a árvore de causas numa lista pronta para desenhar.

    Cada balão ganha o seu nível (0 = a parada), a ordem em que deve aparecer e quantos
    filhos tem. Quem desenha não precisa reconstruir a hierarquia — só posicionar.

    Exemplo: a parada da LCL-4,5 com 11 balões em 3 níveis vira 11 itens, o primeiro
    com `nivel=0`, os dois primeiros filhos com `nivel=1`, e assim por diante.
    """
    nos = list(nos or [])
    if not nos:
        return []
    filhos: dict[Optional[str], list[dict]] = {}
    for n in nos:
        filhos.setdefault(n.get("parent_id"), []).append(n)
    for irmaos in filhos.values():
        irmaos.sort(key=lambda n: (n.get("sort_order") or 0, _txt(n.get("titulo"))))

    raiz = next((n for n in nos if not n.get("parent_id")), None)
    if raiz is None:                      # árvore corrompida: devolve rasa, sem perder nada
        return [{"id": n.get("id"), "nivel": 0, "ordem": i, "titulo": _txt(n.get("titulo")),
                 "tipo": n.get("tipo"), "duration_min": n.get("duration_min"),
                 "causa_raiz": bool(n.get("is_root_cause")), "n_filhos": 0,
                 "parent_id": n.get("parent_id")}
                for i, n in enumerate(nos)]

    saida: list[dict] = []

    def visitar(no: dict, nivel: int) -> None:
        kids = filhos.get(no.get("id")) or []
        saida.append({
            "id": no.get("id"),
            "parent_id": no.get("parent_id"),
            "nivel": nivel,
            "ordem": len(saida),
            "titulo": _txt(no.get("titulo")),
            "tipo": no.get("tipo"),
            "duration_min": no.get("duration_min"),
            "causa_raiz": bool(no.get("is_root_cause")),
            "n_filhos": len(kids),
        })
        for k in kids:
            visitar(k, nivel + 1)

    visitar(raiz, 0)
    return saida


def acoes(analise: dict) -> list[dict]:
    """Linhas do Plano de Ação, cada uma já com o nome da causa e o status por extenso.

    A causa não é copiada no banco: a linha guarda só o `node_id` do balão marcado com
    ★, e o texto vem do balão no momento da leitura. Se o balão sumiu, a linha aparece
    sem causa em vez de sumir junto.
    """
    idx = indexar(analise.get("nos") or [])
    saida = []
    for a in (analise.get("actions") or []):
        no = idx.get(a.get("node_id")) or {}
        status = a.get("status")
        saida.append({
            "causa": _txt(no.get("titulo")),
            "descricao": _txt(a.get("descricao")),
            # Uma ação pode ter vários responsáveis; no slide eles saem numa linha
            # só ("João, Thiago"). Análise antiga guardou um texto — mesmo caminho.
            "responsavel": texto_responsaveis(a.get("responsavel")),
            "prazo": _txt(a.get("prazo")),
            "status": status,
            "status_texto": STATUS_ACAO.get(status, ""),
            "node_id": a.get("node_id"),
        })
    return saida


def fotos(analise: dict, limite: int = MAX_FOTOS_SLIDE) -> dict:
    """Fotos do slide: caminho no file server + legenda, no máximo `limite`.

    O documento guarda só o **nome** do arquivo; a pasta é
    `{raiz}/{ano}/{mês}/{equipamento_causa_id}`. Foto cujo arquivo não está no file
    server é descartada em silêncio — o material mensal não pode quebrar porque uma
    imagem sumiu.
    """
    fichas = list(analise.get("fotos") or [])
    escolhidas: list[dict] = []
    try:
        from src.utils import failure_photos_storage as storage
        subpasta = storage.nome_pasta_analise(analise)
        mes = storage.mes_ref(analise)
        for f in fichas:
            if len(escolhidas) >= limite:
                break
            nome = _txt(f.get("arquivo"))
            if not nome:
                continue
            caminho = storage.caminho(subpasta, mes, nome)
            if caminho and caminho.exists():
                escolhidas.append({"caminho": str(caminho), "legenda": _txt(f.get("legenda")),
                                   "largura": f.get("largura"), "altura": f.get("altura")})
    except Exception as e:                      # file server fora do ar (BR-09 das fotos)
        print(f"[failure_slides] fotos indisponíveis para {analise.get('parada_chave')}: {e}")
        escolhidas = []
    return {"itens": escolhidas, "total": len(fichas),
            "ocultas": max(0, len(fichas) - len(escolhidas))}


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------

def imagem_diagrama(analise: dict) -> Optional[dict]:
    """Imagem do quadro guardada para esta análise, se ainda vale; senão None.
    Tolerante a falha, como as fotos: file server fora não derruba o material."""
    from src.utils.failure_diagram_image import carregar_valido
    return carregar_valido(analise)


def montar_slide(analise: dict, limite_fotos: int = MAX_FOTOS_SLIDE) -> dict:
    """Uma análise → o conteúdo de um slide."""
    return {
        "id": analise.get("id"),
        "chave": _txt(analise.get("parada_chave")),
        "cabecalho": cabecalho(analise),
        "problema": {
            "descricao": _sec(analise, "problema", "descricao"),
            "area": _sec(analise, "problema", "area"),
            "equipamento": _sec(analise, "problema", "equipamento"),
            "subgrupo": _sec(analise, "problema", "subgrupo"),
            "observacoes": _sec(analise, "problema", "observacoes"),
        },
        "contencao": {
            "acoes": _sec(analise, "contencao", "acoes"),
            "local": _sec(analise, "contencao", "local"),
            "responsavel": _sec(analise, "contencao", "responsavel"),
            "inicio": _sec(analise, "contencao", "inicio"),
        },
        "arvore": arvore_em_niveis(analise.get("nos") or []),
        "acoes": acoes(analise),
        "licoes": _sec(analise, "sustainability", "licoes"),
        "encerramento": {
            "responsavel": _sec(analise, "closing", "responsavel"),
            "data": _sec(analise, "closing", "data"),
        },
        "fotos": fotos(analise, limite_fotos),
        # Desenho do próprio quadro (SVG + PNG), se a imagem guardada ainda vale para a
        # árvore do banco; None = o slide redesenha a árvore no servidor (IM-AF3-08).
        "diagrama": imagem_diagrama(analise),
        "concluida": _txt(analise.get("status")) == "concluida",
    }


def resumo_nao_iniciada(analise: dict) -> dict:
    """Uma linha da lista do fim do material, para as análises nunca trabalhadas."""
    c = cabecalho(analise)
    return {"equipamento": c["equipamento"], "relato": c["relato"],
            "duracao_texto": c["duracao_texto"], "duracao_min": c["duracao_min"],
            "chave": c["chave"], "responsavel": c["responsavel"]}


def montar_mes(analises: list[dict], ano: int, mes: int,
               limite_fotos: int = MAX_FOTOS_SLIDE) -> dict:
    """Todas as análises do mês → o material inteiro.

    Devolve os **slides** (análises com algum trabalho feito, da parada mais longa para
    a mais curta) e, à parte, a **lista das não iniciadas** — que viram uma tabela num
    slide só no fim, em vez de páginas em branco.
    """
    ordenadas = sorted(analises or [],
                       key=lambda a: -((a.get("parada") or {}).get("duracao_min") or 0))
    slides, pendentes = [], []
    for a in ordenadas:
        if esta_iniciada(a):
            slides.append(montar_slide(a, limite_fotos))
        else:
            pendentes.append(resumo_nao_iniciada(a))
    mes_nome = _MESES_PT[mes - 1] if 1 <= mes <= 12 else str(mes)
    return {
        "ano": ano,
        "mes": mes,
        "mes_ref": f"{ano:04d}{mes:02d}",
        "titulo": f"Análises de Falha — {mes_nome} de {ano}",
        "slides": slides,
        "nao_iniciadas": pendentes,
        "total_analises": len(ordenadas),
        "total_fotos": sum(s["fotos"]["total"] for s in slides),
    }


def montar_mes_do_banco(ano: int, mes: int, limite_fotos: int = MAX_FOTOS_SLIDE) -> dict:
    """Atalho para uso na aplicação: busca no Mongo e monta o material do mês."""
    from src.utils import failure_analysis_db as fdb

    return montar_mes(fdb.listar_analises_do_mes(f"{ano:04d}{mes:02d}"),
                      ano, mes, limite_fotos)
