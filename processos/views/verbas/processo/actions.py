from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from ....models import Diaria, Processo, StatusChoicesProcesso, TiposDePagamento
from ....services import criar_assinatura_rascunho, gerar_documento_bytes
from ..verbas_shared import (
    _CREDOR_AGRUPAMENTO_MULTIPLO,
    _VERBA_CONFIG,
    _obter_credor_agrupamento,
)


@require_POST
@permission_required("processos.pode_agrupar_verbas", raise_exception=True)
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

    total = sum(item.valor_total for item in itens if item.valor_total)
    credor_obj = _obter_credor_agrupamento(itens)
    if not credor_obj:
        messages.error(request, 'Nao foi possivel determinar o credor para o agrupamento.')
        return redirect(url_retorno)

    if len({item.beneficiario_id for item in itens if item.beneficiario_id}) > 1:
        messages.info(
            request,
            f'Beneficiarios distintos detectados. O credor do processo foi definido como {_CREDOR_AGRUPAMENTO_MULTIPLO}.',
        )

    status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact='A PAGAR - PENDENTE AUTORIZAÇÃO',
        defaults={'status_choice': 'A PAGAR - PENDENTE AUTORIZAÇÃO'},
    )

    tipo_pagamento_verbas, _ = TiposDePagamento.objects.get_or_create(
        tipo_de_pagamento__iexact='VERBAS INDENIZATÓRIAS',
        defaults={'tipo_de_pagamento': 'VERBAS INDENIZATÓRIAS'},
    )

    with transaction.atomic():
        novo_processo = Processo.objects.create(
            credor=credor_obj,
            valor_bruto=total,
            valor_liquido=total,
            detalhamento=f"Agrupamento de {tipo_verba.capitalize()}s",
            status=status_padrao,
            tipo_pagamento=tipo_pagamento_verbas,
        )

        for item in itens:
            item.processo = novo_processo
            if isinstance(item, Diaria):
                item.avancar_status('ENVIADA PARA PAGAMENTO')
                try:
                    pdf_bytes = gerar_documento_bytes('pcd', item)
                    criar_assinatura_rascunho(
                        entidade=item,
                        tipo_documento='PCD',
                        criador=request.user,
                        pdf_bytes=pdf_bytes,
                        nome_arquivo=f"PCD_{item.id}.pdf",
                    )
                except Exception as e:
                    messages.warning(request, f"PCD para diaria {item.numero_siscac} nao gerado: {str(e)}")
            item.save()

    messages.success(request, f"Processo #{novo_processo.id} gerado com sucesso!")
    messages.info(request, 'PCDs gerados! Acesse o Painel de Assinaturas para enviar ao Autentique.')
    return redirect('editar_processo_verbas', pk=novo_processo.id)
