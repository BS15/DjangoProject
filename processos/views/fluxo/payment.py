"""Views do fluxo de pagamento: lançamento bancário, contas a pagar e autorização."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db.models import Exists, OuterRef
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from ...forms import PendenciaForm
from ...models import Pendencia, Processo, RetencaoImposto, StatusChoicesProcesso
from .helpers import (
    _aplicar_filtros_contas_a_pagar,
    _atualizar_status_em_lote,
    _build_detalhes_pagamento,
    _consolidar_totais_pagamento,
    _gerar_agrupamentos_contas_a_pagar,
    _obter_campo_ordenacao,
    _processar_acao_lote,
    _recusar_processo_view,
)


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def separar_para_lancamento_bancario(request):
    """Armazena na sessão os processos selecionados para o painel de lançamento.

    Endpoint de ação (POST-only). Lê `processos_selecionados`, salva os IDs em
    `request.session["processos_lancamento"]` e redireciona para
    `lancamento_bancario`. Sem seleção, retorna ao painel de contas a pagar com
    mensagem de aviso.
    """
    selecionados = request.POST.getlist("processos_selecionados")

    if not selecionados:
        messages.warning(request, "Nenhum processo foi selecionado.")
        return redirect("contas_a_pagar")

    request.session["processos_lancamento"] = [int(pid) for pid in selecionados]
    return redirect("lancamento_bancario")


@require_GET
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def lancamento_bancario(request):
    """Renderiza o painel de lançamento bancário com totais consolidados.

    Consome os IDs previamente guardados na sessão e divide os processos em duas
    filas operacionais: `A PAGAR - AUTORIZADO` e
    `LANÇADO - AGUARDANDO COMPROVANTE`. Usa `_build_detalhes_pagamento` para
    montar linhas e totais por forma de pagamento, além do total geral exibido
    na tela. Sem IDs em sessão, redireciona para `contas_a_pagar`.
    """
    ids = request.session.get("processos_lancamento", [])

    if not ids:
        messages.warning(request, "Nenhum processo foi selecionado.")
        return redirect("contas_a_pagar")

    status_autorizado = StatusChoicesProcesso.objects.filter(status_choice__iexact="A PAGAR - AUTORIZADO").first()
    status_lancado = StatusChoicesProcesso.objects.filter(status_choice__iexact="LANÇADO - AGUARDANDO COMPROVANTE").first()

    processos_qs = (
        Processo.objects.filter(id__in=ids)
        .select_related("forma_pagamento", "tipo_pagamento", "conta", "credor__conta", "status")
        .prefetch_related("documentos")
        .order_by("forma_pagamento__forma_de_pagamento", "id")
    )

    a_pagar_qs = processos_qs.filter(status=status_autorizado) if status_autorizado else processos_qs.none()
    lancados_qs = processos_qs.filter(status=status_lancado) if status_lancado else processos_qs.none()

    processos_a_pagar, totais_a_pagar = _build_detalhes_pagamento(a_pagar_qs)
    processos_lancados, totais_lancados = _build_detalhes_pagamento(lancados_qs)
    totais_consolidados = _consolidar_totais_pagamento(totais_a_pagar, totais_lancados)

    context = {
        "processos_a_pagar": processos_a_pagar,
        "processos_lancados": processos_lancados,
        "totais_a_pagar": totais_a_pagar,
        "totais_lancados": totais_lancados,
        **totais_consolidados,
    }
    return render(request, "fluxo/lancamento_bancario.html", context)


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def marcar_como_lancado(request):
    """Move um processo para `LANÇADO - AGUARDANDO COMPROVANTE`.

    Endpoint de ação (POST-only) delegado ao wrapper `_processar_acao_lote`.
    """
    return _processar_acao_lote(
        request,
        param_name="processo_id",
        status_origem_esperado="A PAGAR - AUTORIZADO",
        status_destino="LANÇADO - AGUARDANDO COMPROVANTE",
        msg_sucesso="Processo #{processo_id} marcado como lançado com sucesso.",
        msg_vazio="ID de processo inválido.",
        msg_sem_elegiveis=(
            "Ação negada para o Processo #{processo_id}: o status atual não permite marcar como lançado."
        ),
        msg_ignorados="{count} processo(s) ignorado(s) por estarem em outro estágio do fluxo.",
        redirect_to="lancamento_bancario",
    )


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def desmarcar_lancamento(request):
    """Reverte lançamento bancário para `A PAGAR - AUTORIZADO`.

    Endpoint de ação (POST-only) delegado ao wrapper `_processar_acao_lote`.
    """
    return _processar_acao_lote(
        request,
        param_name="processo_id",
        status_origem_esperado="LANÇADO - AGUARDANDO COMPROVANTE",
        status_destino="A PAGAR - AUTORIZADO",
        msg_sucesso="Lançamento do Processo #{processo_id} desmarcado.",
        msg_vazio="ID de processo inválido.",
        msg_sem_elegiveis=(
            "Ação negada para o Processo #{processo_id}: o status atual não permite desmarcar lançamento."
        ),
        msg_ignorados="{count} processo(s) ignorado(s) por estarem em outro estágio do fluxo.",
        redirect_to="lancamento_bancario",
    )


@require_GET
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def contas_a_pagar(request):
    """Renderiza a fila de contas a pagar com facetas, filtros e ordenação.

    Endpoint de leitura (GET-only). Lista processos nos estágios de pagamento,
    calcula agregações para filtros (data, forma, status e conta), aplica filtros
    selecionados na querystring e usa `_obter_campo_ordenacao` para ordenar de
    forma segura. Anota ainda `has_pendencias` e `has_retencoes` para sinalização
    visual na tabela.
    """
    STATUSES_CONTAS_A_PAGAR = [
        "A PAGAR - PENDENTE AUTORIZAÇÃO",
        "A PAGAR - ENVIADO PARA AUTORIZAÇÃO",
        "A PAGAR - AUTORIZADO",
        "LANÇADO - AGUARDANDO COMPROVANTE",
    ]

    processos_base = Processo.objects.filter(status__status_choice__in=STATUSES_CONTAS_A_PAGAR)
    agrupamentos = _gerar_agrupamentos_contas_a_pagar(processos_base)

    data_selecionada = request.GET.get("data")
    forma_selecionada = request.GET.get("forma")
    status_selecionado = request.GET.get("status")
    conta_selecionada = request.GET.get("conta")
    ordem = request.GET.get("ordem", "id")
    direcao = request.GET.get("direcao", "asc")

    order_field = _obter_campo_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "data_pagamento": "data_pagamento",
            "credor": "credor__nome",
            "valor_liquido": "valor_liquido",
            "status": "status__status_choice",
            "tipo_pagamento": "tipo_pagamento__tipo_de_pagamento",
        },
        default_ordem="id",
        default_direcao="asc",
    )

    qs_filtrada = _aplicar_filtros_contas_a_pagar(processos_base, request.GET)

    lista_processos = qs_filtrada.annotate(
        has_pendencias=Exists(Pendencia.objects.filter(processo=OuterRef("pk"))),
        has_retencoes=Exists(RetencaoImposto.objects.filter(nota_fiscal__processo=OuterRef("pk"))),
    ).order_by(order_field)

    context = {
        **agrupamentos,
        "lista_processos": lista_processos,
        "data_selecionada": data_selecionada,
        "forma_selecionada": forma_selecionada,
        "status_selecionado": status_selecionado,
        "conta_selecionada": conta_selecionada,
        "ordem": ordem,
        "direcao": direcao,
        "pode_interagir": True,
    }

    return render(request, "fluxo/contas_a_pagar.html", context)


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def enviar_para_autorizacao(request):
    """Envia em lote processos elegíveis para `A PAGAR - ENVIADO PARA AUTORIZAÇÃO`.

    Endpoint de ação (POST-only). Considera elegíveis apenas processos em
    `A PAGAR - PENDENTE AUTORIZAÇÃO`, atualiza em lote via
    `_atualizar_status_em_lote` e informa por mensagens os totais enviados e
    ignorados por status incompatível.
    """
    return _processar_acao_lote(
        request,
        param_name="processos_selecionados",
        status_origem_esperado="A PAGAR - PENDENTE AUTORIZAÇÃO",
        status_destino="A PAGAR - ENVIADO PARA AUTORIZAÇÃO",
        msg_sucesso="{count} processo(s) enviado(s) para autorização com sucesso.",
        msg_vazio="Nenhum processo foi selecionado.",
        msg_sem_elegiveis='Nenhum dos processos selecionados está com status "{status_origem_esperado}".',
        msg_ignorados=(
            "{count} processo(s) ignorado(s): apenas processos com status "
            '"{status_origem_esperado}" podem ser enviados para autorização.'
        ),
        redirect_to="contas_a_pagar",
    )


@require_GET
@permission_required("processos.pode_autorizar_pagamento", raise_exception=True)
def painel_autorizacao_view(request):
    """Renderiza o painel de autorização com filas pendente e autorizada.

    Expõe no contexto os processos em `A PAGAR - ENVIADO PARA AUTORIZAÇÃO`, os
    já `A PAGAR - AUTORIZADO`, o `PendenciaForm` e a flag de interação baseada
    em permissão do usuário.
    """
    processos = Processo.objects.filter(status__status_choice__iexact="A PAGAR - ENVIADO PARA AUTORIZAÇÃO").order_by(
        "data_pagamento", "id"
    )

    processos_autorizados = Processo.objects.filter(status__status_choice__iexact="A PAGAR - AUTORIZADO").order_by(
        "data_pagamento", "id"
    )

    context = {
        "processos": processos,
        "processos_autorizados": processos_autorizados,
        "pendencia_form": PendenciaForm(),
        "pode_interagir": request.user.has_perm("processos.pode_autorizar_pagamento"),
    }
    return render(request, "fluxo/autorizacao.html", context)


@require_POST
@permission_required("processos.pode_autorizar_pagamento", raise_exception=True)
def autorizar_pagamento(request):
    """Autoriza em lote processos selecionados para `A PAGAR - AUTORIZADO`.

    Endpoint de ação (POST-only) delegado ao wrapper `_processar_acao_lote`.
    """
    return _processar_acao_lote(
        request,
        param_name="processos_selecionados",
        status_origem_esperado="A PAGAR - ENVIADO PARA AUTORIZAÇÃO",
        status_destino="A PAGAR - AUTORIZADO",
        msg_sucesso="{count} pagamento(s) autorizado(s) com sucesso!",
        msg_vazio="Nenhum processo foi selecionado para autorização.",
        msg_sem_elegiveis='Ação negada: nenhum processo selecionado estava no status "{status_origem_esperado}".',
        msg_ignorados="{count} processo(s) ignorado(s) por estarem em outro estágio do fluxo.",
        redirect_to="painel_autorizacao",
    )


@require_POST
@permission_required("processos.pode_autorizar_pagamento", raise_exception=True)
def recusar_autorizacao_view(request, pk):
    """Recusa a autorização de um processo e o devolve ao fluxo de correção.

    Wrapper do helper `_recusar_processo_view` com parâmetros do estágio de
    autorização: permissão, status de devolução e mensagem padronizada.
    """
    return _recusar_processo_view(
        request,
        pk,
        permission="processos.pode_autorizar_pagamento",
        status_devolucao="AGUARDANDO LIQUIDAÇÃO / ATESTE",
        error_message="Processo #{processo_id} não autorizado e devolvido com pendência!",
        redirect_to="painel_autorizacao",
    )


__all__ = [
    "separar_para_lancamento_bancario",
    "lancamento_bancario",
    "marcar_como_lancado",
    "desmarcar_lancamento",
    "contas_a_pagar",
    "enviar_para_autorizacao",
    "painel_autorizacao_view",
    "autorizar_pagamento",
    "recusar_autorizacao_view",
]
