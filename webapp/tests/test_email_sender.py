"""Testes do utilitário de envio de e-mail (utils/email_sender.py).

Mocka smtplib.SMTP — nenhum e-mail real é enviado.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.utils.email_sender import send_email, notificar_evento

# Ambiente mínimo válido para os testes.
ENV_OK = {
    "EMAIL_ENABLED": "1",
    "SMTP_HOST": "smtp.exemplo.com",
    "SMTP_PORT": "587",
    "SMTP_USE_TLS": "1",
    "SMTP_USER": "remetente@exemplo.com",
    "SMTP_PASSWORD": "senha-de-app",
    "EMAIL_TO_DEFAULT": "destino@exemplo.com",
}


def _fake_smtp():
    """Retorna (patch_target, mock_server) para usar como context manager SMTP."""
    server = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = server
    return ctx, server


def test_send_email_sucesso():
    """Envia e-mail com config válida: faz login, starttls e send_message."""
    ctx, server = _fake_smtp()
    with patch.dict("os.environ", ENV_OK, clear=True), \
         patch("smtplib.SMTP", return_value=ctx) as smtp_cls:
        ok = send_email("Assunto", "Corpo")

    assert ok is True
    smtp_cls.assert_called_once_with("smtp.exemplo.com", 587, timeout=30)
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("remetente@exemplo.com", "senha-de-app")
    server.send_message.assert_called_once()


def test_send_email_desativado():
    """EMAIL_ENABLED=0 não tenta conectar e retorna False."""
    env = {**ENV_OK, "EMAIL_ENABLED": "0"}
    with patch.dict("os.environ", env, clear=True), \
         patch("smtplib.SMTP") as smtp_cls:
        ok = send_email("Assunto", "Corpo")

    assert ok is False
    smtp_cls.assert_not_called()


def test_send_email_config_incompleta_retorna_false():
    """Sem SMTP_PASSWORD não envia e não levanta (raise_on_error=False)."""
    env = {**ENV_OK}
    del env["SMTP_PASSWORD"]
    with patch.dict("os.environ", env, clear=True), \
         patch("smtplib.SMTP") as smtp_cls:
        ok = send_email("Assunto", "Corpo")

    assert ok is False
    smtp_cls.assert_not_called()


def test_send_email_usa_destino_explicito():
    """`to` explícito sobrescreve EMAIL_TO_DEFAULT no header."""
    ctx, server = _fake_smtp()
    with patch.dict("os.environ", ENV_OK, clear=True), \
         patch("smtplib.SMTP", return_value=ctx):
        send_email("Assunto", "Corpo", to="outro@exemplo.com")

    enviado = server.send_message.call_args[0][0]
    assert enviado["To"] == "outro@exemplo.com"


def test_notificar_evento_formata_assunto():
    """notificar_evento prefixa '[AMG]' e inclui detalhes no corpo."""
    ctx, server = _fake_smtp()
    with patch.dict("os.environ", ENV_OK, clear=True), \
         patch("smtplib.SMTP", return_value=ctx):
        ok = notificar_evento("Avaria detectada", "Equipamento LCT08 parou.")

    assert ok is True
    enviado = server.send_message.call_args[0][0]
    assert enviado["Subject"] == "[AMG] Avaria detectada"
