"""
Autenticação do zpp-processor.

Chamadas server-side do webapp usam shared secret + headers.
Chamadas diretas do browser (futuro) usariam relay de cookie.
"""
import logging
import os

logger = logging.getLogger(__name__)

# Secret compartilhado entre webapp e zpp-processor
INTERNAL_SECRET = os.getenv("ZPP_INTERNAL_SECRET", "")


def validate_internal_headers(headers, min_level: int) -> tuple[bool, dict | None]:
    """
    Valida chamada interna originada do webapp via headers.
    Retorna (True, user_info) se secret correto e nível suficiente.
    """
    if not INTERNAL_SECRET:
        logger.warning("[auth] ZPP_INTERNAL_SECRET não configurado — chamadas internas bloqueadas")
        return False, None

    secret = headers.get("X-ZPP-Secret", "")
    if secret != INTERNAL_SECRET:
        return False, None

    try:
        level = int(headers.get("X-ZPP-Level", "0"))
    except ValueError:
        return False, None

    if level < min_level:
        return False, None

    return True, {
        "username": headers.get("X-ZPP-User", "desconhecido"),
        "level": level,
    }
