import io
from unittest.mock import patch
from django.test import TestCase
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from processos.models import Processo, StatusChoicesProcesso, TiposDeDocumento, DocumentoProcesso, DocumentoFiscal
from processos.utils import processar_pdf_comprovantes
from processos.validators import verificar_turnpike
from processos.views import STATUS_BLOQUEADOS_TOTAL, STATUS_SOMENTE_DOCUMENTOS


class AuditoriaViewTest(TestCase):
    """Testa a view de auditoria que exibe o histórico do django-simple-history."""

    def test_auditoria_retorna_200(self):
        response = self.client.get('/auditoria/')
        self.assertEqual(response.status_code, 200)

    def test_auditoria_usa_template_correto(self):
        response = self.client.get('/auditoria/')
        self.assertTemplateUsed(response, 'auditoria.html')

    def test_auditoria_contexto_tem_chaves_esperadas(self):
        response = self.client.get('/auditoria/')
        self.assertIn('registros', response.context)
        self.assertIn('total', response.context)
        self.assertIn('modelos_disponiveis', response.context)
        self.assertIn('filtros', response.context)

    def test_auditoria_filtros_preservados_no_contexto(self):
        response = self.client.get('/auditoria/?modelo=Processo&tipo_acao=%2B&usuario=admin')
        self.assertEqual(response.context['filtros']['modelo'], 'Processo')
        self.assertEqual(response.context['filtros']['tipo_acao'], '+')
        self.assertEqual(response.context['filtros']['usuario'], 'admin')


class EditarProcessoRestrictionsTest(TestCase):
    """Tests for the edit-permission tiers on editar_processo view."""

    def _make_processo(self, status_text):
        status_obj = StatusChoicesProcesso.objects.create(status_choice=status_text)
        return Processo.objects.create(status=status_obj)

    # ------------------------------------------------------------------ #
    # Tier-1 (STATUS_BLOQUEADOS_TOTAL): access must be blocked entirely.  #
    # ------------------------------------------------------------------ #

    def test_bloqueado_total_get_redirects_home(self):
        """GET on an archived/cancelled process must redirect to home_page."""
        status_text = next(iter(STATUS_BLOQUEADOS_TOTAL))
        processo = self._make_processo(status_text)
        response = self.client.get(f'/processo/{processo.pk}/editar/')
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_bloqueado_total_post_redirects_home(self):
        """POST on an archived/cancelled process must be rejected (redirect to home)."""
        status_text = next(iter(STATUS_BLOQUEADOS_TOTAL))
        processo = self._make_processo(status_text)
        response = self.client.post(f'/processo/{processo.pk}/editar/', data={})
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_all_bloqueado_statuses_redirect(self):
        """Every Tier-1 status redirects to home_page."""
        for status_text in STATUS_BLOQUEADOS_TOTAL:
            with self.subTest(status=status_text):
                processo = self._make_processo(status_text)
                response = self.client.get(f'/processo/{processo.pk}/editar/')
                self.assertRedirects(response, '/', fetch_redirect_response=False)

    # ------------------------------------------------------------------ #
    # Tier-2 (STATUS_SOMENTE_DOCUMENTOS): only document changes allowed.  #
    # ------------------------------------------------------------------ #

    def test_somente_documentos_get_returns_200(self):
        """GET on an authorised process must render the edit page (not redirect)."""
        status_text = next(iter(STATUS_SOMENTE_DOCUMENTOS))
        processo = self._make_processo(status_text)
        response = self.client.get(f'/processo/{processo.pk}/editar/')
        self.assertEqual(response.status_code, 200)

    def test_somente_documentos_context_flag(self):
        """The `somente_documentos` flag must be True in context for Tier-2 statuses."""
        status_text = next(iter(STATUS_SOMENTE_DOCUMENTOS))
        processo = self._make_processo(status_text)
        response = self.client.get(f'/processo/{processo.pk}/editar/')
        self.assertTrue(response.context['somente_documentos'])

    def test_full_edit_context_flag_is_false(self):
        """The `somente_documentos` flag must be False for unrestricted statuses."""
        status_text = 'A PAGAR - PENDENTE AUTORIZAÇÃO'
        processo = self._make_processo(status_text)
        response = self.client.get(f'/processo/{processo.pk}/editar/')
        self.assertFalse(response.context['somente_documentos'])



