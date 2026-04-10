"""Views de leitura da etapa de prestacao de contas de suprimentos."""

from typing import Any

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from suprimentos.models import SuprimentoDeFundos
from ..helpers import _suprimento_encerrado


@require_GET
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def painel_suprimentos_view(request: HttpRequest) -> HttpResponse:
    """Exibe painel resumido com os suprimentos cadastrados."""
    suprimentos = SuprimentoDeFundos.objects.all().order_by("-id")
    return render(request, "suprimentos/suprimentos_list.html", {"suprimentos": suprimentos})


@require_GET
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def gerenciar_suprimento_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Exibe detalhes operacionais de um suprimento e suas despesas."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)
    despesas = suprimento.despesas.all().order_by("data", "id")

    context: dict[str, Any] = {
        "suprimento": suprimento,
        "despesas": despesas,
        "pode_editar": not _suprimento_encerrado(suprimento),
    }
    return render(request, "suprimentos/gerenciar_suprimento.html", context)


__all__ = ["painel_suprimentos_view", "gerenciar_suprimento_view"]
