import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from faker import Faker

from processos.models import (
    CargosFuncoes,
    ContasBancarias,
    Credor,
    FormasDePagamento,
    Processo,
    StatusChoicesProcesso,
    TagChoices,
    TiposDePagamento,
)

fake = Faker('pt_BR')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_lookup(model, field_name, values):
    """Create lookup-table rows when they don't exist, return queryset."""
    for value in values:
        model.objects.get_or_create(**{field_name: value})
    return model.objects.filter(**{f"{field_name}__in": values})


def _random_cpf():
    """Generate a valid CPF string using Faker."""
    return fake.cpf()


def _random_cnpj():
    """Generate a valid CNPJ string using Faker."""
    return fake.cnpj()


# ---------------------------------------------------------------------------
# Seed data constants
# ---------------------------------------------------------------------------

STATUS_PROCESSOS = [
    "A EMPENHAR",
    "AGUARDANDO LIQUIDAÇÃO / ATESTE",
    "A PAGAR - PENDENTE AUTORIZAÇÃO",
    "A PAGAR - ENVIADO PARA AUTORIZAÇÃO",
    "A PAGAR - AUTORIZADO",
    "PAGO - EM CONFERÊNCIA",
    "PAGO - A CONTABILIZAR",
    "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
    "APROVADO - PENDENTE ARQUIVAMENTO",
    "ARQUIVADO",
    "CANCELADO / ANULADO",
]

TAGS = [
    "Urgente",
    "Contrato",
    "Serviços",
    "Material",
    "Diárias",
    "Verbas Indenizatórias",
    "Suprimento de Fundos",
]

FORMAS_PAGAMENTO = [
	"REMESSA BANCÁRIA",
	"TRANSFERÊNCIA (TED)",
	"PIX",
	"GERENCIADOR/BOLETO BANCÁRIO",
]

TIPOS_PAGAMENTO = [
    "SUPRIMENTO DE FUNDOS",
	"CONTAS FIXAS",
	"IMPOSTOS",
	"VERBAS INDENIZATÓRIAS",
]

GRUPOS = [
    "FORNECEDORES",
    "FUNCIONÁRIOS",
]

CARGOS_POR_GRUPO = {
    "FORNECEDORES": ["Empresa de TI", "Empresa de Limpeza", "Empresa de Segurança"],
    "FUNCIONÁRIOS": ["Assessor", "Analista", "Diretor", "Técnico Administrativo"],
}

