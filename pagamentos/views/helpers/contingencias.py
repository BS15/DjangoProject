"""State machine e regras de negocio para contingencias do fluxo financeiro."""

from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from commons.shared.text_tools import parse_brl_decimal
from pagamentos.domain_models import (
    PROCESSO_STATUS_PRE_AUTORIZACAO,
    ProcessoStatus,
)


_CAMPOS_PERMITIDOS_CONTINGENCIA = {
    "valor_bruto",
    "valor_liquido",
    "n_pagamento_siscac",
    "data_vencimento",
    "data_pagamento",
    "observacao",
    "detalhamento",
    "credor_id",
    "forma_pagamento_id",
    "tipo_pagamento_id",
    "conta_id",
    "tag_id",
}

_STATUS_CONTINGENCIA_FINAL = {"APROVADA", "REJEITADA"}
_STATUS_PRE_AUTORIZACAO = set(PROCESSO_STATUS_PRE_AUTORIZACAO)


def determinar_requisitos_contingencia(status_processo):
    """Define quais níveis de aprovação a contingência deve cumprir.

    Regras:
    - Pré-autorização: Supervisor (sem revisão contábil)
    - Pós-autorização e antes de aprovação final do conselho: Supervisor + Ordenador + revisão contábil
    - Após aprovação do conselho fiscal: Supervisor + Ordenador + Conselho + revisão contábil
    """
    status_norm = (status_processo or "").upper().strip()

    if status_norm in {ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO, ProcessoStatus.ARQUIVADO}:
        return True, True, True

    if status_norm in _STATUS_PRE_AUTORIZACAO:
        return False, False, False

    return True, False, True


def proximo_status_contingencia(contingencia):
    """Calcula o próximo estado da contingência após uma aprovação da etapa atual."""
    if contingencia.status == "PENDENTE_SUPERVISOR":
        if contingencia.exige_aprovacao_ordenador:
            return "PENDENTE_ORDENADOR"
        if contingencia.exige_revisao_contadora:
            return "PENDENTE_CONTADOR"
        return "APROVADA"

    if contingencia.status == "PENDENTE_ORDENADOR":
        if contingencia.exige_aprovacao_conselho:
            return "PENDENTE_CONSELHO"
        if contingencia.exige_revisao_contadora:
            return "PENDENTE_CONTADOR"
        return "APROVADA"

    if contingencia.status == "PENDENTE_CONSELHO":
        if contingencia.exige_revisao_contadora:
            return "PENDENTE_CONTADOR"
        return "APROVADA"

    return contingencia.status


def sincronizar_flag_contingencia_processo(processo):
    """Mantém o flag ``em_contingencia`` alinhado com contingências ativas."""
    possui_ativa = processo.contingencias.exclude(status__in=_STATUS_CONTINGENCIA_FINAL).exists()
    if processo.em_contingencia != possui_ativa:
        processo.em_contingencia = possui_ativa
        processo.save(update_fields=["em_contingencia"])


def normalizar_dados_propostos_contingencia(dados_propostos):
    """Normaliza e valida o payload de mudanças da contingência.

    Retorna apenas campos permitidos e converte tipos para evitar erros na
    aplicação final da contingência.
    """
    if not isinstance(dados_propostos, dict):
        return {}

    normalizado = {}
    aliases = {"novo_valor_liquido": "valor_liquido"}
    campos_data = {"data_empenho", "data_vencimento", "data_pagamento"}
    campos_decimal = {"valor_bruto", "valor_liquido"}
    campos_inteiros = {
        "ano_exercicio",
        "credor_id",
        "forma_pagamento_id",
        "tipo_pagamento_id",
        "conta_id",
        "tag_id",
    }

    for campo_raw, valor_raw in dados_propostos.items():
        campo = aliases.get(campo_raw, campo_raw)
        if campo not in _CAMPOS_PERMITIDOS_CONTINGENCIA and campo not in {"n_nota_empenho", "data_empenho", "ano_exercicio"}:
            continue

        valor = valor_raw
        if isinstance(valor, str):
            valor = valor.strip()
            if valor == "":
                continue

        if campo in campos_decimal:
            valor_decimal = parse_brl_decimal(valor)
            if valor_decimal is None:
                raise ValidationError(f"Valor inválido para o campo '{campo}'.")
            normalizado[campo] = valor_decimal
            continue

        if campo in campos_data:
            if isinstance(valor, str):
                data_ok = None
                for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        data_ok = datetime.strptime(valor, fmt).date()
                        break
                    except ValueError:
                        continue
                if data_ok is None:
                    raise ValidationError(f"Data inválida para o campo '{campo}'.")
                normalizado[campo] = data_ok
                continue

            raise ValidationError(f"Data inválida para o campo '{campo}'.")

        if campo in campos_inteiros:
            try:
                normalizado[campo] = int(valor)
            except (TypeError, ValueError):
                raise ValidationError(f"Valor inválido para o campo '{campo}'.")
            continue

        normalizado[campo] = valor

    return normalizado


