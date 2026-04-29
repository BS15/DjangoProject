"""Actions (POST-only) do domínio de tabela de valores unitários."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from verbas_indenizatorias.models import Tabela_Valores_Unitarios_Verbas_Indenizatorias
from .forms import TabelaValoresUnitariosForm

logger = logging.getLogger(__name__)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_tabela_valores_unitarios", raise_exception=True)
def add_tabela_valor_unitario_action(request):
    """Cria novo item da tabela de valores unitários."""
    form = TabelaValoresUnitariosForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Erro ao salvar. Verifique os campos.")
        return redirect("add_tabela_valor_unitario")

    item = form.save()
    logger.info("mutation=add_tabela_valor_unitario tabela_id=%s user_id=%s", item.id, request.user.pk)
    messages.success(request, "Valor unitário cadastrado com sucesso.")
    return redirect("tabela_valores_unitarios_list")


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_tabela_valores_unitarios", raise_exception=True)
def edit_tabela_valor_unitario_action(request, pk):
    """Atualiza item existente da tabela de valores unitários."""
    item = get_object_or_404(Tabela_Valores_Unitarios_Verbas_Indenizatorias, id=pk)
    form = TabelaValoresUnitariosForm(request.POST, instance=item)

    if not form.is_valid():
        messages.error(request, "Erro ao atualizar. Verifique os campos.")
        return redirect("edit_tabela_valor_unitario", pk=pk)

    form.save()
    logger.info("mutation=edit_tabela_valor_unitario tabela_id=%s user_id=%s", item.id, request.user.pk)
    messages.success(request, "Valor unitário atualizado com sucesso.")
    return redirect("tabela_valores_unitarios_list")
