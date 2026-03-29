# Copilot Instructions — Financial & Administrative Backoffice System

You are an Expert Django Developer assisting in the development of a **Financial and Administrative Backoffice System** for a Brazilian Public Administration entity (Conselho).

---

## 1. Domain Knowledge (Public Administration)

The system strictly models Brazilian public budget execution and document management. You must understand these core concepts:

- **Strict State Machine:** Processes move through rigid stages:
  `A EMPENHAR` → `AGUARDANDO LIQUIDAÇÃO` → `A PAGAR` → `PAGO` → `CONTABILIZADO` → `ARQUIVADO`
- **Immutability & Audit:** Public money requires strict auditing. Do not delete records or files once they are in advanced stages. Use `django-simple-history` for audit trails.
- **Turnpike Pattern:** Transitions between states are guarded by strict validation rules (e.g., a process cannot move to `A PAGAR` without an attested *Nota Fiscal*).
- **Key Workflows:**
  - *Processos de Pagamento:* Standard invoice payments.
  - *Verbas Indenizatórias:* Diárias (Per Diems), Jetons, Reembolsos, and Auxílios.
  - *Suprimentos de Fundos:* Petty cash/advance funds, which require a strict "Prestação de Contas" (Accountability) closure phase before finalizing the process value.
- **External Integrations:** SISCAC (banking/budget system) and Autentique (Digital Signatures).

---

## 2. Tech Stack & Architecture

- **Backend:** Django (Python)
- **Database:** PostgreSQL (Cloud/Production) / SQLite (Local/Dev)
- **Frontend:** Vanilla Bootstrap 5, standard Django Templates, minimal jQuery (mainly for input masking like CPF/CNPJ/Currency). No heavy JS frameworks (React/Vue/Angular).

### Template Architecture (Strict 3-Tier Rule)

| Tier | Role | Example |
|------|------|---------|
| **Tier 1 (Master)** | `base.html` — generic layout and sidebar | `templates/base.html` |
| **Tier 2 (Archetypes)** | Reusable layout shells | `layouts/base_list.html`, `layouts/base_form.html`, `layouts/base_review.html`, `layouts/base_detail.html`, `layouts/base_batch.html` |
| **Tier 3 (Leaves)** | Specific views (e.g., `diarias_list.html`) that **must** extend a Tier 2 archetype and only inject data into specific blocks (`{% block filter_form %}`, `{% block table_rows %}`) | `fluxo/diarias_list.html` |

> **Rule:** Never write standalone boilerplate HTML in leaf templates. Always extend the appropriate Tier 2 archetype.

---

## 3. Development Philosophy & Baselines

- **Function Over Form:** Prioritize highly functional, fast, and simple code over aesthetic complexity. Use standard Bootstrap utility classes; avoid writing custom CSS unless absolutely necessary.
- **Deterministic Over AI:** For tasks like data extraction (e.g., Febraban barcodes), rely strictly on deterministic algorithms, Regex, or specialized libraries — not LLM inference.
- **Single Responsibility Principle:** Keep `views.py` clean:
  - Move non-operational logic (e.g., fake data generators) to separate files (e.g., `desenvolvedor.py`).
  - Move complex business rules to `utils.py` or model methods.
- **Robust Security (RBAC):**
  - All views are globally protected by a Login Middleware. **Do not** use `@login_required`.
  - **Do not** use brittle `@group_required` decorators.
  - Always secure views using Django's permission framework: `@permission_required('app_label.permission_name', raise_exception=True)`.

---

## 4. Implementation Rules

When asked to create or refactor a feature:

1. **Never write raw IDs:** When tracking foreign keys or history, always resolve IDs to their human-readable `__str__` representations.
2. **Forms & Masks:** All Data Entry forms must extend `layouts/base_form.html` so they automatically inherit global jQuery masking for Brazilian currency (R$), CPFs, CNPJs, and Phone numbers.
3. **Database Constraints:** Always respect database constraints (like required `status` foreign keys). Never leave an object in an invalid state before calling `.save()`.
4. **DRY Filters:** Do not duplicate `FilterSet`s. Consolidate filters by model and utilize `RangeFilter` for all dates and monetary values.
