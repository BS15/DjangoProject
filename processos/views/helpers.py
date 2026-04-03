"""Helpers compartilhados do fluxo financeiro.

Contem infraestrutura utilizada por multiplos modulos de views.
"""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied
from django.db.models import Count
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


_CAMPOS_PERMITIDOS_CONTINGENCIA = {
    "n_nota_empenho",
    "data_empenho",
    "valor_bruto",
    "valor_liquido",
    "ano_exercicio",
    "n_pagamento_siscac",
    "data_vencimento",
    "data_pagamento",
    "observacao",
    "detalhamento",
    "credor_id",
    "forma_pagamento_id",
    "tipo_pagamento_id",
    "conta_id",
    "tag_id",
}


def _normalizar_texto(texto):
    """Remove acentos e converte para maiusculas para comparacoes robustas."""
    import unicodedata

    return unicodedata.normalize("NFD", texto.upper()).encode("ascii", "ignore").decode("ascii")


def _obter_campo_ordenacao(request, campos_permitidos, default_ordem="id", default_direcao="desc"):
    """Extrai e formata o campo de ordenacao com base nos parametros GET.

    Garante que apenas colunas mapeadas em `campos_permitidos` sejam usadas.
    Retorna o campo pronto para `order_by`, com prefixo `-` quando descendente.
    """
    ordem = request.GET.get("ordem", default_ordem)
    direcao = request.GET.get("direcao", default_direcao)
    order_field = campos_permitidos.get(ordem, campos_permitidos.get(default_ordem, "id"))
    return f"-{order_field}" if direcao == "desc" else order_field


def _atualizar_status_em_lote(ids, nome_status, queryset_base=None):
    """Atualiza em lote o status de processos e retorna o total de linhas afetadas."""
    if not ids:
        return 0

    status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact=nome_status,
        defaults={"status_choice": nome_status},
    )

    qs = queryset_base if queryset_base is not None else Processo.objects.filter(id__in=ids)
    return qs.update(status=status_obj)


def _gerar_agrupamentos_contas_a_pagar(queryset):
    """Gera agregacoes dos filtros laterais da UI de contas a pagar."""
    return {
        "datas_agrupadas": queryset.values("data_pagamento").annotate(total=Count("id")).order_by("data_pagamento"),
        "formas_agrupadas": queryset.values(
            "forma_pagamento__id", "forma_pagamento__forma_de_pagamento"
        ).annotate(total=Count("id")).order_by("forma_pagamento__forma_de_pagamento"),
        "statuses_agrupados": queryset.values("status__status_choice").annotate(total=Count("id")).order_by(
            "status__status_choice"
        ),
        "contas_agrupadas": queryset.values(
            "conta__id",
            "conta__banco",
            "conta__agencia",
            "conta__conta",
            "conta__titular__nome",
        ).annotate(total=Count("id")).order_by("conta__titular__nome", "conta__banco", "conta__agencia"),
    }


def _aplicar_filtros_contas_a_pagar(queryset, params):
    """Aplica os filtros manuais de contas a pagar com base nos parametros GET."""
    qs = queryset

    status = params.get("status")
    data = params.get("data")
    forma = params.get("forma")
    conta = params.get("conta")

    if status:
        qs = qs.filter(status__status_choice=status)

    if data:
        qs = qs.filter(data_pagamento__isnull=True) if data == "sem_data" else qs.filter(data_pagamento=data)

    if forma:
        if forma == "sem_forma":
            qs = qs.filter(forma_pagamento__isnull=True)
        elif forma.isdigit():
            qs = qs.filter(forma_pagamento__id=int(forma))

    if conta:
        if conta == "sem_conta":
            qs = qs.filter(conta__isnull=True)
        elif conta.isdigit():
            qs = qs.filter(conta__id=int(conta))

    return qs


def _normalizar_filtro_opcao(valor, opcoes_validas, default=""):
    """Normaliza filtro textual para um conjunto fechado de opcoes validas."""
    return valor if valor in opcoes_validas else default


def _aplicar_filtro_por_opcao(queryset, opcao, mapa_filtros):
    """Aplica filtro por opcao com regras mapeadas (kwargs ou callable)."""
    regra = mapa_filtros.get(opcao)
    if not regra:
        return queryset
    if callable(regra):
        return regra(queryset)
    return queryset.filter(**regra)


def _aplicar_filtros_historico(qs, *, tipo_acao="", data_inicio="", data_fim="", usuario=""):
    """Aplica filtros de auditoria em queryset historico."""
    if tipo_acao:
        qs = qs.filter(history_type=tipo_acao)
    if data_inicio:
        qs = qs.filter(history_date__date__gte=data_inicio)
    if data_fim:
        qs = qs.filter(history_date__date__lte=data_fim)
    if usuario:
        qs = qs.filter(history_user__username__icontains=usuario)
    return qs


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


def _consolidar_totais_pagamento(totais_a_pagar, totais_lancados):
    """Consolida totais por forma de pagamento e calcula somatorios gerais."""
    totais = {}
    for origem in (totais_a_pagar, totais_lancados):
        for forma, valor in origem.items():
            totais[forma] = totais.get(forma, 0) + valor

    total_a_pagar = sum(totais_a_pagar.values())
    total_lancados = sum(totais_lancados.values())
    total_geral = total_a_pagar + total_lancados

    return {
        "totais": totais,
        "total_a_pagar": total_a_pagar,
        "total_lancados": total_lancados,
        "total_geral": total_geral,
    }


