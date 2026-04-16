from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from verbas_indenizatorias.forms import ReembolsoForm
from verbas_indenizatorias.models import (
    ReembolsoCombustivel,
    StatusChoicesVerbasIndenizatorias,
)
from ..shared.documents import _salvar_documento_upload
from ..shared.registry import _get_tipos_documento_verbas


def _set_status_case_insensitive(reembolso, status_str):
    status, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
        status_choice__iexact=status_str,
        defaults={"status_choice": status_str},
    )
    reembolso.status = status
    reembolso.save(update_fields=["status"])


@require_POST
@permission_required("fluxo.pode_gerenciar_reembolsos", raise_exception=True)
def add_reembolso_action(request):
    form = ReembolsoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Erro ao salvar. Verifique os campos.")
        return redirect("add_reembolso")

    reembolso = form.save()
    messages.success(request, "Reembolso cadastrado com sucesso.")
    return redirect("gerenciar_reembolso", pk=reembolso.id)


@require_POST
@permission_required("fluxo.pode_gerenciar_reembolsos", raise_exception=True)
def solicitar_autorizacao_reembolso_action(request, pk):
    reembolso = get_object_or_404(ReembolsoCombustivel, id=pk)
    _set_status_case_insensitive(reembolso, "SOLICITADA")
    messages.success(request, "Solicitação de reembolso enviada para autorização.")
    return redirect("gerenciar_reembolso", pk=reembolso.id)


@require_POST
@permission_required("fluxo.pode_gerenciar_reembolsos", raise_exception=True)
def autorizar_reembolso_action(request, pk):
    reembolso = get_object_or_404(ReembolsoCombustivel, id=pk)
    _set_status_case_insensitive(reembolso, "APROVADA")
    messages.success(request, "Reembolso autorizado com sucesso.")
    return redirect("gerenciar_reembolso", pk=reembolso.id)


@require_POST
@permission_required("fluxo.pode_gerenciar_reembolsos", raise_exception=True)
def cancelar_reembolso_action(request, pk):
    reembolso = get_object_or_404(ReembolsoCombustivel, id=pk)
    _set_status_case_insensitive(reembolso, "CANCELADO / ANULADO")
    messages.warning(request, "Reembolso cancelado.")
    return redirect("gerenciar_reembolso", pk=reembolso.id)


@require_POST
@permission_required("fluxo.pode_gerenciar_reembolsos", raise_exception=True)
def registrar_comprovante_reembolso_action(request, pk):
    reembolso = get_object_or_404(ReembolsoCombustivel, id=pk)
    arquivo = request.FILES.get("arquivo")
    tipo_id = request.POST.get("tipo_comprovante")

    if not tipo_id:
        tipo = _get_tipos_documento_verbas().first()
        tipo_id = str(tipo.id) if tipo else None

    _, erro = _salvar_documento_upload(
        reembolso,
        modelo_documento=reembolso.documentos.model,
        fk_name="reembolso",
        arquivo=arquivo,
        tipo_id=tipo_id,
        obrigatorio=True,
    )

    if erro:
        messages.error(request, erro)
    else:
        messages.success(request, "Comprovante anexado com sucesso.")

    return redirect("gerenciar_reembolso", pk=reembolso.id)
