from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError

from verbas_indenizatorias.forms import DiariaForm
from verbas_indenizatorias.models import Diaria
from ..shared.documents import _salvar_documento_upload



def _preparar_nova_diaria(diaria):
    """Cria diária já operacional, sem etapa interna de solicitação/autorização."""
    from verbas_indenizatorias.models import StatusChoicesVerbasIndenizatorias

    diaria.autorizada = True
    status_aprovada, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
        status_choice__iexact='APROVADA',
        defaults={'status_choice': 'APROVADA'},
    )
    diaria.status = status_aprovada


def _salvar_diaria_base(form):
    diaria = form.save(commit=False)
    _preparar_nova_diaria(diaria)
    diaria.save()
    if hasattr(form, 'save_m2m'):
        form.save_m2m()
    return diaria


def _set_status_case_insensitive(diaria, status_str):
    from verbas_indenizatorias.models import StatusChoicesVerbasIndenizatorias

    status, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
        status_choice__iexact=status_str,
        defaults={'status_choice': status_str},
    )
    diaria.status = status
    diaria.save(update_fields=['status'])


@require_POST
@permission_required('fluxo.pode_criar_diarias', raise_exception=True)
def add_diaria_action(request):
    form = DiariaForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Erro ao salvar. Verifique os campos.')
        return redirect('add_diaria')

    diaria = _salvar_diaria_base(form)
    messages.success(request, 'Diária cadastrada com sucesso.')
    return redirect('gerenciar_diaria', pk=diaria.id)



@require_POST
@permission_required('fluxo.pode_gerenciar_diarias', raise_exception=True)
def registrar_comprovante_action(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)
    arquivo = request.FILES.get('arquivo')
    tipo_id = request.POST.get('tipo_comprovante') or request.POST.get('tipo')

    _, erro = _salvar_documento_upload(
        diaria,
        modelo_documento=diaria.documentos.model,
        fk_name='diaria',
        arquivo=arquivo,
        tipo_id=tipo_id,
        obrigatorio=True,
    )

    if erro:
        messages.error(request, erro)
    else:
        messages.success(request, 'Comprovante anexado com sucesso.')

    return redirect('gerenciar_diaria', pk=diaria.id)


@require_POST
@permission_required('fluxo.pode_gerenciar_diarias', raise_exception=True)
def cancelar_diaria_action(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)

    try:
        diaria.avancar_status('REJEITADA')
    except ValidationError:
        _set_status_case_insensitive(diaria, 'CANCELADO / ANULADO')

    diaria.autorizada = False
    diaria.save(update_fields=['autorizada'])
    messages.warning(request, f'Diária #{diaria.numero_siscac} cancelada.')
    return redirect('gerenciar_diaria', pk=diaria.id)


