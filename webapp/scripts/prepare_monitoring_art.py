#!/usr/bin/env python3
"""Prepara a arte SVG do Monitoramento de Ativos (DS-03 do SDD MonAtivo-Prototipo).

Lê ``components/monitoring/art/fonte/`` e escreve ``components/monitoring/art/preparado/``.

Roda fora do runtime, na mão, quando a arte de origem muda:

    python webapp/scripts/prepare_monitoring_art.py

As cinco transformações (DS-03):

T1 — materializa os clones que o mockup criava em JavaScript (``lineB`` e ``lineLCL2``);
T2 — envolve as máquinas da LWB num grupo de linha (``lineLWB``);
T3 — grava ``data-ativo`` em cada grupo de linha;
T4 — normaliza os nomes e gera a chave do conjunto em ``data-conj``;
T5 — fixa os rótulos dos ativos como elementos do desenho.

Além disso materializa o que o mockup também montava em JavaScript e não é
transformação de máquina: os pátios de bobina, as grades de material e as molduras
de ativo. O SVG preparado não depende de nenhum script para ficar completo.

Saídas em ``art/preparado/``:

    planta.svg          composição completa (planta baixa + as três linhas)
    linha_prensa.svg    LCP01, LCP02, LCT2,5   (usado pela página do ativo)
    linhas_corte.svg    LCT16, LCT08, LCL4,5, LCL08
    linha_lwb.svg       LWB
    inventario.json     ativos, conjuntos e chaves geradas
"""

from __future__ import annotations

import copy
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
S = "{%s}" % SVG_NS

RAIZ = Path(__file__).resolve().parents[1] / "src" / "components" / "monitoring" / "art"
FONTE = RAIZ / "fonte"
PREPARADO = RAIZ / "preparado"


# --------------------------------------------------------------------------- #
# T1 — clones a materializar
# --------------------------------------------------------------------------- #

# (arquivo, id de origem, id do clone, transform, sufixo aplicado aos ids internos)
CLONES = [
    ("linha_prensa.svg", "lineA", "lineB", "translate(421,0) scale(-1,1)", "_b"),
    ("linhas_corte.svg", "lineLCL", "lineLCL2", "translate(1490,0)", "_2"),
]

# --------------------------------------------------------------------------- #
# T3 — identidade do ativo por grupo de linha
# --------------------------------------------------------------------------- #

# ATENÇÃO: a atribuição do par lineA/lineB é posicional e segue o que o mockup
# renderiza — no `page4.html` o rótulo LCP02 cai sobre o clone `lineB` (mais à
# esquerda) e LCP01 sobre `lineA`. Trocar os dois é um erro que não gera exceção
# nenhuma: só mostra a máquina errada. Confirmar na passada visual do IM-20.
ATIVO_POR_GRUPO = {
    "lineB": "LCP02",
    "lineA": "LCP01",
    "lineC": "LCT2,5",
    "lineLCT": "LCT16",
    "lineLCT2": "LCT08",
    "lineLCL": "LCL4,5",
    "lineLCL2": "LCL08",
    "lineLWB": "LWB",
}

# Máquinas desenhadas fora do grupo da própria linha. O carro de bobinas da
# LCT2,5 (`nc`) fica solto no desenho porque o grupo `lineC` carrega uma rotação
# que não se aplica a ele — mover para dentro do grupo mudaria a posição. Em vez
# de mover, a identidade do ativo é declarada aqui.
MAQUINAS_AVULSAS = {
    "nc": "LCT2,5",
}

# Ordem de apresentação dos ativos no inventário.
ORDEM_ATIVOS = ["LCP01", "LCP02", "LCT2,5", "LCT16", "LCT08", "LCL4,5", "LCL08", "LWB"]

# --------------------------------------------------------------------------- #
# T2 — a LWB não tem grupo de linha no desenho de origem
# --------------------------------------------------------------------------- #

LWB_MAQUINAS = [f"w{i}" for i in range(1, 13)]
LWB_GRUPO = "lineLWB"

