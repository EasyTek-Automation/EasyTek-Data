# src/config/email_config.py

"""
Configuração central de envio de e-mail (SMTP).

Tudo é lido de variáveis de ambiente (mesmo padrão de docs_config/logging_config),
então para mudar servidor, credenciais ou destinatário basta editar o `.env` —
sem tocar no código. Os defaults abaixo apontam para o Gmail via STARTTLS.

Variáveis (definir em environments/<env>/.env ou .env.common):
    EMAIL_ENABLED      "1" liga o envio, "0" desliga (default "1")
    SMTP_HOST          servidor SMTP            (default smtp.gmail.com)
    SMTP_PORT          porta SMTP               (default 587)
    SMTP_USE_TLS       "1" usa STARTTLS         (default "1")
    SMTP_USER          usuário/e-mail de login  (também vira o "From")
    SMTP_PASSWORD      senha de app / SMTP      (NUNCA commitar valor real)
    EMAIL_FROM         remetente exibido        (default = SMTP_USER)
    EMAIL_TO_DEFAULT   destinatário padrão      (usado quando não passar `to`)
"""

import os
from dataclasses import dataclass


def _as_bool(value: str, default: bool = True) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on", "sim")


@dataclass(frozen=True)
class EmailConfig:
    enabled: bool
    host: str
    port: int
    use_tls: bool
    user: str
    password: str
    sender: str
    default_to: str


def get_email_config() -> EmailConfig:
    """Lê as variáveis de ambiente e devolve um EmailConfig.

    SEM segredos hardcoded: credenciais e destinatário vêm exclusivamente do
    ambiente (injetado via `.env` do AMG-Infra / `.env.standalone`). Apenas os
    defaults NÃO-secretos do Gmail (host/porta/TLS) ficam no código.

    Se `SMTP_PASSWORD` (ou usuário/destino) estiver ausente, `send_email` valida
    antes de conectar e retorna um erro CLARO de config — não um erro de auth
    do SMTP. Isso evita o problema de "fallback velho após revogar a senha".
    """
    user = os.getenv("SMTP_USER", "").strip()
    return EmailConfig(
        enabled=_as_bool(os.getenv("EMAIL_ENABLED"), default=True),
        host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
        port=int(os.getenv("SMTP_PORT", "587")),
        use_tls=_as_bool(os.getenv("SMTP_USE_TLS"), default=True),
        user=user,
        password=os.getenv("SMTP_PASSWORD", ""),
        sender=os.getenv("EMAIL_FROM", "").strip() or user,
        default_to=os.getenv("EMAIL_TO_DEFAULT", "").strip(),
    )
