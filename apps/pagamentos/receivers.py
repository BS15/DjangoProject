"""Receivers (Listeners) para eventos de domínio de satélites no módulo de Pagamentos."""

from django.dispatch import receiver
from django.db import transaction

from commons.shared.signals import solicitacao_cancelamento_processo
from apps.pagamentos.domain_models import CancelamentoProcessual

from apps.pagamentos.services.cancelamentos import (
    _validar_dados_devolucao,
    _criar_devolucao,
    _set_processo_cancelado,
    _processo_pago_ou_posterior,
)


@receiver(solicitacao_cancelamento_processo)
def processar_cancelamento_satelite(
    sender,
    instance,
    processo,
    justificativa,
    usuario,
    dados_devolucao=None,
    tipo_cancelamento_relacional=None,
    kwargs_relacional=None,
    **kwargs
):
    """Escuta eventos de cancelamento de verbas/suprimentos e estorna o Processo."""
    if not processo:
        return

    processo_pago = _processo_pago_ou_posterior(processo)
    
    # A validação final de dados_devolucao vs status é feita aqui também como double-check 
    # pro lado do Processo, garantindo consistência.
    _validar_dados_devolucao(dados_devolucao, processo_pago, "Processo")

    kwargs_cancelamento = kwargs_relacional or {}

    with transaction.atomic():
        if processo_pago and dados_devolucao:
            _criar_devolucao(
                processo,
                dados_devolucao,
                motivo_padrao=f"Devolução referente ao cancelamento oriundo de {sender.__name__} #{instance.pk}.",
            )
        _set_processo_cancelado(processo)
        
        CancelamentoProcessual.objects.create(
            processo=processo,
            tipo=tipo_cancelamento_relacional or CancelamentoProcessual.TIPO_PROCESSO,
            justificativa=justificativa.strip(),
            registrado_por=usuario,
            **kwargs_cancelamento
        )
