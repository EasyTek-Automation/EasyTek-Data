# -*- coding: utf-8 -*-
"""Arte preparada do Monitoramento de Ativos (Bloco A do SDD MonAtivo-Prototipo).

Cobre o que o desenho preparado precisa garantir para que a cor chegue à máquina certa:
toda máquina tem chave de conjunto, nenhuma chave se repete dentro do ativo, o desenho
não depende de script nenhum, e o inventário descreve exatamente o que está no SVG.
"""
import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ART = RAIZ / "src" / "components" / "monitoring" / "art"
PREPARADO = ART / "preparado"
SVG = "{http://www.w3.org/2000/svg}"

_spec = importlib.util.spec_from_file_location(
    "prepare_monitoring_art", RAIZ / "scripts" / "prepare_monitoring_art.py"
)
prep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prep)


def _maquinas(raiz):
    return [el for el in raiz.iter() if "machine" in (el.get("class") or "").split()]


@pytest.fixture(scope="module")
def planta():
    return ET.parse(PREPARADO / "planta.svg").getroot()


@pytest.fixture(scope="module")
def inventario():
    return json.loads((PREPARADO / "inventario.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# normalização de nome (T4)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "nome, esperado",
    [
        ("Aplainadora", "APLANADORA"),          # correção de grafia
        ("Aplanadora", "APLANADORA"),
        ("Aplanadora 1", "APLANADORA_1"),
        ("ConConDL1&2", "CONCONDL1_2"),
        ("Tracionador / medição", "TRACIONADOR_MEDICAO"),
        ("SSpeed + FiWi — Solda", "SSPEED_FIWI_SOLDA"),
        ("Fosso de laço", "FOSSO_DE_LACO"),
    ],
)
def test_normalizar_nome(nome, esperado):
    assert prep.normalizar_nome(nome) == esperado


# --------------------------------------------------------------------------- #
# o desenho preparado
# --------------------------------------------------------------------------- #


def test_planta_tem_as_84_maquinas(planta):
    assert len(_maquinas(planta)) == 84


def test_toda_maquina_tem_chave_de_conjunto(planta):
    sem_chave = [m.get("id") for m in _maquinas(planta) if not m.get("data-conj")]
    assert sem_chave == []


def test_nenhuma_chave_se_repete(planta):
    chaves = [m.get("data-conj") for m in _maquinas(planta)]
    assert len(set(chaves)) == len(chaves)


def test_planta_nao_depende_de_script(planta):
    assert [el for el in planta.iter() if el.tag == SVG + "script"] == []


def test_os_oito_grupos_de_linha_declaram_o_ativo(planta):
    grupos = {
        el.get("id"): el.get("data-ativo")
        for el in planta.iter(SVG + "g")
        if el.get("id") in prep.ATIVO_POR_GRUPO
    }
    assert grupos == prep.ATIVO_POR_GRUPO


def test_cada_ativo_tem_moldura_e_area_de_clique(planta):
    frames = {
        el.get("data-ativo")
        for el in planta.iter(SVG + "rect")
        if "asset-frame" in (el.get("class") or "").split()
        or "asset-hit" in (el.get("class") or "").split()
    }
    hits = [el for el in planta.iter(SVG + "rect") if "asset-hit" in (el.get("class") or "").split()]
    assert {h.get("data-ativo") for h in hits} == set(prep.ORDEM_ATIVOS)
    assert len(hits) == 8
    assert frames  # a moldura vive dentro de um <g data-ativo>


def test_os_rotulos_dos_ativos_sao_elementos_do_desenho(planta):
    textos = {
        el.text
        for el in planta.iter(SVG + "text")
        if "assetlbl" in (el.get("class") or "").split()
    }
    assert textos == set(prep.ORDEM_ATIVOS)


def test_a_lwb_ganhou_grupo_de_linha():
    raiz = ET.parse(PREPARADO / "linha_lwb.svg").getroot()
    grupo = [el for el in raiz.iter(SVG + "g") if el.get("id") == "lineLWB"]
    assert len(grupo) == 1
    assert grupo[0].get("data-ativo") == "LWB"
    assert len(_maquinas(grupo[0])) == 12


@pytest.mark.parametrize(
    "arquivo, clone_id, transform",
    [
        ("linha_prensa.svg", "lineB", "translate(421,0) scale(-1,1)"),
        ("linhas_corte.svg", "lineLCL2", "translate(1490,0)"),
    ],
)
def test_os_clones_estao_materializados(arquivo, clone_id, transform):
    raiz = ET.parse(PREPARADO / arquivo).getroot()
    clone = [el for el in raiz.iter(SVG + "g") if el.get("id") == clone_id]
    assert len(clone) == 1
    assert clone[0].get("transform") == transform
    assert _maquinas(clone[0])  # o clone trouxe as máquinas junto


# --------------------------------------------------------------------------- #
# o inventário
# --------------------------------------------------------------------------- #


def test_inventario_lista_os_oito_ativos(inventario):
    assert [a["ativo"] for a in inventario["ativos"]] == prep.ORDEM_ATIVOS


def test_inventario_bate_com_o_desenho(planta, inventario):
    do_desenho = {m.get("data-conj") for m in _maquinas(planta)}
    do_inventario = {c["chave"] for a in inventario["ativos"] for c in a["conjuntos"]}
    assert do_inventario == do_desenho
    assert inventario["total_maquinas"] == len(do_desenho)


def test_a_chave_e_o_ativo_mais_o_conjunto(inventario):
    for ativo in inventario["ativos"]:
        for conjunto in ativo["conjuntos"]:
            assert conjunto["chave"] == f"{ativo['ativo']}.{conjunto['conjunto']}"


# --------------------------------------------------------------------------- #
# a falha ruidosa
# --------------------------------------------------------------------------- #


def _desenho_com(nomes):
    raiz = ET.Element(SVG + "svg")
    grupo = ET.SubElement(raiz, SVG + "g", {"id": "lineLWB"})
    for i, nome in enumerate(nomes, start=1):
        ET.SubElement(grupo, SVG + "g", {"class": "machine", "id": f"w{i}", "data-name": nome})
    return raiz


def test_chave_duplicada_no_mesmo_ativo_interrompe():
    # "Aplainadora" e "Aplanadora" são grafias diferentes da mesma palavra: depois da
    # normalização viram a mesma chave, e uma delas nunca acenderia.
    raiz = _desenho_com(["Aplainadora", "Aplanadora"])
    with pytest.raises(prep.ErroDePreparacao) as erro:
        prep.gravar_identidade(raiz, "teste.svg")
    assert "colisão de chave" in str(erro.value)


def test_maquina_sem_nome_interrompe():
    raiz = ET.Element(SVG + "svg")
    grupo = ET.SubElement(raiz, SVG + "g", {"id": "lineLWB"})
    ET.SubElement(grupo, SVG + "g", {"class": "machine", "id": "w1"})
    with pytest.raises(prep.ErroDePreparacao) as erro:
        prep.gravar_identidade(raiz, "teste.svg")
    assert "data-name" in str(erro.value)


def test_maquina_fora_de_grupo_interrompe():
    raiz = _desenho_com(["Desbobinador"])
    ET.SubElement(raiz, SVG + "g", {"class": "machine", "id": "solta", "data-name": "Perdida"})
    with pytest.raises(prep.ErroDePreparacao) as erro:
        prep.gravar_identidade(raiz, "teste.svg")
    assert "fora de qualquer grupo" in str(erro.value)


def test_nomes_iguais_em_ativos_diferentes_convivem(inventario):
    # "Desbobinador" existe em quase toda linha — o ativo é o que separa as chaves.
    chaves = [
        c["chave"]
        for a in inventario["ativos"]
        for c in a["conjuntos"]
        if c["conjunto"] == "DESBOBINADOR"
    ]
    assert len(chaves) > 1
    assert len(set(chaves)) == len(chaves)
