import random
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from faker import Faker

from processos.models import (
    ContasBancarias,
    Credor,
    FormasDePagamento,
    Processo,
    StatusChoicesProcesso,
    TagChoices,
    TiposDePagamento,
)

fake = Faker('pt_BR')

MAX_DEDUCTION_RATE = 0.15  # Maximum deduction applied to valor_bruto to derive valor_liquido


def _get_or_create_status_choices():
    """Ensure at least a basic set of process status choices exists."""
    defaults = [
        'Em Análise',
        'Aguardando Pagamento',
        'Pago',
        'Cancelado',
        'Devolvido',
    ]
    choices = []
    for label in defaults:
        obj, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice=label, defaults={'is_active': True}
        )
        choices.append(obj)
    return choices


def _get_or_create_formas_pagamento():
    """Ensure at least a basic set of payment method choices exists."""
    defaults = ['Transferência Bancária', 'PIX', 'Boleto', 'Ordem Bancária']
    choices = []
    for label in defaults:
        obj, _ = FormasDePagamento.objects.get_or_create(
            forma_de_pagamento=label, defaults={'is_active': True}
        )
        choices.append(obj)
    return choices


def _get_or_create_tipos_pagamento():
    """Ensure at least a basic set of payment type choices exists."""
    defaults = ['Serviços', 'Materiais', 'Obras', 'Diárias', 'Outros']
    choices = []
    for label in defaults:
        obj, _ = TiposDePagamento.objects.get_or_create(
            tipo_de_pagamento=label, defaults={'is_active': True}
        )
        choices.append(obj)
    return choices


def _get_or_create_tags():
    """Ensure at least a basic set of tag choices exists."""
    defaults = ['Urgente', 'Prioritário', 'Rotina', 'Auditoria']
    choices = []
    for label in defaults:
        obj, _ = TagChoices.objects.get_or_create(
            tag_choice=label, defaults={'is_active': True}
        )
        choices.append(obj)
    return choices


def _create_credor(tipo='PJ'):
    """Create a single fictitious creditor."""
    conta = ContasBancarias.objects.create(
        titular=fake.name(),
        banco=fake.random_element(['Banco do Brasil', 'Caixa Econômica Federal', 'Bradesco', 'Itaú', 'Santander']),
        agencia=fake.numerify('####-#'),
        conta=fake.numerify('######-#'),
    )
    if tipo == 'PF':
        return Credor.objects.create(
            nome=fake.name(),
            cpf_cnpj=fake.cpf(),
            tipo='PF',
            conta=conta,
            chave_pix=fake.cpf(),
            telefone=fake.phone_number(),
            email=fake.email(),
        )
    return Credor.objects.create(
        nome=fake.company(),
        cpf_cnpj=fake.cnpj(),
        tipo='PJ',
        conta=conta,
        chave_pix=fake.cnpj(),
        telefone=fake.phone_number(),
        email=fake.company_email(),
    )


class Command(BaseCommand):
    help = (
        'Generates fictitious Processo records for testing purposes. '
        'Does not require AI – runs as pure Python/Django.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'count',
            nargs='?',
            type=int,
            default=50,
            help='Number of sample processos to create (default: 50).',
        )
        parser.add_argument(
            '--credores',
            type=int,
            default=10,
            help='Number of fictitious creditors to create (default: 10).',
        )

    def handle(self, *args, **options):
        count = options['count']
        n_credores = options['credores']

        self.stdout.write('Preparando dados auxiliares...')

        status_choices = _get_or_create_status_choices()
        formas = _get_or_create_formas_pagamento()
        tipos = _get_or_create_tipos_pagamento()
        tags = _get_or_create_tags()

        self.stdout.write(f'Criando {n_credores} credores fictícios...')
        credores = [_create_credor(tipo=random.choice(['PF', 'PJ'])) for _ in range(n_credores)]

        self.stdout.write(f'Criando {count} processos fictícios...')

        created = 0
        for i in range(count):
            ano = random.randint(2022, 2026)
            data_empenho = fake.date_between(
                start_date=date(ano, 1, 1),
                end_date=date(ano, 12, 31),
            )
            data_vencimento = fake.date_between(
                start_date=data_empenho,
                end_date=date(ano, 12, 31),
            )
            valor_bruto = Decimal(str(round(random.uniform(500, 150_000), 2)))
            valor_liquido = valor_bruto - Decimal(str(round(random.uniform(0, float(valor_bruto) * MAX_DEDUCTION_RATE), 2)))

            Processo.objects.create(
                extraorcamentario=fake.boolean(chance_of_getting_true=10),
                n_nota_empenho=fake.numerify(f'{ano}NE######'),
                credor=random.choice(credores),
                data_empenho=data_empenho,
                valor_bruto=valor_bruto,
                valor_liquido=valor_liquido,
                ano_exercicio=ano,
                n_pagamento_siscac=fake.numerify('PAG#########') if fake.boolean(chance_of_getting_true=70) else None,
                data_vencimento=data_vencimento,
                data_pagamento=fake.date_between(start_date=data_empenho, end_date=data_vencimento)
                if fake.boolean(chance_of_getting_true=60) else None,
                forma_pagamento=random.choice(formas),
                tipo_pagamento=random.choice(tipos),
                observacao=fake.sentence(nb_words=8) if fake.boolean(chance_of_getting_true=50) else None,
                status=random.choice(status_choices),
                detalhamento=fake.sentence(nb_words=10),
                tag=random.choice(tags) if fake.boolean(chance_of_getting_true=40) else None,
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nConcluído! {created} processo(s) fictício(s) criado(s) com sucesso.'
            )
        )