# --------------------------------------------------------------------------- #
# T4 — correções de grafia (aplicadas depois da normalização)
# --------------------------------------------------------------------------- #

CORRECOES_GRAFIA = {
    "APLAINADORA": "APLANADORA",
}

# --------------------------------------------------------------------------- #
# T5 e materialização do que era JavaScript — coordenadas no espaço do `root`
# --------------------------------------------------------------------------- #

# Rótulo de cada ativo: (texto, x, y). Medidos uma única vez sobre o mockup
# renderizado; a partir daqui são constantes do desenho.
ROTULOS_ATIVO = [
    ("LCP02", 542.06, 394.39),
    ("LCP01", 694.15, 394.39),
    ("LCT2,5", 854.35, 394.39),
    ("LCT16", 1313.89, 499.93),
    ("LCT08", 1442.42, 499.93),
    ("LCL4,5", 1572.20, 499.93),
    ("LCL08", 1702.59, 499.93),
    ("LWB", 108.65, 593.28),
]

# O espaço de coordenadas da planta inteira, como declarado no desenho de base.
VIEW_BOX_PLANTA = (0, 0, 1789, 1068)

# Moldura de cada ativo: caixa envolvente da linha, com folga. Recebe a cor pela
# folha de estilo gerada em tempo de render (DS-06) — aqui nasce sem cor.
MARGEM_MOLDURA = 10.0
CAIXAS_ATIVO = {
    "LCP02": (488.55, 416.39, 595.57, 668.24),
    "LCP01": (640.64, 416.39, 747.66, 668.24),
    "LCT2,5": (821.88, 418.37, 886.82, 639.78),
    "LCT16": (1289.05, 521.93, 1338.73, 753.54),
    "LCT08": (1417.28, 521.93, 1467.57, 743.61),
    "LCL4,5": (1541.46, 521.93, 1602.93, 705.11),
    "LCL08": (1671.86, 521.93, 1733.33, 705.11),
    "LWB": (20.48, 615.28, 196.81, 985.20),
}

# Recorte do croqui de cada ativo (DS-07): a faixa do desenho de origem que mostra
# aquele ativo sozinho, em coordenadas do próprio arquivo. Medida uma vez sobre o
# desenho preparado; a calibração fina é tarefa da passada visual do IM-20.
MARGEM_RECORTE = 24.0
RECORTES = {
    "LCP01": (318.0, -72.0, 323.0, 584.0),
    "LCP02": (-141.0, -72.0, 323.0, 584.0),
    "LCT2,5": (707.0, -72.0, 354.0, 518.0),
    "LCT16": (158.0, -92.0, 160.0, 746.0),
    "LCT08": (571.0, -92.0, 162.0, 714.0),
    "LCL4,5": (971.0, -92.0, 198.0, 590.0),
    "LCL08": (1391.0, -92.0, 198.0, 590.0),
    "LWB": (207.0, -73.0, 256.0, 548.0),
}

# Em que desenho cada ativo vive — é dele que sai o croqui da página do ativo.
DESENHO_DO_ATIVO = {
    "LCP01": "linha_prensa.svg",
    "LCP02": "linha_prensa.svg",
    "LCT2,5": "linha_prensa.svg",
    "LCT16": "linhas_corte.svg",
    "LCT08": "linhas_corte.svg",
    "LCL4,5": "linhas_corte.svg",
    "LCL08": "linhas_corte.svg",
    "LWB": "linha_lwb.svg",
}

# Pátios de bobina (R2): quatro grades idênticas, geometria do mockup.
PATIOS_CX = [626, 956, 1286, 1616]
PATIO_COLS, PATIO_ROWS = 5, 4
PATIO_CW, PATIO_CH, PATIO_GX, PATIO_GY = 46, 26, 6, 6
PATIO_OY = 210
PATIO_LETRAS = ["A", "B", "C", "D"]

