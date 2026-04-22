/* ──────────────────────────────────────────────────────────────────────────
   DOCUMENTO FORMSET JAVASCRIPT MANAGER (CANON)
   
   Reusable manager for document formset add/remove/reorder across all modules.
   Works with the _documento_formset_generic.html template.
   
   Usage:
     new DocumentoFormsetManager('documentos');  // Initialize for prefix 'documentos'
───────────────────────────────────────────────────────────────────────────── */

class DocumentoFormsetManager {
  static DRAG_MIDPOINT_DIVISOR = 2;

  constructor(prefix) {
    this.prefix = prefix;
    this.containerSelector = `#document-list-${prefix}`;
    this.emptyFormSelector = `#empty-doc-form-${prefix}`;
    this.managementForm = `#id_${prefix}-TOTAL_FORMS`;
    this.badgeSelector = `#doc-count-badge-${prefix}`;
    this.dropzoneSelector = `#doc-dropzone-${prefix}`;
    this.dropInputSelector = `#drop-upload-input-${prefix}`;
    this.selectDropFilesBtnSelector = `#select-drop-files-${prefix}`;
    this.batchTypeSelectSelector = `#batch-doc-type-${prefix}`;
    this.batchApplyTypeSelector = `.batch-apply-type-btn[data-doc-prefix="${prefix}"]`;
    this.batchSelectAllSelector = `.batch-select-all-docs-btn[data-doc-prefix="${prefix}"]`;
    this.batchClearSelectionSelector = `.batch-clear-docs-btn[data-doc-prefix="${prefix}"]`;
    this.draggedRow = null;
    
    this.init();
  }

  init() {
    if (!$(this.containerSelector).length) {
      return;
    }
    this.attachEventHandlers();
    this.bindDropzone();
    this.bindBatchTypeControls();
    this.makeFormsetDraggable();
    this.syncOrderFields();
    this.updateDocumentCount();
  }

  attachEventHandlers() {
    $(this.containerSelector).on('click', '.remove-doc-btn', (e) => {
      e.preventDefault();
      const row = $(e.target).closest('.document-row');
      this.removeDocument(row);
    });
  }

  bindBatchTypeControls() {
    $(document).on('click', this.batchSelectAllSelector, (e) => {
      e.preventDefault();
      this.getVisibleRows().find('.doc-batch-check').prop('checked', true);
    });

    $(document).on('click', this.batchClearSelectionSelector, (e) => {
      e.preventDefault();
      this.getVisibleRows().find('.doc-batch-check').prop('checked', false);
    });

    $(document).on('click', this.batchApplyTypeSelector, (e) => {
      e.preventDefault();
      const selectedType = $(this.batchTypeSelectSelector).val();
      if (!selectedType) {
        return;
      }
      const selectedRows = this.getSelectedRows();
      if (!selectedRows.length) {
        return;
      }
      selectedRows.each((_, rowEl) => {
        const typeField = $(rowEl).find('select[name$="-tipo"]').first();
        if (typeField.length) {
          typeField.val(String(selectedType)).trigger('change');
        }
      });
    });
  }

  bindDropzone() {
    const dropzone = $(this.dropzoneSelector);
    const input = $(this.dropInputSelector);
    const selectBtn = $(this.selectDropFilesBtnSelector);

    if (!dropzone.length || !input.length || !selectBtn.length) {
      return;
    }

    selectBtn.on('click', (e) => {
      e.preventDefault();
      input.trigger('click');
    });

    input.on('change', (e) => {
      this.addFiles(e.target.files);
      e.target.value = '';
    });

    dropzone.on('dragenter dragover', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.addClass('border-primary');
    });

