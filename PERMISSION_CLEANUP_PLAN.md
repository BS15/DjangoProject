# Permission Structure Cleanup — Action Plan

**Document Created:** 2026-04-07  
**Status:** Recommended Actions to Align Codebase with Current RBAC Pattern

---

## Phase 1: Remove Superseded Utilities (✂️ BREAKING)

### Task 1.1 — Clean `processos/utils/utils_permissoes.py`

**Current State:**
```python
def user_in_group(user, group_name):
    """Verifica se um usuário (Django User) pertence a um grupo específico."""
    if user.is_superuser:
        return True
    if user.groups.filter(name=group_name).exists():
        return True
    return False


def group_required(*group_names):
    """Decorator de view que exige autenticação e pertencimento a um dos grupos."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if request.user.groups.filter(name__in=group_names).exists():
                return view_func(request, *args, **kwargs)
            raise PermissionDenied(f"Acesso negado. Requer um dos grupos: {', '.join(group_names)}")
        return _wrapped_view
    return decorator
```

**Action:** Delete both functions entirely (they are not used).

**Recommended Result:**
```python
# processos/utils/utils_permissoes.py
# [DEPRECATED] This file is now empty and can be removed in a future refactoring.
# Permission management has been consolidated to use Django's @permission_required decorator.
# See: .github/copilot-instructions.md#robust-security-rbac
```

### Task 1.2 — Update `processos/utils/__init__.py`

**Current State (line 60):**
```python
from .utils_permissoes import user_in_group, group_required
```

**Current Exports (in `__all__`):**
```python
__all__ = [
    # ... other exports ...
    "user_in_group",
    "group_required",
    # ...
]
```

**Action:** Remove imports and exports:

**Before:**
```python
from .utils_permissoes import user_in_group, group_required
```

**After:**
```python
# Removed: user_in_group, group_required
# These have been superseded by @permission_required decorator.
# See: .github/copilot-instructions.md#robust-security-rbac
```

Also remove from `__all__`:
```python
# Remove from __all__:
    # "user_in_group",
    # "group_required",
```

---

## Phase 2: Address `_is_cap_backoffice()` Security Decision

### Current Function
**Location:** `processos/views/fluxo/security.py:22-27`

```python
def _is_cap_backoffice(user):
    """Retorna True para perfis de backoffice autorizados."""
    return user.is_active and (
        user.is_superuser
        or user.is_staff
        or user.has_perm("processos.pode_operar_contas_pagar")
    )
```

### Two Options:

#### ✅ Option A: Remove `is_staff` Check (Recommended)
```python
def _is_cap_backoffice(user):
    """Retorna True se usuário tem permissão explícita de backoffice."""
    return user.is_active and (
        user.is_superuser
        or user.has_perm("processos.pode_operar_contas_pagar")
    )
```

**Pros:**
- Enforces strict RBAC principle
- No implicit privileges based on Django staff flag
- Easier to audit and reason about permissions

**Cons:**
- Superadmins might need explicit permission assignment
- Could break existing workflows if staff users relied on implicit access

#### ⚠️ Option B: Document the `is_staff` Exception
```python
def _is_cap_backoffice(user):
    """
    Retorna True para perfis de backoffice autorizados.
    
    IMPORTANT: This function grants access to:
    1. Superusers (Django superuser flag)
    2. Django staff users (is_staff=True) — implicit policy
    3. Users with explicit 'pode_operar_contas_pagar' permission
    
    The is_staff exception is intentional to support broad admin access.
    See: PERMISSION_STRUCTURE_AUDIT.md for security considerations.
    """
    return user.is_active and (
        user.is_superuser
        or user.is_staff
        or user.has_perm("processos.pode_operar_contas_pagar")
    )
```

**Pros:**
- Documents the current behavior
- No immediate code changes needed
- Preserves existing access patterns

**Cons:**
- Violates pure RBAC principle
- Creates implicit privilege escalation path

### Recommendation
**Choose Option A** (remove `is_staff`), but if organizational policy requires staff access:
- Use Option B (document)
- Then create a migration to explicitly assign `pode_operar_contas_pagar` permission to all staff users

---

## Phase 3: Implementation Steps

### Step 1: Create Migration (if keeping `is_staff`)
```python
# processos/migrations/0XXX_document_staff_backoffice_access.py
from django.db import migrations
from django.contrib.auth.models import Permission, Group, User

def assign_staff_permissions(apps, schema_editor):
    """Assign pode_operar_contas_pagar to all staff users."""
    permission = Permission.objects.get(
        codename='pode_operar_contas_pagar',
        content_type__app_label='processos'
    )
    for user in User.objects.filter(is_staff=True):
        user.user_permissions.add(permission)

class Migration(migrations.Migration):
    dependencies = [
        ('processos', '0079_add_verbas_rbac_permissions'),
    ]

    operations = [
        migrations.RunPython(assign_staff_permissions),
    ]
```

### Step 2: Update Code
- Implement either Option A or B in `security.py`
- Deploy with appropriate warning to administrators

### Step 3: Audit and Test
- Run `test_rbac.py` to verify no breakage
- Check logs for file download access denied errors
- Adjust permissions as needed for roles that legitimately need access

---

## Migration Checklist

- [ ] **Phase 1 Start:** Review which users currently use the app
- [ ] **Phase 1.1:** Remove `user_in_group()` and `group_required()` from `utils_permissoes.py`
- [ ] **Phase 1.2:** Update `processos/utils/__init__.py` exports
- [ ] **Phase 2:** Choose between Option A or B for `_is_cap_backoffice()`
- [ ] **Phase 3.1:** Create optional migration if needed
- [ ] **Phase 3.2:** Implement chosen security pattern
- [ ] **Phase 3.3:** Run tests: `python manage.py test processos.tests.test_rbac`
- [ ] **Phase 3.4:** Deploy and monitor file download access logs

---

## Testing Verification

After changes, verify with:

```bash
# Run RBAC tests
python manage.py test processos.tests.test_rbac -v 2

# Check for any remaining imports of removed functions
grep -r "group_required\|user_in_group" --include="*.py" processos/

# Verify @permission_required is used consistently
grep -r "@permission_required" --include="*.py" processos/views/ | wc -l
```

---

## Risk Assessment

| Task | Risk | Mitigation |
|------|------|-----------|
| Remove `group_required()` | **LOW** — Not used anywhere | Grep confirms zero usage |
| Remove `user_in_group()` | **LOW** — Not used anywhere | Grep confirms zero usage |
| Remove `is_staff` check | **MEDIUM** — Staff users may lose access | Document policy + test + monitor |
| Keep `is_staff` + Document | **LOW** — No code change, just docs | Add inline comment explaining policy |

---

## Schedule Recommendation

- **Week 1:** Decision on `is_staff` handling (Option A vs B)
- **Week 2:** Code review and PR creation
- **Week 3:** Testing in dev/staging
- **Week 4:** Deploy to production with monitoring

---

## References

- Audit Report: [PERMISSION_STRUCTURE_AUDIT.md](PERMISSION_STRUCTURE_AUDIT.md)
- Copilot Instructions: [.github/copilot-instructions.md](.github/copilot-instructions.md#L48)
- RBAC Test Suite: [processos/tests/test_rbac.py](processos/tests/test_rbac.py)
- Security Implementation: [processos/views/fluxo/security.py](processos/views/fluxo/security.py)
