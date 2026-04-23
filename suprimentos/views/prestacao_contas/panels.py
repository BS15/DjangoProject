"""Views de leitura da etapa de prestacao de contas de suprimentos."""

from typing import Any

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from suprimentos.models import PrestacaoContasSuprimento, SuprimentoDeFundos
from suprimentos.services.prestacao import obter_ou_criar_prestacao_suprimento
from ..helpers import _suprimento_encerrado
from suprimentos.forms import DespesaSuprimentoForm, EnviarPrestacaoSuprimentoForm


@require_GET
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def painel_suprimentos_view(request: HttpRequest) -> HttpResponse:
    """Exibe painel resumido com os suprimentos cadastrados."""
    suprimentos = SuprimentoDeFundos.objects.all().order_by("-id")
    return render(request, "suprimentos/suprimentos_list.html", {"suprimentos": suprimentos})


@require_GET
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def gerenciar_suprimento_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Exibe detalhes operacionais read-only de um suprimento e suas despesas."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)
    despesas = suprimento.despesas.all().order_by("data", "id")
    prestacao = obter_ou_criar_prestacao_suprimento(suprimento)

    pode_editar = (
        not _suprimento_encerrado(suprimento)
        and prestacao.status == PrestacaoContasSuprimento.STATUS_ABERTA
    )

    context: dict[str, Any] = {
        "suprimento": suprimento,
        "despesas": despesas,
        "pode_editar": pode_editar,
        "prestacao": prestacao,
        "form_enviar_prestacao": EnviarPrestacaoSuprimentoForm(),
        "STATUS_ABERTA": PrestacaoContasSuprimento.STATUS_ABERTA,
        "STATUS_ENVIADA": PrestacaoContasSuprimento.STATUS_ENVIADA,
        "STATUS_ENCERRADA": PrestacaoContasSuprimento.STATUS_ENCERRADA,
    }
    return render(request, "suprimentos/gerenciar_suprimento.html", context)


@require_GET
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def cancelar_suprimento_spoke_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Exibe spoke dedicada para cancelamento formal do suprimento."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos.objects.select_related("status", "processo__status"), id=pk)
    status_choice = (getattr(getattr(suprimento, "status", None), "status_choice", "") or "").upper()
    return render(request, "suprimentos/cancelar_suprimento_spoke.html", {
        "suprimento": suprimento,
        "entidade_paga": status_choice == "ENCERRADO",
    })


@require_GET
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def adicionar_despesa_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Exibe spoke dedicada para registro de nova despesa de suprimento."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)
    if _suprimento_encerrado(suprimento):
        return render(
            request,
            "suprimentos/add_despesa_suprimento.html",
            {
                "suprimento": suprimento,
                "pode_editar": False,
                "form": DespesaSuprimentoForm(),
            },
        )

    return render(
        request,
        "suprimentos/add_despesa_suprimento.html",
        {
            "suprimento": suprimento,
            "pode_editar": True,
            "form": DespesaSuprimentoForm(),
        },
    )


@require_GET
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def revisar_prestacoes_suprimento_view(request: HttpRequest) -> HttpResponse:
    """Painel do operador listando prestações de suprimento aguardando revisão."""
    prestacoes = (
        PrestacaoContasSuprimento.objects.select_related("suprimento__suprido", "submetido_por")
        .filter(status=PrestacaoContasSuprimento.STATUS_ENVIADA)
        .order_by("submetido_em")
    )
    context: dict[str, Any] = {
        "prestacoes": prestacoes,
        "STATUS_ENVIADA": PrestacaoContasSuprimento.STATUS_ENVIADA,
    }
    return render(request, "suprimentos/revisar_prestacoes_suprimento.html", context)


@require_GET
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def revisar_prestacao_suprimento_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Exibe detalhes de uma prestação de suprimento para revisão do operador."""
    prestacao: Any = get_object_or_404(
        PrestacaoContasSuprimento.objects.select_related(
            "suprimento__suprido",
            "suprimento__processo",
            "submetido_por",
        ),
        pk=pk,
    )
    suprimento = prestacao.suprimento
    despesas = suprimento.despesas.all().order_by("data", "id")

    context: dict[str, Any] = {
        "prestacao": prestacao,
        "suprimento": suprimento,
        "despesas": despesas,
        "pode_aprovar": prestacao.status == PrestacaoContasSuprimento.STATUS_ENVIADA,
        "STATUS_ENVIADA": PrestacaoContasSuprimento.STATUS_ENVIADA,
    }
    return render(request, "suprimentos/revisar_prestacao_suprimento.html", context)


__all__ = [
    "painel_suprimentos_view",
    "gerenciar_suprimento_view",
    "cancelar_suprimento_spoke_view",
    "adicionar_despesa_view",
    "revisar_prestacoes_suprimento_view",
    "revisar_prestacao_suprimento_view",
]
