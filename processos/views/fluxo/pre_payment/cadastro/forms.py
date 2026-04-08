"""Views de formulario (GET+POST) da etapa de cadastro/edicao."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import DatabaseError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .....forms import DocumentoFormSet, DocumentoOrcamentarioFormSet, PendenciaFormSet, ProcessoForm
from .....models import Processo
from ..helpers import (
    _aplicar_confirmacao_extra_orcamentario,
    _configurar_status_novo_processo,
    _redirect_seguro_ou_fallback,
    _salvar_processo_completo,
    _validar_regras_edicao_processo,
)


logger = logging.getLogger(__name__)


@permission_required("processos.acesso_backoffice", raise_exception=True)
def add_process_view(request):
    """Cria um novo processo de pagamento."""
    post_data = request.POST if request.method == "POST" else None
    files_data = request.FILES if request.method == "POST" else None

    processo_form = ProcessoForm(post_data, prefix="processo")
    documento_formset = DocumentoFormSet(post_data, files_data, prefix="documento")
    pendencia_formset = PendenciaFormSet(post_data, prefix="pendencia")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER", "")

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
                if request.POST.get("btn_goto_fiscais"):
                    return redirect("documentos_fiscais", pk=processo.id)
                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                return redirect("editar_processo", pk=processo.id)
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
            "documento_formset": documento_formset,
            "pendencia_formset": pendencia_formset,
            "next_url": next_url,
        },
    )


@permission_required("processos.acesso_backoffice", raise_exception=True)
def editar_processo(request, pk):
    """Hub de edicao modular do processo."""
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = processo.status.status_choice.upper() if processo.status else ""
    redirecionamento, somente_documentos = _validar_regras_edicao_processo(request, processo, status_inicial)
    if redirecionamento:
        return redirecionamento

    if request.method == "POST":
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

    total_documentos = processo.documentos.count()
    total_notas = processo.notas_fiscais.count()
    notas_nao_atestadas = processo.notas_fiscais.filter(atestada=False).count()
    total_pendencias = processo.pendencias.count()
    pendencias_abertas = processo.pendencias.filter(status__status_choice__iexact="A RESOLVER").count()

    context = {
        "processo": processo,
        "status_inicial": status_inicial,
        "somente_documentos": somente_documentos,
        "aguardando_liquidacao": status_inicial.startswith("AGUARDANDO LIQUIDAÇÃO"),
        "total_documentos": total_documentos,
        "total_notas": total_notas,
        "notas_nao_atestadas": notas_nao_atestadas,
        "total_pendencias": total_pendencias,
        "pendencias_abertas": pendencias_abertas,
    }

    return render(request, "fluxo/editar_processo_hub.html", context)


@permission_required("processos.acesso_backoffice", raise_exception=True)
def editar_processo_capa_view(request, pk):
    """Spoke de edicao da capa do processo."""
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = processo.status.status_choice.upper() if processo.status else ""
    redirecionamento, somente_documentos = _validar_regras_edicao_processo(request, processo, status_inicial)
    if redirecionamento:
        return redirecionamento

    if somente_documentos:
        messages.error(
            request,
            "Neste status, apenas documentos podem ser alterados. Use a tela específica de documentos.",
        )
        return redirect("editar_processo_documentos", pk=pk)

    post_data = request.POST if request.method == "POST" else None
    next_url = request.POST.get("next") or request.GET.get("next") or ""
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


@permission_required("processos.acesso_backoffice", raise_exception=True)
def editar_processo_documentos_view(request, pk):
    """Spoke de edicao de anexos do processo."""
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = processo.status.status_choice.upper() if processo.status else ""
    redirecionamento, _ = _validar_regras_edicao_processo(request, processo, status_inicial)
    if redirecionamento:
        return redirecionamento

    post_data = request.POST if request.method == "POST" else None
    files_data = request.FILES if request.method == "POST" else None
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    documento_formset = DocumentoFormSet(post_data, files_data, instance=processo, prefix="documento")
    documento_orcamentario_formset = DocumentoOrcamentarioFormSet(post_data, instance=processo, prefix="docorc")

    if request.method == "POST":
        if documento_formset.is_valid() and documento_orcamentario_formset.is_valid():
            try:
                with transaction.atomic():
                    documento_formset.save()
                    documento_orcamentario_formset.save()
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


@permission_required("processos.acesso_backoffice", raise_exception=True)
def editar_processo_pendencias_view(request, pk):
    """Spoke de edicao de pendencias do processo."""
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = processo.status.status_choice.upper() if processo.status else ""
    redirecionamento, somente_documentos = _validar_regras_edicao_processo(request, processo, status_inicial)
    if redirecionamento:
        return redirecionamento

    if somente_documentos:
        messages.error(
            request,
            "Neste status, apenas documentos podem ser alterados.",
        )
        return redirect("editar_processo_documentos", pk=pk)

    post_data = request.POST if request.method == "POST" else None
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    pendencia_formset = PendenciaFormSet(post_data, instance=processo, prefix="pendencia")

    if request.method == "POST":
        if pendencia_formset.is_valid():
            try:
                with transaction.atomic():
                    pendencia_formset.save()
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
