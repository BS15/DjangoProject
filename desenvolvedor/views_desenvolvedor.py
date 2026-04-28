"""Views de suporte ao desenvolvimento: geração de dados fictícios, PDFs de teste e inspeção de RBAC."""

import csv
import io
import logging
import random
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from faker import Faker
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError

from credores.imports import (
    download_template_csv_credores,
    painel_importacao_view,
)
from credores.models import CargosFuncoes, ContasBancarias, Credor
from fiscal.models import CodigosImposto, DocumentoFiscal, RetencaoImposto, StatusChoicesRetencoes
from fiscal.models import LiquidacaoDocumentoFiscal
from pagamentos.domain_models import (
    Boleto_Bancario,
    DocumentoOrcamentario,
    FormasDePagamento,
    Processo,
    StatusChoicesProcesso,
    TagChoices,
    TiposDeDocumento,
    TiposDePagamento,
)
from pagamentos.views.support.contas_fixas.imports import download_template_csv_contas
from commons.shared.text_tools import format_brl_currency
from commons.shared.pdf_tools import gerar_documento_pdf
from pagamentos.pdf_generators import FLUXO_DOCUMENT_REGISTRY
from suprimentos.pdf_generators import SUPRIMENTOS_DOCUMENT_REGISTRY
from verbas_indenizatorias.models import Diaria, MeiosDeTransporte, StatusChoicesVerbasIndenizatorias
from verbas_indenizatorias.pdf_generators import VERBAS_DOCUMENT_REGISTRY

logger = logging.getLogger(__name__)

_fake_generator = Faker("pt_BR")
_MIN_FAKE_ANO_EXERCICIO = 2020
_FAKE_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"

_GRUPOS_PERMISSOES_FAKE = {
    "FUNCIONARIO(A) CONTAS A PAGAR": [
        "pagamentos.operador_contas_a_pagar",
        "pagamentos.pode_visualizar_processos_pagamento",
        "pagamentos.pode_editar_processos_pagamento",
        "pagamentos.pode_aprovar_contingencia_supervisor",
        "pagamentos.pode_arquivar",
        "suprimentos.acesso_backoffice",
        "suprimentos.pode_gerir_prestacao_contas_suprimento",
        "verbas_indenizatorias.analisar_prestacao_contas",
    ],
    "FISCAL DE CONTRATO": ["pagamentos.pode_atestar_liquidacao"],
    "ORDENADOR(A) DE DESPESA": ["pagamentos.pode_visualizar_processos_pagamento", "pagamentos.pode_autorizar_pagamento"],
    "CONTADOR(A)": ["pagamentos.pode_visualizar_processos_pagamento", "pagamentos.pode_contabilizar"],
    "CONSELHEIRO(A) FISCAL": ["pagamentos.pode_visualizar_processos_pagamento", "pagamentos.pode_auditar_conselho"],
}

_USUARIOS_TESTE_RBAC = [
    {
        "perfil": "Operador contas a pagar",
        "username": "teste_operador_contas_pagar",
        "password": "Teste@123",
        "email": "teste_operador_contas_pagar@example.com",
        "groups": ["FUNCIONARIO(A) CONTAS A PAGAR"],
    },
    {
        "perfil": "Fiscal de contrato e proponente",
        "username": "teste_fiscal_proponente",
        "password": "Teste@123",
        "email": "teste_fiscal_proponente@example.com",
        "groups": ["FISCAL DE CONTRATO"],
    },
    {
        "perfil": "Conselheiro fiscal",
        "username": "teste_conselheiro_fiscal",
        "password": "Teste@123",
        "email": "teste_conselheiro_fiscal@example.com",
        "groups": ["CONSELHEIRO(A) FISCAL"],
    },
    {
        "perfil": "Contador",
        "username": "teste_contador",
        "password": "Teste@123",
        "email": "teste_contador@example.com",
        "groups": ["CONTADOR(A)"],
    },
    {
        "perfil": "Ordenador de despesas",
        "username": "teste_ordenador_despesas",
        "password": "Teste@123",
        "email": "teste_ordenador_despesas@example.com",
        "groups": ["ORDENADOR(A) DE DESPESA"],
    },
]

