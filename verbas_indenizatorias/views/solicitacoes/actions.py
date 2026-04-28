import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from requests.exceptions import RequestException

from commons.shared.integracoes.autentique import enviar_documento_para_assinatura
from commons.shared.logging_gradients import log_audit, log_critical, log_recoverable
from verbas_indenizatorias.constants import STATUS_VERBA_APROVADA, STATUS_VERBA_REVISADA
from verbas_indenizatorias.services.documentos import gerar_e_anexar_pcd_diaria
from ..shared.registry import _VERBA_CONFIG


logger = logging.getLogger(__name__)


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
