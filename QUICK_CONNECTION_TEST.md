# ⚡ Quick Connection Test Guide

## 🚀 Fastest Way to Test All Connections

### Option 1: One-Click HTTP Requests (FASTEST)
```bash
# Test if Autentique API is working
curl -s http://localhost:8000/health/autentique/ | python -m json.tool

# Test overall system health
curl -s http://localhost:8000/health/status/ | python -m json.tool
```

### Option 2: Run Test Script
```bash
cd /workspaces/DjangoProject
python test_connections_simple.py
```

---

## 📋 Connection Checklist

| Connection | Type | Status | How to Test |
|---|---|---|---|
| **Database** | SQLite | ✅ Configured | `python manage.py dbshell` or health endpoint |
| **Autentique API** | HTTP/GraphQL | ⚠️ Needs verification | `curl /health/autentique/` |
| **Django Templates** | Local | ✅ Rendering | `python manage.py runserver` then visit site |

---

## 🔍 What Each Temperature Means

### 🟢 GREEN (Working)
- ✅ All connections functional
- ✅ No errors in logs
- ✅ API responding correctly

### 🟡 YELLOW (Degraded)
- ⚠️ Some connections slow
- ⚠️ Timeouts occurring
- ⚠️ Retries happening

### 🔴 RED (Broken)
- ❌ Cannot reach API
- ❌ Authentication failed
- ❌ Consistent errors

---

## 🛠️ Common Connection Issues & Fixes

### Problem: "Cannot connect to Autentique"
```bash
# Check if your network can reach Autentique
ping api.autentique.com.br

# Or use curl
curl -I https://api.autentique.com.br/v2/graphql

# Expected: Should get a response (not "Connection refused")
```
**Fix:** Check firewall/network settings

### Problem: "Authentication failed" or "401 Unauthorized"
```bash
# Check if token is set
echo $AUTENTIQUE_API_TOKEN

# Check if token is in .env file
cat /workspaces/DjangoProject/.env | grep AUTENTIQUE
```
**Fix:** Update token in .env file (ask Autentique for new one)

### Problem: "Timeout" errors
```bash
# Check network latency
curl -w "Time: %{time_total}s\n" -o /dev/null -s https://api.autentique.com.br/v2/graphql

# If time > 30s, network is slow
```
**Fix:** Check your internet connection or Autentique API status

### Problem: "File not found" when downloading documents
```bash
# Check storage directory exists
ls -la /workspaces/DjangoProject/media/assinaturas_rascunho/

# Check if files are being uploaded correctly
python manage.py shell
>>> from pagamentos.domain_models import AssinaturaEletronica
>>> AssinaturaEletronica.objects.count()
```
**Fix:** Check media directory permissions

---

## 📊 Connection Status Endpoints

### Available Endpoints (in DEBUG mode only)

**1. Autentique Health Check**
```
GET /health/autentique/
```
Response:
```json
{
  "autentique": {
    "connected": true,
    "authenticated": true,
    "errors": []
  }
}
```

**2. Overall Status
```
GET /health/status/
```
Response:
```json
{
  "status": "OK",
  "checks": {
    "database": {"connected": true},
    "autentique": {"connected": true, "authenticated": true}
  }
}
```

---

## 🔐 Security Note

These health check endpoints require `@permission_required("auth.staff")`.

To test, you must:
1. Be logged in as a staff user
2. Have access to these development endpoints
3. Remember: These are DEBUG ONLY, remove before production!

---

## 📝 Test Results Interpretation

### Good Response Example:
```json
{
  "autentique": {
    "connected": true,
    "authenticated": true,
    "errors": []
  },
  "database": {
    "connected": true
  },
  "status": "OK"
}
```
✅ **All systems operational**

### Bad Response Examples:

**Network Error:**
```json
{
  "autentique": {
    "connected": false,
    "authenticated": false,
    "errors": ["Cannot connect to api.autentique.com.br - network/firewall issue"]
  }
}
```
❌ **Fix:** Check network/firewall

**Auth Error:**
```json
{
  "autentique": {
    "connected": true,
    "authenticated": false,
    "errors": ["Authentication failure - token may be invalid"]
  }
}
```
❌ **Fix:** Update token in .env

**Timeout Error:**
```json
{
  "autentique": {
    "connected": false,
    "authenticated": false,
    "errors": ["API request timeout - connection is slow/unreachable"]
  }
}
```
❌ **Fix:** Check internet speed, Autentique status

---

## 🎯 Quick Debugging Steps

1. **Start Django Server**
   ```bash
   python manage.py runserver
   ```

2. **Open another terminal and test connections**
   ```bash
   curl http://localhost:8000/health/status/
   ```

3. **Check the JSON response**
   - All should show `true` for connected/authenticated
   - `errors` array should be empty

4. **If there are errors, identify the type**
   - Network → Check firewall/internet
   - Auth → Check token in .env
   - API → Check Autentique status page

5. **Monitor Django logs while testing**
   ```bash
   # In Django console, you'll see log messages like:
   # INFO: Verificando status do documento na Autentique
   # ERROR: Erro de conexão
   ```

---

## 📞 When to Contact Autentique Support

Contact Autentique if you have:
- ✅ Valid network connectivity
- ✅ Valid token in .env
- ✅ Health checks show "connected: false"
- ✅ Direct API calls failing consistently

**DO NOT contact them if:**
- ❌ Your network is down
- ❌ Your token is wrong
- ❌ Your firewall blocks them

---

## 🚨 Emergency Fix

If Autentique API is down but you need to run the system:

1. **Disable signature features temporarily:**
   ```python
   # In settings.py, add:
   AUTENTIQUE_DISABLED = True
   ```

2. **Modify views to skip Autentique calls:**
   ```python
   if not AUTENTIQUE_DISABLED:
       response = send_to_autentique(...)
   else:
       messages.warning(request, "Signature service is temporarily offline")
   ```

3. **Use non-digital signature workflow** until Autentique recovers

---

## 📚 Further Help

- **Django Logs:** `python manage.py runserver | grep -i error`
- **Test Script:** `python test_connections_simple.py`
- **Analysis Report:** Read `CONNECTION_ANALYSIS_REPORT.md`
- **Full Summary:** Read `CONNECTION_TESTING_SUMMARY.md`

---

## Last Tested

```
Environment: Ubuntu 24.04 LTS
Python:      3.12.3
Django:      6.0.2
Database:    SQLite
Autentique:  API v2 (GraphQL)
Token Set:   YES (as of April 2026)
```

---

**Questions? Check the detailed reports in:**
- `CONNECTION_TESTING_SUMMARY.md` - Full implementation details
- `CONNECTION_ANALYSIS_REPORT.md` - Detailed technical analysis
