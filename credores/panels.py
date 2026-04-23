"""Panels (GET-only) do domínio de credores."""

from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from credores.filters import CredorFilter
from credores.forms import CredorEditForm, CredorForm
from credores.models import Credor
from pagamentos.domain_models import Processo
from pagamentos.views.shared import render_filtered_list


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def add_credor_view(request):
    """Tela de entrada para cadastro de novo credor."""
    return render(request, "cadastros/add_credor.html", {"form": CredorForm()})


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def credores_list_view(request):
    """Lista filtrável de credores."""
    queryset = Credor.objects.all().order_by("nome")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=CredorFilter,
        template_name="cadastros/credores_list.html",
        items_key="credores",
        filter_key="filter",
    )


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def gerenciar_credor_view(request, pk):
    """Hub de gestão do credor sem mutação por GET."""
    credor = get_object_or_404(Credor, pk=pk)
    historico_processos = (
        Processo.objects.filter(credor=credor)
        .select_related("status")
        .order_by("-id")[:10]
    )
    context = {
        "credor": credor,
        "form_edit": CredorEditForm(instance=credor),
        "historico_processos": historico_processos,
    }
    return render(request, "cadastros/edit_credor.html", context)


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def api_dados_credor(request, credor_id):
    """Retorna em JSON dados de credor para autofill em formulários."""
    try:
        credor = Credor.objects.select_related("conta").get(id=credor_id)

        dados = {
            "sucesso": True,
            "cpf_cnpj": credor.cpf_cnpj,
            "pix": credor.chave_pix,
        }

        if credor.conta:
            dados.update(
                {
                    "conta_id": credor.conta.id,
                    "banco": credor.conta.banco,
                    "agencia": credor.conta.agencia,
                    "conta": credor.conta.conta,
                }
            )

        return JsonResponse(dados)
    except Credor.DoesNotExist:
        return JsonResponse({"sucesso": False, "erro": "Credor não encontrado"})
