from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse

from processos.models.segments.cadastros import Credor
from processos.models import Diaria, MeiosDeTransporte, StatusChoicesVerbasIndenizatorias
from processos.models.segments.core import Processo, ReembolsoCombustivel
from processos.models.segments.documents import DocumentoDiaria
from processos.models.segments.parametrizations import TiposDeDocumento
from processos.views import (
    add_auxilio_view,
    add_diaria_view,
    add_jeton_view,
    add_reembolso_view,
    agrupar_verbas_view,
    auxilios_list_view,
    diarias_list_view,
    edit_auxilio_view,
    edit_jeton_view,
    edit_reembolso_view,
    jetons_list_view,
    reembolsos_list_view,
)


class VerbasSplitRoutingTest(TestCase):
    def test_rotas_principais_verbas_apontam_para_views_exportadas(self):
        casos = [
            ('diarias_list', diarias_list_view),
            ('reembolsos_list', reembolsos_list_view),
            ('jetons_list', jetons_list_view),
            ('auxilios_list', auxilios_list_view),
            ('add_diaria', add_diaria_view),
            ('add_reembolso', add_reembolso_view),
            ('add_jeton', add_jeton_view),
            ('add_auxilio', add_auxilio_view),
        ]

        for nome_url, view_esperada in casos:
            with self.subTest(url_name=nome_url):
                match = resolve(reverse(nome_url))
                self.assertIs(match.func, view_esperada)

    def test_rotas_edicao_verbas_apontam_para_views_exportadas(self):
        casos = [
            ('edit_reembolso', {'pk': 1}, edit_reembolso_view),
            ('edit_jeton', {'pk': 1}, edit_jeton_view),
            ('edit_auxilio', {'pk': 1}, edit_auxilio_view),
        ]

        for nome_url, kwargs, view_esperada in casos:
            with self.subTest(url_name=nome_url):
                match = resolve(reverse(nome_url, kwargs=kwargs))
                self.assertIs(match.func, view_esperada)


class AgrupamentoVerbasRuleTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='agrupador_verbas', password='testpass123')
        permissao = Permission.objects.get(codename='pode_agrupar_verbas')
        self.user.user_permissions.add(permissao)
        self.beneficiario_a = Credor.objects.create(nome='Beneficiario A', tipo='PF')
        self.beneficiario_b = Credor.objects.create(nome='Beneficiario B', tipo='PF')

    def _request_post_com_sessao(self, url, data):
        request = self.factory.post(url, data=data)
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        request.user = self.user
        request._messages = FallbackStorage(request)
        return request

    def _novo_reembolso(self, beneficiario, numero):
        return ReembolsoCombustivel.objects.create(
            numero_sequencial=str(numero),
            beneficiario=beneficiario,
            data_saida=date(2026, 1, 10),
            data_retorno=date(2026, 1, 11),
            cidade_origem='Brasilia',
            cidade_destino='Goiania',
            distancia_km='100.00',
            preco_combustivel='6.00',
            valor_total='120.00',
        )

    def test_agrupar_multiplos_beneficiarios_define_credor_banco_do_brasil(self):
        reembolso_1 = self._novo_reembolso(self.beneficiario_a, 1)
        reembolso_2 = self._novo_reembolso(self.beneficiario_b, 2)

        url = reverse('agrupar_verbas', kwargs={'tipo_verba': 'reembolso'})
        request = self._request_post_com_sessao(
            url,
            {'verbas_selecionadas': [str(reembolso_1.id), str(reembolso_2.id)]},
        )

        response = agrupar_verbas_view(request, 'reembolso')

        self.assertEqual(response.status_code, 302)
        processo = Processo.objects.latest('id')
        self.assertEqual(processo.credor.nome, 'BANCO DO BRASIL S/A')

        reembolso_1.refresh_from_db()
        reembolso_2.refresh_from_db()
        self.assertEqual(reembolso_1.processo_id, processo.id)
        self.assertEqual(reembolso_2.processo_id, processo.id)

    def test_agrupar_mesmo_beneficiario_mantem_credor_original(self):
        reembolso_1 = self._novo_reembolso(self.beneficiario_a, 3)
        reembolso_2 = self._novo_reembolso(self.beneficiario_a, 4)

        url = reverse('agrupar_verbas', kwargs={'tipo_verba': 'reembolso'})
        request = self._request_post_com_sessao(
            url,
            {'verbas_selecionadas': [str(reembolso_1.id), str(reembolso_2.id)]},
        )

        response = agrupar_verbas_view(request, 'reembolso')

        self.assertEqual(response.status_code, 302)
        processo = Processo.objects.latest('id')
        self.assertEqual(processo.credor_id, self.beneficiario_a.id)


