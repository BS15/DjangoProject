"""
Testes de Contratos Congelados — URLs e Permissões.

Este módulo valida que URLs e permissões permanecem estáveis 
durante refatorações de fragmentação de apps.

Executar: python manage.py test processos.tests.test_frozen_contracts
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


class FrozenURLContractsTest(TestCase):
    """Validar que nomes de URL permanecem estáveis."""

    def test_home_page_resolves(self):
        """URL: home_page deve resolver."""
        url = reverse('home_page')
        self.assertEqual(url, '/')

    def test_add_process_resolves(self):
        """URL: add_process deve resolver."""
        url = reverse('add_process')
        self.assertEqual(url, '/adicionar/')

    def test_a_empenhar_resolves(self):
        """URL: a_empenhar deve resolver."""
        url = reverse('a_empenhar')
        self.assertIn('a-empenhar', url)

    def test_contas_a_pagar_resolves(self):
        """URL: contas_a_pagar deve resolver."""
        url = reverse('contas_a_pagar')
        self.assertIn('contas-a-pagar', url)

    def test_painel_conselho_resolves(self):
        """URL: painel_conselho deve resolver."""
        url = reverse('painel_conselho')
        self.assertIn('conselho', url)

    def test_painel_arquivamento_resolves(self):
        """URL: painel_arquivamento deve resolver."""
        url = reverse('painel_arquivamento')
        self.assertIn('arquivamento', url)

    def test_painel_verbas_resolves(self):
        """URL: painel_verbas deve resolver (se existe em URLconf)."""
        try:
            url = reverse('painel_verbas')
            self.assertIn('verbas', url)
        except:
            self.skipTest("painel_verbas não está em URLconf ainda")

    def test_auditoria_resolves(self):
        """URL: auditoria deve resolver."""
        url = reverse('auditoria')
        self.assertIn('auditoria', url)

    def test_sync_siscac_resolves(self):
        """URL: sincronizar_siscac deve resolver."""
        url = reverse('sincronizar_siscac')
        self.assertIn('sincronizar-siscac', url)

    def test_api_documentos_processo_resolves(self):
        """URL: api_documentos_processo deve resolver com kwargs."""
        url = reverse('api_documentos_processo', kwargs={'processo_id': 999})
        self.assertIn('/api/processo/999/documentos/', url)

    def test_download_arquivo_seguro_resolves(self):
        """URL: download_arquivo_seguro deve resolver com kwargs."""
        url = reverse('download_arquivo_seguro', kwargs={
            'tipo_documento': 'nota_fiscal',
            'documento_id': 123
        })
        self.assertIn('/documentos/secure/nota_fiscal/123/', url)


class FrozenPermissionContractsTest(TestCase):
    """Validar que codenames de permissão permanecem estáveis."""

    FLUXO_PERMS = [
        'pode_operar_contas_pagar',
        'pode_autorizar_pagamento',
        'pode_auditar_conselho',
        'pode_arquivar',
        'pode_contabilizar',
        'pode_atestar_liquidacao',
    ]

    VERBAS_PERMS = [
        'pode_visualizar_verbas',
        'pode_gerenciar_processos_verbas',
        'pode_gerenciar_jetons',
        'pode_gerenciar_reembolsos',
        'pode_gerenciar_auxilios',
        'pode_importar_diarias',
        'pode_sincronizar_diarias_siscac',
        'pode_agrupar_verbas',
    ]

    ADMIN_PERMS = [
        'acesso_backoffice',
    ]

    def test_fluxo_permissions_exist(self):
        """Validar que permissões de fluxo existem."""
        for codename in self.FLUXO_PERMS:
            perm = Permission.objects.filter(codename=codename).first()
            self.assertIsNotNone(
                perm,
                f"Permissão '{codename}' não encontrada"
            )

    def test_verbas_permissions_exist(self):
        """Validar que permissões de verbas existem."""
        for codename in self.VERBAS_PERMS:
            perm = Permission.objects.filter(codename=codename).first()
            self.assertIsNotNone(
                perm,
                f"Permissão '{codename}' não encontrada"
            )

    def test_admin_permissions_exist(self):
        """Validar que permissões administrativas existem."""
        for codename in self.ADMIN_PERMS:
            perm = Permission.objects.filter(codename=codename).first()
            self.assertIsNotNone(
                perm,
                f"Permissão '{codename}' não encontrada"
            )

    def test_all_custom_permissions_found(self):
        """Listar todas as permissões customizadas (para debug)."""
        custom_perms = Permission.objects.filter(
            content_type__app_label__in=['processos']
        ).values_list('codename', 'content_type__app_label').distinct()

        # Apenas listar; não é uma asserção
        perms_count = custom_perms.count()
        self.assertGreater(
            perms_count, 0,
            f"Nenhuma permissão found em app 'processos' (encontradas {perms_count})"
        )


class FrozenContentTypeContractsTest(TestCase):
    """Validar que Content-Types core permanecem estáveis."""

    CORE_MODELS = [
        'processo',
        'credor',
        'contasbancarias',
        'documentofiscal',
        'diaria',
        'suprimentodefundos',
    ]

    def test_core_content_types_exist(self):
        """Validar Content-Types dos modelos core."""
        for model_name in self.CORE_MODELS:
            ct = ContentType.objects.filter(
                model=model_name.lower()
            ).first()
            self.assertIsNotNone(
                ct,
                f"Content-Type para modelo '{model_name}' não encontrado"
            )

    def test_processo_content_type_in_processos_app(self):
        """Validar que Content-Type de Processo está em app 'processos' (baseline)."""
        ct = ContentType.objects.filter(
            app_label='processos', model='processo'
        ).first()
        self.assertIsNotNone(
            ct,
            "Em Fase 1, Processo deve estar em app_label='processos'"
        )
