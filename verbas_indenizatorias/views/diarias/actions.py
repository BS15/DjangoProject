import logging
logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.utils.http import url_has_allowed_host_and_scheme

from pagamentos.domain_models import Processo
from pagamentos.services.cancelamentos import cancelar_verba, extrair_dados_devolucao_do_post
from verbas_indenizatorias.constants import (
    STATUS_VERBA_APROVADA,
    STATUS_VERBA_RASCUNHO,
    STATUS_VERBA_SOLICITADA,
)
from verbas_indenizatorias.forms import ComprovanteDiariaFormSet, DiariaForm
from verbas_indenizatorias.forms import DiariaComSolicitacaoAssinadaForm
from verbas_indenizatorias.models import Diaria, PrestacaoContasDiaria
from verbas_indenizatorias.services.documentos import (
    anexar_solicitacao_assinada_diaria,
    gerar_e_anexar_pcd_diaria,
    gerar_e_anexar_scd_diaria,
    gerar_e_anexar_termo_prestacao_diaria,
)
from verbas_indenizatorias.services.prestacao import aceitar_prestacao, encerrar_prestacao, obter_ou_criar_prestacao
from verbas_indenizatorias.services.vinculos_diaria import (
    desvincular_diaria_do_processo,
    processo_em_pre_autorizacao,
    vincular_diaria_em_processo_existente,
)
from ..shared.documents import _validar_upload_documento
from .access import _pode_acessar_prestacao, _pode_gerenciar_vinculo_diaria


PRESTACAO_REVIEW_QUEUE_KEY = 'prestacoes_review_queue'

def _redirect_com_next(request, fallback_name, **kwargs):
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback_name, **kwargs)


def _obter_fila_prestacoes_da_sessao(request):
    fila = []
    for valor in request.session.get(PRESTACAO_REVIEW_QUEUE_KEY, []):
        if str(valor).isdigit():
            fila.append(int(valor))
    return fila


def _limpar_fila_prestacoes_da_sessao(request):
    request.session.pop(PRESTACAO_REVIEW_QUEUE_KEY, None)
    request.session.modified = True


@require_POST
@permission_required('verbas_indenizatorias.visualizar_prestacao_contas', raise_exception=True)
def iniciar_revisao_prestacoes_action(request):
    ids_raw = request.POST.getlist('prestacao_ids')
    prestacao_ids = [int(pid) for pid in ids_raw if pid.isdigit()]

    if not prestacao_ids:
        messages.warning(request, 'Selecione ao menos uma prestação para iniciar a revisão.')
        return redirect('painel_revisar_prestacoes')

    ids_validos = set(
        PrestacaoContasDiaria.objects.filter(id__in=prestacao_ids).values_list('id', flat=True)
    )
    fila = [pid for pid in prestacao_ids if pid in ids_validos]

    if not fila:
        messages.warning(request, 'Nenhuma prestação selecionada é válida para revisão.')
        return redirect('painel_revisar_prestacoes')

    request.session[PRESTACAO_REVIEW_QUEUE_KEY] = fila
    request.session.modified = True
    return redirect('revisar_prestacao', pk=fila[0])


@require_POST
@permission_required('verbas_indenizatorias.visualizar_prestacao_contas', raise_exception=True)
def sair_revisao_prestacoes_action(request):
    _limpar_fila_prestacoes_da_sessao(request)
    messages.info(request, 'Fila de revisão de diárias encerrada.')
    return redirect('painel_revisar_prestacoes')


def _preparar_nova_diaria(diaria):
    """Cria diária em rascunho para seguir fluxo de solicitação/autorização."""
    diaria.definir_status(STATUS_VERBA_RASCUNHO, autorizada=False)


def _preparar_diaria_com_solicitacao_assinada(diaria):
    """Cria diária em trilha direta: já aprovada e pronta para fluxo operacional."""
    diaria.definir_status(STATUS_VERBA_APROVADA, autorizada=True)


