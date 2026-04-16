"""
Validação de sessão via endpoint interno do webapp.
O zpp-processor não gerencia autenticação própria — delega ao webapp.
"""
import logging
import requests

import config

logger = logging.getLogger(__name__)


def validate_session(cookie: str, min_level: int) -> tuple[bool, dict | None]:
    """
    Valida cookie de sessão consultando o webapp.

    Retorna (True, user_info) se sessão válida e nível suficiente.
    Retorna (False, None) caso contrário.
    """
    try:
        resp = requests.get(
            f"{config.WEBAPP_INTERNAL_URL}/internal/validate-session",
            cookies={"session": cookie},
            timeout=5,
        )

        if resp.status_code != 200:
            return False, None

        data = resp.json()

        if not data.get("valid"):
            return False, None

        if data.get("level", 0) < min_level:
            return False, None

        return True, data

    except requests.RequestException as e:
        logger.error(f"[auth] Erro ao validar sessão com o webapp: {e}")
        return False, None
