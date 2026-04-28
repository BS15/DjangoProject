#!/usr/bin/env python
"""
Comprehensive test script to verify all external connections in the Django project.
Tests Autentique API, templates, and view connections.
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DjangoProject.settings')
sys.path.insert(0, str(Path(__file__).parent))
django.setup()

import requests
from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.template import Template, Context
from django.template.loader import render_to_string
from django.urls import reverse
from commons.shared.integracoes.autentique import (
    AUTENTIQUE_API_URL,
    AUTENTIQUE_API_TOKEN,
    _get_headers,
    _get_robust_session,
)


class ConnectionTestReport:
    """Track test results for reporting."""
    
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0
    
    def add_test(self, name, status, message, error=None):
        """Add a test result."""
        self.tests.append({
            'name': name,
            'status': status,
            'message': message,
            'error': str(error) if error else None,
        })
        
        if status == 'PASSED':
            self.passed += 1
        elif status == 'FAILED':
            self.failed += 1
        elif status == 'SKIPPED':
            self.skipped += 1
    
    def print_report(self):
        """Print a formatted report."""
        print("\n" + "="*80)
        print("CONNECTION TEST REPORT")
        print("="*80 + "\n")
        
        for test in self.tests:
            status_symbol = "✓" if test['status'] == 'PASSED' else "✗" if test['status'] == 'FAILED' else "⊘"
            print(f"{status_symbol} {test['name']}")
            print(f"  Status: {test['status']}")
            print(f"  Message: {test['message']}")
            if test['error']:
                print(f"  Error: {test['error']}")
            print()
        
        print("="*80)
        print(f"Summary: {self.passed} passed, {self.failed} failed, {self.skipped} skipped")
        print(f"Total: {len(self.tests)} tests")
        print("="*80 + "\n")
        
        return self.failed == 0


report = ConnectionTestReport()


def test_database_connection():
    """Test basic Django database connection."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        report.add_test(
            "Database Connection",
            "PASSED",
            "Django database connection successful"
        )
    except Exception as e:
        report.add_test(
            "Database Connection",
            "FAILED",
            "Failed to connect to database",
            e
        )


def test_autentique_api_connectivity():
    """Test if Autentique API is reachable."""
    try:
        if not AUTENTIQUE_API_TOKEN:
            report.add_test(
                "Autentique API Connectivity",
                "SKIPPED",
                "AUTENTIQUE_API_TOKEN environment variable not set"
            )
            return
        
        session = _get_robust_session()
        headers = _get_headers()
        
        # Simple query to check connectivity
        test_query = """
        query {
            viewer {
                id
            }
        }
        """
        
        response = session.post(
            AUTENTIQUE_API_URL,
            headers=headers,
            json={"query": test_query},
            timeout=10,
        )
        
        if response.status_code == 200:
            data = response.json()
            if "errors" not in data or data.get("data") is not None:
                report.add_test(
                    "Autentique API Connectivity",
                    "PASSED",
                    f"Autentique API is reachable (Status: {response.status_code})"
                )
            else:
                errors = data.get("errors", [])
                report.add_test(
                    "Autentique API Connectivity",
                    "FAILED",
                    f"Autentique API returned errors: {errors}",
                    None
                )
        else:
            report.add_test(
                "Autentique API Connectivity",
                "FAILED",
                f"Autentique API returned HTTP {response.status_code}",
                response.text
            )
    
    except requests.exceptions.ConnectionError as e:
        report.add_test(
            "Autentique API Connectivity",
            "FAILED",
            "Cannot connect to Autentique API - network error",
            e
        )
    except requests.exceptions.Timeout as e:
        report.add_test(
            "Autentique API Connectivity",
            "FAILED",
            "Autentique API connection timeout",
            e
        )
    except Exception as e:
        report.add_test(
            "Autentique API Connectivity",
            "FAILED",
            "Unexpected error testing Autentique API",
            e
        )


def test_autentique_authentication():
    """Test if Autentique API token is valid."""
    try:
        if not AUTENTIQUE_API_TOKEN:
            report.add_test(
                "Autentique API Authentication",
                "SKIPPED",
                "AUTENTIQUE_API_TOKEN environment variable not set"
            )
            return
        
        if AUTENTIQUE_API_TOKEN == "":
            report.add_test(
                "Autentique API Authentication",
                "FAILED",
                "AUTENTIQUE_API_TOKEN is empty",
                None
            )
            return
        
        session = _get_robust_session()
        headers = _get_headers()
        
        # Query that requires authentication
        test_query = """
        query {
            viewer {
                id
                email
            }
        }
        """
        
        response = session.post(
            AUTENTIQUE_API_URL,
            headers=headers,
            json={"query": test_query},
            timeout=10,
        )
        
        data = response.json()
        
        if response.status_code == 200 and "errors" not in data and data.get("data", {}).get("viewer"):
            report.add_test(
                "Autentique API Authentication",
                "PASSED",
                "Autentique API token is valid and authenticated"
            )
        elif "errors" in data:
            errors = data.get("errors", [])
            if any("authentication" in str(e).lower() or "unauthorized" in str(e).lower() for e in errors):
                report.add_test(
                    "Autentique API Authentication",
                    "FAILED",
                    "Autentique API token is invalid or expired",
                    str(errors)
                )
            else:
                report.add_test(
                    "Autentique API Authentication",
                    "FAILED",
                    "Autentique API responded with errors",
                    str(errors)
                )
        else:
            report.add_test(
                "Autentique API Authentication",
                "FAILED",
                "Autentique API authentication check failed",
                None
            )
    
    except Exception as e:
        report.add_test(
            "Autentique API Authentication",
            "FAILED",
            "Error testing Autentique API authentication",
            e
        )


