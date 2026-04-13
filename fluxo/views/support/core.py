"""Views centrais de suporte: página inicial e detalhe de processo."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render

from fluxo.domain_models import Processo
from fluxo.filters import ProcessoFilter


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def home_page(request):
    """Painel principal com listagem filtrada de processos."""
    meu_filtro = ProcessoFilter(request.GET, queryset=Processo.objects.select_related(
        "status", "credor"
    ).order_by("-id"))
    return render(request, "fluxo/home.html", {
        "meu_filtro": meu_filtro,
        "lista_processos": meu_filtro.qs,
    })


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def process_detail_view(request, pk):
    """Exibe o detalhe completo de um processo e seus vínculos."""
    processo = get_object_or_404(Processo, id=pk)
    documentos = processo.documentos.all().order_by("ordem")
    notas_fiscais = processo.notas_fiscais.all().order_by("id")
    pendencias = processo.pendencias.select_related("tipo", "status").order_by("id")
    return render(request, "fluxo/process_detail.html", {
        "processo": processo,
        "documentos": documentos,
        "notas_fiscais": notas_fiscais,
        "pendencias": pendencias,
    })


__all__ = ["home_page", "process_detail_view"]
