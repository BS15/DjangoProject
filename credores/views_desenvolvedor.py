import csv
import io
import random
from datetime import date, timedelta
from decimal import Decimal

from faker import Faker
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from credores.imports import (
    download_template_csv_contas,
    download_template_csv_credores,
    painel_importacao_view,
)
from ..utils import format_brl_currency
from ..models import (
    CargosFuncoes,
    CodigosImposto,
    ContasBancarias,
    Credor,
    Diaria,
    Boleto_Bancario,
    DocumentoFiscal,
    FormasDePagamento,
    MeiosDeTransporte,
    Processo,
    RetencaoImposto,
    StatusChoicesProcesso,
    StatusChoicesRetencoes,
    StatusChoicesVerbasIndenizatorias,
    TagChoices,
    TiposDeDocumento,
    TiposDePagamento,
)

_fake_generator = Faker('pt_BR')
_MIN_FAKE_ANO_EXERCICIO = 2020

def _ensure_fake_lookup_tables():
    """Garante dados mínimos de catálogos para geração de registros fictícios."""
    for s in [
        "AGUARDANDO LIQUIDAÇÃO / ATESTE",
        "A PAGAR - PENDENTE AUTORIZAÇÃO",
        "PAGO - EM CONFERÊNCIA",
        "ARQUIVADO",
        "CANCELADO / ANULADO",
    ]:
        StatusChoicesProcesso.objects.get_or_create(
            opcao_status__iexact=s,
            defaults={"opcao_status": s},
        )

    for t in ["Serviços", "Material", "Contrato", "Diárias"]:
        TagChoices.objects.get_or_create(tag_choice=t)

    for f in ["PIX", "TRANSFERÊNCIA (TED)", "REMESSA BANCÁRIA"]:
        FormasDePagamento.objects.get_or_create(forma_de_pagamento=f)

    for t in ["CONTAS FIXAS", "VERBAS INDENIZATÓRIAS", "IMPOSTOS"]:
        TiposDePagamento.objects.get_or_create(tipo_de_pagamento=t)

    for s in ["A RECOLHER", "RECOLHIDA"]:
        StatusChoicesRetencoes.objects.get_or_create(status_choice=s)

    for s in ["PENDENTE", "APROVADO", "CONCLUÍDO"]:
        StatusChoicesVerbasIndenizatorias.objects.get_or_create(status_choice=s)

    for m in ["Veículo Próprio", "Transporte Público", "Aéreo"]:
        MeiosDeTransporte.objects.get_or_create(meio_de_transporte=m)

    for cargo in ["Analista", "Assessor", "Diretor", "Técnico Administrativo"]:
        CargosFuncoes.objects.get_or_create(grupo="FUNCIONÁRIOS", cargo_funcao=cargo)
    for cargo in ["Empresa de TI", "Empresa de Limpeza"]:
        CargosFuncoes.objects.get_or_create(grupo="FORNECEDORES", cargo_funcao=cargo)

    if not ContasBancarias.objects.exists():
        ContasBancarias.objects.create(
            banco="Banco do Brasil",
            agencia="0001",
            conta=str(random.randint(10000, 99999)),
        )

    if not CodigosImposto.objects.exists():
        CodigosImposto.objects.create(
            codigo="1708",
            aliquota=Decimal("1.50"),
            regra_competencia="pagamento",
            serie_reinf="S4000",
        )

    if not Credor.objects.filter(tipo='PJ').exists():
        ContasBancarias.objects.get_or_create(
            banco="Caixa Econômica Federal",
            agencia="1234",
            defaults={
                "conta": str(random.randint(10000, 99999)),
            },
        )
        conta = ContasBancarias.objects.first()
        Credor.objects.create(
            nome=_fake_generator.company(),
            cpf_cnpj=_fake_generator.cnpj(),
            tipo='PJ',
            conta=conta,
            email=_fake_generator.email(),
            telefone=_fake_generator.phone_number()[:20],
            chave_pix=_fake_generator.email(),
        )

    if not Credor.objects.filter(tipo='PF').exists():
        conta = ContasBancarias.objects.first()
        cargo = CargosFuncoes.objects.filter(grupo="FUNCIONÁRIOS").first()
        Credor.objects.create(
            nome=_fake_generator.name(),
            cpf_cnpj=_fake_generator.cpf(),
            tipo='PF',
            cargo_funcao=cargo,
            conta=conta,
            email=_fake_generator.email(),
            telefone=_fake_generator.phone_number()[:20],
            chave_pix=_fake_generator.email(),
        )

