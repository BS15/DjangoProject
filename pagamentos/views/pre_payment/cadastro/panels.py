"""Painéis GET de cadastro e documentos fiscais do pré-pagamento."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from credores.models import Credor
from fiscal.models import CodigosImposto, DocumentoFiscal
from pagamentos.domain_models import Processo, ProcessoStatus

from .forms import DocumentoFormSet, DocumentoOrcamentarioFormSet, PendenciaFormSet, ProcessoCapaEdicaoForm, ProcessoForm
from ..helpers import _validar_regras_edicao_processo

from .actions import _status_bloqueia_gestao_fiscal


def _get_next_url(request, *, allow_referer=False):
    """Resolve a URL de retorno priorizando GET e opcionalmente referer."""
    next_url = request.GET.get("next") or ""
    if not next_url and allow_referer:
        next_url = request.META.get("HTTP_REFERER", "")
    return next_url


def _get_status_inicial(processo):
    """Normaliza o status textual do processo para uso nas guards da UI."""
    return processo.status.opcao_status.upper() if processo.status else ""


def _obter_contexto_edicao(request, pk):
    """Carrega processo, status inicial e resultado das regras de guarda da edição."""
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = _get_status_inicial(processo)
    redirecionamento, somente_documentos = _validar_regras_edicao_processo(request, processo, status_inicial)
    return processo, status_inicial, redirecionamento, somente_documentos


def _montar_contexto_hub(processo, status_inicial, somente_documentos):
    """Monta os indicadores resumidos exibidos no hub de edição."""
    return {
        "processo": processo,
        "status_inicial": status_inicial,
        "somente_documentos": somente_documentos,
        "aguardando_liquidacao": status_inicial == ProcessoStatus.AGUARDANDO_LIQUIDACAO,
        "total_documentos": processo.documentos.count(),
        "total_notas": processo.notas_fiscais.count(),
        "notas_nao_atestadas": processo.notas_fiscais.filter(atestada=False).count(),
        "total_pendencias": processo.pendencias.count(),
        "pendencias_abertas": processo.pendencias.filter(status__opcao_status__iexact="A RESOLVER").count(),
    }


def _montar_peek_tables_hub(request, processo):
    """Monta tabelas paginadas de apoio do hub (somente leitura)."""
    documentos_qs = processo.documentos.select_related("tipo").all().order_by("ordem", "id")
    pendencias_qs = processo.pendencias.select_related("tipo", "status").all().order_by("id")
    liquidacoes_qs = DocumentoFiscal.objects.select_related("nome_emitente").filter(
        processo=processo
    ).order_by("-data_emissao", "-id")
    return {
        "documentos_page": Paginator(documentos_qs, 6).get_page(request.GET.get("docs_page")),
        "pendencias_page": Paginator(pendencias_qs, 6).get_page(request.GET.get("pend_page")),
        "liquidacoes_page": Paginator(liquidacoes_qs, 6).get_page(request.GET.get("liq_page")),
    }


@require_GET
@permission_required("pagamentos.pode_editar_processos_pagamento", raise_exception=True)
def add_process_view(request):
    """Renderiza a tela de criação da capa inicial do processo."""
    processo_form = ProcessoForm(prefix="processo")
    next_url = _get_next_url(request, allow_referer=True)

    return render(
        request,
        "pagamentos/add_process.html",
        {
            "processo_form": processo_form,
            "next_url": next_url,
            "trigger_a_empenhar_checked": False,
        },
    )


@require_GET
@permission_required("pagamentos.pode_editar_processos_pagamento", raise_exception=True)
def editar_processo(request, pk):
    """Hub de edição modular do processo."""
    processo, status_inicial, redirecionamento, somente_documentos = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    context = _montar_contexto_hub(processo, status_inicial, somente_documentos)
    context.update(_montar_peek_tables_hub(request, processo))
    return render(request, "pagamentos/editar_processo_hub.html", context)


@require_GET
@permission_required("pagamentos.pode_editar_processos_pagamento", raise_exception=True)
def editar_processo_capa_view(request, pk):
    """Spoke GET de edição da capa do processo."""
    processo, status_inicial, redirecionamento, somente_documentos = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    if somente_documentos:
        messages.error(
            request,
            "Neste status, apenas documentos podem ser alterados. Use a tela específica de documentos.",
        )
        return redirect("editar_processo_documentos", pk=pk)

    return render(
        request,
        "pagamentos/editar_processo_capa.html",
        {
            "processo": processo,
            "processo_form": ProcessoCapaEdicaoForm(instance=processo, prefix="processo"),
            "status_inicial": status_inicial,
            "next_url": _get_next_url(request),
        },
    )


@require_GET
@permission_required("pagamentos.pode_editar_processos_pagamento", raise_exception=True)
def editar_processo_documentos_view(request, pk):
    """Spoke GET de edição de anexos do processo."""
    from pagamentos.views.helpers import _get_tipos_documento_para_processo

    processo, status_inicial, redirecionamento, _ = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    from pagamentos.domain_models import ProcessoStatus

    precisa_documento_orcamentario = (
        not processo.extraorcamentario
        and status_inicial != ProcessoStatus.A_EMPENHAR
        and not processo.documentos.filter(tipo__tipo_documento__iexact="DOCUMENTOS ORÇAMENTÁRIOS").exists()
    )

    tipos_documento = _get_tipos_documento_para_processo(processo)

    return render(
        request,
        "pagamentos/editar_processo_documentos.html",
        {
            "processo": processo,
            "documento_formset": DocumentoFormSet(
                instance=processo,
                prefix="documento",
                form_kwargs={"tipo_queryset": tipos_documento},
            ),
            "tipos_documento": tipos_documento,
            "entity_label": f"Processo {processo.id}",
            "pode_interagir": True,  # Users can always interact with docs; guards live at action level
            "status_inicial": status_inicial,
            "next_url": _get_next_url(request),
            "precisa_documento_orcamentario": precisa_documento_orcamentario,
        },
    )


@require_GET
@permission_required("pagamentos.pode_editar_processos_pagamento", raise_exception=True)
def editar_processo_pendencias_view(request, pk):
    """Spoke GET de edição de pendências do processo."""
    processo, status_inicial, redirecionamento, somente_documentos = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    if somente_documentos:
        messages.error(request, "Neste status, apenas documentos podem ser alterados.")
        return redirect("editar_processo_documentos", pk=pk)

    return render(
        request,
        "pagamentos/editar_processo_pendencias.html",
        {
            "processo": processo,
            "pendencia_formset": PendenciaFormSet(instance=processo, prefix="pendencia"),
            "status_inicial": status_inicial,
            "next_url": _get_next_url(request),
        },
    )


@permission_required("pagamentos.pode_editar_processos_pagamento", raise_exception=True)
def documentos_fiscais_view(request, pk):
    """Renderiza a tela de gestão de documentos fiscais de um processo."""
    processo = get_object_or_404(Processo, id=pk)
    documentos = processo.documentos.all().order_by("ordem")
    fiscais_contrato = User.objects.filter(groups__name="FISCAL DE CONTRATO").order_by("first_name", "last_name")
    credores = Credor.objects.all().order_by("nome")
    codigos_imposto = CodigosImposto.objects.all().order_by("codigo")
    source = request.GET.get("source", "")
    pode_gerenciar_fiscal = not _status_bloqueia_gestao_fiscal(processo)

    context = {
        "processo": processo,
        "documentos": documentos,
        "fiscais_contrato": fiscais_contrato,
        "credores": credores,
        "codigos_imposto": codigos_imposto,
        "source": source,
        "pode_gerenciar_fiscal": pode_gerenciar_fiscal,
    }
    return render(request, "fiscal/documentos_fiscais.html", context)


__all__ = [
    "add_process_view",
    "editar_processo",
    "editar_processo_capa_view",
    "editar_processo_documentos_view",
    "editar_processo_pendencias_view",
    "documentos_fiscais_view",
]