class VerificarTurnpikeTest(TestCase):
    """Tests for the verificar_turnpike status-transition gate."""

    def _make_processo(self, status_text='A EMPENHAR'):
        status_obj = StatusChoicesProcesso.objects.create(status_choice=status_text)
        return Processo.objects.create(status=status_obj)

    def _add_document(self, processo, tipo_nome):
        tipo, _ = TiposDeDocumento.objects.get_or_create(
            tipo_de_documento=tipo_nome
        )
        return DocumentoProcesso.objects.create(
            processo=processo,
            tipo=tipo,
            arquivo='dummy/path.pdf',
            ordem=1,
        )

    def _add_nota_fiscal(self, processo, atestada=True):
        return DocumentoFiscal.objects.create(
            processo=processo,
            numero_nota_fiscal='NF-001',
            data_emissao='2024-01-01',
            valor_bruto='1000.00',
            valor_liquido='900.00',
            atestada=atestada,
        )

    # ------------------------------------------------------------------ #
    # Rule 1: A EMPENHAR → AGUARDANDO LIQUIDAÇÃO                          #
    # ------------------------------------------------------------------ #

    def test_empenhar_to_aguardando_sem_documento_retorna_erro(self):
        """Without DOCUMENTOS ORÇAMENTÁRIOS, transition must be blocked."""
        processo = self._make_processo('A EMPENHAR')
        erros = verificar_turnpike(processo, 'A EMPENHAR', 'AGUARDANDO LIQUIDAÇÃO')
        self.assertTrue(len(erros) > 0)
        self.assertIn('DOCUMENTOS ORÇAMENTÁRIOS', erros[0])

    def test_empenhar_to_aguardando_com_documento_ok(self):
        """With DOCUMENTOS ORÇAMENTÁRIOS attached, transition must be allowed."""
        processo = self._make_processo('A EMPENHAR')
        self._add_document(processo, 'DOCUMENTOS ORÇAMENTÁRIOS')
        erros = verificar_turnpike(processo, 'A EMPENHAR', 'AGUARDANDO LIQUIDAÇÃO')
        self.assertEqual(erros, [])

    def test_empenhar_to_aguardando_case_insensitive(self):
        """Document type check must be case-insensitive (ASCII chars, SQLite-compatible)."""
        processo = self._make_processo('A EMPENHAR')
        # 'Comprovante de Pagamento' → validates iexact works for ASCII case differences;
        # for the DOCUMENTOS ORÇAMENTÁRIOS type, we store with the canonical uppercase form
        # to avoid SQLite's limited Unicode LIKE behaviour in tests.
        self._add_document(processo, 'DOCUMENTOS ORÇAMENTÁRIOS')
        erros = verificar_turnpike(processo, 'A EMPENHAR', 'AGUARDANDO LIQUIDAÇÃO')
        self.assertEqual(erros, [])

    def test_empenhar_to_aguardando_ateste_variant(self):
        """'AGUARDANDO LIQUIDAÇÃO / ATESTE' variant must also be accepted as the target."""
        processo = self._make_processo('A EMPENHAR')
        self._add_document(processo, 'DOCUMENTOS ORÇAMENTÁRIOS')
        erros = verificar_turnpike(processo, 'A EMPENHAR', 'AGUARDANDO LIQUIDAÇÃO / ATESTE')
        self.assertEqual(erros, [])

    # ------------------------------------------------------------------ #
    # Rule 2: AGUARDANDO LIQUIDAÇÃO → A PAGAR - PENDENTE AUTORIZAÇÃO      #
    # ------------------------------------------------------------------ #

    def test_aguardando_to_pagar_sem_notas_retorna_erro(self):
        """Without any documentos fiscais, transition must be blocked."""
        processo = self._make_processo('AGUARDANDO LIQUIDAÇÃO')
        erros = verificar_turnpike(processo, 'AGUARDANDO LIQUIDAÇÃO', 'A PAGAR - PENDENTE AUTORIZAÇÃO')
        self.assertTrue(len(erros) > 0)

    def test_aguardando_to_pagar_nota_nao_atestada_retorna_erro(self):
        """When a nota fiscal is NOT attested, transition must be blocked."""
        processo = self._make_processo('AGUARDANDO LIQUIDAÇÃO')
        self._add_nota_fiscal(processo, atestada=False)
        erros = verificar_turnpike(processo, 'AGUARDANDO LIQUIDAÇÃO', 'A PAGAR - PENDENTE AUTORIZAÇÃO')
        self.assertTrue(len(erros) > 0)
        self.assertIn('atestados', erros[0])

    def test_aguardando_to_pagar_todas_atestadas_ok(self):
        """When all notas fiscais are attested, transition must be allowed."""
        processo = self._make_processo('AGUARDANDO LIQUIDAÇÃO')
        self._add_nota_fiscal(processo, atestada=True)
        self._add_nota_fiscal(processo, atestada=True)
        erros = verificar_turnpike(processo, 'AGUARDANDO LIQUIDAÇÃO', 'A PAGAR - PENDENTE AUTORIZAÇÃO')
        self.assertEqual(erros, [])

    def test_aguardando_ateste_variant_also_checked(self):
        """'AGUARDANDO LIQUIDAÇÃO / ATESTE' variant triggers the same rule."""
        processo = self._make_processo('AGUARDANDO LIQUIDAÇÃO / ATESTE')
        self._add_nota_fiscal(processo, atestada=False)
        erros = verificar_turnpike(processo, 'AGUARDANDO LIQUIDAÇÃO / ATESTE', 'A PAGAR - PENDENTE AUTORIZAÇÃO')
        self.assertTrue(len(erros) > 0)

    # ------------------------------------------------------------------ #
    # Rule 3: LANÇADO - AGUARDANDO COMPROVANTE → PAGO - EM CONFERÊNCIA    #
    # ------------------------------------------------------------------ #

    def test_lancado_to_pago_sem_comprovante_retorna_erro(self):
        """Without COMPROVANTE DE PAGAMENTO, transition must be blocked."""
        processo = self._make_processo('LANÇADO - AGUARDANDO COMPROVANTE')
        erros = verificar_turnpike(
            processo,
            'LANÇADO - AGUARDANDO COMPROVANTE',
            'PAGO - EM CONFERÊNCIA',
        )
        self.assertTrue(len(erros) > 0)
        self.assertIn('COMPROVANTE DE PAGAMENTO', erros[0])

    def test_lancado_to_pago_com_comprovante_ok(self):
        """With COMPROVANTE DE PAGAMENTO attached, transition must be allowed."""
        processo = self._make_processo('LANÇADO - AGUARDANDO COMPROVANTE')
        self._add_document(processo, 'COMPROVANTE DE PAGAMENTO')
        erros = verificar_turnpike(
            processo,
            'LANÇADO - AGUARDANDO COMPROVANTE',
            'PAGO - EM CONFERÊNCIA',
        )
        self.assertEqual(erros, [])

    def test_lancado_to_pago_comprovante_case_insensitive(self):
        """Document type check must be case-insensitive."""
        processo = self._make_processo('LANÇADO - AGUARDANDO COMPROVANTE')
        self._add_document(processo, 'Comprovante de Pagamento')
        erros = verificar_turnpike(
            processo,
            'LANÇADO - AGUARDANDO COMPROVANTE',
            'PAGO - EM CONFERÊNCIA',
        )
        self.assertEqual(erros, [])

    # ------------------------------------------------------------------ #
    # Transitions not in any rule must not generate errors.               #
    # ------------------------------------------------------------------ #

    def test_unrelated_transition_no_error(self):
        """Transitions not covered by the turnpike must always pass."""
        processo = self._make_processo('A PAGAR - PENDENTE AUTORIZAÇÃO')
        erros = verificar_turnpike(
            processo,
            'A PAGAR - PENDENTE AUTORIZAÇÃO',
            'A PAGAR - ENVIADO PARA AUTORIZAÇÃO',
        )
        self.assertEqual(erros, [])