_CREDENCIAIS_USUARIOS_TESTE_PATH = Path(__file__).resolve().parents[1] / "usuarios_teste_credenciais.txt"


def _ensure_rbac_groups_for_fake_users():
    """Garante grupos/permissoes canônicas para perfis usados nos usuários de teste."""
    grupos = {}
    permissoes_ausentes = []

    for nome_grupo, permissoes in _GRUPOS_PERMISSOES_FAKE.items():
        grupo, _ = Group.objects.get_or_create(name=nome_grupo)
        for permissao_str in permissoes:
            try:
                app_label, codename = permissao_str.split(".", 1)
            except ValueError:
                permissoes_ausentes.append(permissao_str)
                continue

            permissao = Permission.objects.filter(
                codename=codename,
                content_type__app_label=app_label,
            ).first()
            if permissao is None:
                permissoes_ausentes.append(permissao_str)
                continue
            grupo.permissions.add(permissao)
        grupos[nome_grupo] = grupo

    return grupos, sorted(set(permissoes_ausentes))


def _create_or_update_fake_users_with_permissions():
    """Cria usuários hipotéticos de teste e salva credenciais em txt na raiz do projeto."""
    grupos, permissoes_ausentes = _ensure_rbac_groups_for_fake_users()
    UserModel = get_user_model()

    criados = 0
    atualizados = 0
    linhas_credenciais = [
        "USUARIOS HIPOTETICOS DE TESTE - RBAC",
        "",
    ]

    for user_cfg in _USUARIOS_TESTE_RBAC:
        user, created = UserModel.objects.get_or_create(
            username=user_cfg["username"],
            defaults={
                "email": user_cfg["email"],
                "is_active": True,
            },
        )

        user.email = user_cfg["email"]
        user.is_active = True
        user.set_password(user_cfg["password"])
        user.save(update_fields=["email", "is_active", "password"])

        grupos_usuario = [grupos[nome] for nome in user_cfg["groups"] if nome in grupos]
        user.groups.set(grupos_usuario)

        if created:
            criados += 1
        else:
            atualizados += 1

        linhas_credenciais.extend(
            [
                f"Perfil: {user_cfg['perfil']}",
                f"Usuario: {user_cfg['username']}",
                f"Senha: {user_cfg['password']}",
                f"Grupos: {', '.join(user_cfg['groups'])}",
                "",
            ]
        )

    _CREDENCIAIS_USUARIOS_TESTE_PATH.write_text("\n".join(linhas_credenciais), encoding="utf-8")

    return {
        "criados": criados,
        "atualizados": atualizados,
        "total": len(_USUARIOS_TESTE_RBAC),
        "arquivo": str(_CREDENCIAIS_USUARIOS_TESTE_PATH),
        "permissoes_ausentes": permissoes_ausentes,
    }


def _create_fake_documento_orcamentario(processo, numero_nota_empenho, data_empenho, ano_exercicio):
    """Cria documento orçamentário canônico com arquivo e tipo obrigatórios."""
    tipo_doc, _ = TiposDeDocumento.objects.get_or_create(
        tipo_documento__iexact="DOCUMENTOS ORÇAMENTÁRIOS",
        defaults={"tipo_documento": "DOCUMENTOS ORÇAMENTÁRIOS"},
    )
    nome_arquivo = f"doc_orcamentario_fake_{processo.id}_{ano_exercicio}.pdf"
    return DocumentoOrcamentario.objects.create(
        processo=processo,
        arquivo=ContentFile(_FAKE_PDF_BYTES, name=nome_arquivo),
        tipo=tipo_doc,
        numero_nota_empenho=numero_nota_empenho,
        data_empenho=data_empenho,
        ano_exercicio=ano_exercicio,
    )

