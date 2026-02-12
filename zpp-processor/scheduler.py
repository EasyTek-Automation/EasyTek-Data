"""
Sistema de agendamento automático para processamento ZPP
Thread em background que verifica periodicamente se deve processar arquivos
"""
import threading
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pymongo import MongoClient
import config
from processor import ZPPProcessor
from models.processing_log import (
    generate_job_id,
    create_processing_log,
    update_processing_log
)

logger = logging.getLogger(__name__)


class ZPPScheduler:
    """
    Agendador automático de processamento ZPP
    Executa em thread separada, consultando configurações no MongoDB
    """

    def __init__(self, mongo_uri: str, db_name: str):
        """
        Inicializa o agendador

        Args:
            mongo_uri: URI MongoDB
            db_name: Nome do banco
        """
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_run: Optional[datetime] = None

        # Conectar ao MongoDB para consultar configurações
        try:
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.db = self.client[db_name]
            logger.info("[Scheduler] Conectado ao MongoDB")
        except Exception as e:
            logger.error(f"[Scheduler] Erro ao conectar: {e}")
            raise

    def get_config(self) -> dict:
        """
        Busca configuração atual do MongoDB

        Returns:
            Dicionário de configuração
        """
        try:
            config_doc = self.db[config.CONFIG_COLLECTION].find_one({"_id": "global"})

            if not config_doc:
                # Criar configuração padrão se não existir
                from models.processing_log import create_default_config
                default_config = create_default_config()
                self.db[config.CONFIG_COLLECTION].insert_one(default_config)
                config_doc = default_config

            return config_doc

        except Exception as e:
            logger.error(f"[Scheduler] Erro ao buscar config: {e}")
            # Retornar configuração padrão em caso de erro
            return {
                "auto_process": config.AUTO_PROCESS,
                "interval_minutes": config.INTERVAL_MINUTES
            }

    def should_run(self) -> bool:
        """
        Verifica se deve executar processamento

        Returns:
            True se deve executar
        """
        cfg = self.get_config()

        # Verificar se auto-process está ativado
        if not cfg.get("auto_process", False):
            return False

        # Verificar intervalo desde última execução
        interval_minutes = cfg.get("interval_minutes", 60)

        if self.last_run is None:
            return True

        time_since_last = datetime.now() - self.last_run
        if time_since_last >= timedelta(minutes=interval_minutes):
            return True

        return False

    def run_processing(self):
        """
        Executa processamento automático
        """
        job_id = generate_job_id()

        logger.info(f"\n{'='*80}")
        logger.info(f"[Scheduler] Processamento Automático Iniciado")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"{'='*80}\n")

        # Criar log inicial
        log_doc = create_processing_log(
            job_id=job_id,
            trigger_type="automatic",
            triggered_by="system"
        )

        try:
            # Inserir log inicial
            self.db[config.LOGS_COLLECTION].insert_one(log_doc)

            # Inicializar processador
            processor = ZPPProcessor(
                mongo_uri=self.mongo_uri,
                db_name=self.db_name,
                archive_dir=config.OUTPUT_DIR
            )

            # Processar diretório
            results = processor.process_directory(
                directory=config.INPUT_DIR,
                batch_size=config.BATCH_SIZE,
                move_after_process=True
            )

            # Fechar processador
            processor.close()

            # Atualizar log
            log_update = update_processing_log(
                current_log=log_doc,
                files_processed=results,
                status="success" if results else "failed",
                error_message=None if results else "Nenhum arquivo encontrado"
            )

            self.db[config.LOGS_COLLECTION].update_one(
                {"job_id": job_id},
                {"$set": log_update}
            )

            # Atualizar timestamp de última execução
            self.last_run = datetime.now()

            logger.info(f"\n[Scheduler] Processamento concluído: {len(results)} arquivo(s)")

        except Exception as e:
            logger.error(f"[Scheduler] Erro no processamento: {e}")

            # Atualizar log com erro
            self.db[config.LOGS_COLLECTION].update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "failed",
                    "completed_at": datetime.now(),
                    "error_message": str(e)
                }}
            )

    def scheduler_loop(self):
        """
        Loop principal do agendador
        Executa a cada 1 minuto verificando se deve processar
        """
        logger.info("[Scheduler] Thread iniciada")

        while self.running:
            try:
                if self.should_run():
                    self.run_processing()

                # Aguardar 1 minuto antes de próxima verificação
                time.sleep(60)

            except Exception as e:
                logger.error(f"[Scheduler] Erro no loop: {e}")
                time.sleep(60)  # Continuar após erro

        logger.info("[Scheduler] Thread encerrada")

    def start(self):
        """Inicia a thread do agendador"""
        if self.running:
            logger.warning("[Scheduler] Já está rodando")
            return

        self.running = True
        self.thread = threading.Thread(target=self.scheduler_loop, daemon=True)
        self.thread.start()
        logger.info("[Scheduler] Iniciado")

    def stop(self):
        """Para a thread do agendador"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("[Scheduler] Parado")

    def close(self):
        """Fecha conexão MongoDB"""
        self.client.close()
