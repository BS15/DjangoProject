"""Serviços de cancelamento para o domínio de verbas indenizatórias."""

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


def cancelar_verba(verba, justificativa: str, usuario, dados_devolucao: dict | None = None):
    """Cancela verba indenizatória e dispara evento para registrar devolução."""
    from apps.verbas_indenizatorias.models import (
        AuxilioRepresentacao,
        Diaria,
        Jeton,
        ReembolsoCombustivel,
    )

    _validar_justificativa(justificativa)
    processo = getattr(verba, "processo", None)
    if not processo and hasattr(verba, "diaria") and verba.diaria:
        processo = verba.diaria.processo
    if not processo:
        raise ValidationError("A verba precisa estar vinculada a um processo para ser cancelada.")

    status_verba = ((getattr(getattr(verba, "status", None), "status_choice", "") or "").upper())
    verba_paga = status_verba == "PAGA"
    _validar_dados_devolucao(dados_devolucao, verba_paga, "Verba indenizatória")

    tipo_cancelamento = None
    kwargs_cancelamento = {}

    if isinstance(verba, Diaria):
        tipo_cancelamento = "verbas_diaria" # Equivalente local
        kwargs_cancelamento["diaria"] = verba
    elif isinstance(verba, ReembolsoCombustivel):
        tipo_cancelamento = "verbas_reembolso"
        kwargs_cancelamento["reembolso"] = verba
    elif isinstance(verba, Jeton):
        tipo_cancelamento = "verbas_jeton"
        kwargs_cancelamento["jeton"] = verba
    elif isinstance(verba, AuxilioRepresentacao):
        tipo_cancelamento = "verbas_auxilio"
        kwargs_cancelamento["auxilio"] = verba
    else:
        raise ValidationError("Tipo de verba não suportado para cancelamento.")

    with transaction.atomic():
        verba.definir_status("CANCELADA - ANULADA", autorizada=False)

        # Dispara evento para o módulo de Pagamentos orquestrar seu Processo Financeiro atrelado
        solicitacao_cancelamento_processo.send(
            sender=verba.__class__,
            instance=verba,
            processo=processo,
            justificativa=justificativa,
            usuario=usuario,
            dados_devolucao=dados_devolucao,
            tipo_cancelamento_relacional=tipo_cancelamento,
            kwargs_relacional=kwargs_cancelamento,
        )