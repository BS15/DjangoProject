"""Telas de revisao da etapa de conselho fiscal."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .....models import Processo
from .....services.shared import gerar_resposta_pdf
from ...helpers import _processo_fila_detalhe_view


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def conselho_processo_view(request, pk):
    """Revisa processo na etapa de conselho fiscal."""
    processo = get_object_or_404(Processo.objects.select_related("reuniao_conselho"), id=pk)
    reuniao = processo.reuniao_conselho
    if not reuniao:
        messages.error(request, f"Processo #{processo.id} não está vinculado a uma reunião do Conselho.")
        return redirect("painel_conselho")
    if reuniao.status not in {"AGENDADA", "EM_ANALISE"}:
        messages.error(request, f"A reunião {reuniao.numero}ª está concluída e não permite nova análise.")
        return redirect("painel_conselho")

    return _processo_fila_detalhe_view(
        request,
        pk,
        permission="processos.pode_auditar_conselho",
        queue_key="conselho_queue",
        fallback_view="analise_reuniao",
        fallback_kwargs={"reuniao_id": reuniao.id},
        session_keys_to_clear=["conselho_reuniao_id"],
        current_view="conselho_processo",
        template_name="fluxo/conselho_processo.html",
        approve_action="aprovar",
        approve_status="APROVADO - PENDENTE ARQUIVAMENTO",
        approve_message="Processo #{processo_id} aprovado pelo Conselho e liberado para arquivamento!",
        reject_action="rejeitar",
        reject_status="PAGO - A CONTABILIZAR",
        reject_message="Processo #{processo_id} recusado pelo Conselho Fiscal e devolvido para a Contabilidade!",
        editable=False,
    )


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
@xframe_options_sameorigin
def gerar_parecer_conselho_view(request, pk):
    """Gera e retorna o PDF de parecer do conselho para um processo."""
    processo = get_object_or_404(Processo, pk=pk)
    numero_reuniao = processo.reuniao_conselho.numero if processo.reuniao_conselho else None
    nome_arquivo = f"Parecer_Conselho_Fiscal_Proc_{processo.id}.pdf"
    return gerar_resposta_pdf(
        "conselho_fiscal",
        processo,
        nome_arquivo,
        inline=True,
        numero_reuniao=numero_reuniao,
    )


__all__ = ["conselho_processo_view", "gerar_parecer_conselho_view"]