def _salvar_diaria_base(form, criador=None, solicitacao_assinada=False):
    diaria = form.save(commit=False)
    if criador and not diaria.criado_por_id:
        diaria.criado_por = criador
    diaria.save()
    if solicitacao_assinada:
        _preparar_diaria_com_solicitacao_assinada(diaria)
    else:
        _preparar_nova_diaria(diaria)
    if hasattr(form, 'save_m2m'):
        form.save_m2m()
    return diaria


@require_POST
@permission_required('pagamentos.pode_criar_diarias', raise_exception=True)
def add_diaria_action(request):
    form = DiariaForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Erro ao salvar. Verifique os campos.')
        return redirect('add_diaria')

    with transaction.atomic():
        diaria = _salvar_diaria_base(form, criador=request.user)
        if diaria.tipo_solicitacao == 'COMPLEMENTACAO':
            gerar_e_anexar_scd_diaria(diaria, criador=request.user)
        logger.info("mutation=add_diaria diaria_id=%s user_id=%s", diaria.id, request.user.pk)

    messages.success(request, 'Diária cadastrada com sucesso.')
    return redirect('gerenciar_diaria', pk=diaria.id)


@require_POST
@permission_required('pagamentos.pode_criar_diarias', raise_exception=True)
def add_diaria_assinada_action(request):
    form = DiariaComSolicitacaoAssinadaForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, 'Erro ao salvar diária com solicitação assinada. Verifique os campos.')
        return redirect('add_diaria_assinada')

    with transaction.atomic():
        diaria = _salvar_diaria_base(form, criador=request.user, solicitacao_assinada=True)
        anexar_solicitacao_assinada_diaria(diaria, form.cleaned_data['solicitacao_assinada_arquivo'])
        gerar_e_anexar_pcd_diaria(diaria, criador=request.user)
        logger.info(
            "mutation=add_diaria_assinada diaria_id=%s user_id=%s",
            diaria.id,
            request.user.pk,
        )

    messages.success(
        request,
        'Diária cadastrada em modo solicitação já assinada, aprovada automaticamente e com PCD gerado.',
    )
    return redirect('gerenciar_diaria', pk=diaria.id)


@require_POST
@permission_required('pagamentos.pode_gerenciar_diarias', raise_exception=True)
def solicitar_autorizacao_diaria_action(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)
    diaria.definir_status(STATUS_VERBA_SOLICITADA, autorizada=False)
    logger.info("mutation=solicitar_autorizacao_diaria diaria_id=%s user_id=%s", diaria.id, request.user.pk)
    messages.success(request, 'Solicitação de diária enviada para autorização.')
    return redirect('gerenciar_diaria', pk=diaria.id)


@require_POST
def autorizar_diaria_action(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)
    if diaria.proponente_id != request.user.id:
        messages.error(request, 'Você só pode autorizar diárias em que esteja vinculado como proponente.')
        return redirect('painel_autorizacao_diarias')

    status_atual = (getattr(getattr(diaria, 'status', None), 'status_choice', '') or '').upper()
    if status_atual != STATUS_VERBA_SOLICITADA:
        messages.error(request, 'A diária precisa estar no status SOLICITADA para autorização.')
        return redirect('painel_autorizacao_diarias')

    diaria.definir_status(STATUS_VERBA_APROVADA, autorizada=True)
    logger.info("mutation=autorizar_diaria diaria_id=%s user_id=%s", diaria.id, request.user.pk)
    messages.success(request, 'Diária autorizada com sucesso.')
    return redirect('gerenciar_diaria', pk=diaria.id)


