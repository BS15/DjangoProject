"""Views do fluxo de PAGAMENTO."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import redirect, render

from ..forms import PendenciaForm
from ..models import Pendencia, Processo, RetencaoImposto, StatusChoicesProcesso
from .helpers import _build_detalhes_pagamento, _recusar_processo_view


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def separar_para_lancamento_bancario(request):
    """Armazena seleção de processos para a etapa de lançamento bancário.

    Em POST, lê os IDs enviados pela UI (`processos_selecionados`) e salva a
    lista na sessão para uso na próxima tela. Quando nenhum item é selecionado,
    informa o usuário e retorna ao painel de contas a pagar.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponseRedirect: Redireciona para `lancamento_bancario` em sucesso
        ou `contas_a_pagar` em cenários sem seleção/método não esperado.
    """
    if request.method == "POST":
        selecionados = request.POST.getlist("processos_selecionados")

        if not selecionados:
            messages.warning(request, "Nenhum processo foi selecionado.")
            return redirect("contas_a_pagar")

        request.session["processos_lancamento"] = [int(pid) for pid in selecionados]
        return redirect("lancamento_bancario")

    return redirect("contas_a_pagar")


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def lancamento_bancario(request):
    """Exibe o painel de lançamento bancário com consolidação de totais.

    A view consome IDs previamente armazenados em sessão e separa os processos
    em duas listas operacionais:
    - `A PAGAR - AUTORIZADO`
    - `LANÇADO - AGUARDANDO COMPROVANTE`

    Para cada grupo, monta detalhes de pagamento via helper e agrega totais por
    forma de pagamento, além dos totais gerais para exibição no painel.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponse: Template `fluxo/lancamento_bancario.html` com processos e
        totais consolidados. Redireciona para `contas_a_pagar` se a sessão não
        tiver processos selecionados.
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

    totais = {}
    for forma, val in totais_a_pagar.items():
        totais[forma] = totais.get(forma, 0) + val
    for forma, val in totais_lancados.items():
        totais[forma] = totais.get(forma, 0) + val

    total_a_pagar = sum(totais_a_pagar.values())
    total_lancados = sum(totais_lancados.values())
    total_geral = total_a_pagar + total_lancados

    context = {
        "processos_a_pagar": processos_a_pagar,
        "processos_lancados": processos_lancados,
        "totais": totais,
        "totais_a_pagar": totais_a_pagar,
        "totais_lancados": totais_lancados,
        "total_a_pagar": total_a_pagar,
        "total_lancados": total_lancados,
        "total_geral": total_geral,
    }
    return render(request, "fluxo/lancamento_bancario.html", context)


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def marcar_como_lancado(request):
    """Marca um processo como lançado para aguardar comprovante.

    Em POST, recebe `processo_id`, garante a existência do status de destino
    (`LANÇADO - AGUARDANDO COMPROVANTE`) e atualiza o processo correspondente.
    O resultado da operação é informado por mensagens ao usuário.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponseRedirect: Sempre retorna para `lancamento_bancario`.
    """
    if request.method == "POST":
        processo_id = request.POST.get("processo_id")

        if processo_id:
            status_lancado, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact="LANÇADO - AGUARDANDO COMPROVANTE",
                defaults={"status_choice": "LANÇADO - AGUARDANDO COMPROVANTE"},
            )
            updated = Processo.objects.filter(id=processo_id).update(status=status_lancado)
            if updated:
                messages.success(request, f"Processo #{processo_id} marcado como lançado com sucesso.")
            else:
                messages.warning(request, f"Processo #{processo_id} não encontrado.")
        else:
            messages.warning(request, "ID de processo inválido.")

    return redirect("lancamento_bancario")


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def desmarcar_lancamento(request):
    """Reverte um processo lançado para o status de autorizado.

    Em POST, recebe `processo_id`, garante o status
    `A PAGAR - AUTORIZADO` e desfaz a marcação de lançamento bancário.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponseRedirect: Sempre retorna para `lancamento_bancario`.
    """
    if request.method == "POST":
        processo_id = request.POST.get("processo_id")

        if processo_id:
            status_autorizado, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact="A PAGAR - AUTORIZADO",
                defaults={"status_choice": "A PAGAR - AUTORIZADO"},
            )
            updated = Processo.objects.filter(id=processo_id).update(status=status_autorizado)
            if updated:
                messages.success(request, f"Lançamento do Processo #{processo_id} desmarcado.")
            else:
                messages.warning(request, f"Processo #{processo_id} não encontrado.")
        else:
            messages.warning(request, "ID de processo inválido.")

    return redirect("lancamento_bancario")


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def contas_a_pagar(request):
    """Renderiza painel de contas a pagar com filtros agregados e listagem.

    A view considera processos em estágios de pagamento/autorização/lançamento,
    calcula facetas para filtros (data, forma, status, conta) e aplica ordenação
    controlada por parâmetros GET.

    Além da listagem, anota indicadores para UI:
    - `has_pendencias`: existência de pendências no processo.
    - `has_retencoes`: existência de retenções vinculadas via notas fiscais.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponse: Página `fluxo/contas_a_pagar.html` com filtros e resultados.
    """
    STATUSES_CONTAS_A_PAGAR = [
        "A PAGAR - PENDENTE AUTORIZAÇÃO",
        "A PAGAR - ENVIADO PARA AUTORIZAÇÃO",
        "A PAGAR - AUTORIZADO",
        "LANÇADO - AGUARDANDO COMPROVANTE",
    ]

    processos_pendentes = Processo.objects.filter(status__status_choice__in=STATUSES_CONTAS_A_PAGAR)

    datas_agrupadas = processos_pendentes.values("data_pagamento").annotate(total=Count("id")).order_by("data_pagamento")

    formas_agrupadas = (
        processos_pendentes.values("forma_pagamento__id", "forma_pagamento__forma_de_pagamento")
        .annotate(total=Count("id"))
        .order_by("forma_pagamento__forma_de_pagamento")
    )

    statuses_agrupados = (
        processos_pendentes.values("status__status_choice").annotate(total=Count("id")).order_by("status__status_choice")
    )

    contas_agrupadas = (
        processos_pendentes.values(
            "conta__id",
            "conta__banco",
            "conta__agencia",
            "conta__conta",
            "conta__titular__nome",
        )
        .annotate(total=Count("id"))
        .order_by("conta__titular__nome", "conta__banco", "conta__agencia")
    )

    data_selecionada = request.GET.get("data")
    forma_selecionada = request.GET.get("forma")
    status_selecionado = request.GET.get("status")
    conta_selecionada = request.GET.get("conta")
    ordem = request.GET.get("ordem", "id")
    direcao = request.GET.get("direcao", "asc")

    lista_processos = processos_pendentes

    if status_selecionado:
        lista_processos = lista_processos.filter(status__status_choice=status_selecionado)

    if data_selecionada:
        if data_selecionada == "sem_data":
            lista_processos = lista_processos.filter(data_pagamento__isnull=True)
        else:
            lista_processos = lista_processos.filter(data_pagamento=data_selecionada)

    if forma_selecionada:
        if forma_selecionada == "sem_forma":
            lista_processos = lista_processos.filter(forma_pagamento__isnull=True)
        else:
            try:
                lista_processos = lista_processos.filter(forma_pagamento__id=int(forma_selecionada))
            except (ValueError, TypeError):
                pass

    if conta_selecionada:
        if conta_selecionada == "sem_conta":
            lista_processos = lista_processos.filter(conta__isnull=True)
        else:
            try:
                lista_processos = lista_processos.filter(conta__id=int(conta_selecionada))
            except (ValueError, TypeError):
                pass

    ORDER_FIELDS = {
        "id": "id",
        "data_pagamento": "data_pagamento",
        "credor": "credor__nome",
        "valor_liquido": "valor_liquido",
        "status": "status__status_choice",
        "tipo_pagamento": "tipo_pagamento__tipo_de_pagamento",
    }
    order_field = ORDER_FIELDS.get(ordem, "id")
    if direcao == "desc":
        order_field = f"-{order_field}"

    lista_processos = lista_processos.annotate(
        has_pendencias=Exists(Pendencia.objects.filter(processo=OuterRef("pk"))),
        has_retencoes=Exists(RetencaoImposto.objects.filter(nota_fiscal__processo=OuterRef("pk"))),
    ).order_by(order_field)

    context = {
        "datas_agrupadas": datas_agrupadas,
        "formas_agrupadas": formas_agrupadas,
        "statuses_agrupados": statuses_agrupados,
        "contas_agrupadas": contas_agrupadas,
        "lista_processos": lista_processos,
        "data_selecionada": data_selecionada,
        "forma_selecionada": forma_selecionada,
        "status_selecionado": status_selecionado,
        "conta_selecionada": conta_selecionada,
        "ordem": ordem,
        "direcao": direcao,
        "pode_interagir": request.user.has_perm("processos.pode_operar_contas_pagar"),
    }

    return render(request, "fluxo/contas_a_pagar.html", context)


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def enviar_para_autorizacao(request):
    """Envia processos elegíveis para a etapa de autorização de pagamento.

    Aceita seleção em lote (`processos_selecionados`) e aplica regra de elegibilidade:
    apenas processos em `A PAGAR - PENDENTE AUTORIZAÇÃO` podem avançar para
    `A PAGAR - ENVIADO PARA AUTORIZAÇÃO`.

    A resposta é comunicada por mensagens:
    - quantidade enviada com sucesso;
    - quantidade ignorada por status incompatível;
    - aviso quando nada foi selecionado.

    Args:
        request: Requisição HTTP (esperado POST para operação).

    Returns:
        HttpResponseRedirect: Retorna ao painel `contas_a_pagar`.
    """
    if request.method == "POST":
        if not request.user.has_perm("processos.pode_operar_contas_pagar"):
            raise PermissionDenied
        selecionados = request.POST.getlist("processos_selecionados")

        if selecionados:
            elegiveis = Processo.objects.filter(
                id__in=selecionados,
                status__status_choice__iexact="A PAGAR - PENDENTE AUTORIZAÇÃO",
            )
            count_elegiveis = elegiveis.count()
            count_ignorados = len(selecionados) - count_elegiveis

            if count_elegiveis > 0:
                status_aguardando, _ = StatusChoicesProcesso.objects.get_or_create(
                    status_choice__iexact="A PAGAR - ENVIADO PARA AUTORIZAÇÃO",
                    defaults={"status_choice": "A PAGAR - ENVIADO PARA AUTORIZAÇÃO"},
                )
                elegiveis.update(status=status_aguardando)
                messages.success(request, f"{count_elegiveis} processo(s) enviado(s) para autorização com sucesso.")
            else:
                messages.error(
                    request,
                    'Nenhum dos processos selecionados está com status "A PAGAR - PENDENTE AUTORIZAÇÃO".',
                )

            if count_ignorados > 0:
                messages.warning(
                    request,
                    f"{count_ignorados} processo(s) ignorado(s): apenas processos com status "
                    f'"A PAGAR - PENDENTE AUTORIZAÇÃO" podem ser enviados para autorização.',
                )
        else:
            messages.warning(request, "Nenhum processo foi selecionado.")

    return redirect("contas_a_pagar")


