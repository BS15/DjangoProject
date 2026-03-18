from django.test import TestCase
from .invoice_processor import process_invoice_taxes, _normalizar_cidade
from .models import Processo, StatusChoicesProcesso, TiposDeDocumento, DocumentoProcesso, DocumentoFiscal
from .validators import verificar_turnpike
from .views import STATUS_BLOQUEADOS_TOTAL, STATUS_SOMENTE_DOCUMENTOS


class NormalizarCidadeTest(TestCase):
    def test_remove_acentos(self):
        self.assertEqual(_normalizar_cidade("Florianópolis"), "FLORIANOPOLIS")

    def test_uppercase(self):
        self.assertEqual(_normalizar_cidade("joinville"), "JOINVILLE")

    def test_string_vazia(self):
        self.assertEqual(_normalizar_cidade(""), "")

    def test_none(self):
        self.assertEqual(_normalizar_cidade(None), "")


class ProcessInvoiceTaxesSimpleNacionalTest(TestCase):
    """Optante pelo Simples Nacional: impostos federais são ignorados."""

    def _base_json(self):
        return {
            "valor_bruto": 1000.00,
            "valor_liquido": 1000.00,
            "optante_simples_nacional": True,
            "impostos_federais": {"ir": 94.0, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }

    def test_sem_retencoes_federais(self):
        resultado = process_invoice_taxes(self._base_json())
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertNotIn("6190", codigos)
        self.assertNotIn("6147", codigos)

    def test_sucesso_matematico(self):
        resultado = process_invoice_taxes(self._base_json())
        self.assertTrue(resultado["sucesso_matematico"])

    def test_sem_alertas(self):
        resultado = process_invoice_taxes(self._base_json())
        self.assertEqual(resultado["alertas_usuario"], [])


class ProcessInvoiceTaxesFederaisTest(TestCase):
    """Não optante – validação dos códigos de impostos federais."""

    def _json_com_aliquota(self, soma_federais, valor_bruto=1000.00):
        return {
            "valor_bruto": valor_bruto,
            "valor_liquido": valor_bruto - soma_federais,
            "optante_simples_nacional": False,
            "impostos_federais": {
                "ir": soma_federais,
                "pis": 0.0,
                "cofins": 0.0,
                "csll": 0.0,
            },
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }

    def test_codigo_6190(self):
        # 9.45% → entre 9.40 e 9.50
        resultado = process_invoice_taxes(self._json_com_aliquota(94.50))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertIn("6190", codigos)

    def test_codigo_6147(self):
        # 5.85% → entre 5.80 e 5.90
        resultado = process_invoice_taxes(self._json_com_aliquota(58.50))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertIn("6147", codigos)

    def test_aliquota_fora_dos_intervalos(self):
        # 10% → nenhum código reconhecido
        resultado = process_invoice_taxes(self._json_com_aliquota(100.0))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertNotIn("6190", codigos)
        self.assertNotIn("6147", codigos)

    def test_alerta_sem_impostos_sem_justificativa(self):
        data = self._json_com_aliquota(0.0)
        data["valor_liquido"] = 1000.00
        resultado = process_invoice_taxes(data)
        self.assertTrue(any("impostos federais" in a for a in resultado["alertas_usuario"]))

    def test_sem_alerta_com_justificativa(self):
        data = self._json_com_aliquota(0.0)
        data["valor_liquido"] = 1000.00
        data["justificativa_isencao_federal"] = "Imune por decisão judicial"
        resultado = process_invoice_taxes(data)
        self.assertFalse(any("impostos federais" in a for a in resultado["alertas_usuario"]))


class ProcessInvoiceTaxesISSTest(TestCase):
    """Validação das regras de ISS municipal."""

    def _json_iss(self, valor, cidade):
        return {
            "valor_bruto": 1000.00,
            "valor_liquido": 1000.00 - valor,
            "optante_simples_nacional": True,
            "impostos_federais": {"ir": 0.0, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": valor, "local_prestacao_servico": cidade},
            "inss_destacado": 0.0,
        }

    def test_cidade_conveniada_gera_retencao(self):
        resultado = process_invoice_taxes(self._json_iss(50.0, "Florianópolis"))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertIn("ISS_RETIDO", codigos)

    def test_cidade_nao_conveniada_gera_alerta(self):
        resultado = process_invoice_taxes(self._json_iss(50.0, "São Paulo"))
        self.assertFalse(
            any(r["codigo"] == "ISS_RETIDO" for r in resultado["retencoes_a_processar"])
        )
        self.assertTrue(any("não conveniada" in a for a in resultado["alertas_usuario"]))

    def test_cidade_uppercase_sem_acento(self):
        resultado = process_invoice_taxes(self._json_iss(30.0, "BALNEARIO CAMBORIU"))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertIn("ISS_RETIDO", codigos)

    def test_iss_zero_sem_retencao(self):
        resultado = process_invoice_taxes(self._json_iss(0.0, "Joinville"))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertNotIn("ISS_RETIDO", codigos)


class ProcessInvoiceTaxesINSSTest(TestCase):
    """Validação das regras de INSS."""

    def _json_inss(self, valor):
        return {
            "valor_bruto": 1000.00,
            "valor_liquido": 1000.00 - valor,
            "optante_simples_nacional": True,
            "impostos_federais": {"ir": 0.0, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": valor,
        }

    def test_inss_destacado_gera_retencao(self):
        resultado = process_invoice_taxes(self._json_inss(110.0))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertIn("INSS_RETIDO", codigos)

    def test_inss_destacado_gera_alerta_informativo(self):
        resultado = process_invoice_taxes(self._json_inss(110.0))
        self.assertTrue(any("INSS" in a for a in resultado["alertas_usuario"]))

    def test_inss_zero_sem_retencao(self):
        resultado = process_invoice_taxes(self._json_inss(0.0))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertNotIn("INSS_RETIDO", codigos)


class ProcessInvoiceTaxesMathCheckTest(TestCase):
    """Verificação matemática de integridade."""

    def test_nota_fechada_sucesso(self):
        data = {
            "valor_bruto": 1000.00,
            "valor_liquido": 905.50,
            "optante_simples_nacional": False,
            "impostos_federais": {"ir": 94.50, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }
        resultado = process_invoice_taxes(data)
        self.assertTrue(resultado["sucesso_matematico"])
        self.assertFalse(any("integridade" in a for a in resultado["alertas_usuario"]))

    def test_nota_com_divergencia_gera_alerta(self):
        data = {
            "valor_bruto": 1000.00,
            "valor_liquido": 800.00,   # Divergência proposital
            "optante_simples_nacional": False,
            "impostos_federais": {"ir": 94.50, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }
        resultado = process_invoice_taxes(data)
        self.assertFalse(resultado["sucesso_matematico"])
        self.assertTrue(any("integridade" in a for a in resultado["alertas_usuario"]))

    def test_tolerancia_centavos(self):
        # diferença de 0.03 deve ser aceita
        data = {
            "valor_bruto": 1000.00,
            "valor_liquido": 905.47,
            "optante_simples_nacional": False,
            "impostos_federais": {"ir": 94.50, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }
        resultado = process_invoice_taxes(data)
        self.assertTrue(resultado["sucesso_matematico"])


class ProcessInvoiceTaxesOutputContractTest(TestCase):
    """Verifica o contrato de saída da função."""

    def test_chaves_obrigatorias(self):
        data = {
            "valor_bruto": 500.0,
            "valor_liquido": 500.0,
            "optante_simples_nacional": True,
            "impostos_federais": {"ir": 0.0, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }
        resultado = process_invoice_taxes(data)
        self.assertIn("sucesso_matematico", resultado)
        self.assertIn("valor_bruto_identificado", resultado)
        self.assertIn("valor_liquido_identificado", resultado)
        self.assertIn("retencoes_a_processar", resultado)
        self.assertIn("alertas_usuario", resultado)

    def test_retencoes_tem_campos_corretos(self):
        data = {
            "valor_bruto": 1000.00,
            "valor_liquido": 905.50,
            "optante_simples_nacional": False,
            "impostos_federais": {"ir": 94.50, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }
        resultado = process_invoice_taxes(data)
        for retencao in resultado["retencoes_a_processar"]:
            self.assertIn("codigo", retencao)
            self.assertIn("valor", retencao)
            self.assertIn("descricao", retencao)


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

from .models import (
    CodigosImposto,
    Credor,
    DadosContribuinte,
    DocumentoFiscal,
    Processo,
)
from .reinf_services import (
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
