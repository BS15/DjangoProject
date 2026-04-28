# Template & Connection Analysis Report

## Overview
This report analyzes all external connections and templates in the Django project to identify potential points of failure.

---

## 1. EXTERNAL API INTEGRATIONS

### 1.1 Autentique Digital Signature API

**File:** `commons/shared/integracoes/autentique.py`

**Status:** ✓ Configured
- API URL: `https://api.autentique.com.br/v2/graphql`
- Token: Set in `.env` as `AUTENTIQUE_API_TOKEN`
- Current Token: `ec3599fbeca60ce9f3971f4efdd0265a88300ec9cbc16043efe9f764101cdfa9`

**Potential Issues Identified:**

⚠️ **ISSUE 1: Missing Content-Type Header for JSON Requests**
- Location: `autentique.py`, line 119 (query verification)
- Function: `verificar_e_baixar_documento()`
- Code:
  ```python
  response = _get_robust_session().post(
      AUTENTIQUE_API_URL,
      headers=_get_headers(),
      json={"query": query, "variables": {"id": autentique_id}},
      timeout=15,
  )
  ```
- **Fix:** Update `_get_headers()` to include Content-Type for JSON requests
- **Current Headers:** `{"Authorization": f"Bearer {token}"}`
- **Should Be:** `{"Authorization": f"Bearer {token}", "Content-Type": "application/json"}`

⚠️ **ISSUE 2: Inconsistent Header Management**
- The `_get_headers()` function doesn't differentiate between multipart (upload) and JSON requests
- Multipart requests automatically handle Content-Type
- JSON requests need explicit Content-Type header

⚠️ **ISSUE 3: No Error Differentiation**
- Generic error handling doesn't distinguish between:
  - Network connectivity issues
  - Authentication failures (invalid/expired token)
  - API errors
  - Rate limiting
- Error messages are too generic for debugging

⚠️ **ISSUE 4: Timeout Too Short**
- 15 seconds timeout may be too short for large file uploads
- Large PDF files might fail silently

⚠️ **ISSUE 5: No Logging of Request/Response**
- Requests and responses are not logged, making debugging difficult
- Only exceptions are logged, not full request details

**Impact:** Files sent to Autentique for signature might fail or be rejected

---

## 2. TEMPLATES USING EXTERNAL CONNECTIONS

### 2.1 Template Files That Reference Signatures

**Location:** `verbas_indenizatorias/templates/`

Files that reference Autentique connections:
- `diarias/detalhe_diaria.html` - Displays signature status
- `diarias/painel_assinaturas.html` - Signature management panel
- `processo/detalhe_processo.html` - Process details with signature links

**Potential Issues:**
- Templates may render before connection to fetch signature status
- No fallback rendering if API is unreachable
- UI may show stale data if API is down

### 2.2 Base Templates

**Location:** `commons/templates/layouts/`

- `base_detail.html` - Extends base.html
- `base_form.html` - Form rendering
- `base_list.html` - List views
- `base_review.html` - Review workflow

**Status:** ✓ Base templates do not directly call external APIs

---

## 3. VIEWS ACCESSING EXTERNAL CONNECTIONS

### 3.1 Signature-Related Views

**File:** `verbas_indenizatorias/views/diarias/signatures.py`

#### View 1: `sincronizar_assinatura_view()`
- Calls: `verificar_e_baixar_documento()`
- Risk Level: **HIGH**
- Error Handling: ✓ Has try/catch, but stores "ERRO" status
- Logging: ✓ Logs critical errors

#### View 2: `reenviar_assinatura_view()`
- Calls: `enviar_documento_para_assinatura()`
- Risk Level: **HIGH**
- Error Handling: ✓ Has try/catch
- Logging: ✓ Logs critical errors
- **NEW ISSUE:** File not closed properly if exception occurs mid-upload

### 3.2 Process Action Views

**File:** `verbas_indenizatorias/views/processo/actions.py`

#### View: `emitir_pcd_e_enviar_autentique_action()`
- Calls: `enviar_documento_para_assinatura()`
- Risk Level: **HIGH**
- Errors reported: Messages with "Falha de conexão ao enviar para a Autentique"

---

## 4. IDENTIFIED CONNECTION FAILURES & FIXES

### FAILURE 1: Missing Content-Type Header ⚠️
**Symptom:** API might reject JSON requests as malformed
**Location:** `commons/shared/integracoes/autentique.py`, `_get_headers()`

**Fix:**
```python
def _get_headers(request_type="json"):
    headers = {"Authorization": f"Bearer {AUTENTIQUE_API_TOKEN}"}
    if request_type == "json":
        headers["Content-Type"] = "application/json"
    return headers
```