def _create_fake_processos(n):
    """Cria ``n`` processos fictícios e retorna a quantidade criada."""
    status_list = list(StatusChoicesProcesso.objects.all())
    tag_list = list(TagChoices.objects.all())
    forma_list = list(FormasDePagamento.objects.all())
    tipo_list = list(TiposDePagamento.objects.all())
    contas = list(ContasBancarias.objects.all())
    credores = list(Credor.objects.all())

    if not credores or not contas or not status_list:
        return 0

    current_year = date.today().year
    created = 0
    for i in range(n):
        data_empenho = _fake_generator.date_between(start_date="-2y", end_date="today")
        data_vencimento = data_empenho + timedelta(days=random.randint(15, 90))
        data_pagamento = data_vencimento + timedelta(days=random.randint(0, 30))
        valor_bruto = Decimal(str(round(random.uniform(500.00, 150_000.00), 2)))
        retencao_pct = Decimal(str(round(random.uniform(0, 0.15), 4)))
        valor_liquido = (valor_bruto * (1 - retencao_pct)).quantize(Decimal("0.01"))
        ano = data_empenho.year if _MIN_FAKE_ANO_EXERCICIO <= data_empenho.year <= current_year else current_year
        existing_count = Processo.objects.count()
        n_empenho = f"{ano}NE{str(existing_count + i + 1).zfill(5)}"
        n_siscac = f"PAG{str(existing_count + i + 1).zfill(6)}"
        Processo.objects.create(
            extraorcamentario=random.choice([False, False, False, True]),
            n_nota_empenho=n_empenho,
            credor=random.choice(credores),
            data_empenho=data_empenho,
            valor_bruto=valor_bruto,
            valor_liquido=valor_liquido,
            ano_exercicio=ano,
            n_pagamento_siscac=n_siscac,
            data_vencimento=data_vencimento,
            data_pagamento=data_pagamento,
            forma_pagamento=random.choice(forma_list) if forma_list else None,
            tipo_pagamento=random.choice(tipo_list) if tipo_list else None,
            observacao=_fake_generator.sentence(nb_words=8)[:200],
            conta=random.choice(contas),
            status=random.choice(status_list),
            detalhamento=_fake_generator.sentence(nb_words=10)[:200],
            tag=random.choice(tag_list) if tag_list else None,
        )
        created += 1
        return 0
    """
    Arquivo movido para desenvolvedor/views_desenvolvedor.py
    Todos os recursos de desenvolvimento e testes especiais agora estão centralizados lá.
    """
    created += 1
    return created

def _create_fake_diarias(n, credores_pf, processos):
    """Cria ``n`` diárias fictícias e vincula a processos existentes quando possível."""
    status_list = list(StatusChoicesVerbasIndenizatorias.objects.all())
    transportes = list(MeiosDeTransporte.objects.all())

    cidades_origem = ["Brasília/DF", "São Paulo/SP", "Rio de Janeiro/RJ", "Belo Horizonte/MG"]
    cidades_destino = ["Manaus/AM", "Fortaleza/CE", "Salvador/BA", "Recife/PE", "Porto Alegre/RS", "Curitiba/PR"]

    created = 0
    for i in range(n):
        beneficiario = random.choice(credores_pf)
        data_saida = _fake_generator.date_between(start_date="-6m", end_date="today")
        dias = random.randint(1, 10)
        data_retorno = data_saida + timedelta(days=dias)
        quantidade = Decimal(str(round(random.uniform(0.5, float(dias)), 1)))
        existing_count = Diaria.objects.count()
        numero_seq = f"DIA{date.today().year}{str(existing_count + i + 1).zfill(5)}"
        processo = random.choice(processos) if processos else None
        Diaria.objects.create(
            processo=processo,
            numero_siscac=numero_seq,
            beneficiario=beneficiario,
            tipo_solicitacao=random.choice(['INICIAL', 'PRORROGACAO', 'COMPLEMENTACAO']),
            data_saida=data_saida,
            data_retorno=data_retorno,
            cidade_origem=random.choice(cidades_origem),
            cidade_destino=random.choice(cidades_destino),
            objetivo=_fake_generator.sentence(nb_words=8)[:200],
            quantidade_diarias=quantidade,
            meio_de_transporte=random.choice(transportes) if transportes else None,
            status=random.choice(status_list) if status_list else None,
            autorizada=random.choice([True, False]),
        )
        created += 1
    return created