# Grades de material no chão, abaixo de cada linha: (x central, y do topo, tipo).
MATERIAIS = [
    (542.06, 692.0, "chapa"),   # LCP02
    (694.15, 692.0, "chapa"),   # LCP01
    (854.35, 692.0, "chapa"),   # LCT2,5
    (1313.89, 798.0, "chapa"),  # LCT16
    (1442.42, 798.0, "chapa"),  # LCT08
    (1572.20, 798.0, "dots"),   # LCL4,5
    (1702.59, 798.0, "dots"),   # LCL08
    (330.0, 890.0, "chapa"),    # LWB
    (330.0, 965.0, "chapa"),    # LWB
]

# Onde cada desenho-fonte entra na planta.
EMBEDS = {
    "svgLwb": "linha_lwb.svg",
    "svgPress": "linha_prensa.svg",
    "svgCut": "linhas_corte.svg",
}


class ErroDePreparacao(RuntimeError):
    """Falha que impede gerar arte confiável — sempre interrompe o script."""


# --------------------------------------------------------------------------- #
# utilidades
# --------------------------------------------------------------------------- #


def _classes(el: ET.Element) -> list[str]:
    return (el.get("class") or "").split()


def _maquinas(raiz: ET.Element) -> list[ET.Element]:
    return [el for el in raiz.iter() if "machine" in _classes(el)]


def _por_id(raiz: ET.Element, alvo: str) -> ET.Element | None:
    for el in raiz.iter():
        if el.get("id") == alvo:
            return el
    return None


def _pai_de(raiz: ET.Element, filho: ET.Element) -> ET.Element | None:
    for pai in raiz.iter():
        for candidato in list(pai):
            if candidato is filho:
                return pai
    return None


def normalizar_nome(nome: str) -> str:
    """Transforma o nome escrito no desenho na chave do conjunto.

    "Tracionador / medição" -> "TRACIONADOR_MEDICAO"
    "ConConDL1&2"           -> "CONCONDL1_2"
    "Aplainadora"           -> "APLANADORA"   (correção de grafia)
    """
    sem_acento = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    chave = re.sub(r"[^0-9A-Za-z]+", "_", sem_acento).strip("_").upper()
    return CORRECOES_GRAFIA.get(chave, chave)


def _sub(pai: ET.Element, tag: str, **attrs) -> ET.Element:
    el = ET.SubElement(pai, S + tag)
    for chave, valor in attrs.items():
        el.set(chave.replace("_", "-"), str(valor))
    return el


# --------------------------------------------------------------------------- #
# T1 — materializar os clones
# --------------------------------------------------------------------------- #


def materializar_clone(raiz: ET.Element, origem: str, clone_id: str, transform: str, sufixo: str) -> None:
    origem_el = _por_id(raiz, origem)
    if origem_el is None:
        raise ErroDePreparacao(f"grupo de origem '{origem}' não existe no desenho")
    if _por_id(raiz, clone_id) is not None:
        raise ErroDePreparacao(f"o clone '{clone_id}' já existe no desenho de origem")

    clone = copy.deepcopy(origem_el)
    clone.set("id", clone_id)
    clone.set("transform", transform)
    for el in clone.iter():
        if el is clone:
            continue
        if el.get("id"):
            el.set("id", el.get("id") + sufixo)

    pai = _pai_de(raiz, origem_el)
    if pai is None:
        raise ErroDePreparacao(f"não achei o pai de '{origem}'")
    pai.append(clone)


# --------------------------------------------------------------------------- #
# T2 — agrupar a LWB
# --------------------------------------------------------------------------- #


def agrupar_lwb(raiz: ET.Element) -> None:
    if _por_id(raiz, LWB_GRUPO) is not None:
        return

    maquinas = []
    for ident in LWB_MAQUINAS:
        el = _por_id(raiz, ident)
        if el is None:
            raise ErroDePreparacao(f"máquina '{ident}' da LWB não existe no desenho")
        maquinas.append(el)

    pai = _pai_de(raiz, maquinas[0])
    if pai is None:
        raise ErroDePreparacao("não achei o pai das máquinas da LWB")
    if any(_pai_de(raiz, m) is not pai for m in maquinas[1:]):
        raise ErroDePreparacao("as máquinas da LWB estão espalhadas em pais diferentes")

    posicao = list(pai).index(maquinas[0])
    grupo = ET.Element(S + "g", {"id": LWB_GRUPO})
    for maquina in maquinas:
        pai.remove(maquina)
        grupo.append(maquina)
    pai.insert(posicao, grupo)


