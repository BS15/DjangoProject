import csv

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ...filters import DiariaFilter
from ...forms import DiariaForm
from ...models import (
    AssinaturaAutentique,
    Credor,
    Diaria,
    DocumentoDiaria,
    ReembolsoCombustivel,
    StatusChoicesVerbasIndenizatorias,
    Tabela_Valores_Unitarios_Verbas_Indenizatorias,
)
from ...services import (
    enviar_para_assinatura,
    gerar_e_anexar_scd_diaria,
    gerar_resposta_pdf,
    sincronizar_assinatura,
)
from ...utils import confirmar_diarias_lote, preview_diarias_lote
from .verbas_shared import (
    _anexar_documento,
    _get_tipos_documento_ativos,
    _processar_upload_documento,
    _render_lista_verba,
)

@permission_required("processos.pode_visualizar_verbas", raise_exception=True)
def diarias_list_view(request):
    return _render_lista_verba(request, Diaria, DiariaFilter, 'verbas/diarias_list.html')


@permission_required("processos.pode_importar_diarias", raise_exception=True)
def download_template_diarias_csv(request):
    """Baixa modelo CSV para importação em lote de diárias."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="template_diarias.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'NOME_BENEFICIARIO',
            'DATA_SAIDA',
            'DATA_RETORNO',
            'CIDADE_ORIGEM',
            'CIDADE_DESTINO',
            'OBJETIVO',
            'QUANTIDADE_DIARIAS',
        ]
    )
    return response


@permission_required("processos.pode_importar_diarias", raise_exception=True)
def importar_diarias_view(request):
    """Importa diárias em lote com pré-visualização e confirmação."""
    session_key = 'importar_diarias_preview'
    context = {}

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'confirmar':
            preview_items = request.session.pop(session_key, None)
            if not isinstance(preview_items, list) or not preview_items:
                messages.error(request, 'Sessão expirada ou prévia não encontrada. Por favor, importe o arquivo novamente.')
                return redirect('importar_diarias')

            resultados = confirmar_diarias_lote(preview_items, request.user)
            context['resultados'] = resultados

        elif action == 'cancelar':
            request.session.pop(session_key, None)
            return redirect('importar_diarias')

        elif request.FILES.get('csv_file'):
            resultado_preview = preview_diarias_lote(request.FILES['csv_file'])
            request.session[session_key] = resultado_preview['preview']
            context['preview'] = resultado_preview['preview']
            context['erros_preview'] = resultado_preview['erros']

    return render(request, 'verbas/importar_diarias.html', context)


@permission_required("processos.pode_criar_diarias", raise_exception=True)
def add_diaria_view(request):
    if request.method == 'POST':
        form = DiariaForm(request.POST)
        if form.is_valid():
            nova_diaria = form.save(commit=False)
            nova_diaria.autorizada = False
            nova_diaria.save()
            nova_diaria.avancar_status('SOLICITADA')

            try:
                gerar_e_anexar_scd_diaria(nova_diaria, request.user)
                messages.info(
                    request,
                    'PDF gerado! Acesse o Painel de Assinaturas para enviar ao Autentique.',
                )
            except Exception as e:
                messages.warning(request, f"Diária cadastrada, mas falha ao gerar SCD: {str(e)}")

            arquivo = request.FILES.get('documento_anexo')
            tipo_id = request.POST.get('tipo_documento_anexo')
            if arquivo and tipo_id:
                _anexar_documento(DocumentoDiaria, 'diaria', nova_diaria, arquivo, tipo_id)

            meio = nova_diaria.meio_de_transporte
            if meio and 'VEÍCULO PRÓPRIO' in meio.meio_de_transporte.upper():
                status_pendente = StatusChoicesVerbasIndenizatorias.objects.filter(
                    status_choice__iexact='PEDIDO - CÁLCULO DE VALORES PENDENTE'
                ).first()
                ReembolsoCombustivel.objects.create(
                    diaria=nova_diaria,
                    beneficiario=nova_diaria.beneficiario,
                    numero_sequencial=nova_diaria.numero_siscac or '',
                    data_saida=nova_diaria.data_saida,
                    data_retorno=nova_diaria.data_retorno,
                    cidade_origem=nova_diaria.cidade_origem,
                    cidade_destino=nova_diaria.cidade_destino,
                    objetivo=nova_diaria.objetivo,
                    distancia_km=0,
                    preco_combustivel=0,
                    valor_total=0,
                    status=status_pendente,
                )
                messages.info(
                    request,
                    'Reembolso de combustível criado automaticamente com status '
                    '"PEDIDO - CÁLCULO DE VALORES PENDENTE". '
                    'Verifique a distância e o preço médio do combustível para concluir o cálculo.',
                )

            messages.success(request, 'Diária cadastrada com sucesso!')
            return redirect('diarias_list')
        messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = DiariaForm()

    tipos_doc = _get_tipos_documento_ativos()
    return render(request, 'verbas/add_diaria.html', {'form': form, 'tipos_documento': tipos_doc})


@permission_required("processos.pode_gerenciar_diarias", raise_exception=True)
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


@permission_required("processos.pode_autorizar_diarias", raise_exception=True)
def painel_autorizacao_diarias_view(request):
    diarias_pendentes = Diaria.objects.select_related(
        'beneficiario', 'proponente', 'status', 'processo'
    ).filter(status__status_choice='SOLICITADA').order_by('-id')

    return render(request, 'verbas/painel_autorizacao_diarias.html', {'diarias_pendentes': diarias_pendentes})


@require_POST
@permission_required("processos.pode_autorizar_diarias", raise_exception=True)
def alternar_autorizacao_diaria(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)
    diaria.autorizada = not diaria.autorizada
    diaria.save()

    if diaria.autorizada:
        messages.success(request, f'Diária #{diaria.numero_siscac} AUTORIZADA com sucesso!')
    else:
        messages.warning(request, f'Autorização da Diária #{diaria.numero_siscac} foi revogada.')

    return redirect('painel_autorizacao_diarias')


@require_POST
@permission_required("processos.pode_autorizar_diarias", raise_exception=True)
def aprovar_diaria_view(request, diaria_id):
    diaria = get_object_or_404(Diaria, id=diaria_id)

    diaria.avancar_status('APROVADA')
    diaria.autorizada = True
    diaria.save(update_fields=['autorizada'])

    messages.success(request, 'Diária aprovada com sucesso.')
    return redirect('painel_autorizacao_diarias')


def sincronizar_assinatura_view(request, assinatura_id):
    assinatura = get_object_or_404(AssinaturaAutentique, id=assinatura_id)

    is_backoffice = request.user.has_perm('processos.pode_gerenciar_diarias')
    entidade = assinatura.entidade_relacionada
    is_owner = (
        (hasattr(entidade, 'proponente') and entidade.proponente == request.user)
        or (
            hasattr(entidade, 'beneficiario')
            and entidade.beneficiario
            and entidade.beneficiario.email == request.user.email
        )
    )
    if not (is_backoffice or is_owner):
        raise PermissionDenied('Você não tem permissão para sincronizar este documento.')

    if assinatura.status == 'ASSINADO':
        messages.info(request, 'Este documento já foi assinado.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    try:
        status_sync = sincronizar_assinatura(assinatura)
        if status_sync == 'signed':
            messages.success(request, 'Documento assinado e sincronizado com sucesso!')
        else:
            messages.info(request, 'O documento ainda está pendente de assinatura no Autentique.')
    except Exception as e:
        messages.error(request, f"Erro ao verificar assinatura: {str(e)}")
    return redirect(request.META.get('HTTP_REFERER', '/'))


def reenviar_assinatura_view(request, diaria_id):
    diaria = get_object_or_404(Diaria, id=diaria_id)

    is_backoffice = request.user.has_perm('processos.pode_gerenciar_diarias')
    is_owner = (
        (diaria.proponente == request.user)
        or (diaria.beneficiario and diaria.beneficiario.email == request.user.email)
    )
    if not (is_backoffice or is_owner):
        raise PermissionDenied('Você não tem permissão para reenviar este documento.')

    try:
        signatarios = [
            {'email': diaria.beneficiario.email, 'action': 'SIGN'},
            {'email': diaria.proponente.email, 'action': 'SIGN'},
        ]
        enviar_para_assinatura(
            entidade=diaria,
            tipo_documento='SCD',
            nome_doc=f"SCD_{diaria.numero_siscac}",
            signatarios=signatarios,
            doc_type='scd',
        )
        messages.success(request, 'SCD reenviado para assinatura com sucesso!')
    except Exception as e:
        messages.error(request, f"Erro ao reenviar SCD para assinatura: {str(e)}")

    return redirect('gerenciar_diaria', pk=diaria.id)


def minhas_solicitacoes_view(request):
    diarias = Diaria.objects.filter(beneficiario__email=request.user.email).order_by('-id')
    return render(request, 'verbas/minhas_solicitacoes.html', {'diarias': diarias})


@permission_required("processos.pode_criar_diarias", raise_exception=True)
def api_valor_unitario_diaria(request, beneficiario_id):
    try:
        credor = Credor.objects.select_related('cargo_funcao').get(id=beneficiario_id)

        if not credor.cargo_funcao_id:
            return JsonResponse({'sucesso': False, 'erro': 'Beneficiário sem cargo/função definido', 'valor_unitario': None})

        valor_unitario = Tabela_Valores_Unitarios_Verbas_Indenizatorias.get_valor_para_cargo_diaria(credor.cargo_funcao)

        if valor_unitario is not None:
            return JsonResponse(
                {
                    'sucesso': True,
                    'valor_unitario': str(valor_unitario),
                    'cargo_funcao': str(credor.cargo_funcao),
                }
            )
        return JsonResponse(
            {
                'sucesso': False,
                'erro': 'Nenhum valor unitário cadastrado para este cargo/função',
                'valor_unitario': None,
            }
        )
    except Credor.DoesNotExist:
        return JsonResponse({'sucesso': False, 'erro': 'Beneficiário não encontrado', 'valor_unitario': None})


@permission_required("processos.pode_gerenciar_diarias", raise_exception=True)
def gerar_pcd_view(request, pk):
    diaria = get_object_or_404(Diaria, pk=pk)
    nome_arquivo = f"PCD_{diaria.numero_siscac}.pdf"
    return gerar_resposta_pdf('pcd', diaria, nome_arquivo, inline=True)


