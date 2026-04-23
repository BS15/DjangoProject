import logging

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from pagamentos.services.cancelamentos import cancelar_verba, extrair_dados_devolucao_do_post
from verbas_indenizatorias.forms import JetonForm
from verbas_indenizatorias.models import Jeton, StatusChoicesVerbasIndenizatorias


def _set_status_case_insensitive(jeton, status_str):
    status, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
        status_choice__iexact=status_str,
        defaults={"status_choice": status_str},
    )
    jeton.status = status
    jeton.save(update_fields=["status"])


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_jetons", raise_exception=True)
def add_jeton_action(request):
    form = JetonForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Erro ao salvar. Verifique os campos.")
        return redirect("add_jeton")

    jeton = form.save()
    logger.info("mutation=add_jeton jeton_id=%s user_id=%s", jeton.id, request.user.pk)
    messages.success(request, "Jeton cadastrado com sucesso.")
    return redirect("gerenciar_jeton", pk=jeton.id)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_jetons", raise_exception=True)
def solicitar_autorizacao_jeton_action(request, pk):
    jeton = get_object_or_404(Jeton, id=pk)
    _set_status_case_insensitive(jeton, "SOLICITADA")
    logger.info("mutation=solicitar_autorizacao_jeton jeton_id=%s user_id=%s", jeton.id, request.user.pk)
    messages.success(request, "Solicitação de Jeton enviada para autorização.")
    return redirect("gerenciar_jeton", pk=jeton.id)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_jetons", raise_exception=True)
def autorizar_jeton_action(request, pk):
    jeton = get_object_or_404(Jeton, id=pk)
    _set_status_case_insensitive(jeton, "APROVADA")
    logger.info("mutation=autorizar_jeton jeton_id=%s user_id=%s", jeton.id, request.user.pk)
    messages.success(request, "Jeton autorizado com sucesso.")
    return redirect("gerenciar_jeton", pk=jeton.id)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_jetons", raise_exception=True)
def cancelar_jeton_action(request, pk):
    justificativa = (request.POST.get("justificativa") or "").strip()
    if not justificativa:
        messages.error(request, "A justificativa do cancelamento é obrigatória.")
        return redirect("cancelar_jeton_spoke", pk=pk)

    jeton = get_object_or_404(Jeton.objects.select_related("processo__status"), id=pk)
    try:
        cancelar_verba(jeton, justificativa, request.user, dados_devolucao=extrair_dados_devolucao_do_post(request))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("cancelar_jeton_spoke", pk=pk)

    logger.info("mutation=cancelar_jeton jeton_id=%s user_id=%s", jeton.id, request.user.pk)
    messages.warning(request, "Jeton cancelado.")
    return redirect("gerenciar_jeton", pk=jeton.id)
