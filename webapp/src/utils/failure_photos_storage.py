# src/utils/failure_photos_storage.py

"""
Camada de storage das fotos da Análise de Falhas (DS-02 do SDD analise-falhas-fotos).

Isola TODO o acesso ao file server externo (CIFS marca em produção; pasta local em
desenvolvimento). O disco do webapp nunca recebe os bytes das imagens — tudo é lido e
gravado direto no caminho de `FAILURE_PHOTOS_ROOT`.

Layout (BR-01): `{raiz}/{AAAA}/{MM}/{subpasta}/{uuid}.{ext}` para o original e
`{raiz}/{AAAA}/{MM}/{subpasta}/.thumbs/{uuid}.{ext}` para a miniatura.

Segurança (BR-06): `_seguro()` garante que nenhum caminho escape da pasta da análise
(proteção de path traversal, mesmo padrão do `docs_config`).
"""

from __future__ import annotations

import io
import os
import re
import uuid
from pathlib import Path
from typing import Optional

# mime real → extensão normalizada e formato Pillow (BR-03).
FORMATOS = {
    "image/jpeg": (".jpg", "JPEG"),
    "image/png": (".png", "PNG"),
    "image/webp": (".webp", "WEBP"),
}
MAX_BYTES = 7_500_000     # 7,5 MB por foto (BR-03)
THUMB_LADO = 320          # maior lado da miniatura, px (BR-04)

_FALLBACK_DEV = "/data/failure-photos"  # usado quando FAILURE_PHOTOS_ROOT não é setado


class PhotosStorageError(Exception):
    """Falha ao acessar o file server (indisponível, sem permissão, I/O). Tratável —
    o chamador degrada com elegância (BR-09), não deixa virar 500 cru."""


def raiz() -> Path:
    """Raiz do storage de fotos: `FAILURE_PHOTOS_ROOT` (mount CIFS em prod), com
    fallback local em desenvolvimento."""
    return Path(os.getenv("FAILURE_PHOTOS_ROOT", _FALLBACK_DEV))


def disponivel() -> bool:
    """True se a raiz existe (ou pôde ser criada) e é gravável. Base da degradação
    graciosa quando o CIFS está fora (BR-09)."""
    try:
        r = raiz()
        r.mkdir(parents=True, exist_ok=True)
        return os.access(r, os.W_OK)
    except (OSError, ValueError):
        return False


