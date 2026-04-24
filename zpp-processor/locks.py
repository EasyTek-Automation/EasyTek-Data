"""
Lock em memória por tipo de planilha.
Garante que apenas um processamento por tipo esteja ativo por vez.
Seguro com --workers 1 (processo único, sem necessidade de Redis/Mongo).
"""
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_lock: dict[str, bool] = {
    "zppprd":     False,
    "zppparadas": False,
}


def is_locked(tipo: str) -> bool:
    return _lock.get(tipo, False)


@contextmanager
def acquire_lock(tipo: str):
    """
    Adquire lock para o tipo informado.
    Lança LockActiveError se já houver processamento em andamento.
    Libera o lock via finally — nunca deixa travado após exceção.
    """
    if _lock[tipo]:
        raise LockActiveError(tipo)
    _lock[tipo] = True
    logger.info(f"[lock] Adquirido para {tipo}")
    try:
        yield
    finally:
        _lock[tipo] = False
        logger.info(f"[lock] Liberado para {tipo}")


class LockActiveError(Exception):
    def __init__(self, tipo: str):
        self.tipo = tipo
        super().__init__(
            f"Processamento rejeitado: já existe um processamento de {tipo} em andamento. "
            "Tente novamente em instantes."
        )
