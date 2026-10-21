# src/utils/failure_slides_pptx.py

"""
Gerador do material mensal da Análise de Falhas em PowerPoint (S3 da proposta
`analise-falhas-v2/PROPOSTA-slide-mensal.md`).

Um arquivo `.pptx` por mês, no formato 16:9: capa, **um slide por análise** e, no fim,
a lista das análises abertas que ninguém trabalhou ainda. O texto é texto de verdade —
dá para corrigir uma frase antes da reunião e colar um slide noutro deck; só a árvore
de causas e as fotos são imagem.

Recebe o material já mastigado por `failure_slides.montar_mes`; não fala com o banco.

O dimensionamento das caixas veio da medição do recorte real do cliente (2026-08-05):
descrição do problema chega a 500 caracteres, contenção a 225, lições a 334, e o Plano
de Ação a 6 linhas com descrição de até 369.
"""

from __future__ import annotations

import io
import textwrap
from typing import Any, Optional

from src.utils.failure_tree_image import desenhar as desenhar_arvore

# Paleta da IDENTIDADE VISUAL DO CLIENTE, tirada do slide-modelo que ele mandou
# (`prototipos/analise-falha-TRANS001-2026-07 (3).pptx`, 2º slide): faixa vertical azul
# na borda direita e um quarto de anel laranja no canto inferior direito.
AZUL = (0, 83, 128)          # #005380 — azul institucional
AZUL_CLARO = (232, 240, 247)
LARANJA = (255, 55, 0)       # #ff3700 — laranja do arco
VERDE = (46, 125, 50)
CINZA = (107, 114, 128)
CINZA_FUNDO = (243, 244, 246)
BRANCO = (255, 255, 255)
PRETO = (17, 24, 39)

_CORES_STATUS = {1: LARANJA, 2: AZUL, 3: VERDE, 4: VERDE}

# Moldura da identidade, em cm (medidas do slide-modelo do cliente).
BARRA_X, BARRA_W = 30.95, 2.92      # faixa vertical azul, da borda de cima à de baixo
ARCO_LADO = 4.82                    # quarto de anel laranja, colado no canto inferior
ARCO_X = 33.87 - 4.82 - 0.15        # onde o arco começa (o conteúdo para antes dele)
ARCO_RAIO_INTERNO = 0.4453          # proporção do raio (do SVG original)
MARGEM_DIREITA = 30.55              # onde o conteúdo tem de parar, antes da faixa

# Limites de texto por caixa (caracteres) — do tamanho real medido, com folga.
LIM_PROBLEMA = 620
LIM_CONTENCAO = 300
LIM_LICOES = 420
LIM_ACAO = 190
MAX_ACOES_SLIDE = 6


def _rgb(cor):
    from pptx.dml.color import RGBColor

    return RGBColor(*cor)


def _cm(valor: float):
    from pptx.util import Cm

    return Cm(valor)


def _corta(texto: str, limite: int) -> str:
    texto = (texto or "").strip()
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _caixa_texto(slide, x, y, w, h, texto, *, tamanho=11, negrito=False, cor=PRETO,
                 alinhamento=None, espaco_linha=0.95):
    from pptx.util import Pt

    caixa = slide.shapes.add_textbox(_cm(x), _cm(y), _cm(w), _cm(h))
    quadro = caixa.text_frame
    quadro.word_wrap = True
    # Sem as margens internas padrão (~0,25 cm de cada lado): elas comiam largura que
    # o cálculo de quebra de linha não enxergava, e o texto quebrava antes do previsto
    # ("RESPONS ÁVEL", "Aprovad o").
    quadro.margin_left = quadro.margin_right = 0
    quadro.margin_top = quadro.margin_bottom = 0
    quadro.text = texto or ""
    for p in quadro.paragraphs:
        if alinhamento is not None:
            p.alignment = alinhamento
        p.line_spacing = espaco_linha
        for run in p.runs:
            run.font.size = Pt(tamanho)
            run.font.bold = negrito
            run.font.color.rgb = _rgb(cor)
            run.font.name = "Calibri"
    return caixa


def _painel(slide, x, y, w, h, titulo, *, fundo=CINZA_FUNDO):
    """Bloco cinza com título azul — o mesmo enquadramento das seções do A3."""
    from pptx.enum.shapes import MSO_SHAPE

    forma = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   _cm(x), _cm(y), _cm(w), _cm(h))
    forma.fill.solid()
    forma.fill.fore_color.rgb = _rgb(fundo)
    forma.line.fill.background()
    forma.shadow.inherit = False
    forma.text_frame.text = ""
    if titulo:
        _caixa_texto(slide, x + 0.25, y + 0.12, w - 0.4, 0.6, titulo.upper(),
                     tamanho=9.5, negrito=True, cor=AZUL)
    return forma


