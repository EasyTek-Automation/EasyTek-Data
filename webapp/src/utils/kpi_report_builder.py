"""Carregamento do template DOCX, inline de imagens e renderização final.

Camada 4 — único módulo que importa `docxtpl` e toca filesystem do template.

Origem: projeto SDD KPIReport (DS-02 / DS-05) — implementado em IM-03.
"""
from __future__ import annotations

import logging
import os
from io import BytesIO

from docx.opc.exceptions import PackageNotFoundError
from docx.shared import Mm  # docxtpl 0.20.2 não reexporta — usar python-docx (adaptação IM-03)
from docxtpl import DocxTemplate, InlineImage
from jinja2 import TemplateSyntaxError, UndefinedError

from src.utils import kpi_report_config as cfg

logger = logging.getLogger(__name__)


class TemplateLoadError(Exception):
    """Falha ao carregar ou renderizar template DOCX (SP-14).

    `self.path` = caminho tentado; `self.original` = exceção raiz.
    """

    def __init__(self, path: str, original: Exception) -> None:
        super().__init__(f"Falha no template DOCX: {path} ({type(original).__name__})")
        self.path = path
        self.original = original


def _resolve_template_path() -> str:
    """Resolve caminho final — override por env `KPI_REPORT_TEMPLATE_PATH` se arquivo existir;
    senão `TEMPLATE_PATH_DEFAULT` (SP-06 D6).
    """
    override = os.environ.get("KPI_REPORT_TEMPLATE_PATH", "").strip()
    if override and os.path.isfile(override):
        return override
    return cfg.TEMPLATE_PATH_DEFAULT


def _load_template() -> DocxTemplate:
    """Carrega `DocxTemplate` do caminho resolvido.

    Faz verificação eager (SP-14) — `DocxTemplate` é lazy (não valida no constructor),
    então checamos `os.path.isfile` antes. Converte qualquer falha para `TemplateLoadError`.
    """
    path = _resolve_template_path()

    if not os.path.isfile(path):
        raise TemplateLoadError(path, FileNotFoundError(f"Template não encontrado: {path}"))

    try:
        return DocxTemplate(path)
    except (PackageNotFoundError, KeyError) as exc:
        raise TemplateLoadError(path, exc) from exc


def _inline_images_from_figures(
    template: DocxTemplate,
    figures_png: dict[str, bytes],
    width_mm: int = 80,
) -> dict[str, InlineImage]:
    """Converte dict `{kpi_key: bytes_png, ...}` em dict `{kpi_key: InlineImage, ...}`.

    Largura padrão 80 mm (DS-02 / DS-04); `docxtpl` preserva proporção automaticamente.
    """
    return {
        key: InlineImage(template, BytesIO(png_bytes), width=Mm(width_mm))
        for key, png_bytes in figures_png.items()
    }


def montar_docx(dados: dict) -> bytes:
    """Carrega template, inline-a as imagens dos sunbursts, renderiza Jinja, retorna bytes do `.docx`.

    Captura `TemplateSyntaxError` / `UndefinedError` e re-lança como `TemplateLoadError` (SP-14).
    """
    template = _load_template()  # pode lançar TemplateLoadError

    # Envelopa PNGs dos sunbursts (Blocos 1 e 3) como InlineImage antes do render
    for bloco_key in ("bloco1", "bloco3"):
        bloco = dados.get(bloco_key)
        if not bloco:
            continue
        figs = bloco.get("sunburst_figures")
        if isinstance(figs, dict) and figs and isinstance(next(iter(figs.values())), (bytes, bytearray)):
            bloco["sunburst_figures"] = _inline_images_from_figures(template, figs)

    try:
        template.render(dados, autoescape=True)
    except (TemplateSyntaxError, UndefinedError) as exc:
        raise TemplateLoadError(_resolve_template_path(), exc) from exc

    buffer = BytesIO()
    template.save(buffer)
    return buffer.getvalue()
