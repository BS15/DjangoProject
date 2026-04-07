import logging

from django.contrib import messages
from django.db import transaction

from ....forms import PendenciaFormSet, ProcessoForm
from ....models import AuxilioRepresentacao, Diaria, Jeton, ReembolsoCombustivel
from ..verbas_shared import _get_tipos_documento_ativos

logger = logging.getLogger(__name__)


def _instanciar_formularios_processo_verbas(request, processo):
    """Constroi formulários de edição do processo de verbas conforme o método."""
    if request.method == 'POST':
        return (
            ProcessoForm(request.POST, instance=processo, prefix='processo'),
            PendenciaFormSet(request.POST, instance=processo, prefix='pendencia'),
        )

    return (
        ProcessoForm(instance=processo, prefix='processo'),
        PendenciaFormSet(instance=processo, prefix='pendencia'),
    )


def _salvar_formularios_processo_verbas(request, *, processo_form, pendencia_formset):
    """Persiste formulários do processo de verbas com tratamento transacional."""
    if not (processo_form.is_valid() and pendencia_formset.is_valid()):
        messages.error(request, 'Verifique os erros no formulario.')
        return None

    try:
        with transaction.atomic():
            processo = processo_form.save()
            pendencia_formset.save()
    except Exception as exc:
        logger.exception('Erro ao atualizar processo de verbas', exc_info=exc)
        messages.error(request, 'Erro interno ao salvar as alteracoes.')
        return None

    messages.success(request, f'Processo #{processo.id} atualizado com sucesso!')
    return processo


def _montar_contexto_processo_verbas(processo, *, processo_form, pendencia_formset):
    """Monta o contexto completo da tela de edição de processo de verbas."""
    return {
        'processo': processo,
        'processo_form': processo_form,
        'pendencia_formset': pendencia_formset,
        'diarias': Diaria.objects.filter(processo=processo).prefetch_related('documentos__tipo'),
        'reembolsos': ReembolsoCombustivel.objects.filter(processo=processo).prefetch_related('documentos__tipo'),
        'jetons': Jeton.objects.filter(processo=processo).prefetch_related('documentos__tipo'),
        'auxilios': AuxilioRepresentacao.objects.filter(processo=processo).prefetch_related('documentos__tipo'),
        'tipos_documento': _get_tipos_documento_ativos(),
    }