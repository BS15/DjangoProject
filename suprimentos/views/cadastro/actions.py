import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from suprimentos.forms import SuprimentoForm
from .actions import persistir_suprimento_com_processo

logger = logging.getLogger(__name__)

@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def add_suprimento_view(request: HttpRequest) -> HttpResponse:
    """Cria um suprimento e o processo financeiro vinculado."""
    form = SuprimentoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            persistir_suprimento_com_processo(form)
            messages.success(request, "Suprimento de Fundos cadastrado com sucesso!")
            return redirect("painel_suprimentos")
        except (ValidationError, DatabaseError, TypeError, ValueError):
            logger.exception("Erro ao cadastrar suprimento de fundos")
            messages.error(request, "Erro interno ao salvar suprimento. Tente novamente.")
    elif request.method == "POST":
        messages.error(request, "Verifique os erros no formulário.")

    return render(request, "suprimentos/add_suprimento.html", {"form": form})

__all__ = ["add_suprimento_view"]

# --- Business logic for suprimento creation below ---
from typing import Any
from django.db import transaction
from suprimentos.services.processo_integration import criar_processo_para_suprimento
from suprimentos.forms import SuprimentoForm
from suprimentos.models import StatusChoicesSuprimentoDeFundos


def persistir_suprimento_com_processo(form_suprimento: SuprimentoForm) -> Any:
    """Persiste suprimento e cria o processo financeiro vinculado em transação atômica."""
    with transaction.atomic():
        suprimento: Any = form_suprimento.save(commit=False)
        status_aberto, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(status_choice="ABERTO")
        suprimento.status = status_aberto
        suprimento.save()

        nome_lotacao = suprimento.lotacao or "Unidade Não Especificada"
        detalhamento = (
            f"Referente a suprimento de fundos da {nome_lotacao} "
            f"- mês {suprimento.data_saida.month}/{suprimento.data_saida.year}"
        )

        criar_processo_para_suprimento(suprimento, detalhamento)
        return suprimento


__all__ = ["persistir_suprimento_com_processo"]