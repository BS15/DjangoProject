import logging
logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from requests.exceptions import RequestException

from pagamentos.domain_models import Processo
from pagamentos.forms import DocumentoFormSet, DocumentoOrcamentarioFormSet, PendenciaFormSet, ProcessoForm
from pagamentos.models import TiposDePagamento
from commons.shared.logging_gradients import log_audit, log_critical, log_recoverable
from commons.shared.integracoes.autentique import enviar_documento_para_assinatura
from verbas_indenizatorias.constants import STATUS_VERBA_APROVADA, STATUS_VERBA_REVISADA
from verbas_indenizatorias.services.documentos import gerar_e_anexar_pcd_diaria
from verbas_indenizatorias.services.processo_integration import criar_processo_e_vincular_verbas
from .helpers import _forcar_campos_canonicos_processo_verbas, _pode_gerenciar_processo_verbas_da_entidade
from ..shared.registry import (
    _CREDOR_AGRUPAMENTO_MULTIPLO,
    _VERBA_CONFIG,
    _obter_credor_agrupamento,
)


def _emitir_pcd_e_enviar_para_assinatura_beneficiario(diaria, criador):
    assinatura = (
        diaria.assinaturas_autentique.select_for_update()
        .filter(tipo_documento="PCD")
        .order_by("-criado_em")
        .first()
    )

    if assinatura and assinatura.arquivo:
        assinatura.arquivo.open("rb")
        try:
            pdf_bytes = assinatura.arquivo.read()
        finally:
            try:
                assinatura.arquivo.close()
            except Exception as exc:
                log_recoverable(
                    logger,
                    "erro_ao_fechar_arquivo_assinatura_diaria",
                    exc=exc,
                    assinatura_id=assinatura.id,
                )
    else:
        assinatura = gerar_e_anexar_pcd_diaria(diaria, criador=criador)
        assinatura.arquivo.open("rb")
        try:
            pdf_bytes = assinatura.arquivo.read()
        finally:
            try:
                assinatura.arquivo.close()
            except Exception as exc:
                log_recoverable(
                    logger,
                    "erro_ao_fechar_arquivo_assinatura_diaria",
                    exc=exc,
                    assinatura_id=assinatura.id,
                )

    proponente_email = (getattr(diaria.proponente, "email", "") or "").strip()
    if not proponente_email:
        return assinatura, False

    payload = enviar_documento_para_assinatura(
        pdf_bytes,
        f"PCD_Diaria_{diaria.id}",
        signatarios=[{"email": proponente_email, "action": "SIGN"}],
    )
    autentique_id = payload.get("id")
    if not autentique_id:
        raise RuntimeError("A Autentique não retornou o identificador do documento enviado.")

    assinatura.autentique_id = autentique_id
    assinatura.autentique_url = payload.get("url") or ""
    assinatura.dados_signatarios = payload.get("signers_data") or {}
    assinatura.status = "PENDENTE"
    assinatura.save(update_fields=["autentique_id", "autentique_url", "dados_signatarios", "status"])

    return assinatura, True


@require_POST
@permission_required("pagamentos.pode_agrupar_verbas", raise_exception=True)
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


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def aprovar_revisao_solicitacao_action(request, tipo_verba, pk):
    config = _VERBA_CONFIG.get(tipo_verba)
    if not config:
        messages.error(request, "Tipo de solicitação inválido para revisão.")
        return redirect("painel_revisar_solicitacoes")

    with transaction.atomic():
        solicitacao = get_object_or_404(
            config["model"].objects.select_for_update().select_related("status"),
            id=pk,
        )
        if solicitacao.processo_id:
            messages.warning(request, "Solicitação já está vinculada a processo.")
            return redirect("revisar_solicitacao_verba", tipo_verba=tipo_verba, pk=pk)

        status_atual = (solicitacao.status.status_choice if solicitacao.status else "").upper()
        if status_atual != STATUS_VERBA_APROVADA:
            messages.warning(request, "A solicitação precisa estar APROVADA para revisão operacional.")
            return redirect("revisar_solicitacao_verba", tipo_verba=tipo_verba, pk=pk)

        if tipo_verba == "diaria":
            pcd_enviado_para_assinatura = False
            try:
                assinatura, pcd_enviado_para_assinatura = _emitir_pcd_e_enviar_para_assinatura_beneficiario(
                    solicitacao,
                    criador=request.user,
                )
                if pcd_enviado_para_assinatura:
                    logger.info(
                        "mutation=emitir_pcd_e_liberar_assinatura_diaria_na_revisao diaria_id=%s user_id=%s assinatura_id=%s autentique_id=%s",
                        solicitacao.id,
                        request.user.pk,
                        assinatura.id,
                        assinatura.autentique_id,
                    )
                else:
                    logger.info(
                        "mutation=emitir_pcd_sem_envio_autentique_na_revisao diaria_id=%s user_id=%s assinatura_id=%s",
                        solicitacao.id,
                        request.user.pk,
                        assinatura.id,
                    )
            except RequestException:
                log_critical(
                    logger,
                    "falha_envio_autentique_na_revisao",
                    diaria_id=solicitacao.id,
                    user_id=request.user.pk,
                )
                messages.error(request, "Falha de conexão ao enviar para a Autentique. Tente novamente.")
                return redirect("revisar_solicitacao_verba", tipo_verba=tipo_verba, pk=pk)
            except RuntimeError as exc:
                log_critical(
                    logger,
                    "falha_negocio_envio_autentique_na_revisao",
                    exc=exc,
                    diaria_id=solicitacao.id,
                    user_id=request.user.pk,
                )
                messages.error(request, str(exc))
                return redirect("revisar_solicitacao_verba", tipo_verba=tipo_verba, pk=pk)

        solicitacao.definir_status(STATUS_VERBA_REVISADA)
        log_audit(
            logger,
            "aprovar_revisao_solicitacao",
            tipo_verba=tipo_verba,
            solicitacao_id=solicitacao.id,
            user_id=request.user.pk,
        )
        if tipo_verba == "diaria":
            if pcd_enviado_para_assinatura:
                messages.success(request, "Solicitação revisada. PCD emitido e enviado para assinatura do beneficiário.")
            else:
                messages.warning(
                    request,
                    "Solicitação revisada. O PCD foi emitido, mas não foi enviado ao Autentique porque o proponente não possui e-mail.",
                )
        else:
            messages.success(request, "Solicitação revisada e liberada para agrupamento.")
    return redirect("revisar_solicitacao_verba", tipo_verba=tipo_verba, pk=pk)


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
