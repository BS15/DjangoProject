"""Views do fluxo de POS-PAGAMENTO."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required

from django.db import IntegrityError
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_POST
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse

from ...forms import PendenciaForm
from ...models import (
    Contingencia,
    Processo,
    ReuniaoConselho,
    RetencaoImposto,
)
from ...utils import normalize_choice
from ...pdf_engine import gerar_documento_pdf
from ...filters import ProcessoFilter
from ..shared import apply_filterset
from .support_views import (
    painel_pendencias_view,
    painel_contingencias_view,
    add_contingencia_view,
    analisar_contingencia_view,
    painel_devolucoes_view,
    registrar_devolucao_view,
    process_detail_view,
)
from .helpers import (
    _aplicar_filtro_por_opcao,
    _aprovar_processo_view,
    _executar_arquivamento_definitivo,
    _iniciar_fila_sessao,
    _processo_fila_detalhe_view,
    _recusar_processo_view,
)


@require_GET
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def painel_conferencia_view(request):
    """Exibe o painel de conferência de processos pagos.

    Lista processos em `PAGO - EM CONFERÊNCIA` e anota indicadores de risco:
    existência de pendência e retenções não pagas. Também aceita filtro GET
    (`filtro`) para recortes operacionais no painel.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponse: Renderização de `fluxo/conferencia.html`.
    """
    processos_pagos = (
        Processo.objects.filter(status__status_choice__iexact="PAGO - EM CONFERÊNCIA")
        .annotate(
            tem_pendencia=Exists(
                Contingencia.objects.filter(processo=OuterRef("pk"))
            ),
            tem_retencao=Exists(
                RetencaoImposto.objects.filter(nota_fiscal__processo=OuterRef("pk")).exclude(
                    status__status_choice__iexact="PAGO"
                )
            ),
        )
        .order_by("data_pagamento")
    )

    filtro = normalize_choice(
        request.GET.get("filtro", ""),
        {"com_pendencia", "com_retencao", "com_ambos", "sem_pendencias"},
    )
    processos_pagos = _aplicar_filtro_por_opcao(
        processos_pagos,
        filtro,
        {
            "com_pendencia": {"tem_pendencia": True},
            "com_retencao": {"tem_retencao": True},
            "com_ambos": {"tem_pendencia": True, "tem_retencao": True},
            "sem_pendencias": {"tem_pendencia": False, "tem_retencao": False},
        },
    )

    context = {
        "processos": processos_pagos,
        "pode_interagir": request.user.has_perm("processos.pode_operar_contas_pagar"),
        "filtro_ativo": filtro,
    }
    return render(request, "fluxo/conferencia.html", context)


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def iniciar_conferencia_view(request):
    """Inicializa a fila de trabalho da conferência na sessão do usuário.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponseRedirect: Próximo processo da fila de conferência ou painel.
    """
    return _iniciar_fila_sessao(request, "conferencia_queue", "painel_conferencia", "conferencia_processo")


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def aprovar_conferencia_view(request, pk):
    """Mantém compatibilidade da rota de aprovação direta da conferência.

    A aprovação direta foi desativada e a conferência deve ocorrer pela tela
    de revisão do processo. Esta view apenas notifica e redireciona.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo (não utilizado no fluxo atual).

    Returns:
        HttpResponseRedirect: Redireciona para `painel_conferencia`.
    """
    messages.error(request, "A aprovação direta foi desativada. Abra o processo para realizar a conferência.")
    return redirect("painel_conferencia")


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def conferencia_processo_view(request, pk):
    """Orquestra a revisão de um processo na etapa de conferência.

    Encapsula chamada ao helper de detalhe em fila com as regras da etapa:
    - Aprovação move para `PAGO - A CONTABILIZAR`.
    - Permite salvar alterações intermediárias.
    - Mantém edição habilitada com bloqueio de documentos.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo em análise.

    Returns:
        HttpResponse: Tela de detalhe da conferência ou redirecionamentos de
        fluxo definidos pelo helper.
    """
    return _processo_fila_detalhe_view(
        request,
        pk,
        permission="processos.pode_operar_contas_pagar",
        queue_key="conferencia_queue",
        fallback_view="painel_conferencia",
        current_view="conferencia_processo",
        template_name="fluxo/conferencia_processo.html",
        approve_action="confirmar",
        approve_status="PAGO - A CONTABILIZAR",
        approve_message="Processo #{processo_id} confirmado na conferência e enviado para Contabilização!",
        save_action="salvar",
        save_message="Alterações do Processo #{processo_id} salvas.",
        editable=True,
        lock_documents=True,
    )


@require_GET
@permission_required("processos.pode_contabilizar", raise_exception=True)
def painel_contabilizacao_view(request):
    """Exibe o painel de processos prontos para contabilização.

    Lista processos em `PAGO - A CONTABILIZAR` e disponibiliza formulário de
    pendência para operações auxiliares da interface.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponse: Renderização de `fluxo/contabilizacao.html`.
    """
    processos = Processo.objects.filter(status__status_choice__iexact="PAGO - A CONTABILIZAR").order_by("data_pagamento")
    context = {
        "processos": processos,
        "pendencia_form": PendenciaForm(),
        "pode_interagir": request.user.has_perm("processos.pode_contabilizar"),
    }

    return render(request, "fluxo/contabilizacao.html", context)


@require_POST
@permission_required("processos.pode_contabilizar", raise_exception=True)
def iniciar_contabilizacao_view(request):
    """Inicializa a fila de trabalho da contabilização na sessão.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponseRedirect: Próximo processo da fila de contabilização.
    """
    return _iniciar_fila_sessao(
        request,
        "contabilizacao_queue",
        "painel_contabilizacao",
        "contabilizacao_processo",
    )


@permission_required("processos.pode_contabilizar", raise_exception=True)
def contabilizacao_processo_view(request, pk):
    """Revisa processo na etapa de contabilização com ações de aprovar/recusar.

    Regras do fluxo:
    - Aprovar: envia para `CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL`.
    - Recusar: devolve para `PAGO - EM CONFERÊNCIA`.
    - Salvar: mantém alterações sem transição de status.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo em análise.

    Returns:
        HttpResponse: Tela de detalhe da contabilização ou redirecionamento
        conforme processamento do helper.
    """
    return _processo_fila_detalhe_view(
        request,
        pk,
        permission="processos.pode_contabilizar",
        queue_key="contabilizacao_queue",
        fallback_view="painel_contabilizacao",
        current_view="contabilizacao_processo",
        template_name="fluxo/contabilizacao_processo.html",
        approve_action="aprovar",
        approve_status="CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        approve_message="Processo #{processo_id} contabilizado e enviado ao Conselho Fiscal!",
        save_action="salvar",
        save_message="Alterações do Processo #{processo_id} salvas.",
        reject_action="rejeitar",
        reject_status="PAGO - EM CONFERÊNCIA",
        reject_message="Processo #{processo_id} recusado pela Contabilidade e devolvido para a Conferência!",
        editable=True,
    )


@require_POST
@permission_required("processos.pode_contabilizar", raise_exception=True)
def aprovar_contabilizacao_view(request, pk):
    """Aprova contabilização por rota direta e avança status do processo.

    Wrapper de conveniência para aprovação direta fora da tela de fila.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo a aprovar.

    Returns:
        HttpResponseRedirect: Retorna ao `painel_contabilizacao`.
    """
    return _aprovar_processo_view(
        request,
        pk,
        permission="processos.pode_contabilizar",
        new_status="CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        success_message="Processo #{processo_id} contabilizado e enviado ao Conselho Fiscal!",
        redirect_to="painel_contabilizacao",
    )


@require_POST
@permission_required("processos.pode_contabilizar", raise_exception=True)
def recusar_contabilizacao_view(request, pk):
    """Recusa contabilização e devolve o processo para conferência.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo recusado.

    Returns:
        HttpResponseRedirect: Retorna ao `painel_contabilizacao`.
    """
    return _recusar_processo_view(
        request,
        pk,
        permission="processos.pode_contabilizar",
        status_devolucao="PAGO - EM CONFERÊNCIA",
        error_message="Processo #{processo_id} recusado pela Contabilidade e devolvido para a Conferência!",
        redirect_to="painel_contabilizacao",
    )


@require_GET
@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def painel_conselho_view(request):
    """Exibe o painel do conselho com reuniões ativas e processos pendentes.

    Apresenta:
    - reuniões com status AGENDADA/EM_ANALISE;
    - processos contabilizados ainda sem reunião vinculada.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponse: Renderização de `fluxo/conselho.html`.
    """
    reunioes_ativas = ReuniaoConselho.objects.filter(status__in=["AGENDADA", "EM_ANALISE"]).order_by("-numero")
    processos_sem_reuniao = Processo.objects.filter(
        status__status_choice__iexact="CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        reuniao_conselho__isnull=True,
    ).order_by("data_pagamento")
    context = {
        "reunioes_ativas": reunioes_ativas,
        "processos_sem_reuniao": processos_sem_reuniao,
        "pode_interagir": request.user.has_perm("processos.pode_auditar_conselho"),
    }
    return render(request, "fluxo/conselho.html", context)


@require_POST
@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def iniciar_conselho_view(request):
    """Inicializa a fila de análise do conselho na sessão do usuário.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponseRedirect: Próximo processo da fila do conselho.
    """
    return _iniciar_fila_sessao(request, "conselho_queue", "painel_conselho", "conselho_processo")


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def conselho_processo_view(request, pk):
    """Revisa processo na etapa de conselho fiscal.

    Regras da etapa:
    - Aprovação: `APROVADO - PENDENTE ARQUIVAMENTO`.
    - Recusa: devolução para `PAGO - A CONTABILIZAR`.
    - Edição desabilitada nesta fase.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo em análise.

    Returns:
        HttpResponse: Tela de detalhe do conselho ou redirecionamentos de fila.
    """
    return _processo_fila_detalhe_view(
        request,
        pk,
        permission="processos.pode_auditar_conselho",
        queue_key="conselho_queue",
        fallback_view="painel_conselho",
        current_view="conselho_processo",
        template_name="fluxo/conselho_processo.html",
        approve_action="aprovar",
        approve_status="APROVADO - PENDENTE ARQUIVAMENTO",
        approve_message="Processo #{processo_id} aprovado pelo Conselho e liberado para arquivamento!",
        reject_action="rejeitar",
        reject_status="PAGO - A CONTABILIZAR",
        reject_message="Processo #{processo_id} recusado pelo Conselho Fiscal e devolvido para a Contabilidade!",
        editable=False,
    )


@require_POST
@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def aprovar_conselho_view(request, pk):
    """Aprova processo no conselho via rota direta.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo a aprovar.

    Returns:
        HttpResponseRedirect: Retorna ao `painel_conselho`.
    """
    return _aprovar_processo_view(
        request,
        pk,
        permission="processos.pode_auditar_conselho",
        new_status="APROVADO - PENDENTE ARQUIVAMENTO",
        success_message="Processo #{processo_id} aprovado pelo Conselho e liberado para arquivamento!",
        redirect_to="painel_conselho",
    )


@require_POST
@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def recusar_conselho_view(request, pk):
    """Recusa processo no conselho e devolve para contabilização.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo recusado.

    Returns:
        HttpResponseRedirect: Retorna ao `painel_conselho`.
    """
    return _recusar_processo_view(
        request,
        pk,
        permission="processos.pode_auditar_conselho",
        status_devolucao="PAGO - A CONTABILIZAR",
        error_message="Processo #{processo_id} recusado pelo Conselho Fiscal e devolvido para a Contabilidade!",
        redirect_to="painel_conselho",
    )


@require_GET
@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def gerenciar_reunioes_view(request):
    """Exibe listagem de reuniões cadastradas do conselho fiscal."""
    reunioes = ReuniaoConselho.objects.all()
    context = {
        "reunioes": reunioes,
        "pode_interagir": request.user.has_perm("processos.pode_auditar_conselho"),
    }
    return render(request, "processos/gerenciar_reunioes.html", context)


@require_POST
@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def gerenciar_reunioes_action(request):
    """Cria reunião do conselho a partir do formulário do painel."""
    numero = request.POST.get("numero", "").strip()
    trimestre_referencia = request.POST.get("trimestre_referencia", "").strip()
    data_reuniao = request.POST.get("data_reuniao") or None

    if numero and trimestre_referencia:
        try:
            ReuniaoConselho.objects.create(
                numero=int(numero),
                trimestre_referencia=trimestre_referencia,
                data_reuniao=data_reuniao,
            )
            messages.success(request, f"{numero}ª Reunião criada com sucesso.")
        except ValueError:
            messages.error(request, "Número da reunião inválido.")
        except IntegrityError as e:
            messages.error(request, f"Erro de integridade ao criar reunião: {e}")
    else:
        messages.warning(request, "Preencha o número e o trimestre de referência.")

    return redirect("gerenciar_reunioes")


@require_GET
@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def montar_pauta_reuniao_view(request, reuniao_id):
    """Exibe montagem de pauta de uma reunião específica do conselho."""
    reuniao = get_object_or_404(ReuniaoConselho, id=reuniao_id)

    processos_na_pauta = reuniao.processos_em_pauta.all().order_by("data_pagamento")
    processos_elegiveis = Processo.objects.filter(
        status__status_choice__iexact="CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        reuniao_conselho__isnull=True,
    ).order_by("data_pagamento")

    context = {
        "reuniao": reuniao,
        "processos_na_pauta": processos_na_pauta,
        "processos_elegiveis": processos_elegiveis,
        "pode_interagir": request.user.has_perm("processos.pode_auditar_conselho"),
    }
    return render(request, "processos/montar_pauta_conselho.html", context)


@require_POST
@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def montar_pauta_reuniao_action(request, reuniao_id):
    """Vincula processos selecionados à pauta da reunião do conselho."""
    reuniao = get_object_or_404(ReuniaoConselho, id=reuniao_id)
    processos_ids = request.POST.getlist("processos_selecionados")
    if processos_ids:
        updated = Processo.objects.filter(id__in=processos_ids).update(reuniao_conselho=reuniao)
        messages.success(request, f"{updated} processo(s) adicionado(s) à pauta.")
    else:
        messages.warning(request, "Nenhum processo selecionado.")
    return redirect("montar_pauta_reuniao", reuniao_id=reuniao_id)


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def analise_reuniao_view(request, reuniao_id):
    """Exibe painel de análise dos processos da pauta da reunião.

    Args:
        request: Requisição HTTP atual.
        reuniao_id: ID da reunião em análise.

    Returns:
        HttpResponse: Renderização de `processos/analise_reuniao.html`.
    """
    if not request.user.has_perm("processos.pode_auditar_conselho"):
        raise PermissionDenied
    reuniao = get_object_or_404(ReuniaoConselho, id=reuniao_id)
    processos_na_pauta = reuniao.processos_em_pauta.all().order_by("data_pagamento")
    context = {
        "reuniao": reuniao,
        "processos": processos_na_pauta,
        "pendencia_form": PendenciaForm(),
        "pode_interagir": True,
    }
    return render(request, "processos/analise_reuniao.html", context)


@require_POST
@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def iniciar_conselho_reuniao_view(request, reuniao_id):
    """Inicializa fila de análise do conselho restrita a uma reunião.

    Exige POST e encaminha argumentos extras ao helper de fila para manter o
    contexto da reunião durante a navegação entre processos.

    Args:
        request: Requisição HTTP atual.
        reuniao_id: ID da reunião usada como escopo da fila.

    Returns:
        HttpResponseRedirect: Próxima tela do fluxo de análise.
    """
    get_object_or_404(ReuniaoConselho, id=reuniao_id)
    return _iniciar_fila_sessao(
        request,
        "conselho_queue",
        "analise_reuniao",
        "conselho_processo",
        extra_args={"reuniao_id": reuniao_id},
    )


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
@xframe_options_sameorigin
def gerar_parecer_conselho_view(request, pk):
    """Gera e retorna o PDF de parecer do conselho para um processo.

    O documento é renderizado para exibição inline no navegador com proteção
    de clickjacking apropriada ao uso interno do sistema.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo para geração do parecer.

    Returns:
        HttpResponse: Conteúdo PDF inline.
    """
    processo = get_object_or_404(Processo, pk=pk)
    numero_reuniao = processo.reuniao_conselho.numero if processo.reuniao_conselho else None
    pdf_bytes = gerar_documento_pdf("conselho_fiscal", processo, numero_reuniao=numero_reuniao)
    nome_arquivo = f"Parecer_Conselho_Fiscal_Proc_{processo.id}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{nome_arquivo}"'
    return response


@require_GET
@permission_required("processos.pode_arquivar", raise_exception=True)
def painel_arquivamento_view(request):
    """Exibe painel de arquivamento com pendentes e histórico arquivado.

    Inclui:
    - processos prontos para arquivamento definitivo;
    - lista filtrável de processos já arquivados.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponse: Renderização de `fluxo/arquivamento.html`.
    """
    processos_pendentes = Processo.objects.filter(status__status_choice__iexact="APROVADO - PENDENTE ARQUIVAMENTO").order_by(
        "data_pagamento"
    )

    arquivados_qs = Processo.objects.filter(status__status_choice__iexact="ARQUIVADO").order_by("-id")

    arquivamento_filtro = apply_filterset(request, ProcessoFilter, arquivados_qs)
    processos_arquivados = arquivamento_filtro.qs

    return render(
        request,
        "fluxo/arquivamento.html",
        {
            "processos_pendentes": processos_pendentes,
            "processos_arquivados": processos_arquivados,
            "processos_arquivados_count": processos_arquivados.count(),
            "arquivamento_filtro": arquivamento_filtro,
            "pode_interagir": request.user.has_perm("processos.pode_arquivar"),
        },
    )


@require_POST
@permission_required("processos.pode_arquivar", raise_exception=True)
def arquivar_processo_action(request, pk):
    """Executa o arquivamento definitivo de um processo elegível.

    Etapas:
    1. Garante status `APROVADO - PENDENTE ARQUIVAMENTO`.
    2. Delega geração/salvamento de PDF e transição para helper de serviço.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo a arquivar.

    Returns:
        HttpResponseRedirect: Retorna ao `painel_arquivamento` com mensagens.
    """
    processo = get_object_or_404(Processo, id=pk)

    status_atual = processo.status.status_choice if processo.status else ""
    if status_atual.upper() != "APROVADO - PENDENTE ARQUIVAMENTO":
        messages.error(request, f"Processo #{processo.id} não está no status correto para arquivamento.")
        return redirect("painel_arquivamento")

    sucesso = _executar_arquivamento_definitivo(processo, request.user)
    if not sucesso:
        messages.error(request, f"Processo #{processo.id} não possui documentos para arquivar.")
        return redirect("painel_arquivamento")

    messages.success(request, f"Processo #{processo.id} arquivado definitivamente com sucesso!")
    return redirect("painel_arquivamento")


@require_GET
@permission_required("processos.pode_arquivar", raise_exception=True)
def arquivar_processo_view(request, pk):
    """Exibe a ficha de conferência pré-arquivamento de um processo.

    Não executa nenhuma mutação. A execução efetiva ocorre em
    `arquivar_processo_action`, mantendo separação explícita de
    responsabilidades entre leitura/revisão e ação de arquivamento.
    """
    processo = get_object_or_404(Processo, id=pk)
    status_atual = processo.status.status_choice if processo.status else ""
    elegivel = status_atual.upper() == "APROVADO - PENDENTE ARQUIVAMENTO"

    return render(
        request,
        "fluxo/arquivar_processo.html",
        {
            "processo": processo,
            "elegivel_para_arquivamento": elegivel,
            "pode_interagir": request.user.has_perm("processos.pode_arquivar"),
        },
    )


__all__ = [
    "painel_conferencia_view",
    "iniciar_conferencia_view",
    "aprovar_conferencia_view",
    "conferencia_processo_view",
    "painel_contabilizacao_view",
    "iniciar_contabilizacao_view",
    "contabilizacao_processo_view",
    "aprovar_contabilizacao_view",
    "recusar_contabilizacao_view",
    "painel_conselho_view",
    "iniciar_conselho_view",
    "conselho_processo_view",
    "aprovar_conselho_view",
    "recusar_conselho_view",
    "gerenciar_reunioes_view",
    "gerenciar_reunioes_action",
    "montar_pauta_reuniao_view",
    "montar_pauta_reuniao_action",
    "analise_reuniao_view",
    "iniciar_conselho_reuniao_view",
    "gerar_parecer_conselho_view",
    "painel_arquivamento_view",
    "arquivar_processo_view",
    "arquivar_processo_action",
]
