"""Serviços de cancelamento para o domínio de suprimentos de fundos."""

from django.core.exceptions import ValidationError
from django.db import transaction

from commons.shared.signals import solicitacao_cancelamento_processo


def _validar_justificativa(justificativa: str):
    """Lança ValidationError se a justificativa estiver vazia."""
    if not (justificativa or "").strip():
        raise ValidationError("A justificativa do cancelamento é obrigatória.")


def _validar_dados_devolucao(dados_devolucao: dict | None, entidade_paga: bool, entidade_label: str):
    """Quando entidade está paga, exige dados de devolução completos."""
    if not entidade_paga:
        return
    if not dados_devolucao:
        raise ValidationError(
            f"{entidade_label} com status pago requer devolução correspondente ao cancelamento."
        )
    if not dados_devolucao.get("valor_devolvido"):
        raise ValidationError("Informe o valor da devolução.")
    if not dados_devolucao.get("data_devolucao"):
        raise ValidationError("Informe a data da devolução.")
    if not dados_devolucao.get("comprovante"):
        raise ValidationError("O comprovante da devolução é obrigatório.")


def cancelar_suprimento(suprimento, justificativa: str, usuario, dados_devolucao: dict | None = None):
    """Cancela suprimento de fundos e dispara evento para registrar devolução."""
    from apps.suprimentos.models import StatusChoicesSuprimentoDeFundos
    from apps.pagamentos.domain_models import StatusProcesso

    _validar_justificativa(justificativa)
    processo = getattr(suprimento, "processo", None)
    if not processo:
        raise ValidationError("O suprimento precisa estar vinculado a um processo para ser cancelado.")

    status_suprimento = ((getattr(getattr(suprimento, "status", None), "status_choice", "") or "").upper())
    suprimento_pago = status_suprimento == "ENCERRADO"
    _validar_dados_devolucao(dados_devolucao, suprimento_pago, "Suprimento de fundos")

    status_cancelado, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(
        status_choice__iexact=StatusProcesso.CANCELADO_ANULADO,
        defaults={"status_choice": StatusProcesso.CANCELADO_ANULADO},
    )

    with transaction.atomic():
        suprimento.status = status_cancelado
        suprimento.save(update_fields=["status"])

        # Dispara evento para o módulo de Pagamentos orquestrar seu Processo Financeiro atrelado
        solicitacao_cancelamento_processo.send(
            sender=suprimento.__class__,
            instance=suprimento,
            processo=processo,
            justificativa=justificativa,
            usuario=usuario,
            dados_devolucao=dados_devolucao,
            tipo_cancelamento_relacional="suprimento_fundos", # Equivalente ao CancelamentoProcessual.TIPO_SUPRIMENTO
            kwargs_relacional={"suprimento": suprimento},
        )