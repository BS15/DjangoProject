"""Funções auxiliares privadas do pagamentos de suprimentos."""

from datetime import datetime
from typing import Any, Mapping

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from commons.shared.text_tools import parse_brl_decimal
from pagamentos.domain_models import StatusChoicesProcesso
from pagamentos.services.processo_documentos import gerar_documentos_automaticos_processo
from suprimentos.models import DespesaSuprimento, StatusChoicesSuprimentoDeFundos

def _suprimento_encerrado(suprimento: Any) -> bool:
    """Indica se o suprimento está em status final de encerramento."""
    return bool(suprimento.status and suprimento.status.status_choice.upper() == "ENCERRADO")


def _salvar_despesa_manual(
    suprimento: Any,
    dados_post: Mapping[str, str],
    arquivo_pdf: UploadedFile | None,
) -> DespesaSuprimento:
    """Valida os dados brutos do POST e persiste uma despesa."""
    data_raw = dados_post.get("data", "").strip()
    detalhamento = dados_post.get("detalhamento", "").strip()
    valor_raw = dados_post.get("valor", "").strip()

    if not (data_raw and detalhamento and valor_raw):
        raise ValidationError("Dados incompletos para registrar despesa.")

    try:
        data_obj = datetime.strptime(data_raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError("Data da despesa inválida.") from exc

    valor = parse_brl_decimal(valor_raw)
    if valor is None:
        raise ValidationError("Valor da despesa inválido.")

    return DespesaSuprimento.objects.create(
        suprimento=suprimento,
        data=data_obj,
        estabelecimento=dados_post.get("estabelecimento"),
        detalhamento=detalhamento,
        nota_fiscal=dados_post.get("nota_fiscal"),
        valor=valor,
        arquivo=arquivo_pdf,
    )


def _atualizar_status_apos_fechamento(suprimento: Any) -> None:
    """Atualiza status do suprimento e do processo vinculado após o fechamento da prestação."""
    with transaction.atomic():
        processo = suprimento.processo
        if processo:
            status_anterior = processo.status.status_choice if processo.status else ""
            status_conferencia, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact="PAGO - EM CONFERÊNCIA",
                defaults={"status_choice": "PAGO - EM CONFERÊNCIA"},
            )
            processo.status = status_conferencia
            processo.save(update_fields=["status"])
            gerar_documentos_automaticos_processo(
                processo,
                status_anterior,
                "PAGO - EM CONFERÊNCIA",
            )

        status_encerrado, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(status_choice="ENCERRADO")
        suprimento.status = status_encerrado
        suprimento.save(update_fields=["status"])
