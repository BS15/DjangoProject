"""Paineis GET da etapa de conferencia."""

from django.contrib.auth.decorators import permission_required
from django.db.models import Exists, OuterRef
from django.shortcuts import render
from django.views.decorators.http import require_GET

from commons.shared.text_tools import normalize_choice
from fiscal.models import RetencaoImposto
from pagamentos.domain_models import Contingencia, Processo, ProcessoStatus
from pagamentos.views.helpers import _aplicar_filtro_por_opcao, _resolver_parametros_ordenacao


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def painel_conferencia_view(request):
    """Exibe o painel de conferencia de processos pagos."""
    processos_pagos = Processo.objects.filter(status__opcao_status__iexact=ProcessoStatus.PAGO_EM_CONFERENCIA).annotate(
        tem_pendencia=Exists(Contingencia.objects.filter(processo=OuterRef("pk"))),
        tem_retencao=Exists(
            RetencaoImposto.objects.filter(nota_fiscal__processo=OuterRef("pk")).exclude(
                status__status_choice__iexact="PAGO"
            )
        ),
    )

    filtro = normalize_choice(
        request.GET.get("filtro", ""),
        {"com_pendencia", "com_retencao", "com_ambos", "sem_pendencias"},
    )
    processos_pagos = _aplicar_filtro_por_opcao(
        processos_pagos,
        filtro,
        {
            "com_pendencia": {"tem_pendencia": True},
            "com_retencao": {"tem_retencao": True},
            "com_ambos": {"tem_pendencia": True, "tem_retencao": True},
            "sem_pendencias": {"tem_pendencia": False, "tem_retencao": False},
        },
    )

    ordem, direcao, order_field = _resolver_parametros_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "credor": "credor__nome",
            "empenho": "n_nota_empenho",
            "data_pagamento": "data_pagamento",
            "valor_liquido": "valor_liquido",
        },
        default_ordem="data_pagamento",
        default_direcao="asc",
    )
    processos_pagos = processos_pagos.order_by(order_field, "id")

    context = {
        "processos": processos_pagos,
        "ordem": ordem,
        "direcao": direcao,
        "pode_interagir": request.user.has_perm("pagamentos.operador_contas_a_pagar"),
        "filtro_ativo": filtro,
    }
    return render(request, "pagamentos/conferencia.html", context)


__all__ = ["painel_conferencia_view"]
