"""Views de formulario da etapa de cadastro de suprimentos."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ....forms import SuprimentoForm
from ..helpers import _persistir_suprimento_com_processo


@permission_required("processos.acesso_backoffice", raise_exception=True)
def add_suprimento_view(request: HttpRequest) -> HttpResponse:
    """Cria um suprimento e o processo financeiro vinculado."""
    form = SuprimentoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            _persistir_suprimento_com_processo(form)
            messages.success(request, "Suprimento de Fundos cadastrado com sucesso!")
            return redirect("painel_suprimentos")
        except Exception as exc:
            messages.error(request, f"Erro interno ao salvar: {exc}")
    elif request.method == "POST":
        messages.error(request, "Verifique os erros no formulário.")

    return render(request, "suprimentos/add_suprimento.html", {"form": form})


__all__ = ["add_suprimento_view"]
