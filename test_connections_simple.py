#!/usr/bin/env python
"""
Simple connection test script - tests external API connectivity first.
"""

import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment for Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DjangoProject.settings')

# Test 1: Check environment variables
print("\n" + "="*80)
print("TEST 1: Environment Variables")
print("="*80)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

autentique_token = os.getenv('AUTENTIQUE_API_TOKEN', '')
if autentique_token:
    print(f"✓ AUTENTIQUE_API_TOKEN is set: {autentique_token[:20]}...")
else:
    print("✗ AUTENTIQUE_API_TOKEN is NOT set")

# Test 2: Check basic imports
print("\n" + "="*80)
print("TEST 2: Module Imports")
print("="*80)

try:
    import requests
    print("✓ requests module available")
except ImportError as e:
    print(f"✗ requests module: {e}")

try:
    from requests.adapters import HTTPAdapter, Retry
    print("✓ requests adapters available")
except ImportError as e:
    print(f"✗ requests adapters: {e}")

# Test 3: Test Autentique API connectivity
print("\n" + "="*80)
print("TEST 3: Autentique API Connectivity")
print("="*80)

import requests

AUTENTIQUE_API_URL = "https://api.autentique.com.br/v2/graphql"

def get_headers():
    return {"Authorization": f"Bearer {autentique_token}", "Content-Type": "application/json"}

def get_robust_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

try:
    print(f"Attempting to reach: {AUTENTIQUE_API_URL}")
    session = get_robust_session()
    headers = get_headers()
    
    # Test with a simple query
    test_query = {"query": "query { viewer { id email } }"}
    
    print("Sending GraphQL query...")
    response = session.post(
        AUTENTIQUE_API_URL,
        headers=headers,
        json=test_query,
        timeout=10,
    )
    
    print(f"API Response Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        if "errors" in data and data["errors"]:
            print(f"✗ API returned errors: {data['errors']}")
            if any("authentication" in str(e).lower() for e in data["errors"]):
                print("  → Token might be invalid or expired")
        elif "data" in data:
            print(f"✓ API is working! Response: {data}")
        else:
            print(f"⚠ Unexpected response format: {data}")
    else:
        print(f"✗ API returned HTTP {response.status_code}")
        print(f"Response: {response.text[:500]}")

except requests.exceptions.ConnectionError as e:
    print(f"✗ Cannot connect to API - Network Error")
    print(f"  Error: {str(e)[:200]}")

except requests.exceptions.Timeout as e:
    print(f"✗ API connection timeout")
    print(f"  Error: {str(e)[:200]}")

except Exception as e:
    print(f"✗ Unexpected error: {type(e).__name__}: {str(e)[:200]}")

# Test 4: Django Setup
print("\n" + "="*80)
print("TEST 4: Django Setup")
print("="*80)

try:
    import django
    django.setup()
    print("✓ Django is configured and ready")
except Exception as e:
    print(f"✗ Django setup failed: {e}")
    sys.exit(1)

# Test 5: Database Connection
print("\n" + "="*80)
print("TEST 5: Database Connection")
print("="*80)

try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("✓ Database connection successful")
except Exception as e:
    print(f"✗ Database connection failed: {e}")

# Test 6: Check installed apps
print("\n" + "="*80)
print("TEST 6: Installed Apps")
print("="*80)

from django.conf import settings

required_apps = [
    'pagamentos',
    'commons',
    'verbas_indenizatorias',
    'credores',
    'fiscal',
    'suprimentos',
    'simple_history',
    'django_filters',
]

for app in required_apps:
    found = False
    for installed_app in settings.INSTALLED_APPS:
        if app.lower() in installed_app.lower():
            found = True
            break
    if found:
        print(f"✓ {app} is installed")
    else:
        print(f"✗ {app} is NOT installed")

# Test 7: Integration Models and Relations
print("\n" + "="*80)
print("TEST 7: Models and Relations")
print("="*80)

try:
    from pagamentos.domain_models import AssinaturaEletronica
    count = AssinaturaEletronica.objects.count()
    print(f"✓ AssinaturaEletronica model accessible (count: {count})")
except Exception as e:
    print(f"✗ AssinaturaEletronica model error: {e}")

try:
    from verbas_indenizatorias.models import Diaria
    if hasattr(Diaria, 'assinaturas_autentique'):
        print("✓ Diária has assinaturas_autentique relation")
    else:
        print("✗ Diária missing assinaturas_autentique relation")
except Exception as e:
    print(f"✗ Diária model error: {e}")

# Test 8: Template Rendering
print("\n" + "="*80)
print("TEST 8: Template Rendering")
print("="*80)

try:
    from django.template.loader import render_to_string
    from django.test import RequestFactory
    from django.contrib.auth.models import User
    
    factory = RequestFactory()
    request = factory.get('/')
    request.user = User.objects.first() or User(username='anonymous')
    
    templates_to_test = [
        'base.html',
        'layouts/base_detail.html',
    ]
    
    for template_path in templates_to_test:
        try:
            render_to_string(template_path, {'request': request})
            print(f"✓ Template '{template_path}' renders successfully")
        except Exception as e:
            print(f"✗ Template '{template_path}' failed: {str(e)[:100]}")
            
except Exception as e:
    print(f"⚠ Could not test templates: {e}")

# Test 9: Integration Services Import
print("\n" + "="*80)
print("TEST 9: Integration Services")
print("="*80)

try:
    from commons.shared.integracoes.autentique import (
        enviar_documento_para_assinatura,
        verificar_e_baixar_documento,
    )
    print("✓ Autentique integration services imported successfully")
except Exception as e:
    print(f"✗ Failed to import integration services: {e}")

try:
    from pagamentos.services.integracoes import (
        enviar_documento_para_assinatura as enviar_doc,
        verificar_e_baixar_documento as verificar_doc,
    )
    print("✓ Pagamentos integration services imported successfully")
except Exception as e:
    print(f"✗ Failed to import pagamentos services: {e}")

# Final Summary
print("\n" + "="*80)
print("CONNECTION TEST COMPLETE")
print("="*80)
print("\nNext steps:")
print("1. If Autentique API test failed, check your internet connection")
print("2. If token is invalid, verify AUTENTIQUE_API_TOKEN in .env file")
print("3. Check database connectivity if DB tests failed")
print("4. Run Django management commands: manage.py migrate, manage.py runserver")
print("="*80 + "\n")
