"""Paineis GET da etapa de autorizacao."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from pagamentos.forms import PendenciaForm
from pagamentos.domain_models import Processo, ProcessoStatus
from pagamentos.views.helpers import _resolver_parametros_ordenacao


@require_GET
@permission_required("pagamentos.pode_autorizar_pagamento", raise_exception=True)
def painel_autorizacao_view(request):
    """Renderiza o painel de autorizacao com filas pendente e autorizada."""
    ordem, direcao, order_field = _resolver_parametros_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "credor": "credor__nome",
            "empenho": "n_nota_empenho",
            "valor_liquido": "valor_liquido",
            "status": "status__opcao_status",
        },
        default_ordem="id",
        default_direcao="desc",
    )

    processos = Processo.objects.filter(
        status__opcao_status__iexact=ProcessoStatus.A_PAGAR_ENVIADO_PARA_AUTORIZACAO
    ).order_by(order_field, "-id")

    processos_autorizados = Processo.objects.filter(
        status__opcao_status__iexact=ProcessoStatus.A_PAGAR_AUTORIZADO
    ).order_by("data_pagamento", "id")

    context = {
        "processos": processos,
        "processos_autorizados": processos_autorizados,
        "pendencia_form": PendenciaForm(),
        "ordem": ordem,
        "direcao": direcao,
        "pode_interagir": request.user.has_perm("pagamentos.pode_autorizar_pagamento"),
    }
    return render(request, "pagamentos/autorizacao.html", context)


__all__ = ["painel_autorizacao_view"]
