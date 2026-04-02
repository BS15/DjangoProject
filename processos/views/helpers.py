"""Helpers compartilhados do fluxo financeiro.

Contem infraestrutura utilizada por multiplos modulos de views.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import DocumentoFormSet, PendenciaForm, PendenciaFormSet
from ..models import (
    Contingencia,
    DocumentoFiscal,
    DocumentoProcesso,
    Pendencia,
    Processo,
    StatusChoicesPendencias,
    StatusChoicesProcesso,
    TiposDeDocumento,
)


def _normalizar_texto(texto):
    """Remove acentos e converte para maiusculas para comparacoes robustas."""
    import unicodedata

    return unicodedata.normalize("NFD", texto.upper()).encode("ascii", "ignore").decode("ascii")


def _build_history_record(record, modelo_label):
    """Build an enriched history record dict, resolving ForeignKeys to human-readable strings."""
    from django.db.models import ForeignKey

    HISTORY_TYPE_LABELS = {"+": "Criação", "~": "Alteração", "-": "Exclusão"}
    changed_fields = []

    if record.history_type == "~":
        prev = record.prev_record
        if prev is not None:
            try:
                delta = record.diff_against(prev)
                model_fields = {f.name: f for f in record.instance._meta.get_fields()}

                for change in delta.changes:
                    field_name = change.field
                    old_val = change.old
                    new_val = change.new

                    field_obj = model_fields.get(field_name)
                    if isinstance(field_obj, ForeignKey):
                        related_model = field_obj.related_model

                        if old_val is not None:
                            try:
                                old_obj = related_model.objects.get(pk=old_val)
                                old_val = str(old_obj)
                            except related_model.DoesNotExist:
                                old_val = f"ID {old_val} (Excluído)"

                        if new_val is not None:
                            try:
                                new_obj = related_model.objects.get(pk=new_val)
                                new_val = str(new_obj)
                            except related_model.DoesNotExist:
                                new_val = f"ID {new_val} (Excluído)"

                    if isinstance(old_val, bool):
                        old_val = "Sim" if old_val else "Não"
                    if isinstance(new_val, bool):
                        new_val = "Sim" if new_val else "Não"

                    if old_val is None:
                        old_val = "N/A"
                    if new_val is None:
                        new_val = "N/A"

                    changed_fields.append(
                        {
                            "field": field_name.replace("_", " ").title(),
                            "old": old_val,
                            "new": new_val,
                        }
                    )
            except Exception as e:
                print(f"Error building history diff: {e}")

    return {
        "modelo": modelo_label,
        "history_date": record.history_date,
        "history_user": record.history_user,
        "history_type": record.history_type,
        "history_type_label": HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
        "history_change_reason": getattr(record, "history_change_reason", None),
        "str_repr": str(record),
        "changed_fields": changed_fields,
    }


def _get_unified_history(pk):
    """Aggregates and sorts history records for a Processo and its related models."""
    processo = get_object_or_404(Processo, id=pk)
    history_records = []

    for record in processo.history.all().select_related("history_user"):
        history_records.append(_build_history_record(record, "Processo"))
    for record in DocumentoProcesso.history.filter(processo_id=pk).select_related("history_user"):
        history_records.append(_build_history_record(record, "Documento"))
    for record in Pendencia.history.filter(processo_id=pk).select_related("history_user"):
        history_records.append(_build_history_record(record, "Pendência"))
    for record in DocumentoFiscal.history.filter(processo_id=pk).select_related("history_user"):
        history_records.append(_build_history_record(record, "Nota Fiscal"))

    history_records.sort(key=lambda x: x["history_date"], reverse=True)
    return history_records


def _iniciar_fila_sessao(request, queue_key, fallback_view, detail_view, extra_args=None):
    """
    Stores a list of Processo IDs from POST into the session queue and redirects
    to the first item's detail view. Handles GET by redirecting to fallback_view.
    Callers must be protected by @permission_required.
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


def _handle_queue_navigation(request, pk, action, queue_key, fallback_view):
    """Handles 'sair', 'pular', and 'voltar' actions for detailed review views."""
    queue = request.session.get(queue_key, [])
    current_index = queue.index(pk) if pk in queue else -1
    next_pk = queue[current_index + 1] if 0 <= current_index < len(queue) - 1 else None
    prev_pk = queue[current_index - 1] if current_index > 0 else None

    if action == "sair":
        request.session.pop(queue_key, None)
        request.session.modified = True
        return redirect(fallback_view)

    if action == "pular":
        if next_pk:
            return redirect(request.resolver_match.view_name, pk=next_pk)
        messages.info(request, "Não há mais processos na fila. Retornando ao painel.")
        request.session.pop(queue_key, None)
        request.session.modified = True
        return redirect(fallback_view)

    if action == "voltar":
        if prev_pk:
            return redirect(request.resolver_match.view_name, pk=prev_pk)
        messages.info(request, "Não há processo anterior na fila.")
        return redirect(request.resolver_match.view_name, pk=pk)

    return None, queue, current_index, next_pk, prev_pk


def _registrar_recusa(request, processo, form, status_devolucao):
    """Saves a pendency and rolls back the process status in an atomic transaction."""
    with transaction.atomic():
        pendencia = form.save(commit=False)
        pendencia.processo = processo
        status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
            status_choice__iexact="A RESOLVER", defaults={"status_choice": "A RESOLVER"}
        )
        pendencia.status = status_pendencia
        pendencia.save()
        processo.avancar_status(status_devolucao, usuario=request.user)


