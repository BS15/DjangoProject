"""Serviços canônicos de revisão de processos no pós-pagamento."""

from django.db import transaction
from django.db.models import Q

from pagamentos.domain_models import Processo, StatusChoicesPendencias, TiposDeDocumento


def obter_tipos_documento_para_processo(processo):
    """Retorna tipos documentais ativos válidos para o processo informado."""
    return TiposDeDocumento.objects.filter(ativo=True).filter(
        Q(tipo_pagamento=processo.tipo_pagamento) | Q(tipo_pagamento__isnull=True)
    )


def registrar_recusa_processo(*, request_user, processo, form, status_devolucao):
    """Registra pendência de recusa e devolve o processo ao status anterior."""
    with transaction.atomic():
        processo_lock = Processo.objects.select_for_update().get(pk=processo.pk)
        pendencia = form.save(commit=False)
        pendencia.processo = processo_lock
        status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
            opcao_status__iexact="A RESOLVER",
            defaults={"opcao_status": "A RESOLVER"},
        )
        pendencia.status = status_pendencia
        pendencia.save()
        processo_lock.avancar_status(status_devolucao, usuario=request_user)
    return processo_lock


def salvar_documentos_sem_exclusao(doc_formset, processo):
    """Salva apenas inclusões/atualizações de documentos, ignorando exclusões."""
    for form in doc_formset.forms:
        if not form.cleaned_data:
            continue
        should_delete = form.cleaned_data.get("DELETE", False)
        is_existing = bool(form.instance.pk)
        if should_delete:
            continue
        if form.has_changed() or not is_existing:
            instance = form.save(commit=False)
            instance.processo = processo
            instance.save()


def persistir_revisao_processo(
    *,
    processo,
    doc_formset,
    pendencia_formset,
    lock_documents=False,
    approve_status=None,
    usuario=None,
):
    """Persiste alterações da revisão e opcionalmente aprova transição de status."""
    with transaction.atomic():
        processo_lock = Processo.objects.select_for_update().get(pk=processo.pk)
        salvar_documentos_sem_exclusao(doc_formset, processo_lock)
        if lock_documents:
            processo_lock.documentos.all().update(imutavel=True)

        pendencia_formset.instance = processo_lock
        pendencia_formset.save()

        if approve_status:
            processo_lock.avancar_status(approve_status, usuario=usuario)

    return processo_lock


def aprovar_processo_por_id(*, processo_id, new_status, usuario):
    """Aplica aprovação de processo com lock pessimista para consistência."""
    with transaction.atomic():
        processo = Processo.objects.select_for_update().get(id=processo_id)
        processo.avancar_status(new_status, usuario=usuario)
    return processo


__all__ = [
    "aprovar_processo_por_id",
    "obter_tipos_documento_para_processo",
    "persistir_revisao_processo",
    "registrar_recusa_processo",
    "salvar_documentos_sem_exclusao",
]