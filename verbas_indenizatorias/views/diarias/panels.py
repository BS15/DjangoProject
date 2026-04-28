from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET
from openpyxl import Workbook

from pagamentos.domain_models import Processo, STATUS_PROCESSO_PRE_AUTORIZACAO
from pagamentos.views.helpers import _resolver_parametros_ordenacao
from pagamentos.views.shared import render_filtered_list
from verbas_indenizatorias.forms import ComprovanteDiariaFormSet, DiariaComSolicitacaoAssinadaForm, DiariaForm
from verbas_indenizatorias.models import Diaria, PrestacaoContasDiaria
from verbas_indenizatorias.filters import DiariaFilter
from verbas_indenizatorias.services.autorizacao_diarias import listar_diarias_pendentes_para_proponente
from .access import _pode_acessar_prestacao, _pode_gerenciar_vinculo_diaria
from ..shared.registry import _get_tipos_documento_verbas


PRESTACAO_REVIEW_QUEUE_KEY = 'prestacoes_review_queue'


def _obter_prestacao_sem_criar(diaria):
    try:
        return diaria.prestacao_contas
    except PrestacaoContasDiaria.DoesNotExist:
        return None


def _processos_vinculaveis_queryset():
    return (
        Processo.objects.select_related("status", "credor")
        .filter(status__opcao_status__in=[status.value for status in STATUS_PROCESSO_PRE_AUTORIZACAO])
        .order_by("-id")
    )


@require_GET
@permission_required("pagamentos.pode_visualizar_verbas", raise_exception=True)
def diarias_list_view(request):
    queryset = Diaria.objects.select_related("beneficiario", "status", "processo").order_by("-id")
    extra_context = {}
    if _pode_gerenciar_vinculo_diaria(request.user):
        extra_context["processos_vinculaveis"] = _processos_vinculaveis_queryset()

    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=DiariaFilter,
        template_name='verbas/diarias_list.html',
        items_key='diarias',
        filter_key='filter',
        extra_context=extra_context,
        sort_fields={
            'numero_siscac': 'numero_siscac',
            'status': 'status__status_choice',
            'beneficiario': 'beneficiario__nome',
            'data_saida': 'data_saida',
            'valor_total': 'valor_total',
            'processo': 'processo__id',
        },
        default_ordem='numero_siscac',
        default_direcao='desc',
        tie_breaker='-id',
    )


@require_GET
@permission_required("pagamentos.pode_criar_diarias", raise_exception=True)
def add_diaria_view(request):
    return render(
        request,
        'verbas/add_diaria.html',
        {
            'form': DiariaForm(),
            'form_action_url': 'add_diaria_action',
            'modo_solicitacao_assinada': False,
        },
    )


@require_GET
@permission_required("pagamentos.pode_criar_diarias", raise_exception=True)
def add_diaria_assinada_view(request):
    return render(
        request,
        'verbas/add_diaria.html',
        {
            'form': DiariaComSolicitacaoAssinadaForm(),
            'form_action_url': 'add_diaria_assinada_action',
            'modo_solicitacao_assinada': True,
        },
    )


@require_GET
@permission_required("pagamentos.pode_gerenciar_diarias", raise_exception=True)
def gerenciar_diaria_view(request, pk):
    diaria = get_object_or_404(Diaria.objects.select_related('beneficiario', 'status', 'processo', 'prestacao_contas'), id=pk)
    prestacao = _obter_prestacao_sem_criar(diaria)
    comprovantes = prestacao.documentos.select_related('tipo').all() if prestacao else []

    context = {
        'diaria': diaria,
        'prestacao': prestacao,
        'comprovantes': comprovantes,
        'tipos_documento': _get_tipos_documento_verbas(),
        'pode_gerenciar_vinculo_diaria': _pode_gerenciar_vinculo_diaria(request.user),
    }
    return render(request, 'verbas/gerenciar_diaria.html', context)


@require_GET
@permission_required("pagamentos.pode_gerenciar_diarias", raise_exception=True)
def vinculo_diaria_spoke_view(request, pk):
    diaria = get_object_or_404(
        Diaria.objects.select_related('beneficiario', 'status', 'processo', 'prestacao_contas'),
        id=pk,
    )
    if not _pode_gerenciar_vinculo_diaria(request.user):
        return HttpResponseForbidden("Acesso negado para vinculação de diárias.")

    context = {
        'diaria': diaria,
        'processos_vinculaveis': _processos_vinculaveis_queryset(),
    }
    return render(request, 'verbas/vinculo_diaria_spoke.html', context)


@require_GET
@permission_required("pagamentos.pode_gerenciar_diarias", raise_exception=True)
def devolucao_diaria_spoke_view(request, pk):
    diaria = get_object_or_404(Diaria.objects.select_related('beneficiario', 'status'), id=pk)
    context = {'diaria': diaria}
    return render(request, 'verbas/devolucao_diaria_spoke.html', context)


