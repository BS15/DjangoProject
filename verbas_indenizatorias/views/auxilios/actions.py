import logging
logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from pagamentos.services.cancelamentos import cancelar_verba, extrair_dados_devolucao_do_post
from verbas_indenizatorias.forms import AuxilioForm
from verbas_indenizatorias.models import AuxilioRepresentacao, StatusChoicesVerbasIndenizatorias


def _set_status_case_insensitive(auxilio, status_str):
    status, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
        status_choice__iexact=status_str,
        defaults={"status_choice": status_str},
    )
    auxilio.status = status
    auxilio.save(update_fields=["status"])


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_auxilios", raise_exception=True)
def add_auxilio_action(request):
    form = AuxilioForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Erro ao salvar. Verifique os campos.")
        return redirect("add_auxilio")

    auxilio = form.save()
    logger.info("mutation=add_auxilio auxilio_id=%s user_id=%s", auxilio.id, request.user.pk)
    messages.success(request, "Auxílio cadastrado com sucesso.")
    return redirect("gerenciar_auxilio", pk=auxilio.id)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_auxilios", raise_exception=True)
def solicitar_autorizacao_auxilio_action(request, pk):
    auxilio = get_object_or_404(AuxilioRepresentacao, id=pk)
    _set_status_case_insensitive(auxilio, "SOLICITADA")
    logger.info("mutation=solicitar_autorizacao_auxilio auxilio_id=%s user_id=%s", auxilio.id, request.user.pk)
    messages.success(request, "Solicitação de auxílio enviada para autorização.")
    return redirect("gerenciar_auxilio", pk=auxilio.id)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_auxilios", raise_exception=True)
def autorizar_auxilio_action(request, pk):
    auxilio = get_object_or_404(AuxilioRepresentacao, id=pk)
    _set_status_case_insensitive(auxilio, "APROVADA")
    logger.info("mutation=autorizar_auxilio auxilio_id=%s user_id=%s", auxilio.id, request.user.pk)
    messages.success(request, "Auxílio autorizado com sucesso.")
    return redirect("gerenciar_auxilio", pk=auxilio.id)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_auxilios", raise_exception=True)
def cancelar_auxilio_action(request, pk):
    justificativa = (request.POST.get("justificativa") or "").strip()
    if not justificativa:
        messages.error(request, "A justificativa do cancelamento é obrigatória.")
        return redirect("cancelar_auxilio_spoke", pk=pk)

    auxilio = get_object_or_404(AuxilioRepresentacao.objects.select_related("processo__status"), id=pk)
    try:
        cancelar_verba(auxilio, justificativa, request.user, dados_devolucao=extrair_dados_devolucao_do_post(request))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("cancelar_auxilio_spoke", pk=pk)

    logger.info("mutation=cancelar_auxilio auxilio_id=%s user_id=%s", auxilio.id, request.user.pk)
    messages.warning(request, "Auxílio cancelado.")
    return redirect("gerenciar_auxilio", pk=auxilio.id)