def gerar_dados_fake_view(request):
    """Gera dados fictícios de processos, fiscais, retenções e diárias via formulário."""
    context = {'resultados': None}

    if request.method == 'POST':
        try:
            n_processos = max(0, int(request.POST.get('n_processos') or 0))
            n_documentos = max(0, int(request.POST.get('n_documentos') or 0))
            n_retencoes = max(0, int(request.POST.get('n_retencoes') or 0))
            n_diarias = max(0, int(request.POST.get('n_diarias') or 0))
        except (ValueError, TypeError):
            messages.error(request, "Valores inválidos. Use apenas números inteiros.")
            return redirect('gerar_dados_fake')

        _ensure_fake_lookup_tables()

        resultados = {}

        if n_processos > 0:
            criados = _create_fake_processos(n_processos)
            resultados['processos'] = criados
            if criados:
                messages.success(request, f"✔ {criados} processo(s) criado(s).")
            else:
                messages.warning(request, "Não foi possível criar processos. Verifique se há credores e contas bancárias cadastrados.")

        if n_documentos > 0:
            processos_existentes = list(Processo.objects.all())
            if not processos_existentes:
                messages.warning(request, f"Não há processos cadastrados. Os {n_documentos} documento(s) fiscal(is) não puderam ser gerados. Gere processos primeiro.")
            else:
                criados = _create_fake_documentos_fiscais(n_documentos, processos_existentes)
                resultados['documentos_fiscais'] = criados
                messages.success(request, f"✔ {criados} documento(s) fiscal(is) criado(s).")

        if n_retencoes > 0:
            notas_existentes = list(DocumentoFiscal.objects.all())
            if not notas_existentes:
                messages.warning(request, f"Não há documentos fiscais cadastrados. As {n_retencoes} retenção(ões) não puderam ser geradas. Gere documentos fiscais primeiro.")
            else:
                criados = _create_fake_retencoes(n_retencoes, notas_existentes)
                if criados:
                    resultados['retencoes'] = criados
                    messages.success(request, f"✔ {criados} retenção(ões) criada(s).")
                else:
                    messages.warning(request, "Não foi possível criar retenções. Verifique se há códigos de imposto cadastrados.")

        if n_diarias > 0:
            credores_pf = list(Credor.objects.filter(tipo='PF'))
            if not credores_pf:
                messages.warning(request, f"Não há credores PF cadastrados. As {n_diarias} diária(s) não puderam ser geradas.")
            else:
                processos_existentes = list(Processo.objects.all()) if Processo.objects.exists() else None
                criados = _create_fake_diarias(n_diarias, credores_pf, processos_existentes)
                resultados['diarias'] = criados
                messages.success(request, f"✔ {criados} diária(s) criada(s).")

        context['resultados'] = resultados
        return render(request, 'gerar_dados_fake.html', context)

    return render(request, 'gerar_dados_fake.html', context)

def gerar_dummy_pdf_view(request, pk):
    """Gera PDF fictício e anexa ao processo como documento de nota fiscal para testes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    from django.utils import timezone as tz

    processo = get_object_or_404(Processo, id=pk)

    tipo_nf = TiposDeDocumento.objects.filter(tipo_de_documento__iexact='NOTA FISCAL (NF)').first()
    if not tipo_nf:
        tipo_nf = TiposDeDocumento.objects.create(tipo_de_documento='NOTA FISCAL (NF)')

    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 80, "NOTA FISCAL DE TESTE")
    c.setFont("Helvetica", 13)
    c.drawCentredString(width / 2, height - 110, "*** DOCUMENTO FICTÍCIO GERADO PARA TESTES ***")
    c.line(50, height - 125, width - 50, height - 125)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, height - 160, f"Processo Nº:  {processo.id}")
    c.drawString(60, height - 185, f"Credor:       {processo.credor}")
    c.drawString(
        60,
        height - 210,
        f"Valor Bruto:  {format_brl_currency(processo.valor_bruto)}" if processo.valor_bruto else "Valor Bruto:  ---",
    )
    c.drawString(60, height - 235, f"Gerado em:    {tz.now().strftime('%d/%m/%Y %H:%M')}")

    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, 40, "Este documento é fictício e destina-se exclusivamente a testes do sistema.")
    c.save()
    buffer.seek(0)

    timestamp = tz.now().strftime('%Y%m%d_%H%M%S')
    filename = f'nota_fiscal_dummy_{timestamp}.pdf'
    ordem = processo.documentos.count() + 1

    doc = Boleto_Bancario(processo=processo, tipo=tipo_nf, ordem=ordem)
    doc.arquivo.save(filename, ContentFile(buffer.getvalue()), save=True)

    messages.success(request, f'PDF de teste gerado e vinculado ao Processo #{processo.id}.')
    return redirect('documentos_fiscais', pk=pk)