# --------------------------------------------------------------------------- #
# T3 + T4 — identidade do ativo e chave do conjunto
# --------------------------------------------------------------------------- #


def gravar_identidade(raiz: ET.Element, arquivo: str) -> dict[str, list[dict]]:
    """Escreve `data-ativo` nos grupos e `data-conj` nas máquinas.

    Devolve {ativo: [{"conjunto":..., "chave":..., "nome":..., "id":...}]}.
    """
    inventario: dict[str, list[dict]] = {}
    vistas: set[ET.Element] = set()
    pares: list[tuple[ET.Element, str]] = []

    for grupo_id, ativo in ATIVO_POR_GRUPO.items():
        grupo = _por_id(raiz, grupo_id)
        if grupo is None:
            continue
        grupo.set("data-ativo", ativo)
        inventario.setdefault(ativo, [])
        pares.extend((maquina, ativo) for maquina in _maquinas(grupo))

    for maquina_id, ativo in MAQUINAS_AVULSAS.items():
        maquina = _por_id(raiz, maquina_id)
        if maquina is None:
            continue
        if "machine" not in _classes(maquina):
            raise ErroDePreparacao(f"{arquivo}: '{maquina_id}' não é uma máquina")
        inventario.setdefault(ativo, [])
        pares.append((maquina, ativo))

    chaves: dict[str, str] = {}
    for maquina, ativo in pares:
        nome = maquina.get("data-name")
        if not nome:
            raise ErroDePreparacao(
                f"{arquivo}: máquina '{maquina.get('id')}' do ativo {ativo} não tem data-name"
            )
        conjunto = normalizar_nome(nome)
        chave = f"{ativo}.{conjunto}"
        if chave in chaves:
            raise ErroDePreparacao(
                f"{arquivo}: colisão de chave no ativo {ativo} — '{chaves[chave]}' e "
                f"'{nome}' geram a mesma chave '{chave}'. Renomeie uma das máquinas no "
                f"desenho de origem; chave duplicada faz um conjunto nunca acender."
            )
        chaves[chave] = nome
        maquina.set("data-conj", chave)
        vistas.add(maquina)
        inventario[ativo].append(
            {"conjunto": conjunto, "chave": chave, "nome": nome, "id": maquina.get("id")}
        )

    orfas = [m.get("id") for m in _maquinas(raiz) if m not in vistas]
    if orfas:
        raise ErroDePreparacao(
            f"{arquivo}: máquinas fora de qualquer grupo de linha: {orfas}. "
            f"Sem grupo não há ativo, e sem ativo a máquina nunca recebe cor."
        )
    return inventario


# --------------------------------------------------------------------------- #
# T5 e demais elementos que o mockup montava em JavaScript
# --------------------------------------------------------------------------- #


def desenhar_rotulos(raiz: ET.Element) -> None:
    grupo = _sub(raiz, "g", id="asset-labels")
    for texto, x, y in ROTULOS_ATIVO:
        el = _sub(grupo, "text", **{"class": "assetlbl", "text_anchor": "middle", "x": x, "y": y})
        el.text = texto


def _caixa_com_margem(ativo: str) -> dict[str, float]:
    """A moldura do ativo em coordenadas da planta — é ela que a página usa para posicionar
    a área clicável por cima do desenho."""
    x0, y0, x1, y1 = CAIXAS_ATIVO[ativo]
    m = MARGEM_MOLDURA
    return {
        "x": round(x0 - m, 2),
        "y": round(y0 - m, 2),
        "largura": round((x1 - x0) + 2 * m, 2),
        "altura": round((y1 - y0) + 2 * m, 2),
    }


