"""Views centrais de suporte: página inicial e detalhe de processo."""

from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from pagamentos.domain_models import Processo
from pagamentos.filters import ProcessoFilter
from fiscal.models import DocumentoFiscal, RetencaoImposto


@permission_required("pagamentos.pode_visualizar_processos_pagamento", raise_exception=True)
def home_page(request):
    """Painel principal com listagem filtrada de processos."""
    meu_filtro = ProcessoFilter(request.GET, queryset=Processo.objects.select_related(
        "status", "credor"
    ).order_by("-id"))
    return render(request, "pagamentos/home.html", {
        "meu_filtro": meu_filtro,
        "lista_processos": meu_filtro.qs,
    })


@permission_required("pagamentos.pode_visualizar_processos_pagamento", raise_exception=True)
def process_detail_view(request, pk):
    """Exibe o detalhe completo de um processo e seus vínculos."""
    processo = get_object_or_404(Processo, id=pk)
    documentos_qs = processo.documentos.select_related("tipo").all().order_by("ordem", "id")
    pendencias_qs = processo.pendencias.select_related("tipo", "status").all().order_by("id")
    liquidacoes_qs = DocumentoFiscal.objects.select_related("nome_emitente", "fiscal_contrato").filter(
        processo=processo
    ).order_by("-data_emissao", "-id")
    retencoes_qs = RetencaoImposto.objects.select_related(
        "nota_fiscal",
        "codigo",
        "status",
        "beneficiario",
    ).filter(nota_fiscal__processo=processo).order_by("-data_pagamento", "-id")

    documentos_page = Paginator(documentos_qs, 8).get_page(request.GET.get("docs_page"))
    pendencias_page = Paginator(pendencias_qs, 8).get_page(request.GET.get("pend_page"))
    liquidacoes_page = Paginator(liquidacoes_qs, 8).get_page(request.GET.get("liq_page"))
    retencoes_page = Paginator(retencoes_qs, 8).get_page(request.GET.get("ret_page"))

    return render(request, "pagamentos/process_detail.html", {
        "processo": processo,
        "documentos_page": documentos_page,
        "pendencias_page": pendencias_page,
        "liquidacoes_page": liquidacoes_page,
        "retencoes_page": retencoes_page,
    })


__all__ = ["home_page", "process_detail_view"]
