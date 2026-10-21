# src/utils/failure_tree_image.py

"""
Desenho da árvore de causas em PNG, feito no servidor (S3 da proposta
`analise-falhas-v2/PROPOSTA-slide-mensal.md`).

O diagrama que aparece na tela é desenhado pelo navegador (cytoscape) e **não existe**
no servidor. Para o material mensal sair sozinho, sem ninguém abrir cada análise, aqui
a árvore é redesenhada do zero a partir dos balões — cada um sabe o seu pai, o seu tipo
e o tempo que carrega.

Quando o S2 entrar (imagem capturada da tela ao salvar), este módulo continua sendo a
rede de segurança: análise sem imagem guardada cai aqui.

Medições do recorte real do cliente (2026-08-05) que guiaram o layout: até 11 balões,
até 7 níveis de profundidade, título de balão chegando a 119 caracteres. Ou seja, a
árvore desce fundo com poucos irmãos — o desenho comprime a largura por nível em vez de
espalhar.
"""

from __future__ import annotations

import io
import textwrap
from typing import Optional

# Paleta do relatório semanal / indicadores (mesma identidade visual).
AZUL = (0, 80, 144)
AZUL_CLARO = (232, 240, 247)
LARANJA = (233, 109, 56)
CINZA = (107, 114, 128)
CINZA_CLARO = (209, 213, 219)
VERMELHO = (192, 57, 43)
BRANCO = (255, 255, 255)
PRETO = (17, 24, 39)

# Uma cor por nível de profundidade, na ligação que ENTRA no balão. Ajuda a ler de
# relance até onde cada ramo desce: tudo que chega por uma linha laranja está no mesmo
# nível. Cicla se a árvore for mais funda que a paleta (o recorte do cliente vai a 7).
CORES_NIVEL = (
    (0, 80, 144),      # 1 — azul da identidade
    (233, 109, 56),    # 2 — laranja da identidade
    (46, 125, 50),     # 3 — verde
    (109, 76, 158),    # 4 — roxo
    (0, 131, 143),     # 5 — azul-petróleo
    (166, 78, 46),     # 6 — terracota
)

# Colunas por faixa. Acima disso a árvore quebra para uma faixa abaixo: o painel do
# slide é largo, mas não *tão* largo — 4 balões por fileira é o limite em que o texto
# ainda se lê depois da redução.
MAX_COLUNAS = 3

_FONTES = (
    "/usr/share/fonts/truetype/liberation/LiberationSans-{}.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans{}.ttf",
)


def _fonte(tamanho: int, negrito: bool = False):
    from PIL import ImageFont

    for molde in _FONTES:
        for sufixo in ((("Bold", "-Bold") if negrito else ("Regular", ""))):
            try:
                return ImageFont.truetype(molde.format(sufixo), tamanho)
            except OSError:
                continue
    return ImageFont.load_default()


def _linhas(texto: str, largura_chars: int, maximo: int) -> list[str]:
    linhas = textwrap.wrap(texto or "", largura_chars) or [""]
    if len(linhas) > maximo:
        linhas = linhas[:maximo]
        linhas[-1] = linhas[-1][: max(0, largura_chars - 1)] + "…"
    return linhas


def _estrela(d, cx: float, cy: float, raio: float, cor) -> None:
    """Estrela de 5 pontas — o marcador de causa raiz."""
    import math

    pontos = []
    for i in range(10):
        r = raio if i % 2 == 0 else raio * 0.42
        ang = -math.pi / 2 + i * math.pi / 5
        pontos.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.polygon(pontos, fill=cor)


