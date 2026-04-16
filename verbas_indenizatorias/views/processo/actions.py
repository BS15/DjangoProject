from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from fluxo.domain_models import Processo
from fluxo.forms import DocumentoFormSet, DocumentoOrcamentarioFormSet, PendenciaFormSet, ProcessoForm
from fluxo.models import TiposDePagamento
from verbas_indenizatorias.services.processo_integration import criar_processo_e_vincular_verbas
from .helpers import _forcar_campos_canonicos_processo_verbas
from ..shared.registry import (
    _CREDOR_AGRUPAMENTO_MULTIPLO,
    _VERBA_CONFIG,
    _obter_credor_agrupamento,
)


@require_POST
@permission_required("verbas_indenizatorias.pode_agrupar_verbas", raise_exception=True)
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

    # Todas as verbas devem estar aprovadas e sem processo para agrupamento.
    itens_query = modelo_verba.objects.select_related('beneficiario').filter(
        id__in=selecionados,
        processo__isnull=True,
        status__status_choice__iexact='APROVADA',
    )

    itens = list(itens_query)

    if not itens:
        messages.warning(
            request,
            'Selecione itens APROVADOS e ainda não agrupados em processo para gerar pagamento.',
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
        tipo_de_pagamento__iexact="VERBAS INDENIZATÓRIAS",
        defaults={"tipo_de_pagamento": "VERBAS INDENIZATÓRIAS"},
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
    processo = get_object_or_404(Processo, id=pk)
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
    processo = get_object_or_404(Processo, id=pk)
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
    processo = get_object_or_404(Processo, id=pk)
    documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=processo, prefix="documento")

    if not documento_formset.is_valid():
        messages.error(request, "Verifique os erros nos documentos.")
        return redirect("editar_processo_verbas_documentos", pk=pk)

    documento_formset.save()
    messages.success(request, f"Documentos do Processo #{processo.id} atualizados com sucesso!")
    return redirect("editar_processo_verbas", pk=processo.id)
