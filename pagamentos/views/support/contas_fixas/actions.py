"""Actions (POST-only) de contas fixas."""

import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from credores.models import ContaFixa, FaturaMensal
from pagamentos.domain_models import Processo

from .forms import ContaFixaForm

logger = logging.getLogger(__name__)


def _redirect_painel_com_periodo(request):
    mes_raw = request.POST.get("mes")
    ano_raw = request.POST.get("ano")
    try:
        mes = int(mes_raw)
        ano = int(ano_raw)
    except (TypeError, ValueError):
        mes = None
        ano = None
    if mes is not None and ano is not None:
        query = urlencode({"mes": max(1, min(12, mes)), "ano": max(2000, min(2100, ano))})
        return redirect(f"{reverse('painel_contas_fixas')}?{query}")
    return redirect("painel_contas_fixas")


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def add_conta_fixa_action(request):
    form = ContaFixaForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Erro ao cadastrar conta fixa. Verifique os campos.")
        return redirect("add_conta_fixa")

    conta = form.save()
    logger.info("mutation=add_conta_fixa conta_id=%s user_id=%s", conta.pk, request.user.pk)
    messages.success(request, "Conta fixa cadastrada com sucesso.")
    return redirect("painel_contas_fixas")


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def edit_conta_fixa_action(request, pk):
    conta = get_object_or_404(ContaFixa, pk=pk)
    form = ContaFixaForm(request.POST, instance=conta)
    if not form.is_valid():
        messages.error(request, "Erro ao atualizar conta fixa. Verifique os campos.")
        return redirect("edit_conta_fixa", pk=pk)

    form.save()
    logger.info("mutation=edit_conta_fixa conta_id=%s user_id=%s", conta.pk, request.user.pk)
    messages.success(request, "Conta fixa atualizada com sucesso.")
    return redirect("painel_contas_fixas")


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def excluir_conta_fixa_action(request, pk):
    conta = get_object_or_404(ContaFixa, pk=pk)
    conta.ativa = False
    conta.save(update_fields=["ativa"])
    logger.info("mutation=deactivate_conta_fixa conta_id=%s user_id=%s", pk, request.user.pk)
    messages.success(request, "Conta fixa inativada com sucesso.")
    return _redirect_painel_com_periodo(request)


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def vincular_processo_fatura_action(request, fatura_id):
    fatura = get_object_or_404(FaturaMensal, pk=fatura_id)
    processo_id = request.POST.get("processo_id")
    if not processo_id:
        messages.error(request, "Informe o ID do processo para vincular.")
        return _redirect_painel_com_periodo(request)

    processo = get_object_or_404(Processo, pk=processo_id)
    fatura.processo_vinculado = processo
    fatura.save(update_fields=["processo_vinculado"])
    logger.info(
        "mutation=vincular_processo_fatura fatura_id=%s processo_id=%s user_id=%s",
        fatura.pk,
        processo.pk,
        request.user.pk,
    )
    messages.success(request, f"Fatura vinculada ao processo #{processo.pk}.")
    return _redirect_painel_com_periodo(request)


__all__ = [
    "add_conta_fixa_action",
    "edit_conta_fixa_action",
    "excluir_conta_fixa_action",
    "vincular_processo_fatura_action",
]