def _recorte(ativo: str) -> dict:
    """O `viewBox` que mostra só este ativo, com folga em volta."""
    x, y, largura, altura = RECORTES[ativo]
    m = MARGEM_RECORTE
    return {
        "desenho": DESENHO_DO_ATIVO[ativo],
        "view_box": [round(x - m, 2), round(y - m, 2),
                     round(largura + 2 * m, 2), round(altura + 2 * m, 2)],
    }


def desenhar_molduras(raiz: ET.Element) -> None:
    grupo = _sub(raiz, "g", id="asset-frames")
    for ativo in ORDEM_ATIVOS:
        x0, y0, x1, y1 = CAIXAS_ATIVO[ativo]
        m = MARGEM_MOLDURA
        alvo = _sub(grupo, "g", **{"data-ativo": ativo})
        _sub(
            alvo,
            "rect",
            **{
                "class": "asset-frame",
                "x": round(x0 - m, 2),
                "y": round(y0 - m, 2),
                "width": round((x1 - x0) + 2 * m, 2),
                "height": round((y1 - y0) + 2 * m, 2),
                "rx": 8,
            },
        )
        # Área de captura do clique. Precisa de opacidade mínima diferente de
        # zero: com fill-opacity 0 o elemento deixa de receber clique em alguns
        # navegadores (aprendizado registrado no projeto).
        _sub(
            alvo,
            "rect",
            **{
                "class": "asset-hit",
                "x": round(x0 - m, 2),
                "y": round(y0 - m, 2),
                "width": round((x1 - x0) + 2 * m, 2),
                "height": round((y1 - y0) + 2 * m, 2),
                "rx": 8,
                "data-ativo": ativo,
            },
        )


def desenhar_patios(raiz: ET.Element) -> None:
    alvo = _por_id(raiz, "yards")
    if alvo is None:
        raise ErroDePreparacao("planta_base.svg não tem o grupo 'yards'")

    largura = PATIO_COLS * PATIO_CW + (PATIO_COLS - 1) * PATIO_GX
    altura = PATIO_ROWS * PATIO_CH + (PATIO_ROWS - 1) * PATIO_GY
    for cx in PATIOS_CX:
        ox = cx - largura / 2
        _sub(
            alvo, "rect",
            **{"class": "yard", "x": ox - 10, "y": PATIO_OY - 10,
               "width": largura + 20, "height": altura + 20, "rx": 6},
        )
        for linha in range(PATIO_ROWS):
            for coluna in range(PATIO_COLS):
                x = ox + coluna * (PATIO_CW + PATIO_GX)
                y = PATIO_OY + linha * (PATIO_CH + PATIO_GY)
                _sub(alvo, "rect", **{"class": "cell", "x": x, "y": y,
                                      "width": PATIO_CW, "height": PATIO_CH, "rx": 3})
                rotulo = _sub(alvo, "text", **{"class": "yardlbl", "x": x + 5, "y": y + 15})
                rotulo.text = f"{PATIO_LETRAS[linha]}{coluna + 1}"


def desenhar_materiais(raiz: ET.Element) -> None:
    grupo = _sub(raiz, "g", id="materials")
    for cx, y, tipo in MATERIAIS:
        if tipo == "chapa":
            cw, ch, gx, gy, cols, rows = 24, 16, 5, 7, 4, 2
            total = cols * cw + (cols - 1) * gx
            x0 = cx - total / 2
            for linha in range(rows):
                for coluna in range(cols):
                    x = round(x0 + coluna * (cw + gx), 2)
                    yy = y + linha * (ch + gy)
                    vazia = ((linha * cols + coluna) % 2) == 1
                    _sub(grupo, "rect", **{"class": "mblank" if vazia else "mchapa",
                                           "x": x, "y": yy, "width": cw, "height": ch, "rx": 2})
                    if not vazia:
                        _sub(grupo, "line", **{"class": "mline", "x1": x + 3, "y1": yy + ch / 2,
                                               "x2": x + cw - 3, "y2": yy + ch / 2})
        else:
            cols, rows, sp = 6, 5, 6
            x0 = cx - (cols - 1) * sp / 2
            for linha in range(rows):
                for coluna in range(cols):
                    _sub(grupo, "circle", **{"class": "mdot", "cx": round(x0 + coluna * sp, 2),
                                             "cy": y + linha * sp, "r": 1.7})


