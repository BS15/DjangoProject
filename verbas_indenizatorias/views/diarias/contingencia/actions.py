"""Ações de contingência de diárias (POST views)."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from verbas_indenizatorias.forms import ContingenciaDiariaForm
from verbas_indenizatorias.models import ContingenciaDiaria, Diaria
from verbas_indenizatorias.services.contingencia import (
    aprovar_contingencia_diaria,
    criar_contingencia_diaria,
    rejeitar_contingencia_diaria,
)

logger = logging.getLogger(__name__)


@require_POST
@permission_required('verbas_indenizatorias.pode_gerenciar_diarias', raise_exception=True)
def add_contingencia_diaria_action(request, pk):
    """Cria uma contingência de retificação para a diária."""
    diaria = get_object_or_404(Diaria, pk=pk)
    form = ContingenciaDiariaForm(request.POST)

    if not form.is_valid():
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)
        return redirect('add_contingencia_diaria', pk=pk)

    cd = form.cleaned_data
    try:
        contingencia = criar_contingencia_diaria(
            diaria=diaria,
            solicitante=request.user,
            campo_corrigido=cd['campo_corrigido'],
            valor_proposto=cd['valor_proposto'],
            justificativa=cd['justificativa'],
            valor_anterior=cd.get('valor_anterior', ''),
        )
    except Exception as exc:
        messages.error(request, f"Erro ao abrir contingência: {exc}")
        return redirect('add_contingencia_diaria', pk=pk)

    messages.success(
        request,
        f"Contingência #{contingencia.pk} aberta com sucesso para a Diária #{diaria.pk}. "
        "Aguardando aprovação do supervisor."
    )
    return redirect('gerenciar_diaria', pk=pk)


@require_POST
@permission_required('verbas_indenizatorias.pode_gerenciar_diarias', raise_exception=True)
def analisar_contingencia_diaria_action(request, pk):
    """Aprova ou rejeita uma contingência de diária."""
    contingencia = get_object_or_404(ContingenciaDiaria, pk=pk)
    acao = (request.POST.get('action') or '').strip()
    parecer = (request.POST.get('parecer') or '').strip()

    if contingencia.status in {'APROVADA', 'REJEITADA'}:
        messages.error(request, 'Esta contingência já foi finalizada.')
        return redirect('painel_contingencias_diarias')

    if acao == 'aprovar':
        sucesso, msg = aprovar_contingencia_diaria(contingencia, request.user, parecer)
        if sucesso:
            messages.success(
                request,
                f"Contingência #{contingencia.pk} aprovada e aplicada à Diária #{contingencia.diaria_id}."
            )
        else:
            messages.error(request, f"Erro ao aprovar: {msg}")

    elif acao == 'rejeitar':
        if not parecer:
            messages.error(request, 'O parecer é obrigatório para rejeitar uma contingência.')
            return redirect('painel_contingencias_diarias')
        sucesso, msg = rejeitar_contingencia_diaria(contingencia, request.user, parecer)
        if sucesso:
            messages.success(request, f"Contingência #{contingencia.pk} rejeitada.")
        else:
            messages.error(request, f"Erro ao rejeitar: {msg}")

    else:
        messages.error(request, 'Ação inválida.')

    return redirect('painel_contingencias_diarias')


__all__ = [
    'add_contingencia_diaria_action',
    'analisar_contingencia_diaria_action',
]
