"""Painéis de contingência de diárias (GET views)."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from verbas_indenizatorias.forms import ContingenciaDiariaForm
from verbas_indenizatorias.models import ContingenciaDiaria, Diaria


@require_GET
@permission_required('pagamentos.pode_gerenciar_diarias', raise_exception=True)
def painel_contingencias_diarias_view(request):
    """Lista todas as contingências de diárias com filtro básico por status."""
    contingencias = ContingenciaDiaria.objects.select_related(
        'diaria__beneficiario', 'solicitante', 'aprovado_por'
    ).order_by('-criado_em')

    status_filtro = (request.GET.get('status') or '').strip().upper()
    if status_filtro in {'PENDENTE_SUPERVISOR', 'APROVADA', 'REJEITADA'}:
        contingencias = contingencias.filter(status=status_filtro)

    return render(request, 'verbas/painel_contingencias_diarias.html', {
        'contingencias': contingencias,
        'filtro_status': status_filtro,
    })


@require_GET
@permission_required('pagamentos.pode_gerenciar_diarias', raise_exception=True)
def add_contingencia_diaria_view(request, pk):
    """Formulário de abertura de contingência para a diária."""
    diaria = get_object_or_404(Diaria.objects.select_related('beneficiario', 'status'), pk=pk)
    form = ContingenciaDiariaForm()
    return render(request, 'verbas/add_contingencia_diaria.html', {
        'form': form,
        'diaria': diaria,
    })


__all__ = [
    'painel_contingencias_diarias_view',
    'add_contingencia_diaria_view',
]
