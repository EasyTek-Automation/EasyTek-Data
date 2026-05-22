"""Renderização Plotly → PNG bytes com fallback gracioso (SP-13).

Camada 3 — isolada para que falha de kaleido/Chromium não derrube a geração do DOCX.
Usa `plotly.io.to_image` (kaleido v1 >= 1.0 conforme RV-05).

Origem: projeto SDD KPIReport (DS-02 / DS-05) — implementado em IM-03.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from io import BytesIO
from threading import RLock

import plotly.graph_objects as go
import plotly.io as pio

logger = logging.getLogger(__name__)


# ============================================================================
# PNG cache — perf #2 (KPIReport-v2).
# Chave: hash determinístico do (fig dict, width, height, scale).
# TTL: 60s — janela típica entre dois exports (PDF então DOCX).
# Capacidade: 64 entradas — evita crescimento ilimitado em processos longos.
# ============================================================================
_PNG_CACHE: dict[str, tuple[float, bytes]] = {}
_PNG_CACHE_LOCK = RLock()
_PNG_CACHE_TTL_S = 60.0
_PNG_CACHE_MAX = 64


def _png_cache_key(fig: go.Figure, width: int, height: int, scale: int) -> str:
    """Hash determinístico da figura + opts de render. Estável entre processos."""
    try:
        payload = json.dumps(fig.to_dict(), sort_keys=True, default=str)
    except Exception:
        # to_dict pode falhar em figs malformadas — sem cache nesse caso.
        return ""
    h = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f"{h}:{width}x{height}@{scale}"


def _png_cache_get(key: str) -> bytes | None:
    if not key:
        return None
    with _PNG_CACHE_LOCK:
        entry = _PNG_CACHE.get(key)
        if not entry:
            return None
        ts, png = entry
        if time.monotonic() - ts > _PNG_CACHE_TTL_S:
            _PNG_CACHE.pop(key, None)
            return None
        return png


def _png_cache_put(key: str, png: bytes) -> None:
    if not key:
        return
    with _PNG_CACHE_LOCK:
        if len(_PNG_CACHE) >= _PNG_CACHE_MAX:
            # FIFO-ish eviction: remove entrada mais antiga
            oldest = min(_PNG_CACHE.items(), key=lambda kv: kv[1][0])[0]
            _PNG_CACHE.pop(oldest, None)
        _PNG_CACHE[key] = (time.monotonic(), png)


def png_cache_clear() -> None:
    """Limpa o cache PNG. Útil em testes."""
    with _PNG_CACHE_LOCK:
        _PNG_CACHE.clear()


def png_cache_stats() -> dict:
    """Telemetria simples — usado em testes e diagnóstico."""
    with _PNG_CACHE_LOCK:
        return {"size": len(_PNG_CACHE), "ttl_s": _PNG_CACHE_TTL_S, "max": _PNG_CACHE_MAX}


class SunburstRenderError(Exception):
    """Reservada para futura evolução em que falha de imagem aborte a geração.

    Caminho atual nunca propaga ao chamador — `renderizar_sunburst_png` captura
    tudo e devolve placeholder.
    """


def renderizar_sunburst_png(
    fig: go.Figure,
    kpi_label: str,
    width: int = 900,
    height: int = 700,
    scale: int = 2,
) -> bytes:
    """Renderiza Plotly Figure como PNG via `pio.to_image` (kaleido v1).

    Em falha, devolve placeholder PNG cinza com texto "Sunburst {kpi_label} indisponível"
    e emite log WARNING (sem stack trace — SP-17 L5). Nunca lança ao chamador (BR-10).
    Resultado armazenado em cache 60s (perf #2) — segundo export mesma fig vira instant.
    """
    key = _png_cache_key(fig, width, height, scale)
    cached = _png_cache_get(key)
    if cached is not None:
        return cached
    try:
        png = pio.to_image(fig, format="png", width=width, height=height, scale=scale)
        _png_cache_put(key, png)
        return png
    except Exception as exc:
        logger.warning(
            "Falha ao renderizar sunburst %s: %s",
            kpi_label, type(exc).__name__,
        )
        return _gerar_placeholder_png(kpi_label, width, height, scale)


def renderizar_em_paralelo(
    specs: list,
    width: int = 900,
    height: int = 700,
    scale: int = 2,
    n_workers: int = 1,
) -> dict:
    """Renderiza múltiplas Plotly Figures via Kaleido async (asyncio.gather).

    Args:
        specs: lista de tuplas `(key, fig, label)` — key identifica resultado, fig é
            Plotly Figure, label usado em logs/placeholder de falha.
        width/height/scale: dimensões da imagem (idênticas a `renderizar_sunburst_png`).
        n_workers: workers paralelos do Kaleido (1 já é ótimo — overhead spawn > ganho).

    Returns:
        dict `{key: png_bytes}`. Em falha individual, retorna placeholder. Em falha
        do Kaleido em si, faz fallback serial chamando `renderizar_sunburst_png`.

    Performance: 12s serial → ~3s via persistent Kaleido(n=1) async (perf #1).
    """
    if not specs:
        return {}

    # Fase A — checa cache PNG (perf #2). Quem bateu sai do batch async.
    results: dict = {}
    cache_keys: dict = {}  # key → cache_key (para popular cache após render)
    misses: list = []  # specs que precisam render
    for key, fig, label in specs:
        ck = _png_cache_key(fig, width, height, scale)
        cache_keys[key] = ck
        cached = _png_cache_get(ck)
        if cached is not None:
            results[key] = cached
        else:
            misses.append((key, fig, label))

    if not misses:
        return results

    import asyncio
    try:
        from kaleido import Kaleido
    except ImportError:
        logger.warning("Kaleido class indisponível — fallback serial")
        for key, fig, label in misses:
            results[key] = renderizar_sunburst_png(fig, label, width, height, scale)
        return results

    opts = {"format": "png", "width": width, "height": height, "scale": scale}
    n = max(1, min(n_workers, len(misses)))

    async def _gather():
        k = Kaleido(n=n)
        await k.open()
        try:
            tasks = [k.calc_fig(fig, opts=opts) for _, fig, _ in misses]
            return await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await k.close()

    try:
        raw = asyncio.run(_gather())
    except Exception:
        logger.exception("Falha kaleido async — fallback serial")
        for key, fig, label in misses:
            results[key] = renderizar_sunburst_png(fig, label, width, height, scale)
        return results

    for (key, _fig, label), png in zip(misses, raw):
        if isinstance(png, Exception):
            logger.warning("Falha kaleido %s: %s", label, type(png).__name__)
            results[key] = _gerar_placeholder_png(label, width, height, scale)
        else:
            results[key] = png
            ck = cache_keys.get(key)
            if ck:
                _png_cache_put(ck, png)
    return results


def _gerar_placeholder_png(
    kpi_label: str,
    width: int,
    height: int,
    scale: int,
) -> bytes:
    """Gera PNG cinza com texto "Sunburst {kpi_label} indisponível" centralizado.

    Implementação via Pillow (DS-05): fundo `#CCCCCC` cinza neutro, texto preto centralizado.
    Dimensões idênticas ao sunburst real para preservar layout do template.

    Fallback do fallback (SP-13 / DS-03): se Pillow também falhar, devolve PNG 1×1
    transparente hardcoded — garante que `docxtpl.InlineImage` não quebre.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Aplica scale para resolução compatível com o sunburst real
        w = width * scale
        h = height * scale

        img = Image.new("RGB", (w, h), color="#CCCCCC")
        draw = ImageDraw.Draw(img)

        texto = f"Sunburst {kpi_label} indisponível"
        # Fonte: tenta DejaVuSans (instalada via fonts-liberation no Dockerfile), cai para default
        try:
            font_size = max(int(24 * scale), 12)
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Centraliza texto
        bbox = draw.textbbox((0, 0), texto, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pos = ((w - tw) // 2, (h - th) // 2)
        draw.text(pos, texto, fill="#000000", font=font)

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except Exception as exc:
        logger.warning(
            "Falha ao gerar placeholder PNG para %s: %s — usando PNG 1×1 hardcoded",
            kpi_label, type(exc).__name__,
        )
        # PNG 1×1 transparente hardcoded — não quebra docxtpl.InlineImage
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8"
            b"\x0f\x00\x00\x01\x01\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
