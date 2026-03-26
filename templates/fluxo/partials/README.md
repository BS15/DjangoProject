# templates/fluxo/partials/

Shared HTML fragments (partials) for the **process creation** (`add_process.html`),
**process editing** (`editar_processo.html`), and the three **panel/processo detail**
workflow templates (conferência, contabilização, conselho fiscal).

---

## Original partials (process creation / editing)

| File | Purpose | Key parameters |
|------|---------|----------------|
| `_head_styles.html` | `<head>` meta tags, CDN links, and shared CSS | `page_title` |
| `_flash_messages.html` | Django `messages` alert loop | — |
| `_form_errors.html` | `processo_form` + `documento_formset` error list | — |
| `_pdf_viewer.html` | Left-column sticky PDF viewer card | `viewer_theme`, `viewer_placeholder_icon`, `viewer_placeholder_title`, `viewer_placeholder_text` |
| `_transferencia_block.html` | Bank-transfer (TED/DOC) sub-form | — |
| `_pix_block.html` | PIX key sub-form | — |
| `_empty_pendencia_form.html` | Hidden empty pendência row cloned by JS | — |
| `_modal_batch_tipo.html` | "Definir Tipo em Lote" Bootstrap modal | `batch_header_class`, `batch_confirm_class` |
| `_modal_preview_confirm.html` | Save-confirmation modal | — |

---

## Panel page partials (conferência / contabilização list views)

### `_painel_selecao_bar.html`
Bulk-selection action bar shown when ≥1 row is checked.

**Parameters** (via `{% with %}`):

| Parameter | Description | Example values |
|-----------|-------------|----------------|
| `bar_id` | HTML `id` of the bar `<div>` | `start-conferencia-bar` |
| `bar_color` | Bootstrap colour name | `success`, `primary` |
| `iniciar_url_name` | Django URL name for batch-start POST | `iniciar_conferencia` |
| `iniciar_label` | Start-button label text | `Iniciar Conferência` |

**Context** (already in view context): `pode_interagir`

```django
{% with bar_id="start-conferencia-bar"
        bar_color="success"
        iniciar_url_name="iniciar_conferencia"
        iniciar_label="Iniciar Conferência" %}
    {% include "fluxo/partials/_painel_selecao_bar.html" %}
{% endwith %}
```

---

### `_painel_js_selecao.html`
Row-selection JavaScript that powers the selection bar.

**Parameters** (via `{% with %}`):

| Parameter | Description |
|-----------|-------------|
| `js_bar_id` | HTML `id` of the selection bar element |

```django
{% with js_bar_id="start-conferencia-bar" %}
    {% include "fluxo/partials/_painel_js_selecao.html" %}
{% endwith %}
```

---

## Processo detail partials (conferência / contabilização / conselho fiscal)

### `_processo_info_card.html`
"Informações do Processo" card — process metadata in a 2-column grid.

**Parameters** (via `{% with %}`):

| Parameter | Description | Example values |
|-----------|-------------|----------------|
| `badge_color` | Bootstrap colour for status badge | `success`, `primary`, `info` |
| `value_color` | Bootstrap text-colour for Valor Líquido | `text-success`, `text-primary`, `text-info` |

**Context**: `processo`

```django
{% with badge_color="success" value_color="text-success" %}
    {% include "fluxo/partials/_processo_info_card.html" %}
{% endwith %}
```

---

### `_processo_doc_formset.html`
Editable documents formset with drag-to-reorder and add/remove functionality.

**Parameters** (via `{% with %}`):

| Parameter | Description | Example values |
|-----------|-------------|----------------|
| `add_btn_class` | Bootstrap button variant for "Adicionar Documento" | `btn-outline-success`, `btn-outline-primary` |

**Context**: `doc_formset`, `tipos_documento`, `pode_interagir`, `processo`

```django
{% with add_btn_class="btn-outline-success" %}
    {% include "fluxo/partials/_processo_doc_formset.html" %}
{% endwith %}
```

---

### `_processo_doc_readonly.html`
Read-only documents list (no formset — used by Conselho Fiscal view).

**Context**: `processo`

```django
{% include "fluxo/partials/_processo_doc_readonly.html" %}
```

---

