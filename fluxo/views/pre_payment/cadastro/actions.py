"""Acoes POST da etapa de documentos fiscais do cadastro."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from fluxo.domain_models import Processo
from .forms import DocumentoFormSet, DocumentoOrcamentarioFormSet, PendenciaFormSet, ProcessoForm
from ..helpers import (
    _redirect_seguro_ou_fallback,
    _salvar_processo_completo,
    _validar_regras_edicao_processo,
)


logger = logging.getLogger(__name__)


def _get_status_inicial(processo):
    return processo.status.status_choice.upper() if processo.status else ""


def _obter_contexto_edicao(request, pk):
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = _get_status_inicial(processo)
    redirecionamento, somente_documentos = _validar_regras_edicao_processo(request, processo, status_inicial)
    return processo, status_inicial, redirecionamento, somente_documentos


def _salvar_formsets_em_transacao(*formsets):
    with transaction.atomic():
        for formset in formsets:
            formset.save()


def _status_bloqueia_exclusao_nota_fiscal(processo):
    """Indica se o processo já está em estágio onde exclusão de nota é proibida."""
    if not processo.status:
        return False

    status_atual = (processo.status.status_choice or "").upper()
    prefixos_bloqueados = ("PAGO", "CONTABILIZADO", "APROVADO", "ARQUIVADO")
    return any(status_atual.startswith(prefixo) for prefixo in prefixos_bloqueados)


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
@require_POST
def add_process_action(request):
    """Persiste a capa inicial do processo."""
    processo_form = ProcessoForm(request.POST, prefix="processo")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER", "")
    trigger_a_empenhar = request.POST.get("trigger_a_empenhar") == "on"

    if not processo_form.is_valid():
        messages.error(request, "Verifique os erros no formulário da capa do processo.")
        return redirect("add_process")

    is_extra = processo_form.cleaned_data.get("extraorcamentario")
    try:
        def mutator(processo_instancia):
            processo_instancia.definir_status_inicial(trigger_a_empenhar)

        processo = _salvar_processo_completo(processo_form, mutator_func=mutator)
        messages.success(
            request,
            f"Processo #{processo.id} inserido com sucesso! Complete documentos, fiscais e pendências na etapa de edição.",
        )
        return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", processo.id)
    except (DatabaseError, TypeError, ValueError):
        logger.exception("Erro crítico ao salvar processo na criação")
        messages.error(request, "Ocorreu um erro interno ao salvar no banco de dados.")
        return redirect("add_process")


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
@require_POST
def editar_processo_capa_action(request, pk):
    """Persiste alterações da capa do processo."""
    processo, status_inicial, redirecionamento, somente_documentos = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento
    if somente_documentos:
        messages.error(request, "Neste status, apenas documentos podem ser alterados. Use a tela específica de documentos.")
        return redirect("editar_processo_documentos", pk=pk)

    processo_form = ProcessoForm(request.POST, instance=processo, prefix="processo")
    next_url = request.POST.get("next") or ""

    if not processo_form.is_valid():
        messages.error(request, "Verifique os erros na capa do processo.")
        return redirect("editar_processo_capa", pk=pk)

    confirmar_extra = request.POST.get("confirmar_extra_orcamentario") == "on"
    try:
        def _mutator(proc):
            proc.converter_para_extraorcamentario(confirmar_extra)

        processo_saved = _salvar_processo_completo(processo_form, mutator_func=_mutator)
        messages.success(request, f"Capa do Processo #{processo_saved.id} atualizada com sucesso!")
        return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", processo_saved.id)
    except (DatabaseError, TypeError, ValueError):
        logger.exception("Erro ao atualizar capa do processo %s", pk)
        messages.error(request, "Erro interno ao salvar a capa do processo.")
        return redirect("editar_processo_capa", pk=pk)


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
@require_POST
def editar_processo_documentos_action(request, pk):
    """Persiste anexos e documentos orçamentários do processo."""
    processo, _, redirecionamento, _ = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=processo, prefix="documento")
    documento_orcamentario_formset = DocumentoOrcamentarioFormSet(request.POST, instance=processo, prefix="docorc")
    next_url = request.POST.get("next") or ""

    if not (documento_formset.is_valid() and documento_orcamentario_formset.is_valid()):
        messages.error(request, "Verifique os erros nos documentos e dados orçamentários.")
        return redirect("editar_processo_documentos", pk=pk)

    try:
        _salvar_formsets_em_transacao(documento_formset, documento_orcamentario_formset)
        messages.success(request, f"Documentos do Processo #{pk} atualizados com sucesso!")
        return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", pk)
    except (DatabaseError, TypeError, ValueError, OSError):
        logger.exception("Erro ao atualizar documentos do processo %s", pk)
        messages.error(request, "Erro interno ao salvar os documentos.")
        return redirect("editar_processo_documentos", pk=pk)


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
@require_POST
def editar_processo_pendencias_action(request, pk):
    """Persiste pendências administrativas do processo."""
    processo, _, redirecionamento, somente_documentos = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento
    if somente_documentos:
        messages.error(request, "Neste status, apenas documentos podem ser alterados.")
        return redirect("editar_processo_documentos", pk=pk)

    pendencia_formset = PendenciaFormSet(request.POST, instance=processo, prefix="pendencia")
    next_url = request.POST.get("next") or ""

    if not pendencia_formset.is_valid():
        messages.error(request, "Verifique os erros nas pendências.")
        return redirect("editar_processo_pendencias", pk=pk)

    try:
        _salvar_formsets_em_transacao(pendencia_formset)
        messages.success(request, f"Pendências do Processo #{pk} atualizadas com sucesso!")
        return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", pk)
    except (DatabaseError, TypeError, ValueError):
        logger.exception("Erro ao atualizar pendências do processo %s", pk)
        messages.error(request, "Erro interno ao salvar as pendências.")
        return redirect("editar_processo_pendencias", pk=pk)


__all__ = [
    "add_process_action",
    "editar_processo_capa_action",
    "editar_processo_documentos_action",
    "editar_processo_pendencias_action",
    "_status_bloqueia_exclusao_nota_fiscal",
]
