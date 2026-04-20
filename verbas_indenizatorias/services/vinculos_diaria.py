"""Serviços canônicos para vínculo/desvínculo de diárias com processos existentes."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce

from pagamentos.domain_models import STATUS_PROCESSO_PRE_AUTORIZACAO, TiposDePagamento
from verbas_indenizatorias.models import AuxilioRepresentacao, Diaria, Jeton, ReembolsoCombustivel

_PROCESSO_STATUS_PRE_AUTORIZACAO_VALUES = {status.value for status in STATUS_PROCESSO_PRE_AUTORIZACAO}


def _agregar_total(queryset, field_name):
    return queryset.aggregate(
        total=Coalesce(Sum(field_name), 0, output_field=DecimalField(max_digits=15, decimal_places=2))
    )["total"]


def processo_em_pre_autorizacao(processo):
    if not processo or not processo.status:
        return False
    return (processo.status.opcao_status or "").upper() in _PROCESSO_STATUS_PRE_AUTORIZACAO_VALUES


def _obter_tipo_pagamento_verbas():
    tipo_pagamento_verbas, _ = TiposDePagamento.objects.get_or_create(
        tipo_pagamento__iexact="VERBAS INDENIZATÓRIAS",
        defaults={"tipo_pagamento": "VERBAS INDENIZATÓRIAS"},
    )
    return tipo_pagamento_verbas


def _recalcular_totais_processo_verbas(processo):
    if not processo:
        return

    total_diarias = _agregar_total(Diaria.objects.filter(processo=processo), "valor_total")
    total_reembolsos = _agregar_total(ReembolsoCombustivel.objects.filter(processo=processo), "valor_total")
    total_jetons = _agregar_total(Jeton.objects.filter(processo=processo), "valor_total")
    total_auxilios = _agregar_total(AuxilioRepresentacao.objects.filter(processo=processo), "valor_total")
    total_geral = total_diarias + total_reembolsos + total_jetons + total_auxilios

    tipo_pagamento_verbas = _obter_tipo_pagamento_verbas()

    update_fields = []
    if processo.valor_bruto != total_geral:
        processo.valor_bruto = total_geral
        update_fields.append("valor_bruto")
    if processo.valor_liquido != total_geral:
        processo.valor_liquido = total_geral
        update_fields.append("valor_liquido")
    if processo.tipo_pagamento_id != tipo_pagamento_verbas.id:
        processo.tipo_pagamento = tipo_pagamento_verbas
        update_fields.append("tipo_pagamento")
    if processo.extraorcamentario:
        processo.extraorcamentario = False
        update_fields.append("extraorcamentario")

    if update_fields:
        processo.save(update_fields=update_fields)


@transaction.atomic
def vincular_diaria_em_processo_existente(diaria, processo):
    processo_anterior = diaria.processo

    if processo and not processo_em_pre_autorizacao(processo):
        raise ValidationError("Vinculação permitida apenas até a autorização do processo.")
    if processo_anterior and not processo_em_pre_autorizacao(processo_anterior):
        raise ValidationError("A diária já está em processo após autorização e não pode ser remanejada.")

    diaria.processo = processo
    diaria.save(update_fields=["processo"])

    _recalcular_totais_processo_verbas(processo)
    if processo_anterior and processo_anterior != processo:
        _recalcular_totais_processo_verbas(processo_anterior)

    return diaria


@transaction.atomic
def desvincular_diaria_do_processo(diaria):
    processo_anterior = diaria.processo
    if not processo_anterior:
        return diaria
    if not processo_em_pre_autorizacao(processo_anterior):
        raise ValidationError("Desvinculação permitida apenas até a autorização do processo.")

    diaria.processo = None
    diaria.save(update_fields=["processo"])
    _recalcular_totais_processo_verbas(processo_anterior)
    return diaria