### `_processo_pendencias_formset.html`
Editable pendências formset with add/remove and dynamic tipo-select population.

**Context**: `pendencia_formset`, `pode_interagir`, `processo`

```django
{% include "fluxo/partials/_processo_pendencias_formset.html" %}
```

---

### `_processo_pendencias_readonly.html`
Read-only pendências list (no formset — used by Conselho Fiscal view).

**Context**: `processo`

```django
{% include "fluxo/partials/_processo_pendencias_readonly.html" %}
```

---

### `_processo_history_card.html`
Collapsible history/audit-log card — identical markup in all three process detail templates.

**Context**: `history_records` (list of history record objects)

```django
{% include "fluxo/partials/_processo_history_card.html" %}
```

---

### `_processo_contingencias_card.html`
Collapsible contingências card — identical markup in all three process detail templates.

**Context**: `contingencias` (list of Contingencia objects)

```django
{% include "fluxo/partials/_processo_contingencias_card.html" %}
```

---

### `_processo_rejeitar_modal.html`
Bootstrap modal for returning/rejecting a process.

**Parameters** (via `{% with %}`):

| Parameter | Description | conferência→Contabilização | Conselho→Contabilização |
|-----------|-------------|---------------------------|------------------------|
| `rejeitar_modal_title` | Modal header (processo id appended automatically) | `Devolver Processo` | `Recusar Contas — Processo` |
| `rejeitar_modal_body` | Explanatory text | `Informe o erro…` | `Aponte a inconsistência…` |
| `rejeitar_label_tipo` | Label for tipo field | `Tipo de Pendência` | `Tipo de Apontamento` |
| `rejeitar_label_descricao` | Label for description field | `Descrição do Erro` | `Despacho / Justificativa` |
| `rejeitar_confirm_label` | Submit button label | `Confirmar Devolução` | `Registrar Recusa` |

**Context**: `processo`, `pendencia_form`, `pode_interagir`

```django
{% with rejeitar_modal_title="Devolver Processo"
        rejeitar_modal_body="Informe o erro que impede a contabilização. O processo retornará à Conferência."
        rejeitar_label_tipo="Tipo de Pendência"
        rejeitar_label_descricao="Descrição do Erro"
        rejeitar_confirm_label="Confirmar Devolução" %}
    {% include "fluxo/partials/_processo_rejeitar_modal.html" %}
{% endwith %}
```

---

### `_processo_formset_js.html`
Shared JavaScript for:
1. Connecting action buttons (Confirmar/Aprovar, Salvar, Pular, Voltar) to the main form submission.
2. Dynamically adding/removing document rows from the formset.
3. Dynamically adding/removing pendência rows from the formset.

**Parameters** (via `{% with %}`):

| Parameter | Description | conferência | contabilização |
|-----------|-------------|-------------|----------------|
| `js_form_id` | `id` of the main `<form>` | `conferencia-form` | `contabilizacao-form` |
| `js_primary_btn` | `id` of the primary action button | `btn-confirmar` | `btn-aprovar` |
| `js_primary_action` | `action` value that triggers confirmation | `confirmar` | `aprovar` |
| `js_confirm_msg_prefix` | Text before process id in confirm() | `Confirmar a conferência e enviar o Processo #` | `Confirmar a contabilização e enviar o Processo #` |
| `js_confirm_msg_suffix` | Text after process id in confirm() | ` para Contabilização?` | ` para o Conselho Fiscal?` |

**Context**: `processo`

```django
{% with js_form_id="conferencia-form"
        js_primary_btn="btn-confirmar"
        js_primary_action="confirmar"
        js_confirm_msg_prefix="Confirmar a conferência e enviar o Processo #"
        js_confirm_msg_suffix=" para Contabilização?" %}
    {% include "fluxo/partials/_processo_formset_js.html" %}
{% endwith %}
```

---

## Conventions

- Partials are **"dumb"** — they render context variables as-is and contain
  minimal conditional logic.
- Page-specific behaviour (colours, extra fields, JS hooks) lives in the
  parent template that includes each partial.
- All partials consume variables already present in the Django view context;
  no extra view changes are required.
- Parameters are passed via `{% with %}` blocks as documented above.
