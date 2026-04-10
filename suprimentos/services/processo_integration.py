"""Hooks de integração entre suprimentos e Processo."""

from decimal import Decimal


def criar_processo_para_suprimento(suprimento, detalhamento):
    """Cria processo financeiro para suprimento e realiza a vinculação."""
    from fluxo.models import FormasDePagamento, Processo, StatusChoicesProcesso, TiposDePagamento

    forma_pgto, _ = FormasDePagamento.objects.get_or_create(
        forma_de_pagamento__iexact="CARTÃO PRÉ-PAGO",
        defaults={"forma_de_pagamento": "CARTÃO PRÉ-PAGO"},
    )
    tipo_pgto, _ = TiposDePagamento.objects.get_or_create(
        tipo_de_pagamento__iexact="SUPRIMENTO DE FUNDOS",
        defaults={"tipo_de_pagamento": "SUPRIMENTO DE FUNDOS"},
    )
    status_inicial, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact="A EMPENHAR",
        defaults={"status_choice": "A EMPENHAR"},
    )

    taxa_saque = suprimento.taxa_saque or Decimal("0")
    processo = Processo.objects.create(
        credor=suprimento.suprido,
        valor_bruto=suprimento.valor_liquido,
        valor_liquido=(suprimento.valor_liquido or Decimal("0")) - taxa_saque,
        forma_pagamento=forma_pgto,
        tipo_pagamento=tipo_pgto,
        status=status_inicial,
        detalhamento=detalhamento,
        extraorcamentario=False,
    )

    suprimento.processo = processo
    suprimento.save(update_fields=["processo"])
    return processo


def gerar_documentos_relacionados_por_transicao(processo, status_anterior, novo_status):
    """Gera recibos de suprimento quando o processo entra em pago."""
    from fluxo.services.processo_documentos import gerar_anexo_por_tipo

    entrou_em_pago = not status_anterior.startswith("PAGO") and novo_status.startswith("PAGO")
    if not entrou_em_pago:
        return

    for suprimento in processo.suprimentos.all():
        gerar_anexo_por_tipo(
            processo,
            "recibo_suprimento",
            suprimento,
            f"Recibo_Suprimento_{suprimento.id}.pdf",
            "RECIBO DE PAGAMENTO",
        )


def sincronizar_relacoes_apos_transicao(processo, status_anterior, novo_status, usuario=None):
    """Suprimentos não propagam status a partir do pagamento do processo."""
    return None
