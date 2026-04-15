"""Painéis GET da etapa de cadastro de suprimentos."""

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from suprimentos.forms import SuprimentoForm


@require_GET
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def add_suprimento_view(request: HttpRequest) -> HttpResponse:
    """Renderiza o formulário de criação de suprimento."""
    return render(request, "suprimentos/add_suprimento.html", {"form": SuprimentoForm()})


__all__ = ["add_suprimento_view"]