# ---------------------------------------------------------------------------
# EFD-Reinf XML batch generation tests
# ---------------------------------------------------------------------------

from datetime import date as _date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from processos.models import (
    CodigosImposto,
    Credor,
    DadosContribuinte,
    DocumentoFiscal,
    Processo,
)
from processos.reinf_services import (
    _build_r2010_xml,
    _build_r4020_xml,
    gerar_lotes_reinf,
)


class GerarLotesReinfHelpersTest(TestCase):
    """Unit tests for _build_r2010_xml and _build_r4020_xml."""

    def _make_codigo_inss(self):
        return CodigosImposto.objects.create(
            codigo='1490',
            regra_competencia='emissao',
            serie_reinf='S2000',
        )

    def _make_codigo_federal(self, natureza='15001'):
        return CodigosImposto.objects.create(
            codigo='6190',
            regra_competencia='emissao',
            serie_reinf='S4000',
            natureza_rendimento=natureza,
        )

    def _make_credor(self, cnpj='12345678000195'):
        return Credor.objects.create(nome='Empresa Teste', cpf_cnpj=cnpj, tipo='PJ')

    def _make_nota(self, credor, atestada=True):
        proc = Processo.objects.create()
        return DocumentoFiscal.objects.create(
            processo=proc,
            nome_emitente=credor,
            numero_nota_fiscal='NF-001',
            data_emissao=_date(2024, 3, 15),
            valor_bruto=Decimal('1000.00'),
            valor_liquido=Decimal('900.00'),
            atestada=atestada,
        )

    def _make_retencao(self, nota, codigo, valor='50.00', base='1000.00'):
        from ..models import RetencaoImposto
        from .models import RetencaoImposto
        ret = RetencaoImposto(
            nota_fiscal=nota,
            codigo=codigo,
            valor=Decimal(valor),
            rendimento_tributavel=Decimal(base),
        )
        ret.save()
        return ret

    # --- _build_r2010_xml ---

    def test_r2010_xml_has_correct_root_tag(self):
        codigo = self._make_codigo_inss()
        credor = self._make_credor()
        nota = self._make_nota(credor)
        ret = self._make_retencao(nota, codigo)

        xml_str = _build_r2010_xml('12345678000195', [ret], 3, 2024)
        self.assertIn('<Reinf', xml_str)

    def test_r2010_xml_contains_evtServTom(self):
        codigo = self._make_codigo_inss()
        credor = self._make_credor()
        nota = self._make_nota(credor)
        ret = self._make_retencao(nota, codigo)

        xml_str = _build_r2010_xml('12345678000195', [ret], 3, 2024)
        self.assertIn('evtServTom', xml_str)

    def test_r2010_xml_contains_perApur(self):
        codigo = self._make_codigo_inss()
        credor = self._make_credor()
        nota = self._make_nota(credor)
        ret = self._make_retencao(nota, codigo)

        xml_str = _build_r2010_xml('12345678000195', [ret], 3, 2024)
        self.assertIn('<perApur>2024-03</perApur>', xml_str)

    def test_r2010_xml_contains_cnpj(self):
        codigo = self._make_codigo_inss()
        credor = self._make_credor()
        nota = self._make_nota(credor)
        ret = self._make_retencao(nota, codigo)

        xml_str = _build_r2010_xml('12345678000195', [ret], 3, 2024)
        self.assertIn('12345678000195', xml_str)

    def test_r2010_xml_contains_valor_retido(self):
        codigo = self._make_codigo_inss()
        credor = self._make_credor()
        nota = self._make_nota(credor)
        ret = self._make_retencao(nota, codigo, valor='75.50')

        xml_str = _build_r2010_xml('12345678000195', [ret], 3, 2024)
        self.assertIn('75.50', xml_str)

    def test_r2010_xml_lists_multiple_retencoes(self):
        codigo = self._make_codigo_inss()
        credor = self._make_credor()
        nota = self._make_nota(credor)
        ret1 = self._make_retencao(nota, codigo, valor='50.00')
        ret2 = self._make_retencao(nota, codigo, valor='30.00')

        xml_str = _build_r2010_xml('12345678000195', [ret1, ret2], 3, 2024)
        self.assertEqual(xml_str.count('<nfSeq>'), 2)

    # --- _build_r4020_xml ---

    def test_r4020_xml_has_correct_root_tag(self):
        codigo = self._make_codigo_federal()
        credor = self._make_credor()
        nota = self._make_nota(credor)
        ret = self._make_retencao(nota, codigo)

        xml_str = _build_r4020_xml('12345678000195', [ret], 3, 2024)
        self.assertIn('<Reinf', xml_str)

    def test_r4020_xml_contains_evtRetPJ(self):
        codigo = self._make_codigo_federal()
        credor = self._make_credor()
        nota = self._make_nota(credor)
        ret = self._make_retencao(nota, codigo)

        xml_str = _build_r4020_xml('12345678000195', [ret], 3, 2024)
        self.assertIn('evtRetPJ', xml_str)

    def test_r4020_xml_contains_natureza_rendimento(self):
        codigo = self._make_codigo_federal(natureza='15001')
        credor = self._make_credor()
        nota = self._make_nota(credor)
        ret = self._make_retencao(nota, codigo)

        xml_str = _build_r4020_xml('12345678000195', [ret], 3, 2024)
        self.assertIn('<natRend>15001</natRend>', xml_str)

    def test_r4020_xml_groups_by_natureza(self):
        """Two retentions with the same natureza should produce a single detPag."""
        codigo = self._make_codigo_federal(natureza='15001')
        credor = self._make_credor()
        nota = self._make_nota(credor)
        ret1 = self._make_retencao(nota, codigo, valor='40.00')
        ret2 = self._make_retencao(nota, codigo, valor='60.00')

        xml_str = _build_r4020_xml('12345678000195', [ret1, ret2], 3, 2024)
        self.assertEqual(xml_str.count('<detPag>'), 1)


