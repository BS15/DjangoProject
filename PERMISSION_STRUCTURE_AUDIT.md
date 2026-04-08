# Permission Structure Audit

**Date:** 2026-04-07  
**Status:** ⚠️ Found superseded functions that should be removed or deprecated

---

## Summary

The codebase has **evolved** from a group-based approach (`@group_required`) to a **permission-based RBAC approach** (`@permission_required`). However, **old utilities remain in place** and are no longer used, creating potential confusion and maintenance debt.

---

## 1. Superseded & Unused Functions

### ❌ `group_required()` Decorator
**Location:** [`processos/utils/utils_permissoes.py:14-26`](processos/utils/utils_permissoes.py#L14)

- **Status:** SUPERSEDED ✗
- **Exports:** Exported in [`processos/utils/__init__.py:60`](processos/utils/__init__.py#L60) and listed in `__all__`
- **Usage:** NOT USED anywhere in the codebase (no calls found)
- **Why SuperSeded:** [Copilot Instructions](/.github/copilot-instructions.md#L50) explicitly states: **"Do not use brittle `@group_required` decorators"**
- **Replacement Pattern:** Use `@permission_required('app_label.permission_name', raise_exception=True)` instead

### ⚠️ `user_in_group()` Function
**Location:** [`processos/utils/utils_permissoes.py:5-11`](processos/utils/utils_permissoes.py#L5)

- **Status:** UNUSED (only exported)
- **Exports:** Exported in [`processos/utils/__init__.py:60`](processos/utils/__init__.py#L60)
- **Usage:** NOT USED anywhere in the codebase
- **Recommendation:** Remove or mark as deprecated

---

## 2. Questionable Security Function

### 🔍 `_is_cap_backoffice()` Function
**Location:** [`processos/views/fluxo/security.py:22-27`](processos/views/fluxo/security.py#L22)

```python
def _is_cap_backoffice(user):
    """Retorna True para perfis de backoffice autorizados."""
    return user.is_active and (
        user.is_superuser
        or user.is_staff
        or user.has_perm("processos.pode_operar_contas_pagar")
    )
```

**⚠️ CONCERN:** The `user.is_staff` check grants broad access to anyone marked as staff.

- **Usage:** Only called once in [`processos/views/fluxo/security.py:119`](processos/views/fluxo/security.py#L119) within `download_arquivo_seguro()`
- **Issue:** Combines implicit staff privileges with explicit permission checks, which violates RBAC principle
- **Recommendation:** 
  - Either remove the `user.is_staff` check (enforce permissions explicitly)
  - Or document why staff should have automatic CAP access

---

## 3. Current Implementation Pattern (✅ CORRECT)

The bulk of the codebase correctly uses the modern RBAC pattern:

### Pattern Example 1: Views Directory
```python
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def add_process_view(request):
    ...
```

**Files Using This Pattern:**
- ✅ [`processos/views/cadastros.py`](processos/views/cadastros.py) (Multiple uses)
- ✅ [`processos/views/fluxo/pre_payment/cadastro/forms.py`](processos/views/fluxo/pre_payment/cadastro/forms.py)
- ✅ [`processos/views/fluxo/payment/comprovantes/actions.py`](processos/views/fluxo/payment/comprovantes/actions.py)
- ✅ [`processos/views/fluxo/post_payment/conselho/actions.py`](processos/views/fluxo/post_payment/conselho/actions.py)
- ✅ [`processos/views/fluxo/post_payment/contabilizacao/actions.py`](processos/views/fluxo/post_payment/contabilizacao/actions.py)
- ✅ [`processos/views/verbas/tipos/diarias/actions.py`](processos/views/verbas/tipos/diarias/actions.py)
- ✅ And many more...

### Pattern Example 2: Defined Permissions (Migration)
```python
# From processos/migrations/0079_add_verbas_rbac_permissions.py
options={'permissions': [
    ('acesso_backoffice', 'Pode acessar as telas gerais do sistema financeiro'),
    ('pode_operar_contas_pagar', 'Pode empenhar, triar notas e fazer conferência'),
    ('pode_atestar_liquidacao', 'Pode atestar notas fiscais (Fiscal do Contrato)'),
    ...
]}
```

---

## 4. Inline Permission Checks

**Good pattern also used (for special cases):**

Location: [`processos/views/fluxo/auditing.py:56-62`](processos/views/fluxo/auditing.py#L56)

```python
def api_processo_detalhes(request):
    """Retorna detalhes de um processo por ``id`` informado via query string."""
    if not (
        request.user.has_perm("processos.pode_auditar_conselho")
        or request.user.has_perm("processos.acesso_backoffice")
    ):
        raise PermissionDenied
```

This is acceptable for views that need **multiple permission options**.

---

## 5. Test Coverage

**RBAC test file exists:**  
[`processos/tests/test_rbac.py`](processos/tests/test_rbac.py)

- ✅ Tests middleware authorization
- ✅ Tests permission-denied scenarios
- ✅ Tests successful access with correct permissions
- ✅ Validates that `raise_exception=True` is used on all decorators

---

## Recommendations (Action Items)

### Priority 1: Remove Superseded Functions
- [ ] Remove `group_required()` from [`processos/utils/utils_permissoes.py`](processos/utils/utils_permissoes.py)
- [ ] Remove `user_in_group()` from [`processos/utils/utils_permissoes.py`](processos/utils/utils_permissoes.py)
- [ ] Update exports in [`processos/utils/__init__.py`](processos/utils/__init__.py)

### Priority 2: Review `_is_cap_backoffice()` Security
- [ ] Decide: Does `user.is_staff` deserve blanket access?
- [ ] If yes: Document this policy in a code comment
- [ ] If no: Replace with explicit permission check (`user.has_perm("processos.pode_operar_contas_pagar")`)

### Priority 3: Consistency Check
- [ ] Audit all views in `processos/views/` to ensure **100% use** `@permission_required()` or inline `has_perm()` checks
- [ ] Verify no hardcoded group checks like `.groups.filter(name="...").exists()` except where documented

---

## File Locations Reference

| File | Purpose | Status |
|------|---------|--------|
| [.github/copilot-instructions.md](.github/copilot-instructions.md) | Architecture guidelines | ✅ Current guidance |
| [processos/utils/utils_permissoes.py](processos/utils/utils_permissoes.py) | Old permission utilities | ❌ Superseded |
| [processos/utils/__init__.py](processos/utils/__init__.py) | Public API exports | ⚠️ Exports unused |
| [processos/views/fluxo/security.py](processos/views/fluxo/security.py) | File download security | ⚠️ Has `is_staff` check |
| [processos/migrations/0053_add_rbac_permissions.py](processos/migrations/0053_add_rbac_permissions.py) | RBAC permission definitions | ✅ Current system |
| [processos/tests/test_rbac.py](processos/tests/test_rbac.py) | RBAC security tests | ✅ Validates patterns |

---

## Conclusion

**✅ The codebase is mostly aligned with modern RBAC patterns** using `@permission_required()` throughout.

**❌ But technical debt remains:**
1. Old `group_required()` and `user_in_group()` functions unused but exported
2. `_is_cap_backoffice()` has implicit `is_staff` bypass that may violate RBAC principles
3. These could confuse future developers into using deprecated patterns

**📋 Suggested next steps:** Remove superseded functions and rationalize `_is_cap_backoffice()`.
