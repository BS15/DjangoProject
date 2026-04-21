"""Views de acoes da etapa de prestacao de contas de suprimentos."""

from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from suprimentos.forms import DespesaSuprimentoForm, EnviarPrestacaoSuprimentoForm
from suprimentos.models import PrestacaoContasSuprimento, SuprimentoDeFundos
from suprimentos.services.prestacao import (
    encerrar_prestacao_suprimento,
    enviar_prestacao_suprimento,
    obter_ou_criar_prestacao_suprimento,
)
from ..helpers import _atualizar_status_apos_fechamento, _suprimento_encerrado
import logging

logger = logging.getLogger(__name__)


@require_POST
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def adicionar_despesa_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Registra manualmente uma despesa de suprimento a partir de dados do POST."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)

    if _suprimento_encerrado(suprimento):
        messages.error(request, "Este suprimento já foi encerrado e não pode receber novas despesas.")
        return redirect("gerenciar_suprimento_view", pk=suprimento.id)

    form = DespesaSuprimentoForm(request.POST, request.FILES)
    if form.is_valid():
        despesa = form.save(commit=False)
        despesa.suprimento = suprimento
        despesa.save()
        logger.info(
            "mutation=add_despesa_suprimento suprimento_id=%s despesa_id=%s user_id=%s",
            suprimento.id,
            despesa.id,
            request.user.pk,
        )
        messages.success(request, "Despesa e documento anexados com sucesso!")
        return redirect("gerenciar_suprimento_view", pk=suprimento.id)
    else:
        messages.error(request, "Verifique os campos da despesa e tente novamente.")
        return redirect("adicionar_despesa_view", pk=suprimento.id)


@require_POST
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def fechar_suprimento_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Encerra a prestacao de contas e avanca o processo vinculado para conferencia."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)

    if _suprimento_encerrado(suprimento):
        messages.warning(request, f"Suprimento #{suprimento.id} já está encerrado.")
        return redirect("suprimentos_list")

    _atualizar_status_apos_fechamento(suprimento)
    logger.info("mutation=fechar_suprimento suprimento_id=%s user_id=%s", suprimento.id, request.user.pk)
    messages.success(
        request,
        f"Prestação de contas do suprimento #{suprimento.id} encerrada e enviada para Conferência!",
    )
    return redirect("suprimentos_list")


@require_POST
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def enviar_prestacao_suprimento_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Registra o envio da prestação de contas pelo responsável pelo suprimento."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)

    if _suprimento_encerrado(suprimento):
        messages.error(request, "Este suprimento já foi encerrado.")
        return redirect("gerenciar_suprimento_view", pk=suprimento.id)

    form = EnviarPrestacaoSuprimentoForm(request.POST, request.FILES)
    if not form.is_valid():
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)
        return redirect("gerenciar_suprimento_view", pk=suprimento.id)

    prestacao = obter_ou_criar_prestacao_suprimento(suprimento)

    if prestacao.status == PrestacaoContasSuprimento.STATUS_ENVIADA:
        messages.warning(request, "A prestação de contas já foi enviada e aguarda revisão.")
        return redirect("gerenciar_suprimento_view", pk=suprimento.id)

    if prestacao.status == PrestacaoContasSuprimento.STATUS_ENCERRADA:
        messages.warning(request, "A prestação de contas já está encerrada.")
        return redirect("gerenciar_suprimento_view", pk=suprimento.id)

    comprovante = form.cleaned_data.get("comprovante_devolucao")
    data_devolucao = form.cleaned_data.get("data_devolucao")

    try:
        with transaction.atomic():
            enviar_prestacao_suprimento(prestacao, comprovante, data_devolucao, request.user)
    except ValidationError as exc:
        for msg in exc.messages:
            messages.error(request, msg)
        return redirect("gerenciar_suprimento_view", pk=suprimento.id)

    logger.info(
        "mutation=enviar_prestacao_suprimento suprimento_id=%s user_id=%s",
        suprimento.id,
        request.user.pk,
    )
    messages.success(
        request,
        f"Prestação de contas do suprimento #{suprimento.id} enviada para revisão com sucesso!",
    )
    return redirect("gerenciar_suprimento_view", pk=suprimento.id)


@require_POST
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def aprovar_prestacao_suprimento_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Operador aprova a prestação de contas, aciona a devolução automática e encerra o suprimento."""
    prestacao: Any = get_object_or_404(
        PrestacaoContasSuprimento.objects.select_related("suprimento__processo"),
        pk=pk,
    )

    if prestacao.status != PrestacaoContasSuprimento.STATUS_ENVIADA:
        messages.warning(request, "Esta prestação não está aguardando revisão.")
        return redirect("revisar_prestacao_suprimento", pk=prestacao.id)

    try:
        encerrar_prestacao_suprimento(prestacao, request.user)
    except ValidationError as exc:
        for msg in exc.messages:
            messages.error(request, msg)
        return redirect("revisar_prestacao_suprimento", pk=prestacao.id)

    logger.info(
        "mutation=aprovar_prestacao_suprimento prestacao_id=%s suprimento_id=%s user_id=%s",
        prestacao.id,
        prestacao.suprimento_id,
        request.user.pk,
    )
    messages.success(
        request,
        f"Prestação do suprimento #{prestacao.suprimento_id} aprovada e encerrada com sucesso!",
    )
    return redirect("revisar_prestacoes_suprimento")


__all__ = [
    "adicionar_despesa_action",
    "fechar_suprimento_action",
    "enviar_prestacao_suprimento_action",
    "aprovar_prestacao_suprimento_action",
]
