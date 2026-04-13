"""Painel GET de documentos fiscais do cadastro."""

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render

from credores.models import Credor
from fiscal.models import CodigosImposto
from fluxo.domain_models import Processo

from .actions import _status_bloqueia_exclusao_nota_fiscal


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
def documentos_fiscais_view(request, pk):
    """Renderiza a tela de gestão de documentos fiscais de um processo."""
    processo = get_object_or_404(Processo, id=pk)
    documentos = processo.documentos.all().order_by("ordem")
    fiscais_contrato = User.objects.filter(groups__name="FISCAL DE CONTRATO").order_by("first_name", "last_name")
    credores = Credor.objects.all().order_by("nome")
    codigos_imposto = CodigosImposto.objects.all().order_by("codigo")
    source = request.GET.get("source", "")
    pode_remover_nota_fiscal = not _status_bloqueia_exclusao_nota_fiscal(processo)

    context = {
        "processo": processo,
        "documentos": documentos,
        "fiscais_contrato": fiscais_contrato,
        "credores": credores,
        "codigos_imposto": codigos_imposto,
        "source": source,
        "pode_remover_nota_fiscal": pode_remover_nota_fiscal,
    }
    return render(request, "fiscal/documentos_fiscais.html", context)


__all__ = ["documentos_fiscais_view"]
