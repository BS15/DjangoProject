"""Paineis GET do fluxo de processos de verbas indenizatorias."""

from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from pagamentos.domain_models import Processo
from pagamentos.forms import DocumentoFormSet, PendenciaFormSet, ProcessoForm
from .helpers import _montar_contexto_processo_verbas, _pode_gerenciar_processo_verbas_da_entidade


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def verbas_panel_view(request):
    """Renderiza o painel inicial de operacoes de verbas indenizatorias."""
    return render(request, "verbas/verbas_panel.html")


@require_GET
@permission_required("pagamentos.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas_view(request, pk):
    """Hub de edição para processos de verbas indenizatórias."""
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    context = _montar_contexto_processo_verbas(processo)
    return render(request, "verbas/editar_processo_verbas_hub.html", context)


@require_GET
@permission_required("pagamentos.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas_capa_view(request, pk):
    """Spoke de edição da capa do processo de verbas."""
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    processo_form = ProcessoForm(instance=processo, prefix="processo")
    context = _montar_contexto_processo_verbas(processo, processo_form=processo_form)
    return render(request, "verbas/editar_processo_verbas_capa.html", context)


@require_GET
@permission_required("pagamentos.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas_pendencias_view(request, pk):
    """Spoke de edição das pendências do processo de verbas."""
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    pendencia_formset = PendenciaFormSet(instance=processo, prefix="pendencia")
    context = _montar_contexto_processo_verbas(processo, pendencia_formset=pendencia_formset)
    return render(request, "verbas/editar_processo_verbas_pendencias.html", context)


@require_GET
@permission_required("pagamentos.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas_itens_view(request, pk):
    """Spoke de gestão dos itens individuais vinculados ao processo."""
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    context = _montar_contexto_processo_verbas(processo)
    return render(request, "verbas/editar_processo_verbas_itens.html", context)


@require_GET
@permission_required("pagamentos.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas_documentos_view(request, pk):
    """Spoke de gestão de documentos do processo e cards read-only dos docs de verba."""
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    context = _montar_contexto_processo_verbas(processo)
    context.update({
        "documento_formset": DocumentoFormSet(
            instance=processo,
            prefix="documento",
            form_kwargs={"tipo_queryset": context.get("tipos_documento")},
        ),
    })
    return render(request, "verbas/editar_processo_verbas_documentos.html", context)
