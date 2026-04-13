"""Views e lógica de negócio dedicadas à sincronização SISCAC de pagamentos."""

import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from fluxo.domain_models import Processo
from fluxo.utils import decimals_equal_money, names_bidirectional_match, parse_siscac_report

logger = logging.getLogger(__name__)


def sync_siscac_payments(extracted_payments):
    """Concilia pagamentos extraídos com processos internos e classifica sucessos/divergências."""
    resultados = {"sucessos": [], "divergencias": [], "nao_encontrados": [], "retroativos_corrigidos": 0}
    matched_processo_ids = []

    for payment in extracted_payments:
        if payment["comprovante"] is None:
            continue

        candidates = Processo.objects.filter(
            comprovantes_pagamento__numero_comprovante=payment["comprovante"],
            documentos_orcamentarios__numero_nota_empenho=payment["nota_empenho"],
        ).select_related("credor").distinct()

        for processo in candidates:
            if processo.credor is None or not processo.credor.nome:
                continue

            credor_match = names_bidirectional_match(processo.credor.nome, payment["credor"])
            valor_decimal = payment["valor_total"].quantize(Decimal("0.01"))
            valor_match = decimals_equal_money(valor_decimal, processo.valor_liquido)

            if credor_match and valor_match:
                if processo.n_pagamento_siscac != payment["siscac_pg"]:
                    if processo.n_pagamento_siscac:
                        resultados["retroativos_corrigidos"] += 1
                    processo.n_pagamento_siscac = payment["siscac_pg"]
                    processo.save(update_fields=["n_pagamento_siscac"])
                resultados["sucessos"].append(
                    {
                        "id": processo.id,
                        "siscac_pg": payment["siscac_pg"],
                        "credor": processo.credor.nome,
                        "valor": processo.valor_liquido,
                    }
                )
                matched_processo_ids.append(processo.id)
            else:
                resultados["divergencias"].append(
                    {
                        "processo_id": processo.id,
                        "siscac_pg": payment["siscac_pg"],
                        "credor_siscac": payment["credor"],
                        "valor_siscac": valor_decimal,
                        "credor_sistema": processo.credor.nome,
                        "valor_sistema": processo.valor_liquido,
                    }
                )
                matched_processo_ids.append(processo.id)

    status_pagos = [
        "PAGO - EM CONFERÊNCIA",
        "PAGO - A CONTABILIZAR",
        "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        "APROVADO - PENDENTE ARQUIVAMENTO",
        "ARQUIVADO",
    ]
    orphans = (
        Processo.objects.filter(status__status_choice__in=status_pagos)
        .filter(Q(n_pagamento_siscac__isnull=True) | Q(n_pagamento_siscac__exact=""))
        .exclude(id__in=matched_processo_ids)
        .select_related("credor")
    )

    for orphan in orphans:
        resultados["nao_encontrados"].append(
            {
                "id": orphan.id,
                "credor": orphan.credor.nome if orphan.credor else "—",
                "data_pagamento": orphan.data_pagamento,
                "valor_liquido": orphan.valor_liquido,
            }
        )

    return resultados


@require_GET
@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
def sincronizar_siscac(request):
    """Renderiza o painel de sincronização SISCAC."""
    return render(request, "fluxo/sincronizar_siscac.html", {})


@require_POST
@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
def sincronizar_siscac_manual_action(request):
    """Processa sincronização manual de pares processo|SISCAC selecionados."""
    force_sync_ids = request.POST.getlist("force_sync_ids")
    count = 0
    errors = 0

    for item in force_sync_ids:
        try:
            processo_id, siscac_pg = item.split("|", 1)
            updated = Processo.objects.filter(id=int(processo_id)).update(n_pagamento_siscac=siscac_pg)
            if updated:
                count += 1
            else:
                errors += 1
        except (TypeError, ValueError):
            errors += 1

    if count:
        messages.success(request, f"{count} processo(s) sincronizado(s) com sucesso.")
    if errors:
        messages.error(request, f"{errors} item(ns) não puderam ser sincronizados.")
    return redirect("sincronizar_siscac")


@require_POST
@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
def sincronizar_siscac_auto_action(request):
    """Processa upload do PDF SISCAC e executa sincronização automática."""
    pdf_file = request.FILES.get("siscac_pdf")
    if not pdf_file or not pdf_file.name.lower().endswith(".pdf"):
        messages.error(request, "Nenhum arquivo ou PDF inválido enviado.")
        return redirect("sincronizar_siscac")

    try:
        extracted = parse_siscac_report(pdf_file)
        results = sync_siscac_payments(extracted)
        return render(request, "fluxo/sincronizar_siscac.html", {"resultados": results})
    except (OSError, TypeError, ValueError):
        logger.exception("Falha ao processar relatório SISCAC no modo automático")
        messages.error(request, "Erro ao processar o relatório SISCAC. Verifique o arquivo e tente novamente.")
        return redirect("sincronizar_siscac")