@require_POST
@permission_required('pagamentos.pode_visualizar_verbas', raise_exception=True)
def registrar_comprovante_action(request, pk):
    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update().select_related('beneficiario'), id=pk)
        if not _pode_acessar_prestacao(request.user, diaria):
            return HttpResponseForbidden("Acesso negado para prestação de contas desta diária.")

        prestacao = obter_ou_criar_prestacao(diaria)
        if prestacao.status == PrestacaoContasDiaria.STATUS_ENCERRADA:
            messages.error(request, 'A prestação de contas desta diária já foi encerrada.')
            return _redirect_com_next(request, 'gerenciar_prestacao', pk=diaria.id)

        comprovante_formset = ComprovanteDiariaFormSet(
            request.POST,
            request.FILES,
            instance=prestacao,
            prefix='comprovante',
        )

        if not comprovante_formset.is_valid():
            for form in comprovante_formset.forms:
                if form.errors:
                    for field, errors in form.errors.items():
                        messages.error(request, f"Erro no formulário: {field} - {', '.join(errors)}")
            return _redirect_com_next(request, 'gerenciar_prestacao', pk=diaria.id)

        try:
            # Validate file uploads before saving
            for form in comprovante_formset.forms:
                if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                    arquivo = form.cleaned_data.get('arquivo')
                    tipo = form.cleaned_data.get('tipo')
                    if arquivo and tipo:
                        erro = _validar_upload_documento(arquivo, tipo.id, obrigatorio=True)
                        if erro:
                            messages.error(request, erro)
                            return _redirect_com_next(request, 'gerenciar_prestacao', pk=diaria.id)

            # Save all forms (including deletions, handled by formset)
            comprovante_formset.save()
            logger.info("mutation=registrar_comprovante_diaria diaria_id=%s user_id=%s", diaria.id, request.user.pk)
            messages.success(request, 'Comprovantes atualizados com sucesso.')
        except (ValidationError, ValueError) as exc:
            error_msg = ' '.join(exc.messages) if hasattr(exc, 'messages') else str(exc)
            messages.error(request, f'Erro ao salvar comprovantes: {error_msg}')
            return _redirect_com_next(request, 'gerenciar_prestacao', pk=diaria.id)

    return _redirect_com_next(request, 'gerenciar_prestacao', pk=diaria.id)


@require_POST
def encerrar_prestacao_action(request, pk):
    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update().select_related('beneficiario'), id=pk)
        if not _pode_acessar_prestacao(request.user, diaria):
            return HttpResponseForbidden("Acesso negado para prestação de contas desta diária.")

        prestacao = obter_ou_criar_prestacao(diaria)
        if prestacao.status == PrestacaoContasDiaria.STATUS_ENCERRADA:
            messages.info(request, 'A prestação de contas já está encerrada.')
            return _redirect_com_next(request, 'gerenciar_prestacao', pk=diaria.id)

        encerrar_prestacao(prestacao, request.user)
        gerar_e_anexar_termo_prestacao_diaria(diaria, request.user)
        logger.info("mutation=encerrar_prestacao_diaria diaria_id=%s prestacao_id=%s user_id=%s", diaria.id, prestacao.id, request.user.pk)

    messages.success(request, 'Prestação de contas encerrada com sucesso.')
    return _redirect_com_next(request, 'gerenciar_prestacao', pk=diaria.id)


@require_POST
def vincular_diaria_processo_action(request, pk):
    if not _pode_gerenciar_vinculo_diaria(request.user):
        return HttpResponseForbidden("Acesso negado para vinculação de diárias.")

    processo_id = request.POST.get('processo_id')
    if not processo_id:
        messages.error(request, 'Informe o processo para vincular a diária.')
        return redirect('vinculo_diaria_spoke', pk=pk)

    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update().select_related('processo__status'), id=pk)
        processo = get_object_or_404(Processo.objects.select_for_update().select_related('status'), id=processo_id)
        if not processo_em_pre_autorizacao(processo):
            messages.error(request, 'O processo selecionado já passou da etapa de autorização.')
            return redirect('vinculo_diaria_spoke', pk=pk)
        try:
            vincular_diaria_em_processo_existente(diaria, processo)
            logger.info(
                "mutation=vincular_diaria_processo diaria_id=%s processo_id=%s user_id=%s",
                diaria.id,
                processo.id,
                request.user.pk,
            )
            messages.success(request, f'Diária vinculada ao processo #{processo.id} com sucesso.')
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))

    return redirect('gerenciar_diaria', pk=pk)


