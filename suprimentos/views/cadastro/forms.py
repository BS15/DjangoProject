"""Views de formulario da etapa de cadastro de suprimentos."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from suprimentos.forms import SuprimentoForm
from ..helpers import _persistir_suprimento_com_processo


logger = logging.getLogger(__name__)


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def add_suprimento_view(request: HttpRequest) -> HttpResponse:
    """Cria um suprimento e o processo financeiro vinculado."""
    form = SuprimentoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            _persistir_suprimento_com_processo(form)
            messages.success(request, "Suprimento de Fundos cadastrado com sucesso!")
            return redirect("painel_suprimentos")
        except (ValidationError, DatabaseError, TypeError, ValueError):
            logger.exception("Erro ao cadastrar suprimento de fundos")
            messages.error(request, "Erro interno ao salvar suprimento. Tente novamente.")
    elif request.method == "POST":
        messages.error(request, "Verifique os erros no formulário.")

    return render(request, "suprimentos/add_suprimento.html", {"form": form})


__all__ = ["add_suprimento_view"]
