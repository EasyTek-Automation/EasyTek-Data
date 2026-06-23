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


# Casas decimais por campo — espelha a formatação do PDF (kpi_report_v2_pdf._fmt = casas=1).
# O template DOCX imprime os valores crus via Jinja ({{ bloco1.kpis_planta.mttr }}), sem filtro,
# expondo floats como "31.362000000000002". Pré-formatamos aqui para strings pt-BR antes do render.
_DOCX_CASAS_KPI = {"mtbf": 1, "mttr": 1, "taxa_avaria": 1}
_DOCX_CASAS_LINHA = {
    "mtbf": 1, "mttr": 1, "taxa_avaria": 1,
    "avaria_min": 1, "atividade_h": 1, "uptime_h": 1,
    "num_ordens": 0, "num_paradas": 0,
}


def _fmt_campos(d: dict | None, casas_por_campo: dict[str, int]) -> None:
    """Formata in-place os campos numéricos de `d` conforme `casas_por_campo` (pt-BR)."""
    if not isinstance(d, dict):
        return
    for campo, casas in casas_por_campo.items():
        v = d.get(campo)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            d[campo] = cfg.fmt_numero(v, casas=casas)


def _formatar_numeros_docx(dados: dict) -> None:
    """Pré-formata todos os números expostos ao template DOCX para strings pt-BR.

    Mutação in-place — `montar_docx` é o passo terminal do export DOCX, o dict não é
    reutilizado depois. Mesmo padrão da mutação de `sunburst_figures` (linha abaixo).
    """
    for bkey in ("bloco1", "bloco3"):
        bloco = dados.get(bkey)
        if not isinstance(bloco, dict):
            continue
        _fmt_campos(bloco.get("kpis_planta"), _DOCX_CASAS_KPI)
        _fmt_campos(bloco.get("metas"), _DOCX_CASAS_KPI)
        if isinstance(bloco.get("alert_range"), (int, float)) and not isinstance(bloco.get("alert_range"), bool):
            bloco["alert_range"] = cfg.fmt_numero(bloco["alert_range"], casas=1)

    bloco4 = dados.get("bloco4")
    if isinstance(bloco4, dict):
        for linha in (bloco4.get("linhas") or []):
            _fmt_campos(linha, _DOCX_CASAS_LINHA)
        _fmt_campos(bloco4.get("total"), _DOCX_CASAS_LINHA)

    for bkey in ("bloco2", "bloco5"):
        bloco = dados.get(bkey)
        if isinstance(bloco, dict):
            for parada in (bloco.get("paradas") or []):
                _fmt_campos(parada, {"duracao_min": 0})


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


def _mes_corrente_do_relatorio(dados: dict) -> tuple[int, str]:
    """Resolve `(ano, "YYYY-MM")` do mês corrente do relatório (SP-16 / DS-11).

    Preferência: início da janela mensal já calculada em `dados["periodo"]["inicio_mensal"]`
    — garante que o custo cobre o mesmo mês dos demais blocos. Fallback: `compute_monthly_window`
    sobre o agora no fuso configurado. Sem hardcode de data.
    """
    periodo = dados.get("periodo")
    inicio = periodo.get("inicio_mensal") if isinstance(periodo, dict) else None
    if inicio is None:
        inicio, _ = cfg.compute_monthly_window(cfg._now_in_report_timezone())
    return inicio.year, f"{inicio.year:04d}-{inicio.month:02d}"


