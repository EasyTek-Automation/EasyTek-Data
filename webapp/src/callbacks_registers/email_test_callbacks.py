# src/callbacks_registers/email_test_callbacks.py

"""
Callback do botão 'Testar e-mail' no header.

Ao clicar em `btn-test-email`, dispara um e-mail de teste via
`utils.email_sender.notificar_evento` e mostra o resultado no toast
`email-test-toast`. Serve para validar a configuração SMTP sem depender
de nenhum evento real do sistema.
"""

from dash.dependencies import Input, Output

from src.utils.email_sender import notificar_evento


def register_email_test_callbacks(app):
    """Registra o callback que envia um e-mail de teste ao clicar no botão do header."""

    @app.callback(
        Output("email-test-toast", "is_open"),
        Output("email-test-toast", "children"),
        Output("email-test-toast", "icon"),
        Input("btn-test-email", "n_clicks"),
        prevent_initial_call=True,
    )
    def enviar_email_teste(n_clicks):
        """Dispara o e-mail de teste e devolve (abrir_toast, mensagem, cor)."""
        ok = notificar_evento(
            "Teste de e-mail",
            "Disparo manual pelo botão do header para validar a configuração SMTP.",
        )
        if ok:
            return True, "E-mail de teste enviado com sucesso.", "success"
        return (
            True,
            "Falha ao enviar. Confira SMTP_USER / SMTP_PASSWORD / "
            "EMAIL_TO_DEFAULT e os logs do webapp.",
            "danger",
        )
