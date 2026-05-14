"""Callbacks Dash do KPIReport — Camada 1 (D8).

Orquestra clique do usuário, coleta + builder, devolve bytes via `dcc.send_bytes`.
Controla estado visual do item de dropdown (SP-16) e timeout duro (SP-12 + RV-03).

Origem: projeto SDD KPIReport (DS-01 / DS-02 / DS-05 / DS-06) — implementado em IM-05.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
)

import dash
from dash import Input, Output, State, dcc

from src.utils import kpi_report_config as cfg
from src.utils.kpi_report_builder import TemplateLoadError, montar_docx
from src.utils.kpi_report_data import coletar_dados_relatorio

logger = logging.getLogger(__name__)

# Flag de "log L1 (store None) já emitido nesta sessão" — SP-02 item 4 / SP-17 L1
_log_l1_emitido: bool = False


# Chaves obrigatórias mínimas do contrato (SP-02 item 2)
_CHAVES_OBRIGATORIAS: tuple[str, ...] = ("data", "names", "year", "equipment_ids")


def _store_estrutura_valida(stored_data: dict | None) -> bool:
    """Verifica chaves mínimas do contrato — `data`, `names`, `year`, `equipment_ids` (SP-02 item 2).

    Retorna True apenas se todas presentes com tipos corretos. Chaves opcionais
    do store (ex: `monthly_aggregates`, `selected_equipment_ids`) não invalidam.
    """
    if not isinstance(stored_data, dict):
        return False
    for chave in _CHAVES_OBRIGATORIAS:
        if chave not in stored_data:
            return False
    if not isinstance(stored_data["data"], dict):
        return False
    if not isinstance(stored_data["names"], dict):
        return False
    if not isinstance(stored_data["year"], int):
        return False
    if not isinstance(stored_data["equipment_ids"], list):
        return False
    return True


def _executar_geracao(stored_data: dict) -> tuple[bytes, str]:
    """Envoltório que roda coleta + builder em `ThreadPoolExecutor` com timeout duro (SP-12).

    Lança `TimeoutError` se exceder `TIMEOUT_GERACAO_S`. Limitação conhecida:
    `future.cancel()` não interrompe thread nativa do kaleido (aceito em RV-03;
    mitigado por `--max-requests 200` no gunicorn). Retorna `(bytes_docx, filename)`.
    """
    def _job() -> tuple[bytes, str]:
        agora = cfg._now_in_report_timezone()
        dados = coletar_dados_relatorio(stored_data, agora)
        bytes_docx = montar_docx(dados)
        filename = cfg.gerar_nome_arquivo(agora)
        return bytes_docx, filename

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_job)
        try:
            return future.result(timeout=cfg.TIMEOUT_GERACAO_S)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise TimeoutError(f"Geração excedeu {cfg.TIMEOUT_GERACAO_S}s") from exc


def register_kpi_report_callbacks(app: dash.Dash) -> None:
    """Registra os 2 callbacks do KPIReport — chamado por `callbacks.register_callbacks(app)`."""

    @app.callback(
        Output("download-kpi-report", "data"),
        Output("btn-export-indicators-docx", "children"),
        Output("btn-export-indicators-docx", "disabled", allow_duplicate=True),
        Input("btn-export-indicators-docx", "n_clicks"),
        State("store-indicator-filters", "data"),
        prevent_initial_call=True,
    )
    def export_kpi_report_docx(n_clicks, stored_data):
        """Gera DOCX e devolve `(dcc.send_bytes, "Exportar DOCX", False)` em sucesso.

        Captura `TimeoutError` (SP-12), `TemplateLoadError` (SP-14) e `Exception`
        genérico — em todos os casos retorna `(dash.no_update, "Exportar DOCX", False)`
        com log apropriado (SP-17 L6/L7/L8).
        """
        if not n_clicks:
            raise dash.exceptions.PreventUpdate

        # Defesa em profundidade — botão deveria estar disabled (SP-02), mas valida via cinto
        if not _store_estrutura_valida(stored_data):
            logger.warning(
                "Bypass detectado: callback de geração invocado com store inválido (SP-17 L9)"
            )
            return dash.no_update, "Exportar DOCX", False

        t_inicio = time.perf_counter()
        try:
            bytes_docx, filename = _executar_geracao(stored_data)
            delta_t = time.perf_counter() - t_inicio

            if delta_t > cfg.LATENCIA_GUIDELINE_S:
                logger.warning(
                    "Geração de KPIReport ultrapassou guideline: %.2fs (limite %.0fs)",
                    delta_t, cfg.LATENCIA_GUIDELINE_S,
                )

            return (
                dcc.send_bytes(
                    lambda buf: buf.write(bytes_docx),
                    filename,
                    type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                "Exportar DOCX",
                False,
            )

        except TimeoutError:
            logger.exception(
                "Timeout duro na geração de KPIReport (>%ds) — possível hang de kaleido. Worker pode estar com slot ocupado até reciclagem.",
                int(cfg.TIMEOUT_GERACAO_S),
            )
            return dash.no_update, "Exportar DOCX", False
        except TemplateLoadError as exc:
            logger.exception(
                "Falha ao carregar/renderizar template DOCX: %s (%s)",
                exc.path, type(exc.original).__name__,
            )
            return dash.no_update, "Exportar DOCX", False
        except Exception:
            logger.exception("Erro inesperado na geração de KPIReport")
            return dash.no_update, "Exportar DOCX", False

    @app.callback(
        Output("toast-kpi-report-generating", "is_open"),
        Output("toast-kpi-report-progress", "value", allow_duplicate=True),
        Output("interval-toast-kpi-report-tick", "disabled", allow_duplicate=True),
        Output("interval-toast-kpi-report-tick", "n_intervals"),
        Input("btn-export-indicators-docx", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_kpi_report_toast(n_clicks):
        """Abre toast de progresso imediatamente ao clicar em Exportar DOCX.

        Reseta barra (`value=100`) e Interval (`n_intervals=0`, `disabled=False`)
        para reiniciar a contagem em cada clique. Roda em paralelo à geração; toast
        fecha sozinho em 10s (`duration=10000`) ou via botão dismiss.
        """
        if not n_clicks:
            raise dash.exceptions.PreventUpdate
        return True, 100, False, 0

    @app.callback(
        Output("toast-kpi-report-progress", "value", allow_duplicate=True),
        Output("interval-toast-kpi-report-tick", "disabled", allow_duplicate=True),
        Input("interval-toast-kpi-report-tick", "n_intervals"),
        prevent_initial_call=True,
    )
    def tick_kpi_report_progress(n_intervals):
        """Decrementa barra 100→0 em 100 ticks de 100ms (= 10s); desabilita ao chegar a 0."""
        if n_intervals is None:
            raise dash.exceptions.PreventUpdate
        remaining = max(0, 100 - n_intervals)
        if remaining == 0:
            return 0, True
        return remaining, False

    @app.callback(
        Output("btn-export-indicators-docx", "disabled", allow_duplicate=True),
        Input("store-indicator-filters", "data"),
        prevent_initial_call="initial_duplicate",  # Dash 3.x exige c/ allow_duplicate (adaptação IM-05)
    )
    def update_export_docx_disabled(stored_data):
        """Habilita/desabilita item DOCX baseado em estrutura do store (SP-02).

        Emite log L1 (INFO) na 1ª detecção de None na sessão; L2 (WARNING) em toda
        detecção de estrutura inválida.
        """
        global _log_l1_emitido

        if stored_data is None:
            if not _log_l1_emitido:
                logger.info(
                    "Botão Exportar DOCX desabilitado: store-indicator-filters ainda não populado"
                )
                _log_l1_emitido = True
            return True

        if not _store_estrutura_valida(stored_data):
            chaves_presentes = sorted(stored_data.keys()) if isinstance(stored_data, dict) else "n/a"
            logger.warning(
                "Botão Exportar DOCX desabilitado: store-indicator-filters com estrutura inválida — chaves esperadas: %s; recebido: %s",
                list(_CHAVES_OBRIGATORIAS), chaves_presentes,
            )
            return True

        return False
