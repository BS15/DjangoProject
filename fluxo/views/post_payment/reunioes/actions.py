"""Acoes POST de gerenciamento de reunioes do conselho."""

import logging
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from fluxo.domain_models import Processo, ProcessoStatus, ReuniaoConselho, ReuniaoConselhoStatus


logger = logging.getLogger(__name__)

REUNIAO_STATUS_ANALISE = {ReuniaoConselhoStatus.AGENDADA, ReuniaoConselhoStatus.EM_ANALISE}


@require_POST
@permission_required("fluxo.pode_auditar_conselho", raise_exception=True)
def gerenciar_reunioes_action(request: HttpRequest) -> HttpResponse:
    """Cria reuniao do conselho a partir do formulario do painel."""
    numero = request.POST.get("numero", "").strip()
    trimestre_referencia = request.POST.get("trimestre_referencia", "").strip()
    data_reuniao = request.POST.get("data_reuniao") or None

    if numero and trimestre_referencia:
        try:
            ReuniaoConselho.objects.create(
                numero=int(numero),
                trimestre_referencia=trimestre_referencia,
                data_reuniao=data_reuniao,
            )
            messages.success(request, f"{numero}ª Reunião criada com sucesso.")
        except ValueError:
            messages.error(request, "Número da reunião inválido.")
        except IntegrityError as exc:
            logger.exception(
                "IntegrityError ao criar reunião: numero=%s, trimestre=%s",
                numero,
                trimestre_referencia,
            )
            messages.error(request, "Erro ao criar reunião. Verifique os dados e tente novamente.")
    else:
        messages.warning(request, "Preencha o número e o trimestre de referência.")

    return redirect("gerenciar_reunioes")


@require_POST
@permission_required("fluxo.pode_auditar_conselho", raise_exception=True)
def montar_pauta_reuniao_action(request: HttpRequest, reuniao_id: int) -> HttpResponse:
    """Vincula processos selecionados a pauta da reuniao do conselho."""
    reuniao = get_object_or_404(ReuniaoConselho, id=reuniao_id)
    processos_ids = request.POST.getlist("processos_selecionados")
    if processos_ids:
        processos = Processo.objects.select_for_update().filter(id__in=processos_ids)
        updated = 0
        for processo in processos:
            processo.reuniao_conselho = reuniao
            processo.full_clean()
            processo.save(update_fields=["reuniao_conselho"])
            updated += 1
        messages.success(request, f"{updated} processo(s) adicionado(s) à pauta.")
    else:
        messages.warning(request, "Nenhum processo selecionado.")
    return redirect("montar_pauta_reuniao", reuniao_id=reuniao_id)


@require_POST
@permission_required("fluxo.pode_auditar_conselho", raise_exception=True)
def iniciar_conselho_reuniao_action(request: HttpRequest, reuniao_id: int) -> HttpResponse:
    """Inicializa fila de analise para processos selecionados de uma reuniao."""
    reuniao = get_object_or_404(ReuniaoConselho, id=reuniao_id)
    if reuniao.status not in REUNIAO_STATUS_ANALISE:
        messages.error(request, "A reunião selecionada está concluída e não pode iniciar nova análise.")
        return redirect("analise_reuniao", reuniao_id=reuniao_id)

    ids_raw = request.POST.getlist("processo_ids")
    process_ids = [int(pid) for pid in ids_raw if pid.isdigit()]
    if not process_ids:
        messages.warning(request, "Selecione ao menos um processo para iniciar a revisão.")
        return redirect("analise_reuniao", reuniao_id=reuniao_id)

    processos_validos = set(
        Processo.objects.filter(
            id__in=process_ids,
            reuniao_conselho_id=reuniao_id,
            status__status_choice__iexact=ProcessoStatus.CONTABILIZADO_CONSELHO,
        ).values_list("id", flat=True)
    )
    fila = [pid for pid in process_ids if pid in processos_validos]
    if not fila:
        messages.error(request, "Nenhum processo selecionado é elegível para análise nesta reunião.")
        return redirect("analise_reuniao", reuniao_id=reuniao_id)
    if len(fila) < len(process_ids):
        messages.warning(request, "Alguns processos foram ignorados por não pertencerem à reunião ou estágio esperado.")

    if reuniao.status == ReuniaoConselhoStatus.AGENDADA:
        reuniao.status = ReuniaoConselhoStatus.EM_ANALISE
        reuniao.save(update_fields=["status"])

    request.session["conselho_queue"] = fila
    request.session["conselho_reuniao_id"] = reuniao_id
    request.session.modified = True
    return redirect("conselho_processo", pk=fila[0])


__all__ = [
    "gerenciar_reunioes_action",
    "montar_pauta_reuniao_action",
    "iniciar_conselho_reuniao_action",
]
