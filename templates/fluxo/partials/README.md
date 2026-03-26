# templates/fluxo/partials/

Shared HTML fragments (partials) for the **process creation** (`add_process.html`)
and **process editing** (`editar_processo.html`) templates.

## Files

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

## Usage

Pass parameters with `{% with %}`:

```django
{% with viewer_theme="primary"
        viewer_placeholder_icon="bi-file-earmark-arrow-up"
        viewer_placeholder_title="Nenhum documento selecionado"
        viewer_placeholder_text="Faça o upload de um PDF à direita." %}
    {% include "fluxo/partials/_pdf_viewer.html" %}
{% endwith %}
```

## Conventions

- Partials are **"dumb"** — they render context variables as-is and contain
  minimal conditional logic.
- Page-specific behaviour (colours, extra fields, JS hooks) lives in the
  parent template that includes each partial.
- All partials consume variables already present in the Django view context;
  no extra view changes are required.
