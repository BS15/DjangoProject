"""Acoes POST da etapa de empenho."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from fluxo.models import Processo
from ..helpers import _registrar_empenho_e_anexar_siscac


logger = logging.getLogger(__name__)


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
@require_POST
def registrar_empenho_action(request):
    """Registra empenho e avanca o processo para AGUARDANDO LIQUIDACAO."""
    processo_id = request.POST.get("processo_id")
    n_nota_empenho = request.POST.get("n_nota_empenho")
    data_empenho_str = request.POST.get("data_empenho")
    ano_exercicio = request.POST.get("ano_exercicio")
    siscac_file = request.FILES.get("siscac_file")

    if not (processo_id and n_nota_empenho and data_empenho_str):
        messages.error(request, "Por favor, preencha o número e a data da nota de empenho para avançar.")
        return redirect("a_empenhar")

    try:
        with transaction.atomic():
            processo = Processo.objects.get(id=processo_id)
            ano_exercicio_int = int(ano_exercicio) if ano_exercicio and ano_exercicio.isdigit() else None
            _registrar_empenho_e_anexar_siscac(
                processo,
                n_nota_empenho,
                data_empenho_str,
                siscac_file,
                ano_exercicio=ano_exercicio_int,
            )
            try:
                processo.avancar_status("AGUARDANDO LIQUIDAÇÃO", usuario=request.user)
            except ValidationError as ve:
                raise ValueError(str(ve))

        messages.success(
            request,
            f"Empenho registrado com sucesso! Processo #{processo.id} avançou para Aguardando Liquidação.",
        )
    except Processo.DoesNotExist:
        messages.error(request, "Processo não encontrado.")
    except (DatabaseError, OSError, TypeError, ValueError):
        logger.exception("Erro inesperado ao salvar empenho do processo %s", processo_id)
        messages.error(request, "Erro interno ao salvar empenho. Tente novamente.")

    return redirect("a_empenhar")


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
@require_POST
def avancar_para_pagamento_view(request, pk):
    """Avanca processo de AGUARDANDO LIQUIDACAO para A PAGAR - PENDENTE AUTORIZACAO."""
    processo = get_object_or_404(Processo, id=pk)
    status_atual = processo.status.status_choice.upper() if processo.status else ""

    if not status_atual.startswith("AGUARDANDO LIQUIDAÇÃO"):
        messages.error(
            request,
            f'O processo #{pk} não está em status "Aguardando Liquidação" '
            f'(status atual: "{processo.status}"). Ação não permitida.',
        )
        return redirect("editar_processo", pk=pk)

    try:
        with transaction.atomic():
            processo.avancar_status("A PAGAR - PENDENTE AUTORIZAÇÃO", usuario=request.user)

        messages.success(request, f'Processo #{pk} avançado com sucesso para "A Pagar - Pendente Autorização".')
    except ValidationError as ve:
        for erro in ve.messages:
            messages.error(request, erro)
    except (DatabaseError, TypeError, ValueError):
        logger.exception("Erro ao avançar processo %s para pagamento", pk)
        messages.error(request, "Erro interno ao avançar o processo. Tente novamente.")

    return redirect("editar_processo", pk=pk)


__all__ = ["registrar_empenho_action", "avancar_para_pagamento_view"]
