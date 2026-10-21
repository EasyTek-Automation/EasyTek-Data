# src/utils/failure_diagram_image.py

"""
Imagem do diagrama de causa e efeito, gerada pelo próprio quadro (Excalidraw) e guardada
para o slide (IM-AF3-08 do SDD analise-falhas-v3).

Em linguagem simples: o slide mostrava a árvore redesenhada pelo servidor, em escadinha,
sem a arrumação que o PCM fez na tela. Agora o navegador exporta o desenho do quadro
(SVG = vetor, não perde qualidade no zoom; PNG de reserva para quem não lê SVG) e ele
fica na pasta da análise, ao lado das fotos:

    {raiz}/{AAAA}/{MM}/{equip}_{causa}_{id-curto}/.diagrama/diagrama.svg
                                                          /diagrama.png
                                                          /diagrama.json

**Quando a imagem vale.** O `diagrama.json` guarda a *assinatura* da árvore no momento
da exportação. Se o diagrama mudar depois (outro salvar, pela v2 ou pela v3, sem gerar
imagem nova), a assinatura do banco deixa de bater e o slide volta ao redesenho do
servidor — nunca mostra um diagrama desatualizado. Editar texto do A3 ou fotos não
mexe na árvore, então não invalida a imagem.

**Segurança.** O SVG nunca é servido ao navegador: só entra no `.pptx`. Mesmo assim é
recusado se trouxer script ou manipulador de evento, e tem teto de tamanho.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.utils import failure_photos_storage as storage

PASTA = ".diagrama"
MAX_SVG = 3_000_000      # 3 MB — o SVG de uma análise real tem ~30 KB
MAX_PNG = 8_000_000      # 8 MB — PNG 2× de um diagrama grande

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SVG_PROIBIDO = re.compile(rb"<\s*script|\son[a-z]+\s*=|javascript:|<\s*foreignObject", re.I)


class DiagramaInvalido(ValueError):
    """Arquivo recusado (tipo errado, tamanho acima do teto, conteúdo ativo)."""


def assinatura(nos: list[dict]) -> str:
    """Impressão digital do que aparece no desenho: balões, textos, ligações, causa raiz,
    posição e tempo. Duas árvores com a mesma assinatura desenham a mesma coisa.

    Exemplo: mover um balão 30 px muda a assinatura; editar a seção 2 (contenção) não.
    """
    def _pos(v):
        return None if v is None else round(float(v))

    linhas = sorted(
        [
            str(n.get("id") or ""),
            str(n.get("parent_id") or ""),
            (n.get("titulo") or "").strip(),
            str(n.get("tipo") or ""),
            bool(n.get("is_root_cause")),
            _pos(n.get("position_x")),
            _pos(n.get("position_y")),
            int(n.get("duration_min") or 0),
        ]
        for n in (nos or [])
    )
    bruto = json.dumps(linhas, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def validar_svg(dados: bytes) -> None:
    """Aceita só SVG do tamanho esperado e sem conteúdo ativo; senão `DiagramaInvalido`."""
    if not dados or len(dados) > MAX_SVG:
        raise DiagramaInvalido("SVG vazio ou acima do limite.")
    cabeca = dados[:2000].lstrip()
    if not (cabeca.startswith(b"<svg") or cabeca.startswith(b"<?xml")) or b"<svg" not in cabeca:
        raise DiagramaInvalido("O arquivo não é um SVG.")
    if _SVG_PROIBIDO.search(dados):
        raise DiagramaInvalido("SVG com conteúdo ativo (script/evento) recusado.")


def validar_png(dados: bytes) -> None:
    """Aceita só PNG dentro do teto; senão `DiagramaInvalido`."""
    if not dados or len(dados) > MAX_PNG or not dados.startswith(_PNG_MAGIC):
        raise DiagramaInvalido("PNG vazio, inválido ou acima do limite.")


def _pasta_analise(analise: dict) -> Path:
    """Pasta `.diagrama` da análise (mesma pasta das fotos)."""
    base = storage._pasta(storage.nome_pasta_analise(analise), storage.mes_ref(analise))
    alvo = storage._seguro(base, PASTA)
    if alvo is None:
        raise storage.PhotosStorageError("Caminho do diagrama fora da pasta da análise.")
    return alvo


def _gravar_atomico(caminho: Path, dados: bytes) -> None:
    """Grava num temporário e troca de nome — quem lê nunca pega arquivo pela metade."""
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_bytes(dados)
    os.replace(tmp, caminho)


def salvar(analise: dict, svg: bytes, png: bytes, usuario: str = "") -> dict:
    """Valida e grava SVG + PNG + ficha com a assinatura da árvore ATUAL do banco.

    Levanta `DiagramaInvalido` (arquivo recusado) ou `PhotosStorageError` (file server).
    """
    validar_svg(svg)
    validar_png(png)
    if not storage.disponivel():
        raise storage.PhotosStorageError("Armazenamento indisponível.")
    pasta = _pasta_analise(analise)
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        _gravar_atomico(pasta / "diagrama.svg", svg)
        _gravar_atomico(pasta / "diagrama.png", png)
        ficha = {
            "assinatura": assinatura(analise.get("nos") or []),
            "versao": analise.get("versao"),
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "gerado_por": usuario,
        }
        _gravar_atomico(pasta / "diagrama.json", json.dumps(ficha).encode("utf-8"))
    except OSError as e:
        raise storage.PhotosStorageError(f"Falha ao gravar o diagrama: {e}")
    return ficha


def _ficha(analise: dict) -> Optional[dict]:
    """Ficha gravada junto da imagem, ou None se não houver/estiver ilegível."""
    try:
        return json.loads((_pasta_analise(analise) / "diagrama.json").read_text())
    except (OSError, ValueError, storage.PhotosStorageError):
        return None


def atual(analise: dict) -> bool:
    """A imagem guardada ainda desenha a árvore que está no banco?"""
    ficha = _ficha(analise)
    return bool(ficha) and ficha.get("assinatura") == assinatura(analise.get("nos") or [])


def carregar_valido(analise: dict) -> Optional[dict]:
    """`{"svg": bytes, "png": bytes}` se houver imagem e ela valer para a árvore atual;
    senão None (o slide usa o redesenho do servidor). Nunca levanta exceção."""
    try:
        if not atual(analise):
            return None
        pasta = _pasta_analise(analise)
        return {"svg": (pasta / "diagrama.svg").read_bytes(),
                "png": (pasta / "diagrama.png").read_bytes()}
    except Exception as e:                       # file server fora do ar: slide segue
        print(f"[failure_diagram_image] imagem indisponível para {analise.get('parada_chave')}: {e}")
        return None
