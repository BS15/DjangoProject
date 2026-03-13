from django.core.exceptions import ValidationError

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