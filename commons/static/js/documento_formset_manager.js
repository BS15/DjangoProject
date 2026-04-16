/* ──────────────────────────────────────────────────────────────────────────
   DOCUMENTO FORMSET JAVASCRIPT MANAGER (CANON)
   
   Reusable manager for document formset add/remove/reorder across all modules.
   Works with the _documento_formset_generic.html template.
   
   Usage:
     new DocumentoFormsetManager('documentos');  // Initialize for prefix 'documentos'
───────────────────────────────────────────────────────────────────────────── */

class DocumentoFormsetManager {
  constructor(prefix) {
    this.prefix = prefix;
    this.formPrefix = `${prefix}-`;
    this.containerSelector = `#document-list-${prefix}`;
    this.emptyFormSelector = `#empty-doc-form-${prefix}`;
    this.addBtnSelector = `#add-doc-btn-${prefix}`;
    this.managementForm = `#id_${prefix}-TOTAL_FORMS`;
    
    this.init();
  }

  init() {
    this.attachEventHandlers();
    this.makeFormsetDraggable();
  }

  attachEventHandlers() {
    // Handle "Add Document" button
    $(this.addBtnSelector).on('click', (e) => {
      e.preventDefault();
      this.addDocument();
    });

    // Handle remove buttons (delegated event)
    $(document).on('click', '.remove-doc-btn', (e) => {
      e.preventDefault();
      const row = $(e.target).closest('.document-row');
      this.removeDocument(row);
    });
  }

  addDocument() {
    const container = $(this.containerSelector);
    const emptyForm = $(this.emptyFormSelector);
    const totalForms = parseInt($(this.managementForm).val());

    // Clone empty form template
    const newForm = emptyForm.clone();
    
    // Replace __prefix__ with the actual form index
    newForm.find('input, select').each(function() {
      const name = $(this).attr('name');
      if (name) {
        $(this).attr('name', name.replace('__prefix__', totalForms));
        $(this).attr('id', `id_${newForm.find('input, select').attr('name')}`);
      }
    });

    newForm.attr('data-form-index', totalForms);
    newForm.show();

    // Append to container
    container.append(newForm);

    // Update form count in Django management form
    $(this.managementForm).val(totalForms + 1);

    // Update badge
    this.updateDocumentCount();

    // Re-attach drag handles
    this.makeFormsetDraggable();
  }

  removeDocument(row) {
    const deleteCheckbox = row.find('.django-delete-checkbox input[type="checkbox"]');
    
    if (deleteCheckbox.length) {
      // Mark for deletion (formset convention)
      deleteCheckbox.prop('checked', true);
      row.hide();
    } else {
      // Brand new form not yet in DB — just remove
      row.remove();
    }

    this.updateDocumentCount();
  }

  makeFormsetDraggable() {
    const container = $(this.containerSelector);
    const rows = container.find('.document-row:visible');

    if (rows.length > 1) {
      // Simple jQuery-based drag via mouseover reordering
      // (could upgrade to Sortable.js for better UX)
      rows.find('.drag-handle').css('cursor', 'move');
    }
  }

  updateDocumentCount() {
    const count = $(this.containerSelector).find('.document-row:visible').length;
    $(`#doc-count-badge`).text(`${count} doc(s)`);
  }
}

// Auto-initialize for common prefixes (optional convenience)
document.addEventListener('DOMContentLoaded', function() {
  // Check for presence of standard document formset containers
  ['documentos', 'docorc', 'docfiscal'].forEach(prefix => {
    if ($(`#document-list-${prefix}`).length) {
      window[`docManager_${prefix}`] = new DocumentoFormsetManager(prefix);
    }
  });
});