@require_POST
def desvincular_diaria_processo_action(request, pk):
    if not _pode_gerenciar_vinculo_diaria(request.user):
        return HttpResponseForbidden("Acesso negado para desvinculação de diárias.")

    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update().select_related('processo__status'), id=pk)
        if not diaria.processo_id:
            messages.info(request, 'A diária já está sem processo vinculado.')
            return redirect('vinculo_diaria_spoke', pk=pk)
        try:
            processo_id = diaria.processo_id
            desvincular_diaria_do_processo(diaria)
            logger.info(
                "mutation=desvincular_diaria_processo diaria_id=%s processo_id=%s user_id=%s",
                diaria.id,
                processo_id,
                request.user.pk,
            )
            messages.success(request, 'Diária desvinculada do processo com sucesso.')
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))

    return redirect('gerenciar_diaria', pk=pk)


@require_POST
@permission_required('verbas_indenizatorias.analisar_prestacao_contas', raise_exception=True)
def aceitar_prestacao_action(request, pk):
    prestacao_aceita = False
    with transaction.atomic():
        prestacao = get_object_or_404(
            PrestacaoContasDiaria.objects.select_for_update().select_related('diaria__processo'),
            pk=pk,
        )
        diaria = prestacao.diaria
        if not diaria.processo:
            messages.error(request, 'A diária precisa estar vinculada a um processo para aceitar a prestação.')
            return redirect('revisar_prestacao', pk=prestacao.id)

        try:
            aceitar_prestacao(prestacao, request.user, diaria.processo)
            gerar_e_anexar_termo_prestacao_diaria(diaria, request.user)
            logger.info(
                "mutation=aceitar_prestacao_diaria diaria_id=%s prestacao_id=%s processo_id=%s user_id=%s",
                diaria.id,
                prestacao.id,
                diaria.processo.id,
                request.user.pk,
            )
            messages.success(request, 'Prestação aceita e comprovantes anexados ao processo com sucesso.')
            prestacao_aceita = True
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))

    if not prestacao_aceita:
        return redirect('revisar_prestacao', pk=pk)

    fila = _obter_fila_prestacoes_da_sessao(request)
    if pk in fila:
        idx = fila.index(pk)
        proxima_prestacao = fila[idx + 1] if idx < len(fila) - 1 else None
        if proxima_prestacao:
            return redirect('revisar_prestacao', pk=proxima_prestacao)
        _limpar_fila_prestacoes_da_sessao(request)
        messages.info(request, 'Não há mais diárias na fila de revisão.')
        return redirect('painel_revisar_prestacoes')

    return redirect('revisar_prestacao', pk=pk)


@require_POST
@permission_required('pagamentos.pode_gerenciar_diarias', raise_exception=True)
def cancelar_diaria_action(request, pk):
    justificativa = (request.POST.get("justificativa") or "").strip()
    if not justificativa:
        messages.error(request, "A justificativa do cancelamento é obrigatória.")
        return redirect("cancelar_diaria_spoke", pk=pk)

    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update().select_related("processo__status"), id=pk)

        try:
            cancelar_verba(diaria, justificativa, request.user, dados_devolucao=extrair_dados_devolucao_do_post(request))
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("cancelar_diaria_spoke", pk=pk)
        logger.info("mutation=cancelar_diaria diaria_id=%s user_id=%s", diaria.id, request.user.pk)

    messages.warning(request, f'Diária #{diaria.numero_siscac} cancelada.')
    return redirect('gerenciar_diaria', pk=diaria.id)

