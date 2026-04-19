"""Hooks de integração entre suprimentos de fundos e Processo."""

import logging

logger = logging.getLogger(__name__)


def criar_processo_para_suprimento(suprimento, detalhamento):
    """Cria processo de pagamento para suprimento de fundos em transação atômica."""
    from django.db import transaction
    from pagamentos.models import Processo, StatusChoicesProcesso, TiposDePagamento

    # Definir status padrão
    status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact="A EMPENHAR",
        defaults={"status_choice": "A EMPENHAR"},
    )

    # Definir tipo de pagamento
    tipo_pagamento_suprimento, _ = TiposDePagamento.objects.get_or_create(
        tipo_de_pagamento__iexact="SUPRIMENTO DE FUNDOS",
        defaults={"tipo_de_pagamento": "SUPRIMENTO DE FUNDOS"},
    )

    with transaction.atomic():
        novo_processo = Processo.objects.create(
            credor=suprimento.suprido,
            valor_bruto=suprimento.valor_liquido + suprimento.taxa_saque,
            valor_liquido=suprimento.valor_liquido,
            detalhamento=detalhamento,
            status=status_padrao,
            tipo_pagamento=tipo_pagamento_suprimento,
        )

        suprimento.processo = novo_processo
        suprimento.save(update_fields=["processo"])

    return novo_processo


def gerar_documentos_relacionados_por_transicao(processo, status_anterior, novo_status):
    """Hook de integração para documentos automáticos de suprimento.

    Mantido para compatibilidade com o orquestrador canônico do fluxo.
    No estado atual do domínio, suprimentos não geram anexos adicionais a partir
    dessas transições genéricas do Processo.
    """
    return None


def sincronizar_relacoes_apos_transicao(processo, status_anterior, novo_status, usuario=None):
    """Hook de sincronização pós-transição para suprimentos vinculados.

    Mantido para compatibilidade com o orquestrador canônico do fluxo.
    As mudanças de estado específicas de suprimento são tratadas no próprio
    domínio de suprimentos; portanto, esta integração é atualmente neutra.
    """
    return None
