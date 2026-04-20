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
from verbas_indenizatorias.forms import ComprovanteDiariaFormSet, DiariaForm
from verbas_indenizatorias.models import Diaria, PrestacaoContasDiaria
from verbas_indenizatorias.services.documentos import (
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
from commons.shared.integracoes.autentique import enviar_documento_para_assinatura


def _redirect_com_next(request, fallback_name, **kwargs):
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback_name, **kwargs)


def _preparar_nova_diaria(diaria):
    """Cria diária já operacional, sem etapa interna de solicitação/autorização."""
    from verbas_indenizatorias.models import StatusChoicesVerbasIndenizatorias

    diaria.autorizada = True
    status_aprovada, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
        status_choice__iexact='APROVADA',
        defaults={'status_choice': 'APROVADA'},
    )
    diaria.status = status_aprovada


def _salvar_diaria_base(form, criador=None):
    diaria = form.save(commit=False)
    _preparar_nova_diaria(diaria)
    if criador and not diaria.criado_por_id:
        diaria.criado_por = criador
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
@permission_required('verbas_indenizatorias.pode_criar_diarias', raise_exception=True)
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
            messages.error(request, 'Verifique os erros nos comprovantes.')
            return _redirect_com_next(request, 'gerenciar_prestacao', pk=diaria.id)

        try:
            for form in comprovante_formset.forms:
                cleaned_data = form.cleaned_data or {}
                if cleaned_data.get('DELETE'):
                    continue
                if not cleaned_data:
                    continue
                arquivo = cleaned_data.get('arquivo')
                tipo_id = cleaned_data.get('tipo').id if cleaned_data.get('tipo') else None
                if arquivo:
                    erro = _validar_upload_documento(arquivo, tipo_id, obrigatorio=True)
                    if erro:
                        messages.error(request, erro)
                        return _redirect_com_next(request, 'gerenciar_prestacao', pk=diaria.id)
                is_existing = bool(form.instance.pk)
                if form.has_changed() or not is_existing:
                    instance = form.save(commit=False)
                    instance.prestacao = prestacao
                    instance.save()
            logger.info("mutation=registrar_comprovante_diaria diaria_id=%s user_id=%s", diaria.id, request.user.pk)
            messages.success(request, 'Comprovantes atualizados com sucesso.')
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))

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
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))

    return redirect('revisar_prestacao', pk=pk)


@require_POST
@permission_required('verbas_indenizatorias.pode_gerenciar_diarias', raise_exception=True)
def cancelar_diaria_action(request, pk):
    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update(), id=pk)

        try:
            diaria.avancar_status('REJEITADA')
        except ValidationError:
            _set_status_case_insensitive(diaria, 'CANCELADO / ANULADO')

        diaria.autorizada = False
        diaria.save(update_fields=['autorizada'])
        logger.info("mutation=cancelar_diaria diaria_id=%s user_id=%s", diaria.id, request.user.pk)

    messages.warning(request, f'Diária #{diaria.numero_siscac} cancelada.')
    return redirect('gerenciar_diaria', pk=diaria.id)


@require_POST
@permission_required('verbas_indenizatorias.pode_gerenciar_diarias', raise_exception=True)
def liberar_para_assinatura_action(request, pk):
    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update(), pk=pk)

        if not diaria.proponente or not diaria.proponente.email:
            messages.error(request, 'A diária não possui proponente com e-mail para assinatura.')
            return redirect('liberar_assinatura_diaria_spoke', pk=diaria.id)

        assinatura = (
            diaria.assinaturas_autentique.select_for_update()
            .filter(tipo_documento='PCD')
            .order_by('-criado_em')
            .first()
        )

        if assinatura and assinatura.arquivo:
            assinatura.arquivo.open('rb')
            try:
                pdf_bytes = assinatura.arquivo.read()
            finally:
                try:
                    assinatura.arquivo.close()
                except Exception:
                    pass
        else:
            assinatura = gerar_e_anexar_pcd_diaria(diaria, criador=request.user)
            assinatura.arquivo.open('rb')
            try:
                pdf_bytes = assinatura.arquivo.read()
            finally:
                try:
                    assinatura.arquivo.close()
                except Exception:
                    pass

        payload = enviar_documento_para_assinatura(
            pdf_bytes,
            f"PCD_Diaria_{diaria.id}",
            signatarios=[{'email': diaria.proponente.email}],
        )

        assinatura.autentique_id = payload.get('id')
        assinatura.autentique_url = payload.get('url') or ''
        assinatura.dados_signatarios = payload.get('signers_data') or {}
        assinatura.status = 'PENDENTE'
        assinatura.save(update_fields=['autentique_id', 'autentique_url', 'dados_signatarios', 'status'])

        logger.info(
            "mutation=liberar_para_assinatura_diaria diaria_id=%s user_id=%s assinatura_id=%s autentique_id=%s",
            diaria.id,
            request.user.pk,
            assinatura.id,
            assinatura.autentique_id,
        )

    messages.success(request, 'Documento liberado para assinatura com sucesso.')
    return redirect('gerenciar_diaria', pk=pk)

