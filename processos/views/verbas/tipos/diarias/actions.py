from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .....models import Diaria
from .....utils import confirmar_diarias_lote, preview_diarias_lote


@permission_required('processos.pode_importar_diarias', raise_exception=True)
def importar_diarias_view(request):
    session_key = 'importar_diarias_preview'
    context = {}

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'confirmar':
            preview_items = request.session.pop(session_key, None)
            if not isinstance(preview_items, list) or not preview_items:
                messages.error(request, 'Sessao expirada ou previa nao encontrada. Por favor, importe o arquivo novamente.')
                return redirect('importar_diarias')

            resultados = confirmar_diarias_lote(preview_items, request.user)
            context['resultados'] = resultados

        elif action == 'cancelar':
            request.session.pop(session_key, None)
            return redirect('importar_diarias')

        elif request.FILES.get('csv_file'):
            resultado_preview = preview_diarias_lote(request.FILES['csv_file'])
            request.session[session_key] = resultado_preview['preview']
            context['preview'] = resultado_preview['preview']
            context['erros_preview'] = resultado_preview['erros']

    return render(request, 'verbas/importar_diarias.html', context)


@permission_required('processos.pode_autorizar_diarias', raise_exception=True)
def painel_autorizacao_diarias_view(request):
    diarias_pendentes = Diaria.objects.select_related(
        'beneficiario', 'proponente', 'status', 'processo'
    ).filter(status__status_choice='SOLICITADA').order_by('-id')

    return render(request, 'verbas/painel_autorizacao_diarias.html', {'diarias_pendentes': diarias_pendentes})


@require_POST
@permission_required('processos.pode_autorizar_diarias', raise_exception=True)
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
@permission_required('processos.pode_autorizar_diarias', raise_exception=True)
def aprovar_diaria_view(request, diaria_id):
    diaria = get_object_or_404(Diaria, id=diaria_id)

    diaria.avancar_status('APROVADA')
    diaria.autorizada = True
    diaria.save(update_fields=['autorizada'])

    messages.success(request, 'Diaria aprovada com sucesso.')
    return redirect('painel_autorizacao_diarias')