def _capa(prs, material: dict) -> None:
    from pptx.enum.text import PP_ALIGN

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _moldura(slide, prs)

    # Capa clara, como o slide-modelo do cliente: o azul fica na faixa lateral e no
    # título, não no fundo inteiro.
    # 34 pt e não 40: "Análises de Falha — setembro de 2026" tem de caber numa linha
    # só, senão a segunda linha desce por cima do risco laranja.
    _caixa_texto(slide, 2.5, 7.6, 27, 1.8, material["titulo"], tamanho=34,
                 negrito=True, cor=AZUL, alinhamento=PP_ALIGN.LEFT)
    risco = slide.shapes.add_shape(1, _cm(2.6), _cm(9.9), _cm(6.0), _cm(0.16))
    risco.fill.solid()
    risco.fill.fore_color.rgb = _rgb(LARANJA)
    risco.line.fill.background()
    risco.shadow.inherit = False
    resumo = (f"{len(material['slides'])} análises no material · "
              f"{len(material['nao_iniciadas'])} abertas sem tratamento · "
              f"{material['total_fotos']} fotos")
    _caixa_texto(slide, 2.6, 10.4, 26, 1.2, resumo, tamanho=16, cor=CINZA)


def _faixa_titulo(slide, prs, cab: dict, concluida: bool) -> None:
    from pptx.enum.text import PP_ALIGN

    faixa = slide.shapes.add_shape(1, 0, 0, _cm(BARRA_X), _cm(2.5))
    faixa.fill.solid()
    faixa.fill.fore_color.rgb = _rgb(AZUL)
    faixa.line.fill.background()
    faixa.shadow.inherit = False

    _caixa_texto(slide, 0.9, 0.25, 17, 1.0,
                 _corta(cab["equipamento"], _chars_por_linha(18, 22, negrito=True)),
                 tamanho=22, negrito=True, cor=BRANCO)
    # O relato para antes da coluna da direita (duração/contexto): com a largura antiga
    # um relato longo passava por cima dela.
    _caixa_texto(slide, 0.95, 1.35, 17.5, 0.8,
                 _corta(cab["relato"], _chars_por_linha(17.5, 12)),
                 tamanho=12, cor=BRANCO)
    _caixa_texto(slide, 18.5, 0.3, 12.0, 0.9, f"{cab['duracao_texto']} de parada",
                 tamanho=16, negrito=True, cor=BRANCO, alinhamento=PP_ALIGN.RIGHT)
    contexto = (f"{cab['n_apontamentos']} apontamentos · {cab['n_ordens']} ordens · "
                f"{'concluída' if concluida else 'em análise'}")
    _caixa_texto(slide, 18.5, 1.4, 12.0, 0.7, contexto, tamanho=10.5, cor=BRANCO,
                 alinhamento=PP_ALIGN.RIGHT)


def _chars_por_linha(largura_cm: float, tamanho_pt: float, negrito: bool = False) -> int:
    """Quantos caracteres cabem numa linha daquela largura, naquele corpo de letra.

    Estimativa deliberadamente conservadora (largura média de caractere ≈ metade do
    corpo). Serve para **cortar o texto antes** de ele estourar a caixa: no PowerPoint
    o texto que não cabe não some — ele vaza por cima do que vem embaixo, que foi
    exatamente o defeito visto nos slides de julho/2026.
    """
    fator = 0.021 * (1.08 if negrito else 1.0)   # negrito ocupa mais largura
    return max(8, int(largura_cm / (fator * tamanho_pt)))


def _quebrar(texto: str, chars: int, max_linhas: int) -> tuple[str, int]:
    """Quebra o texto em no máximo `max_linhas` linhas de `chars` caracteres.

    A quebra é feita aqui, e não deixada para o PowerPoint: só assim o número de linhas
    é **conhecido** na hora de reservar a altura. Estimar e deixar o programa quebrar
    produzia uma linha a mais do que o previsto em palavras longas — e essa linha extra
    caía por cima do texto de baixo.
    """
    linhas = textwrap.wrap((texto or "").strip(), max(6, chars)) or [""]
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        linhas[-1] = linhas[-1][: max(1, chars - 1)].rstrip() + "…"
    return "\n".join(linhas), len(linhas)