@permission_required("processos.pode_autorizar_pagamento", raise_exception=True)
def painel_autorizacao_view(request):
    """Exibe o painel de autorização com filas pendente e autorizada.

    O contexto inclui:
    - processos enviados para autorização;
    - processos já autorizados;
    - formulário de pendência para ações complementares na interface;
    - flag de permissão de interação.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponse: Página `fluxo/autorizacao.html`.
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


@permission_required("processos.pode_autorizar_pagamento", raise_exception=True)
def autorizar_pagamento(request):
    """Autoriza pagamentos em lote para processos selecionados.

    Em POST, altera o status dos processos escolhidos para
    `A PAGAR - AUTORIZADO`, com feedback via mensagens.

    Observação:
    A operação atualiza diretamente os IDs recebidos; a camada de UI deve
    garantir a seleção da fila correta para evitar autorizações indevidas.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponseRedirect: Retorna ao `painel_autorizacao`.
    """
    if request.method == "POST":
        if not request.user.has_perm("processos.pode_autorizar_pagamento"):
            raise PermissionDenied
        selecionados = request.POST.getlist("processos_selecionados")

        if selecionados:
            status_autorizado, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact="A PAGAR - AUTORIZADO",
                defaults={"status_choice": "A PAGAR - AUTORIZADO"},
            )

            Processo.objects.filter(id__in=selecionados).update(status=status_autorizado)
            messages.success(request, f"{len(selecionados)} pagamento(s) autorizado(s) com sucesso!")
        else:
            messages.warning(request, "Nenhum processo foi selecionado para autorização.")

    return redirect("painel_autorizacao")


@permission_required("processos.pode_autorizar_pagamento", raise_exception=True)
def recusar_autorizacao_view(request, pk):
    """Recusa autorização de um processo e o devolve para correção.

    Wrapper fino sobre helper comum de recusa, mantendo consistência de
    permissões, status de devolução e mensagem de erro no fluxo de autorização.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo recusado.

    Returns:
        HttpResponseRedirect: Redireciona para o painel de autorização.
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