def test_templates_render():
    """Test that all key templates can render without errors."""
    template_paths = [
        'base.html',
        'layouts/base_list.html',
        'layouts/base_form.html',
        'layouts/base_detail.html',
        'layouts/base_review.html',
    ]
    
    factory = RequestFactory()
    request = factory.get('/')
    
    # Create a mock user
    try:
        from django.contrib.auth.models import User
        user = User.objects.first()
        if not user:
            user = User.objects.create_user(username='testuser', password='testpass')
        request.user = user
    except:
        request.user = None
    
    for template_path in template_paths:
        try:
            render_to_string(template_path, {'request': request})
            report.add_test(
                f"Template: {template_path}",
                "PASSED",
                f"Template renders successfully"
            )
        except Exception as e:
            report.add_test(
                f"Template: {template_path}",
                "FAILED",
                f"Template failed to render",
                e
            )


def test_signature_views_exist():
    """Test that signature-related views are accessible."""
    try:
        from django.urls import get_resolver
        from django.urls.exceptions import Resolver404
        
        # Check if signature-related URLs exist
        signature_urls = [
            'painel_assinaturas_diaria',
            'sincronizar_assinatura',
            'reenviar_para_autentique',
        ]
        
        resolver = get_resolver()
        for url_name in signature_urls:
            try:
                url = reverse(url_name, args=[1])
                report.add_test(
                    f"URL: {url_name}",
                    "PASSED",
                    f"URL '{url_name}' exists and resolves"
                )
            except Resolver404:
                report.add_test(
                    f"URL: {url_name}",
                    "FAILED",
                    f"URL '{url_name}' not found in URL configuration"
                )
    except Exception as e:
        report.add_test(
            "Signature URLs",
            "FAILED",
            "Error checking signature URLs",
            e
        )


def test_assinatura_model():
    """Test that AssinaturaEletronica model is accessible."""
    try:
        from pagamentos.domain_models import AssinaturaEletronica
        count = AssinaturaEletronica.objects.count()
        report.add_test(
            "AssinaturaEletronica Model",
            "PASSED",
            f"Model accessible. Current count: {count}"
        )
    except Exception as e:
        report.add_test(
            "AssinaturaEletronica Model",
            "FAILED",
            "Cannot access AssinaturaEletronica model",
            e
        )


def test_diaria_model_signature_relation():
    """Test that Diária model has signature relations."""
    try:
        from verbas_indenizatorias.models import Diaria
        
        # Check if the model has the signature relation
        if hasattr(Diaria, 'assinaturas_autentique'):
            report.add_test(
                "Diária Signature Relation",
                "PASSED",
                "Diária model has assinaturas_autentique relation"
            )
        else:
            report.add_test(
                "Diária Signature Relation",
                "FAILED",
                "Diária model missing assinaturas_autentique relation"
            )
    except Exception as e:
        report.add_test(
            "Diária Signature Relation",
            "FAILED",
            "Error checking Diária model",
            e
        )


def test_integracao_services_import():
    """Test that integration services can be imported."""
    try:
        from pagamentos.services.integracoes import (
            enviar_documento_para_assinatura,
            verificar_e_baixar_documento,
        )
        report.add_test(
            "Integration Services Import",
            "PASSED",
            "Integration service functions imported successfully"
        )
    except Exception as e:
        report.add_test(
            "Integration Services Import",
            "FAILED",
            "Failed to import integration services",
            e
        )


def test_installed_apps():
    """Test that all required apps are installed."""
    from django.conf import settings
    
    required_apps = [
        'pagamentos',
        'commons',
        'verbas_indenizatorias',
        'credores',
        'fiscal',
        'suprimentos',
    ]
    
    for app in required_apps:
        if f'{app}.apps.{app.capitalize()}Config' in settings.INSTALLED_APPS or app in settings.INSTALLED_APPS:
            report.add_test(
                f"App: {app}",
                "PASSED",
                f"App '{app}' is installed"
            )
        else:
            report.add_test(
                f"App: {app}",
                "FAILED",
                f"App '{app}' is NOT installed"
            )


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("STARTING CONNECTION AND INTEGRATION TESTS")
    print("="*80 + "\n")
    
    # Run all tests
    test_installed_apps()
    test_database_connection()
    test_autentique_api_connectivity()
    test_autentique_authentication()
    test_integracao_services_import()
    test_assinatura_model()
    test_diaria_model_signature_relation()
    test_templates_render()
    test_signature_views_exist()
    
    # Print report
    success = report.print_report()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
