"""Serviços canônicos para cancelamento de processos, verbas e suprimentos."""

from django.core.exceptions import ValidationError
from django.db import transaction

from pagamentos.domain_models import (
    CancelamentoProcessual,
    STATUS_PROCESSO_PAGOS_E_POSTERIORES,
    StatusChoicesProcesso,
    StatusProcesso,
)


def _status_processo(processo) -> str:
    if not processo or not processo.status:
        return ""
    return (processo.status.opcao_status or "").upper()


def _processo_pago_ou_posterior(processo) -> bool:
    return _status_processo(processo) in STATUS_PROCESSO_PAGOS_E_POSTERIORES


def _set_processo_cancelado(processo):
    status_cancelado, _ = StatusChoicesProcesso.objects.get_or_create(
        opcao_status__iexact=StatusProcesso.CANCELADO_ANULADO,
        defaults={"opcao_status": StatusProcesso.CANCELADO_ANULADO},
    )
    processo.status = status_cancelado
    processo.save(update_fields=["status"])


def _validar_justificativa(justificativa: str):
    if not (justificativa or "").strip():
        raise ValidationError("A justificativa do cancelamento é obrigatória.")


def _exigir_sem_processo_pago(processo):
    if _processo_pago_ou_posterior(processo):
        raise ValidationError("Não é permitido cancelar processos que já foram pagos.")


def _exigir_devolucao_quando_pago(processo, foi_pago: bool, entidade_label: str):
    if foi_pago and not processo.devolucoes.exists():
        raise ValidationError(
            f"{entidade_label} com status pago só pode ser cancelado após registro de devolução."
        )


def registrar_cancelamento_processo(processo, justificativa: str, usuario):
    _validar_justificativa(justificativa)
    _exigir_sem_processo_pago(processo)
    with transaction.atomic():
        _set_processo_cancelado(processo)
        CancelamentoProcessual.objects.create(
            processo=processo,
            tipo=CancelamentoProcessual.TIPO_PROCESSO,
            justificativa=justificativa.strip(),
            registrado_por=usuario,
        )


def cancelar_verba(verba, justificativa: str, usuario):
    from verbas_indenizatorias.models import (
        AuxilioRepresentacao,
        Diaria,
        Jeton,
        ReembolsoCombustivel,
        StatusChoicesVerbasIndenizatorias,
    )

    _validar_justificativa(justificativa)
    processo = getattr(verba, "processo", None)
    if not processo and hasattr(verba, "diaria") and verba.diaria:
        processo = verba.diaria.processo
    if not processo:
        raise ValidationError("A verba precisa estar vinculada a um processo para ser cancelada.")

    _exigir_sem_processo_pago(processo)

    status_verba = ((getattr(getattr(verba, "status", None), "status_choice", "") or "").upper())
    verba_paga = status_verba == "PAGA"
    _exigir_devolucao_quando_pago(processo, verba_paga, "Verba indenizatória")

    tipo_cancelamento = None
    kwargs_cancelamento = {}

    if isinstance(verba, Diaria):
        tipo_cancelamento = CancelamentoProcessual.TIPO_DIARIA
        kwargs_cancelamento["diaria"] = verba
    elif isinstance(verba, ReembolsoCombustivel):
        tipo_cancelamento = CancelamentoProcessual.TIPO_REEMBOLSO
        kwargs_cancelamento["reembolso"] = verba
    elif isinstance(verba, Jeton):
        tipo_cancelamento = CancelamentoProcessual.TIPO_JETON
        kwargs_cancelamento["jeton"] = verba
    elif isinstance(verba, AuxilioRepresentacao):
        tipo_cancelamento = CancelamentoProcessual.TIPO_AUXILIO
        kwargs_cancelamento["auxilio"] = verba
    else:
        raise ValidationError("Tipo de verba não suportado para cancelamento.")

    status_cancelado, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
        status_choice__iexact=StatusProcesso.CANCELADO_ANULADO,
        defaults={"status_choice": StatusProcesso.CANCELADO_ANULADO},
    )

    with transaction.atomic():
        _set_processo_cancelado(processo)
        verba.status = status_cancelado
        update_fields = ["status"]
        if hasattr(verba, "autorizada"):
            verba.autorizada = False
            update_fields.append("autorizada")
        verba.save(update_fields=update_fields)

        CancelamentoProcessual.objects.create(
            processo=processo,
            tipo=tipo_cancelamento,
            justificativa=justificativa.strip(),
            registrado_por=usuario,
            **kwargs_cancelamento,
        )


def cancelar_suprimento(suprimento, justificativa: str, usuario):
    from suprimentos.models import StatusChoicesSuprimentoDeFundos

    _validar_justificativa(justificativa)
    processo = getattr(suprimento, "processo", None)
    if not processo:
        raise ValidationError("O suprimento precisa estar vinculado a um processo para ser cancelado.")

    _exigir_sem_processo_pago(processo)

    status_suprimento = ((getattr(getattr(suprimento, "status", None), "status_choice", "") or "").upper())
    suprimento_pago = status_suprimento == "ENCERRADO"
    _exigir_devolucao_quando_pago(processo, suprimento_pago, "Suprimento de fundos")

    status_cancelado, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(
        status_choice__iexact=StatusProcesso.CANCELADO_ANULADO,
        defaults={"status_choice": StatusProcesso.CANCELADO_ANULADO},
    )

    with transaction.atomic():
        _set_processo_cancelado(processo)
        suprimento.status = status_cancelado
        suprimento.save(update_fields=["status"])
        CancelamentoProcessual.objects.create(
            processo=processo,
            tipo=CancelamentoProcessual.TIPO_SUPRIMENTO,
            justificativa=justificativa.strip(),
            registrado_por=usuario,
            suprimento=suprimento,
        )
