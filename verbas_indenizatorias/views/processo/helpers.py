import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse

from pagamentos.forms import PendenciaFormSet, ProcessoForm
from pagamentos.models import TiposDePagamento
from verbas_indenizatorias.models import AuxilioRepresentacao, Diaria, Jeton, ReembolsoCombustivel
from ..shared.registry import _get_tipos_documento_verbas

logger = logging.getLogger(__name__)


def _agregar_total(queryset, field_name):
    """Retorna total decimal agregado com fallback para 0."""
    return queryset.aggregate(
        total=Coalesce(Sum(field_name), 0, output_field=DecimalField(max_digits=15, decimal_places=2))
    )["total"]


def _calcular_totais_verbas(processo):
    """Calcula total consolidado das verbas vinculadas ao processo."""
    total_diarias = _agregar_total(Diaria.objects.filter(processo=processo), "valor_total")
    total_reembolsos = _agregar_total(ReembolsoCombustivel.objects.filter(processo=processo), "valor_total")
    total_jetons = _agregar_total(Jeton.objects.filter(processo=processo), "valor_total")
    total_auxilios = _agregar_total(AuxilioRepresentacao.objects.filter(processo=processo), "valor_total")

    total_geral = total_diarias + total_reembolsos + total_jetons + total_auxilios
    return {
        "total_diarias": total_diarias,
        "total_reembolsos": total_reembolsos,
        "total_jetons": total_jetons,
        "total_auxilios": total_auxilios,
        "total_geral": total_geral,
    }


def _forcar_campos_canonicos_processo_verbas(processo):
    """Aplica defaults canônicos para processos de verbas indenizatórias."""
    totais = _calcular_totais_verbas(processo)
    tipo_pagamento_verbas, _ = TiposDePagamento.objects.get_or_create(
        tipo_pagamento__iexact="VERBAS INDENIZATÓRIAS",
        defaults={"tipo_pagamento": "VERBAS INDENIZATÓRIAS"},
    )

    update_fields = []
    if processo.extraorcamentario:
        processo.extraorcamentario = False
        update_fields.append("extraorcamentario")

    if processo.tipo_pagamento_id != tipo_pagamento_verbas.id:
        processo.tipo_pagamento = tipo_pagamento_verbas
        update_fields.append("tipo_pagamento")

    if processo.valor_bruto != totais["total_geral"]:
        processo.valor_bruto = totais["total_geral"]
        update_fields.append("valor_bruto")

    if processo.valor_liquido != totais["total_geral"]:
        processo.valor_liquido = totais["total_geral"]
        update_fields.append("valor_liquido")

    if update_fields:
        processo.save(update_fields=update_fields)

    return totais


def _instanciar_formularios_processo_verbas(request, processo):
    """Constroi formulários de edição do processo de verbas conforme o método."""
    if request.method == "POST":
        return (
            ProcessoForm(request.POST, instance=processo, prefix="processo"),
            PendenciaFormSet(request.POST, instance=processo, prefix="pendencia"),
        )

    return (
        ProcessoForm(instance=processo, prefix="processo"),
        PendenciaFormSet(instance=processo, prefix="pendencia"),
    )


def _salvar_formularios_processo_verbas(request, *, processo_form, pendencia_formset):
    """Persiste formulários do processo de verbas com tratamento transacional."""
    if not (processo_form.is_valid() and pendencia_formset.is_valid()):
        messages.error(request, "Verifique os erros no formulário.")
        return None

    try:
        with transaction.atomic():
            processo = processo_form.save()
            pendencia_formset.save()
            _forcar_campos_canonicos_processo_verbas(processo)
    except (ValidationError, DatabaseError, TypeError, ValueError) as exc:
        logger.exception("Erro ao atualizar processo de verbas", exc_info=exc)
        messages.error(request, "Erro interno ao salvar as alterações.")
        return None

    messages.success(request, f"Processo #{processo.id} atualizado com sucesso!")
    return processo


def _contar_docs_verbas(diarias, reembolsos, jetons, auxilios):
    """Conta total de documentos anexados a todas as verbas do processo."""
    total = 0
    for item in diarias:
        prestacao = getattr(item, "prestacao_contas", None)
        if prestacao:
            total += len(prestacao.documentos.all())
    for qs in (reembolsos, jetons, auxilios):
        for item in qs:
            total += len(item.documentos.all())
    return total


