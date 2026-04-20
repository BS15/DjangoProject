from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET

from pagamentos.domain_models import Processo, STATUS_PROCESSO_PRE_AUTORIZACAO
from pagamentos.views.shared import render_filtered_list
from verbas_indenizatorias.forms import ComprovanteDiariaFormSet, DiariaForm
from verbas_indenizatorias.models import Diaria, PrestacaoContasDiaria
from verbas_indenizatorias.filters import DiariaFilter
from verbas_indenizatorias.services.prestacao import obter_ou_criar_prestacao
from .access import _pode_acessar_prestacao, _pode_gerenciar_vinculo_diaria
from ..shared.registry import _get_tipos_documento_verbas


def _processos_vinculaveis_queryset():
    return (
        Processo.objects.select_related("status", "credor")
        .filter(status__opcao_status__in=[status.value for status in STATUS_PROCESSO_PRE_AUTORIZACAO])
        .order_by("-id")
    )


@require_GET
@permission_required("verbas_indenizatorias.pode_visualizar_verbas", raise_exception=True)
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
    )


@require_GET
@permission_required("verbas_indenizatorias.pode_criar_diarias", raise_exception=True)
def add_diaria_view(request):
    return render(request, 'verbas/add_diaria.html', {'form': DiariaForm()})


@require_GET
@permission_required("verbas_indenizatorias.pode_gerenciar_diarias", raise_exception=True)
def gerenciar_diaria_view(request, pk):
    diaria = get_object_or_404(Diaria.objects.select_related('beneficiario', 'status', 'processo', 'prestacao_contas'), id=pk)
    prestacao = obter_ou_criar_prestacao(diaria)
    comprovantes = prestacao.documentos.select_related('tipo').all()

    processos_vinculaveis = Processo.objects.none()
    if _pode_gerenciar_vinculo_diaria(request.user):
        processos_vinculaveis = _processos_vinculaveis_queryset()

    context = {
        'diaria': diaria,
        'prestacao': prestacao,
        'comprovantes': comprovantes,
        'tipos_documento': _get_tipos_documento_verbas(),
        'pode_gerenciar_vinculo_diaria': _pode_gerenciar_vinculo_diaria(request.user),
        'processos_vinculaveis': processos_vinculaveis,
    }
    return render(request, 'verbas/gerenciar_diaria.html', context)


@require_GET
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
            .order_by('-id')
        )

    context = {
        'credor': credor,
        'diarias': diarias,
        'status_aberta': PrestacaoContasDiaria.STATUS_ABERTA,
        'status_encerrada': PrestacaoContasDiaria.STATUS_ENCERRADA,
    }
    return render(request, 'verbas/minha_prestacao_list.html', context)


@require_GET
def gerenciar_prestacao_view(request, pk):
    diaria = get_object_or_404(Diaria.objects.select_related('beneficiario', 'status', 'processo', 'prestacao_contas'), id=pk)
    if not _pode_acessar_prestacao(request.user, diaria):
        return HttpResponseForbidden("Acesso negado para prestação de contas desta diária.")

    prestacao = obter_ou_criar_prestacao(diaria)
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
        'total_docs_prestacao': prestacao.documentos.count(),
    }
    return render(request, 'verbas/gerenciar_prestacao.html', context)


@require_GET
@permission_required('verbas_indenizatorias.analisar_prestacao_contas', raise_exception=True)
def painel_revisar_prestacoes_view(request):
    prestacoes = PrestacaoContasDiaria.objects.select_related('diaria__beneficiario', 'diaria__status').order_by('-criado_em')

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

    context = {
        'prestacoes': prestacoes,
        'filtro_status': status,
        'filtro_beneficiario': beneficiario,
        'filtro_periodo_de': request.GET.get('periodo_de') or '',
        'filtro_periodo_ate': request.GET.get('periodo_ate') or '',
        'status_aberta': PrestacaoContasDiaria.STATUS_ABERTA,
        'status_encerrada': PrestacaoContasDiaria.STATUS_ENCERRADA,
    }
    return render(request, 'verbas/painel_revisar_prestacoes.html', context)


@require_GET
@permission_required('verbas_indenizatorias.analisar_prestacao_contas', raise_exception=True)
def revisar_prestacao_view(request, pk):
    prestacao = get_object_or_404(
        PrestacaoContasDiaria.objects.select_related('diaria__beneficiario', 'diaria__status', 'diaria__processo').prefetch_related('documentos__tipo'),
        pk=pk,
    )
    comprovantes = prestacao.documentos.select_related('tipo').all()
    diaria = prestacao.diaria

    context = {
        'prestacao': prestacao,
        'comprovantes': comprovantes,
        'diaria': diaria,
        'processo_vinculado': diaria.processo,
        'pode_aceitar': prestacao.status == PrestacaoContasDiaria.STATUS_ABERTA,
    }
    return render(request, 'verbas/revisar_prestacao.html', context)


@permission_required("verbas_indenizatorias.pode_importar_diarias", raise_exception=True)
def download_template_diarias_csv(request):
    """Baixa um CSV-modelo para importação de diárias."""
    conteudo = (
        "NOME_BENEFICIARIO,DATA_SOLICITACAO,DATA_SAIDA,DATA_RETORNO,QUANTIDADE_DIARIAS,CIDADE_ORIGEM,CIDADE_DESTINO,OBJETIVO,TIPO_SOLICITACAO\n"
    )
    response = HttpResponse(conteudo, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="template_diarias.csv"'
    return response


__all__ = [
    'diarias_list_view',
    'add_diaria_view',
    'gerenciar_diaria_view',
    'minha_prestacao_list_view',
    'gerenciar_prestacao_view',
    'painel_revisar_prestacoes_view',
    'revisar_prestacao_view',
    'download_template_diarias_csv',
]
