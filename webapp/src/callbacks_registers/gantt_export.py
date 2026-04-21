"""
Rota Flask para exportação de PDF do módulo Planejamento Gantt via WeasyPrint.

Baseado no padrão estabelecido em workflow_export.py:
- CSS inlinado do disco (WeasyPrint não resolve HTTP dentro do container Docker)
- base_url file:// aponta para o diretório de assets (resolve @font-face etc.)
- Página A4 landscape definida no CSS inlinado pelo cliente (gantt_print.js)

O cliente (gantt_print.js) coleta os KPIs e o container do Gantt, monta
um HTML standalone com estilos print-friendly e faz POST desse HTML aqui.
"""

import io
import logging
import os
import re

from flask import request, send_file
from flask_login import login_required

logger = logging.getLogger(__name__)

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')


def _inline_css(html_content):
    """Substitui <link rel='stylesheet'> por <style> com CSS do disco inlinado.

    Mesmo problema resolvido no workflow_export: WeasyPrint no container
    não consegue fazer HTTP para localhost. Ler do disco e inlinear garante
    Bootstrap + estilos customizados aplicados em qualquer ambiente.
    """
    def _replace_link(match):
        href_match = re.search(r'href=["\']([^"\']+)["\']', match.group(0))
        if not href_match:
            return ''
        url = href_match.group(1)
        parts = url.split('/assets/', 1)
        if len(parts) < 2:
            return ''
        rel_path = parts[1].split('?')[0]
        filepath = os.path.join(_ASSETS_DIR, *rel_path.split('/'))
        if not os.path.exists(filepath):
            logger.debug("CSS não encontrado: %s", filepath)
            return ''
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                css = f.read()
            return f'<style>\n{css}\n</style>'
        except Exception:
            logger.warning("Falha ao ler CSS: %s", filepath, exc_info=True)
            return ''

    return re.sub(
        r'<link\b[^>]*\brel=["\']stylesheet["\'][^>]*/?>',
        _replace_link,
        html_content,
        flags=re.IGNORECASE,
    )


def register_gantt_export_routes(server):
    """Registra rota Flask POST /gantt/export-pdf."""

    @server.route('/gantt/export-pdf', methods=['POST'])
    @login_required
    def export_gantt_pdf():
        """Recebe HTML do cliente, gera PDF A4 paisagem, retorna para download."""
        try:
            import weasyprint
        except ImportError:
            logger.error("WeasyPrint não instalado.")
            return "WeasyPrint não instalado no servidor.", 500

        try:
            html_content = request.get_data(as_text=True)
            if not html_content:
                return "Conteúdo HTML vazio.", 400

            html_content = _inline_css(html_content)
            assets_url = 'file:///' + _ASSETS_DIR.replace('\\', '/').lstrip('/') + '/'

            pdf_bytes = weasyprint.HTML(
                string=html_content,
                base_url=assets_url,
            ).write_pdf()

            return send_file(
                io.BytesIO(pdf_bytes),
                mimetype='application/pdf',
                as_attachment=True,
                download_name='planejamento-gantt.pdf',
            )

        except Exception:
            logger.exception("Erro ao gerar PDF do Gantt")
            return "Erro interno ao gerar PDF.", 500
