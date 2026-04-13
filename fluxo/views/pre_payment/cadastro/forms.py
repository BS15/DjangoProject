"""Views de formulario (GET+POST) da etapa de cadastro/edicao."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import DatabaseError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from fluxo.forms import DocumentoFormSet, DocumentoOrcamentarioFormSet, PendenciaFormSet, ProcessoForm
from fluxo.domain_models import Processo
from ..helpers import (
    _aplicar_confirmacao_extra_orcamentario,
    _configurar_status_novo_processo,
    _redirect_seguro_ou_fallback,
    _salvar_processo_completo,
    _validar_regras_edicao_processo,
)


logger = logging.getLogger(__name__)


def _get_request_payloads(request):
    """Retorna POST/FILES apenas em submissões."""
    if request.method != "POST":
        return None, None
    return request.POST, request.FILES


def _get_next_url(request, *, allow_referer=False):
    """Resolve a URL de retorno priorizando POST, depois GET e opcionalmente referer."""
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not next_url and allow_referer:
        next_url = request.META.get("HTTP_REFERER", "")
    return next_url


def _get_status_inicial(processo):
    """Normaliza o status textual do processo para uso nas guards da UI."""
    return processo.status.status_choice.upper() if processo.status else ""


def _obter_contexto_edicao(request, pk):
    """Carrega processo, status inicial e resultado das regras de guarda da edição."""
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = _get_status_inicial(processo)
    redirecionamento, somente_documentos = _validar_regras_edicao_processo(request, processo, status_inicial)
    return processo, status_inicial, redirecionamento, somente_documentos


def _redirecionar_post_hub(request, pk):
    """Encaminha submissões legadas do hub para o spoke correspondente."""
    if any(key.startswith("documento-") for key in request.POST.keys()) or request.FILES:
        messages.info(request, "A edição foi modularizada. Você foi redirecionado para o spoke de documentos.")
        return redirect("editar_processo_documentos", pk=pk)
    if any(key.startswith("pendencia-") for key in request.POST.keys()):
        messages.info(request, "A edição foi modularizada. Você foi redirecionado para o spoke de pendências.")
        return redirect("editar_processo_pendencias", pk=pk)
    if any(key.startswith("processo-") for key in request.POST.keys()):
        messages.info(request, "A edição foi modularizada. Você foi redirecionado para o spoke da capa.")
        return redirect("editar_processo_capa", pk=pk)
    messages.info(request, "Use os módulos de edição disponíveis no hub do processo.")
    return redirect("editar_processo", pk=pk)


def _montar_contexto_hub(processo, status_inicial, somente_documentos):
    """Monta os indicadores resumidos exibidos no hub de edição."""
    return {
        "processo": processo,
        "status_inicial": status_inicial,
        "somente_documentos": somente_documentos,
        "aguardando_liquidacao": status_inicial.startswith("AGUARDANDO LIQUIDAÇÃO"),
        "total_documentos": processo.documentos.count(),
        "total_notas": processo.notas_fiscais.count(),
        "notas_nao_atestadas": processo.notas_fiscais.filter(atestada=False).count(),
        "total_pendencias": processo.pendencias.count(),
        "pendencias_abertas": processo.pendencias.filter(status__status_choice__iexact="A RESOLVER").count(),
    }


def _salvar_formsets_em_transacao(*formsets):
    """Persiste os formsets informados em uma única transação atômica."""
    with transaction.atomic():
        for formset in formsets:
            formset.save()


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def add_process_view(request):
    """Cria a capa inicial do processo e encaminha a complementação ao hub."""
    post_data, _ = _get_request_payloads(request)

    processo_form = ProcessoForm(post_data, prefix="processo")
    next_url = _get_next_url(request, allow_referer=True)

    if request.method == "POST":
        trigger_a_empenhar = request.POST.get("trigger_a_empenhar") == "on"

        if processo_form.is_valid():
            is_extra = processo_form.cleaned_data.get("extraorcamentario")

            try:
                def mutator(processo_instancia):
                    _configurar_status_novo_processo(processo_instancia, trigger_a_empenhar, is_extra)

                processo = _salvar_processo_completo(
                    processo_form,
                    mutator_func=mutator,
                )

                messages.success(
                    request,
                    f"Processo #{processo.id} inserido com sucesso! Complete documentos, fiscais e pendências na etapa de edição.",
                )
                return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", processo.id)
            except (DatabaseError, TypeError, ValueError) as e:
                logger.exception("Erro crítico ao salvar processo na criação")
                messages.error(request, "Ocorreu um erro interno ao salvar no banco de dados.")
        else:
            messages.error(request, "Verifique os erros no formulário da capa do processo.")

    return render(
        request,
        "fluxo/add_process.html",
        {
            "processo_form": processo_form,
            "next_url": next_url,
            "trigger_a_empenhar_checked": request.POST.get("trigger_a_empenhar") == "on",
        },
    )


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def editar_processo(request, pk):
    """Hub de edicao modular do processo."""
    processo, status_inicial, redirecionamento, somente_documentos = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    if request.method == "POST":
        return _redirecionar_post_hub(request, pk)

    context = _montar_contexto_hub(processo, status_inicial, somente_documentos)

    return render(request, "fluxo/editar_processo_hub.html", context)


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def editar_processo_capa_view(request, pk):
    """Spoke de edicao da capa do processo."""
    processo, status_inicial, redirecionamento, somente_documentos = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    if somente_documentos:
        messages.error(
            request,
            "Neste status, apenas documentos podem ser alterados. Use a tela específica de documentos.",
        )
        return redirect("editar_processo_documentos", pk=pk)

    post_data, _ = _get_request_payloads(request)
    next_url = _get_next_url(request)
    processo_form = ProcessoForm(post_data, instance=processo, prefix="processo")

    if request.method == "POST":
        if processo_form.is_valid():
            confirmar_extra = request.POST.get("confirmar_extra_orcamentario") == "on"
            try:
                def _mutator(proc):
                    _aplicar_confirmacao_extra_orcamentario(proc, confirmar_extra, status_inicial)

                processo_saved = _salvar_processo_completo(
                    processo_form,
                    mutator_func=_mutator,
                )
                messages.success(request, f"Capa do Processo #{processo_saved.id} atualizada com sucesso!")
                return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", processo_saved.id)
            except (DatabaseError, TypeError, ValueError) as e:
                logger.exception("Erro ao atualizar capa do processo %s", pk)
                messages.error(request, "Erro interno ao salvar a capa do processo.")
        else:
            messages.error(request, "Verifique os erros na capa do processo.")

    return render(
        request,
        "fluxo/editar_processo_capa.html",
        {
            "processo": processo,
            "processo_form": processo_form,
            "status_inicial": status_inicial,
            "next_url": next_url,
        },
    )


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def editar_processo_documentos_view(request, pk):
    """Spoke de edicao de anexos do processo."""
    processo, status_inicial, redirecionamento, _ = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    post_data, files_data = _get_request_payloads(request)
    next_url = _get_next_url(request)
    documento_formset = DocumentoFormSet(post_data, files_data, instance=processo, prefix="documento")
    documento_orcamentario_formset = DocumentoOrcamentarioFormSet(post_data, instance=processo, prefix="docorc")

    if request.method == "POST":
        if documento_formset.is_valid() and documento_orcamentario_formset.is_valid():
            try:
                _salvar_formsets_em_transacao(documento_formset, documento_orcamentario_formset)
                messages.success(request, f"Documentos do Processo #{pk} atualizados com sucesso!")
                return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", pk)
            except (DatabaseError, TypeError, ValueError, OSError) as e:
                logger.exception("Erro ao atualizar documentos do processo %s", pk)
                messages.error(request, "Erro interno ao salvar os documentos.")
        else:
            messages.error(request, "Verifique os erros nos documentos e dados orçamentários.")

    return render(
        request,
        "fluxo/editar_processo_documentos.html",
        {
            "processo": processo,
            "documento_formset": documento_formset,
            "documento_orcamentario_formset": documento_orcamentario_formset,
            "status_inicial": status_inicial,
            "next_url": next_url,
        },
    )


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def editar_processo_pendencias_view(request, pk):
    """Spoke de edicao de pendencias do processo."""
    processo, status_inicial, redirecionamento, somente_documentos = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    if somente_documentos:
        messages.error(
            request,
            "Neste status, apenas documentos podem ser alterados.",
        )
        return redirect("editar_processo_documentos", pk=pk)

    post_data, _ = _get_request_payloads(request)
    next_url = _get_next_url(request)
    pendencia_formset = PendenciaFormSet(post_data, instance=processo, prefix="pendencia")

    if request.method == "POST":
        if pendencia_formset.is_valid():
            try:
                _salvar_formsets_em_transacao(pendencia_formset)
                messages.success(request, f"Pendências do Processo #{pk} atualizadas com sucesso!")
                return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", pk)
            except (DatabaseError, TypeError, ValueError) as e:
                logger.exception("Erro ao atualizar pendências do processo %s", pk)
                messages.error(request, "Erro interno ao salvar as pendências.")
        else:
            messages.error(request, "Verifique os erros nas pendências.")

    return render(
        request,
        "fluxo/editar_processo_pendencias.html",
        {
            "processo": processo,
            "pendencia_formset": pendencia_formset,
            "status_inicial": status_inicial,
            "next_url": next_url,
        },
    )


__all__ = [
    "add_process_view",
    "editar_processo",
    "editar_processo_capa_view",
    "editar_processo_documentos_view",
    "editar_processo_pendencias_view",
]