def _nome_curto(nome: str, limite: int) -> str:
    """Nome que não cabe vira "Marinho C." — cortar no meio da palavra ("Marinho Cast…")
    deixa a coluna do responsável ilegível na reunião."""
    nome = (nome or "").strip()
    if len(nome) <= limite:
        return nome
    partes = nome.split()
    if len(partes) > 1:
        curto = f"{partes[0]} {partes[-1][0]}."
        if len(curto) <= limite:
            return curto
    return _corta(nome, limite)


def _altura_linha_texto(tamanho_pt: float) -> float:
    """Altura de uma linha de texto, em cm (corpo em pontos × 0,0353 cm/pt, com folga)."""
    return tamanho_pt * 0.0353 * 1.18


def _prazo_curto(prazo: str) -> str:
    """`2026-08-31` vira `31/08/26` — a data por extenso comia a linha do rodapé."""
    p = (prazo or "").strip()
    if len(p) == 10 and p[4] == "-" and p[7] == "-":
        return f"{p[8:]}/{p[5:7]}/{p[2:4]}"
    return p


# Escadinha de tamanhos (causa, descrição, rodapé) em pontos. O bloco tenta o maior
# que faça TODAS as ações caberem inteiras; só desce um degrau quando não couber.
_ESCADA_ACOES = ((9, 8, 7.5), (8.5, 7.5, 7), (8, 7, 6.5), (7.5, 6.5, 6),
                 (7, 6, 6), (6.5, 5.5, 5.5))

# Corpos possíveis para os textos das seções 1, 2 e 5 (o mesmo para as três, para não
# ficar uma seção com letra maior que a vizinha).
TAMANHOS_TEXTO = (9.5, 9, 8.5, 8)


_SEM_CAUSA = object()      # sentinela: ação sem vínculo com balão nenhum


def _texto_meta(a: dict) -> str:
    """Rodapé da ação: quem responde e até quando. Uma ação pode ter mais de um
    responsável — os nomes já chegam prontos numa linha ("João, Thiago")."""
    return " · ".join(p for p in (a["responsavel"], _prazo_curto(a["prazo"])) if p)


def _medir_acoes(acoes: list[dict], largura: float, degrau: int) -> tuple:
    """Itens já quebrados em linhas e a altura total do bloco, num dado degrau da
    escadinha de tamanhos. Não desenha nada — serve para a coluna saber de quanto
    espaço a seção 4 precisa antes de repartir a altura."""
    t_causa, t_desc, t_meta = _ESCADA_ACOES[degrau]
    alt_causa = _altura_linha_texto(t_causa)
    alt_desc = _altura_linha_texto(t_desc)
    alt_meta = _altura_linha_texto(t_meta)
    chars_causa = _chars_por_linha(largura, t_causa, negrito=True)
    chars_desc = _chars_por_linha(largura, t_desc)

    chars_meta = _chars_por_linha(largura - 2.3, t_meta)   # o status ocupa a direita

    itens, total = [], 0.0
    causa_anterior = _SEM_CAUSA
    for a in acoes:
        # Uma causa raiz pode ter várias ações. A causa só é escrita na PRIMEIRA
        # delas — repetir o título em negrito a cada ação comia tanta altura que
        # ações inteiras ficavam de fora ("+N ações não exibidas"). As seguintes
        # entram encostadas, como na tela.
        atual = a.get("node_id") or _SEM_CAUSA
        if atual != causa_anterior:
            causa, n_causa = _quebrar(a["causa"] or "(sem causa vinculada)", chars_causa, 4)
        else:
            causa, n_causa = "", 0
        causa_anterior = atual
        desc, n_desc = (_quebrar(a["descricao"], chars_desc, 8) if a["descricao"]
                        else ("", 0))
        # O rodapé (quem · até quando) pode passar de uma linha quando a ação tem
        # vários responsáveis; medir só uma linha fazia o texto invadir a ação
        # seguinte.
        meta, n_meta = _quebrar(_texto_meta(a), chars_meta, 2)
        altura = n_causa * alt_causa + n_desc * alt_desc + n_meta * alt_meta + 0.16
        itens.append({"causa": causa, "n_causa": n_causa, "desc": desc,
                      "n_desc": n_desc, "meta": meta, "n_meta": n_meta,
                      "altura": altura, "acao": a})
        total += altura
    return itens, total


