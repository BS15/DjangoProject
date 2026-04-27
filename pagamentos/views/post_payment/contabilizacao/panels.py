"""Paineis GET da etapa de contabilizacao."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from pagamentos.forms import PendenciaForm
from pagamentos.domain_models import Processo, ProcessoStatus
from pagamentos.views.helpers import _resolver_parametros_ordenacao


@require_GET
@permission_required("pagamentos.pode_contabilizar", raise_exception=True)
def painel_contabilizacao_view(request):
    """Exibe o painel de processos prontos para contabilizacao."""
    ordem, direcao, order_field = _resolver_parametros_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "credor": "credor__nome",
            "data_pagamento": "data_pagamento",
            "valor_liquido": "valor_liquido",
            "status": "status__opcao_status",
        },
        default_ordem="data_pagamento",
        default_direcao="asc",
    )
    processos = Processo.objects.filter(status__opcao_status__iexact=ProcessoStatus.PAGO_A_CONTABILIZAR).order_by(
        order_field,
        "id",
    )
    context = {
        "processos": processos,
        "pendencia_form": PendenciaForm(),
        "ordem": ordem,
        "direcao": direcao,
        "pode_interagir": request.user.has_perm("pagamentos.pode_contabilizar"),
    }

    return render(request, "pagamentos/contabilizacao.html", context)


__all__ = ["painel_contabilizacao_view"]
