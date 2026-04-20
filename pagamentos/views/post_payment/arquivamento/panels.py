"""Paineis GET da etapa de arquivamento."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from pagamentos.filters import ProcessoFilter
from pagamentos.domain_models import Processo, ProcessoStatus
from pagamentos.views.shared import apply_filterset


@require_GET
@permission_required("pagamentos.pode_arquivar", raise_exception=True)
def painel_arquivamento_view(request):
    """Exibe painel de arquivamento com pendentes e historico arquivado."""
    processos_pendentes = Processo.objects.filter(
        status__opcao_status__iexact=ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO
    ).order_by(
        "data_pagamento"
    )

    arquivados_qs = Processo.objects.filter(status__opcao_status__iexact=ProcessoStatus.ARQUIVADO).order_by("-id")

    arquivamento_filtro = apply_filterset(request, ProcessoFilter, arquivados_qs)
    processos_arquivados = arquivamento_filtro.qs

    return render(
        request,
        "pagamentos/arquivamento.html",
        {
            "processos_pendentes": processos_pendentes,
            "processos_arquivados": processos_arquivados,
            "processos_arquivados_count": processos_arquivados.count(),
            "arquivamento_filtro": arquivamento_filtro,
            "pode_interagir": request.user.has_perm("pagamentos.pode_arquivar"),
        },
    )


__all__ = ["painel_arquivamento_view"]
