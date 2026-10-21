# src/utils/email_sender.py

"""
Utilitário de envio de e-mail via SMTP.

Adaptado do script `enviar_email.py`, mas parametrizado pela config central
(`config/email_config.py`) e pronto para ser chamado de qualquer lugar do
webapp quando um evento ocorrer.

Uso típico (dispara no ponto onde o evento acontece):
    from src.utils.email_sender import send_email

    if avaria_detectada:
        send_email(
            assunto="[AMG] Avaria detectada",
            corpo=f"Equipamento {equip} parou às {hora}.",
        )

`send_email` NUNCA levanta exceção por padrão (retorna True/False e loga o erro),
para que uma falha de e-mail não derrube o fluxo do evento. Passe
`raise_on_error=True` se quiser tratar a exceção você mesmo.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config.email_config import get_email_config

logger = logging.getLogger(__name__)


def send_email(assunto: str, corpo: str, to: str | None = None,
               html: bool = False, raise_on_error: bool = False) -> bool:
    """
    Envia um e-mail usando as configurações de `email_config`.

    Args:
        assunto: linha de assunto.
        corpo: conteúdo da mensagem (texto puro; use html=True para HTML).
        to: destinatário; aceita vários separados por vírgula. Se None,
            usa EMAIL_TO_DEFAULT do ambiente.
        html: True envia o corpo como text/html em vez de text/plain.
        raise_on_error: True propaga a exceção; False (default) só loga e
            retorna False.

    Returns:
        True se o e-mail foi entregue ao servidor SMTP, False caso contrário
        (ou se o envio estiver desligado via EMAIL_ENABLED=0).
    """
    cfg = get_email_config()

    if not cfg.enabled:
        logger.info("Envio de e-mail desativado (EMAIL_ENABLED=0). Assunto: %s", assunto)
        return False

    destinatario = (to or cfg.default_to).strip()

    # Validação mínima para falhar cedo com mensagem clara.
    faltando = [nome for nome, val in
                (("SMTP_USER", cfg.user), ("SMTP_PASSWORD", cfg.password),
                 ("destinatário", destinatario)) if not val]
    if faltando:
        msg = f"Config de e-mail incompleta, faltando: {', '.join(faltando)}"
        if raise_on_error:
            raise ValueError(msg)
        logger.error(msg)
        return False

    mensagem = MIMEMultipart()
    mensagem["From"] = cfg.sender
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.attach(MIMEText(corpo, "html" if html else "plain", "utf-8"))

    try:
        logger.info("Enviando e-mail '%s' para %s via %s:%s",
                    assunto, destinatario, cfg.host, cfg.port)
        with smtplib.SMTP(cfg.host, cfg.port, timeout=30) as server:
            if cfg.use_tls:
                server.starttls()
            server.login(cfg.user, cfg.password)
            # send_message aceita múltiplos destinatários lidos do header "To".
            server.send_message(mensagem)
        logger.info("E-mail '%s' enviado com sucesso.", assunto)
        return True

    except Exception as e:  # noqa: BLE001 — falha de e-mail não deve quebrar o evento
        logger.error("Falha ao enviar e-mail '%s': %s", assunto, e)
        if raise_on_error:
            raise
        return False


def notificar_evento(evento: str, detalhes: str = "", to: str | None = None) -> bool:
    """
    Atalho para disparar um e-mail padronizado quando um evento ocorrer.

    Formata assunto/corpo num padrão único ("[AMG] <evento>") para que ligar
    uma notificação seja uma linha no ponto do evento:

        from src.utils.email_sender import notificar_evento
        notificar_evento("Avaria detectada", f"Equipamento {equip} parou.")

    Args:
        evento: nome curto do evento (vira o assunto).
        detalhes: texto adicional no corpo (opcional).
        to: destinatário; None usa EMAIL_TO_DEFAULT.

    Returns:
        True se enviado com sucesso, False caso contrário.
    """
    corpo = f"O evento '{evento}' ocorreu no AMG-Data."
    if detalhes:
        corpo += f"\n\nDetalhes:\n{detalhes}"
    return send_email(assunto=f"[AMG] {evento}", corpo=corpo, to=to)


def notificar_parada_gatilho(
    equipamento: str,
    duracao_min: float,
    inicio=None,
    causa: str | None = None,
    ordem: str | None = None,
    gatilho_min: int | None = None,
    to: str | None = None,
) -> bool:
    """
    Dispara e-mail quando uma parada atinge o gatilho de tempo do equipamento.

    Regra: envia SOMENTE se `duracao_min >= gatilho`. O gatilho vem de
    `gatilho_min` (se passado) ou do cadastro em `breakdown_thresholds`
    (`maintenance_breakdown_thresholds`) via `get_threshold(equipamento)`.

    É idempotente em relação à regra, mas NÃO faz dedupe entre chamadas — quem
    chama deve garantir que dispara uma vez por parada (ex.: só para registros
    novos/não notificados). Ver nota no ponto de integração.

    Args:
        equipamento: id/centro de trabalho da parada (ex.: "LCT08").
        duracao_min: duração da parada em minutos.
        inicio: datetime/str de início da parada (opcional, vai no corpo).
        causa: código/descrição da causa (opcional).
        ordem: nº da ordem SAP (opcional).
        gatilho_min: força o gatilho; se None, busca no cadastro.
        to: destinatário; None usa EMAIL_TO_DEFAULT.

    Returns:
        True se o e-mail foi enviado; False se não atingiu o gatilho ou falhou.
    """
    # Resolve o gatilho (parâmetro tem prioridade sobre o cadastro).
    if gatilho_min is None:
        try:
            from src.utils.breakdown_thresholds import get_threshold
            gatilho_min = get_threshold(equipamento)
        except Exception as e:  # noqa: BLE001
            logger.error("Não foi possível obter o gatilho de %s: %s", equipamento, e)
            return False

    if duracao_min < gatilho_min:
        return False  # ainda não atingiu o gatilho — não notifica

    linhas = [
        f"Equipamento: {equipamento}",
        f"Duração: {int(duracao_min)} min (gatilho: {gatilho_min} min)",
    ]
    if inicio is not None:
        linhas.append(f"Início: {inicio}")
    if causa:
        linhas.append(f"Causa: {causa}")
    if ordem:
        linhas.append(f"Ordem: {ordem}")

    return send_email(
        assunto=f"[AMG] Parada atingiu o gatilho — {equipamento}",
        corpo="Uma parada atingiu o gatilho de tempo configurado.\n\n" + "\n".join(linhas),
        to=to,
    )
