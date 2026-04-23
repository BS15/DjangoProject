"""Ações POST da etapa de comprovantes de pagamento."""

import logging

logger = logging.getLogger(__name__)

import json
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import permission_required
from pagamentos.domain_models.documentos import ComprovanteDePagamento
from pagamentos.domain_models import DocumentoProcesso, Processo, ProcessoStatus, TiposDeDocumento

__all__ = []


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
@require_POST
def vincular_comprovantes_action(request):
    try:
        dados = json.loads(request.body)
        processo_id = dados.get("processo_id")
        comprovantes = dados.get("comprovantes", [])

        if not processo_id:
            return JsonResponse({"sucesso": False, "erro": "ID do processo não informado."})
        if not comprovantes:
            return JsonResponse({"sucesso": False, "erro": "Nenhum comprovante enviado."})

        processo = get_object_or_404(Processo, id=processo_id)
        if not processo.status or processo.status.opcao_status.upper() != ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE:
            return JsonResponse(
                {
                    "sucesso": False,
                    "erro": f"Processo #{processo_id} não está no status correto. Status atual: {processo.status}",
                }
            )

        tipo_comprovante, _ = TiposDeDocumento.objects.get_or_create(
            tipo_de_documento__iexact="Comprovante de Pagamento",
            defaults={"tipo_de_documento": "Comprovante de Pagamento"},
        )

        temp_paths_to_delete = []
        data_pagamento_processo = None

        with transaction.atomic():
            for idx, comprovante in enumerate(comprovantes):
                temp_path = comprovante.get("temp_path")
                if not temp_path:
                    continue
                valor_pago = comprovante.get("valor_pago")
                credor_nome = comprovante.get("credor_nome") or ""
                data_pagamento = comprovante.get("data_pagamento") or None
                numero_comprovante = comprovante.get("numero_comprovante") or None
                if data_pagamento and not data_pagamento_processo:
                    data_pagamento_processo = data_pagamento
                if default_storage.exists(temp_path):
                    with default_storage.open(temp_path) as temp_file:
                        conteudo_arquivo = temp_file.read()
                    nome_arquivo = f"Comprovante_Proc_{processo.id}_{idx + 1}.pdf"
                    DocumentoProcesso.objects.create(
                        processo=processo,
                        arquivo=ContentFile(conteudo_arquivo, name=nome_arquivo),
                        tipo=tipo_comprovante,
                        ordem=99,
                    )
                    ComprovanteDePagamento.objects.create(
                        processo=processo,
                        credor_nome=credor_nome,
                        valor_pago=valor_pago,
                        data_pagamento=data_pagamento,
                        numero_comprovante=numero_comprovante,
                        arquivo=ContentFile(conteudo_arquivo, name=nome_arquivo),
                    )
                    temp_paths_to_delete.append(temp_path)
            processo.avancar_status(ProcessoStatus.PAGO_EM_CONFERENCIA, usuario=request.user)
            if data_pagamento_processo:
                processo.data_pagamento = data_pagamento_processo
                processo.save(update_fields=["data_pagamento"])
                for nota in processo.notas_fiscais.all():
                    for retencao in nota.retencoes.filter(codigo__regra_competencia="pagamento"):
                        retencao.save(update_fields=["competencia"])
        logger.info("mutation=vincular_comprovantes processo_id=%s user_id=%s", processo_id, request.user.pk)
        for temp_path in temp_paths_to_delete:
            try:
                default_storage.delete(temp_path)
            except (FileNotFoundError, OSError) as exc:
                logger.warning("Falha ao remover arquivo temporário %s: %s", temp_path, exc)
        return JsonResponse(
            {
                "sucesso": True,
                "mensagem": f'Processo #{processo_id} baixado com sucesso! Status alterado para "PAGO - EM CONFERÊNCIA".',
            }
        )
    except json.JSONDecodeError:
        return JsonResponse({"sucesso": False, "erro": "JSON inválido no corpo da requisição."})
    except (OSError, TypeError, ValueError) as exc:
        logger.exception("Erro ao vincular comprovantes no processo %s", request.body)
        return JsonResponse({"sucesso": False, "erro": str(exc)})
