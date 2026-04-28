"""Infraestrutura de fluxo: filas de revisao, aprovacao/recusa e formularios."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from pagamentos.forms import DocumentoFormSet, PendenciaForm, PendenciaFormSet
from pagamentos.domain_models import (
    Contingencia,
    Devolucao,
    Processo,
)
from pagamentos.services.revisao_fluxo import (
    aprovar_processo_por_id,
    obter_tipos_documento_para_processo,
    persistir_revisao_processo,
    registrar_recusa_processo,
    salvar_documentos_sem_exclusao,
)
from fiscal.models import RetencaoImposto
from .audit_builders import _get_unified_history


def _get_tipos_documento_para_processo(processo):
    """Retorna os TiposDocumento ativos válidos para o processo informado.

    Inclui tipos vinculados ao tipo de pagamento do processo e tipos gerais
    (sem tipo_pagamento definido), excluindo tipos de outros contextos de pagamento.
    """
    return obter_tipos_documento_para_processo(processo)


def _registrar_recusa(request, processo, form, status_devolucao):
    """Registra uma pendência e devolve o processo ao status informado.

    A criação da pendência e a transição de status ocorrem em uma única
    transação para preservar consistência no fluxo administrativo.
    """
    return registrar_recusa_processo(
        request_user=request.user,
        processo=processo,
        form=form,
        status_devolucao=status_devolucao,
    )


def _salvar_documentos_sem_exclusao(doc_formset, processo):
    """Salva documentos do processo sem permitir exclusão física.

    O helper aceita inclusões e atualizações vindas do formset, mas ignora
    marcações de remoção para respeitar o requisito de imutabilidade do fluxo.
    """
    return salvar_documentos_sem_exclusao(doc_formset, processo)


def _iniciar_fila_sessao(request, queue_key, fallback_view, detail_view, extra_args=None):
    """Inicia uma fila de revisão na sessão a partir dos processos enviados via POST.

    Quando há seleção válida, persiste os IDs na sessão e redireciona para a
    primeira tela de detalhe. Requisições que não sejam POST retornam para a
    view de fallback.
    """
    if request.method != "POST":
        return redirect(fallback_view, **(extra_args or {}))

    ids_raw = request.POST.getlist("processo_ids")
    process_ids = [int(pid) for pid in ids_raw if pid.isdigit()]

    if not process_ids:
        messages.warning(request, "Selecione ao menos um processo para iniciar a revisão.")
        return redirect(fallback_view, **(extra_args or {}))

    request.session[queue_key] = process_ids
    request.session.modified = True
    return redirect(detail_view, pk=process_ids[0])


def _handle_queue_navigation(
    request,
    pk,
    action,
    queue_key,
    fallback_view,
    *,
    fallback_kwargs=None,
    session_keys_to_clear=None,
):
    """Processa a navegação entre itens de uma fila de revisão.

    Trata as ações de saída, avanço e retorno, devolvendo um redirecionamento
    imediato quando necessário ou os metadados da fila para a renderização da
    tela atual.
    """
    fallback_kwargs = fallback_kwargs or {}
    session_keys_to_clear = session_keys_to_clear or []

    queue = request.session.get(queue_key, [])
    current_index = queue.index(pk) if pk in queue else -1
    next_pk = queue[current_index + 1] if 0 <= current_index < len(queue) - 1 else None
    prev_pk = queue[current_index - 1] if current_index > 0 else None

    if action == "sair":
        request.session.pop(queue_key, None)
        for session_key in session_keys_to_clear:
            request.session.pop(session_key, None)
        request.session.modified = True
        return redirect(fallback_view, **fallback_kwargs)

    if action == "pular":
        if next_pk:
            return redirect(request.resolver_match.view_name, pk=next_pk)
        messages.info(request, "Não há mais processos na fila. Retornando ao painel.")
        request.session.pop(queue_key, None)
        for session_key in session_keys_to_clear:
            request.session.pop(session_key, None)
        request.session.modified = True
        return redirect(fallback_view, **fallback_kwargs)

    if action == "voltar":
        if prev_pk:
            return redirect(request.resolver_match.view_name, pk=prev_pk)
        messages.info(request, "Não há processo anterior na fila.")
        return redirect(request.resolver_match.view_name, pk=pk)

    return None, queue, current_index, next_pk, prev_pk


def _processo_fila_detalhe_view(
    request,
    pk,
    *,
    permission,
    queue_key,
    fallback_view,
    current_view,
    template_name,
    approve_action,
    approve_status,
    approve_message,
    save_action="salvar",
    save_message=None,
    reject_action=None,
    reject_status=None,
    reject_message=None,
    editable=True,
    lock_documents=False,
    fallback_kwargs=None,
    session_keys_to_clear=None,
):
    """Renderiza e processa a tela detalhada de revisão em filas operacionais.

    Centraliza a lógica comum de navegação, aprovação, salvamento parcial,
    recusa com pendência, histórico e montagem de contexto para as etapas de
    conferência, contabilização e conselho.
    """
    processo = get_object_or_404(Processo, id=pk)
    can_interact = request.user.has_perm(permission)

    queue = []
    current_index = -1
    next_pk = None
    prev_pk = None
    doc_formset = None
    pendencia_formset = None

    fallback_kwargs = fallback_kwargs or {}
    session_keys_to_clear = session_keys_to_clear or []

    if request.method == "POST":
        action = request.POST.get("action", "")

        nav_result = _handle_queue_navigation(
            request,
            pk,
            action,
            queue_key,
            fallback_view,
            fallback_kwargs=fallback_kwargs,
            session_keys_to_clear=session_keys_to_clear,
        )
        if isinstance(nav_result, HttpResponse):
            return nav_result

        _, queue, current_index, next_pk, prev_pk = nav_result

        allowed_actions = {approve_action}
        if editable:
            allowed_actions.add(save_action)
        if reject_action:
            allowed_actions.add(reject_action)

        if action in allowed_actions:
            if not can_interact:
                raise PermissionDenied

            if reject_action and action == reject_action:
                form = PendenciaForm(request.POST)
                if form.is_valid():
                    _registrar_recusa(request, processo, form, reject_status)
                    messages.error(request, reject_message.format(processo_id=processo.id))
                    if next_pk:
                        return redirect(current_view, pk=next_pk)
                    request.session.pop(queue_key, None)
                    for session_key in session_keys_to_clear:
                        request.session.pop(session_key, None)
                    request.session.modified = True
                    return redirect(fallback_view, **fallback_kwargs)
                messages.warning(request, "Erro ao registrar recusa. Verifique os dados da pendência.")
                return redirect(current_view, pk=pk)

            if editable:
                doc_formset = DocumentoFormSet(
                    request.POST,
                    request.FILES,
                    instance=processo,
                    prefix="documentos",
                )
                pendencia_formset = PendenciaFormSet(
                    request.POST,
                    instance=processo,
                    prefix="pendencias",
                )

                if doc_formset.is_valid() and pendencia_formset.is_valid():
                    processo_lock = persistir_revisao_processo(
                        processo=processo,
                        doc_formset=doc_formset,
                        pendencia_formset=pendencia_formset,
                        lock_documents=lock_documents,
                        approve_status=approve_status if action == approve_action else None,
                        usuario=request.user,
                    )

                    if action == approve_action:
                        messages.success(request, approve_message.format(processo_id=processo_lock.id))
                        if next_pk:
                            return redirect(current_view, pk=next_pk)
                        request.session.pop(queue_key, None)
                        for session_key in session_keys_to_clear:
                            request.session.pop(session_key, None)
                        request.session.modified = True
                        return redirect(fallback_view, **fallback_kwargs)

                    messages.success(request, save_message.format(processo_id=processo_lock.id))
                    return redirect(current_view, pk=pk)

                messages.error(request, "Verifique os erros no formulário abaixo.")
            else:
                processo_lock = aprovar_processo_por_id(
                    processo_id=processo.pk,
                    new_status=approve_status,
                    usuario=request.user,
                )
                messages.success(request, approve_message.format(processo_id=processo_lock.id))
                if next_pk:
                    return redirect(current_view, pk=next_pk)
                request.session.pop(queue_key, None)
                for session_key in session_keys_to_clear:
                    request.session.pop(session_key, None)
                request.session.modified = True
                return redirect(fallback_view, **fallback_kwargs)
    else:
        _, queue, current_index, next_pk, prev_pk = _handle_queue_navigation(
            request,
            pk,
            "",
            queue_key,
            fallback_view,
            fallback_kwargs=fallback_kwargs,
            session_keys_to_clear=session_keys_to_clear,
        )

    if editable:
        tipos_documento = _get_tipos_documento_para_processo(processo)
        if doc_formset is None:
            doc_formset = DocumentoFormSet(
                instance=processo,
                prefix="documentos",
                form_kwargs={"tipo_queryset": tipos_documento},
            )
        if pendencia_formset is None:
            pendencia_formset = PendenciaFormSet(instance=processo, prefix="pendencias")

    history_records = _get_unified_history(pk)

    processo_pendencias = list(
        processo.pendencias.select_related("tipo", "status").order_by("-id")[:5]
    )
    processo_retencoes = list(
        RetencaoImposto.objects.select_related(
            "nota_fiscal",
            "codigo",
            "status",
            "beneficiario",
        )
        .filter(nota_fiscal__processo=processo)
        .order_by("-data_pagamento", "-id")[:5]
    )
    processo_devolucoes = list(
        Devolucao.objects.filter(processo=processo).order_by("-data_devolucao", "-id")[:5]
    )

    contingencias = Contingencia.objects.filter(processo=processo).select_related(
        "solicitante", "aprovado_por_supervisor", "aprovado_por_ordenador", "aprovado_por_conselho"
    ).order_by("-data_solicitacao")

    context = {
        "processo": processo,
        "pendencia_form": PendenciaForm(),
        "history_records": history_records,
        "processo_pendencias": processo_pendencias,
        "processo_retencoes": processo_retencoes,
        "processo_devolucoes": processo_devolucoes,
        "contingencias": contingencias,
        "queue": queue,
        "current_index": current_index,
        "next_pk": next_pk,
        "prev_pk": prev_pk,
        "queue_length": len(queue),
        "queue_position": current_index + 1 if current_index >= 0 else 1,
        "pode_interagir": can_interact,
    }

    if editable:
        context.update(
            {
                "doc_formset": doc_formset,
                "pendencia_formset": pendencia_formset,
                "tipos_documento": tipos_documento,
            }
        )

    return render(request, template_name, context)


def _aprovar_processo_view(request, pk, *, permission, new_status, success_message, redirect_to):
    """Processa uma aprovação simples por view com troca de status segura.

    Valida permissão, carrega o processo e delega a transição ao método de
    domínio para garantir turnpike e auditoria.
    """
    if request.method == "POST":
        if not request.user.has_perm(permission):
            raise PermissionDenied

        processo = aprovar_processo_por_id(
            processo_id=pk,
            new_status=new_status,
            usuario=request.user,
        )

        messages.success(request, success_message.format(processo_id=processo.id))

    return redirect(redirect_to)


def _recusar_processo_view(request, pk, *, permission, status_devolucao, error_message, redirect_to):
    """Processa a recusa de um processo registrando a pendência correspondente.

    Em caso de formulário válido, cria a pendência e devolve o processo ao
    estágio anterior definido para a etapa atual do fluxo.
    """
    processo = get_object_or_404(Processo, id=pk)
    if request.method == "POST":
        if not request.user.has_perm(permission):
            raise PermissionDenied
        form = PendenciaForm(request.POST)
        if form.is_valid():
            _registrar_recusa(request, processo, form, status_devolucao)
            messages.error(request, error_message.format(processo_id=processo.id))
        else:
            messages.warning(request, "Erro ao registrar recusa. Verifique os dados da pendência.")
    return redirect(redirect_to)


__all__ = [
    "_registrar_recusa",
    "_salvar_documentos_sem_exclusao",
    "_iniciar_fila_sessao",
    "_handle_queue_navigation",
    "_processo_fila_detalhe_view",
    "_aprovar_processo_view",
    "_recusar_processo_view",
]