def aplicar_aprovacao_contingencia(contingencia):
    """Aplica uma contingência aprovada ao processo com validações financeiras.

    Quando houver alteração de valor líquido, valida a compatibilidade com os
    comprovantes anexados. As atualizações do processo e o encerramento da
    contingência são persistidos atomicamente.
    """
    processo = contingencia.processo

    if "valor_liquido" in contingencia.dados_propostos:
        raw_value = contingencia.dados_propostos["valor_liquido"]
        novo_valor_liquido = parse_brl_decimal(raw_value)
        if novo_valor_liquido is None:
            return False, "O valor líquido proposto na contingência é inválido."

        soma_comprovantes = sum(
            comp.valor_pago for comp in processo.comprovantes_pagamento.all() if comp.valor_pago is not None
        )

        if abs(novo_valor_liquido - Decimal(str(soma_comprovantes))) > Decimal("0.01"):
            return (
                False,
                "A contingência não pode ser aprovada. O novo valor líquido proposto não corresponde à "
                "soma dos comprovantes bancários anexados no sistema. O setor responsável deve anexar "
                "os comprovantes restantes antes da aprovação.",
            )

    with transaction.atomic():
        campos_alterados = []
        campos_orcamentarios = {}
        for campo, valor in contingencia.dados_propostos.items():
            if campo in {"n_nota_empenho", "data_empenho", "ano_exercicio"}:
                campos_orcamentarios[campo] = valor
                continue

            if campo in _CAMPOS_PERMITIDOS_CONTINGENCIA and hasattr(processo, campo):
                setattr(processo, campo, valor)
                campos_alterados.append(campo)

        if campos_orcamentarios:
            processo.registrar_documento_orcamentario(
                numero_nota_empenho=campos_orcamentarios.get("n_nota_empenho", processo.n_nota_empenho),
                data_empenho=campos_orcamentarios.get("data_empenho", processo.data_empenho),
                ano_exercicio=campos_orcamentarios.get("ano_exercicio", processo.ano_exercicio),
            )

        if not campos_alterados and not campos_orcamentarios:
            return False, "Nenhum campo válido foi informado para atualização no processo."

        if campos_alterados:
            processo._bypass_domain_seal = True
            try:
                processo.save(update_fields=campos_alterados)
            finally:
                processo._bypass_domain_seal = False

        contingencia.status = "APROVADA"
        contingencia.save(update_fields=["status"])

        sincronizar_flag_contingencia_processo(processo)

    return True, None


def processar_aprovacao_contingencia(contingencia, usuario, parecer):
    """
    Executa a lógica de aprovação para a etapa atual da contingência.
    Aplica os campos do aprovador, avança o status, e chama
    aplicar_aprovacao_contingencia quando o fluxo estiver completo.

    Retorna (sucesso: bool, mensagem_erro: str | None).
    Levanta nenhuma exceção — erros de negócio são retornados como (False, msg).
    """
    from django.utils import timezone

    if contingencia.status == "PENDENTE_CONTADOR":
        return False, "A etapa de contador não pode ser processada como aprovação comum. Use a ação de revisão contábil."

    with transaction.atomic():
        if contingencia.status == "PENDENTE_SUPERVISOR":
            contingencia.parecer_supervisor = parecer
            contingencia.aprovado_por_supervisor = usuario
            contingencia.data_aprovacao_supervisor = timezone.now()
            contingencia.save(update_fields=[
                "parecer_supervisor", "aprovado_por_supervisor", "data_aprovacao_supervisor"
            ])
        elif contingencia.status == "PENDENTE_ORDENADOR":
            contingencia.parecer_ordenador = parecer
            contingencia.aprovado_por_ordenador = usuario
            contingencia.data_aprovacao_ordenador = timezone.now()
            contingencia.save(update_fields=[
                "parecer_ordenador", "aprovado_por_ordenador", "data_aprovacao_ordenador"
            ])
        elif contingencia.status == "PENDENTE_CONSELHO":
            contingencia.parecer_conselho = parecer
            contingencia.aprovado_por_conselho = usuario
            contingencia.data_aprovacao_conselho = timezone.now()
            contingencia.save(update_fields=[
                "parecer_conselho", "aprovado_por_conselho", "data_aprovacao_conselho"
            ])
        else:
            return False, f"Etapa '{contingencia.status}' não suporta aprovação."

        proximo = proximo_status_contingencia(contingencia)
        contingencia.status = proximo
        contingencia.save(update_fields=["status"])

        if proximo == "APROVADA":
            sucesso, msg_erro = aplicar_aprovacao_contingencia(contingencia)
            if not sucesso:
                return False, msg_erro

        sincronizar_flag_contingencia_processo(contingencia.processo)

    return True, None


def processar_revisao_contadora_contingencia(contingencia, usuario, parecer):
    """
    Executa a revisão obrigatória da contadora e aplica a aprovação.
    Retorna (sucesso: bool, mensagem_erro: str | None).
    """
    from django.utils import timezone

    if not parecer:
        return False, "O parecer da contadora é obrigatório para concluir a revisão."

    with transaction.atomic():
        contingencia.parecer_contadora = parecer
        contingencia.revisado_por_contadora = usuario
        contingencia.data_revisao_contadora = timezone.now()
        contingencia.save(update_fields=[
            "parecer_contadora", "revisado_por_contadora", "data_revisao_contadora"
        ])

        sucesso, msg_erro = aplicar_aprovacao_contingencia(contingencia)
        if not sucesso:
            return False, msg_erro

    return True, None


__all__ = [
    "_CAMPOS_PERMITIDOS_CONTINGENCIA",
    "_STATUS_CONTINGENCIA_FINAL",
    "_STATUS_PRE_AUTORIZACAO",
    "determinar_requisitos_contingencia",
    "proximo_status_contingencia",
    "sincronizar_flag_contingencia_processo",
    "normalizar_dados_propostos_contingencia",
    "aplicar_aprovacao_contingencia",
    "processar_aprovacao_contingencia",
    "processar_revisao_contadora_contingencia",
]
