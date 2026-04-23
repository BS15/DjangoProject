"""Painéis de devolução de diárias (GET views)."""

from decimal import Decimal

from django.contrib.auth.decorators import permission_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from verbas_indenizatorias.forms import DevolucaoDiariaForm
from verbas_indenizatorias.models import Diaria, DevolucaoDiaria


@require_GET
@permission_required('pagamentos.pode_gerenciar_diarias', raise_exception=True)
def painel_devolucoes_diarias_view(request):
    """Lista todas as devoluções de diárias."""
    devolucoes = DevolucaoDiaria.objects.select_related(
        'diaria__beneficiario', 'registrado_por'
    ).order_by('-data_devolucao')

    beneficiario_q = (request.GET.get('beneficiario') or '').strip()
    if beneficiario_q:
        devolucoes = devolucoes.filter(diaria__beneficiario__nome__icontains=beneficiario_q)

    total_devolvido = devolucoes.aggregate(total=Sum('valor_devolvido'))['total'] or Decimal('0')

    return render(request, 'verbas/painel_devolucoes_diarias.html', {
        'devolucoes': devolucoes,
        'total_devolvido': total_devolvido,
        'filtro_beneficiario': beneficiario_q,
    })


@require_GET
@permission_required('pagamentos.pode_gerenciar_diarias', raise_exception=True)
def registrar_devolucao_diaria_view(request, pk):
    """Formulário para registrar devolução de diária."""
    diaria = get_object_or_404(Diaria.objects.select_related('beneficiario', 'status'), pk=pk)
    form = DevolucaoDiariaForm()
    return render(request, 'verbas/add_devolucao_diaria.html', {
        'form': form,
        'diaria': diaria,
    })


__all__ = [
    'painel_devolucoes_diarias_view',
    'registrar_devolucao_diaria_view',
]
