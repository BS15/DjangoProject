"""Views e helpers do fluxo de suprimentos de fundos."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ..forms import SuprimentoForm
from ..models import DespesaSuprimento, StatusChoicesProcesso, StatusChoicesSuprimentoDeFundos, SuprimentoDeFundos
from ..models.fluxo import FormasDePagamento, Processo, TiposDePagamento
from ..utils import parse_brl_decimal


def _suprimento_encerrado(suprimento: Any) -> bool:
    """Indica se o suprimento está em status final de encerramento."""
    return bool(suprimento.status and suprimento.status.status_choice.upper() == "ENCERRADO")


def _criar_suprimento_e_processo_vinculado(form_suprimento: SuprimentoForm) -> Any:
    """Cria o suprimento e o processo vinculado em transacao atomica."""
    with transaction.atomic():
        suprimento: Any = form_suprimento.save(commit=False)
        status_aberto, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(status_choice="ABERTO")
        suprimento.status = status_aberto
        suprimento.save()

        nome_lotacao = suprimento.lotacao or "Unidade Não Especificada"
        detalhamento = (
            f"Referente a suprimento de fundos da {nome_lotacao} "
            f"- mês {suprimento.data_saida.month}/{suprimento.data_saida.year}"
        )

        forma_pgto, _ = FormasDePagamento.objects.get_or_create(
            forma_de_pagamento__iexact="CARTÃO PRÉ-PAGO",
            defaults={"forma_de_pagamento": "CARTÃO PRÉ-PAGO"},
        )
        tipo_pgto, _ = TiposDePagamento.objects.get_or_create(
            tipo_de_pagamento__iexact="SUPRIMENTO DE FUNDOS",
            defaults={"tipo_de_pagamento": "SUPRIMENTO DE FUNDOS"},
        )
        status_inicial, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact="A EMPENHAR",
            defaults={"status_choice": "A EMPENHAR"},
        )

        taxa_saque = suprimento.taxa_saque or Decimal("0")
        processo = Processo.objects.create(
            credor=suprimento.suprido,
            valor_bruto=suprimento.valor_liquido,
            valor_liquido=(suprimento.valor_liquido or Decimal("0")) - taxa_saque,
            forma_pagamento=forma_pgto,
            tipo_pagamento=tipo_pgto,
            status=status_inicial,
            detalhamento=detalhamento,
            extraorcamentario=False,
        )

        suprimento.processo = processo
        suprimento.save(update_fields=["processo"])
        return suprimento


def _salvar_despesa_manual(
    suprimento: Any,
    dados_post: Mapping[str, str],
    arquivo_pdf: UploadedFile | None,
) -> DespesaSuprimento:
    """Valida os dados brutos do POST e persiste uma despesa."""
    data_raw = dados_post.get("data", "").strip()
    detalhamento = dados_post.get("detalhamento", "").strip()
    valor_raw = dados_post.get("valor", "").strip()

    if not (data_raw and detalhamento and valor_raw):
        raise ValidationError("Dados incompletos para registrar despesa.")

    try:
        data_obj = datetime.strptime(data_raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError("Data da despesa inválida.") from exc

    valor = parse_brl_decimal(valor_raw)
    if valor is None:
        raise ValidationError("Valor da despesa inválido.")

    return DespesaSuprimento.objects.create(
        suprimento=suprimento,
        data=data_obj,
        estabelecimento=dados_post.get("estabelecimento"),
        detalhamento=detalhamento,
        nota_fiscal=dados_post.get("nota_fiscal"),
        valor=valor,
        arquivo=arquivo_pdf,
    )


def _encerrar_prestacao_suprimento(suprimento: Any) -> None:
    """Atualiza suprimento e processo para o estado de encerramento."""
    with transaction.atomic():
        processo = suprimento.processo
        if processo:
            status_anterior = processo.status.status_choice if processo.status else ""
            status_conferencia, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact="PAGO - EM CONFERÊNCIA",
                defaults={"status_choice": "PAGO - EM CONFERÊNCIA"},
            )
            processo.status = status_conferencia
            processo.save(update_fields=["status"])
            processo.disparar_documentos_automaticos_por_status(
                status_anterior,
                "PAGO - EM CONFERÊNCIA",
            )

        status_encerrado, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(status_choice="ENCERRADO")
        suprimento.status = status_encerrado
        suprimento.save(update_fields=["status"])


@require_GET
@permission_required("processos.acesso_backoffice", raise_exception=True)
def painel_suprimentos_view(request: HttpRequest) -> HttpResponse:
    """Exibe painel resumido com os suprimentos cadastrados."""
    suprimentos = SuprimentoDeFundos.objects.all().order_by("-id")
    return render(request, "suprimentos/suprimentos_list.html", {"suprimentos": suprimentos})


@require_GET
@permission_required("processos.acesso_backoffice", raise_exception=True)
def gerenciar_suprimento_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Exibe detalhes operacionais de um suprimento e suas despesas."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)
    despesas = suprimento.despesas.all().order_by("data", "id")

    context: dict[str, Any] = {
        "suprimento": suprimento,
        "despesas": despesas,
        "pode_editar": not _suprimento_encerrado(suprimento),
    }
    return render(request, "suprimentos/gerenciar_suprimento.html", context)


@require_POST
@permission_required("processos.acesso_backoffice", raise_exception=True)
def adicionar_despesa_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Registra manualmente uma despesa de suprimento a partir de dados do POST."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)

    if _suprimento_encerrado(suprimento):
        messages.error(request, "Este suprimento já foi encerrado e não pode receber novas despesas.")
        return redirect("gerenciar_suprimento", pk=suprimento.id)

    try:
        _salvar_despesa_manual(suprimento, request.POST, request.FILES.get("arquivo"))
        messages.success(request, "Despesa e documento anexados com sucesso!")
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception:
        messages.error(request, "Erro ao processar a despesa. Verifique os valores.")

    return redirect("gerenciar_suprimento", pk=suprimento.id)


@require_POST
@permission_required("processos.acesso_backoffice", raise_exception=True)
def fechar_suprimento_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Encerra a prestação de contas e avança o processo vinculado para conferência."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)

    if _suprimento_encerrado(suprimento):
        messages.warning(request, f"Suprimento #{suprimento.id} já está encerrado.")
        return redirect("painel_suprimentos")

    _encerrar_prestacao_suprimento(suprimento)
    messages.success(
        request,
        f"Prestação de contas do suprimento #{suprimento.id} encerrada e enviada para Conferência!",
    )
    return redirect("painel_suprimentos")


@permission_required("processos.acesso_backoffice", raise_exception=True)
def add_suprimento_view(request: HttpRequest) -> HttpResponse:
    """Cria um suprimento e o processo financeiro vinculado."""
    form = SuprimentoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            _criar_suprimento_e_processo_vinculado(form)
            messages.success(request, "Suprimento de Fundos cadastrado com sucesso!")
            return redirect("painel_suprimentos")
        except Exception as e:
            messages.error(request, f"Erro interno ao salvar: {e}")
    elif request.method == "POST":
        messages.error(request, "Verifique os erros no formulário.")

    return render(request, "suprimentos/add_suprimento.html", {"form": form})


__all__ = [
    "painel_suprimentos_view",
    "gerenciar_suprimento_view",
    "adicionar_despesa_action",
    "fechar_suprimento_action",
    "add_suprimento_view",
]