BANCOS = [
    {"banco": "Banco do Brasil", "agencia": "0001"},
    {"banco": "Caixa Econômica Federal", "agencia": "1234"},
    {"banco": "Bradesco", "agencia": "3456"},
    {"banco": "Itaú", "agencia": "5678"},
    {"banco": "Santander", "agencia": "9012"},
]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Generates 50 sample processos with realistic fake data using Faker. "
        "Also creates the required lookup data (status, tags, payment methods, "
        "creditors, bank accounts, etc.) if they do not already exist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=50,
            help="Number of sample processos to create (default: 50).",
        )
        parser.add_argument(
            "--credores",
            type=int,
            default=20,
            help="Number of sample credores to create (default: 20).",
        )

    def handle(self, *args, **options):
        count = options["count"]
        n_credores = options["credores"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== create_sample_data ==="))

        # ------------------------------------------------------------------
        # 1. Lookup tables
        # ------------------------------------------------------------------
        self.stdout.write("  Creating lookup data…")

        status_qs = _get_or_create_lookup(
            StatusChoicesProcesso, "status_choice", STATUS_PROCESSOS
        )
        tag_qs = _get_or_create_lookup(TagChoices, "tag_choice", TAGS)
        forma_qs = _get_or_create_lookup(
            FormasDePagamento, "forma_de_pagamento", FORMAS_PAGAMENTO
        )
        tipo_pag_qs = _get_or_create_lookup(
            TiposDePagamento, "tipo_de_pagamento", TIPOS_PAGAMENTO
        )

        status_list = list(status_qs)
        tag_list = list(tag_qs)
        forma_list = list(forma_qs)
        tipo_pag_list = list(tipo_pag_qs)

        # ------------------------------------------------------------------
        # 2. CargosFuncoes
        # ------------------------------------------------------------------
        for nome_grupo in GRUPOS:
            for cargo_nome in CARGOS_POR_GRUPO[nome_grupo]:
                CargosFuncoes.objects.get_or_create(
                    grupo=nome_grupo, cargo_funcao=cargo_nome
                )

        # ------------------------------------------------------------------
        # 3. Bank accounts
        # ------------------------------------------------------------------
        contas = []
        for banco_info in BANCOS:
            conta, _ = ContasBancarias.objects.get_or_create(
                banco=banco_info["banco"],
                agencia=banco_info["agencia"],
                defaults={
                    "conta": str(random.randint(10000, 99999)),
                },
            )
            contas.append(conta)

        # ------------------------------------------------------------------
        # 4. Credores  (PF + PJ mix)
        # ------------------------------------------------------------------
        self.stdout.write(f"  Creating {n_credores} credores…")

        grupos_list = GRUPOS

        credores_pj = []
        credores_pf = []

        for i in range(n_credores):
            tipo = "PF" if i % 3 != 0 else "PJ"  # ~2/3 PF, 1/3 PJ
            nome_grupo = random.choice(grupos_list)
            cargo_choices = list(
                CargosFuncoes.objects.filter(grupo=nome_grupo)
            )
            cargo = random.choice(cargo_choices) if cargo_choices else None
            conta = random.choice(contas)

            if tipo == "PF":
                nome = fake.name()
                cpf_cnpj = _random_cpf()
            else:
                nome = fake.company()
                cpf_cnpj = _random_cnpj()

            credor = Credor.objects.create(
                nome=nome,
                cpf_cnpj=cpf_cnpj,
                conta=conta,
                chave_pix=fake.email(),
                cargo_funcao=cargo,
                telefone=fake.phone_number()[:20],
                email=fake.email(),
                tipo=tipo,
            )

            if tipo == "PJ":
                credores_pj.append(credor)
            else:
                credores_pf.append(credor)

        # Ensure we have at least one of each type for FK constraints
        if not credores_pj:
            credores_pj = credores_pf[:1]
        if not credores_pf:
            credores_pf = credores_pj[:1]

        all_credores = credores_pj + credores_pf

        # ------------------------------------------------------------------
        # 5. Processos
        # ------------------------------------------------------------------
        self.stdout.write(f"  Creating {count} processos…")

        created = 0
        for i in range(count):
            data_empenho = fake.date_between(start_date="-2y", end_date="today")
            data_vencimento = data_empenho + timedelta(days=random.randint(15, 90))
            data_pagamento = data_vencimento + timedelta(days=random.randint(0, 30))

            valor_bruto = Decimal(
                str(round(random.uniform(500.00, 150_000.00), 2))
            )
            # Net value is 85–100 % of gross
            retencao_pct = Decimal(str(round(random.uniform(0, 0.15), 4)))
            valor_liquido = (valor_bruto * (1 - retencao_pct)).quantize(
                Decimal("0.01")
            )

            ano = data_empenho.year
            current_year = date.today().year
            if ano < 2020 or ano > current_year:
                ano = current_year

            n_empenho = (
                f"{ano}NE{str(i + 1).zfill(5)}"
            )
            n_siscac = f"PAG{str(i + 1).zfill(6)}"

            Processo.objects.create(
                extraorcamentario=random.choice([False, False, False, True]),
                n_nota_empenho=n_empenho,
                credor=random.choice(all_credores),
                data_empenho=data_empenho,
                valor_bruto=valor_bruto,
                valor_liquido=valor_liquido,
                ano_exercicio=ano,
                n_pagamento_siscac=n_siscac,
                data_vencimento=data_vencimento,
                data_pagamento=data_pagamento,
                forma_pagamento=random.choice(forma_list),
                tipo_pagamento=random.choice(tipo_pag_list),
                observacao=fake.sentence(nb_words=8)[:200],
                conta=random.choice(contas),
                status=random.choice(status_list),
                detalhamento=fake.sentence(nb_words=10)[:200],
                tag=random.choice(tag_list),
            )
            created += 1

        # ------------------------------------------------------------------
        # 6. Summary
        # ------------------------------------------------------------------
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✔  Done! Created {created} processos and "
                f"{len(all_credores)} credores."
            )
        )
        self.stdout.write(
            "   Run  python manage.py runserver  and visit the admin or "
            "home page to see the sample data."
        )