@require_GET
@permission_required("pagamentos.pode_gerenciar_diarias", raise_exception=True)
def apostila_diaria_spoke_view(request, pk):
    diaria = get_object_or_404(Diaria.objects.select_related('beneficiario', 'status'), id=pk)
    context = {'diaria': diaria}
    return render(request, 'verbas/apostila_diaria_spoke.html', context)


@require_GET
@permission_required("pagamentos.pode_gerenciar_diarias", raise_exception=True)
def cancelar_diaria_spoke_view(request, pk):
    diaria = get_object_or_404(Diaria.objects.select_related('beneficiario', 'status'), id=pk)
    status_choice = (getattr(getattr(diaria, "status", None), "status_choice", "") or "").upper()
    context = {'diaria': diaria, 'entidade_paga': status_choice == "PAGA"}
    return render(request, 'verbas/cancelar_diaria_spoke.html', context)


@require_GET
@permission_required("pagamentos.pode_visualizar_verbas", raise_exception=True)
def minha_prestacao_list_view(request):
    from credores.models import Credor

    credor = getattr(request.user, 'credor_vinculado', None)
    if not credor:
        credor = Credor.objects.filter(usuario=request.user).first()

    diarias = Diaria.objects.none()
    if credor:
        diarias = (
            Diaria.objects.filter(beneficiario=credor)
            .select_related('status', 'prestacao_contas')
        )
        ordem, direcao, order_field = _resolver_parametros_ordenacao(
            request,
            campos_permitidos={
                'numero_siscac': 'numero_siscac',
                'periodo': 'data_saida',
                'destino': 'cidade_destino',
                'valor_total': 'valor_total',
                'status_diaria': 'status__status_choice',
                'status_prestacao': 'prestacao_contas__status',
            },
            default_ordem='numero_siscac',
            default_direcao='desc',
        )
        diarias = diarias.order_by(order_field, '-id')
    else:
        ordem, direcao = 'numero_siscac', 'desc'

    context = {
        'credor': credor,
        'diarias': diarias,
        'ordem': ordem,
        'direcao': direcao,
        'status_aberta': PrestacaoContasDiaria.STATUS_ABERTA,
        'status_encerrada': PrestacaoContasDiaria.STATUS_ENCERRADA,
    }
    return render(request, 'verbas/minha_prestacao_list.html', context)


@require_GET
@permission_required("pagamentos.pode_visualizar_verbas", raise_exception=True)
def gerenciar_prestacao_view(request, pk):
    diaria = get_object_or_404(Diaria.objects.select_related('beneficiario', 'status', 'processo', 'prestacao_contas'), id=pk)
    if not _pode_acessar_prestacao(request.user, diaria):
        return HttpResponseForbidden("Acesso negado para prestação de contas desta diária.")

    prestacao = _obter_prestacao_sem_criar(diaria)
    if prestacao is None:
        prestacao = PrestacaoContasDiaria(diaria=diaria, status=PrestacaoContasDiaria.STATUS_ABERTA)
        comprovantes = []
    else:
        comprovantes = prestacao.documentos.select_related('tipo').all()
    pode_editar = prestacao.status == PrestacaoContasDiaria.STATUS_ABERTA
    comprovante_formset = ComprovanteDiariaFormSet(instance=prestacao, prefix='comprovante')

    context = {
        'diaria': diaria,
        'prestacao': prestacao,
        'comprovantes': comprovantes,
        'tipos_documento': _get_tipos_documento_verbas(),
        'pode_editar': pode_editar,
        'comprovante_formset': comprovante_formset,
        'total_docs_prestacao': prestacao.documentos.count() if prestacao.pk else 0,
    }
    return render(request, 'verbas/gerenciar_prestacao.html', context)


@require_GET
@permission_required("pagamentos.pode_gerenciar_diarias", raise_exception=True)
def painel_autorizacao_diarias_view(request):
    diarias_pendentes = listar_diarias_pendentes_para_proponente(request.user)
    ordem = request.GET.get('ordem', 'numero_sequencial')
    if ordem not in {'numero_sequencial', 'beneficiario', 'saida', 'retorno', 'destino', 'quantidade_diarias', 'valor_total'}:
        ordem = 'numero_sequencial'
    direcao = request.GET.get('direcao', 'desc')
    if direcao not in {'asc', 'desc'}:
        direcao = 'desc'

    sort_keys = {
        'numero_sequencial': lambda item: item['diaria'].numero_siscac or item['diaria'].id,
        'beneficiario': lambda item: (item['diaria'].beneficiario.nome or '').lower(),
        'saida': lambda item: item['diaria'].data_saida,
        'retorno': lambda item: item['diaria'].data_retorno,
        'destino': lambda item: (item['diaria'].cidade_destino or '').lower(),
        'quantidade_diarias': lambda item: item['diaria'].quantidade_diarias or 0,
        'valor_total': lambda item: item['diaria'].valor_total or 0,
    }
    diarias_pendentes = sorted(diarias_pendentes, key=sort_keys[ordem], reverse=(direcao == 'desc'))
    return render(request, 'verbas/painel_autorizacao_diarias.html', {
        'diarias_pendentes': diarias_pendentes,
        'ordem': ordem,
        'direcao': direcao,
    })