    dropzone.on('dragleave', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.removeClass('border-primary');
    });

    dropzone.on('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.removeClass('border-primary');
      const files = e.originalEvent?.dataTransfer?.files;
      this.addFiles(files);
    });
  }

  addFiles(fileList) {
    if (!fileList || !fileList.length) {
      return;
    }
    Array.from(fileList).forEach((file) => this.addDocument({ file }));
  }

  addDocument({ file = null } = {}) {
    const container = $(this.containerSelector);
    const emptyForm = $(this.emptyFormSelector);
    const totalForms = parseInt($(this.managementForm).val(), 10);

    if (!emptyForm.length || isNaN(totalForms)) {
      return;
    }

    const newForm = emptyForm.clone();
    newForm.removeAttr('id');

    newForm.find('*').each(function () {
      const el = $(this);
      ['name', 'id', 'for'].forEach((attr) => {
        const value = el.attr(attr);
        if (value && value.includes('__prefix__')) {
          el.attr(attr, value.replace(/__prefix__/g, totalForms));
        }
      });
    });

    newForm.attr('data-form-index', totalForms);
    newForm.show();
    container.append(newForm);

    $(this.managementForm).val(totalForms + 1);
    if (file) {
      const fileInput = newForm.find(`input[type="file"][name="${this.prefix}-${totalForms}-arquivo"]`);
      if (fileInput.length && typeof DataTransfer !== 'undefined') {
        try {
          const dt = new DataTransfer();
          dt.items.add(file);
          fileInput[0].files = dt.files;
        } catch (error) {
          console.warn('Não foi possível vincular automaticamente o arquivo ao formulário.', error);
        }
      }
    }
    this.makeFormsetDraggable();
    this.syncOrderFields();
    this.updateDocumentCount();
  }

  removeDocument(row) {
    const deleteCheckbox = row.find('.django-delete-checkbox input[type="checkbox"]');
    
    if (deleteCheckbox.length) {
      // Mark for deletion (formset convention)
      deleteCheckbox.prop('checked', true);
      row.hide();
    } else {
      row.remove();
    }

    this.syncOrderFields();
    this.updateDocumentCount();
  }

  makeFormsetDraggable() {
    const container = $(this.containerSelector);
    const rows = container.find('.document-row');

    rows.each((_, rowEl) => {
      const row = $(rowEl);
      const handle = row.find('.drag-handle').first();
      if (!handle.length) {
        return;
      }
      handle.css('cursor', 'grab');
      if (!row.data('drag-bound')) {
        row.attr('draggable', true);
        row.data('drag-bound', true);
      }
    });

    if (container.data('drag-container-bound')) {
      return;
    }

    container.data('drag-container-bound', true);

    container.on('dragstart', '.document-row', (e) => {
      const isHandle = $(e.target).closest('.drag-handle').length > 0;
      if (!isHandle) {
        e.preventDefault();
        return;
      }
      this.draggedRow = e.currentTarget;
      if (e.originalEvent?.dataTransfer) {
        e.originalEvent.dataTransfer.effectAllowed = 'move';
        // Browser DnD APIs require non-empty drag data in some engines.
        const dragToken = this.draggedRow.dataset.docId
          || this.draggedRow.dataset.formIndex
          || `new-${Date.now()}`;
        e.originalEvent.dataTransfer.setData('text/plain', dragToken);
      }
      $(this.draggedRow).addClass('opacity-50');
    });

    container.on('dragend', '.document-row', () => {
      if (this.draggedRow) {
        $(this.draggedRow).removeClass('opacity-50');
      }
      this.draggedRow = null;
      this.syncOrderFields();
    });

    container.on('dragover', '.document-row', (e) => {
      e.preventDefault();
      if (!this.draggedRow || this.draggedRow === e.currentTarget) {
        return;
      }
      const target = e.currentTarget;
      const targetRect = target.getBoundingClientRect();
      const halfHeight = targetRect.height / DocumentoFormsetManager.DRAG_MIDPOINT_DIVISOR;
      const shouldInsertAfter = e.originalEvent.clientY > targetRect.top + halfHeight;

      if (shouldInsertAfter) {
        target.parentNode.insertBefore(this.draggedRow, target.nextSibling);
      } else {
        target.parentNode.insertBefore(this.draggedRow, target);
      }
    });
  }

  getVisibleRows() {
    return $(this.containerSelector).find('.document-row:visible');
  }

  getSelectedRows() {
    return this.getVisibleRows().filter((_, rowEl) => {
      const row = $(rowEl);
      return row.find('.doc-batch-check').is(':checked');
    });
  }

  syncOrderFields() {
    this.getVisibleRows().each((index, rowEl) => {
      const orderInput = $(rowEl).find('input[name$="-ordem"]').first();
      if (orderInput.length) {
        orderInput.val(index + 1);
      }
    });
  }

  updateDocumentCount() {
    const count = this.getVisibleRows().length;
    $(this.badgeSelector).text(`${count} doc(s)`);
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