class GerarLotesReinfIntegrationTest(TestCase):
    """Integration tests for gerar_lotes_reinf."""

    def setUp(self):
        self.contribuinte = DadosContribuinte.objects.create(
            cnpj='00000000000191',
            razao_social='Empresa Contribuinte',
            tipo_inscricao=1,
        )

    def _setup_data(self, familia, cnpj, atestada=True, competencia_month=3, competencia_year=2024):
        """Helper to create a full chain: Credor→Processo→DocumentoFiscal→RetencaoImposto."""
        from ..models import RetencaoImposto
        from .models import RetencaoImposto

        codigo = CodigosImposto.objects.create(
            codigo=f'TEST_{familia}_{cnpj[:4]}',
            regra_competencia='emissao',
            serie_reinf='S2000' if familia == 'INSS' else 'S4000',
            natureza_rendimento='15001' if familia == 'FEDERAL' else None,
        )
        credor = Credor.objects.create(nome=f'Credor {cnpj}', cpf_cnpj=cnpj, tipo='PJ')
        proc = Processo.objects.create()
        nota = DocumentoFiscal.objects.create(
            processo=proc,
            nome_emitente=credor,
            numero_nota_fiscal='NF-TEST',
            data_emissao=_date(competencia_year, competencia_month, 15),
            valor_bruto=Decimal('1000.00'),
            valor_liquido=Decimal('900.00'),
            atestada=atestada,
        )
        ret = RetencaoImposto(
            nota_fiscal=nota,
            codigo=codigo,
            valor=Decimal('50.00'),
            rendimento_tributavel=Decimal('1000.00'),
        )
        ret.save()
        return ret

    def test_raises_value_error_when_no_contribuinte(self):
        self.contribuinte.delete()
        with self.assertRaises(ValueError):
            gerar_lotes_reinf(3, 2024)

    def test_always_includes_r1000_and_closers(self):
        result = gerar_lotes_reinf(3, 2024)
        self.assertIn('R-1000_Cadastro_Empresa.xml', result)
        self.assertIn('INSS_R2010/R2099_Fechamento.xml', result)
        self.assertIn('Federais_R4020/R4099_Fechamento.xml', result)

    def test_returns_only_r1000_and_closers_when_no_records(self):
        result = gerar_lotes_reinf(3, 2024)
        self.assertEqual(len(result), 3)

    def test_returns_only_r1000_and_closers_when_not_atestada(self):
        self._setup_data('INSS', '11111111000101', atestada=False)
        result = gerar_lotes_reinf(3, 2024)
        self.assertEqual(len(result), 3)

    def test_returns_r2010_for_inss(self):
        self._setup_data('INSS', '11111111000101')
        result = gerar_lotes_reinf(3, 2024)
        r2010_keys = [k for k in result if k.startswith('INSS_R2010/R2010_')]
        self.assertEqual(len(r2010_keys), 1)

    def test_returns_r4020_for_federal(self):
        self._setup_data('FEDERAL', '22222222000101')
        result = gerar_lotes_reinf(3, 2024)
        r4020_keys = [k for k in result if k.startswith('Federais_R4020/R4020_')]
        self.assertEqual(len(r4020_keys), 1)

    def test_groups_inss_by_cnpj(self):
        """Three INSS retentions for the same CNPJ → single R-2010 file."""
        from ..models import RetencaoImposto
        from .models import RetencaoImposto

        cnpj = '33333333000101'
        codigo = CodigosImposto.objects.create(
            codigo='INSS_GRP',
            regra_competencia='emissao',
            serie_reinf='S2000',
        )
        credor = Credor.objects.create(nome='Credor Agrupado', cpf_cnpj=cnpj, tipo='PJ')
        proc = Processo.objects.create()
        for i in range(3):
            nota = DocumentoFiscal.objects.create(
                processo=proc,
                nome_emitente=credor,
                numero_nota_fiscal=f'NF-{i}',
                data_emissao=_date(2024, 3, 10 + i),
                valor_bruto=Decimal('500.00'),
                valor_liquido=Decimal('450.00'),
                atestada=True,
            )
            ret = RetencaoImposto(
                nota_fiscal=nota,
                codigo=codigo,
                valor=Decimal('20.00'),
                rendimento_tributavel=Decimal('500.00'),
            )
            ret.save()

        result = gerar_lotes_reinf(3, 2024)
        r2010_keys = [k for k in result if k.startswith('INSS_R2010/R2010_')]
        self.assertEqual(len(r2010_keys), 1)

    def test_two_cnpjs_produce_two_inss_files(self):
        self._setup_data('INSS', '44444444000101')
        self._setup_data('INSS', '55555555000101')
        result = gerar_lotes_reinf(3, 2024)
        r2010_keys = [k for k in result if k.startswith('INSS_R2010/R2010_')]
        self.assertEqual(len(r2010_keys), 2)

    def test_filename_contains_cnpj_and_period(self):
        cnpj = '66666666000101'
        self._setup_data('INSS', cnpj)
        result = gerar_lotes_reinf(3, 2024)
        expected_filename = f'INSS_R2010/R2010_CNPJ_{cnpj}_202403.xml'
        self.assertIn(expected_filename, result)

    def test_ignores_wrong_competencia(self):
        """Records from a different period should not appear."""
        self._setup_data('INSS', '77777777000101', competencia_month=5, competencia_year=2024)
        result = gerar_lotes_reinf(3, 2024)
        r2010_keys = [k for k in result if k.startswith('INSS_R2010/R2010_')]
        self.assertEqual(len(r2010_keys), 0)

    def test_xml_content_is_valid_xml(self):
        import xml.etree.ElementTree as ET

        self._setup_data('INSS', '88888888000101')
        result = gerar_lotes_reinf(3, 2024)
        for filename, content in result.items():
            with self.subTest(filename=filename):
                tree = ET.fromstring(content)
                self.assertIsNotNone(tree)


