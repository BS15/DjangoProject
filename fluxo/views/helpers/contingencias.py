"""State machine e regras de negocio para contingencias do fluxo financeiro."""

from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from commons.shared.text_tools import parse_brl_decimal
from fluxo.domain_models import (
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


__all__ = [
    "_CAMPOS_PERMITIDOS_CONTINGENCIA",
    "_STATUS_CONTINGENCIA_FINAL",
    "_STATUS_PRE_AUTORIZACAO",
    "determinar_requisitos_contingencia",
    "proximo_status_contingencia",
    "sincronizar_flag_contingencia_processo",
    "normalizar_dados_propostos_contingencia",
    "aplicar_aprovacao_contingencia",
]