def _montar_acoes(acoes: list[dict], largura: float, disponivel: float) -> tuple:
    """Escolhe o maior corpo de letra em que **todas** as ações cabem inteiras.

    Devolve `(itens, tamanhos, sobraram)`. Cada item traz o texto já quebrado em
    linhas e a altura que vai ocupar. `sobraram` é quantas ações não couberam nem no
    menor tamanho — normalmente zero.

    Por que existe: antes o bloco tinha corpo fixo e três colunas à direita
    (responsável, prazo, status) que comiam 6,3 dos 11,3 cm de largura. Sobrava tão
    pouco para o texto que as frases eram cortadas com "…" e parte das ações nem
    aparecia. Agora o texto usa a largura inteira e esses três campos viram uma linha
    de rodapé por ação.
    """
    for degrau in range(len(_ESCADA_ACOES)):
        itens, total = _medir_acoes(acoes, largura, degrau)
        if total <= disponivel:
            return itens, _ESCADA_ACOES[degrau], 0

    # Nem no menor tamanho coube tudo: mostra quantas couberem, inteiras.
    cabem, total = [], 0.0
    for item in itens:
        if total + item["altura"] > disponivel - 0.4:
            break
        cabem.append(item)
        total += item["altura"]
    return cabem or itens[:1], _ESCADA_ACOES[-1], len(acoes) - len(cabem or itens[:1])


def _bloco_acoes(slide, x, y, w, h, acoes: list[dict]) -> None:
    """Seção 4 — Plano de Ação. Uma ação por bloco: causa em negrito, a ação embaixo e
    um rodapé com responsável, prazo e status."""
    _painel(slide, x, y, w, h, "4. Plano de Ação")
    if not acoes:
        _caixa_texto(slide, x + 0.3, y + 0.85, w - 0.6, 0.6,
                     "Nenhuma ação registrada.", tamanho=10, cor=CINZA)
        return

    from pptx.enum.text import PP_ALIGN

    lt = w - 0.6
    topo = y + 0.82
    disponivel = h - (topo - y) - 0.18
    itens, (t_causa, t_desc, t_meta), sobraram = _montar_acoes(acoes, lt, disponivel)
    alt_causa = _altura_linha_texto(t_causa)
    alt_desc = _altura_linha_texto(t_desc)
    alt_meta = _altura_linha_texto(t_meta)
    l_status = 2.3                                   # canto direito do rodapé

    linha_y = topo
    for item in itens:
        a = item["acao"]
        alto = 0.0
        # `n_causa == 0` = outra ação da MESMA causa: o título já foi escrito acima.
        if item["n_causa"]:
            _caixa_texto(slide, x + 0.3, linha_y, lt, item["n_causa"] * alt_causa,
                         item["causa"], tamanho=t_causa, negrito=True)
            alto += item["n_causa"] * alt_causa
        if item["n_desc"]:
            _caixa_texto(slide, x + 0.3, linha_y + alto, lt,
                         item["n_desc"] * alt_desc, item["desc"],
                         tamanho=t_desc, cor=CINZA)
            alto += item["n_desc"] * alt_desc
        # Rodapé da ação: quem, até quando e em que pé está. Ocupa a largura menos o
        # canto do status, e pode ir a duas linhas quando há vários responsáveis.
        _caixa_texto(slide, x + 0.3, linha_y + alto, lt - l_status,
                     item["n_meta"] * alt_meta, item["meta"] or "sem responsável",
                     tamanho=t_meta, cor=CINZA)
        _caixa_texto(slide, x + w - 0.3 - l_status, linha_y + alto, l_status, alt_meta,
                     a["status_texto"] or "—", tamanho=t_meta, negrito=True,
                     cor=_CORES_STATUS.get(a["status"], CINZA),
                     alinhamento=PP_ALIGN.RIGHT)
        linha_y += item["altura"]

    if sobraram:
        _caixa_texto(slide, x + 0.3, y + h - 0.48, lt, 0.4,
                     f"+{sobraram} ações não exibidas", tamanho=7.5, cor=CINZA)


def _bloco_fotos(slide, x, y, w, h, fotos: dict) -> None:
    _painel(slide, x, y, w, h, "Registro fotográfico")
    itens = fotos["itens"]
    if not itens:
        _caixa_texto(slide, x + 0.3, y + 0.9, w - 0.6, 0.6,
                     "Sem fotos anexadas nesta análise.", tamanho=10, cor=CINZA)
        return

    largura_celula = (w - 0.6) / len(itens)
    for i, foto in enumerate(itens):
        try:
            slide.shapes.add_picture(foto["caminho"],
                                     _cm(x + 0.3 + i * largura_celula), _cm(y + 0.85),
                                     height=_cm(h - 1.7))
        except Exception as e:                 # imagem corrompida não derruba o material
            print(f"[failure_slides_pptx] foto ignorada ({e})")
            continue
        if foto["legenda"]:
            _caixa_texto(slide, x + 0.3 + i * largura_celula, y + h - 0.75,
                         largura_celula - 0.2, 0.5, _corta(foto["legenda"], 40),
                         tamanho=7.5, cor=CINZA)
    if fotos["ocultas"]:
        _caixa_texto(slide, x + w - 3.4, y + 0.12, 3.0, 0.5,
                     f"+{fotos['ocultas']} fotos", tamanho=8, cor=CINZA)


