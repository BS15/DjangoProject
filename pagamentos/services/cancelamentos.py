"""Serviços canônicos para cancelamento de processos, verbas e suprimentos."""

from django.core.exceptions import ValidationError
from django.db import transaction

from commons.shared.text_tools import parse_brl_decimal

from pagamentos.domain_models import (
    CancelamentoProcessual,
    DevolucaoProcessual,
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


def _criar_devolucao(processo, dados_devolucao: dict, motivo_padrao: str):
    """Cria o registro de DevolucaoProcessual dentro de uma transação atômica já aberta."""
    motivo = (dados_devolucao.get("motivo") or "").strip() or motivo_padrao
    DevolucaoProcessual.objects.create(
        processo=processo,
        valor_devolvido=dados_devolucao["valor_devolvido"],
        data_devolucao=dados_devolucao["data_devolucao"],
        motivo=motivo,
        comprovante=dados_devolucao["comprovante"],
    )


def registrar_cancelamento_processo(processo, justificativa: str, usuario, dados_devolucao: dict | None = None):
    _validar_justificativa(justificativa)
    processo_pago = _processo_pago_ou_posterior(processo)
    _validar_dados_devolucao(dados_devolucao, processo_pago, "Processo")

    with transaction.atomic():
        if processo_pago and dados_devolucao:
            _criar_devolucao(
                processo,
                dados_devolucao,
                motivo_padrao=f"Devolução referente ao cancelamento do Processo #{processo.pk}.",
            )
        _set_processo_cancelado(processo)
        CancelamentoProcessual.objects.create(
            processo=processo,
            tipo=CancelamentoProcessual.TIPO_PROCESSO,
            justificativa=justificativa.strip(),
            registrado_por=usuario,
        )


def cancelar_verba(verba, justificativa: str, usuario, dados_devolucao: dict | None = None):
    from verbas_indenizatorias.models import (
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

    with transaction.atomic():
        if verba_paga and dados_devolucao:
            _criar_devolucao(
                processo,
                dados_devolucao,
                motivo_padrao=f"Devolução referente ao cancelamento da verba #{verba.pk}.",
            )
        _set_processo_cancelado(processo)
        verba.definir_status(StatusProcesso.CANCELADO_ANULADO, autorizada=False)

        CancelamentoProcessual.objects.create(
            processo=processo,
            tipo=tipo_cancelamento,
            justificativa=justificativa.strip(),
            registrado_por=usuario,
            **kwargs_cancelamento,
        )


def cancelar_suprimento(suprimento, justificativa: str, usuario, dados_devolucao: dict | None = None):
    from suprimentos.models import StatusChoicesSuprimentoDeFundos

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
        if suprimento_pago and dados_devolucao:
            _criar_devolucao(
                processo,
                dados_devolucao,
                motivo_padrao=f"Devolução referente ao cancelamento do Suprimento #{suprimento.pk}.",
            )
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


def extrair_dados_devolucao_do_post(request) -> dict | None:
    """Extrai campos de devolução do POST/FILES do request.

    Retorna um dict com os dados se `valor_devolvido` foi preenchido, ou None.
    Usado pelas actions de cancelamento que precisam criar devolução atomicamente.
    """
    valor_raw = (request.POST.get("valor_devolvido") or "").strip()
    if not valor_raw:
        return None
    return {
        "valor_devolvido": parse_brl_decimal(valor_raw),
        "data_devolucao": (request.POST.get("data_devolucao") or "").strip() or None,
        "motivo": (request.POST.get("motivo_devolucao") or "").strip(),
        "comprovante": request.FILES.get("comprovante_devolucao"),
    }
