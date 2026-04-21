"""Views de geração de PDF para suprimentos de fundos."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from commons.shared.pdf_tools import gerar_documento_pdf
from commons.shared.pdf_response import montar_resposta_pdf
from suprimentos.models import SuprimentoDeFundos
from suprimentos.pdf_generators import SUPRIMENTOS_DOCUMENT_REGISTRY


@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
@xframe_options_sameorigin
def gerar_relatorio_prestacao_contas_view(request, pk):
    """Gera o PDF do relatório de prestação de contas do suprimento de fundos."""
    suprimento = get_object_or_404(SuprimentoDeFundos, pk=pk)
    pdf_bytes = gerar_documento_pdf("relatorio_prestacao_contas", suprimento, SUPRIMENTOS_DOCUMENT_REGISTRY)
    nome_arquivo = f"Relatorio_Prestacao_Contas_Suprimento_{suprimento.pk}.pdf"
    return montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=True)


__all__ = ["gerar_relatorio_prestacao_contas_view"]
