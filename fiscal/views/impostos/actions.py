"""Action views for tax retention grouping and API operations."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from credores.models import Credor
from fiscal.models import RetencaoImposto
from fiscal.services.impostos import (
    anexar_guia_comprovante_relatorio_em_processos,
    criar_documentos_pagamento_impostos,
)
from pagamentos.domain_models import Processo, StatusChoicesProcesso, TiposDePagamento
import logging

logger = logging.getLogger(__name__)
SESSION_RETENCOES_DOCS_KEY = "retencoes_documentos_pagamento"


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def agrupar_retencoes_action(request: HttpRequest) -> HttpResponse:
    """Agrupa retenções selecionadas em um novo processo de recolhimento."""
    selecionados = request.POST.getlist("retencao_ids") or request.POST.getlist("itens_selecionados")

    if not selecionados:
        messages.warning(request, "Nenhum item selecionado para agrupar.")
        return redirect("painel_impostos_view")

    with transaction.atomic():
        retencoes = list(
            RetencaoImposto.objects.select_for_update()
            .filter(id__in=selecionados, processo_pagamento__isnull=True)
        )

        if not retencoes:
            messages.warning(request, "Nenhuma retenção elegível para agrupamento foi encontrada.")
            return redirect("painel_impostos_view")

        total_impostos = sum((retencao.valor or 0) for retencao in retencoes)
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
        logger.info("mutation=agrupar_retencoes novo_processo_id=%s user_id=%s", novo_processo.id, request.user.pk)

        for retencao in retencoes:
            retencao.processo_pagamento = novo_processo
            retencao.save(update_fields=["processo_pagamento"])

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

    with transaction.atomic():
        retencoes = list(
            RetencaoImposto.objects.select_for_update()
            .select_related("processo_pagamento", "codigo", "nota_fiscal")
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
@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def selecionar_retencoes_documentacao_action(request: HttpRequest) -> HttpResponse:
    """Armazena retenções selecionadas em sessão e redireciona para o spoke de documentação."""
    selecionados = request.POST.getlist("retencao_ids")
    if not selecionados:
        messages.warning(request, "Selecione ao menos uma retenção para registrar documentos de pagamento.")
        return redirect("painel_impostos_view")

    retencoes_existentes = list(RetencaoImposto.objects.filter(id__in=selecionados).values_list("id", flat=True))
    if not retencoes_existentes:
        messages.warning(request, "Nenhuma retenção válida foi encontrada para os IDs selecionados.")
        return redirect("painel_impostos_view")

    request.session[SESSION_RETENCOES_DOCS_KEY] = retencoes_existentes
    return redirect("registrar_documentos_pagamento_view")


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def remover_retencao_documentacao_action(request: HttpRequest) -> HttpResponse:
    """Remove uma retenção da lista de documentação em sessão."""
    retencao_id = request.POST.get("retencao_id")
    ids_em_sessao = request.session.get(SESSION_RETENCOES_DOCS_KEY, [])

    if not retencao_id or not ids_em_sessao:
        messages.warning(request, "Nenhuma retenção disponível para remoção.")
        return redirect("registrar_documentos_pagamento_view")

    ids_atualizados = [rid for rid in ids_em_sessao if str(rid) != str(retencao_id)]
    if ids_atualizados:
        request.session[SESSION_RETENCOES_DOCS_KEY] = ids_atualizados
        messages.success(request, "Retenção removida da lista.")
        return redirect("registrar_documentos_pagamento_view")

    request.session.pop(SESSION_RETENCOES_DOCS_KEY, None)
    messages.warning(request, "Todas as retenções foram removidas da lista.")
    return redirect("painel_impostos_view")


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def registrar_documentos_pagamento_action(request: HttpRequest) -> HttpResponse:
    """Cria DocumentoPagamentoImposto para cada retenção selecionada (spoke de documentação)."""
    selecionados = request.POST.getlist("retencao_ids")
    if not selecionados:
        selecionados = [str(retencao_id) for retencao_id in request.session.get(SESSION_RETENCOES_DOCS_KEY, [])]
    relatorio_arquivo = request.FILES.get("relatorio_retencoes")
    guia_arquivo = request.FILES.get("guia_recolhimento")
    comprovante_arquivo = request.FILES.get("comprovante_pagamento")
    competencia_raw = (request.POST.get("competencia") or "").strip()

    if not selecionados:
        messages.warning(request, "Selecione ao menos uma retenção para registrar a documentação.")
        return redirect("registrar_documentos_pagamento_view")

    if not relatorio_arquivo or not guia_arquivo or not comprovante_arquivo:
        messages.error(request, "É obrigatório anexar os três documentos: relatório, guia e comprovante.")
        return redirect("registrar_documentos_pagamento_view")

    try:
        from datetime import date
        parts = competencia_raw.split("-")
        if len(parts) != 2:
            raise ValueError("formato inválido")
        competencia = date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, IndexError):
        messages.error(request, "Informe a competência no formato YYYY-MM.")
        return redirect("registrar_documentos_pagamento_view")

    retencoes = list(
        RetencaoImposto.objects.select_related("codigo")
        .filter(id__in=selecionados)
    )
    if not retencoes:
        messages.warning(request, "Nenhuma retenção encontrada para os IDs informados.")
        return redirect("registrar_documentos_pagamento_view")

    criados = criar_documentos_pagamento_impostos(
        retencoes=retencoes,
        relatorio_bytes=relatorio_arquivo.read(),
        relatorio_nome=relatorio_arquivo.name,
        guia_bytes=guia_arquivo.read(),
        guia_nome=guia_arquivo.name,
        comprovante_bytes=comprovante_arquivo.read(),
        comprovante_nome=comprovante_arquivo.name,
        competencia=competencia,
    )
    logger.info(
        "mutation=registrar_documentos_pagamento criados=%s user_id=%s",
        len(criados), request.user.pk,
    )
    messages.success(
        request,
        f"Documentação registrada para {len(criados)} retenção(ões). "
        f"{len(retencoes) - len(criados)} já possuíam documentação e foram ignoradas.",
    )
    request.session.pop(SESSION_RETENCOES_DOCS_KEY, None)
    return redirect("painel_impostos_view")


__all__ = [
    "agrupar_retencoes_action",
    "anexar_documentos_retencoes_action",
    "selecionar_retencoes_documentacao_action",
    "remover_retencao_documentacao_action",
    "registrar_documentos_pagamento_action",
]
