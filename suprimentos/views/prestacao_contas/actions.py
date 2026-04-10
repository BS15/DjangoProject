"""Views de acoes da etapa de prestacao de contas de suprimentos."""

from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from suprimentos.models import SuprimentoDeFundos
from ..helpers import _atualizar_status_apos_fechamento, _salvar_despesa_manual, _suprimento_encerrado


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
@require_POST
def adicionar_despesa_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Registra manualmente uma despesa de suprimento a partir de dados do POST."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)

    if _suprimento_encerrado(suprimento):
        messages.error(request, "Este suprimento já foi encerrado e não pode receber novas despesas.")
        return redirect("gerenciar_suprimento", pk=suprimento.id)

    try:
        _salvar_despesa_manual(suprimento, request.POST, request.FILES.get("arquivo"))
        messages.success(request, "Despesa e documento anexados com sucesso!")
    except ValidationError as exc:
        messages.error(request, str(exc))
    except (OSError, TypeError, ValueError):
        messages.error(request, "Erro ao processar a despesa. Verifique os valores.")

    return redirect("gerenciar_suprimento", pk=suprimento.id)


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
@require_POST
def fechar_suprimento_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Encerra a prestacao de contas e avanca o processo vinculado para conferencia."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)

    if _suprimento_encerrado(suprimento):
        messages.warning(request, f"Suprimento #{suprimento.id} já está encerrado.")
        return redirect("painel_suprimentos")

    _atualizar_status_apos_fechamento(suprimento)
    messages.success(
        request,
        f"Prestação de contas do suprimento #{suprimento.id} encerrada e enviada para Conferência!",
    )
    return redirect("painel_suprimentos")


__all__ = ["adicionar_despesa_action", "fechar_suprimento_action"]
