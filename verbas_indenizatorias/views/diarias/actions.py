import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError

from verbas_indenizatorias.forms import DiariaForm
from verbas_indenizatorias.services import gerar_e_anexar_scd_diaria
from verbas_indenizatorias.models import Diaria
from ..shared.documents import _salvar_documento_upload


logger = logging.getLogger(__name__)


def _preparar_nova_diaria(diaria):
    diaria.autorizada = False


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
def solicitar_autorizacao_action(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)

    try:
        diaria.avancar_status('SOLICITADA')
        gerar_e_anexar_scd_diaria(diaria, request.user)
        messages.success(request, 'Solicitação enviada para autorização.')
    except ValidationError as exc:
        messages.error(request, f'Não foi possível solicitar autorização: {exc}')
    except (OSError, RuntimeError, TypeError, ValueError):
        logger.exception('Falha ao gerar SCD para diária %s', diaria.id)
        messages.warning(request, 'Solicitação enviada, mas o SCD não foi gerado automaticamente.')

    return redirect('gerenciar_diaria', pk=diaria.id)


@require_POST
@permission_required('fluxo.pode_autorizar_diarias', raise_exception=True)
def autorizar_diaria_action(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)

    try:
        diaria.avancar_status('APROVADA')
        diaria.autorizada = True
        diaria.save(update_fields=['autorizada'])
        messages.success(request, f'Diária #{diaria.numero_siscac} autorizada com sucesso.')
    except ValidationError as exc:
        messages.error(request, f'Não foi possível autorizar a diária: {exc}')

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
    messages.success(request, f'Diária #{diaria.numero_siscac} aprovada com sucesso.')
    return redirect('painel_autorizacao_diarias')