# Colunas do slide, em cm. A **estreita** (textos do A3) fica à esquerda e a **larga**
# (árvore de causas + fotos) à direita, parando antes da faixa azul da identidade.
COL_X, COL_W = 0.7, 11.2
LARGA_X, LARGA_W = 12.4, 18.15
COL_TOPO, COL_BASE, COL_GAP = 2.9, 18.4, 0.2


def _texto_que_cabe(texto: str, largura_cm: float, tamanho_pt: float,
                    altura_cm: float, limite: int) -> str:
    """Texto quebrado em linhas e cortado no que couber na altura dada.

    Necessário porque as seções cedem altura para o Plano de Ação quando ele precisa:
    sem cortar o texto junto, o parágrafo continuava do mesmo tamanho e transbordava
    por cima da seção de baixo.
    """
    linhas = max(1, int(altura_cm // _altura_linha_texto(tamanho_pt)))
    quebrado, _n = _quebrar(_corta(texto, limite), _chars_por_linha(largura_cm, tamanho_pt),
                            linhas)
    return quebrado


def _altura_texto(texto: str, largura_cm: float, tamanho_pt: float,
                  limite: int) -> float:
    """Altura (cm) que um texto ocupa depois de cortado no limite da caixa.

    Conta as linhas de verdade (quebra por palavra), e não `caracteres ÷ largura`: a
    conta por caracteres dava sempre uma linha a menos, porque nenhuma linha real
    termina exatamente na borda — e essa linha a mais aparecia cortada com "…".
    """
    linhas = textwrap.wrap(_corta(texto or "", limite),
                           max(6, _chars_por_linha(largura_cm, tamanho_pt))) or [""]
    return len(linhas) * _altura_linha_texto(tamanho_pt)


def _coluna_texto(slide, dados: dict) -> None:
    """Problema, Contenção, Plano de Ação e Lições/Encerramento, um sob o outro.

    As alturas são calculadas a partir do texto de cada análise, e não fixas. Com
    alturas fixas o Problema reservava 5,4 cm mesmo para três linhas enquanto o Plano
    de Ação, espremido em 3,6 cm, sobrepunha as próprias linhas e invadia a seção de
    baixo (defeito visto no material de julho/2026). Sobra sempre vai para o Plano de
    Ação, que é o que a reunião discute.
    """
    lt = COL_W - 0.6                                    # largura útil do texto
    prob, cont = dados["problema"], dados["contencao"]
    fecho = dados["encerramento"]

    total = COL_BASE - COL_TOPO - 3 * COL_GAP

    # Escolhe o par (corpo dos textos, degrau da seção 4) de maior qualidade em que
    # TUDO cabe inteiro. Reduzir meio ponto na letra é sempre melhor do que cortar
    # frase: as ações são o compromisso que sai da reunião e os textos são o laudo.
    melhor = None
    for t_txt in TAMANHOS_TEXTO:
        h_prob = (0.78 + _altura_texto(prob["descricao"] or "—", lt, t_txt, LIM_PROBLEMA)
                  + 0.25 + (0.5 if prob["area"] else 0.0))
        h_cont = 0.78 + _altura_texto(cont["acoes"] or "—", lt, t_txt, LIM_CONTENCAO) + 0.25
        h_lic = 0.78 + _altura_texto(dados["licoes"] or "—", lt, t_txt, LIM_LICOES) + 0.75
        h_prob, h_cont = min(h_prob, 8.0), min(h_cont, 5.0)
        h_lic = min(h_lic, 5.0)
        for degrau in range(len(_ESCADA_ACOES)):
            if dados["acoes"]:
                _itens, alt = _medir_acoes(dados["acoes"], lt, degrau)
                h_acoes = max(3.2, 1.0 + alt)
            else:
                h_acoes = 3.2
            if h_prob + h_cont + h_lic + h_acoes <= total:
                qualidade = t_txt * 2 + _ESCADA_ACOES[degrau][0]
                if melhor is None or qualidade > melhor[0]:
                    melhor = (qualidade, t_txt, h_prob, h_cont, h_lic, h_acoes)
                break
            if not dados["acoes"]:
                break

    if melhor:
        _q, t_txt, h_prob, h_cont, h_lic, h_acoes = melhor
    else:
        # Nem no menor par coube: usa o menor corpo e aperta os textos até o mínimo —
        # aí sim o texto é cortado, com "…" (caso extremo, fora da medição do cliente).
        t_txt = TAMANHOS_TEXTO[-1]
        h_prob, h_cont, h_lic = 2.3, 1.7, 2.0
        h_acoes = total - (h_prob + h_cont + h_lic)

    # A sobra vai para o Problema (é o texto mais longo na medição do cliente).
    sobra = total - (h_prob + h_cont + h_lic + h_acoes)
    if sobra > 0:
        h_prob += sobra

    y = COL_TOPO
    _painel(slide, COL_X, y, COL_W, h_prob, "1. Problema")
    alt_corpo = h_prob - (1.45 if prob["area"] else 0.95)
    _caixa_texto(slide, COL_X + 0.3, y + 0.72, lt, alt_corpo,
                 _texto_que_cabe(prob["descricao"] or "—", lt, t_txt, alt_corpo,
                                 LIM_PROBLEMA), tamanho=t_txt)
    if prob["area"]:
        _caixa_texto(slide, COL_X + 0.3, y + h_prob - 0.62, lt, 0.5,
                     f"Área: {prob['area']}", tamanho=8, cor=CINZA)

    y += h_prob + COL_GAP
    _painel(slide, COL_X, y, COL_W, h_cont, "2. Contenção")
    _caixa_texto(slide, COL_X + 0.3, y + 0.72, lt, h_cont - 0.9,
                 _texto_que_cabe(cont["acoes"] or "—", lt, t_txt, h_cont - 0.9,
                                 LIM_CONTENCAO), tamanho=t_txt)

    y += h_cont + COL_GAP
    _bloco_acoes(slide, COL_X, y, COL_W, h_acoes, dados["acoes"])

    y += h_acoes + COL_GAP
    _painel(slide, COL_X, y, COL_W, h_lic, "5. Lições aprendidas · 6. Encerramento")
    _caixa_texto(slide, COL_X + 0.3, y + 0.72, lt, h_lic - 1.35,
                 _texto_que_cabe(dados["licoes"] or "—", lt, t_txt, h_lic - 1.35,
                                 LIM_LICOES), tamanho=t_txt)
    assinatura = fecho["responsavel"] or dados["cabecalho"]["responsavel"] or "—"
    _caixa_texto(slide, COL_X + 0.3, y + h_lic - 0.62, lt, 0.5,
                 f"Assinatura: {assinatura}    Data: {fecho['data'] or '—'}",
                 tamanho=8.5, cor=CINZA)


def _imagem_ajustada(slide, png: bytes, x, y, w, h):
    """Encaixa a imagem no espaço (x, y, w, h) usando o máximo dele, sem distorcer.

    Antes a árvore era colada com a largura fixa do painel; uma árvore baixa e larga
    ficava como uma tira no topo, com metade do maior painel do slide em branco. Aqui
    ela cresce até esbarrar no lado que limitar, e fica centralizada no que sobrar.
    """
    from PIL import Image

    with Image.open(io.BytesIO(png)) as im:
        pw, ph = im.size
    if not pw or not ph:
        return None
    if pw / ph >= w / h:                    # limita pela largura
        larg, alt = w, w * ph / pw
    else:                                   # limita pela altura
        alt, larg = h, h * pw / ph
    return slide.shapes.add_picture(io.BytesIO(png), _cm(x + (w - larg) / 2),
                                    _cm(y + (h - alt) / 2), width=_cm(larg), height=_cm(alt))


# Extensão do PowerPoint 2016+ para imagem vetorial: o `a:blip` aponta para o PNG (quem
# não lê SVG mostra ele) e carrega, dentro, a referência ao SVG. É exatamente o que o
# próprio PowerPoint grava ao inserir um SVG.
_NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_SVG = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
_URI_SVG = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"


def _anexar_svg(slide, picture, svg: bytes) -> None:
    """Pendura o SVG na imagem já colada: zoom no slide sem serrilhar (IM-AF3-08).

    Em linguagem simples: a figura do slide continua sendo o PNG, mas o PowerPoint novo
    desenha a versão vetorial guardada junto. PowerPoint antigo, Google Slides e
    LibreOffice mostram o PNG.
    """
    from lxml import etree
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    from pptx.opc.package import Part

    pacote = slide.part.package
    parte = Part(pacote.next_partname("/ppt/media/diagrama%d.svg"), "image/svg+xml",
                 pacote, svg)
    rid = slide.part.relate_to(parte, RT.IMAGE)
    blip = picture._element.find(f".//{{{_NS_A}}}blip")
    ext_lst = blip.find(f"{{{_NS_A}}}extLst")
    if ext_lst is None:
        ext_lst = etree.SubElement(blip, f"{{{_NS_A}}}extLst")
    ext = etree.SubElement(ext_lst, f"{{{_NS_A}}}ext", uri=_URI_SVG)
    svg_blip = etree.SubElement(ext, f"{{{_NS_SVG}}}svgBlip", nsmap={"asvg": _NS_SVG})
    svg_blip.set(f"{{{_NS_R}}}embed", rid)


def _arvore_no_painel(slide, dados: dict, x, y, w, h) -> None:
    """Painel 3: o desenho do próprio quadro, se houver imagem válida guardada
    (SVG + PNG de reserva); senão, a árvore redesenhada pelo servidor."""
    img = dados.get("diagrama")
    if img:
        try:
            pic = _imagem_ajustada(slide, img["png"], x, y, w, h)
            if pic is not None:
                _anexar_svg(slide, pic, img["svg"])
                return
        except Exception as e:                  # imagem ruim não derruba o material
            print(f"[failure_slides_pptx] imagem do quadro recusada ({e}); usando o redesenho")
    png = desenhar_arvore(dados["arvore"], largura=1800, altura=900,
                          proporcao_alvo=w / h)   # o painel onde ela é colada
    if png:
        try:
            _imagem_ajustada(slide, png, x, y, w, h)
        except Exception as e:
            print(f"[failure_slides_pptx] árvore não desenhada ({e})")


def _slide_analise(prs, dados: dict) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _moldura(slide, prs)
    _faixa_titulo(slide, prs, dados["cabecalho"], dados["concluida"])

    # --- coluna larga (direita): árvore de causas + fotos
    _painel(slide, LARGA_X, 2.9, LARGA_W, 10.2, "3. Árvore de causas  (★ = causa raiz)")
    _arvore_no_painel(slide, dados, LARGA_X + 0.3, 3.7, LARGA_W - 0.6, 8.9)
    # O painel de fotos para antes do arco laranja da identidade (canto inferior
    # direito) — a árvore, que fica acima dele, mantém a largura inteira.
    _bloco_fotos(slide, LARGA_X, 13.4, ARCO_X - LARGA_X, 5.0, dados["fotos"])

    # --- coluna estreita (esquerda): os textos do A3
    _coluna_texto(slide, dados)

    _caixa_texto(slide, LARGA_X, 18.35, LARGA_W, 0.5,
                 f"Análise de Falhas · {dados['chave']}", tamanho=7.5, cor=CINZA)


def _slide_nao_iniciadas(prs, pendentes: list[dict]) -> None:
    """Uma tabela com as análises abertas que ninguém trabalhou — em vez de N slides
    em branco (decisão de 2026-08-05)."""
    from pptx.util import Pt

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _moldura(slide, prs)
    faixa = slide.shapes.add_shape(1, 0, 0, _cm(BARRA_X), _cm(2.5))
    faixa.fill.solid()
    faixa.fill.fore_color.rgb = _rgb(AZUL)
    faixa.line.fill.background()
    faixa.shadow.inherit = False
    _caixa_texto(slide, 0.9, 0.55, 25, 1.2,
                 f"Paradas com análise aberta e sem tratamento — {len(pendentes)}",
                 tamanho=22, negrito=True, cor=BRANCO)

    largura_tab = MARGEM_DIREITA - 0.9
    tabela = slide.shapes.add_table(len(pendentes) + 1, 3, _cm(0.9), _cm(3.2),
                                    _cm(largura_tab),
                                    _cm(1.0 + 0.85 * len(pendentes))).table
    tabela.columns[0].width = _cm(5.6)
    tabela.columns[1].width = _cm(largura_tab - 10.4)
    tabela.columns[2].width = _cm(4.8)
    for i, titulo in enumerate(("Equipamento", "Relato da parada", "Duração")):
        celula = tabela.cell(0, i)
        celula.text = titulo
        for p in celula.text_frame.paragraphs:
            for run in p.runs:
                run.font.size = Pt(11)
                run.font.bold = True
    for linha, item in enumerate(pendentes, start=1):
        for coluna, valor in enumerate((item["equipamento"],
                                        _corta(item["relato"], 90),
                                        item["duracao_texto"])):
            celula = tabela.cell(linha, coluna)
            celula.text = valor or "—"
            for p in celula.text_frame.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(10)


def _arco_png(lado_px: int = 900) -> bytes:
    """Quarto de anel laranja com fundo transparente — o elemento do canto inferior
    direito da identidade do cliente.

    Redesenhado aqui (Pillow) em vez de embutir o arquivo do cliente: são duas linhas
    de geometria (raio externo e interno vindos do SVG original) e o material fica sem
    depender de um binário guardado no repositório.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (lado_px, lado_px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Centro no canto INFERIOR DIREITO; o anel ocupa o quadrante de cima à esquerda.
    r_ext, r_int = lado_px, lado_px * ARCO_RAIO_INTERNO
    d.pieslice([lado_px - r_ext, lado_px - r_ext, lado_px + r_ext, lado_px + r_ext],
               180, 270, fill=LARANJA + (255,))
    d.pieslice([lado_px - r_int, lado_px - r_int, lado_px + r_int, lado_px + r_int],
               180, 270, fill=(0, 0, 0, 0))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _moldura(slide, prs) -> None:
    """Aplica a identidade visual do cliente ao slide: faixa vertical azul na borda
    direita e o quarto de anel laranja no canto inferior direito.

    Vem do slide-modelo que o cliente mandou; todo slide do material recebe a mesma
    moldura, para o arquivo passar por material dele e não por saída de sistema.
    """
    from pptx.enum.shapes import MSO_SHAPE

    faixa = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, _cm(BARRA_X), 0,
                                   _cm(BARRA_W), prs.slide_height)
    faixa.fill.solid()
    faixa.fill.fore_color.rgb = _rgb(AZUL)
    faixa.line.fill.background()
    faixa.shadow.inherit = False

    y = prs.slide_height - _cm(ARCO_LADO)
    x = prs.slide_width - _cm(ARCO_LADO)
    slide.shapes.add_picture(io.BytesIO(_arco_png()), x, y,
                             width=_cm(ARCO_LADO), height=_cm(ARCO_LADO))


def _apresentacao():
    """Apresentação vazia no formato 16:9 (a mesma para o mês inteiro e para uma só)."""
    from pptx import Presentation

    prs = Presentation()
    prs.slide_width = _cm(33.87)      # 16:9
    prs.slide_height = _cm(19.05)
    return prs


def gerar_pptx(material: dict) -> bytes:
    """Material do mês → bytes do `.pptx`.

    `material` é a saída de `failure_slides.montar_mes`. Mês sem nenhuma análise gera
    só a capa — o arquivo existe e diz que o mês está vazio, em vez de falhar.
    """
    prs = _apresentacao()

    _capa(prs, material)
    for dados in material["slides"]:
        _slide_analise(prs, dados)
    if material["nao_iniciadas"]:
        _slide_nao_iniciadas(prs, material["nao_iniciadas"])

    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue()


def nome_arquivo(material: dict) -> str:
    """`analises-falha-2026-07.pptx` — previsível, ordena sozinho na pasta."""
    return f"analises-falha-{material['ano']:04d}-{material['mes']:02d}.pptx"


def gerar_mes(ano: int, mes: int) -> tuple[bytes, str]:
    """Atalho de aplicação: busca no banco, monta e devolve (bytes, nome do arquivo)."""
    from src.utils.failure_slides import montar_mes_do_banco

    material = montar_mes_do_banco(ano, mes)
    return gerar_pptx(material), nome_arquivo(material)


def nome_arquivo_analise(dados: dict) -> str:
    """`analise-falha-LONGI002-2026-06.pptx` — o equipamento e o mês da própria parada.

    A chave da parada é `<equipamento>_<AAAAMM>_<causa>_<hash do relato>`; daí saem as
    duas partes que importam para quem procura o arquivo depois. Chave fora do padrão
    (formato antigo, 3 partes) cai num nome genérico em vez de quebrar o download.
    """
    partes = (dados.get("chave") or "").split("_")
    equipamento = partes[0] if partes and partes[0] else "analise"
    mes_ref = partes[1] if len(partes) > 1 and partes[1].isdigit() and len(partes[1]) == 6 else ""
    sufixo = f"-{mes_ref[:4]}-{mes_ref[4:]}" if mes_ref else ""
    return f"analise-falha-{equipamento}{sufixo}.pptx"


def gerar_analise(analise: dict) -> tuple[bytes, str]:
    """Uma análise → `.pptx` de **um slide só** (S5), sem capa nem lista do fim.

    Serve ao botão "Exportar esta análise" da página do A3: quem quer levar uma análise
    isolada para uma reunião não precisa do material do mês inteiro. O slide é
    exatamente o mesmo do material mensal — mesma função de desenho, mesmo layout.
    """
    from src.utils.failure_slides import montar_slide

    dados = montar_slide(analise)
    prs = _apresentacao()
    _slide_analise(prs, dados)

    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue(), nome_arquivo_analise(dados)
