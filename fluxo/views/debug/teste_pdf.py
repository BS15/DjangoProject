from decimal import Decimal
from unittest.mock import MagicMock

from django.http import HttpResponse
from django.shortcuts import render
from faker import Faker

from fluxo.pdf_generators import gerar_documento_pdf

fake = Faker('pt_BR')


def painel_teste_pdfs(request):
    return render(request, 'fluxo/teste_pdfs.html')


def gerar_pdf_fake_view(request, doc_type):
    def mock_credor():
        c = MagicMock()
        c.nome = fake.name()
        c.cpf_cnpj = fake.cpf()
        c.email = fake.email()
        return c

    def mock_user():
        u = MagicMock()
        u.get_full_name.return_value = fake.name()
        return u

    if doc_type in ['scd', 'pcd']:
        obj = MagicMock()
        obj.numero_siscac = fake.numerify(text="2026/####")
        obj.beneficiario = mock_credor()
        obj.proponente = mock_user()
        obj.data_saida = fake.date_between(start_date='today', end_date='+5d')
        obj.data_retorno = fake.date_between(start_date='+6d', end_date='+10d')
        obj.cidade_origem = fake.city()
        obj.cidade_destino = fake.city()
        obj.objetivo = fake.paragraph(nb_sentences=2)
        obj.quantidade_diarias = Decimal('2.5')
        obj.valor_total = Decimal(fake.numerify(text="####.##"))
        obj.meio_de_transporte.nome = "Aéreo"

    elif doc_type in ['autorizacao', 'conselho_fiscal', 'contabilizacao']:
        obj = MagicMock()
        obj.id = fake.random_int(min=1000, max=9999)
        obj.n_nota_empenho = fake.numerify(text="2026NE####")
        obj.credor = mock_credor()
        obj.valor_liquido = Decimal(fake.numerify(text="####.##"))
        obj.credor.conta.banco = "Banco do Brasil"
        obj.credor.conta.agencia = "1234-5"
        obj.credor.conta.conta = "98765-4"
        obj.detalhamento = fake.paragraph(nb_sentences=2)

    elif doc_type == 'ateste':
        obj = MagicMock()
        obj.numero = fake.numerify(text="NF-####")
        obj.numero_nota_fiscal = obj.numero
        obj.valor = Decimal(fake.numerify(text="####.##"))
        obj.valor_bruto = obj.valor
        obj.processo.id = fake.random_int(min=1000, max=9999)
        obj.processo.credor = mock_credor()
        obj.fiscal_contrato = mock_user()

    elif doc_type.startswith('recibo_'):
        obj = MagicMock()
        if doc_type == 'recibo_reembolso':
            obj.__class__.__name__ = 'ReembolsoCombustivel'
        elif doc_type == 'recibo_auxilio':
            obj.__class__.__name__ = 'AuxilioRepresentacao'
        elif doc_type == 'recibo_jeton':
            obj.__class__.__name__ = 'Jeton'
        elif doc_type == 'recibo_suprimento':
            obj.__class__.__name__ = 'SuprimentoDeFundos'

        obj.beneficiario = mock_credor()
        obj.suprido = obj.beneficiario
        obj.valor_total = Decimal(fake.numerify(text="####.##"))
        obj.valor_aprovado = obj.valor_total

    else:
        return HttpResponse(f"Tipo de documento '{doc_type}' não reconhecido.", status=400)

    kwargs = {'numero_reuniao': fake.random_int(min=1, max=50)} if doc_type == 'conselho_fiscal' else {}
    pdf_bytes = gerar_documento_pdf(doc_type, obj, **kwargs)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="teste_{doc_type}.pdf"'
    return response
