"""Paineis GET de gerenciamento de reunioes do conselho."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from pagamentos.forms import PendenciaForm
from pagamentos.domain_models import Processo, ProcessoStatus, ReuniaoConselho


@require_GET
@permission_required("pagamentos.pode_auditar_conselho", raise_exception=True)
def gerenciar_reunioes_view(request):
    """Exibe listagem de reunioes cadastradas do conselho fiscal."""
    reunioes = ReuniaoConselho.objects.all()
    context = {
        "reunioes": reunioes,
        "pode_interagir": request.user.has_perm("pagamentos.pode_auditar_conselho"),
    }
    return render(request, "pagamentos/gerenciar_reunioes.html", context)


@require_GET
@permission_required("pagamentos.pode_auditar_conselho", raise_exception=True)
def montar_pauta_reuniao_view(request, reuniao_id):
    """Exibe montagem de pauta de uma reuniao especifica do conselho."""
    reuniao = get_object_or_404(ReuniaoConselho, id=reuniao_id)

    processos_na_pauta = reuniao.processos_em_pauta.all().order_by("data_pagamento")
    processos_elegiveis = Processo.objects.filter(
        status__opcao_status__iexact=ProcessoStatus.CONTABILIZADO_CONSELHO,
        reuniao_conselho__isnull=True,
    ).order_by("data_pagamento")

    context = {
        "reuniao": reuniao,
        "processos_na_pauta": processos_na_pauta,
        "processos_elegiveis": processos_elegiveis,
        "pode_interagir": request.user.has_perm("pagamentos.pode_auditar_conselho"),
    }
    return render(request, "pagamentos/montar_pauta_conselho.html", context)


@require_GET
@permission_required("pagamentos.pode_auditar_conselho", raise_exception=True)
def analise_reuniao_view(request, reuniao_id):
    """Exibe painel de analise dos processos da pauta da reuniao."""
    reuniao = get_object_or_404(ReuniaoConselho, id=reuniao_id)
    processos_na_pauta = reuniao.processos_em_pauta.all().order_by("data_pagamento")
    context = {
        "reuniao": reuniao,
        "processos": processos_na_pauta,
        "pendencia_form": PendenciaForm(),
        "pode_interagir": True,
    }
    return render(request, "pagamentos/analise_reuniao.html", context)


__all__ = ["gerenciar_reunioes_view", "montar_pauta_reuniao_view", "analise_reuniao_view"]
