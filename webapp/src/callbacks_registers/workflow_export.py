"""
Rota Flask para exportação de PDF do módulo Workflow via WeasyPrint.

WeasyPrint renderiza o HTML server-side respeitando @page { size: A4 landscape }
de forma 100% confiável — independente das configurações do browser do usuário.

CSS é inlinado a partir dos arquivos do disco antes de passar para WeasyPrint,
pois em produção (Docker) o WeasyPrint não consegue fazer requisições HTTP para
buscar arquivos CSS via <link> tags com URLs relativas ao host (problema de rede
entre o processo WeasyPrint e o servidor gunicorn rodando na mesma imagem).
"""

import io
import logging
import os
import re

from flask import request, send_file
from flask_login import login_required

logger = logging.getLogger(__name__)

# Diretório de assets relativo a este arquivo: src/callbacks_registers → src/assets
_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')


def _inline_css(html_content):
    """Substitui <link rel="stylesheet"> por blocos <style> com CSS inlinado do disco.

    WeasyPrint server-side não consegue resolver URLs http://localhost:... dentro de
    containers Docker. Inlinear garante que Bootstrap e estilos customizados sejam
    aplicados independente do ambiente de execução.

    Extrai o caminho relativo após '/assets/' da URL de cada link, lê o arquivo do
    disco e insere o conteúdo dentro de <style>. Links que não existem no disco
    são removidos silenciosamente (sem quebrar o HTML restante).
    """
    def _replace_link(match):
        href_match = re.search(r'href=["\']([^"\']+)["\']', match.group(0))
        if not href_match:
            return ''
        url = href_match.group(1)
        # Extrai caminho relativo após '/assets/'
        parts = url.split('/assets/', 1)
        if len(parts) < 2:
            return ''
        rel_path = parts[1].split('?')[0]       # descarta query string
        filepath = os.path.join(_ASSETS_DIR, *rel_path.split('/'))
        if not os.path.exists(filepath):
            logger.debug("CSS não encontrado no disco: %s", filepath)
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


def register_workflow_export_routes(server):
    """Registra rota Flask POST /workflow/export-pdf."""

    @server.route('/workflow/export-pdf', methods=['POST'])
    @login_required
    def export_workflow_pdf():
        """Recebe HTML do cliente, gera PDF A4 paisagem e retorna para download."""
        try:
            import weasyprint
        except ImportError:
            logger.error("WeasyPrint não instalado. Execute: pip install weasyprint")
            return "WeasyPrint não instalado no servidor.", 500

        try:
            html_content = request.get_data(as_text=True)
            if not html_content:
                return "Conteúdo HTML vazio.", 400

            # Inlinear CSS antes do WeasyPrint processar (resolve problema de rede em Docker)
            html_content = _inline_css(html_content)

            # base_url aponta para o diretório de assets como file:// para que URLs
            # relativas dentro do CSS inlinado (ex: @font-face em FontAwesome) resolvam
            assets_url = 'file:///' + _ASSETS_DIR.replace('\\', '/').lstrip('/') + '/'

            pdf_bytes = weasyprint.HTML(
                string=html_content,
                base_url=assets_url,
            ).write_pdf()

            return send_file(
                io.BytesIO(pdf_bytes),
                mimetype='application/pdf',
                as_attachment=True,
                download_name='relatorio-demandas.pdf',
            )

        except Exception:
            logger.exception("Erro ao gerar PDF do workflow")
            return "Erro interno ao gerar PDF.", 500
