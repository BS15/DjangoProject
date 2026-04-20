"""Paineis GET da etapa de lancamento bancario."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from pagamentos.domain_models import Processo, ProcessoStatus, StatusChoicesProcesso
from pagamentos.views.helpers import _build_detalhes_pagamento, _consolidar_totais_pagamento


@require_GET
@permission_required("pagamentos.pode_operar_contas_pagar", raise_exception=True)
def lancamento_bancario(request):
    """Renderiza o painel de lancamento bancario com totais consolidados."""
    ids = request.session.get("processos_lancamento", [])

    if not ids:
        messages.warning(request, "Nenhum processo foi selecionado.")
        return redirect("contas_a_pagar")

    status_autorizado = StatusChoicesProcesso.objects.filter(
        status_choice__iexact=ProcessoStatus.A_PAGAR_AUTORIZADO
    ).first()
    status_lancado = StatusChoicesProcesso.objects.filter(
        status_choice__iexact=ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE
    ).first()

    processos_qs = (
        Processo.objects.filter(id__in=ids)
        .select_related("forma_pagamento", "tipo_pagamento", "conta", "credor__conta", "status")
        .prefetch_related("documentos")
        .order_by("forma_pagamento__forma_pagamento", "id")
    )

    a_pagar_qs = processos_qs.filter(status=status_autorizado) if status_autorizado else processos_qs.none()
    lancados_qs = processos_qs.filter(status=status_lancado) if status_lancado else processos_qs.none()

    processos_a_pagar, totais_a_pagar = _build_detalhes_pagamento(a_pagar_qs)
    processos_lancados, totais_lancados = _build_detalhes_pagamento(lancados_qs)
    totais_consolidados = _consolidar_totais_pagamento(totais_a_pagar, totais_lancados)

    context = {
        "processos_a_pagar": processos_a_pagar,
        "processos_lancados": processos_lancados,
        "totais_a_pagar": totais_a_pagar,
        "totais_lancados": totais_lancados,
        **totais_consolidados,
    }
    return render(request, "pagamentos/lancamento_bancario.html", context)


__all__ = ["lancamento_bancario"]
