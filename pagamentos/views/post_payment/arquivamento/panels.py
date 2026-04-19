"""Paineis GET da etapa de arquivamento."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from fluxo.filters import ProcessoFilter
from fluxo.domain_models import Processo, ProcessoStatus
from fluxo.views.shared import apply_filterset


@require_GET
@permission_required("fluxo.pode_arquivar", raise_exception=True)
def painel_arquivamento_view(request):
    """Exibe painel de arquivamento com pendentes e historico arquivado."""
    processos_pendentes = Processo.objects.filter(
        status__status_choice__iexact=ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO
    ).order_by(
        "data_pagamento"
    )

    arquivados_qs = Processo.objects.filter(status__status_choice__iexact=ProcessoStatus.ARQUIVADO).order_by("-id")

    arquivamento_filtro = apply_filterset(request, ProcessoFilter, arquivados_qs)
    processos_arquivados = arquivamento_filtro.qs

    return render(
        request,
        "fluxo/arquivamento.html",
        {
            "processos_pendentes": processos_pendentes,
            "processos_arquivados": processos_arquivados,
            "processos_arquivados_count": processos_arquivados.count(),
            "arquivamento_filtro": arquivamento_filtro,
            "pode_interagir": request.user.has_perm("fluxo.pode_arquivar"),
        },
    )


__all__ = ["painel_arquivamento_view"]
