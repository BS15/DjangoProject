import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from verbas_indenizatorias.forms import DiariaForm
from verbas_indenizatorias.services import gerar_e_anexar_scd_diaria
from verbas_indenizatorias.models import Diaria, DocumentoDiaria, ReembolsoCombustivel, StatusChoicesVerbasIndenizatorias
from ...verbas_shared import (
    _get_tipos_documento_ativos,
    _processar_upload_documento,
    _salvar_verba_com_anexo_opcional,
)


logger = logging.getLogger(__name__)


def _preparar_nova_diaria(diaria):
    """Aplica campos obrigatórios antes da primeira persistência da diária."""
    diaria.autorizada = False


def _criar_reembolso_pendente_se_necessario(request, diaria):
    """Cria reembolso pendente quando a diária usa veículo próprio."""
    meio = diaria.meio_de_transporte
    if not meio or 'VEÍCULO PRÓPRIO' not in meio.meio_de_transporte.upper():
        return

    status_pendente = StatusChoicesVerbasIndenizatorias.objects.filter(
        status_choice__iexact='PEDIDO - CÁLCULO DE VALORES PENDENTE'
    ).first()
    ReembolsoCombustivel.objects.create(
        diaria=diaria,
        beneficiario=diaria.beneficiario,
        numero_sequencial=diaria.numero_siscac or '',
        data_saida=diaria.data_saida,
        data_retorno=diaria.data_retorno,
        cidade_origem=diaria.cidade_origem,
        cidade_destino=diaria.cidade_destino,
        objetivo=diaria.objetivo,
        distancia_km=0,
        preco_combustivel=0,
        valor_total=0,
        status=status_pendente,
    )
    messages.info(
        request,
        'Reembolso de combustivel criado automaticamente com status '
        '"PEDIDO - CÁLCULO DE VALORES PENDENTE". '
        'Verifique a distancia e o preco medio do combustivel para concluir o calculo.',
    )


def _executar_rotinas_pos_cadastro_diaria(request, diaria):
    """Executa rotinas específicas de diária após a persistência inicial."""
    diaria.avancar_status('SOLICITADA')

    try:
        gerar_e_anexar_scd_diaria(diaria, request.user)
        messages.info(request, 'PDF gerado! Acesse o Painel de Assinaturas para enviar ao Autentique.')
    except (OSError, RuntimeError, TypeError, ValueError):
        logger.exception("Falha ao gerar SCD para diária %s", diaria.id)
        messages.warning(
            request,
            'Diária cadastrada, mas o SCD não foi gerado automaticamente. Use o Painel de Assinaturas.',
        )

    _criar_reembolso_pendente_se_necessario(request, diaria)


@permission_required('fluxo.pode_criar_diarias', raise_exception=True)
def add_diaria_view(request):
    if request.method == 'POST':
        form = DiariaForm(request.POST)
        if form.is_valid():
            nova_diaria = _salvar_verba_com_anexo_opcional(
                request,
                form=form,
                modelo_documento=DocumentoDiaria,
                fk_name='diaria',
                pre_save=_preparar_nova_diaria,
                post_save=lambda diaria: _executar_rotinas_pos_cadastro_diaria(request, diaria),
            )
            if nova_diaria:
                messages.success(request, 'Diaria cadastrada com sucesso!')
                return redirect('diarias_list')
        else:
            messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = DiariaForm()

    tipos_doc = _get_tipos_documento_ativos()
    return render(request, 'verbas/add_diaria.html', {'form': form, 'tipos_documento': tipos_doc})


@permission_required('fluxo.pode_gerenciar_diarias', raise_exception=True)
def gerenciar_diaria_view(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)
    documentos = diaria.documentos.select_related('tipo').all()
    tipos_doc = _get_tipos_documento_ativos()

    if request.method == 'POST':
        _processar_upload_documento(request, diaria, DocumentoDiaria, 'diaria')
        return redirect('gerenciar_diaria', pk=diaria.id)

    context = {
        'diaria': diaria,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
        'tem_assinatura_scd': diaria.assinaturas_autentique.filter(tipo_documento='SCD').exists(),
    }
    return render(request, 'verbas/gerenciar_diaria.html', context)