def _slug(valor) -> str:
    """Normaliza um texto para nome de pasta seguro (alfanumérico, `-`, `_`, `.`)."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", str(valor or "").strip()).strip("-")
    return s or "x"


def nome_pasta_analise(analise: dict) -> str:
    """Nome LEGÍVEL da pasta da análise no file server (BR-01):
    `{equipamento}_{causa}_{id-curto}`.

    Só usa campos **imutáveis** do snapshot da parada (`parada.equipamento_nome`/
    `equipamento`, `parada.causa`) + os 8 primeiros do `_id` — assim o caminho é
    determinístico e **não muda** se o equipamento for renomeado depois (senão os
    arquivos "sumiriam"). O id-curto garante unicidade entre paradas parecidas.
    Ex.: `PRENSA-02_201_6a59100e`."""
    parada = analise.get("parada") or {}
    equip = parada.get("equipamento_nome") or parada.get("equipamento") or "equip"
    causa = parada.get("causa") or "causa"
    id_curto = (str(analise.get("id") or "")[:8]) or "00000000"
    return f"{_slug(equip)}_{_slug(causa)}_{id_curto}"


def mes_ref(analise: dict) -> str:
    """Mês de referência 'YYYYMM' da parada (extraído da chave
    `EQUIP_YYYYMM_causa_hash`; fallback para o mês de `parada.inicio`)."""
    for parte in (analise.get("parada_chave") or "").split("_"):
        if len(parte) == 6 and parte.isdigit():
            return parte
    inicio = (analise.get("parada") or {}).get("inicio")
    if hasattr(inicio, "strftime"):
        return inicio.strftime("%Y%m")
    if isinstance(inicio, str) and len(inicio) >= 7:
        return inicio[:4] + inicio[5:7]  # ISO YYYY-MM...
    return "000000"


def subpasta_rel(analise: dict) -> str:
    """Caminho relativo LEGÍVEL da pasta da análise no file server, para exibição:
    `{AAAA}/{MM}/{equip}_{causa}_{id-curto}`."""
    m = mes_ref(analise)
    return f"{m[:4]}/{m[4:6]}/{nome_pasta_analise(analise)}"


def _pasta(subpasta: str, mes_ref: str) -> Path:
    """Pasta da análise: `{raiz}/{AAAA}/{MM}/{subpasta}` (mes_ref = 'YYYYMM')."""
    aaaa, mm = mes_ref[:4], mes_ref[4:6]
    return raiz() / aaaa / mm / subpasta


def _seguro(base: Path, nome: str) -> Optional[Path]:
    """Resolve `base/nome` e confirma que fica SOB `base` (anti path traversal).

    `nome` pode conter subpasta conhecida (ex.: '.thumbs/uuid.jpg'); qualquer tentativa
    de escapar (`../`) devolve None.
    """
    try:
        base_r = base.resolve()
        alvo = (base / nome).resolve()
    except (OSError, ValueError):
        return None
    if alvo == base_r or base_r in alvo.parents:
        return alvo
    return None


def salvar(subpasta: str, mes_ref: str, dados: bytes, mime: str) -> dict:
    """Valida, trata (Pillow) e grava original + miniatura no file server.

    - Valida mime (BR-03) e tamanho ≤ 7,5 MB.
    - `exif_transpose` (orientação) + **remove EXIF/GPS** (não repassa exif no save).
    - Gera thumbnail (maior lado ~320px) em `.thumbs/`.
    Retorna a ficha: {arquivo, thumb, largura, altura, bytes, mime}.
    Levanta `ValueError` (mime/tamanho) ou `PhotosStorageError` (I/O no file server).
    """
    if mime not in FORMATOS:
        raise ValueError(f"Formato não suportado: {mime}")
    if not dados or len(dados) > MAX_BYTES:
        raise ValueError("Arquivo vazio ou acima de 7,5 MB")

    ext, fmt = FORMATOS[mime]
    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(dados))
        img = ImageOps.exif_transpose(img)  # endireita foto de celular
    except Exception as e:
        raise ValueError(f"Imagem inválida: {e}")

    largura, altura = img.size
    salvar_kwargs = {}
    if fmt == "JPEG":
        img = img.convert("RGB")
        salvar_kwargs = {"quality": 85, "optimize": True}

    nome = f"{uuid.uuid4().hex}{ext}"
    pasta = _pasta(subpasta, mes_ref)
    dest = _seguro(pasta, nome)
    dest_thumb = _seguro(pasta, f".thumbs/{nome}")
    if dest is None or dest_thumb is None:
        raise PhotosStorageError("Caminho inválido")

    try:
        pasta.mkdir(parents=True, exist_ok=True)
        dest_thumb.parent.mkdir(parents=True, exist_ok=True)
        # save SEM o kwarg `exif=` → EXIF descartado (privacidade + tamanho).
        img.save(dest, format=fmt, **salvar_kwargs)
        thumb = img.copy()
        thumb.thumbnail((THUMB_LADO, THUMB_LADO))
        thumb.save(dest_thumb, format=fmt, **salvar_kwargs)
    except OSError as e:
        raise PhotosStorageError(f"Falha ao gravar no file server: {e}")

    return {
        "arquivo": nome,
        "thumb": nome,       # mesmo nome, na subpasta .thumbs
        "largura": largura,
        "altura": altura,
        "bytes": dest.stat().st_size if dest.exists() else len(dados),
        "mime": mime,
    }


def caminho(subpasta: str, mes_ref: str, nome: str, thumb: bool = False) -> Optional[Path]:
    """Caminho absoluto para SERVIR o arquivo (original ou miniatura), com guarda de
    traversal. Devolve None se escapar da pasta ou não existir."""
    pasta = _pasta(subpasta, mes_ref)
    rel = f".thumbs/{nome}" if thumb else nome
    alvo = _seguro(pasta, rel)
    if alvo is None or not alvo.is_file():
        return None
    return alvo


def excluir(subpasta: str, mes_ref: str, arquivo: str, thumb: str) -> None:
    """Hard delete do original e da miniatura no file server (BR-07). Idempotente:
    arquivo já ausente não é erro."""
    pasta = _pasta(subpasta, mes_ref)
    for rel in (arquivo, f".thumbs/{thumb}"):
        alvo = _seguro(pasta, rel)
        if alvo is not None and alvo.exists():
            try:
                alvo.unlink()
            except OSError as e:
                raise PhotosStorageError(f"Falha ao excluir no file server: {e}")


def rotacionar(subpasta: str, mes_ref: str, arquivo: str, thumb: str,
               graus: int, mime: str) -> dict:
    """Gira o original (múltiplo de 90, sentido horário como na UI) e regenera a
    miniatura, sobrescrevendo os arquivos no file server. Rotação **lossless** via
    `transpose` (sem interpolação). Devolve as novas dimensões `{largura, altura}`.

    Mapeamento: a UI usa graus no sentido horário (CSS `rotate` positivo); o Pillow
    `ROTATE_*` é anti-horário — por isso 90°(horário) → `ROTATE_270`, etc."""
    graus = int(graus) % 360
    if graus == 0:
        raise ValueError("Rotação nula")
    ext, fmt = FORMATOS.get(mime, (".jpg", "JPEG"))
    from PIL import Image
    tmap = {
        90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }
    if graus not in tmap:
        raise ValueError("Rotação deve ser múltiplo de 90")

    pasta = _pasta(subpasta, mes_ref)
    orig = _seguro(pasta, arquivo)
    th = _seguro(pasta, f".thumbs/{thumb}")
    if orig is None or th is None or not orig.is_file():
        raise PhotosStorageError("Arquivo não encontrado")

    salvar_kwargs = {"quality": 85, "optimize": True} if fmt == "JPEG" else {}
    try:
        img = Image.open(orig).transpose(tmap[graus])
        if fmt == "JPEG":
            img = img.convert("RGB")
        img.save(orig, format=fmt, **salvar_kwargs)
        thumb_img = img.copy()
        thumb_img.thumbnail((THUMB_LADO, THUMB_LADO))
        thumb_img.save(th, format=fmt, **salvar_kwargs)
    except OSError as e:
        raise PhotosStorageError(f"Falha ao girar no file server: {e}")
    return {"largura": img.size[0], "altura": img.size[1]}
