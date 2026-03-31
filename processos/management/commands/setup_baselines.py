from django.core.management.base import BaseCommand

from processos.models import TiposDePagamento, TiposDeDocumento, FormasDePagamento

FORMAS_DE_PAGAMENTO = [
    'PIX',
    'TRANSFERÊNCIA (TED)',
    'BOLETO BANCÁRIO',
    'DEPÓSITO IDENTIFICADO',
    'CHEQUE',
    'REMESSA BANCÁRIA',
]

# Common document set shared by payment types that follow the standard NF workflow.
DOCUMENTOS_PADRAO_NF = [
    'BOLETO BANCÁRIO',
    'RELATÓRIO DE FATURAMENTO',
    'NOTA FISCAL (NF)',
    'ORDEM DE COMPRA (OC)',
    'DOCUMENTOS ORÇAMENTÁRIOS',
    'COMPROVANTE DE PAGAMENTO',
]

TIPOS_E_DOCUMENTOS = {
    'CONTAS FIXAS': DOCUMENTOS_PADRAO_NF,
    'IMPOSTOS': [
        'GUIA DE ARRECADAÇÃO',
        'RELATÓRIO DE RETENÇÕES',
        'COMPROVANTE DE PAGAMENTO',
    ],
    'VERBAS INDENIZATÓRIAS': [
        'SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS (SCD)',
        'PROPOSTA DE CONCESSÃO DE DIÁRIAS (PCD)',
        'COMPROVAÇÃO DE DESLOCAMENTO',
    ],
    # Documents for these types will be defined once the Prestação de Contas
    # and payroll workflows are fully specified.
    'SUPRIMENTO DE FUNDOS': [],
    'REMUNERAÇÃO': [],
    'DESPESAS EVENTUAIS': DOCUMENTOS_PADRAO_NF,
}


class Command(BaseCommand):
    help = 'Populates the database with standard baseline configuration data.'

    def handle(self, *args, **kwargs):
        self.stdout.write('\n--- Formas de Pagamento ---')
        for forma in FORMAS_DE_PAGAMENTO:
            obj, created = FormasDePagamento.objects.get_or_create(forma_de_pagamento=forma)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [CRIADO]  Forma de Pagamento -> {forma}'))
            else:
                self.stdout.write(f'  [OK]      Forma de Pagamento já existe -> {forma}')

        self.stdout.write('\n--- Tipos de Pagamento & Documentos ---')
        for tipo, documentos in TIPOS_E_DOCUMENTOS.items():
            tipo_obj, created = TiposDePagamento.objects.get_or_create(tipo_de_pagamento=tipo)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [CRIADO]  Tipo de Pagamento -> {tipo}'))
            else:
                self.stdout.write(f'  [OK]      Tipo de Pagamento já existe -> {tipo}')

            for doc in documentos:
                doc_obj, doc_created = TiposDeDocumento.objects.get_or_create(
                    tipo_de_documento=doc,
                    tipo_de_pagamento=tipo_obj,
                )
                if doc_created:
                    self.stdout.write(self.style.SUCCESS(f'    [CRIADO]  Documento -> {doc}'))
                else:
                    self.stdout.write(f'    [OK]      Documento já existe -> {doc}')

        self.stdout.write(self.style.SUCCESS('\n✔  Baseline configurado com sucesso.'))