@override_settings(SECURE_SSL_REDIRECT=False)
class DiariaCreationFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='diarias_tester', password='testpass123')
        permissao = Permission.objects.get(codename='pode_criar_diarias')
        self.user.user_permissions.add(permissao)
        self.client.force_login(self.user)

        self.beneficiario = Credor.objects.create(nome='Beneficiario Diaria', tipo='PF')
        self.tipo_documento = TiposDeDocumento.objects.create(
            tipo_de_documento='COMPROVANTE DE VIAGEM',
            is_active=True,
        )
        self.meio_aereo = MeiosDeTransporte.objects.create(meio_de_transporte='AEREO')
        self.meio_veiculo_proprio = MeiosDeTransporte.objects.create(meio_de_transporte='VEÍCULO PRÓPRIO')
        self.status_reembolso = StatusChoicesVerbasIndenizatorias.objects.create(
            status_choice='PEDIDO - CÁLCULO DE VALORES PENDENTE'
        )
        self.url = reverse('add_diaria')

    def _payload_base(self, meio_id):
        return {
            'numero_siscac': 'SISCAC-001',
            'beneficiario': str(self.beneficiario.id),
            'tipo_solicitacao': 'INICIAL',
            'data_saida': '2026-04-10',
            'data_retorno': '2026-04-12',
            'cidade_origem': 'Brasilia',
            'cidade_destino': 'Goiania',
            'objetivo': 'Representacao institucional',
            'meio_de_transporte': str(meio_id),
            'quantidade_diarias': '2.0',
            'valor_total': '',
        }

    @patch('processos.views.verbas.tipos.diarias.forms.gerar_e_anexar_scd_diaria')
    def test_add_diaria_com_anexo_opcional_cria_documento(self, gerar_scd_mock):
        arquivo = SimpleUploadedFile('comprovante.pdf', b'%PDF-1.4\ncomprovante', content_type='application/pdf')
        payload = self._payload_base(self.meio_aereo.id)
        payload.update(
            {
                'numero_siscac': 'SISCAC-ANEXO',
                'tipo_documento_anexo': str(self.tipo_documento.id),
                'documento_anexo': arquivo,
            }
        )

        response = self.client.post(self.url, data=payload)

        self.assertEqual(response.status_code, 302)
        diaria = Diaria.objects.get(numero_siscac='SISCAC-ANEXO')
        self.assertTrue(DocumentoDiaria.objects.filter(diaria=diaria, tipo=self.tipo_documento).exists())
        gerar_scd_mock.assert_called_once_with(diaria, self.user)

    @patch('processos.views.verbas.tipos.diarias.forms.gerar_e_anexar_scd_diaria')
    def test_add_diaria_com_veiculo_proprio_cria_reembolso_pendente(self, gerar_scd_mock):
        payload = self._payload_base(self.meio_veiculo_proprio.id)
        payload['numero_siscac'] = 'SISCAC-VEICULO'

        response = self.client.post(self.url, data=payload)

        self.assertEqual(response.status_code, 302)
        diaria = Diaria.objects.get(numero_siscac='SISCAC-VEICULO')
        reembolso = ReembolsoCombustivel.objects.get(diaria=diaria)
        self.assertEqual(reembolso.status_id, self.status_reembolso.id)
        self.assertEqual(reembolso.beneficiario_id, diaria.beneficiario_id)
        self.assertEqual(reembolso.numero_sequencial, diaria.numero_siscac)
        gerar_scd_mock.assert_called_once_with(diaria, self.user)

    @patch('processos.views.verbas.tipos.diarias.forms.gerar_e_anexar_scd_diaria')
    def test_add_diaria_com_upload_incompleto_nao_persiste_registro(self, gerar_scd_mock):
        arquivo = SimpleUploadedFile('comprovante.pdf', b'%PDF-1.4\nincompleto', content_type='application/pdf')
        payload = self._payload_base(self.meio_aereo.id)
        payload.update(
            {
                'numero_siscac': 'SISCAC-INVALIDO',
                'documento_anexo': arquivo,
            }
        )

        response = self.client.post(self.url, data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Diaria.objects.filter(numero_siscac='SISCAC-INVALIDO').exists())
        self.assertEqual(DocumentoDiaria.objects.count(), 0)
        gerar_scd_mock.assert_not_called()