### FAILURE 2: File Handle Not Closed ⚠️
**Symptom:** Permission denied or resource leak errors
**Location:** `verbas_indenizatorias/views/diarias/signatures.py`, line 77
**Code:**
```python
assinatura.arquivo.open("rb")
payload = enviar_documento_para_assinatura(...)
# File not closed!
```

**Fix:**
```python
with assinatura.arquivo.open("rb") as f:
    payload = enviar_documento_para_assinatura(f.read(), ...)
finally:
    assinatura.arquivo.close()
```

### FAILURE 3: Generic Error Messages ⚠️
**Symptom:** Cannot debug connection issues
**Location:** All API calls
**Fix:** Add specific error type identification:
```python
except requests.exceptions.Timeout:
    messages.error(request, "API connection timeout - please try again")
except requests.exceptions.ConnectionError:
    messages.error(request, "Network error - cannot reach Autentique")
except Exception as e:
    if "authentication" in str(e).lower():
        messages.error(request, "Authentication failed - check API token")
    else:
        messages.error(request, f"Error: {e}")
```

### FAILURE 4: No Connection Health Check ⚠️
**Symptom:** UI shows "send to Autentique" button even when API is down
**Location:** Dashboard and process pages
**Fix:** Add a connection status view

---

## 5. TEMPLATES NEEDING CONNECTION CHECKS

### Critical Templates That Display Signature Status

1. **`verbas_indenizatorias/templates/diarias/painel_assinaturas.html`**
   - Contains Autentique links
   - Should show connection status

2. **`verbas_indenizatorias/templates/diarias/detalhe_diaria.html`**
   - Shows "Enviar para Assinatura" buttons
   - Should indicate if Autentique is unavailable

3. **`pagamentos/templates/assinatura_eletronicas_list.html`**
   - Lists all signatures
   - Should show which ones failed to connect

---

## 6. TEST COVERAGE

### Currently Missing Tests

1. ❌ Autentique API connectivity test
2. ❌ Token validation test  
3. ❌ Large file upload test
4. ❌ Timeout handling test
5. ❌ Network error recovery test
6. ❌ Expired token renewal test
7. ❌ Template rendering with no connection test
8. ❌ Database connection test

### Recommended Test Suite

Create `tests/test_integrations.py`:
```python
class AutentiqueIntegrationTests(TestCase):
    def test_api_connectivity(self)
    def test_token_valid(self)
    def test_document_upload(self)
    def test_document_download(self)
    def test_timeout_handling(self)
    def test_network_error_handling(self)
    def test_malformed_response_handling(self)
    def test_template_render_without_api(self)
```

---

## 7. RECOMMENDED FIXES (Priority Order)

### Priority 1: Critical (Do First)
- [ ] Add Content-Type header to JSON requests
- [ ] Fix file handle closing in `reenviar_assinatura_view`
- [ ] Add specific error handling for different connection failures

### Priority 2: Important (Do Second)
- [ ] Add logging for all API requests/responses
- [ ] Create API health check endpoint
- [ ] Add timeout increase for large uploads
- [ ] Update UI to show API status

### Priority 3: Nice to Have (Do Later)
- [ ] Add retry logic with exponential backoff
- [ ] Create API token refresh mechanism
- [ ] Add offline mode for signature features
- [ ] Create comprehensive test suite

---

## 8. ENVIRONMENT CONFIGURATION CHECK

- ✓ `AUTENTIQUE_API_TOKEN` is set in `.env`
- ✓ `SECRET_KEY` is configured
- ✓ `DEBUG` mode is True (development)
- ✓ Database configured locally (SQLite)
- ✓ All required apps installed

---

## 9. HOW TO TEST CONNECTIONS

### Option 1: Run the provided test script
```bash
python test_connections_simple.py
```

### Option 2: Manual testing
```bash
# Check API connectivity
curl -X POST https://api.autentique.com.br/v2/graphql \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { viewer { id } }"}'

# If you get a valid response, the API is working
```

### Option 3: Django shell test
```bash
python manage.py shell
>>> from commons.shared.integracoes.autentique import verificar_e_baixar_documento
>>> verificar_e_baixar_documento("test-id-here")  # This will fail but show connection
```

---

## 10. NEXT STEPS

1. **Run the test scripts** to identify actual failure points
2. **Apply Priority 1 fixes** from section 7
3. **Add comprehensive logging** to all API calls
4. **Create health check endpoint** at `/health/autentique/`
5. **Update templates** to show API status
6. **Add test coverage** for all integration points
