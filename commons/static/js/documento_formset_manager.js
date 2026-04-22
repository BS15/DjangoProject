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
    this.containerSelector = `#document-list-${prefix}`;
    this.emptyFormSelector = `#empty-doc-form-${prefix}`;
    this.managementForm = `#id_${prefix}-TOTAL_FORMS`;
    this.badgeSelector = `#doc-count-badge-${prefix}`;
    this.dropzoneSelector = `#doc-dropzone-${prefix}`;
    this.dropInputSelector = `#drop-upload-input-${prefix}`;
    this.selectDropFilesBtnSelector = `#select-drop-files-${prefix}`;
    this.addDocRowBtnSelector = `.add-doc-row-btn[data-doc-prefix="${prefix}"]`;
    this.batchTypeSelectSelector = `#batch-doc-type-${prefix}`;
    this.batchFeedbackSelector = `#batch-doc-feedback-${prefix}`;
    this.batchApplyTypeSelector = `.batch-apply-type-btn[data-doc-prefix="${prefix}"]`;
    this.batchSelectAllSelector = `.batch-select-all-docs-btn[data-doc-prefix="${prefix}"]`;
    this.batchClearSelectionSelector = `.batch-clear-docs-btn[data-doc-prefix="${prefix}"]`;
    this.typeFieldSelector = 'select[name$="-tipo"]';
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

    $(this.containerSelector).on('change', 'input[type="file"][name$="-arquivo"]', (e) => {
      const row = $(e.target).closest('.document-row');
      const file = e.target.files && e.target.files[0] ? e.target.files[0] : null;
      this.ensureTipoSelection(row, file ? file.name : '');
      this.updateLocalPreviewButton(row, file);
    });

    $(document).on('click', this.addDocRowBtnSelector, (e) => {
      e.preventDefault();
      this.addDocument();
    });
  }

  bindBatchTypeControls() {
    $(document).on('click', this.batchSelectAllSelector, (e) => {
      e.preventDefault();
      this.getVisibleRows().find('.doc-batch-check').prop('checked', true);
      this.setBatchFeedback('');
    });

    $(document).on('click', this.batchClearSelectionSelector, (e) => {
      e.preventDefault();
      this.getVisibleRows().find('.doc-batch-check').prop('checked', false);
      this.setBatchFeedback('');
    });

    $(document).on('click', this.batchApplyTypeSelector, (e) => {
      e.preventDefault();
      const selectedType = $(this.batchTypeSelectSelector).val();
      if (!selectedType) {
        this.setBatchFeedback('Selecione um tipo de documento para aplicar em lote.', true);
        return;
      }
      const selectedRows = this.getSelectedRows();
      if (!selectedRows.length) {
        this.setBatchFeedback('Selecione ao menos um documento para aplicar o tipo em lote.', true);
        return;
      }
      selectedRows.each((_index, rowEl) => {
        const typeField = $(rowEl).find(this.typeFieldSelector).first();
        if (typeField.length) {
          typeField.val(selectedType).trigger('change');
        }
      });
      this.setBatchFeedback(`Tipo aplicado em ${selectedRows.length} documento(s).`);
    });
  }

  setBatchFeedback(message, isError = false) {
    const feedback = $(this.batchFeedbackSelector);
    if (!feedback.length) {
      return;
    }
    feedback.text(message || '');
    feedback.toggleClass('text-danger', Boolean(isError));
    feedback.toggleClass('text-muted', !isError);
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
      const originalEvent = e.originalEvent || {};
      const dataTransfer = originalEvent.dataTransfer || null;
      const files = dataTransfer ? dataTransfer.files : null;
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
    const startSearchIndex = Math.max(totalForms - 1, 0);
    const nextFormIndex = this.getNextFormIndex(startSearchIndex);

    if (!emptyForm.length || isNaN(totalForms) || nextFormIndex < 0) {
      return;
    }

    const newForm = emptyForm.clone();
    newForm.removeAttr('id');

    newForm.find('*').each(function () {
      const el = $(this);
      ['name', 'id', 'for'].forEach((attr) => {
        const value = el.attr(attr);
        if (value && value.includes('__prefix__')) {
          el.attr(attr, value.replace(/__prefix__/g, nextFormIndex));
        }
      });
    });

    newForm.attr('data-form-index', nextFormIndex);
    newForm.show();
    container.append(newForm);

    $(this.managementForm).val(Math.max(totalForms, nextFormIndex + 1));
    this.ensureTipoSelection(newForm, file ? file.name : '');

    if (file) {
      const fileInput = newForm.find(`input[type="file"][name="${this.prefix}-${nextFormIndex}-arquivo"]`);
      if (fileInput.length && typeof DataTransfer !== 'undefined') {
        try {
          const dt = new DataTransfer();
          dt.items.add(file);
          fileInput[0].files = dt.files;
          // Reusa o handler de `change` para centralizar `ensureTipoSelection` e
          // `updateLocalPreviewButton` no mesmo fluxo, evitando lógica duplicada.
          fileInput.trigger('change');
        } catch (error) {
          console.warn('Não foi possível vincular automaticamente o arquivo ao formulário.', error);
          this.setBatchFeedback(
            `Não foi possível anexar automaticamente "${file.name || 'arquivo'}". Selecione-o manualmente na linha criada.`,
            true,
          );
          this.updateLocalPreviewButton(newForm, file);
        }
      } else {
        this.setBatchFeedback(
          `Seu navegador não permitiu anexar automaticamente "${file.name || 'arquivo'}". Selecione-o manualmente na linha criada.`,
          true,
        );
        this.updateLocalPreviewButton(newForm, file);
      }
    }
    this.makeFormsetDraggable();
    this.syncOrderFields();
    this.updateDocumentCount();
  }

  getNextFormIndex(preferredIndex = 0) {
    const usedIndexes = new Set();
    const pattern = new RegExp(`^${this.prefix}-(\\d+)-`);
    $(this.containerSelector).find('[name]').each((_index, field) => {
      const fieldName = field.name || '';
      const match = fieldName.match(pattern);
      if (match) {
        usedIndexes.add(parseInt(match[1], 10));
      }
    });

    if (!usedIndexes.has(preferredIndex)) {
      return preferredIndex;
    }

    let candidate = preferredIndex + 1;
    while (usedIndexes.has(candidate)) {
      candidate += 1;
    }
    return candidate;
  }

  removeDocument(row) {
    this.clearLocalPreviewButton(row);
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
      if (e.originalEvent && e.originalEvent.dataTransfer) {
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
      const halfHeight = targetRect.height / DOC_DRAG_MIDPOINT_DIVISOR;
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

  ensureTipoSelection(row, fileName = '') {
    const selectTipo = row.find('select[name$="-tipo"]').first();
    if (!selectTipo.length || selectTipo.val()) {
      return;
    }

    const normalizedFileName = this.normalizeText(fileName || '');
    const preferredOption = selectTipo.find('option').filter((_, option) => {
      const value = (option.value || '').trim();
      if (!value) {
        return false;
      }
      const label = this.normalizeText(option.text || '');
      const hasOrcamentoHint = DOC_ORCAMENTO_FILENAME_HINTS
        .some((hint) => normalizedFileName.includes(hint));
      if (hasOrcamentoHint) {
        return label.includes(DOC_ORCAMENTO_LABEL_HINT);
      }
      return label.includes(DOC_DEFAULT_LABEL_HINT);
    }).first();

    if (preferredOption.length) {
      selectTipo.val(preferredOption.val());
      return;
    }

    const firstValidOption = selectTipo.find('option').filter((_, option) => (option.value || '').trim()).first();
    if (firstValidOption.length) {
      selectTipo.val(firstValidOption.val());
    }
  }

  updateLocalPreviewButton(row, file) {
    const previewBtn = row.find(`.doc-preview-btn[data-doc-prefix="${this.prefix}"]`).first();
    if (!previewBtn.length) {
      return;
    }

    this.revokePreviewBlobUrl(previewBtn);

    if (!file) {
      previewBtn.attr('data-doc-local-url', '');
      previewBtn.attr('data-doc-name', '');
      previewBtn.addClass('d-none');
      return;
    }

    const localUrl = URL.createObjectURL(file);
    previewBtn.attr('data-doc-local-url', localUrl);
    previewBtn.attr('data-doc-name', file.name || '');
    previewBtn.removeClass('d-none');
  }

  clearLocalPreviewButton(row) {
    const previewBtn = row.find(`.doc-preview-btn[data-doc-prefix="${this.prefix}"]`).first();
    if (!previewBtn.length) {
      return;
    }
    this.revokePreviewBlobUrl(previewBtn);
  }

  revokePreviewBlobUrl(previewBtn) {
    const localUrl = previewBtn.attr('data-doc-local-url');
    if (localUrl && localUrl.startsWith('blob:')) {
      URL.revokeObjectURL(localUrl);
      previewBtn.attr('data-doc-local-url', '');
    }
  }

  normalizeText(value) {
    return (value || '')
      .toString()
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
  }
}

const DOC_DRAG_MIDPOINT_DIVISOR = 2;
const DOC_ORCAMENTO_FILENAME_HINTS = ['empenho', 'orcament'];
const DOC_ORCAMENTO_LABEL_HINT = 'orcament';
const DOC_DEFAULT_LABEL_HINT = 'outro';

// Auto-initialize for common prefixes (optional convenience)
document.addEventListener('DOMContentLoaded', function() {
  // Check for presence of standard document formset containers
  ['documentos', 'docorc', 'docfiscal'].forEach(prefix => {
    if ($(`#document-list-${prefix}`).length) {
      window[`docManager_${prefix}`] = new DocumentoFormsetManager(prefix);
    }
  });
});
