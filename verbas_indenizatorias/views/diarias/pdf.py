"""Views de geração de PDF para diárias."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from commons.shared.pdf_tools import gerar_documento_pdf
from commons.shared.pdf_response import montar_resposta_pdf
from verbas_indenizatorias.models import Diaria
from verbas_indenizatorias.pdf_generators import VERBAS_DOCUMENT_REGISTRY


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
@xframe_options_sameorigin
def gerar_pcd_view(request, pk):
    """Gera e exibe o PDF da Proposta de Concessão de Diárias (PCD)."""
    diaria = get_object_or_404(Diaria, pk=pk)
    pdf_bytes = gerar_documento_pdf("pcd", diaria, VERBAS_DOCUMENT_REGISTRY)
    nome_arquivo = f"PCD_Diaria_{diaria.pk}.pdf"
    return montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=True)


__all__ = ["gerar_pcd_view"]
