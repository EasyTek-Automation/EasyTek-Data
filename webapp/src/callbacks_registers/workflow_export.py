"""
Rota Flask para exportação de PDF do módulo Workflow via WeasyPrint.

WeasyPrint renderiza o HTML server-side respeitando @page { size: A4 landscape }
de forma 100% confiável — independente das configurações do browser do usuário.
"""

import io
import logging

from flask import request, send_file
from flask_login import login_required

logger = logging.getLogger(__name__)


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

            pdf_bytes = weasyprint.HTML(
                string=html_content,
                base_url=request.host_url,
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