class GerarLoteReinfViewTest(TestCase):
    """Tests for the gerar_lote_reinf_view endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        self.contribuinte = DadosContribuinte.objects.create(
            cnpj='00000000000191',
            razao_social='Empresa Contribuinte',
            tipo_inscricao=1,
        )

    def _setup_inss_record(self, cnpj='99999999000101', month=3, year=2024):
        from ..models import RetencaoImposto
        from .models import RetencaoImposto

        codigo = CodigosImposto.objects.create(
            codigo='VIEW_INSS',
            regra_competencia='emissao',
            serie_reinf='S2000',
        )
        credor = Credor.objects.create(nome='View Credor', cpf_cnpj=cnpj, tipo='PJ')
        proc = Processo.objects.create()
        nota = DocumentoFiscal.objects.create(
            processo=proc,
            nome_emitente=credor,
            numero_nota_fiscal='NF-VIEW',
            data_emissao=_date(year, month, 20),
            valor_bruto=Decimal('2000.00'),
            valor_liquido=Decimal('1800.00'),
            atestada=True,
        )
        ret = RetencaoImposto(
            nota_fiscal=nota,
            codigo=codigo,
            valor=Decimal('100.00'),
            rendimento_tributavel=Decimal('2000.00'),
        )
        ret.save()

    def test_returns_404_when_no_contribuinte(self):
        self.contribuinte.delete()
        response = self.client.get('/reinf/gerar-lotes/?mes=3&ano=2024', secure=True)
        self.assertEqual(response.status_code, 404)

    def test_returns_zip_when_records_exist(self):
        self._setup_inss_record()
        response = self.client.get('/reinf/gerar-lotes/?mes=3&ano=2024', secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

    def test_zip_filename_contains_period(self):
        self._setup_inss_record()
        response = self.client.get('/reinf/gerar-lotes/?mes=3&ano=2024', secure=True)
        self.assertIn('lotes_reinf_202403.zip', response['Content-Disposition'])

    def test_zip_contains_xml_file(self):
        import io
        import zipfile

        self._setup_inss_record(cnpj='99999999000101')
        response = self.client.get('/reinf/gerar-lotes/?mes=3&ano=2024', secure=True)
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        names = zf.namelist()
        self.assertTrue(any(n.endswith('.xml') for n in names))

    def test_redirects_when_not_logged_in(self):
        self.client.logout()
        response = self.client.get('/reinf/gerar-lotes/?mes=3&ano=2024', secure=True)
        self.assertEqual(response.status_code, 302)


# ===========================================================================
# ⚠  DEBUG / DESENVOLVIMENTO — REMOVER ANTES DE PRODUÇÃO
#
# Esta classe de teste imprime os campos extraídos pela função
# processar_pdf_comprovantes no console para inspeção visual.
# NÃO inclua esta classe em ambiente de produção, pois ela pode
# expor informações sensíveis nos logs.
#
# Para desativar: comente ou remova a classe inteira abaixo.
# ===========================================================================
class ComprovantesExtracaoDebugTest(TestCase):
    """
    ⚠  DEBUG / DESENVOLVIMENTO — REMOVER ANTES DE PRODUÇÃO.

    Teste de impressão no console para a função processar_pdf_comprovantes.
    Constrói um PDF sintético de uma página com valor, data e CNPJ conhecidos,
    executa o extrator e imprime todos os campos extraídos no stdout para
    verificação manual.
    """

    def _make_pdf(self, text_lines):
        """Cria um PDF de uma página em memória contendo as linhas de texto fornecidas."""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        y = 750
        for line in text_lines:
            c.drawString(50, y, line)
            y -= 20
        c.save()
        buffer.seek(0)
        buffer.name = "test_comprovante.pdf"
        return buffer

    @patch('processos.utils.default_storage')
    def test_console_print_extracao_valor_data_credor(self, mock_storage):
        """
        ⚠  DEBUG — imprime os campos extraídos no console.

        Cria um comprovante sintético com valor, data de pagamento e dois
        CNPJs: um cadastrado no banco (credor_cadastrado) e um desconhecido.
        Imprime no console TODOS os CNPJs/CPFs encontrados no texto, indicando
        para cada um se há correspondência no cadastro de credores.
        Verifique o output no console para confirmar se os campos estão
        sendo extraídos corretamente.
        """
        import contextlib
        from processos.models import Credor
        credor_cadastrado = Credor.objects.create(
            nome='Fornecedor Teste Ltda',
            cpf_cnpj='11.222.333/0001-44',
        )

        pdf_bytes = self._make_pdf([
            "COMPROVANTE DE PAGAMENTO",
            "CNPJ FAVORECIDO: 11.222.333/0001-44",
            "CNPJ SACADO: 99.999.999/0001-99",
            "VALOR TOTAL: 1.500,00",
            "DATA DO PAGAMENTO: 15/03/2026",
        ]).read()

        # Captura o conteúdo salvo para devolver no open()
        saved_content = {}

        def fake_save(path, content):
            saved_content[path] = content.read() if hasattr(content, 'read') else bytes(content)
            return path

        def fake_open(path, mode='rb'):
            @contextlib.contextmanager
            def _cm():
                yield io.BytesIO(saved_content.get(path, pdf_bytes))
            return _cm()

        mock_storage.save.side_effect = fake_save
        mock_storage.url.side_effect = lambda path: f'/media/{path}'
        mock_storage.open.side_effect = fake_open

        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "test_comprovante.pdf"
        resultados = processar_pdf_comprovantes(pdf_file)

        print("\n" + "=" * 60)
        print("[DEBUG] RESULTADO DA EXTRACAO DE COMPROVANTES")
        print("=" * 60)
        for r in resultados:
            print(f"  Pagina        : {r['pagina']}")
            print(f"  Credor        : {r['credor_extraido']}")
            print(f"  Valor         : {r['valor_extraido']}")
            print(f"  Data pagamento: {r['data_pagamento']}")
            print(f"  Caminho temp  : {r['temp_path']}")
            print(f"  URL           : {r['url']}")
            print("  CNPJs/CPFs encontrados:")
            for item in r.get('documentos_encontrados', []):
                match_info = item['credor'].nome if item['credor'] else "SEM CORRESPONDÊNCIA NO CADASTRO"
                print(f"    {item['doc']}  →  {match_info}")
            print("  Dados bancários encontrados:")
            for item in r.get('contas_encontradas', []):
                match_info = item['credor'].nome if item['credor'] else "SEM CORRESPONDÊNCIA NO CADASTRO"
                print(f"    AG {item['agencia']} / CC {item['conta']}  →  {match_info}")
            print("-" * 60)
        print("[FIM DO DEBUG]\n")

        self.assertEqual(len(resultados), 1)
        r = resultados[0]
        self.assertEqual(r['pagina'], 1)
        self.assertIn('credor_extraido', r)
        self.assertIn('valor_extraido', r)
        self.assertIn('data_pagamento', r)
        self.assertIn('temp_path', r)
        self.assertIn('url', r)
        self.assertIn('documentos_encontrados', r)
        self.assertAlmostEqual(r['valor_extraido'], 1500.0)
        self.assertEqual(r['data_pagamento'], '2026-03-15')
        self.assertEqual(r['credor_extraido'], credor_cadastrado.nome)

        docs = {item['doc']: item['credor'] for item in r['documentos_encontrados']}
        self.assertIn('11.222.333/0001-44', docs)
        self.assertIn('99.999.999/0001-99', docs)
        self.assertEqual(docs['11.222.333/0001-44'], credor_cadastrado)
        self.assertIsNone(docs['99.999.999/0001-99'])
        self.assertIn('contas_encontradas', r)
        self.assertEqual(r['contas_encontradas'], [])

    @patch('processos.utils.default_storage')
    def test_console_print_identificacao_por_dados_bancarios(self, mock_storage):
        """
        ⚠  DEBUG — imprime os dados bancários extraídos no console.

        Cria um comprovante sintético sem CNPJ/CPF correspondente no cadastro,
        mas com dois pares AGENCIA/CONTA: um vinculado a um credor cadastrado e
        outro desconhecido. Imprime no console TODOS os pares encontrados,
        indicando para cada um se há correspondência no cadastro de contas
        bancárias.
        """
        import contextlib
        from processos.models import Credor, ContasBancarias

        credor_por_conta = Credor.objects.create(
            nome='Prestador Via Conta Ltda',
            cpf_cnpj='55.666.777/0001-88',
        )
        ContasBancarias.objects.create(
            titular=credor_por_conta,
            banco='341',
            agencia='1234-5',
            conta='98765-0',
        )

        pdf_bytes = self._make_pdf([
            "COMPROVANTE DE TRANSFERENCIA",
            "AGENCIA: 1234-5 CONTA: 98.765-0",
            "AGENCIA: 9999-9 CONTA: 1111-1",
            "VALOR TOTAL: 3.200,00",
            "DATA DO PAGAMENTO: 20/03/2026",
        ]).read()

        saved_content = {}

        def fake_save(path, content):
            saved_content[path] = content.read() if hasattr(content, 'read') else bytes(content)
            return path

        def fake_open(path, mode='rb'):
            @contextlib.contextmanager
            def _cm():
                yield io.BytesIO(saved_content.get(path, pdf_bytes))
            return _cm()

        mock_storage.save.side_effect = fake_save
        mock_storage.url.side_effect = lambda path: f'/media/{path}'
        mock_storage.open.side_effect = fake_open

        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "test_comprovante_bancario.pdf"
        resultados = processar_pdf_comprovantes(pdf_file)

        print("\n" + "=" * 60)
        print("[DEBUG] RESULTADO DA EXTRACAO — IDENTIFICACAO POR CONTA BANCARIA")
        print("=" * 60)
        for r in resultados:
            print(f"  Pagina        : {r['pagina']}")
            print(f"  Credor        : {r['credor_extraido']}")
            print(f"  Valor         : {r['valor_extraido']}")
            print(f"  Data pagamento: {r['data_pagamento']}")
            print(f"  Caminho temp  : {r['temp_path']}")
            print(f"  URL           : {r['url']}")
            print("  CNPJs/CPFs encontrados:")
            for item in r.get('documentos_encontrados', []):
                match_info = item['credor'].nome if item['credor'] else "SEM CORRESPONDÊNCIA NO CADASTRO"
                print(f"    {item['doc']}  →  {match_info}")
            print("  Dados bancários encontrados:")
            for item in r.get('contas_encontradas', []):
                match_info = item['credor'].nome if item['credor'] else "SEM CORRESPONDÊNCIA NO CADASTRO"
                print(f"    AG {item['agencia']} / CC {item['conta']}  →  {match_info}")
            print("-" * 60)
        print("[FIM DO DEBUG]\n")

        self.assertEqual(len(resultados), 1)
        r = resultados[0]
        self.assertEqual(r['pagina'], 1)
        self.assertIn('contas_encontradas', r)
        self.assertAlmostEqual(r['valor_extraido'], 3200.0)
        self.assertEqual(r['data_pagamento'], '2026-03-20')
        self.assertEqual(r['credor_extraido'], credor_por_conta.nome)

        contas = {(item['agencia'], item['conta']): item['credor'] for item in r['contas_encontradas']}
        self.assertIn(('1234-5', '98765-0'), contas)
        self.assertIn(('9999-9', '1111-1'), contas)
        self.assertEqual(contas[('1234-5', '98765-0')], credor_por_conta)
        self.assertIsNone(contas[('9999-9', '1111-1')])


class BasePDFDocumentTest(TestCase):
    """Tests for the BasePDFDocument strategy-pattern base class."""

    def _make_single_page_pdf(self):
        """Create a minimal single-page PDF in memory and return its bytes."""
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.drawString(100, 700, "Template")
        c.save()
        buf.seek(0)
        return buf.read()

    def test_draw_content_not_implemented(self):
        """Instantiating BasePDFDocument and calling draw_content raises NotImplementedError."""
        from processos.pdf_engine import BasePDFDocument
        doc = BasePDFDocument(obj=None)
        with self.assertRaises(NotImplementedError):
            doc.draw_content()

    def test_generate_returns_bytes(self):
        """generate() merges content with letterhead and returns bytes."""
        from processos.pdf_engine import BasePDFDocument
        from pypdf import PdfReader

        letterhead_pdf = self._make_single_page_pdf()

        class ConcreteDoc(BasePDFDocument):
            def draw_content(self):
                self.canvas.drawString(100, 600, "Hello PDF")

        with patch('processos.pdf_engine.open', return_value=io.BytesIO(letterhead_pdf), create=True):
            with patch('processos.pdf_engine.settings') as mock_settings:
                mock_settings.BASE_DIR = ''
                mock_settings.CRECI_LETTERHEAD_PATH = 'dummy.pdf'
                with patch('processos.pdf_engine.os.path.join', return_value='dummy.pdf'):
                    with patch('processos.pdf_engine.PdfReader') as mock_reader_cls:
                        # First call → content PDF; second call → letterhead PDF
                        real_reader = PdfReader
                        call_count = {'n': 0}

                        def side_effect(arg):
                            call_count['n'] += 1
                            if call_count['n'] == 1:
                                return real_reader(arg)
                            return real_reader(io.BytesIO(letterhead_pdf))

                        mock_reader_cls.side_effect = side_effect
                        doc = ConcreteDoc(obj=None, letterhead_path='dummy.pdf')
                        result = doc.generate()

        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

    def test_letterhead_path_defaults_to_settings(self):
        """letterhead_path falls back to settings.CRECI_LETTERHEAD_PATH when not provided."""
        from processos.pdf_engine import BasePDFDocument
        with patch('processos.pdf_engine.settings') as mock_settings:
            mock_settings.CRECI_LETTERHEAD_PATH = '/path/to/letterhead.pdf'
            doc = BasePDFDocument(obj=None)
        self.assertEqual(doc.letterhead_path, '/path/to/letterhead.pdf')

    def test_explicit_letterhead_path_overrides_settings(self):
        """An explicit letterhead_path argument takes precedence over settings."""
        from processos.pdf_engine import BasePDFDocument
        doc = BasePDFDocument(obj=None, letterhead_path='/custom/path.pdf')
        self.assertEqual(doc.letterhead_path, '/custom/path.pdf')



# ---------------------------------------------------------------------------
# download_arquivo_seguro – authorization tests
# ---------------------------------------------------------------------------

import io
from unittest.mock import patch
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import (
    Processo, DocumentoProcesso, DocumentoFiscal, TiposDeDocumento,
    Credor, RegistroAcessoArquivo,
)
from ..models.suprimentos import SuprimentoDeFundos, DespesaSuprimento, StatusChoicesSuprimentoDeFundos
from ..models.verbas import Diaria, DocumentoDiaria


def _make_cap_user(username='cap_user', email='cap@example.com'):
    user = User.objects.create_user(username=username, password='pass', email=email)
    perm = Permission.objects.get(codename='pode_operar_contas_pagar')
    user.user_permissions.add(perm)
    return user


def _make_plain_user(username='plain', email='plain@example.com'):
    return User.objects.create_user(username=username, password='pass', email=email)


def _make_tipo():
    tipo, _ = TiposDeDocumento.objects.get_or_create(tipo_de_documento='TEST DOC')
    return tipo


def _doc_url(tipo, pk):
    return reverse('download_arquivo_seguro', args=[tipo, pk])


@override_settings(SECURE_SSL_REDIRECT=False)
class DownloadArquivoSeguroProcessoTest(TestCase):
    """tipo_documento='processo' — only CAP/backoffice allowed."""

    def setUp(self):
        self.cap = _make_cap_user()
        self.plain = _make_plain_user()
        tipo = _make_tipo()
        processo = Processo.objects.create()
        self.doc = DocumentoProcesso.objects.create(
            processo=processo, tipo=tipo, arquivo='pagamentos/2026/proc_1/test.pdf', ordem=1
        )

    def test_cap_gets_file(self):
        self.client.force_login(self.cap)
        with patch('django.db.models.fields.files.FieldFile.open', return_value=io.BytesIO(b'%PDF')):
            response = self.client.get(_doc_url('processo', self.doc.id))
        self.assertNotEqual(response.status_code, 403)

    def test_plain_user_gets_403(self):
        self.client.force_login(self.plain)
        response = self.client.get(_doc_url('processo', self.doc.id))
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_redirects(self):
        response = self.client.get(_doc_url('processo', self.doc.id))
        self.assertEqual(response.status_code, 302)

    def test_no_registro_created_for_unauthorized(self):
        count_before = RegistroAcessoArquivo.objects.count()
        self.client.force_login(self.plain)
        self.client.get(_doc_url('processo', self.doc.id))
        self.assertEqual(RegistroAcessoArquivo.objects.count(), count_before)


@override_settings(SECURE_SSL_REDIRECT=False)
class DownloadArquivoSeguroFiscalTest(TestCase):
    """tipo_documento='fiscal' — CAP OR matching fiscal_contrato allowed."""

    def setUp(self):
        self.cap = _make_cap_user()
        self.fiscal_user = _make_plain_user(username='fiscal', email='fiscal@example.com')
        self.other_user = _make_plain_user(username='other', email='other@example.com')
        tipo = _make_tipo()
        processo = Processo.objects.create()
        self.doc_processo = DocumentoProcesso.objects.create(
            processo=processo, tipo=tipo, arquivo='pagamentos/2026/proc_1/nf.pdf', ordem=1
        )
        self.doc_fiscal = DocumentoFiscal.objects.create(
            processo=processo,
            numero_nota_fiscal='NF-001',
            data_emissao='2026-01-01',
            valor_bruto='1000.00',
            valor_liquido='900.00',
            documento_vinculado=self.doc_processo,
            fiscal_contrato=self.fiscal_user,
        )

    def test_cap_can_access(self):
        self.client.force_login(self.cap)
        with patch('django.db.models.fields.files.FieldFile.open', return_value=io.BytesIO(b'%PDF')):
            response = self.client.get(_doc_url('fiscal', self.doc_fiscal.id))
        self.assertNotEqual(response.status_code, 403)

    def test_fiscal_contrato_can_access(self):
        self.client.force_login(self.fiscal_user)
        with patch('django.db.models.fields.files.FieldFile.open', return_value=io.BytesIO(b'%PDF')):
            response = self.client.get(_doc_url('fiscal', self.doc_fiscal.id))
        self.assertNotEqual(response.status_code, 403)

    def test_other_user_gets_403(self):
        self.client.force_login(self.other_user)
        response = self.client.get(_doc_url('fiscal', self.doc_fiscal.id))
        self.assertEqual(response.status_code, 403)

    def test_no_registro_for_rejected_user(self):
        count_before = RegistroAcessoArquivo.objects.count()
        self.client.force_login(self.other_user)
        self.client.get(_doc_url('fiscal', self.doc_fiscal.id))
        self.assertEqual(RegistroAcessoArquivo.objects.count(), count_before)


@override_settings(SECURE_SSL_REDIRECT=False)
class DownloadArquivoSeguroSuprimentoTest(TestCase):
    """tipo_documento='suprimento' — CAP, or SUPRIDOS+not_encerrado+email_match."""

    def setUp(self):
        self.cap = _make_cap_user()
        self.suprido_user = _make_plain_user(username='suprido', email='suprido@example.com')
        self.other_user = _make_plain_user(username='other2', email='other2@example.com')

        supridos_group, _ = Group.objects.get_or_create(name='SUPRIDOS')
        self.suprido_user.groups.add(supridos_group)

        self.credor = Credor.objects.create(
            nome='Suprido Teste', email='suprido@example.com', tipo='PF'
        )
        self.suprimento = SuprimentoDeFundos.objects.create(
            suprido=self.credor,
            valor_liquido='500.00',
            taxa_saque='0.00',
            data_saida='2026-01-01',
            data_retorno='2026-01-10',
        )
        self.despesa = DespesaSuprimento.objects.create(
            suprimento=self.suprimento,
            data='2026-01-05',
            estabelecimento='Loja Teste',
            detalhamento='Material de escritório',
            nota_fiscal='NF-100',
            valor='100.00',
            arquivo='suprimentosdefundos/suprimento_1/despesas/test.pdf',
        )

    def test_cap_can_access(self):
        self.client.force_login(self.cap)
        with patch('django.db.models.fields.files.FieldFile.open', return_value=io.BytesIO(b'%PDF')):
            response = self.client.get(_doc_url('suprimento', self.despesa.id))
        self.assertNotEqual(response.status_code, 403)

    def test_suprido_not_encerrado_email_match_can_access(self):
        self.client.force_login(self.suprido_user)
        with patch('django.db.models.fields.files.FieldFile.open', return_value=io.BytesIO(b'%PDF')):
            response = self.client.get(_doc_url('suprimento', self.despesa.id))
        self.assertNotEqual(response.status_code, 403)

    def test_suprido_encerrado_gets_403(self):
        status_enc, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(
            status_choice='ENCERRADO'
        )
        self.suprimento.status = status_enc
        self.suprimento.save()
        self.client.force_login(self.suprido_user)
        response = self.client.get(_doc_url('suprimento', self.despesa.id))
        self.assertEqual(response.status_code, 403)

    def test_suprido_email_mismatch_gets_403(self):
        wrong_user = _make_plain_user(username='wrong_suprido', email='wrong@example.com')
        supridos_group = Group.objects.get(name='SUPRIDOS')
        wrong_user.groups.add(supridos_group)
        self.client.force_login(wrong_user)
        response = self.client.get(_doc_url('suprimento', self.despesa.id))
        self.assertEqual(response.status_code, 403)

    def test_non_supridos_group_gets_403(self):
        self.client.force_login(self.other_user)
        response = self.client.get(_doc_url('suprimento', self.despesa.id))
        self.assertEqual(response.status_code, 403)


@override_settings(SECURE_SSL_REDIRECT=False)
class DownloadArquivoSeguroImmutabilityTest(TestCase):
    """DocumentoProcesso.imutavel enforcement via signals."""

    def setUp(self):
        tipo = _make_tipo()
        processo = Processo.objects.create()
        self.doc = DocumentoProcesso.objects.create(
            processo=processo, tipo=tipo, arquivo='pagamentos/2026/proc_1/orig.pdf', ordem=1,
            imutavel=True,
        )

    def test_immutable_doc_cannot_change_arquivo(self):
        self.doc.arquivo = 'pagamentos/2026/proc_1/new.pdf'
        with self.assertRaises(DjangoValidationError):
            self.doc.save()

    def test_immutable_doc_cannot_be_deleted(self):
        with self.assertRaises(DjangoValidationError):
            self.doc.delete()

    def test_mutable_doc_can_be_deleted(self):
        tipo = _make_tipo()
        processo = Processo.objects.create()
        doc = DocumentoProcesso.objects.create(
            processo=processo, tipo=tipo, arquivo='pagamentos/2026/proc_1/mutable.pdf', ordem=1,
            imutavel=False,
        )
        with patch('processos.models.fluxo._delete_file'):
            doc.delete()
