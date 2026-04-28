"""Debug views for testing connections and integrations."""

import logging
from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import requests

from commons.shared.integracoes.autentique import (
    AUTENTIQUE_API_URL,
    AUTENTIQUE_API_TOKEN,
    _get_headers,
    _get_robust_session,
    AutentiqueConnectionError,
    AutentiqueAuthenticationError,
    AutentiqueAPIError,
)

logger = logging.getLogger(__name__)


@permission_required("auth.staff", raise_exception=True)
@require_http_methods(["GET"])
def health_check_autentique(request):
    """Check if Autentique API is accessible and authentication is valid."""
    results = {
        "autentique": {
            "connected": False,
            "authenticated": False,
            "errors": [],
        }
    }
    
    # Check if token is configured
    if not AUTENTIQUE_API_TOKEN:
        results["autentique"]["errors"].append("AUTENTIQUE_API_TOKEN não está configurado")
        return JsonResponse(results, status=503)
    
    # Test connectivity
    try:
        session = _get_robust_session()
        headers = _get_headers("json")
        
        # Simple connectivity test
        test_query = {"query": "query { viewer { id } }"}
        
        response = session.post(
            AUTENTIQUE_API_URL,
            headers=headers,
            json=test_query,
            timeout=10,
        )
        
        results["autentique"]["connected"] = True
        
        if response.status_code == 200:
            data = response.json()
            
            if "errors" in data and data["errors"]:
                error_msg = str(data["errors"])
                results["autentique"]["errors"].append(f"API Error: {error_msg}")
                
                if any(term in error_msg.lower() for term in ["authentication", "unauthorized", "token"]):
                    results["autentique"]["errors"].append("Authentication failure - token may be invalid")
            else:
                results["autentique"]["authenticated"] = True
        else:
            results["autentique"]["errors"].append(f"HTTP {response.status_code}: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        results["autentique"]["errors"].append("API request timeout - connection to api.autentique.com.br is slow/unreachable")
        
    except requests.exceptions.ConnectionError:
        results["autentique"]["errors"].append("Cannot connect to api.autentique.com.br - network/firewall issue")
        
    except Exception as e:
        results["autentique"]["errors"].append(f"Unexpected error: {type(e).__name__}: {str(e)[:200]}")
    
    status_code = 200 if results["autentique"]["authenticated"] else 503
    return JsonResponse(results, status=status_code)


@permission_required("auth.staff", raise_exception=True)
@require_http_methods(["GET"])
def connection_status_dashboard(request):
    """Return connection status for all integrations."""
    from django.db import connection as db_connection
    
    status = {
        "database": {"connected": False},
        "autentique": {"connected": False, "authenticated": False},
    }
    
    # Database check
    try:
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status["database"]["connected"] = True
    except Exception as e:
        status["database"]["error"] = str(e)
    
    # Autentique check
    if not AUTENTIQUE_API_TOKEN:
        status["autentique"]["error"] = "Token not configured"
    else:
        try:
            session = _get_robust_session()
            headers = _get_headers("json")
            response = session.post(
                AUTENTIQUE_API_URL,
                headers=headers,
                json={"query": "query { viewer { id } }"},
                timeout=5,
            )
            status["autentique"]["connected"] = response.status_code == 200
            status["autentique"]["authenticated"] = response.status_code == 200 and "errors" not in response.json()
        except Exception as e:
            status["autentique"]["error"] = str(e)[:100]
    
    all_ok = status["database"]["connected"] and status["autentique"]["authenticated"]
    status_code = 200 if all_ok else 503
    
    return JsonResponse({
        "status": "OK" if all_ok else "DEGRADED",
        "checks": status,
    }, status=status_code)
