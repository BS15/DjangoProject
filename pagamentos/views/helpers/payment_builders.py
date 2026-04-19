"""Helpers de construção de dados para painéis de pagamento e ações em lote."""

from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect

from fluxo.domain_models import Boleto_Bancario, Processo


def _obter_estatisticas_boletos(processo):
    """Retorna estatísticas de boletos e códigos de barras de um processo."""
    boleto_docs_qs = Boleto_Bancario.objects.select_related("tipo").filter(
        processo=processo,
        tipo__tipo_de_documento__icontains="boleto"
    )
    boleto_barcodes_list = [doc.codigo_barras for doc in boleto_docs_qs if doc.codigo_barras]
    return {
        "boleto_docs_count": boleto_docs_qs.count(),
        "boleto_barcodes_list": boleto_barcodes_list,
        "boleto_barcodes_count": len(boleto_barcodes_list),
    }


def _gerar_agrupamentos_contas_a_pagar(queryset):
    """Gera agregacoes dos filtros laterais da UI de contas a pagar."""
    return {
        "datas_agrupadas": queryset.values("data_pagamento").annotate(total=Count("id")).order_by("data_pagamento"),
        "formas_agrupadas": queryset.values(
            "forma_pagamento__id", "forma_pagamento__forma_de_pagamento"
        ).annotate(total=Count("id")).order_by("forma_pagamento__forma_de_pagamento"),
        "statuses_agrupados": queryset.values("status__status_choice").annotate(total=Count("id")).order_by(
            "status__status_choice"
        ),
        "contas_agrupadas": queryset.values(
            "conta__id",
            "conta__banco",
            "conta__agencia",
            "conta__conta",
            "conta__titular__nome",
        ).annotate(total=Count("id")).order_by("conta__titular__nome", "conta__banco", "conta__agencia"),
    }


def _aplicar_filtros_contas_a_pagar(queryset, params):
    """Aplica os filtros manuais de contas a pagar com base nos parametros GET."""
    qs = queryset

    status = params.get("status")
    data = params.get("data")
    forma = params.get("forma")
    conta = params.get("conta")

    if status:
        qs = qs.filter(status__status_choice=status)

    if data:
        qs = qs.filter(data_pagamento__isnull=True) if data == "sem_data" else qs.filter(data_pagamento=data)

    if forma:
        if forma == "sem_forma":
            qs = qs.filter(forma_pagamento__isnull=True)
        elif forma.isdigit():
            qs = qs.filter(forma_pagamento__id=int(forma))

    if conta:
        if conta == "sem_conta":
            qs = qs.filter(conta__isnull=True)
        elif conta.isdigit():
            qs = qs.filter(conta__id=int(conta))

    return qs


def _build_detalhes_pagamento(processos):
    """Monta os detalhes operacionais de pagamento e consolida totais por forma.

    Classifica cada processo conforme os dados necessários para pagamento
    eletrônico, como código de barras, PIX, transferência ou remessa, e soma
    os valores líquidos por forma de pagamento.
    """
    detalhes = []
    totais = {}
    for p in processos:
        forma = p.forma_pagamento.forma_de_pagamento.lower() if p.forma_pagamento else ""
        forma_nome = p.forma_pagamento.forma_de_pagamento if p.forma_pagamento else "N/A"
        tipo = p.tipo_pagamento.tipo_de_pagamento.upper() if p.tipo_pagamento else ""

        if tipo == "GERENCIADOR/BOLETO BANCÁRIO" or "boleto" in forma or "gerenciador" in forma:
            estatisticas_boletos = _obter_estatisticas_boletos(p)
            dados_pagamento = {
                "tipo": "codigo_barras",
                "codigos_barras": estatisticas_boletos["boleto_barcodes_list"],
            }
        elif "pix" in forma:
            dados_pagamento = {
                "tipo": "pix",
                "chave_pix": (p.credor.chave_pix if p.credor and p.credor.chave_pix else ""),
            }
        elif "transfer" in forma or "ted" in forma:
            credor_conta = p.credor.conta if p.credor else None
            dados_pagamento = {
                "tipo": "transferencia",
                "banco": credor_conta.banco if credor_conta else "",
                "agencia": credor_conta.agencia if credor_conta else "",
                "conta": credor_conta.conta if credor_conta else "",
            }
        else:
            dados_pagamento = {"tipo": "remessa"}

        detalhes.append({"processo": p, "dados_pagamento": dados_pagamento})
        valor = p.valor_liquido or 0
        totais[forma_nome] = totais.get(forma_nome, 0) + valor
    return detalhes, totais


