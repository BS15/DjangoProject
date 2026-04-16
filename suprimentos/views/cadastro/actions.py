import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from suprimentos.forms import SuprimentoForm
from suprimentos.models import StatusChoicesSuprimentoDeFundos
from suprimentos.services.processo_integration import criar_processo_para_suprimento

logger = logging.getLogger(__name__)


def _persistir_suprimento_com_processo(form_suprimento: SuprimentoForm) -> Any:
    """Persiste suprimento e cria o processo financeiro vinculado em transação atômica."""
    with transaction.atomic():
        suprimento: Any = form_suprimento.save(commit=False)
        status_aberto, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(status_choice="ABERTO")
        suprimento.status = status_aberto
        suprimento.save()

        nome_lotacao = suprimento.lotacao or "Unidade Não Especificada"
        detalhamento = (
            f"Referente a suprimento de fundos da {nome_lotacao} "
            f"- mês {suprimento.inicio_periodo.month}/{suprimento.inicio_periodo.year}"
        )

        criar_processo_para_suprimento(suprimento, detalhamento)
        return suprimento


@require_POST
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def add_suprimento_action(request: HttpRequest) -> HttpResponse:
    """Cria um suprimento e o processo financeiro vinculado."""
    form = SuprimentoForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Verifique os erros no formulário.")
        return redirect("add_suprimento_view")

    try:
        _persistir_suprimento_com_processo(form)
        messages.success(request, "Suprimento de Fundos cadastrado com sucesso!")
    except (ValidationError, DatabaseError, TypeError, ValueError):
        logger.exception("Erro ao cadastrar suprimento de fundos")
        messages.error(request, "Erro interno ao salvar suprimento. Tente novamente.")

    return redirect("suprimentos_list")


__all__ = ["add_suprimento_action"]