# --------------------------------------------------------------------------- #
# preparação de cada desenho e composição da planta
# --------------------------------------------------------------------------- #


def preparar_desenho(arquivo: str) -> tuple[ET.ElementTree, dict[str, list[dict]]]:
    arvore = ET.parse(FONTE / arquivo)
    raiz = arvore.getroot()

    for alvo, origem, clone_id, transform, sufixo in CLONES:
        if alvo == arquivo:
            materializar_clone(raiz, origem, clone_id, transform, sufixo)

    if arquivo == "linha_lwb.svg":
        agrupar_lwb(raiz)

    inventario = gravar_identidade(raiz, arquivo)
    return arvore, inventario


def compor_planta(desenhos: dict[str, ET.Element]) -> ET.ElementTree:
    arvore = ET.parse(FONTE / "planta_base.svg")
    raiz = arvore.getroot()

    for embed_id, arquivo in EMBEDS.items():
        alvo = _por_id(raiz, embed_id)
        if alvo is None:
            raise ErroDePreparacao(f"planta_base.svg não tem o encaixe '{embed_id}'")
        if len(alvo):
            raise ErroDePreparacao(f"o encaixe '{embed_id}' já tem conteúdo")
        for filho in list(desenhos[arquivo]):
            alvo.append(copy.deepcopy(filho))

    desenhar_patios(raiz)
    desenhar_materiais(raiz)
    desenhar_molduras(raiz)
    desenhar_rotulos(raiz)
    return arvore


def escrever(arvore: ET.ElementTree, destino: Path) -> None:
    ET.indent(arvore, space="  ")
    arvore.write(destino, encoding="unicode", xml_declaration=False)
    destino.write_text(destino.read_text(encoding="utf-8") + "\n", encoding="utf-8")


def main() -> int:
    ET.register_namespace("", SVG_NS)
    PREPARADO.mkdir(parents=True, exist_ok=True)

    desenhos: dict[str, ET.Element] = {}
    conjuntos_por_ativo: dict[str, list[dict]] = {}

    for arquivo in ("linha_prensa.svg", "linhas_corte.svg", "linha_lwb.svg"):
        arvore, inventario = preparar_desenho(arquivo)
        desenhos[arquivo] = arvore.getroot()
        for ativo, conjuntos in inventario.items():
            if ativo in conjuntos_por_ativo:
                raise ErroDePreparacao(f"o ativo {ativo} aparece em mais de um desenho")
            conjuntos_por_ativo[ativo] = conjuntos
        escrever(arvore, PREPARADO / arquivo)
        print(f"  {arquivo}: {len(_maquinas(arvore.getroot()))} máquinas")

    faltando = [a for a in ORDEM_ATIVOS if a not in conjuntos_por_ativo]
    if faltando:
        raise ErroDePreparacao(f"ativos sem desenho: {faltando}")

    planta = compor_planta(desenhos)
    escrever(planta, PREPARADO / "planta.svg")
    total = len(_maquinas(planta.getroot()))
    print(f"  planta.svg: {total} máquinas")

    inventario = {
        "planta": {"view_box": list(VIEW_BOX_PLANTA)},
        "ativos": [
            {
                "ativo": ativo,
                "caixa": _caixa_com_margem(ativo),
                "croqui": _recorte(ativo),
                "conjuntos": [
                    {"chave": c["chave"], "conjunto": c["conjunto"], "nome": c["nome"]}
                    for c in conjuntos_por_ativo[ativo]
                ],
            }
            for ativo in ORDEM_ATIVOS
        ],
        "total_maquinas": total,
    }
    (PREPARADO / "inventario.json").write_text(
        json.dumps(inventario, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  inventario.json: {len(ORDEM_ATIVOS)} ativos, {total} conjuntos")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ErroDePreparacao as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        sys.exit(1)
