"""Funções auxiliares privadas do fluxo de suprimentos."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from ...forms import SuprimentoForm
from ...models.segments.core import Processo
from ...models.segments.documents import DespesaSuprimento
from ...models.segments.parametrizations import (
    FormasDePagamento,
    StatusChoicesProcesso,
    StatusChoicesSuprimentoDeFundos,
    TiposDePagamento,
)
from ...utils import parse_brl_decimal


def _suprimento_encerrado(suprimento: Any) -> bool:
    """Indica se o suprimento está em status final de encerramento."""
    return bool(suprimento.status and suprimento.status.status_choice.upper() == "ENCERRADO")


def _persistir_suprimento_com_processo(form_suprimento: SuprimentoForm) -> Any:
    """Persiste suprimento e cria o processo financeiro vinculado em transação atômica."""
    with transaction.atomic():
        suprimento: Any = form_suprimento.save(commit=False)
        status_aberto, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(status_choice="ABERTO")
        suprimento.status = status_aberto
        suprimento.save()

        nome_lotacao = suprimento.lotacao or "Unidade Não Especificada"
        detalhamento = (
            f"Referente a suprimento de fundos da {nome_lotacao} "
            f"- mês {suprimento.data_saida.month}/{suprimento.data_saida.year}"
        )

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
        return suprimento


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
            processo.disparar_documentos_automaticos_por_status(
                status_anterior,
                "PAGO - EM CONFERÊNCIA",
            )

        status_encerrado, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(status_choice="ENCERRADO")
        suprimento.status = status_encerrado
        suprimento.save(update_fields=["status"])
