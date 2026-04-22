import logging
logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from pagamentos.domain_models import Processo
from pagamentos.forms import DocumentoFormSet, DocumentoOrcamentarioFormSet, PendenciaFormSet, ProcessoForm
from pagamentos.models import TiposDePagamento
from verbas_indenizatorias.constants import STATUS_VERBA_APROVADA, STATUS_VERBA_REVISADA
from verbas_indenizatorias.models import StatusChoicesVerbasIndenizatorias
from verbas_indenizatorias.services.processo_integration import criar_processo_e_vincular_verbas
from .helpers import _forcar_campos_canonicos_processo_verbas
from ..shared.registry import (
    _CREDOR_AGRUPAMENTO_MULTIPLO,
    _VERBA_CONFIG,
    _obter_credor_agrupamento,
)


def _usuario_pode_revisar_solicitacoes(user):
    return user.has_perm("pagamentos.pode_operar_contas_pagar") or user.has_perm("pagamentos.acesso_backoffice")


def _set_status_case_insensitive(verba, status_str):
    status, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
        status_choice__iexact=status_str,
        defaults={"status_choice": status_str},
    )
    verba.status = status
    verba.save(update_fields=["status"])


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
    logger.info("mutation=agrupar_verbas novo_processo_id=%s user_id=%s tipo_verba=%s", novo_processo.id, request.user.pk, tipo_verba)

    for identificador in falhas_pcd:
        messages.warning(
            request,
            f"PCD para diária {identificador} não pôde ser gerado automaticamente.",
        )

    messages.success(request, f"Processo #{novo_processo.id} gerado com sucesso!")
    if not falhas_pcd:
        messages.info(request, 'PCDs gerados! Acesse o Painel de Assinaturas para enviar ao Autentique.')
    return redirect('editar_processo_verbas', pk=novo_processo.id)


@require_POST
@permission_required("verbas_indenizatorias.pode_visualizar_verbas", raise_exception=True)
def aprovar_revisao_solicitacao_action(request, tipo_verba, pk):
    if not _usuario_pode_revisar_solicitacoes(request.user):
        return HttpResponseForbidden("Acesso negado para revisão operacional de solicitações.")

    config = _VERBA_CONFIG.get(tipo_verba)
    if not config:
        messages.error(request, "Tipo de solicitação inválido para revisão.")
        return redirect("painel_revisar_solicitacoes")

    solicitacao = get_object_or_404(
        config["model"].objects.select_related("status", "processo"),
        id=pk,
    )
    if solicitacao.processo_id:
        messages.warning(request, "Solicitação já está vinculada a processo.")
        return redirect("revisar_solicitacao_verba", tipo_verba=tipo_verba, pk=pk)

    status_atual = (solicitacao.status.status_choice if solicitacao.status else "").upper()
    if status_atual != STATUS_VERBA_APROVADA:
        messages.warning(request, "A solicitação precisa estar APROVADA para revisão operacional.")
        return redirect("revisar_solicitacao_verba", tipo_verba=tipo_verba, pk=pk)

    _set_status_case_insensitive(solicitacao, STATUS_VERBA_REVISADA)
    logger.info(
        "mutation=aprovar_revisao_solicitacao tipo_verba=%s solicitacao_id=%s user_id=%s",
        tipo_verba,
        solicitacao.id,
        request.user.pk,
    )
    messages.success(request, "Solicitação revisada e liberada para agrupamento.")
    return redirect("revisar_solicitacao_verba", tipo_verba=tipo_verba, pk=pk)


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
    from commons.shared.access_utils import user_is_entity_owner
    processo = get_object_or_404(Processo, id=pk)
    if not user_is_entity_owner(request.user, processo):
        from django.http import HttpResponse
        return HttpResponse("Acesso negado: você não é o responsável por este processo.", status=403)
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
    from commons.shared.access_utils import user_is_entity_owner
    processo = get_object_or_404(Processo, id=pk)
    if not user_is_entity_owner(request.user, processo):
        from django.http import HttpResponse
        return HttpResponse("Acesso negado: você não é o responsável por este processo.", status=403)
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


@require_POST
def add_documento_verba_action(request, tipo_verba, pk):
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
