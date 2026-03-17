from django.core.exceptions import ValidationError


# ============================================================
# TURNPIKE: Status-transition gate checks
# ============================================================

def verificar_turnpike(processo, status_anterior, status_novo):
    """
    Validates business rules that must be satisfied before a process is allowed
    to advance to a new status ("turnpike" / porteira).

    Parameters
    ----------
    processo      : Processo instance (already saved in DB; documents/notas are
                    assumed to reflect the final state before the status change).
    status_anterior : str – current status label (case-insensitive).
    status_novo     : str – target status label (case-insensitive).

    Returns
    -------
    list[str] – list of human-readable error messages.  Empty list means OK.
    """
    erros = []

    anterior = status_anterior.upper().strip()
    novo = status_novo.upper().strip()

    # ------------------------------------------------------------------ #
    # Rule 1: A EMPENHAR → AGUARDANDO LIQUIDAÇÃO                          #
    # Requires at least one "DOCUMENTOS ORÇAMENTÁRIOS" document attached. #
    # ------------------------------------------------------------------ #
    if anterior == 'A EMPENHAR' and novo.startswith('AGUARDANDO LIQUIDAÇÃO'):
        tem_doc_orcamentario = processo.documentos.filter(
            tipo__tipo_de_documento__iexact='DOCUMENTOS ORÇAMENTÁRIOS'
        ).exists()
        if not tem_doc_orcamentario:
            erros.append(
                'Para avançar para "Aguardando Liquidação" é necessário anexar ao menos '
                'um documento do tipo "DOCUMENTOS ORÇAMENTÁRIOS".'
            )

    # ------------------------------------------------------------------ #
    # Rule 2: AGUARDANDO LIQUIDAÇÃO → A PAGAR - PENDENTE AUTORIZAÇÃO      #
    # All documentos fiscais linked to the process must have atestada=True.#
    # ------------------------------------------------------------------ #
    if anterior.startswith('AGUARDANDO LIQUIDAÇÃO') and novo == 'A PAGAR - PENDENTE AUTORIZAÇÃO':
        notas = processo.notas_fiscais.all()
        if not notas.exists():
            erros.append(
                'Para avançar para "A Pagar - Pendente Autorização" é necessário que haja ao '
                'menos um documento fiscal vinculado ao processo.'
            )
        else:
            nao_atestadas = notas.filter(atestada=False)
            if nao_atestadas.exists():
                nomes = ', '.join(
                    nf.numero_nota_fiscal or f'(id {nf.pk})' for nf in nao_atestadas[:5]
                )
                erros.append(
                    f'Todos os documentos fiscais devem estar atestados antes de avançar para '
                    f'"A Pagar - Pendente Autorização". Documento(s) pendente(s): {nomes}.'
                )

    # ------------------------------------------------------------------ #
    # Rule 3: LANÇADO - AGUARDANDO COMPROVANTE → PAGO - EM CONFERÊNCIA    #
    # Requires at least one "COMPROVANTE DE PAGAMENTO" document attached.  #
    # ------------------------------------------------------------------ #
    if anterior == 'LANÇADO - AGUARDANDO COMPROVANTE' and novo == 'PAGO - EM CONFERÊNCIA':
        tem_comprovante = processo.documentos.filter(
            tipo__tipo_de_documento__iexact='COMPROVANTE DE PAGAMENTO'
        ).exists()
        if not tem_comprovante:
            erros.append(
                'Para avançar para "Pago - Em Conferência" é necessário anexar ao menos '
                'um documento do tipo "COMPROVANTE DE PAGAMENTO".'
            )

    return erros


def validar_regras_processo(cleaned_data):
    """
    Validates rules specific to the Processo model.
    Returns a dictionary of errors.
    """
    errors = {}

    data_pagamento = cleaned_data.get('data_pagamento')
    data_vencimento = cleaned_data.get('data_vencimento')
    valor_bruto = cleaned_data.get('valor_bruto')
    valor_liquido = cleaned_data.get('valor_liquido')

    # Rule 1: Data de pagamento must not be over data de vencimento
    if data_pagamento and data_vencimento and data_pagamento > data_vencimento:
        errors['data_pagamento'] = ValidationError(
            "A data de pagamento não pode ser posterior à data de vencimento."
        )

    # Rule 2: Valor bruto must not be inferior to valor liquido
    if valor_bruto is not None and valor_liquido is not None and valor_bruto < valor_liquido:
        errors['valor_bruto'] = ValidationError(
            "O valor bruto não pode ser inferior ao valor líquido."
        )

    return errors


def validar_regras_suprimento(cleaned_data):
    """
    Validates rules specific to the SuprimentoDeFundos model.
    Returns a dictionary of errors.
    """
    errors = {}

    data_saida = cleaned_data.get('data_saida')
    data_retorno = cleaned_data.get('data_retorno')

    # Rule: Data de retorno cannot be before data de saida
    if data_saida and data_retorno and data_retorno < data_saida:
        errors['data_retorno'] = ValidationError(
            "O período final (data de retorno) não pode ser anterior ao inicial (data de saída)."
        )

    return errors