"""Panel views for tax retention management."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render

from fiscal.filters import RetencaoIndividualFilter
from fiscal.models import RetencaoImposto
from fluxo.views.shared import apply_filterset


@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def painel_impostos_view(request):
    """Hub de gestão fiscal com retenções individuais filtráveis."""
    queryset_base = RetencaoImposto.objects.select_related(
        "codigo",
        "status",
        "nota_fiscal",
        "nota_fiscal__nome_emitente",
        "beneficiario",
    ).order_by("-id")
    filtro = apply_filterset(request, RetencaoIndividualFilter, queryset_base)
    retencoes = filtro.qs

    context = {
        "filter": filtro,
        "retencoes": retencoes,
    }
    return render(request, "fiscal/painel_impostos.html", context)


@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def painel_impostos(request):
    """Alias legado para compatibilidade de rota."""
    return painel_impostos_view(request)
