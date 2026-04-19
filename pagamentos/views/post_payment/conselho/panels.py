"""Paineis GET da etapa de conselho fiscal."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from pagamentos.domain_models import Processo, ProcessoStatus, ReuniaoConselho, ReuniaoConselhoStatus


@require_GET
@permission_required("pagamentos.pode_auditar_conselho", raise_exception=True)
def painel_conselho_view(request):
    """Exibe o painel do conselho com reunioes ativas e processos pendentes."""
    reunioes_ativas = ReuniaoConselho.objects.filter(
        status__in=[ReuniaoConselhoStatus.AGENDADA, ReuniaoConselhoStatus.EM_ANALISE]
    ).order_by("-numero")
    processos_sem_reuniao = Processo.objects.filter(
        status__status_choice__iexact=ProcessoStatus.CONTABILIZADO_CONSELHO,
        reuniao_conselho__isnull=True,
    ).order_by("data_pagamento")
    context = {
        "reunioes_ativas": reunioes_ativas,
        "processos_sem_reuniao": processos_sem_reuniao,
        "pode_interagir": request.user.has_perm("pagamentos.pode_auditar_conselho"),
    }
    return render(request, "pagamentos/conselho.html", context)


__all__ = ["painel_conselho_view"]
