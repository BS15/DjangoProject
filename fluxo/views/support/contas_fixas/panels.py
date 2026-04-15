"""Views de leitura para contas fixas."""

import datetime

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from credores.models import ContaFixa, FaturaMensal
from credores.models import gerar_faturas_do_mes

from .forms import ContaFixaForm


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def painel_contas_fixas_view(request):
	"""Exibe painel mensal de contas fixas e faturas geradas automaticamente."""
	hoje = datetime.date.today()
	mes = int(request.GET.get("mes", hoje.month))
	ano = int(request.GET.get("ano", hoje.year))

	gerar_faturas_do_mes(ano, mes)

	data_ref = datetime.date(ano, mes, 1)
	faturas = (
		FaturaMensal.objects.filter(mes_referencia=data_ref)
		.select_related("conta_fixa__credor", "processo_vinculado")
		.order_by("conta_fixa__dia_vencimento")
	)

	context = {
		"faturas": faturas,
		"mes": mes,
		"ano": ano,
		"contas_fixas": ContaFixa.objects.select_related("credor").order_by("credor__nome", "referencia"),
	}
	return render(request, "contas/painel_contas_fixas.html", context)


@require_GET
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def add_conta_fixa_view(request):
	"""Renderiza o formulário de criação de conta fixa."""
	return render(request, "contas/add_conta_fixa.html", {"form": ContaFixaForm()})


@require_GET
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def edit_conta_fixa_view(request, pk):
	"""Renderiza o formulário de edição de conta fixa."""
	conta = get_object_or_404(ContaFixa, pk=pk)
	return render(request, "contas/edit_conta_fixa.html", {"form": ContaFixaForm(instance=conta), "conta": conta})


__all__ = ["painel_contas_fixas_view", "add_conta_fixa_view", "edit_conta_fixa_view"]