def _consolidar_totais_pagamento(totais_a_pagar, totais_lancados):
    """Consolida totais por forma de pagamento e calcula somatorios gerais."""
    totais = {}
    for origem in (totais_a_pagar, totais_lancados):
        for forma, valor in origem.items():
            totais[forma] = totais.get(forma, 0) + valor

    total_a_pagar = sum(totais_a_pagar.values())
    total_lancados = sum(totais_lancados.values())
    total_geral = total_a_pagar + total_lancados

    return {
        "totais": totais,
        "total_a_pagar": total_a_pagar,
        "total_lancados": total_lancados,
        "total_geral": total_geral,
    }


def _atualizar_status_em_lote(ids, nome_status, usuario, queryset_base=None):
    """Atualiza em lote garantindo o acionamento de signals (Auditoria) e Turnpikes.

    Itera pelos processos elegíveis chamando avancar_status() para cada um,
    assegurando que as regras de negócio são respeitadas e o usuário é registrado
    no histórico de auditoria.
    """
    if not ids:
        return 0

    qs = queryset_base if queryset_base is not None else Processo.objects.filter(id__in=ids)

    count = 0
    with transaction.atomic():
        for processo in qs:
            processo.avancar_status(nome_status, usuario=usuario)
            count += 1

    return count


def _processar_acao_lote(
    request,
    *,
    param_name,
    status_origem_esperado,
    status_destino,
    msg_sucesso,
    msg_vazio,
    redirect_to,
    msg_sem_elegiveis=None,
    msg_ignorados=None,
):
    """Executa ação em lote respeitando o status de origem esperado.

    Só aplica a transição aos processos elegíveis no estágio correto do fluxo
    e comunica, por mensagens, tanto os itens processados quanto os ignorados.
    """
    selecionados = request.POST.getlist(param_name)
    if not selecionados:
        valor_unico = request.POST.get(param_name)
        selecionados = [valor_unico] if valor_unico else []

    selecionados = [pid for pid in selecionados if pid]
    if not selecionados:
        messages.warning(request, msg_vazio)
        return redirect(redirect_to)

    elegiveis = Processo.objects.filter(
        id__in=selecionados,
        status__status_choice__iexact=status_origem_esperado,
    )
    count_elegiveis = elegiveis.count()
    count_ignorados = len(selecionados) - count_elegiveis

    if count_elegiveis > 0:
        _atualizar_status_em_lote(
            selecionados,
            status_destino,
            usuario=request.user,
            queryset_base=elegiveis,
        )
        messages.success(request, msg_sucesso.format(count=count_elegiveis, processo_id=selecionados[0]))
    else:
        messages.error(
            request,
            (msg_sem_elegiveis or "Ação negada: nenhum processo elegível para transição de status.").format(
                status_origem_esperado=status_origem_esperado,
                count=0,
                processo_id=selecionados[0],
            ),
        )

    if count_ignorados > 0:
        messages.warning(
            request,
            (msg_ignorados or "{count} processo(s) ignorado(s) por estarem em outro estágio do fluxo.").format(
                count=count_ignorados,
                status_origem_esperado=status_origem_esperado,
            ),
        )

    return redirect(redirect_to)


__all__ = [
    "_obter_estatisticas_boletos",
    "_gerar_agrupamentos_contas_a_pagar",
    "_aplicar_filtros_contas_a_pagar",
    "_build_detalhes_pagamento",
    "_consolidar_totais_pagamento",
    "_atualizar_status_em_lote",
    "_processar_acao_lote",
]
