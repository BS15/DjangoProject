"""Paineis GET da etapa de conferencia."""

from django.contrib.auth.decorators import permission_required
from django.db.models import Exists, OuterRef
from django.shortcuts import render
from django.views.decorators.http import require_GET

from fiscal.models import RetencaoImposto
from fluxo.domain_models import Contingencia, Processo
from fluxo.utils import normalize_choice
from fluxo.views.helpers import _aplicar_filtro_por_opcao


@require_GET
@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
def painel_conferencia_view(request):
    """Exibe o painel de conferencia de processos pagos."""
    processos_pagos = (
        Processo.objects.filter(status__status_choice__iexact="PAGO - EM CONFERÊNCIA")
        .annotate(
            tem_pendencia=Exists(Contingencia.objects.filter(processo=OuterRef("pk"))),
            tem_retencao=Exists(
                RetencaoImposto.objects.filter(nota_fiscal__processo=OuterRef("pk")).exclude(
                    status__status_choice__iexact="PAGO"
                )
            ),
        )
        .order_by("data_pagamento")
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

    context = {
        "processos": processos_pagos,
        "pode_interagir": request.user.has_perm("fluxo.pode_operar_contas_pagar"),
        "filtro_ativo": filtro,
    }
    return render(request, "fluxo/conferencia.html", context)


__all__ = ["painel_conferencia_view"]
