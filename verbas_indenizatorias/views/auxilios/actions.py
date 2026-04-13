from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

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
@permission_required("fluxo.pode_gerenciar_auxilios", raise_exception=True)
def add_auxilio_action(request):
    form = AuxilioForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Erro ao salvar. Verifique os campos.")
        return redirect("add_auxilio")

    auxilio = form.save()
    messages.success(request, "Auxílio cadastrado com sucesso.")
    return redirect("gerenciar_auxilio", pk=auxilio.id)


@require_POST
@permission_required("fluxo.pode_gerenciar_auxilios", raise_exception=True)
def solicitar_autorizacao_auxilio_action(request, pk):
    auxilio = get_object_or_404(AuxilioRepresentacao, id=pk)
    _set_status_case_insensitive(auxilio, "SOLICITADA")
    messages.success(request, "Solicitação de auxílio enviada para autorização.")
    return redirect("gerenciar_auxilio", pk=auxilio.id)


@require_POST
@permission_required("fluxo.pode_gerenciar_auxilios", raise_exception=True)
def autorizar_auxilio_action(request, pk):
    auxilio = get_object_or_404(AuxilioRepresentacao, id=pk)
    _set_status_case_insensitive(auxilio, "APROVADA")
    messages.success(request, "Auxílio autorizado com sucesso.")
    return redirect("gerenciar_auxilio", pk=auxilio.id)


@require_POST
@permission_required("fluxo.pode_gerenciar_auxilios", raise_exception=True)
def cancelar_auxilio_action(request, pk):
    auxilio = get_object_or_404(AuxilioRepresentacao, id=pk)
    _set_status_case_insensitive(auxilio, "CANCELADO / ANULADO")
    messages.warning(request, "Auxílio cancelado.")
    return redirect("gerenciar_auxilio", pk=auxilio.id)