def _inject_custo_mensal(template: DocxTemplate, dados: dict) -> None:
    """Injeta a figura de custo do mês corrente como InlineImage no contexto do template.

    DOCX-only (DS-11): roda no passo terminal do export, não em `coletar_dados_relatorio`.
    Defensivo — qualquer falha (sem dados, erro de import/Mongo de custos, figura `None`) deixa
    `dados['custo_mensal_img'] = None` e o template omite o bloco. Nunca derruba o DOCX.
    """
    try:
        ano, mes = _mes_corrente_do_relatorio(dados)
        from src.custos.figuras import figura_custo_mensal
        from src.utils.kpi_report_figures import renderizar_sunburst_png

        fig = figura_custo_mensal(ano, mes)
        if fig is None:
            dados["custo_mensal_img"] = None
            return
        # Render em alta resolução (mantém a proporção ~2.39:1 da aba) para nitidez ao
        # ocupar a largura cheia da página landscape.
        png = renderizar_sunburst_png(fig, kpi_label="custo_mensal",
                                      width=1600, height=668, scale=2)
        # 255 mm = largura útil cheia da página landscape (= largura das tabelas dos blocos,
        # 14480 twips); docxtpl preserva a proporção.
        dados["custo_mensal_img"] = InlineImage(template, BytesIO(png), width=Mm(255))
        dados["custo_mensal_titulo"] = f"Custo de Manutenção — {mes}"
    except Exception:
        logger.exception("Falha ao injetar gráfico de custo no DOCX; bloco omitido")
        dados["custo_mensal_img"] = None


_REC_LIMIT, _MAI_LIMIT = 10, 5


def _fmt_linha_lanc(l: dict) -> dict:
    """Formata uma linha de lançamento de custo para o template DOCX (SP-17 / DS-12).

    Data → `dd/mm/aaaa`; valor → `R$ x.xxx,xx` (pt-BR, 2 casas). Demais campos passam direto.
    """
    data = l.get("data")
    return {
        "data": data.strftime("%d/%m/%Y") if hasattr(data, "strftime") else "",
        "equipamento": l.get("equipamento", "") or "",
        "conta_nome": l.get("conta_nome", "") or "",
        "descritor": l.get("descritor", "") or "",
        "valor": "R$ " + cfg.fmt_numero(l.get("valor", 0) or 0, casas=2),
    }


def _inject_custo_tabelas(dados: dict) -> None:
    """Popula `custo_recentes` / `custo_maiores` (listas formatadas) no contexto do template.

    DOCX-only (DS-12) e defensivo — espelha `_inject_custo_mensal`. Qualquer falha (sem dados, erro
    de import/Mongo de custos) deixa as listas vazias e o template omite cada tabela. Nunca derruba
    o DOCX.
    """
    try:
        ano, mes = _mes_corrente_do_relatorio(dados)
        from src.custos.leitura import fetch_lancamentos_maiores, fetch_lancamentos_recentes

        rec = fetch_lancamentos_recentes(ano, mes, limit=_REC_LIMIT) or []
        mai = fetch_lancamentos_maiores(ano, mes, limit=_MAI_LIMIT) or []
        dados["custo_recentes"] = [_fmt_linha_lanc(l) for l in rec]
        dados["custo_maiores"] = [_fmt_linha_lanc(l) for l in mai]
    except Exception:
        logger.exception("Falha ao injetar tabelas de custo no DOCX; tabelas omitidas")
        dados["custo_recentes"] = []
        dados["custo_maiores"] = []


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

    # Gráfico de Custo de Manutenção do mês corrente (SP-16 / DS-11) — DOCX-only, defensivo.
    _inject_custo_mensal(template, dados)

    # Tabelas de custo (últimos 10 + top 5 maiores) (SP-17 / DS-12) — DOCX-only, defensivo.
    _inject_custo_tabelas(dados)

    # Formata números crus (KPIs/metas/linhas/paradas) para strings pt-BR — o template
    # imprime via Jinja sem filtro, expondo floats como "31.362000000000002" (BR-07).
    _formatar_numeros_docx(dados)

    try:
        template.render(dados, autoescape=True)
    except (TemplateSyntaxError, UndefinedError) as exc:
        raise TemplateLoadError(_resolve_template_path(), exc) from exc

    buffer = BytesIO()
    template.save(buffer)
    return buffer.getvalue()
