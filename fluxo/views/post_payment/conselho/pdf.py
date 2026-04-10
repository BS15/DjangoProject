"""PDF views da etapa de conselho fiscal."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from fluxo.models import Processo
from fluxo.services.shared import gerar_resposta_pdf


@permission_required("fluxo.pode_auditar_conselho", raise_exception=True)
@xframe_options_sameorigin
def gerar_parecer_conselho_view(request, pk):
    """Gera e retorna o PDF de parecer do conselho para um processo."""
    processo = get_object_or_404(Processo, pk=pk)
    numero_reuniao = processo.reuniao_conselho.numero if processo.reuniao_conselho else None
    nome_arquivo = f"Parecer_Conselho_Fiscal_Proc_{processo.id}.pdf"
    return gerar_resposta_pdf(
        "conselho_fiscal",
        processo,
        nome_arquivo,
        inline=True,
        numero_reuniao=numero_reuniao,
    )


__all__ = ["gerar_parecer_conselho_view"]
