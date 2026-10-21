# -*- coding: utf-8 -*-
"""Rota Flask que serve os desenhos preparados do Monitoramento de Ativos.

Por que o desenho não vai embutido no layout: injetar SVG por `dcc.Markdown` **não
funciona** para um desenho inteiro — o renderizador de Markdown reprocessa o HTML e achata
as tags do SVG (o `<svg>` raiz some, `feDropShadow` vira `fedropshadow`, o `<style>` é
descartado), e o que chega à tela não é desenho nenhum. Servido como arquivo, o navegador
usa o próprio parser e o SVG chega íntegro — e ainda ganha cache entre visitas, em vez de
viajar ~140 KB no payload de cada página.

Segurança: o nome do arquivo nunca vem cru do cliente. Só os desenhos conhecidos são
servíveis, e a rota exige login e o mesmo acesso da página.
"""
from flask import abort, send_file
from flask_login import current_user

from src.components.monitoring import svg_registry
from src.utils.permissions import check_access

ROTA = "/maintenance/monitoramento-ativos"
PREFIXO = "/monitoring/art"

DESENHOS = {"planta.svg", "linha_prensa.svg", "linhas_corte.svg", "linha_lwb.svg"}


def register_monitoring_routes(server):
    """Registra a rota de arte no servidor Flask do webapp."""

    @server.route(f"{PREFIXO}/<arquivo>")
    def monitoring_art(arquivo):
        if not getattr(current_user, "is_authenticated", False):
            abort(401)
        permitido, _ = check_access(current_user, ROTA)
        if not permitido:
            abort(403)
        if arquivo not in DESENHOS:
            abort(404)

        caminho = svg_registry.PREPARADO / arquivo
        if not caminho.is_file():
            abort(404)
        return send_file(caminho, mimetype="image/svg+xml")
