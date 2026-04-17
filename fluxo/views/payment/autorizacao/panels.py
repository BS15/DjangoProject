"""Paineis GET da etapa de autorizacao."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from fluxo.forms import PendenciaForm
from fluxo.domain_models import Processo, ProcessoStatus


@require_GET
@permission_required("fluxo.pode_autorizar_pagamento", raise_exception=True)
def painel_autorizacao_view(request):
    """Renderiza o painel de autorizacao com filas pendente e autorizada."""
    processos = Processo.objects.filter(
        status__status_choice__iexact=ProcessoStatus.A_PAGAR_ENVIADO_PARA_AUTORIZACAO
    ).order_by(
        "data_pagamento", "id"
    )

    processos_autorizados = Processo.objects.filter(
        status__status_choice__iexact=ProcessoStatus.A_PAGAR_AUTORIZADO
    ).order_by(
        "data_pagamento", "id"
    )

    context = {
        "processos": processos,
        "processos_autorizados": processos_autorizados,
        "pendencia_form": PendenciaForm(),
        "pode_interagir": request.user.has_perm("fluxo.pode_autorizar_pagamento"),
    }
    return render(request, "fluxo/autorizacao.html", context)


__all__ = ["painel_autorizacao_view"]
