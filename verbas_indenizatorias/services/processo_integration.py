"""Hooks de integração entre verbas indenizatórias e Processo."""

import logging


logger = logging.getLogger(__name__)


def criar_processo_e_vincular_verbas(itens, tipo_verba, credor_obj, usuario=None):
    """Cria processo de agrupamento e vincula lote de verbas em transação atômica."""
    from django.db import transaction

    from commons.shared.signature_services import criar_assinatura_rascunho
    from fluxo.models import Processo, StatusChoicesProcesso, TiposDePagamento
    from fluxo.models import AssinaturaAutentique
    from commons.shared.pdf_response import gerar_documento_bytes
    from verbas_indenizatorias.models import Diaria
    from verbas_indenizatorias.pdf_generators import VERBAS_DOCUMENT_REGISTRY

    total = sum(item.valor_total for item in itens if item.valor_total)
    status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact="A PAGAR - PENDENTE AUTORIZAÇÃO",
        defaults={"status_choice": "A PAGAR - PENDENTE AUTORIZAÇÃO"},
    )
    tipo_pagamento_verbas, _ = TiposDePagamento.objects.get_or_create(
        tipo_de_pagamento__iexact="VERBAS INDENIZATÓRIAS",
        defaults={"tipo_de_pagamento": "VERBAS INDENIZATÓRIAS"},
    )

    falhas_pcd = []
    with transaction.atomic():
        novo_processo = Processo.objects.create(
            credor=credor_obj,
            valor_bruto=total,
            valor_liquido=total,
            detalhamento=f"Agrupamento de {tipo_verba.capitalize()}s",
            status=status_padrao,
            tipo_pagamento=tipo_pagamento_verbas,
        )

        for item in itens:
            item.processo = novo_processo
            if isinstance(item, Diaria):
                item.avancar_status("ENVIADA PARA PAGAMENTO")
                try:
                    pdf_bytes = gerar_documento_bytes("pcd", item, VERBAS_DOCUMENT_REGISTRY)
                    criar_assinatura_rascunho(
                        entidade=item,
                        tipo_documento="PCD",
                        criador=usuario,
                        pdf_bytes=pdf_bytes,
                        nome_arquivo=f"PCD_{item.id}.pdf",
                        assinatura_model=AssinaturaAutentique,
                    )
                except (OSError, RuntimeError, TypeError, ValueError):
                    logger.exception("Falha ao gerar PCD da diária %s", item.id)
                    falhas_pcd.append(item.numero_siscac or item.id)
            item.save()

    return novo_processo, falhas_pcd


def gerar_documentos_relacionados_por_transicao(processo, status_anterior, novo_status):
    """Gera documentos de verbas quando o processo atinge marcos de pagamento."""
    from fluxo.services.processo_documentos import gerar_anexo_por_tipo

    entrou_em_pago = not status_anterior.startswith("PAGO") and novo_status.startswith("PAGO")
    if not entrou_em_pago:
        return

    for diaria in processo.diarias.all():
        identificador = diaria.numero_siscac or diaria.id
        gerar_anexo_por_tipo(
            processo,
            "pcd",
            diaria,
            f"PCD_{identificador}.pdf",
            "PROPOSTA DE CONCESSÃO DE DIÁRIAS (PCD)",
        )

    for reembolso in processo.reembolsos_combustivel.all():
        identificador = reembolso.numero_sequencial or reembolso.id
        gerar_anexo_por_tipo(
            processo,
            "recibo_reembolso",
            reembolso,
            f"Recibo_Reembolso_{identificador}.pdf",
            "RECIBO DE PAGAMENTO",
        )

    for jeton in processo.jetons.all():
        identificador = jeton.numero_sequencial or jeton.id
        gerar_anexo_por_tipo(
            processo,
            "recibo_jeton",
            jeton,
            f"Recibo_Jeton_{identificador}.pdf",
            "RECIBO DE PAGAMENTO",
        )

    for auxilio in processo.auxilios_representacao.all():
        identificador = auxilio.numero_sequencial or auxilio.id
        gerar_anexo_por_tipo(
            processo,
            "recibo_auxilio",
            auxilio,
            f"Recibo_Auxilio_{identificador}.pdf",
            "RECIBO DE PAGAMENTO",
        )


def sincronizar_relacoes_apos_transicao(processo, status_anterior, novo_status, usuario=None):
    """Propaga status do processo pago para verbas agrupadas."""
    if not novo_status.startswith("PAGO"):
        return

    from verbas_indenizatorias.models import StatusChoicesVerbasIndenizatorias

    status_paga, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(status_choice="PAGA")

    conjuntos = (
        processo.diarias.all(),
        processo.reembolsos_combustivel.all(),
        processo.jetons.all(),
        processo.auxilios_representacao.all(),
    )
    for queryset in conjuntos:
        for item in queryset:
            item.status = status_paga
            if usuario:
                item._history_user = usuario
            item.save(update_fields=["status"])
