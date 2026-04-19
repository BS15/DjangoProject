"""Views de API transversais do fluxo de pagamentos.

Este módulo concentra apenas endpoints de uso transversal entre etapas do
fluxo. APIs específicas de negócio vivem nos respectivos namespaces de views.

As regras de segurança seguem o padrão do projeto com `permission_required` e
respostas em `JsonResponse` para chamadas assíncronas.
"""

import json
import logging

from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse

from commons.shared.text_tools import format_brl_amount
from pagamentos.domain_models import Processo
from pagamentos.views.helpers.audit_builders import get_detalhes_pagamento


logger = logging.getLogger(__name__)


@permission_required("pagamentos.pode_operar_contas_pagar", raise_exception=True)
def api_detalhes_pagamento(request):
    """Monta resumo de detalhes de pagamento para uma lista de processos.

    Espera `POST` JSON com `ids` e retorna payload normalizado para exibição em
    painéis de pagamento/autorização, incluindo:
    - dados básicos do processo e credor;
    - valor líquido formatado em padrão brasileiro;
    - forma de pagamento;
    - detalhes derivados de `processo.detalhes_pagamento`.

    Em caso de exceção, captura o erro e devolve mensagem no payload para
    tratamento no frontend.

    Parâmetros:
        request: Requisição HTTP com corpo JSON.

    Retorna:
        JsonResponse: `sucesso=True` com lista em `dados` quando o `POST` é
        válido; caso contrário, `sucesso=False` com descrição do erro.
    """
    if request.method == "POST":
        try:
            dados = json.loads(request.body)
            processo_ids = dados.get("ids", [])

            processos = (
                Processo.objects.filter(id__in=processo_ids)
                .select_related("forma_pagamento", "conta", "credor")
                .prefetch_related("documentos")
            )

            resultados = []
            for p in processos:
                valor_formatado = format_brl_amount(p.valor_liquido, empty_value="0,00")

                pagamento = get_detalhes_pagamento(p)

                resultados.append(
                    {
                        "id": p.id,
                        "empenho": p.n_nota_empenho or "S/N",
                        "credor": p.credor.nome if p.credor else "Sem Credor",
                        "valor": valor_formatado,
                        "forma": p.forma_pagamento.forma_de_pagamento if p.forma_pagamento else "N/A",
                        "detalhe_tipo": pagamento["tipo_formatado"],
                        "detalhe_valor": pagamento["valor_formatado"],
                        "codigos_barras": pagamento["codigos_barras"],
                    }
                )

            return JsonResponse({"sucesso": True, "dados": resultados})
        except (json.JSONDecodeError, TypeError, ValueError, KeyError) as e:
            logger.exception("Erro ao montar detalhes de pagamento")
            return JsonResponse({"sucesso": False, "erro": str(e)})

    return JsonResponse({"sucesso": False, "erro": "Método inválido"})


__all__ = [
    "api_detalhes_pagamento",
]