def _salvar_documentos_sem_exclusao(doc_formset, processo):
    """Persist documents allowing add/reorder but never deleting existing records."""
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
):
    """Shared detailed review view for conferência/contabilização/conselho."""
    processo = get_object_or_404(Processo, id=pk)
    can_interact = request.user.has_perm(permission)

    queue = []
    current_index = -1
    next_pk = None
    prev_pk = None
    doc_formset = None
    pendencia_formset = None

    if request.method == "POST":
        action = request.POST.get("action", "")

        nav_result = _handle_queue_navigation(request, pk, action, queue_key, fallback_view)
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
                    request.session.modified = True
                    return redirect(fallback_view)
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
                    with transaction.atomic():
                        _salvar_documentos_sem_exclusao(doc_formset, processo)
                        if lock_documents:
                            processo.documentos.all().update(imutavel=True)
                        pendencia_formset.save()

                        if action == approve_action:
                            processo.avancar_status(approve_status, usuario=request.user)
                            messages.success(request, approve_message.format(processo_id=processo.id))
                            if next_pk:
                                return redirect(current_view, pk=next_pk)
                            request.session.pop(queue_key, None)
                            request.session.modified = True
                            return redirect(fallback_view)

                        messages.success(request, save_message.format(processo_id=processo.id))
                        return redirect(current_view, pk=pk)

                messages.error(request, "Verifique os erros no formulário abaixo.")
            else:
                processo.avancar_status(approve_status, usuario=request.user)
                messages.success(request, approve_message.format(processo_id=processo.id))
                if next_pk:
                    return redirect(current_view, pk=next_pk)
                request.session.pop(queue_key, None)
                request.session.modified = True
                return redirect(fallback_view)
    else:
        _, queue, current_index, next_pk, prev_pk = _handle_queue_navigation(
            request, pk, "", queue_key, fallback_view
        )

    if editable:
        if doc_formset is None:
            doc_formset = DocumentoFormSet(instance=processo, prefix="documentos")
        if pendencia_formset is None:
            pendencia_formset = PendenciaFormSet(instance=processo, prefix="pendencias")

    history_records = _get_unified_history(pk)

    contingencias = Contingencia.objects.filter(processo=processo).select_related(
        "solicitante", "aprovado_por_supervisor", "aprovado_por_ordenador", "aprovado_por_conselho"
    ).order_by("-data_solicitacao")

    context = {
        "processo": processo,
        "pendencia_form": PendenciaForm(),
        "history_records": history_records,
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
                "tipos_documento": TiposDeDocumento.objects.all(),
            }
        )

    return render(request, template_name, context)


def _build_detalhes_pagamento(processos):
    detalhes = []
    totais = {}
    for p in processos:
        forma = p.forma_pagamento.forma_de_pagamento.lower() if p.forma_pagamento else ""
        forma_nome = p.forma_pagamento.forma_de_pagamento if p.forma_pagamento else "N/A"
        tipo = p.tipo_pagamento.tipo_de_pagamento.upper() if p.tipo_pagamento else ""

        if tipo == "GERENCIADOR/BOLETO BANCÁRIO" or "boleto" in forma or "gerenciador" in forma:
            codigos_barras = [doc.codigo_barras for doc in p.documentos.all() if doc.codigo_barras]
            dados_pagamento = {
                "tipo": "codigo_barras",
                "codigos_barras": codigos_barras,
            }
        elif "pix" in forma:
            dados_pagamento = {
                "tipo": "pix",
                "chave_pix": (p.credor.chave_pix if p.credor and p.credor.chave_pix else ""),
            }
        elif "transfer" in forma or "ted" in forma:
            credor_conta = p.credor.conta if p.credor else None
            dados_pagamento = {
                "tipo": "transferencia",
                "banco": credor_conta.banco if credor_conta else "",
                "agencia": credor_conta.agencia if credor_conta else "",
                "conta": credor_conta.conta if credor_conta else "",
            }
        else:
            dados_pagamento = {"tipo": "remessa"}

        detalhes.append({"processo": p, "dados_pagamento": dados_pagamento})
        valor = p.valor_liquido or 0
        totais[forma_nome] = totais.get(forma_nome, 0) + valor
    return detalhes, totais


def _aprovar_processo_view(request, pk, *, permission, new_status, success_message, redirect_to):
    """Shared approval handler: advances a Processo to a new status via direct assignment."""
    if request.method == "POST":
        if not request.user.has_perm(permission):
            raise PermissionDenied
        processo = get_object_or_404(Processo, id=pk)
        status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact=new_status,
            defaults={"status_choice": new_status},
        )
        processo.status = status_obj
        processo.save()
        messages.success(request, success_message.format(processo_id=processo.id))
    return redirect(redirect_to)


def _recusar_processo_view(request, pk, *, permission, status_devolucao, error_message, redirect_to):
    """Shared refusal handler: registers a Pendencia and rolls the Processo back."""
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
    "_normalizar_texto",
    "_build_history_record",
    "_get_unified_history",
    "_iniciar_fila_sessao",
    "_handle_queue_navigation",
    "_registrar_recusa",
    "_salvar_documentos_sem_exclusao",
    "_processo_fila_detalhe_view",
    "_build_detalhes_pagamento",
    "_aprovar_processo_view",
    "_recusar_processo_view",
]
