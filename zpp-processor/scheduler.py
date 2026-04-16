"""
Scheduler de processamento automático ZPP (canal padrão).
Monitora /data/input e processa arquivos encontrados a cada intervalo configurado.
"""
import logging
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pymongo import MongoClient

import config
from cleaner import find_excel_files
from pipeline import process_file

logger = logging.getLogger(__name__)

_BRT = ZoneInfo("America/Sao_Paulo")


def _move_file(src: Path, dest_dir: Path, suffix: str = "") -> Path:
    """Move arquivo com timestamp BRT no nome."""
    ts = datetime.now(tz=_BRT).strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"{src.stem}_{ts}{suffix}{src.suffix}"
    shutil.move(str(src), str(dest))
    return dest


class ZPPScheduler:
    """
    Executa processamento automático em thread daemon.
    Mantém contagem de tentativas por arquivo em memória.
    Reinício do serviço zera contadores — comportamento intencional (SP-08).
    """

    MAX_RETRIES = 3

    def __init__(self, mongo_uri: str, db_name: str):
        self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        self._db_name = db_name
        self._retry_counts: dict[str, int] = {}
        self.running = False
        self._thread: threading.Thread | None = None

    def _insert_log(self, result) -> None:
        try:
            self._client[self._db_name][config.LOGS_COLLECTION].insert_one(
                result.to_log_doc()
            )
        except Exception as e:
            logger.error(f"[scheduler] Falha ao inserir log no MongoDB: {e}")

    def _run_cycle(self) -> None:
        files = find_excel_files(str(config.INPUT_DIR))
        if not files:
            return

        logger.info(f"[scheduler] {len(files)} arquivo(s) encontrado(s)")

        for file_path in files:
            nome = file_path.name
            tentativas = self._retry_counts.get(nome, 0)

            result = process_file(
                file_path=file_path,
                client=self._client,
                canal="padrao",
                operador="sistema",
            )

            if result.status == "success":
                dest = _move_file(file_path, config.OUTPUT_DIR)
                logger.info(f"[scheduler] {nome} → output/{dest.name}")
                self._retry_counts.pop(nome, None)
                self._insert_log(result)

            elif result.status == "rejected":
                dest = _move_file(file_path, config.REJECTED_DIR, "_Rejected")
                logger.error(f"[scheduler] {nome} rejeitado → rejected/{dest.name}")
                self._retry_counts.pop(nome, None)
                self._insert_log(result)

            else:  # failed
                tentativas += 1
                self._retry_counts[nome] = tentativas
                logger.error(
                    f"[scheduler] {nome} erro interno "
                    f"(tentativa {tentativas}/{self.MAX_RETRIES})"
                )
                self._insert_log(result)

                if tentativas >= self.MAX_RETRIES:
                    dest = _move_file(file_path, config.REJECTED_DIR, "_InternalError")
                    logger.error(f"[scheduler] {nome} → rejected/{dest.name} (3 tentativas)")
                    self._retry_counts.pop(nome, None)

    def _loop(self) -> None:
        logger.info("[scheduler] Thread iniciada")
        while self.running:
            try:
                self._run_cycle()
            except Exception as e:
                logger.error(f"[scheduler] Erro no ciclo: {e}")
            time.sleep(config.SCHEDULER_INTERVAL_SECONDS)
        logger.info("[scheduler] Thread encerrada")

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("[scheduler] Iniciado")

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)

    def close(self) -> None:
        self._client.close()
