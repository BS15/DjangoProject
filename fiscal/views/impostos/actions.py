"""Action views for tax retention grouping and API operations."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from credores.models import Credor
from fiscal.models import RetencaoImposto
from fiscal.services.impostos import anexar_guia_comprovante_relatorio_em_processos
from fluxo.domain_models import Processo, StatusChoicesProcesso, TiposDePagamento


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def agrupar_retencoes_action(request: HttpRequest) -> HttpResponse:
    """Agrupa retenções selecionadas em um novo processo de recolhimento."""
    selecionados = request.POST.getlist("retencao_ids") or request.POST.getlist("itens_selecionados")

    if not selecionados:
        messages.warning(request, "Nenhum item selecionado para agrupar.")
        return redirect("painel_impostos_view")

    total_impostos = 0

    retencoes = RetencaoImposto.objects.filter(id__in=selecionados)

    for retencao in retencoes:
        if retencao.valor:
            total_impostos += retencao.valor

    if total_impostos <= 0:
        messages.warning(request, "Os itens selecionados não possuem valores válidos.")
        return redirect("painel_impostos_view")

    status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact="A PAGAR - PENDENTE AUTORIZAÇÃO",
        defaults={"status_choice": "A PAGAR - PENDENTE AUTORIZAÇÃO"},
    )

    credor_orgao, _ = Credor.objects.get_or_create(
        nome="Órgão Arrecadador (A Definir)",
        defaults={"nome": "Órgão Arrecadador (A Definir)"},
    )

    tipo_pagamento_impostos, _ = TiposDePagamento.objects.get_or_create(
        tipo_de_pagamento="IMPOSTOS"
    )

    novo_processo = Processo.objects.create(
        credor=credor_orgao,
        valor_bruto=total_impostos,
        valor_liquido=total_impostos,
        detalhamento="Pagamento Agrupado de Impostos Retidos",
        observacao="Gerado automaticamente.",
        status=status_padrao,
        tipo_pagamento=tipo_pagamento_impostos,
    )

    retencoes.update(processo_pagamento=novo_processo)

    messages.success(request, f"Processo #{novo_processo.id} para recolhimento gerado com sucesso!")
    return redirect("editar_processo", pk=novo_processo.id)


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def agrupar_impostos_action(request: HttpRequest) -> HttpResponse:
    """Alias legado do agrupamento de retenções."""
    return agrupar_retencoes_action(request)


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

    retencoes = list(
        RetencaoImposto.objects.select_related("processo_pagamento", "codigo", "nota_fiscal")
        .filter(id__in=selecionados, competencia__month=mes_referencia, competencia__year=ano_referencia)
        .exclude(processo_pagamento__isnull=True)
    )

    if not retencoes:
        messages.error(
            request,
            "Nenhuma retenção elegível encontrada para a competência informada. Verifique se as retenções já foram agrupadas.",
        )
        return redirect("painel_impostos_view")

    total_processos = anexar_guia_comprovante_relatorio_em_processos(
        retencoes=retencoes,
        guia_bytes=guia_arquivo.read(),
        guia_nome=guia_arquivo.name,
        comprovante_bytes=comprovante_arquivo.read(),
        comprovante_nome=comprovante_arquivo.name,
        mes=mes_referencia,
        ano=ano_referencia,
    )

    if not total_processos:
        messages.error(request, "Não foi possível identificar processos de recolhimento para anexação dos documentos.")
        return redirect("painel_impostos_view")

    messages.success(
        request,
        f"Guia, comprovante e relatório mensal anexados com sucesso em {total_processos} processo(s) de recolhimento.",
    )
    return redirect("painel_impostos_view")


__all__ = ["agrupar_retencoes_action", "agrupar_impostos_action", "anexar_documentos_retencoes_action"]


