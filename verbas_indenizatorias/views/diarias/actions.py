import logging
logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date
from django.utils import timezone
from decimal import Decimal, InvalidOperation

from verbas_indenizatorias.forms import DiariaForm
from verbas_indenizatorias.models import ApostilaDiaria, DevolucaoDiaria, Diaria, PrestacaoContasDiaria
from verbas_indenizatorias.services.documentos import (
    gerar_e_anexar_pcd_diaria,
    gerar_e_anexar_scd_diaria,
    obter_ou_criar_prestacao,
    registrar_comprovante_prestacao,
)
from ..shared.documents import _validar_upload_documento
from .access import _pode_acessar_prestacao
from commons.shared.integracoes.autentique import enviar_documento_para_assinatura



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
    arquivo = request.FILES.get('arquivo')
    tipo_id = request.POST.get('tipo_comprovante') or request.POST.get('tipo')

    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update().select_related('beneficiario'), id=pk)
        if not _pode_acessar_prestacao(request.user, diaria):
            return HttpResponseForbidden("Acesso negado para prestação de contas desta diária.")

        erro = _validar_upload_documento(arquivo, tipo_id, obrigatorio=True)

        if erro:
            messages.error(request, erro)
        else:
            try:
                registrar_comprovante_prestacao(diaria, arquivo, tipo_id)
                logger.info("mutation=registrar_comprovante_diaria diaria_id=%s user_id=%s", diaria.id, request.user.pk)

                credor = diaria.beneficiario
                if not (hasattr(credor, 'usuario') and credor.usuario == request.user):
                    logger.info(
                        "proxy_upload diaria_id=%s operador_id=%s beneficiario_id=%s",
                        diaria.id, request.user.pk, credor.pk,
                    )

                messages.success(request, 'Comprovante anexado com sucesso.')
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages))

    return redirect('gerenciar_diaria', pk=diaria.id)


@require_POST
def encerrar_prestacao_action(request, pk):
    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update().select_related('beneficiario'), id=pk)
        if not _pode_acessar_prestacao(request.user, diaria):
            return HttpResponseForbidden("Acesso negado para prestação de contas desta diária.")

        prestacao = obter_ou_criar_prestacao(diaria)
        if prestacao.status == PrestacaoContasDiaria.STATUS_ENCERRADA:
            messages.info(request, 'A prestação de contas já está encerrada.')
            return redirect('gerenciar_diaria', pk=diaria.id)

        prestacao.status = PrestacaoContasDiaria.STATUS_ENCERRADA
        prestacao.encerrado_em = timezone.now()
        prestacao.encerrado_por = request.user
        prestacao.save(update_fields=['status', 'encerrado_em', 'encerrado_por'])
        logger.info("mutation=encerrar_prestacao_diaria diaria_id=%s prestacao_id=%s user_id=%s", diaria.id, prestacao.id, request.user.pk)

    messages.success(request, 'Prestação de contas encerrada com sucesso.')
    return redirect('gerenciar_diaria', pk=diaria.id)


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
            return redirect('gerenciar_diaria', pk=diaria.id)

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


@require_POST
@permission_required('verbas_indenizatorias.pode_gerenciar_diarias', raise_exception=True)
def registrar_devolucao_diaria_action(request, pk):
    valor_devolvido_raw = (request.POST.get('valor_devolvido') or '').strip().replace(',', '.')
    data_devolucao = parse_date((request.POST.get('data_devolucao') or '').strip())
    motivo = (request.POST.get('motivo') or '').strip()

    if not valor_devolvido_raw or not data_devolucao or not motivo:
        messages.error(request, 'Informe valor devolvido, data da devolução e motivo.')
        return redirect('gerenciar_diaria', pk=pk)

    try:
        valor_devolvido = Decimal(valor_devolvido_raw)
    except InvalidOperation:
        messages.error(request, 'Valor devolvido inválido.')
        return redirect('gerenciar_diaria', pk=pk)

    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update(), pk=pk)
        devolucao = DevolucaoDiaria(
            diaria=diaria,
            valor_devolvido=valor_devolvido,
            data_devolucao=data_devolucao,
            motivo=motivo,
            registrado_por=request.user,
        )
        devolucao.full_clean()
        devolucao.save()
        logger.info(
            "mutation=registrar_devolucao_diaria diaria_id=%s devolucao_id=%s user_id=%s valor=%s",
            diaria.id,
            devolucao.id,
            request.user.pk,
            devolucao.valor_devolvido,
        )

    messages.success(request, 'Devolução da diária registrada com sucesso.')
    return redirect('gerenciar_diaria', pk=pk)


@require_POST
@permission_required('verbas_indenizatorias.pode_gerenciar_diarias', raise_exception=True)
def registrar_apostila_diaria_action(request, pk):
    texto_correcao = (request.POST.get('texto_correcao') or '').strip()
    campo_corrigido = (request.POST.get('campo_corrigido') or '').strip()
    valor_anterior = (request.POST.get('valor_anterior') or '').strip()
    valor_novo = (request.POST.get('valor_novo') or '').strip()

    if not texto_correcao or not campo_corrigido:
        messages.error(request, 'Informe o texto da apostila e o campo corrigido.')
        return redirect('gerenciar_diaria', pk=pk)

    with transaction.atomic():
        diaria = get_object_or_404(Diaria.objects.select_for_update(), pk=pk)
        apostila = ApostilaDiaria(
            diaria=diaria,
            texto_correcao=texto_correcao,
            campo_corrigido=campo_corrigido,
            valor_anterior=valor_anterior,
            valor_novo=valor_novo,
            registrado_por=request.user,
        )
        apostila.full_clean()
        apostila.save()
        logger.info(
            "mutation=registrar_apostila_diaria diaria_id=%s apostila_id=%s user_id=%s campo_corrigido=%s",
            diaria.id,
            apostila.id,
            request.user.pk,
            apostila.campo_corrigido,
        )

    messages.success(request, 'Apostila da diária registrada com sucesso.')
    return redirect('gerenciar_diaria', pk=pk)


