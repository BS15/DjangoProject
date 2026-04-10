"""Paineis GET da etapa de conselho fiscal."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from fluxo.models import Processo, ReuniaoConselho


@require_GET
@permission_required("fluxo.pode_auditar_conselho", raise_exception=True)
def painel_conselho_view(request):
    """Exibe o painel do conselho com reunioes ativas e processos pendentes."""
    reunioes_ativas = ReuniaoConselho.objects.filter(status__in=["AGENDADA", "EM_ANALISE"]).order_by("-numero")
    processos_sem_reuniao = Processo.objects.filter(
        status__status_choice__iexact="CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        reuniao_conselho__isnull=True,
    ).order_by("data_pagamento")
    context = {
        "reunioes_ativas": reunioes_ativas,
        "processos_sem_reuniao": processos_sem_reuniao,
        "pode_interagir": request.user.has_perm("fluxo.pode_auditar_conselho"),
    }
    return render(request, "fluxo/conselho.html", context)


__all__ = ["painel_conselho_view"]
