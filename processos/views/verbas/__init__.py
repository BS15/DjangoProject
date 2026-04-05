import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db import transaction
from django.views.decorators.http import require_POST

from ...forms import PendenciaFormSet, ProcessoForm
from ...models import (
    AuxilioRepresentacao,
    Diaria,
    Jeton,
    Processo,
    ReembolsoCombustivel,
    StatusChoicesProcesso,
    TiposDePagamento,
)
from ...services import criar_assinatura_rascunho, gerar_documento_bytes
from .verbas_shared import (
    _CREDOR_AGRUPAMENTO_MULTIPLO,
    _VERBA_CONFIG,
    _anexar_documento,
    _extensao_documento_permitida,
    _get_permissao_gestao_verba,
    _get_tipos_documento_ativos,
    _obter_credor_agrupamento,
)

logger = logging.getLogger(__name__)

# Export type-specific verbas endpoints from package root.
from .verbas_diarias import *
from .siscac_diarias_sync import *
from .verbas_reembolso import *
from .verbas_jeton import *
from .verbas_auxilio import *


@permission_required("processos.pode_visualizar_verbas", raise_exception=True)
def verbas_panel_view(request):
    return render(request, 'verbas/verbas_panel.html')


@require_POST
@permission_required("processos.pode_agrupar_verbas", raise_exception=True)
def agrupar_verbas_view(request, tipo_verba):
    selecionados = request.POST.getlist('verbas_selecionadas')

    config = _VERBA_CONFIG.get(tipo_verba)
    if not config:
        return redirect('verbas_panel')

    modelo_verba = config['model']
    url_retorno = config['list_url']

    if not selecionados:
        messages.warning(request, 'Nenhum item selecionado para agrupar.')
        return redirect(url_retorno)

    itens = list(
        modelo_verba.objects.select_related('beneficiario').filter(id__in=selecionados, processo__isnull=True)
    )

    if not itens:
        messages.warning(request, 'Os itens selecionados já possuem processo ou são inválidos.')
        return redirect(url_retorno)

    total = sum(item.valor_total for item in itens if item.valor_total)
    credor_obj = _obter_credor_agrupamento(itens)
    if not credor_obj:
        messages.error(request, 'Não foi possível determinar o credor para o agrupamento.')
        return redirect(url_retorno)

    if len({item.beneficiario_id for item in itens if item.beneficiario_id}) > 1:
        messages.info(
            request,
            f'Beneficiários distintos detectados. O credor do processo foi definido como {_CREDOR_AGRUPAMENTO_MULTIPLO}.',
        )

    status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact='A PAGAR - PENDENTE AUTORIZAÇÃO',
        defaults={'status_choice': 'A PAGAR - PENDENTE AUTORIZAÇÃO'},
    )

    tipo_pagamento_verbas, _ = TiposDePagamento.objects.get_or_create(
        tipo_de_pagamento__iexact='VERBAS INDENIZATÓRIAS',
        defaults={'tipo_de_pagamento': 'VERBAS INDENIZATÓRIAS'},
    )

    with transaction.atomic():
        novo_processo = Processo.objects.create(
            credor=credor_obj,
            valor_bruto=total,
            valor_liquido=total,
            detalhamento=f"Agrupamento de {tipo_verba.capitalize()}s",
            status=status_padrao,
            tipo_pagamento=tipo_pagamento_verbas,
        )

        for item in itens:
            item.processo = novo_processo
            if isinstance(item, Diaria):
                item.avancar_status('ENVIADA PARA PAGAMENTO')
                try:
                    pdf_bytes = gerar_documento_bytes('pcd', item)
                    criar_assinatura_rascunho(
                        entidade=item,
                        tipo_documento='PCD',
                        criador=request.user,
                        pdf_bytes=pdf_bytes,
                        nome_arquivo=f"PCD_{item.id}.pdf",
                    )
                except Exception as e:
                    messages.warning(request, f"PCD para diária {item.numero_siscac} não gerado: {str(e)}")
            item.save()

    messages.success(request, f"Processo #{novo_processo.id} gerado com sucesso!")
    messages.info(request, 'PCDs gerados! Acesse o Painel de Assinaturas para enviar ao Autentique.')
    return redirect('editar_processo_verbas', pk=novo_processo.id)


@permission_required("processos.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas(request, pk):
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        processo_form = ProcessoForm(request.POST, instance=processo, prefix='processo')
        pendencia_formset = PendenciaFormSet(request.POST, instance=processo, prefix='pendencia')

        if processo_form.is_valid() and pendencia_formset.is_valid():
            try:
                with transaction.atomic():
                    processo = processo_form.save()
                    pendencia_formset.save()

                messages.success(request, f'Processo #{processo.id} atualizado com sucesso!')
                return redirect('editar_processo_verbas', pk=processo.id)
            except Exception as e:
                logger.exception('Erro ao atualizar processo de verbas', exc_info=e)
                messages.error(request, 'Erro interno ao salvar as alterações.')
        else:
            messages.error(request, 'Verifique os erros no formulário.')
    else:
        processo_form = ProcessoForm(instance=processo, prefix='processo')
        pendencia_formset = PendenciaFormSet(instance=processo, prefix='pendencia')

    diarias = Diaria.objects.filter(processo=processo).prefetch_related('documentos__tipo')
    reembolsos = ReembolsoCombustivel.objects.filter(processo=processo).prefetch_related('documentos__tipo')
    jetons = Jeton.objects.filter(processo=processo).prefetch_related('documentos__tipo')
    auxilios = AuxilioRepresentacao.objects.filter(processo=processo).prefetch_related('documentos__tipo')
    tipos_doc = _get_tipos_documento_ativos()

    context = {
        'processo': processo,
        'processo_form': processo_form,
        'pendencia_formset': pendencia_formset,
        'diarias': diarias,
        'reembolsos': reembolsos,
        'jetons': jetons,
        'auxilios': auxilios,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'verbas/editar_processo_verbas.html', context)


@require_POST
def api_add_documento_verba(request, tipo_verba, pk):
    config = _VERBA_CONFIG.get(tipo_verba)
    if not config:
        return JsonResponse({'ok': False, 'error': 'Tipo de verba inválido.'}, status=400)

    permissao = _get_permissao_gestao_verba(tipo_verba)
    if not permissao or not request.user.has_perm(permissao):
        raise PermissionDenied('Você não tem permissão para anexar documentos nesta verba.')

    modelo_verba = config['model']
    modelo_documento = config['doc_model']
    fk_name = config['doc_fk']
    tipo_doc_seguro = config['doc_tipo_seguro']
    verba = get_object_or_404(modelo_verba, id=pk)

    arquivo = request.FILES.get('arquivo')
    tipo_id = request.POST.get('tipo')

    if not arquivo or not tipo_id:
        return JsonResponse({'ok': False, 'error': 'Arquivo e tipo de documento são obrigatórios.'}, status=400)

    if not _extensao_documento_permitida(arquivo.name):
        return JsonResponse({'ok': False, 'error': 'Formato não permitido. Use PDF, JPG ou PNG.'}, status=400)

    try:
        doc = _anexar_documento(modelo_documento, fk_name, verba, arquivo, tipo_id)
        arquivo_url = reverse('download_arquivo_seguro', args=[tipo_doc_seguro, doc.id])
        return JsonResponse({'ok': True, 'doc_id': doc.id, 'arquivo_url': arquivo_url, 'tipo': str(doc.tipo)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
