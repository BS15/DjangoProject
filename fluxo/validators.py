from django.core.exceptions import ValidationError

from commons.shared.file_validators import validar_arquivo_seguro
from commons.shared.text_tools import format_brl_currency
from fluxo.domain_models.processos import (
    PROCESSO_STATUS_BLOQUEADOS_FORM,
    PROCESSO_STATUS_BLOQUEADOS_TOTAL,
    PROCESSO_STATUS_SOMENTE_DOCUMENTOS,
    ProcessoStatus,
)


STATUS_BLOQUEADOS_TOTAL = set(PROCESSO_STATUS_BLOQUEADOS_TOTAL)

STATUS_SOMENTE_DOCUMENTOS = set(PROCESSO_STATUS_SOMENTE_DOCUMENTOS)

STATUS_BLOQUEADOS_FORM = list(PROCESSO_STATUS_BLOQUEADOS_FORM)


def verificar_turnpike(processo, status_anterior, status_novo):
    """
    Valida as regras de transição de status do processo (turnpike).

    Retorna uma lista de mensagens de erro; lista vazia indica transição válida.
    """
    erros = []

    anterior = status_anterior.upper().strip()
    novo = status_novo.upper().strip()

    if anterior == ProcessoStatus.A_EMPENHAR and novo == ProcessoStatus.AGUARDANDO_LIQUIDACAO:
        tem_doc_orcamentario = processo.documentos.filter(
            tipo__tipo_de_documento__iexact='DOCUMENTOS ORÇAMENTÁRIOS'
        ).exists()
        if not tem_doc_orcamentario:
            erros.append(
                'Para avançar para "Aguardando Liquidação" é necessário anexar ao menos '
                'um documento do tipo "DOCUMENTOS ORÇAMENTÁRIOS".'
            )

    if anterior == ProcessoStatus.AGUARDANDO_LIQUIDACAO and novo == ProcessoStatus.A_PAGAR_PENDENTE_AUTORIZACAO:
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

    if anterior == ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE and novo == ProcessoStatus.PAGO_EM_CONFERENCIA:
        tipo_pagamento_nome = ''
        if getattr(processo, 'tipo_pagamento_id', None):
            try:
                tipo_pagamento_nome = (processo.tipo_pagamento.tipo_de_pagamento or '').upper()
            except AttributeError:
                tipo_pagamento_nome = ''

        is_suprimento = 'SUPRIMENTO' in tipo_pagamento_nome

        tem_comprovante = processo.documentos.filter(
            tipo__tipo_de_documento__iexact='COMPROVANTE DE PAGAMENTO'
        ).exists()
        if not tem_comprovante:
            erros.append(
                'Para avançar para "Pago - Em Conferência" é necessário anexar ao menos '
                'um documento do tipo "COMPROVANTE DE PAGAMENTO".'
            )

        if not is_suprimento:
            soma_comprovantes = sum(
                comp.valor_pago for comp in processo.comprovantes_pagamento.all()
                if comp.valor_pago is not None
            )
            valor_liquido = processo.valor_liquido or 0
            if abs(float(soma_comprovantes) - float(valor_liquido)) > 0.01:
                erros.append(
                    f'Soma dos comprovantes de pagamento ({format_brl_currency(soma_comprovantes)}) é diferente do '
                    f'valor líquido do processo ({format_brl_currency(valor_liquido)}). '
                    f'Diferença: {format_brl_currency(abs(float(soma_comprovantes) - float(valor_liquido)))}.'
                )

    return erros


def verificar_turnpike_diaria(diaria, status_anterior, novo_status_str):
    """Valida transições de status permitidas para diárias.

    A função retorna lista de erros; quando vazia, a transição está autorizada.
    """
    erros = []
    novo_status_upper = novo_status_str.upper()

    transicoes_validas = {
        '': ['SOLICITADA'],
        'SOLICITADA': ['APROVADA', 'REJEITADA'],
        'APROVADA': ['ENVIADA PARA PAGAMENTO', 'SOLICITADA'],
        'ENVIADA PARA PAGAMENTO': ['PAGA', 'APROVADA'],
        'PAGA': [],
    }

    if status_anterior:
        status_anterior_upper = status_anterior.upper()
        if status_anterior_upper in transicoes_validas and novo_status_upper not in transicoes_validas[status_anterior_upper]:
            permitidas = ', '.join(transicoes_validas.get(status_anterior_upper, [])) or 'nenhuma'
            erros.append(
                (
                    f"Transição inválida de '{status_anterior_upper}' para '{novo_status_upper}'. "
                    f"Transições permitidas: {permitidas}."
                )
            )

    return erros


def validar_regras_processo(cleaned_data):
    """
    Valida regras de negócio do formulário de processo.

    Retorna um dicionário no formato ``{campo: ValidationError}``.
    """
    errors = {}

    data_pagamento = cleaned_data.get('data_pagamento')
    data_vencimento = cleaned_data.get('data_vencimento')
    valor_bruto = cleaned_data.get('valor_bruto')
    valor_liquido = cleaned_data.get('valor_liquido')

    if data_pagamento and data_vencimento and data_vencimento < data_pagamento:
        errors['data_vencimento'] = ValidationError(
            "A data de vencimento não pode ser anterior à data de pagamento."
        )

    if valor_bruto is not None and valor_liquido is not None and valor_bruto < valor_liquido:
        errors['valor_bruto'] = ValidationError(
            "O valor bruto não pode ser inferior ao valor líquido."
        )

    return errors


def validar_regras_suprimento(cleaned_data):
    """
    Valida regras de negócio do formulário de suprimento de fundos.

    Retorna um dicionário no formato ``{campo: ValidationError}``.
    """
    errors = {}

    inicio_periodo = cleaned_data.get('inicio_periodo')
    fim_periodo = cleaned_data.get('fim_periodo')

    if inicio_periodo and fim_periodo and fim_periodo < inicio_periodo:
        errors['fim_periodo'] = ValidationError(
            "O período final não pode ser anterior ao período inicial."
        )

    return errors
