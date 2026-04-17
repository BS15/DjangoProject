"""Paineis GET da etapa de contabilizacao."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from fluxo.forms import PendenciaForm
from fluxo.domain_models import Processo, ProcessoStatus


@require_GET
@permission_required("fluxo.pode_contabilizar", raise_exception=True)
def painel_contabilizacao_view(request):
    """Exibe o painel de processos prontos para contabilizacao."""
    processos = Processo.objects.filter(status__status_choice__iexact=ProcessoStatus.PAGO_A_CONTABILIZAR).order_by("data_pagamento")
    context = {
        "processos": processos,
        "pendencia_form": PendenciaForm(),
        "pode_interagir": request.user.has_perm("fluxo.pode_contabilizar"),
    }

    return render(request, "fluxo/contabilizacao.html", context)


__all__ = ["painel_contabilizacao_view"]
