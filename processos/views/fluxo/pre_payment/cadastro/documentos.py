"""Views de documentos fiscais (notas) inseridas na etapa de cadastro do pré-pagamento.

Este módulo concentra endpoints para:
1. Exibir e gerenciar documentos fiscais vinculados a um processo.
2. Marcar/desmarcar um DocumentoDePagamento como DocumentoFiscal.
3. Persistir dados da nota fiscal e suas retenções, com atualização de
    pendência de ateste de liquidação.

As operações de gravação priorizam consistência transacional e refletem
regras de negócio do backoffice público, mantendo integridade entre nota,
retenções e pendências do processo.
"""

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .....models import (
    CodigosImposto,
    Credor,
    DocumentoFiscal,
    DocumentoDePagamento,
    Pendencia,
    Processo,
    RetencaoImposto,
    StatusChoicesPendencias,
    TiposDePendencias,
)


def _status_bloqueia_exclusao_nota_fiscal(processo):
    """Indica se o processo já está em estágio onde exclusão de nota é proibida."""
    if not processo.status:
        return False

    status_atual = (processo.status.status_choice or "").upper()
    prefixos_bloqueados = ("PAGO", "CONTABILIZADO", "APROVADO", "ARQUIVADO")
    return any(status_atual.startswith(prefixo) for prefixo in prefixos_bloqueados)


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def documentos_fiscais_view(request, pk):
    """Renderiza a tela de gestão de documentos fiscais de um processo."""
    processo = get_object_or_404(Processo, id=pk)
    documentos = processo.documentos.all().order_by("ordem")
    fiscais_contrato = User.objects.filter(groups__name="FISCAL DE CONTRATO").order_by("first_name", "last_name")
    credores = Credor.objects.all().order_by("nome")
    codigos_imposto = CodigosImposto.objects.all().order_by("codigo")
    source = request.GET.get("source", "")
    pode_remover_nota_fiscal = not _status_bloqueia_exclusao_nota_fiscal(processo)

    context = {
        "processo": processo,
        "documentos": documentos,
        "fiscais_contrato": fiscais_contrato,
        "credores": credores,
        "codigos_imposto": codigos_imposto,
        "source": source,
        "pode_remover_nota_fiscal": pode_remover_nota_fiscal,
    }
    return render(request, "fiscal/documentos_fiscais.html", context)


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def api_toggle_documento_fiscal(request, processo_pk, documento_pk):
    """Alterna o vínculo fiscal de um documento do processo."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    processo = get_object_or_404(Processo, id=processo_pk)
    doc = get_object_or_404(DocumentoDePagamento, id=documento_pk, processo=processo)

    try:
        nota = doc.nota_referente

        if _status_bloqueia_exclusao_nota_fiscal(processo):
            return JsonResponse(
                {
                    "status": "blocked",
                    "message": (
                        "Não é permitido remover documento fiscal após a etapa de pagamento. "
                        "Use a interface de contingência para ajustes auditáveis."
                    ),
                },
                status=409,
            )

        nota.retencoes.all().delete()
        nota.delete()
        return JsonResponse({"status": "removed", "message": "Documento fiscal removido."})
    except (DocumentoFiscal.DoesNotExist, AttributeError):
        nota = DocumentoFiscal.objects.create(
            processo=processo,
            documento_vinculado=doc,
            numero_nota_fiscal=f"DOC-{doc.ordem}",
            data_emissao=date.today(),
            valor_bruto=0,
            valor_liquido=0,
        )
        return JsonResponse(
            {
                "status": "created",
                "nota_id": nota.id,
                "message": "Documento marcado como fiscal.",
            }
        )


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
@transaction.atomic
def api_salvar_nota_fiscal(request, processo_pk, nota_pk):
    """Salva os dados da nota fiscal, retenções e pendência de ateste."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    processo = get_object_or_404(Processo, id=processo_pk)
    nota = get_object_or_404(DocumentoFiscal, id=nota_pk, processo=processo)

    try:
        body = json.loads(request.body)
    except (ValueError, AttributeError):
        body = request.POST

    emitente_id = body.get("nome_emitente")
    if emitente_id:
        try:
            nota.nome_emitente = Credor.objects.get(id=int(emitente_id))
        except (Credor.DoesNotExist, ValueError, TypeError):
            nota.nome_emitente = None
    else:
        nota.nome_emitente = None

    numero = body.get("numero_nota_fiscal")
    if numero:
        nota.numero_nota_fiscal = numero

    data_str = body.get("data_emissao", "")
    if data_str:
        try:
            nota.data_emissao = datetime.strptime(str(data_str), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return JsonResponse(
                {
                    "status": "error",
                    "error": "Data de emissão inválida. Use o formato AAAA-MM-DD.",
                },
                status=400,
            )

    valor_bruto = body.get("valor_bruto", "")
    if valor_bruto:
        try:
            nota.valor_bruto = Decimal(str(valor_bruto).replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            return JsonResponse(
                {
                    "status": "error",
                    "error": "Valor bruto inválido. Informe um valor numérico válido.",
                },
                status=400,
            )

    fiscal_id = body.get("fiscal_contrato")
    if fiscal_id:
        try:
            nota.fiscal_contrato = User.objects.get(id=int(fiscal_id))
        except (User.DoesNotExist, ValueError, TypeError):
            nota.fiscal_contrato = None
    else:
        nota.fiscal_contrato = None

    atestada = body.get("atestada")
    nota.atestada = bool(atestada) if isinstance(atestada, bool) else str(atestada).lower() in ("true", "1", "on")

    serie = body.get("serie_nota_fiscal", "")
    nota.serie_nota_fiscal = serie.strip() if serie else None

    codigo_servico = body.get("codigo_servico_inss", "")
    nota.codigo_servico_inss = codigo_servico.strip() if codigo_servico else None

    nota.save()

    nota.retencoes.all().delete()
    codigos = body.get("imposto_codes", [])
    valores = body.get("imposto_values", [])
    rendimentos = body.get("imposto_rendimentos", [])
    beneficiarios = body.get("imposto_beneficiarios", [])
    for codigo_id, rendimento, valor, beneficiario in zip(codigos, rendimentos, valores, beneficiarios):
        if codigo_id and valor:
            try:
                beneficiario_id = int(beneficiario) if beneficiario and str(beneficiario).strip() else None
            except (ValueError, TypeError):
                beneficiario_id = None
            try:
                rendimento_valor = float(str(rendimento).replace(",", ".")) if rendimento and str(rendimento).strip() else None
                imposto_valor = float(str(valor).replace(",", "."))
                RetencaoImposto.objects.create(
                    nota_fiscal=nota,
                    codigo_id=codigo_id,
                    rendimento_tributavel=rendimento_valor,
                    valor=imposto_valor,
                    beneficiario_id=beneficiario_id,
                )
            except (ValueError, TypeError, InvalidOperation):
                return JsonResponse(
                    {
                        "status": "error",
                        "error": f"Erro ao processar o imposto {codigo_id}: Verifique se os valores numéricos são válidos.",
                    },
                    status=400,
                )

    total_retencoes = nota.retencoes.aggregate(total=Sum("valor"))["total"] or 0
    nota.valor_liquido = (nota.valor_bruto or 0) - total_retencoes
    nota.save(update_fields=["valor_liquido"])

    tipo_pendencia, _ = TiposDePendencias.objects.get_or_create(
        tipo_de_pendencia__iexact="ATESTE DE LIQUIDAÇÃO",
        defaults={"tipo_de_pendencia": "ATESTE DE LIQUIDAÇÃO"},
    )

    if not nota.atestada:
        status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
            status_choice__iexact="A RESOLVER",
            defaults={"status_choice": "A RESOLVER"},
        )
        if not processo.pendencias.filter(tipo=tipo_pendencia).exists():
            Pendencia.objects.create(
                processo=processo,
                tipo=tipo_pendencia,
                descricao="DOCUMENTO PENDENTE DE ATESTE DE FISCAL DE CONTRATO",
                status=status_pendencia,
            )
    else:
        outras_nao_atestadas = processo.notas_fiscais.filter(atestada=False).exclude(id=nota.id).exists()
        if not outras_nao_atestadas:
            processo.pendencias.filter(tipo=tipo_pendencia).delete()

    return JsonResponse({"status": "ok", "message": "Nota fiscal salva com sucesso."})


__all__ = ["documentos_fiscais_view", "api_toggle_documento_fiscal", "api_salvar_nota_fiscal"]
