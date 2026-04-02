"""Views de suporte transversal: pendencias, contingencias e devolucoes."""

import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from ..filters import ContingenciaFilter, DevolucaoFilter, PendenciaFilter
from ..forms import DevolucaoForm
from ..models import Contingencia, Devolucao, Pendencia, Processo


def painel_pendencias_view(request):
    queryset_base = Pendencia.objects.select_related(
        "processo", "status", "tipo", "processo__credor", "processo__status"
    ).all().order_by("-id")

    meu_filtro = PendenciaFilter(request.GET, queryset=queryset_base)

    context = {
        "meu_filtro": meu_filtro,
        "pendencias": meu_filtro.qs,
    }
    return render(request, "fluxo/painel_pendencias.html", context)


def painel_contingencias_view(request):
    queryset = Contingencia.objects.select_related("processo", "solicitante").order_by("-data_solicitacao")
    meu_filtro = ContingenciaFilter(request.GET, queryset=queryset)
    return render(
        request,
        "fluxo/painel_contingencias.html",
        {
            "filter": meu_filtro,
            "contingencias": meu_filtro.qs,
        },
    )


def add_contingencia_view(request):
    if request.method == "POST":
        processo_id = request.POST.get("processo_id", "").strip()
        justificativa = request.POST.get("justificativa", "").strip()
        dados_propostos_raw = request.POST.get("dados_propostos", "{}").strip()

        if not processo_id or not justificativa:
            messages.error(request, "Processo e justificativa são obrigatórios.")
            return redirect("add_contingencia")

        try:
            pk = int(processo_id)
        except ValueError:
            messages.error(request, "Processo não encontrado.")
            return redirect("add_contingencia")

        processo = get_object_or_404(Processo, pk=pk)

        try:
            dados_propostos = json.loads(dados_propostos_raw) if dados_propostos_raw else {}
        except (json.JSONDecodeError, ValueError):
            dados_propostos = {}

        contingencia = Contingencia.objects.create(
            processo=processo,
            solicitante=request.user,
            justificativa=justificativa,
            dados_propostos=dados_propostos,
            status="PENDENTE_SUPERVISOR",
        )
        processo.em_contingencia = True
        processo.save(update_fields=["em_contingencia"])

        messages.success(
            request,
            f"Contingência #{contingencia.pk} aberta com sucesso para o Processo #{processo.pk}. "
            "Aguardando aprovação do Supervisor.",
        )
        return redirect("home_page")

    return render(request, "fluxo/add_contingencia.html")


@permission_required("processos.acesso_backoffice", raise_exception=True)
def analisar_contingencia_view(request, pk):
    _CAMPOS_PERMITIDOS_CONTINGENCIA = {
        "n_nota_empenho",
        "data_empenho",
        "valor_bruto",
        "valor_liquido",
        "ano_exercicio",
        "n_pagamento_siscac",
        "data_vencimento",
        "data_pagamento",
        "observacao",
        "detalhamento",
        "credor_id",
        "forma_pagamento_id",
        "tipo_pagamento_id",
        "conta_id",
        "tag_id",
    }

    contingencia = get_object_or_404(Contingencia, pk=pk)
    processo = contingencia.processo

    if request.method == "POST":
        action = request.POST.get("action", "").strip()

        if action == "aprovar":
            if "novo_valor_liquido" in contingencia.dados_propostos:
                raw_value = contingencia.dados_propostos["novo_valor_liquido"]
                if isinstance(raw_value, str):
                    raw_value = raw_value.replace(".", "").replace(",", ".")
                try:
                    novo_valor_liquido = Decimal(str(raw_value))
                except (InvalidOperation, ValueError):
                    messages.error(request, "O valor líquido proposto na contingência é inválido.")
                    return redirect("painel_contingencias")

                soma_comprovantes = sum(
                    comp.valor_pago
                    for comp in processo.comprovantes_pagamento.all()
                    if comp.valor_pago is not None
                )

                if abs(novo_valor_liquido - Decimal(str(soma_comprovantes))) > Decimal("0.01"):
                    messages.error(
                        request,
                        "A contingência não pode ser aprovada. O novo valor líquido proposto não corresponde à "
                        "soma dos comprovantes bancários anexados no sistema. O setor responsável deve anexar "
                        "os comprovantes restantes antes da aprovação.",
                    )
                    return redirect("painel_contingencias")

            campos_alterados = []
            for campo, valor in contingencia.dados_propostos.items():
                if campo in _CAMPOS_PERMITIDOS_CONTINGENCIA and hasattr(processo, campo):
                    setattr(processo, campo, valor)
                    campos_alterados.append(campo)

            processo.em_contingencia = False
            campos_alterados.append("em_contingencia")
            processo.save(update_fields=campos_alterados)

            contingencia.status = "APROVADA"
            contingencia.save(update_fields=["status"])
            messages.success(
                request,
                f"Contingência #{contingencia.pk} aprovada com sucesso. O Processo #{processo.pk} foi atualizado.",
            )

        elif action == "rejeitar":
            contingencia.status = "REJEITADA"
            contingencia.save(update_fields=["status"])

            processo.em_contingencia = False
            processo.save(update_fields=["em_contingencia"])

            messages.warning(request, f"Contingência #{contingencia.pk} rejeitada.")
        else:
            messages.error(request, "Ação inválida.")

    return redirect("painel_contingencias")


def painel_devolucoes_view(request):
    queryset = Devolucao.objects.select_related("processo", "processo__credor").order_by("-data_devolucao")
    meu_filtro = DevolucaoFilter(request.GET, queryset=queryset)
    total_valor = meu_filtro.qs.aggregate(total=Sum("valor_devolvido"))["total"] or Decimal("0")
    return render(
        request,
        "fluxo/devolucoes_list.html",
        {
            "filter": meu_filtro,
            "devolucoes": meu_filtro.qs,
            "total_valor": total_valor,
        },
    )


def registrar_devolucao_view(request, processo_id):
    processo = get_object_or_404(Processo, id=processo_id)

    if request.method == "POST":
        form = DevolucaoForm(request.POST, request.FILES)
        if form.is_valid():
            devolucao = form.save(commit=False)
            devolucao.processo = processo
            devolucao.save()
            messages.success(request, "Devolução registrada com sucesso.")
            return redirect("process_detail", processo.id)
    else:
        form = DevolucaoForm()

    return render(request, "fluxo/add_devolucao.html", {"form": form, "processo": processo})


def process_detail_view(request, pk):
    processo = get_object_or_404(Processo, pk=pk)
    documentos = processo.documentos.all()
    status_permite_devolucao = {
        "PAGO - A CONTABILIZAR",
        "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        "APROVADO - PENDENTE ARQUIVAMENTO",
        "ARQUIVADO",
    }
    pode_registrar_devolucao = processo.status and processo.status.status_choice in status_permite_devolucao
    return render(
        request,
        "fluxo/process_detail.html",
        {
            "processo": processo,
            "documentos": documentos,
            "pode_registrar_devolucao": pode_registrar_devolucao,
        },
    )


__all__ = [
    "painel_pendencias_view",
    "painel_contingencias_view",
    "add_contingencia_view",
    "analisar_contingencia_view",
    "painel_devolucoes_view",
    "registrar_devolucao_view",
    "process_detail_view",
]
