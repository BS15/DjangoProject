from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from verbas_indenizatorias.services.processo_integration import criar_processo_e_vincular_verbas
from ..shared.registry import (
    _CREDOR_AGRUPAMENTO_MULTIPLO,
    _VERBA_CONFIG,
    _obter_credor_agrupamento,
)
@require_POST
@permission_required("fluxo.pode_agrupar_verbas", raise_exception=True)
def agrupar_verbas_view(request, tipo_verba):
    selecionados = request.POST.getlist('verbas_selecionadas')

    config = _VERBA_CONFIG.get(tipo_verba)
    if not config:
        return redirect('verbas_panel')

    modelo_verba = config['model']
    url_retorno = config['list_url']

    if not selecionados:
        messages.warning(request, 'Nenhum item selecionado para agrupar.')
        return redirect(url_retorno)

    itens = list(modelo_verba.objects.select_related('beneficiario').filter(id__in=selecionados, processo__isnull=True))

    if not itens:
        messages.warning(request, 'Os itens selecionados ja possuem processo ou sao invalidos.')
        return redirect(url_retorno)

    credor_obj = _obter_credor_agrupamento(itens)
    if not credor_obj:
        messages.error(request, 'Nao foi possivel determinar o credor para o agrupamento.')
        return redirect(url_retorno)

    if len({item.beneficiario_id for item in itens if item.beneficiario_id}) > 1:
        messages.info(
            request,
            f'Beneficiarios distintos detectados. O credor do processo foi definido como {_CREDOR_AGRUPAMENTO_MULTIPLO}.',
        )

    novo_processo, falhas_pcd = criar_processo_e_vincular_verbas(
        itens,
        tipo_verba,
        credor_obj,
        usuario=request.user,
    )

    for identificador in falhas_pcd:
        messages.warning(
            request,
            f"PCD para diária {identificador} não pôde ser gerado automaticamente.",
        )

    messages.success(request, f"Processo #{novo_processo.id} gerado com sucesso!")
    if not falhas_pcd:
        messages.info(request, 'PCDs gerados! Acesse o Painel de Assinaturas para enviar ao Autentique.')
    return redirect('editar_processo_verbas', pk=novo_processo.id)
