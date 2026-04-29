"""Acoes POST do fluxo de processos de verbas indenizatorias.

Este modulo executa mutacoes de agrupamento, edicao e anexacao documental
seguindo o paradigma manager-worker do dominio.
"""

import logging
logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from pagamentos.domain_models import Processo
from pagamentos.forms import DocumentoFormSet, PendenciaFormSet, ProcessoForm
from pagamentos.models import TiposDePagamento
from commons.shared.logging_gradients import log_audit
from verbas_indenizatorias.constants import STATUS_VERBA_REVISADA
from verbas_indenizatorias.services.processo_integration import criar_processo_e_vincular_verbas
from .helpers import _forcar_campos_canonicos_processo_verbas, _pode_gerenciar_processo_verbas_da_entidade
from ..shared.registry import (
    _CREDOR_AGRUPAMENTO_MULTIPLO,
    _VERBA_CONFIG,
    _obter_credor_agrupamento,
)


@require_POST
@permission_required("verbas_indenizatorias.pode_agrupar_verbas", raise_exception=True)
def agrupar_verbas_view(request, tipo_verba):
    """Agrupa verbas revisadas em um novo processo de pagamento canonico."""
    selecionados = request.POST.getlist('verbas_selecionadas')

    config = _VERBA_CONFIG.get(tipo_verba)
    if not config:
        return redirect('verbas_panel')

    modelo_verba = config['model']
    url_retorno = config['list_url']

    if not selecionados:
        messages.warning(request, 'Nenhum item selecionado para agrupar.')
        return redirect(url_retorno)

    # Todas as verbas devem estar revisadas e sem processo para agrupamento.
    itens_query = modelo_verba.objects.select_related('beneficiario').filter(
        id__in=selecionados,
        processo__isnull=True,
        status__status_choice__iexact=STATUS_VERBA_REVISADA,
    )

    itens = list(itens_query)

    if not itens:
        messages.warning(
            request,
            'Selecione itens REVISADOS e ainda não agrupados em processo para gerar pagamento.',
        )
        return redirect(url_retorno)

    credor_obj = _obter_credor_agrupamento(itens)
    if not credor_obj:
        messages.error(request, 'Nao foi possivel determinar o credor para o agrupamento.')
        return redirect(url_retorno)

    if len({item.beneficiario_id for item in itens if item.beneficiario_id}) > 1:
        messages.info(
            request,
            f'Beneficiarios distintos detectados. O credor do processo foi definido como {_CREDOR_AGRUPAMENTO_MULTIPLO}.',
        )

    novo_processo, falhas_pcd = criar_processo_e_vincular_verbas(
        itens,
        tipo_verba,
        credor_obj,
        usuario=request.user,
    )
    log_audit(
        logger,
        "agrupar_verbas",
        novo_processo_id=novo_processo.id,
        user_id=request.user.pk,
        tipo_verba=tipo_verba,
    )

    for identificador in falhas_pcd:
        messages.warning(
            request,
            f"PCD para diária {identificador} não pôde ser gerado automaticamente.",
        )

    messages.success(request, f"Processo #{novo_processo.id} gerado com sucesso!")
    if not falhas_pcd:
        messages.info(request, 'PCDs gerados! Acesse o Painel de Assinaturas para enviar ao Autentique.')
    return redirect('editar_processo_verbas', pk=novo_processo.id)


def _montar_post_capa_com_campos_canonicos(request, processo):
    """Injeta campos obrigatórios e canônicos do processo de verbas no payload do form."""
    data = request.POST.copy()

    tipo_pagamento_verbas, _ = TiposDePagamento.objects.get_or_create(
        tipo_pagamento__iexact="VERBAS INDENIZATÓRIAS",
        defaults={"tipo_pagamento": "VERBAS INDENIZATÓRIAS"},
    )
    totais = _forcar_campos_canonicos_processo_verbas(processo)

    data["processo-tipo_pagamento"] = str(tipo_pagamento_verbas.id)
    data["processo-extraorcamentario"] = ""
    data["processo-valor_bruto"] = str(totais["total_geral"])
    data["processo-valor_liquido"] = str(totais["total_geral"])

    return data


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas_capa_action(request, pk):
    """Spoke POST da capa de processos de verbas."""
    from django.core.exceptions import PermissionDenied
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    data = _montar_post_capa_com_campos_canonicos(request, processo)
    processo_form = ProcessoForm(data, instance=processo, prefix="processo")

    if not processo_form.is_valid():
        messages.error(request, "Verifique os erros na capa do processo.")
        return redirect("editar_processo_verbas_capa", pk=pk)

    processo_form.save()
    _forcar_campos_canonicos_processo_verbas(processo)
    messages.success(request, f"Capa do Processo #{processo.id} atualizada com sucesso!")
    return redirect("editar_processo_verbas", pk=processo.id)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas_pendencias_action(request, pk):
    """Spoke POST de pendências para processos de verbas."""
    from django.core.exceptions import PermissionDenied
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    pendencia_formset = PendenciaFormSet(request.POST, instance=processo, prefix="pendencia")

    if not pendencia_formset.is_valid():
        messages.error(request, "Verifique os erros nas pendências.")
        return redirect("editar_processo_verbas_pendencias", pk=pk)

    pendencia_formset.save()
    _forcar_campos_canonicos_processo_verbas(processo)
    messages.success(request, f"Pendências do Processo #{processo.id} atualizadas com sucesso!")
    return redirect("editar_processo_verbas", pk=processo.id)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas_documentos_action(request, pk):
    """Spoke POST de documentos do processo de verbas."""
    from django.core.exceptions import PermissionDenied
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=processo, prefix="documento")

    if not documento_formset.is_valid():
        messages.error(request, "Verifique os erros nos documentos.")
        return redirect("editar_processo_verbas_documentos", pk=pk)

    documento_formset.save()
    messages.success(request, f"Documentos do Processo #{processo.id} atualizados com sucesso!")
    return redirect("editar_processo_verbas", pk=processo.id)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_processos_verbas", raise_exception=True)
def add_documento_verba_action(request, tipo_verba, pk):
    """Anexa documento a uma verba especifica e retorna resultado JSON."""
    config = _VERBA_CONFIG.get(tipo_verba)
    if not config:
        return JsonResponse({'ok': False, 'error': 'Tipo de verba invalido.'}, status=400)

    permissao = _get_permissao_gestao_verba(tipo_verba)
    if not permissao or not request.user.has_perm(permissao):
        raise PermissionDenied('Voce nao tem permissao para anexar documentos nesta verba.')

    modelo_verba = config['model']
    modelo_documento = config['doc_model']
    fk_name = config['doc_fk']
    tipo_doc_seguro = config['doc_tipo_seguro']
    verba = get_object_or_404(modelo_verba, id=pk)

    try:
        arquivo, tipo_id = _obter_dados_upload_documento(request)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    doc, erro = _salvar_documento_upload(
        verba,
        modelo_documento=modelo_documento,
        fk_name=fk_name,
        arquivo=arquivo,
        tipo_id=tipo_id,
        obrigatorio=True,
        tipo_doc_seguro=tipo_doc_seguro,
    )
    if erro:
        return JsonResponse({'ok': False, 'error': erro}, status=400)
    logger.info("mutation=add_documento_verba tipo_verba=%s verba_id=%s user_id=%s doc_id=%s", tipo_verba, pk, request.user.pk, getattr(doc, 'id', None))
    return JsonResponse({'ok': True, 'doc_id': getattr(doc, 'id', None)})
