"""Views de leitura da etapa de prestacao de contas de suprimentos."""

from typing import Any

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from suprimentos.models import SuprimentoDeFundos
from ..helpers import _suprimento_encerrado
from suprimentos.forms import DespesaSuprimentoForm


@require_GET
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def painel_suprimentos_view(request: HttpRequest) -> HttpResponse:
    """Exibe painel resumido com os suprimentos cadastrados."""
    suprimentos = SuprimentoDeFundos.objects.all().order_by("-id")
    return render(request, "suprimentos/suprimentos_list.html", {"suprimentos": suprimentos})


@require_GET
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def gerenciar_suprimento_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Exibe detalhes operacionais read-only de um suprimento e suas despesas."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)
    despesas = suprimento.despesas.all().order_by("data", "id")

    context: dict[str, Any] = {
        "suprimento": suprimento,
        "despesas": despesas,
        "pode_editar": not _suprimento_encerrado(suprimento),
    }
    return render(request, "suprimentos/gerenciar_suprimento.html", context)


@require_GET
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def adicionar_despesa_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Exibe spoke dedicada para registro de nova despesa de suprimento."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)
    if _suprimento_encerrado(suprimento):
        return render(
            request,
            "suprimentos/add_despesa_suprimento.html",
            {
                "suprimento": suprimento,
                "pode_editar": False,
                "form": DespesaSuprimentoForm(),
            },
        )

    return render(
        request,
        "suprimentos/add_despesa_suprimento.html",
        {
            "suprimento": suprimento,
            "pode_editar": True,
            "form": DespesaSuprimentoForm(),
        },
    )


__all__ = ["painel_suprimentos_view", "gerenciar_suprimento_view", "adicionar_despesa_view"]
