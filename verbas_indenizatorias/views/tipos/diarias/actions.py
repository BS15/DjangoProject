from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from verbas_indenizatorias.models import Diaria


@permission_required('fluxo.pode_autorizar_diarias', raise_exception=True)
def painel_autorizacao_diarias_view(request):
    diarias_pendentes = Diaria.objects.select_related(
        'beneficiario', 'proponente', 'status', 'processo'
    ).filter(status__status_choice='SOLICITADA').order_by('-id')

    return render(request, 'verbas/painel_autorizacao_diarias.html', {'diarias_pendentes': diarias_pendentes})


@require_POST
@permission_required('fluxo.pode_autorizar_diarias', raise_exception=True)
def alternar_autorizacao_diaria(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)
    diaria.autorizada = not diaria.autorizada
    diaria.save()

    if diaria.autorizada:
        messages.success(request, f'Diaria #{diaria.numero_siscac} AUTORIZADA com sucesso!')
    else:
        messages.warning(request, f'Autorizacao da Diaria #{diaria.numero_siscac} foi revogada.')

    return redirect('painel_autorizacao_diarias')


@require_POST
@permission_required('fluxo.pode_autorizar_diarias', raise_exception=True)
def aprovar_diaria_view(request, diaria_id):
    diaria = get_object_or_404(Diaria, id=diaria_id)

    diaria.avancar_status('APROVADA')
    diaria.autorizada = True
    diaria.save(update_fields=['autorizada'])

    messages.success(request, 'Diaria aprovada com sucesso.')
    return redirect('painel_autorizacao_diarias')