@require_GET
@permission_required('verbas_indenizatorias.visualizar_prestacao_contas', raise_exception=True)
def painel_revisar_prestacoes_view(request):
    prestacoes = PrestacaoContasDiaria.objects.select_related('diaria__beneficiario', 'diaria__status')

    status = (request.GET.get('status') or '').strip()
    beneficiario = (request.GET.get('beneficiario') or '').strip()
    periodo_de = parse_date((request.GET.get('periodo_de') or '').strip())
    periodo_ate = parse_date((request.GET.get('periodo_ate') or '').strip())

    if status in {PrestacaoContasDiaria.STATUS_ABERTA, PrestacaoContasDiaria.STATUS_ENCERRADA}:
        prestacoes = prestacoes.filter(status=status)
    if beneficiario:
        prestacoes = prestacoes.filter(diaria__beneficiario__nome__icontains=beneficiario)
    if periodo_de:
        prestacoes = prestacoes.filter(diaria__data_saida__gte=periodo_de)
    if periodo_ate:
        prestacoes = prestacoes.filter(diaria__data_retorno__lte=periodo_ate)

    ordem, direcao, order_field = _resolver_parametros_ordenacao(
        request,
        campos_permitidos={
            'prestacao': 'id',
            'diaria': 'diaria__numero_siscac',
            'beneficiario': 'diaria__beneficiario__nome',
            'periodo': 'diaria__data_saida',
            'status': 'status',
        },
        default_ordem='prestacao',
        default_direcao='desc',
    )
    prestacoes = prestacoes.order_by(order_field, '-id')

    context = {
        'prestacoes': prestacoes,
        'ordem': ordem,
        'direcao': direcao,
        'filtro_status': status,
        'filtro_beneficiario': beneficiario,
        'filtro_periodo_de': request.GET.get('periodo_de') or '',
        'filtro_periodo_ate': request.GET.get('periodo_ate') or '',
        'status_aberta': PrestacaoContasDiaria.STATUS_ABERTA,
        'status_encerrada': PrestacaoContasDiaria.STATUS_ENCERRADA,
    }
    return render(request, 'verbas/painel_revisar_prestacoes.html', context)


@require_GET
@permission_required('verbas_indenizatorias.visualizar_prestacao_contas', raise_exception=True)
def revisar_prestacao_view(request, pk):
    prestacao = get_object_or_404(
        PrestacaoContasDiaria.objects.select_related('diaria__beneficiario', 'diaria__status', 'diaria__processo').prefetch_related('documentos__tipo'),
        pk=pk,
    )
    comprovantes = prestacao.documentos.select_related('tipo').all()
    diaria = prestacao.diaria

    fila = [int(pid) for pid in request.session.get(PRESTACAO_REVIEW_QUEUE_KEY, []) if str(pid).isdigit()]
    indice_atual = fila.index(pk) if pk in fila else -1
    proxima_prestacao = fila[indice_atual + 1] if 0 <= indice_atual < len(fila) - 1 else None
    prestacao_anterior = fila[indice_atual - 1] if indice_atual > 0 else None

    context = {
        'prestacao': prestacao,
        'comprovantes': comprovantes,
        'diaria': diaria,
        'processo_vinculado': diaria.processo,
        'pode_aceitar': prestacao.status == PrestacaoContasDiaria.STATUS_ABERTA,
        'in_review_queue': indice_atual >= 0,
        'queue_position': indice_atual + 1 if indice_atual >= 0 else 1,
        'queue_length': len(fila),
        'next_pk': proxima_prestacao,
        'prev_pk': prestacao_anterior,
    }
    return render(request, 'verbas/revisar_prestacao.html', context)


@require_GET
@permission_required("pagamentos.pode_importar_diarias", raise_exception=True)
def download_template_diarias_xlsx(request):
    """Baixa uma planilha XLSX-modelo para importação de diárias."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Diarias"
    sheet.append(
        [
            "NOME_BENEFICIARIO",
            "DATA_SOLICITACAO",
            "DATA_SAIDA",
            "DATA_RETORNO",
            "CIDADE_ORIGEM",
            "CIDADE_DESTINO",
            "OBJETIVO",
            "TIPO_SOLICITACAO",
        ]
    )
    sheet.append(
        [
            "NOME DO BENEFICIARIO",
            "28/04/2026",
            "29/04/2026",
            "30/04/2026",
            "Florianopolis",
            "Blumenau",
            "Participacao em reuniao institucional",
            "INICIAL",
        ]
    )

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="template_diarias.xlsx"'
    workbook.save(response)
    return response


__all__ = [
    'diarias_list_view',
    'add_diaria_view',
    'add_diaria_assinada_view',
    'gerenciar_diaria_view',
    'vinculo_diaria_spoke_view',
    'devolucao_diaria_spoke_view',
    'apostila_diaria_spoke_view',
    'cancelar_diaria_spoke_view',
    'minha_prestacao_list_view',
    'gerenciar_prestacao_view',
    'painel_autorizacao_diarias_view',
    'painel_revisar_prestacoes_view',
    'revisar_prestacao_view',
    'download_template_diarias_xlsx',
]
