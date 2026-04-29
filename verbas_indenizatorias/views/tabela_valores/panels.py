"""Panels (GET-only) do domínio de tabela de valores unitários."""

from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from pagamentos.views.shared import render_filtered_list
from verbas_indenizatorias.filters import TabelaValoresUnitariosFilter
from verbas_indenizatorias.models import Tabela_Valores_Unitarios_Verbas_Indenizatorias
from .forms import TabelaValoresUnitariosForm


def tabela_valores_unitarios_list_view(request):
    """Renderiza lista de valores unitários por tipo/cargo."""
    if not (
        request.user.has_perm("verbas_indenizatorias.pode_visualizar_tabela_valores_unitarios")
        or request.user.has_perm("verbas_indenizatorias.pode_gerenciar_tabela_valores_unitarios")
    ):
        raise PermissionDenied

    queryset = (
        Tabela_Valores_Unitarios_Verbas_Indenizatorias.objects
        .select_related("tipo", "cargo_funcao")
        .order_by("tipo__tipo_de_verba_indenizatoria", "cargo_funcao__cargo_funcao", "id")
    )
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=TabelaValoresUnitariosFilter,
        template_name="verbas/tabela_valores_unitarios_list.html",
        items_key="tabelas",
        filter_key="filter",
        sort_fields={
            "tipo": "tipo__tipo_de_verba_indenizatoria",
            "cargo_funcao": "cargo_funcao__cargo_funcao",
            "valor_unitario": "valor_unitario",
        },
        default_ordem="tipo",
        default_direcao="asc",
        tie_breaker="id",
    )


@permission_required("verbas_indenizatorias.pode_gerenciar_tabela_valores_unitarios", raise_exception=True)
def add_tabela_valor_unitario_view(request):
    """Renderiza formulário para criação de item da tabela de valores unitários."""
    return render(request, "verbas/add_tabela_valor_unitario.html", {"form": TabelaValoresUnitariosForm()})


@permission_required("verbas_indenizatorias.pode_gerenciar_tabela_valores_unitarios", raise_exception=True)
def edit_tabela_valor_unitario_view(request, pk):
    """Renderiza formulário para edição de item da tabela de valores unitários."""
    item = get_object_or_404(
        Tabela_Valores_Unitarios_Verbas_Indenizatorias.objects.select_related("tipo", "cargo_funcao"),
        id=pk,
    )
    return render(request, "verbas/edit_tabela_valor_unitario.html", {"form": TabelaValoresUnitariosForm(instance=item), "item": item})
