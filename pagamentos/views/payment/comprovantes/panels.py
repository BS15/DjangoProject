"""Painel GET de comprovantes de pagamento."""

import json

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render

from pagamentos.domain_models import Processo, ProcessoStatus


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def painel_comprovantes_view(request):
    processos_lancados = Processo.objects.filter(
        status__opcao_status__iexact=ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE
    ).select_related("credor").order_by("credor__nome", "id")

    processos_list = []
    for processo in processos_lancados:
        processos_list.append(
            {
                "id": processo.id,
                "credor_nome": processo.credor.nome if processo.credor else "Sem Credor",
                "valor_liquido": str(processo.valor_liquido or "0.00"),
                "n_nota_empenho": processo.n_nota_empenho or "S/N",
            }
        )

    context = {"processos_json": json.dumps(processos_list)}
    return render(request, "fiscal/painel_comprovantes.html", context)


__all__ = ["painel_comprovantes_view"]