def desenhar(arvore: list[dict], largura: int = 1600, altura: int = 900,
             escala: int = 2, proporcao_alvo: float = 2.1) -> Optional[bytes]:
    """Devolve o PNG da árvore, ou `None` se não houver o que desenhar.

    `arvore` é a saída de `failure_slides.arvore_em_niveis` — cada item traz `nivel`,
    `titulo`, `duration_min`, `causa_raiz` e `n_filhos`. Desenha da esquerda (a parada)
    para a direita (as causas), ligando pai e filho por um cotovelo, com o ★ da causa
    raiz em vermelho e o tempo de cada etapa em laranja.

    `escala` desenha em resolução maior e reduz no fim (bordas e texto sem serrilhado).
    """
    if not arvore:
        return None
    from PIL import Image, ImageDraw

    L, A = largura * escala, altura * escala
    img = Image.new("RGB", (L, A), BRANCO)
    d = ImageDraw.Draw(img)

    margem = 16 * escala
    niveis = max(n["nivel"] for n in arvore) + 1

    # Quantas colunas por faixa. Uma cadeia de 6 ou 7 níveis desenhada numa fileira só
    # vira uma tirinha: no slide ela é reduzida pela largura, sobra metade do painel em
    # branco e o texto do balão fica ilegível. Acima de MAX_COLUNAS a árvore "serpenteia"
    # — segue em uma nova faixa abaixo, como um texto que quebra de linha.
    faixas = max(1, -(-niveis // MAX_COLUNAS))          # ceil
    colunas = max(1, -(-niveis // faixas))              # equilibra as faixas
    banda_de = {n["id"]: n["nivel"] // colunas for n in arvore}
    coluna_de = {n["id"]: n["nivel"] % colunas for n in arvore}

    largura_nivel = (L - 2 * margem) / colunas
    caixa_l = max(90 * escala, largura_nivel - 26 * escala)
    altura_faixa = (A - 2 * margem) / faixas
    # Passo vertical COMPACTO: a faixa ocupa só o que os seus balões pedem. Espalhar os
    # balões por toda a altura da faixa deixava um vão branco entre as faixas que o
    # recorte final não tira (ele só apara as bordas) — e a árvore chegava ao slide
    # como uma tira fina.
    # A caixa acompanha a própria largura (≈1/3 dela). Com altura fixa e pequena, o
    # balão ficava 6× mais largo que alto: o conjunto virava uma tira e, reduzido para
    # caber na largura do painel, o texto sumia.
    # `proporcao_alvo` é o formato do espaço onde a imagem vai ser colada (largura ÷
    # altura do painel do slide). O balão cresce em altura até o conjunto chegar perto
    # dessa proporção — assim a árvore preenche o painel em vez de virar uma tira no
    # topo, e o texto sobrevive à redução. O teto de 0,62 da largura evita o balão
    # quadrado quando há poucas faixas.
    folga = 22 * escala
    alvo_conteudo = (L / max(0.5, proporcao_alvo)) / faixas
    caixa_a_alvo = max(40 * escala, min(alvo_conteudo - folga, caixa_l * 0.62,
                                        altura_faixa * 0.9))
    passo_alvo = caixa_a_alvo + folga

    # Centro vertical: dentro de cada faixa, as folhas *daquela faixa* dividem a altura
    # da faixa; o pai fica no meio dos filhos que estão na mesma faixa (quem quebra para
    # a faixa de baixo não puxa o pai).
    centro: dict[str, float] = {}
    topo_acumulado = 0.0
    passos: list[float] = []
    limites: dict[int, tuple[float, float]] = {}    # faixa → (topo, fim)
    for b in range(faixas):
        na_faixa = [n for n in arvore if banda_de[n["id"]] == b]
        if not na_faixa:
            continue
        folhas = [n for n in na_faixa
                  if not any(c["parent_id"] == n["id"] and banda_de[c["id"]] == b
                             for c in arvore)] or na_faixa
        passo_y = min(altura_faixa / max(1, len(folhas)), passo_alvo)
        passos.append(passo_y)
        topo = margem + topo_acumulado
        limites[b] = (topo, topo + passo_y * len(folhas))
        topo_acumulado += passo_y * len(folhas) + (18 * escala if b + 1 < faixas else 0)
        for i, n in enumerate(folhas):
            centro[n["id"]] = topo + passo_y * (i + 0.5)
        for n in reversed(na_faixa):
            filhos = [c for c in na_faixa if c["parent_id"] == n["id"]]
            if filhos:
                centro[n["id"]] = sum(centro[c["id"]] for c in filhos) / len(filhos)
    # A caixa nunca pode passar do passo vertical da faixa mais cheia — senão os balões
    # se encostam (ou se cruzam) quando um nível tem muitos irmãos.
    caixa_a = min(caixa_a_alvo, max(30 * escala, min(passos) - 14 * escala))

    x_de = {n["id"]: margem + coluna_de[n["id"]] * largura_nivel for n in arvore}

    # Ligações primeiro, para ficarem atrás das caixas.
    for n in arvore:
        for c in [x for x in arvore if x["parent_id"] == n["id"]]:
            y0, y1 = centro[n["id"]], centro[c["id"]]
            if banda_de[c["id"]] == banda_de[n["id"]]:
                x0 = x_de[n["id"]] + caixa_l
                x1 = x_de[c["id"]]
                meio = (x0 + x1) / 2
                pontos = [(x0, y0), (meio, y0), (meio, y1), (x1, y1)]
            else:
                # Quebra de faixa: sai pela direita do pai, desce até a CALHA entre as
                # duas faixas, atravessa por lá e sobe/desce até o filho. Passar pela
                # calha (e não pela média das alturas) evita cruzar os balões de baixo.
                x0 = x_de[n["id"]] + caixa_l
                x1 = x_de[c["id"]]
                fim_pai = limites[banda_de[n["id"]]][1]
                topo_filho = limites[banda_de[c["id"]]][0]
                calha = (fim_pai + topo_filho) / 2
                borda = min(L - margem / 2, x0 + 12 * escala)
                entrada = max(margem / 2, x1 - 12 * escala)
                pontos = [(x0, y0), (borda, y0), (borda, calha),
                          (entrada, calha), (entrada, y1), (x1, y1)]
            # Cor pelo nível de quem recebe a ligação; traço mais grosso porque a
            # imagem ainda vai ser reduzida para caber no slide — no fio antigo (2 px)
            # a ligação praticamente sumia.
            cor_nivel = CORES_NIVEL[(c["nivel"] - 1) % len(CORES_NIVEL)]
            d.line(pontos, fill=cor_nivel, width=max(2, int(2.8 * escala)),
                   joint="curve")

    # Fonte proporcional à caixa: o balão é reduzido no slide junto com a imagem, então
    # o que importa é a razão texto/caixa, não o tamanho absoluto em pixels.
    corpo = max(11, int(caixa_l / (26 * escala)) * escala)
    f_titulo = _fonte(int(corpo * 1.05), negrito=True)
    f_causa = _fonte(corpo)
    f_tempo = _fonte(int(corpo * 0.85), negrito=True)
    linha_alt = corpo * 1.25
    chars = max(12, int(caixa_l / (corpo * 0.56)))
    max_linhas = max(1, int((caixa_a - 12 * escala) / linha_alt))

    for n in arvore:
        x, y = x_de[n["id"]], centro[n["id"]] - caixa_a / 2
        raiz_causa = n["causa_raiz"]
        borda = VERMELHO if raiz_causa else (AZUL if n["tipo"] in ("ROOT", "STEP") else CINZA)
        fundo = AZUL_CLARO if n["tipo"] == "ROOT" else BRANCO
        d.rounded_rectangle([x, y, x + caixa_l, y + caixa_a], radius=5 * escala,
                            fill=fundo, outline=borda,
                            width=max(1, (3 if raiz_causa else 2) * escala // 2))
        # A estrela da causa raiz é DESENHADA, não escrita: a fonte do container
        # (Liberation Sans) não tem o glifo "★" e ele sairia como quadrado vazio.
        recuo = 7 * escala
        if raiz_causa:
            _estrela(d, x + 12 * escala,
                     y + max(12 * escala, caixa_a / 2 - linha_alt * 0.15),
                     corpo * 0.55, VERMELHO)
            recuo = corpo * 1.7
        rotulo = n["titulo"] or "(sem título)"
        fonte = f_titulo if n["tipo"] in ("ROOT", "STEP") else f_causa
        chars_no = chars - (3 if raiz_causa else 0)
        texto_linhas = _linhas(rotulo, chars_no, max_linhas)
        # Com o texto centralizado na vertical, recuar só a primeira linha deixava a
        # estrela por cima das demais — o bloco inteiro anda para a direita.
        # Texto centralizado na vertical: encostado no topo, o balão alto ficava com um
        # vazio embaixo e parecia recorte mal feito.
        y_texto = y + max(6 * escala, (caixa_a - len(texto_linhas) * linha_alt) / 2)
        for i, linha in enumerate(texto_linhas):
            d.text((x + recuo, y_texto + i * linha_alt), linha, font=fonte, fill=PRETO)
        if n.get("duration_min"):
            texto = f"{int(n['duration_min'])} min"
            largura_texto = d.textlength(texto, font=f_tempo)
            d.text((x + caixa_l - 7 * escala - largura_texto,
                    y + caixa_a - linha_alt - 2 * escala),
                   texto, font=f_tempo, fill=LARANJA)

    # Árvore estreita (poucos irmãos) deixa faixas brancas enormes em cima e embaixo —
    # recorta o que foi realmente desenhado antes de reduzir, para a imagem chegar ao
    # slide já preenchendo o espaço.
    usado = img.getbbox() if img.mode != "RGB" else _bbox_conteudo(img)
    if usado:
        folga = 10 * escala
        img = img.crop((max(0, usado[0] - folga), max(0, usado[1] - folga),
                        min(L, usado[2] + folga), min(A, usado[3] + folga)))

    img.thumbnail((largura, altura), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _bbox_conteudo(img):
    """Área realmente desenhada (tudo que não é branco)."""
    from PIL import ImageChops, Image

    fundo = Image.new("RGB", img.size, BRANCO)
    return ImageChops.difference(img, fundo).getbbox()