def _processar_acao_lote(
    request,
    *,
    param_name,
    status_origem_esperado,
    status_destino,
    msg_sucesso,
    msg_vazio,
    redirect_to,
    msg_sem_elegiveis=None,
    msg_ignorados=None,
):
    """Processa acao em lote com validacao de status de origem (turnpike)."""
    selecionados = request.POST.getlist(param_name)
    if not selecionados:
        valor_unico = request.POST.get(param_name)
        selecionados = [valor_unico] if valor_unico else []

    selecionados = [pid for pid in selecionados if pid]
    if not selecionados:
        messages.warning(request, msg_vazio)
        return redirect(redirect_to)

    elegiveis = Processo.objects.filter(
        id__in=selecionados,
        status__status_choice__iexact=status_origem_esperado,
    )
    count_elegiveis = elegiveis.count()
    count_ignorados = len(selecionados) - count_elegiveis

    if count_elegiveis > 0:
        _atualizar_status_em_lote(
            selecionados,
            status_destino,
            queryset_base=elegiveis,
        )
        messages.success(request, msg_sucesso.format(count=count_elegiveis, processo_id=selecionados[0]))
    else:
        messages.error(
            request,
            (msg_sem_elegiveis or "Ação negada: nenhum processo elegível para transição de status.").format(
                status_origem_esperado=status_origem_esperado,
                count=0,
                processo_id=selecionados[0],
            ),
        )

    if count_ignorados > 0:
        messages.warning(
            request,
            (msg_ignorados or "{count} processo(s) ignorado(s) por estarem em outro estágio do fluxo.").format(
                count=count_ignorados,
                status_origem_esperado=status_origem_esperado,
            ),
        )

    return redirect(redirect_to)


def _executar_arquivamento_definitivo(processo, usuario):
    """Gera PDF final, persiste arquivo e avanca status para ARQUIVADO."""
    pdf_buffer = processo.gerar_pdf_consolidado()
    if pdf_buffer is None:
        return False

    pdf_bytes = pdf_buffer.read()
    nome_arquivo = f"processo_{processo.id}_consolidado.pdf"

    with transaction.atomic():
        processo.arquivo_final.save(nome_arquivo, ContentFile(pdf_bytes), save=False)
        processo.save(update_fields=["arquivo_final"])
        processo.avancar_status("ARQUIVADO", usuario=usuario)

    return True


def _aplicar_aprovacao_contingencia(contingencia):
    """Executa aprovacao de contingencia com validacao financeira e persistencia atomica."""
    processo = contingencia.processo

    if "novo_valor_liquido" in contingencia.dados_propostos:
        raw_value = contingencia.dados_propostos["novo_valor_liquido"]
        if isinstance(raw_value, str):
            raw_value = raw_value.replace(".", "").replace(",", ".")
        try:
            novo_valor_liquido = Decimal(str(raw_value))
        except (InvalidOperation, ValueError):
            return False, "O valor líquido proposto na contingência é inválido."

        soma_comprovantes = sum(
            comp.valor_pago for comp in processo.comprovantes_pagamento.all() if comp.valor_pago is not None
        )

        if abs(novo_valor_liquido - Decimal(str(soma_comprovantes))) > Decimal("0.01"):
            return (
                False,
                "A contingência não pode ser aprovada. O novo valor líquido proposto não corresponde à "
                "soma dos comprovantes bancários anexados no sistema. O setor responsável deve anexar "
                "os comprovantes restantes antes da aprovação.",
            )

    with transaction.atomic():
        campos_alterados = []
        for campo, valor in contingencia.dados_propostos.items():
            if campo in _CAMPOS_PERMITIDOS_CONTINGENCIA and hasattr(processo, campo):
                setattr(processo, campo, valor)
                campos_alterados.append(campo)

        processo.em_contingencia = False
        campos_alterados.append("em_contingencia")
        processo.save(update_fields=campos_alterados)

        contingencia.status = "APROVADA"
        contingencia.save(update_fields=["status"])

    return True, None


def aplicar_aprovacao_contingencia(contingencia):
    """Wrapper público para aprovação de contingência."""
    return _aplicar_aprovacao_contingencia(contingencia)


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
    "_normalizar_filtro_opcao",
    "_aplicar_filtro_por_opcao",
    "_aplicar_filtros_historico",
    "_build_history_record",
    "_get_unified_history",
    "_iniciar_fila_sessao",
    "_handle_queue_navigation",
    "_registrar_recusa",
    "_salvar_documentos_sem_exclusao",
    "_processo_fila_detalhe_view",
    "_build_detalhes_pagamento",
    "_consolidar_totais_pagamento",
    "_processar_acao_lote",
    "_executar_arquivamento_definitivo",
    "_aplicar_aprovacao_contingencia",
    "aplicar_aprovacao_contingencia",
    "_aprovar_processo_view",
    "_recusar_processo_view",
]
