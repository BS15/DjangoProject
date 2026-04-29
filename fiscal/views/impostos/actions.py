"""Views de ação para agrupamento de retenções e operações de imposto."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from fiscal.services.impostos import (
    agrupar_retencoes_em_processo_recolhimento,
    anexar_documentos_competencia_retencoes,
)
import logging

logger = logging.getLogger(__name__)


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def preparar_revisao_agrupamento_action(request: HttpRequest) -> HttpResponse:
    """Recebe a seleção de retenções e redireciona para a página de revisão do agrupamento."""
    selecionados = request.POST.getlist("retencao_ids") or request.POST.getlist("itens_selecionados")

    if not selecionados:
        messages.warning(request, "Nenhum item selecionado para agrupar.")
        return redirect("painel_impostos_view")

    ids_param = ",".join(str(i) for i in selecionados)
    url = reverse("revisar_agrupamento_retencoes_view") + f"?ids={ids_param}"
    return redirect(url)


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def agrupar_retencoes_action(request: HttpRequest) -> HttpResponse:
    """Agrupa retenções selecionadas em um novo processo de recolhimento."""
    selecionados = request.POST.getlist("retencao_ids") or request.POST.getlist("itens_selecionados")

    if not selecionados:
        messages.warning(request, "Nenhum item selecionado para agrupar.")
        return redirect("painel_impostos_view")

    try:
        novo_processo = agrupar_retencoes_em_processo_recolhimento(selecionados)
    except ValueError as exc:
        messages.warning(request, str(exc))
        return redirect("painel_impostos_view")

    if not novo_processo:
        messages.warning(request, "Nenhuma retenção elegível para agrupamento foi encontrada.")
        return redirect("painel_impostos_view")

    logger.info("mutation=agrupar_retencoes novo_processo_id=%s user_id=%s", novo_processo.id, request.user.pk)

    messages.success(request, f"Processo #{novo_processo.id} para recolhimento gerado com sucesso!")
    return redirect("editar_processo", pk=novo_processo.id)


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def anexar_documentos_retencoes_action(request: HttpRequest) -> HttpResponse:
    """Anexa guia, comprovante e relatório mensal aos processos de recolhimento das retenções selecionadas."""
    selecionados = request.POST.getlist("retencao_ids")
    guia_arquivo = request.FILES.get("guia_arquivo")
    comprovante_arquivo = request.FILES.get("comprovante_arquivo")
    mes_raw = (request.POST.get("mes_referencia") or "").strip()
    ano_raw = (request.POST.get("ano_referencia") or "").strip()

    if not selecionados:
        messages.warning(request, "Selecione ao menos uma retenção para anexar documentos.")
        return redirect("painel_impostos_view")

    if not guia_arquivo or not comprovante_arquivo:
        messages.error(request, "É obrigatório anexar a guia e o comprovante para concluir a operação.")
        return redirect("painel_impostos_view")

    if not mes_raw.isdigit() or not ano_raw.isdigit():
        messages.error(request, "Informe mês e ano de referência válidos para gerar o relatório.")
        return redirect("painel_impostos_view")

    mes_referencia = int(mes_raw)
    ano_referencia = int(ano_raw)
    if mes_referencia < 1 or mes_referencia > 12:
        messages.error(request, "Mês de referência inválido.")
        return redirect("painel_impostos_view")

    total_processos = anexar_documentos_competencia_retencoes(
        retencao_ids=selecionados,
        guia_bytes=guia_arquivo.read(),
        guia_nome=guia_arquivo.name,
        comprovante_bytes=comprovante_arquivo.read(),
        comprovante_nome=comprovante_arquivo.name,
        mes=mes_referencia,
        ano=ano_referencia,
    )

    if not total_processos:
        messages.error(
            request,
            "Nenhuma retenção elegível encontrada para a competência informada. Verifique se as retenções já foram agrupadas.",
        )
        return redirect("painel_impostos_view")

    messages.success(
        request,
        f"Guia, comprovante e relatório mensal anexados com sucesso em {total_processos} processo(s) de recolhimento.",
    )
    return redirect("painel_impostos_view")


__all__ = [
    "preparar_revisao_agrupamento_action",
    "agrupar_retencoes_action",
    "anexar_documentos_retencoes_action",
]