def _montar_cards_documentos_verba(*, diarias, reembolsos, jetons, auxilios):
    """Normaliza docs das verbas vinculadas ao processo sem duplicar registros em Processo."""
    config = [
        {
            "queryset": diarias,
            "titulo": "Diária",
            "gerenciar_url": "gerenciar_diaria",
            "border_class": "border-primary",
            "btn_class": "btn-outline-primary",
            "is_diaria": True,
        },
        {
            "queryset": reembolsos,
            "titulo": "Reembolso",
            "gerenciar_url": "gerenciar_reembolso",
            "border_class": "border-success",
            "btn_class": "btn-outline-success",
            "is_diaria": False,
        },
        {
            "queryset": jetons,
            "titulo": "Jeton",
            "gerenciar_url": "gerenciar_jeton",
            "border_class": "border-warning",
            "btn_class": "btn-outline-warning",
            "is_diaria": False,
        },
        {
            "queryset": auxilios,
            "titulo": "Auxílio",
            "gerenciar_url": "gerenciar_auxilio",
            "border_class": "border-info",
            "btn_class": "btn-outline-info",
            "is_diaria": False,
        },
    ]

    cards = []
    for cfg in config:
        for item in cfg["queryset"]:
            if cfg["is_diaria"]:
                prestacao = getattr(item, "prestacao_contas", None)
                documentos = list(prestacao.documentos.all()) if prestacao else []
            else:
                documentos = list(item.documentos.all())

            cards.append(
                {
                    "titulo": f"{cfg['titulo']} #{item.id} - {getattr(item.beneficiario, 'nome', '-')}",
                    "gerenciar_url": reverse(cfg["gerenciar_url"], kwargs={"pk": item.id}),
                    "documentos": documentos,
                    "border_class": cfg["border_class"],
                    "btn_class": cfg["btn_class"],
                }
            )

    if not cards:
        return [], "Nenhuma verba vinculada a este processo."

    return cards, ""


def _montar_contexto_processo_verbas(processo, *, processo_form=None, pendencia_formset=None):
    """Monta contexto consolidado usado no hub e spokes de verbas."""
    totais = _forcar_campos_canonicos_processo_verbas(processo)

    diarias = Diaria.objects.filter(processo=processo).select_related("beneficiario", "status").prefetch_related("prestacao_contas__documentos__tipo")
    reembolsos = ReembolsoCombustivel.objects.filter(processo=processo).select_related("beneficiario", "status").prefetch_related("documentos__tipo")
    jetons = Jeton.objects.filter(processo=processo).select_related("beneficiario", "status").prefetch_related("documentos__tipo")
    auxilios = AuxilioRepresentacao.objects.filter(processo=processo).select_related("beneficiario", "status").prefetch_related("documentos__tipo")

    # Detecta o único tipo de verba vinculado (agrupamento é sempre mono-tipo).
    if diarias.exists():
        tipo_verba_ativo = "diarias"
    elif reembolsos.exists():
        tipo_verba_ativo = "reembolsos"
    elif jetons.exists():
        tipo_verba_ativo = "jetons"
    elif auxilios.exists():
        tipo_verba_ativo = "auxilios"
    else:
        tipo_verba_ativo = None

    total_itens = diarias.count() + reembolsos.count() + jetons.count() + auxilios.count()

    documentos_verba_cards, documentos_verba_empty_message = _montar_cards_documentos_verba(
        diarias=diarias,
        reembolsos=reembolsos,
        jetons=jetons,
        auxilios=auxilios,
    )

    # Contagens de documentos para badges no hub.
    total_docs_processo = (
        processo.documentos.count()
        + processo.documentos_orcamentarios.count()
        + processo.comprovantes_pagamento.count()
    )
    total_docs_verbas = _contar_docs_verbas(diarias, reembolsos, jetons, auxilios)

    return {
        "processo": processo,
        "processo_form": processo_form,
        "pendencia_formset": pendencia_formset,
        "diarias": diarias,
        "reembolsos": reembolsos,
        "jetons": jetons,
        "auxilios": auxilios,
        "tipo_verba_ativo": tipo_verba_ativo,
        "documentos_verba_cards": documentos_verba_cards,
        "documentos_verba_empty_message": documentos_verba_empty_message,
        "total_itens": total_itens,
        "total_docs_processo": total_docs_processo,
        "total_docs_verbas": total_docs_verbas,
        "totais": totais,
        "tipos_documento": _get_tipos_documento_verbas(),
    }
