# Modular RBAC Permission Structure (2026-04)

## Overview

Each app now defines and uses its own permissions for RBAC. All @permission_required decorators, admin, and custom checks reference only their app's permissions.

---

## Permissions by App

### suprimentos
- `suprimentos.acesso_backoffice`: Acesso ao backoffice de suprimentos

### verbas_indenizatorias
- `verbas_indenizatorias.pode_visualizar_verbas`: Pode visualizar verbas indenizatórias
- `verbas_indenizatorias.pode_gerenciar_jetons`: Pode gerenciar jetons
- `verbas_indenizatorias.pode_agrupar_verbas`: Pode agrupar verbas indenizatórias
- `verbas_indenizatorias.pode_gerenciar_processos_verbas`: Pode gerenciar processos de verbas
- `verbas_indenizatorias.pode_gerenciar_auxilios`: Pode gerenciar auxílios
- `verbas_indenizatorias.pode_gerenciar_reembolsos`: Pode gerenciar reembolsos
- `verbas_indenizatorias.pode_autorizar_diarias`: Pode autorizar diárias
- `verbas_indenizatorias.pode_importar_diarias`: Pode importar diárias
- `verbas_indenizatorias.pode_criar_diarias`: Pode criar diárias
- `verbas_indenizatorias.pode_gerenciar_diarias`: Pode gerenciar diárias

### fiscal
- `fiscal.acesso_backoffice`: Acesso ao backoffice fiscal

---

## Migration Notes
- All views previously using fluxo.* permissions now reference their own app's permissions.
- Permissions are defined in the main model's Meta class in each app.
- No permissions were removed from fluxo; legacy references remain for backward compatibility.
- User/group assignments must be updated to grant new app-specific permissions as needed.

---

## How to Add New Permissions
- Add to the `permissions` list in the Meta class of the relevant model.
- Use the pattern: `app_label.permission_codename`.

---

## How to Check Permissions
- Use `@permission_required('app_label.permission_codename', raise_exception=True)` in views.
- For custom checks: `request.user.has_perm('app_label.permission_codename')`

---

## Contact
- For RBAC or permission issues, contact the system administrator or development team.