def _create_fake_pdf_documento_fiscal(processo, numero_nota_fiscal, serie_nota_fiscal):
    """Anexa um PDF dummy de nota fiscal ao processo para validar lastro documental."""
    tipo_nf, _ = TiposDeDocumento.objects.get_or_create(
        tipo_documento__iexact="NOTA FISCAL (NF)",
        defaults={"tipo_documento": "NOTA FISCAL (NF)"},
    )
    ordem = processo.documentos.count() + 1
    nome_arquivo = f"nota_fiscal_fake_{processo.id}_{serie_nota_fiscal}_{numero_nota_fiscal}.pdf"
    doc = Boleto_Bancario(processo=processo, tipo=tipo_nf, ordem=ordem)
    doc.arquivo.save(nome_arquivo, ContentFile(_FAKE_PDF_BYTES), save=True)
    return doc


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
        TagChoices.objects.get_or_create(opcao_etiqueta=t)

    for f in ["PIX", "TRANSFERÊNCIA (TED)", "REMESSA BANCÁRIA"]:
        FormasDePagamento.objects.get_or_create(forma_pagamento=f)

    for t in ["CONTAS FIXAS", "VERBAS INDENIZATÓRIAS", "IMPOSTOS"]:
        TiposDePagamento.objects.get_or_create(tipo_pagamento=t)

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

    if not Credor.objects.filter(tipo="PJ").exists():
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
            tipo="PJ",
            conta=conta,
            email=_fake_generator.email(),
            telefone=_fake_generator.phone_number()[:20],
            chave_pix=_fake_generator.email(),
        )

    if not Credor.objects.filter(tipo="PF").exists():
        conta = ContasBancarias.objects.first()
        cargo = CargosFuncoes.objects.filter(grupo="FUNCIONÁRIOS").first()
        Credor.objects.create(
            nome=_fake_generator.name(),
            cpf_cnpj=_fake_generator.cpf(),
            tipo="PF",
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
        processo = Processo.objects.create(
            extraorcamentario=random.choice([False, False, False, True]),
            credor=random.choice(credores),
            valor_bruto=valor_bruto,
            valor_liquido=valor_liquido,
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
        _create_fake_documento_orcamentario(
            processo=processo,
            numero_nota_empenho=n_empenho,
            data_empenho=data_empenho,
            ano_exercicio=ano,
        )
        created += 1
    return created


def _create_fake_documentos_fiscais(n, processos):
    """Cria ``n`` documentos fiscais fictícios vinculados aos processos informados."""
    from django.contrib.auth.models import User

    def _get_or_create_fiscal_contrato_fallback():
        grupo_fiscal, _ = Group.objects.get_or_create(name="FISCAL DE CONTRATO")
        fiscal_existente = User.objects.filter(groups=grupo_fiscal, is_active=True).first()
        if fiscal_existente:
            return fiscal_existente

        fiscal, created = User.objects.get_or_create(
            username="fiscal_contrato_fake",
            defaults={
                "email": "fiscal_contrato_fake@example.com",
                "is_active": True,
            },
        )
        if created:
            fiscal.set_password("Teste@123")
            fiscal.save(update_fields=["password"])
        fiscal.groups.add(grupo_fiscal)
        return fiscal

    credores_pj = list(Credor.objects.filter(tipo="PJ"))
    fiscais_contrato = list(User.objects.filter(groups__name="FISCAL DE CONTRATO").distinct())
    fiscais_gerais = list(User.objects.all())
    if not credores_pj:
        credores_pj = list(Credor.objects.all())

    created = 0
    for _ in range(n):
        processo = random.choice(processos)
        emitente = random.choice(credores_pj) if credores_pj else None

        status_nome = (processo.status.opcao_status if processo.status else "").upper()
        em_liquidacao = "LIQUIDA" in status_nome
        if em_liquidacao:
            if not fiscais_contrato:
                fiscais_contrato.append(_get_or_create_fiscal_contrato_fallback())
            fiscal = random.choice(fiscais_contrato)
        else:
            pool_fiscais = fiscais_contrato or fiscais_gerais
            fiscal = random.choice(pool_fiscais) if pool_fiscais else None

        end_date = processo.data_pagamento or date.today()
        start_date = end_date - timedelta(days=180)
        data_emissao = _fake_generator.date_between(start_date=start_date, end_date=end_date)

        base_bruta = processo.valor_bruto or Decimal(str(round(random.uniform(100.00, 50_000.00), 2)))
        fracao = Decimal(str(random.choice(["0.25", "0.33", "0.50", "1.00"])))
        valor_bruto = (base_bruta * fracao).quantize(Decimal("0.01"))
        if valor_bruto <= 0:
            valor_bruto = Decimal("100.00")

        retencao_pct = Decimal(str(round(random.uniform(0, 0.10), 4)))
        valor_liquido = (valor_bruto * (Decimal("1") - retencao_pct)).quantize(Decimal("0.01"))
        if valor_liquido <= 0:
            valor_liquido = Decimal("0.01")

        numero_nota_fiscal = ""
        serie_nota_fiscal = ""
        for _attempt in range(10):
            numero_candidato = f"NF-{_fake_generator.numerify('######')}"
            serie_candidata = _fake_generator.bothify("??#").upper()
            if not DocumentoFiscal.objects.filter(
                processo=processo,
                numero_nota_fiscal=numero_candidato,
                serie_nota_fiscal=serie_candidata,
            ).exists():
                numero_nota_fiscal = numero_candidato
                serie_nota_fiscal = serie_candidata
                break

        if not numero_nota_fiscal:
            numero_nota_fiscal = f"NF-{_fake_generator.numerify('######')}"
            serie_nota_fiscal = _fake_generator.bothify("??#").upper()

        try:
            nota = DocumentoFiscal.objects.create(
                processo=processo,
                nome_emitente=emitente,
                cnpj_emitente=(emitente.cpf_cnpj if emitente else _fake_generator.cnpj()),
                numero_nota_fiscal=numero_nota_fiscal,
                serie_nota_fiscal=serie_nota_fiscal,
                data_emissao=data_emissao,
                valor_bruto=valor_bruto,
                valor_liquido=valor_liquido,
                atestada=True,
            )
            liquidacao, _ = LiquidacaoDocumentoFiscal.objects.get_or_create(documento_fiscal=nota)
            liquidacao.fiscal_contrato = fiscal
            liquidacao.save(update_fields=["fiscal_contrato", "updated_at"])
            _create_fake_pdf_documento_fiscal(processo, numero_nota_fiscal, serie_nota_fiscal)
            created += 1
        except (DjangoValidationError, IntegrityError) as exc:
            logger.warning(
                "evento=erro_geracao_documento_fiscal_fake processo_id=%s numero_nota=%s serie=%s erro=%s",
                getattr(processo, "id", None),
                numero_nota_fiscal,
                serie_nota_fiscal,
                exc,
            )
            continue
    return created


def _create_fake_retencoes(n, notas):
    """Cria ``n`` retenções fictícias vinculadas aos documentos fiscais informados."""
    codigos = list(CodigosImposto.objects.all())
    status_list = list(StatusChoicesRetencoes.objects.all())
    credores = list(Credor.objects.all())

    if not codigos:
        return 0

    created = 0
    for _ in range(n):
        nota = random.choice(notas)
        beneficiario = nota.nome_emitente or (random.choice(credores) if credores else None)
        rendimento = Decimal(str(round(random.uniform(500.00, 30_000.00), 2)))
        codigo = random.choice(codigos)
        aliquota = codigo.aliquota or Decimal("0.015")
        valor = (rendimento * aliquota / 100).quantize(Decimal("0.01"))
        data_pagamento = _fake_generator.date_between(start_date="-1y", end_date="today")
        RetencaoImposto.objects.create(
            nota_fiscal=nota,
            beneficiario=beneficiario,
            codigo=codigo,
            valor=valor,
            rendimento_tributavel=rendimento,
            data_pagamento=data_pagamento,
            status=random.choice(status_list) if status_list else None,
        )
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
        ultima_diaria = (
            Diaria.objects.filter(beneficiario=beneficiario)
            .exclude(data_retorno__isnull=True)
            .order_by("-data_retorno")
            .first()
        )

        if ultima_diaria and ultima_diaria.data_retorno:
            data_saida = ultima_diaria.data_retorno + timedelta(days=random.randint(1, 5))
        else:
            data_saida = _fake_generator.date_between(start_date="-6m", end_date="today")

        dias = random.randint(1, 10)
        data_retorno = data_saida + timedelta(days=dias)
        quantidade = Decimal(str(round(random.uniform(0.5, float(dias)), 1)))

        ano_ref = date.today().year
        prefixo = f"DIA{ano_ref}"
        sequencial = Diaria.objects.filter(numero_siscac__startswith=prefixo).count() + 1
        numero_seq = f"{prefixo}{str(sequencial).zfill(5)}"
        while Diaria.objects.filter(numero_siscac=numero_seq).exists():
            sequencial += 1
            numero_seq = f"{prefixo}{str(sequencial).zfill(5)}"

        processo = random.choice(processos) if processos else None

        try:
            Diaria.objects.create(
                processo=processo,
                numero_siscac=numero_seq,
                beneficiario=beneficiario,
                tipo_solicitacao="INICIAL",
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
        except DjangoValidationError as exc:
            logger.warning(
                "evento=erro_geracao_diaria_fake beneficiario_id=%s numero_siscac=%s erro=%s",
                getattr(beneficiario, "id", None),
                numero_seq,
                exc,
            )
            continue
    return created


@csrf_exempt
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def gerar_dados_fake_view(request):
    """Gera dados fictícios de processos, fiscais, retenções e diárias via formulário."""
    context = {"resultados": None}

    if request.method == "POST":
        try:
            n_processos = max(0, int(request.POST.get("n_processos") or 0))
            n_documentos = max(0, int(request.POST.get("n_documentos") or 0))
            n_retencoes = max(0, int(request.POST.get("n_retencoes") or 0))
            n_diarias = max(0, int(request.POST.get("n_diarias") or 0))
        except (ValueError, TypeError):
            messages.error(request, "Valores inválidos. Use apenas números inteiros.")
            return redirect("gerar_dados_fake")

        _ensure_fake_lookup_tables()
        usuarios_info = _create_or_update_fake_users_with_permissions()

        resultados = {}
        resultados["usuarios_teste"] = usuarios_info["total"]

        messages.success(
            request,
            (
                f"✔ Usuários de teste (total={usuarios_info['total']}, criados={usuarios_info['criados']}, "
                f"atualizados={usuarios_info['atualizados']}) salvos em: {usuarios_info['arquivo']}"
            ),
        )
        if usuarios_info["permissoes_ausentes"]:
            messages.warning(
                request,
                "Permissões ausentes para os usuários de teste: "
                + ", ".join(usuarios_info["permissoes_ausentes"]),
            )

        if n_processos > 0:
            criados = _create_fake_processos(n_processos)
            resultados["processos"] = criados
            if criados:
                messages.success(request, f"✔ {criados} processo(s) criado(s).")
            else:
                messages.warning(request, "Não foi possível criar processos. Verifique se há credores e contas bancárias cadastrados.")

        if n_documentos > 0:
            processos_existentes = list(Processo.objects.all())
            if not processos_existentes:
                messages.warning(
                    request,
                    f"Não há processos cadastrados. Os {n_documentos} documento(s) fiscal(is) não puderam ser gerados. Gere processos primeiro.",
                )
            else:
                criados = _create_fake_documentos_fiscais(n_documentos, processos_existentes)
                resultados["documentos_fiscais"] = criados
                messages.success(request, f"✔ {criados} documento(s) fiscal(is) criado(s).")

        if n_retencoes > 0:
            notas_existentes = list(DocumentoFiscal.objects.all())
            if not notas_existentes:
                messages.warning(
                    request,
                    f"Não há documentos fiscais cadastrados. As {n_retencoes} retenção(ões) não puderam ser geradas. Gere documentos fiscais primeiro.",
                )
            else:
                criados = _create_fake_retencoes(n_retencoes, notas_existentes)
                if criados:
                    resultados["retencoes"] = criados
                    messages.success(request, f"✔ {criados} retenção(ões) criada(s).")
                else:
                    messages.warning(request, "Não foi possível criar retenções. Verifique se há códigos de imposto cadastrados.")

        if n_diarias > 0:
            credores_pf = list(Credor.objects.filter(tipo="PF"))
            if not credores_pf:
                messages.warning(request, f"Não há credores PF cadastrados. As {n_diarias} diária(s) não puderam ser geradas.")
            else:
                processos_existentes = list(Processo.objects.all()) if Processo.objects.exists() else None
                criados = _create_fake_diarias(n_diarias, credores_pf, processos_existentes)
                resultados["diarias"] = criados
                messages.success(request, f"✔ {criados} diária(s) criada(s).")

        context["resultados"] = resultados
        return render(request, "gerar_dados_fake.html", context)

    return render(request, "gerar_dados_fake.html", context)


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def gerar_dummy_pdf_view(request, pk):
    """Gera PDF fictício e anexa ao processo como documento de nota fiscal para testes."""
    from django.utils import timezone as tz
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas

    processo = get_object_or_404(Processo, id=pk)

    tipo_nf = TiposDeDocumento.objects.filter(tipo_documento__iexact="NOTA FISCAL (NF)").first()
    if not tipo_nf:
        tipo_nf = TiposDeDocumento.objects.create(tipo_documento="NOTA FISCAL (NF)")

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

    timestamp = tz.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nota_fiscal_dummy_{timestamp}.pdf"
    ordem = processo.documentos.count() + 1

    doc = Boleto_Bancario(processo=processo, tipo=tipo_nf, ordem=ordem)
    doc.arquivo.save(filename, ContentFile(buffer.getvalue()), save=True)

    messages.success(request, f"PDF de teste gerado e vinculado ao Processo #{processo.id}.")
    return redirect("documentos_fiscais", pk=pk)


def painel_teste_pdfs(request):
    """Renderiza o painel de testes de geração de PDFs."""
    return render(request, "pagamentos/teste_pdfs.html")


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def painel_permissoes_dev_view(request):
    """Renderiza o painel de inspeção de RBAC para depuração operacional."""
    return render(request, "painel_permissoes_dev.html")


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def api_permissoes_dev_view(request):
    """Retorna visão completa de permissões, grupos e usuários para auditoria de acesso."""
    if request.method != "GET":
        return JsonResponse({"sucesso": False, "erro": "Método não permitido."}, status=405)

    UserModel = get_user_model()
    users = list(UserModel.objects.all().prefetch_related("groups", "user_permissions", "groups__permissions"))
    groups = list(Group.objects.all().prefetch_related("permissions", "user_set"))
    permissions = list(
        Permission.objects.all()
        .select_related("content_type")
        .prefetch_related("group_set", "user_set")
        .order_by("content_type__app_label", "codename")
    )

    users_by_id = {user.id: user for user in users}

    user_groups_map = {
        user.id: sorted(
            [{"id": g.id, "name": g.name} for g in user.groups.all()],
            key=lambda item: item["name"],
        )
        for user in users
    }

    users_direct_perms_map = {
        user.id: {
            perm.id for perm in user.user_permissions.all()
        }
        for user in users
    }

    users_via_groups_perms_map = {
        user.id: {
            perm.id for group in user.groups.all() for perm in group.permissions.all()
        }
        for user in users
    }

    groups_users_map = {
        group.id: sorted(
            [
                {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.get_full_name(),
                    "email": user.email,
                    "is_active": user.is_active,
                }
                for user in group.user_set.all()
            ],
            key=lambda item: item["username"],
        )
        for group in groups
    }

    permissions_payload = []
    for perm in permissions:
        group_objs = sorted(
            [
                {"id": group.id, "name": group.name}
                for group in perm.group_set.all()
            ],
            key=lambda item: item["name"],
        )

        direct_users = sorted(
            [
                {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.get_full_name(),
                    "email": user.email,
                    "is_active": user.is_active,
                }
                for user in perm.user_set.all()
            ],
            key=lambda item: item["username"],
        )

        via_groups_user_ids = [
            user.id
            for user in users
            if perm.id in users_via_groups_perms_map.get(user.id, set())
        ]
        via_groups_users = sorted(
            [
                {
                    "id": user_id,
                    "username": users_by_id[user_id].username,
                    "full_name": users_by_id[user_id].get_full_name(),
                    "email": users_by_id[user_id].email,
                    "is_active": users_by_id[user_id].is_active,
                }
                for user_id in via_groups_user_ids
            ],
            key=lambda item: item["username"],
        )

        total_users = {
            item["id"]: item for item in [*direct_users, *via_groups_users]
        }

        permissions_payload.append(
            {
                "id": perm.id,
                "name": perm.name,
                "codename": perm.codename,
                "app_label": perm.content_type.app_label,
                "model": perm.content_type.model,
                "groups": group_objs,
                "users_direct": direct_users,
                "users_via_groups": via_groups_users,
                "users_total": sorted(total_users.values(), key=lambda item: item["username"]),
            }
        )

    groups_payload = []
    for group in groups:
        perms = sorted(
            [
                {
                    "id": perm.id,
                    "name": perm.name,
                    "codename": perm.codename,
                    "app_label": perm.content_type.app_label,
                    "model": perm.content_type.model,
                }
                for perm in group.permissions.all()
            ],
            key=lambda item: (item["app_label"], item["codename"]),
        )
        groups_payload.append(
            {
                "id": group.id,
                "name": group.name,
                "permissions": perms,
                "users": groups_users_map.get(group.id, []),
            }
        )

    users_payload = []
    for user in users:
        direct_perm_ids = users_direct_perms_map.get(user.id, set())
        via_group_perm_ids = users_via_groups_perms_map.get(user.id, set())
        total_perm_ids = sorted(direct_perm_ids.union(via_group_perm_ids))

        direct_permissions = sorted(
            [
                {
                    "id": perm.id,
                    "name": perm.name,
                    "codename": perm.codename,
                    "app_label": perm.content_type.app_label,
                    "model": perm.content_type.model,
                }
                for perm in permissions
                if perm.id in direct_perm_ids
            ],
            key=lambda item: (item["app_label"], item["codename"]),
        )

        group_permissions = sorted(
            [
                {
                    "id": perm.id,
                    "name": perm.name,
                    "codename": perm.codename,
                    "app_label": perm.content_type.app_label,
                    "model": perm.content_type.model,
                }
                for perm in permissions
                if perm.id in via_group_perm_ids
            ],
            key=lambda item: (item["app_label"], item["codename"]),
        )

        total_permissions = sorted(
            [
                {
                    "id": perm.id,
                    "name": perm.name,
                    "codename": perm.codename,
                    "app_label": perm.content_type.app_label,
                    "model": perm.content_type.model,
                }
                for perm in permissions
                if perm.id in total_perm_ids
            ],
            key=lambda item: (item["app_label"], item["codename"]),
        )

        users_payload.append(
            {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name(),
                "email": user.email,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "groups": user_groups_map.get(user.id, []),
                "permissions_direct": direct_permissions,
                "permissions_via_groups": group_permissions,
                "permissions_total": total_permissions,
            }
        )

    resumo = {
        "total_permissions": len(permissions_payload),
        "total_groups": len(groups_payload),
        "total_users": len(users_payload),
        "total_users_active": sum(1 for user in users if user.is_active),
        "total_users_staff": sum(1 for user in users if user.is_staff),
        "total_users_superuser": sum(1 for user in users if user.is_superuser),
    }

    return JsonResponse(
        {
            "sucesso": True,
            "resumo": resumo,
            "permissions": permissions_payload,
            "groups": groups_payload,
            "users": users_payload,
        }
    )


def gerar_pdf_fake_view(request, doc_type):
    """Gera e retorna PDF fictício do tipo informado para validação visual de templates."""

    def mock_credor():
        """Cria objeto credor fictício com dados gerados aleatoriamente."""
        c = MagicMock()
        c.nome = _fake_generator.name()
        c.cpf_cnpj = _fake_generator.cpf()
        c.email = _fake_generator.email()
        c.cargo_funcao = "Analista Administrativo"
        return c

    def mock_user():
        """Cria objeto usuário fictício com nome e username gerados aleatoriamente."""
        u = MagicMock()
        u.get_full_name.return_value = _fake_generator.name()
        u.username = _fake_generator.user_name()
        return u

    if doc_type in ["scd", "pcd"]:
        obj = MagicMock()
        obj.numero_siscac = _fake_generator.numerify(text="2026/####")
        obj.beneficiario = mock_credor()
        obj.proponente = mock_user()
        obj.data_saida = _fake_generator.date_between(start_date="today", end_date="+5d")
        obj.data_retorno = _fake_generator.date_between(start_date="+6d", end_date="+10d")
        obj.cidade_origem = _fake_generator.city()
        obj.cidade_destino = _fake_generator.city()
        obj.objetivo = _fake_generator.paragraph(nb_sentences=2)
        obj.quantidade_diarias = Decimal("2.5")
        obj.valor_total = Decimal(_fake_generator.numerify(text="####.##"))
        obj.meio_de_transporte.nome = "Aéreo"
    elif doc_type in ["autorizacao", "conselho_fiscal", "contabilizacao", "auditoria"]:
        obj = MagicMock()
        obj.id = _fake_generator.random_int(min=1000, max=9999)
        obj.n_nota_empenho = _fake_generator.numerify(text="2026NE####")
        obj.credor = mock_credor()
        obj.valor_liquido = Decimal(_fake_generator.numerify(text="####.##"))
        obj.credor.conta.banco = "Banco do Brasil"
        obj.credor.conta.agencia = "1234-5"
        obj.credor.conta.conta = "98765-4"
        obj.detalhamento = _fake_generator.paragraph(nb_sentences=2)
    elif doc_type == "ateste":
        obj = MagicMock()
        obj.numero = _fake_generator.numerify(text="NF-####")
        obj.numero_nota_fiscal = obj.numero
        obj.valor = Decimal(_fake_generator.numerify(text="####.##"))
        obj.valor_bruto = obj.valor
        obj.processo.id = _fake_generator.random_int(min=1000, max=9999)
        obj.processo.credor = mock_credor()
        obj.liquidacao_atual = MagicMock()
        obj.liquidacao_atual.fiscal_contrato = mock_user()
    elif doc_type.startswith("recibo_"):
        obj = MagicMock()
        if doc_type == "recibo_reembolso":
            obj.__class__.__name__ = "ReembolsoCombustivel"
            obj.data_saida = _fake_generator.date_between(start_date="-5d", end_date="today")
            obj.data_retorno = _fake_generator.date_between(start_date="today", end_date="+5d")
            obj.cidade_origem = _fake_generator.city()
            obj.cidade_destino = _fake_generator.city()
            obj.objetivo = "participação em reunião administrativa"
        elif doc_type == "recibo_auxilio":
            obj.__class__.__name__ = "AuxilioRepresentacao"
            obj.objetivo = "representação institucional em evento setorial"
            obj.data_evento = _fake_generator.date_between(start_date="today", end_date="+15d")
            obj.local_evento = _fake_generator.city()
        elif doc_type == "recibo_jeton":
            obj.__class__.__name__ = "Jeton"
            obj.reuniao = "15ª Sessão"
            obj.data_evento = _fake_generator.date_between(start_date="today", end_date="+15d")
            obj.local_evento = _fake_generator.city()
        elif doc_type == "recibo_suprimento":
            obj.__class__.__name__ = "SuprimentoDeFundos"
            obj.lotacao = "Delegacia Regional de Florianópolis"
            obj.inicio_periodo = _fake_generator.date_between(start_date="today", end_date="+2d")
            obj.fim_periodo = _fake_generator.date_between(start_date="+3d", end_date="+30d")
            obj.data_devolucao_saldo = obj.fim_periodo

        obj.beneficiario = mock_credor()
        obj.suprido = obj.beneficiario
        obj.valor_total = Decimal(_fake_generator.numerify(text="####.##"))
        obj.valor_liquido = obj.valor_total
        obj.valor_aprovado = obj.valor_total
    else:
        return HttpResponse(f"Tipo de documento '{doc_type}' não reconhecido.", status=400)

    kwargs = {"numero_reuniao": _fake_generator.random_int(min=1, max=50)} if doc_type == "conselho_fiscal" else {}

    if doc_type in ["scd", "pcd", "recibo_reembolso", "recibo_auxilio", "recibo_jeton"]:
        registry = VERBAS_DOCUMENT_REGISTRY
    elif doc_type == "recibo_suprimento":
        registry = SUPRIMENTOS_DOCUMENT_REGISTRY
    else:
        registry = FLUXO_DOCUMENT_REGISTRY

    pdf_bytes = gerar_documento_pdf(doc_type, obj, registry, **kwargs)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="teste_{doc_type}.pdf"'
    return response


__all__ = [
    "painel_importacao_view",
    "download_template_csv_credores",
    "download_template_csv_contas",
    "gerar_dados_fake_view",
    "gerar_dummy_pdf_view",
    "painel_teste_pdfs",
    "painel_permissoes_dev_view",
    "api_permissoes_dev_view",
    "gerar_pdf_fake_view",
]
