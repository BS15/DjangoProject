/**
 * static/js/process_form.js
 *
 * Shared JavaScript for the process-creation (add_process) and
 * process-editing (editar_processo) pages.
 *
 * Completely rebuilt for robustness:
 *  - All hook calls are wrapped in try/catch so page-specific errors
 *    never abort the shared initialisation.
 *  - Every DOM query is null-guarded before use.
 *  - No forward references to page-specific functions.
 *
 * ── Extension hooks ────────────────────────────────────────────────────────
 * Each page may define `window.processFormHooks` BEFORE this file is loaded:
 *
 *   window.processFormHooks = {
 *     beforeSubmit(e)            → return false to abort submission
 *     onFormaPagamentoChanged(ehBoleto)
 *     onDocumentRemoved()
 *     onFileSelected(fileInput)
 *   };
 *
 * ── Data attributes ─────────────────────────────────────────────────────────
 * #processForm
 *   data-somente-docs="true|false"
 *
 * select#id_processo-tipo_pagamento
 *   data-api-tipos-url="…"  – overrides /api/documentos-por-pagamento/
 *
 * #dropzone-area
 *   data-active-class="bg-primary"
 *
 * #btn-processar-boleto
 *   data-api-boleto-url="…"
 */

/* ═══════════════════════════════════════════════════════════════════════════
   GLOBAL UTILITY FUNCTIONS (callable from onclick="…" HTML attributes)
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Display a PDF (File object or secure-download URL) in the viewer iframe.
 */
function loadPdfIntoViewer(source) {
    var viewer      = document.getElementById('pdf-viewer');
    var placeholder = document.getElementById('pdf-placeholder');
    if (!viewer || !placeholder) return;

    if (typeof source === 'string') {
        viewer.src = source;
    } else if (source && source.type === 'application/pdf') {
        viewer.src = URL.createObjectURL(source);
    } else {
        alert('Apenas arquivos PDF podem ser visualizados no painel.');
        return;
    }
    viewer.style.display = 'block';
    placeholder.style.display = 'none';
}

/**
 * Copy a barcode string to the clipboard; briefly shows a tick icon.
 * Called via onclick="copiarCodigoBarras(this)" with data-code on the button.
 */
function copiarCodigoBarras(btn) {
    var code = btn.dataset.code;
    if (!code) return;
    navigator.clipboard.writeText(code).then(function () {
        var orig = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check2"></i>';
        setTimeout(function () { btn.innerHTML = orig; }, 2000);
    });
}

/**
 * Populate the #previewModal before showing the save-confirmation dialog.
 * Called from onclick="check_information_alert()" on the "Salvar" button.
 */
window.check_information_alert = function () {
    var credorEl   = document.getElementById('id_processo-credor');
    var prevCreedor = document.getElementById('prev_credor');
    var prevVal     = document.getElementById('prev_val');

    if (credorEl && credorEl.selectedIndex >= 0 && prevCreedor) {
        prevCreedor.innerText = credorEl.options[credorEl.selectedIndex].text;
    } else if (prevCreedor) {
        prevCreedor.innerText = '---';
    }

    var valEl = document.getElementById('id_processo-valor_liquido');
    if (prevVal) prevVal.innerText = valEl ? valEl.value : '0,00';
};

/* ═══════════════════════════════════════════════════════════════════════════
   DOM-READY INITIALISATION
   ═══════════════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', function () {

    /* ── Shared state ──────────────────────────────────────────────────── */
    var processForm        = document.getElementById('processForm');
    var somenteDocs        = processForm && processForm.dataset.somenteDocs === 'true';
    var docTotalInput      = document.getElementById('id_documento-TOTAL_FORMS');
    var containerDocumentos = document.getElementById('document-list');
    var hooks              = window.processFormHooks || {};

    /* ── Safe hook caller: errors in page-specific hooks never crash shared init ── */
    function callHook(name /*, …args */) {
        if (typeof hooks[name] !== 'function') return undefined;
        try {
            var args = Array.prototype.slice.call(arguments, 1);
            return hooks[name].apply(null, args);
        } catch (e) {
            /* hook error isolated — log to console but do not propagate */
            if (typeof console !== 'undefined') console.warn('processFormHooks.' + name + ' error:', e);
        }
    }

    /* ── FORM SUBMIT ───────────────────────────────────────────────────── */
    if (processForm) {
        processForm.addEventListener('submit', function (e) {
            /* Page-specific validation — return false to abort */
            var ok = callHook('beforeSubmit', e);
            if (ok === false || e.defaultPrevented) return;

            /* Clean up and re-index document rows before submission */
            if (containerDocumentos) {
                containerDocumentos.querySelectorAll('.document-row').forEach(function (row) {
                    if (row.style.display === 'none') return;
                    var fileInput = row.querySelector('input[type="file"]');
                    var displayEl = row.querySelector('.doc-filename-display');
                    var hasSaved  = displayEl && displayEl.innerText.trim() !== '';
                    if (!fileInput || (fileInput.files.length === 0 && !hasSaved)) {
                        var idInput = row.querySelector('input[type="hidden"][name$="-id"]');
                        if (!idInput || !idInput.value) row.remove();
                    }
                });
                var remaining = containerDocumentos.querySelectorAll('.document-row');
                remaining.forEach(function (row, i) {
                    row.querySelectorAll('input, select').forEach(function (el) {
                        if (el.name) el.name = el.name.replace(/-\d+-/, '-' + i + '-');
                        if (el.id)   el.id   = el.id.replace(/-\d+-/, '-' + i + '-');
                    });
                });
                var totalDocEl = document.getElementById('id_documento-TOTAL_FORMS');
                if (totalDocEl) totalDocEl.value = remaining.length;
            }

            /* Clean up and re-index pendência rows before submission */
            var penList = document.getElementById('pendencia-list');
            if (penList) {
                penList.querySelectorAll('.pendencia-row').forEach(function (row) {
                    if (row.style.display === 'none') return;
                    var descInput = row.querySelector('input[name$="-descricao"]');
                    if (!descInput || !descInput.value.trim()) {
                        var idInput = row.querySelector('input[type="hidden"][name$="-id"]');
                        if (!idInput || !idInput.value) row.remove();
                    }
                });
                var remainingPen = penList.querySelectorAll('.pendencia-row');
                remainingPen.forEach(function (row, i) {
                    row.querySelectorAll('input, select').forEach(function (el) {
                        if (el.name) el.name = el.name.replace(/-\d+-/, '-' + i + '-');
                        if (el.id)   el.id   = el.id.replace(/-\d+-/, '-' + i + '-');
                    });
                });
                var totalPenEl = document.getElementById('id_pendencia-TOTAL_FORMS');
                if (totalPenEl) totalPenEl.value = remainingPen.length;
            }
        });
    }

    /* ── PENDÊNCIAS ─────────────────────────────────────────────────────── */
    var pendenciaList       = document.getElementById('pendencia-list');
    var pendenciaTotalInput = document.getElementById('id_pendencia-TOTAL_FORMS');
    var btnAddPendencia     = document.getElementById('add-pendencia-btn');

    if (btnAddPendencia && pendenciaList && pendenciaTotalInput) {

        /* Add a new pendência row by cloning the hidden empty-form template */
        btnAddPendencia.addEventListener('click', function () {
            var emptyForm = document.getElementById('empty-pendencia-form');
            if (!emptyForm) return;
            var count   = parseInt(pendenciaTotalInput.value) || 0;
            var newHtml = emptyForm.innerHTML.replace(/__prefix__/g, count);
            var div = document.createElement('div');
            div.innerHTML = newHtml;
            var newRow = div.firstElementChild;
            if (!newRow) return;
            pendenciaList.appendChild(newRow);
            pendenciaTotalInput.value = count + 1;
            /* Hide the "no pendências" placeholder if present */
            var noMsg = document.getElementById('no-pendencia-msg');
            if (noMsg) noMsg.style.display = 'none';
        });

        /* Remove an existing pendência (mark DELETE) or new one (remove DOM) */
        pendenciaList.addEventListener('click', function (e) {
            var btnRemove = e.target.closest('.remove-pendencia-btn');
            if (!btnRemove) return;
            var linha = btnRemove.closest('.pendencia-row');
            if (!linha) return;
            var checkboxDelete = linha.querySelector('input[type="checkbox"][name$="-DELETE"]');
            if (checkboxDelete) {
                checkboxDelete.checked = true;
                linha.style.display = 'none';
            } else {
                linha.remove();
            }
        });
    }

    /* ── TIPO DE PAGAMENTO: unlock document section ──────────────────── */
    /* Use getElementById (more reliable than querySelector with name attr) */
    var selectTipoPagamento = document.getElementById('id_processo-tipo_pagamento') ||
                              document.querySelector('[name="processo-tipo_pagamento"]');
    var avisoDocumentos     = document.getElementById('avisoDocumentos');
    var blocoDocumentos     = document.getElementById('bloco-documentos');

    function atualizarTiposDeDocumento(isUserChange) {
        if (!selectTipoPagamento) return;
        var tipoId = selectTipoPagamento.value;
        if (!tipoId) {
            if (blocoDocumentos) blocoDocumentos.style.display = 'none';
            if (avisoDocumentos) avisoDocumentos.style.display = 'block';
            return;
        }

        /* Unlock immediately — do not wait for the API response.
           A network error must never leave the user stuck with a hidden widget. */
        if (avisoDocumentos) avisoDocumentos.style.display = 'none';
        if (blocoDocumentos) blocoDocumentos.style.display = 'block';
        showDocSelectControls();

        /* Asynchronously narrow the tipo dropdown to types for this payment type. */
        var tipoIdNum = parseInt(tipoId, 10);
        if (!tipoIdNum || tipoIdNum <= 0) return;
        var apiUrl = (selectTipoPagamento.dataset.apiTiposUrl || '/api/documentos-por-pagamento/');
        fetch(apiUrl + '?tipo_pagamento_id=' + encodeURIComponent(tipoIdNum))
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (!data.sucesso) return;
                var templateSelect = document.querySelector('#empty-doc-form select[name$="-tipo"]');
                if (templateSelect) {
                    templateSelect.innerHTML = '<option value="">---------</option>';
                    data.tipos.forEach(function (tipo) {
                        var opt = document.createElement('option');
                        opt.value = tipo.id;
                        opt.textContent = tipo.tipo_de_documento;
                        templateSelect.appendChild(opt);
                    });
                }
                if (containerDocumentos) {
                    containerDocumentos.querySelectorAll('select[name$="-tipo"]').forEach(function (sel) {
                        var prev = sel.value;
                        if (templateSelect) sel.innerHTML = templateSelect.innerHTML;
                        if (!isUserChange) sel.value = prev;
                    });
                }
            })
            .catch(function () {
                /* Network error — block is already visible; leave tipo dropdown as-is */
            });
    }

    if (selectTipoPagamento) {
        if (!somenteDocs) {
            selectTipoPagamento.addEventListener('change', function () {
                atualizarTiposDeDocumento(true);
            });
        } else {
            selectTipoPagamento.disabled = true;
        }
        /* Run immediately if a value is already selected
           (edit page, or add page re-rendered after a POST error) */
        if (selectTipoPagamento.value) {
            atualizarTiposDeDocumento(false);
        }
    }

    /* ── DOCUMENTOS: sortable ordering, add/remove rows, file preview ── */
    function recalcularOrdemDocumentos() {
        if (!containerDocumentos) return;
        var count = 1;
        containerDocumentos.querySelectorAll('.document-row').forEach(function (row) {
            if (row.style.display === 'none') return;
            var inputOrdem = row.querySelector('input[name$="-ordem"]');
            if (inputOrdem) { inputOrdem.value = count; count++; }
        });
    }

    if (containerDocumentos) {
        /* SortableJS drag-and-drop row reordering */
        if (typeof Sortable !== 'undefined') {
            try {
                new Sortable(containerDocumentos, {
                    handle: '.drag-handle',
                    ghostClass: 'bg-light',
                    animation: 150,
                    onEnd: recalcularOrdemDocumentos,
                });
            } catch (e) {
                /* Sortable unavailable — drag-and-drop ordering disabled
                   but all other document-management features continue. */
            }
        }
        recalcularOrdemDocumentos();

        /* "Add Document" button — clone the hidden empty-doc-form template */
        var addDocBtn = document.getElementById('add-doc-btn');
        if (addDocBtn && docTotalInput) {
            addDocBtn.addEventListener('click', function () {
                var emptyDocForm = document.getElementById('empty-doc-form');
                if (!emptyDocForm) return;
                var count   = parseInt(docTotalInput.value) || 0;
                var newHtml = emptyDocForm.innerHTML.replace(/__prefix__/g, count);
                var div = document.createElement('div');
                div.innerHTML = newHtml;
                var newRow = div.firstElementChild;
                if (!newRow) return;
                containerDocumentos.appendChild(newRow);
                docTotalInput.value = count + 1;
                recalcularOrdemDocumentos();
                /* Sync tipo select options from the template select */
                var emptySelect = emptyDocForm.querySelector('select[name$="-tipo"]');
                var newSelect   = newRow.querySelector('select[name$="-tipo"]');
                if (emptySelect && newSelect) newSelect.innerHTML = emptySelect.innerHTML;
            });
        }

        /* Click delegation: PDF preview and row removal */
        containerDocumentos.addEventListener('click', function (e) {
            var btnPreview = e.target.closest('.preview-doc-btn');
            if (btnPreview) {
                var remoteUrl = btnPreview.getAttribute('data-url');
                if (remoteUrl) { loadPdfIntoViewer(remoteUrl); return; }
                var row = btnPreview.closest('.document-row');
                var fi  = row && row.querySelector('input[type="file"]');
                if (fi && fi.files.length > 0) loadPdfIntoViewer(fi.files[0]);
                return;
            }

            var btnRemove = e.target.closest('.remove-doc-btn');
            if (btnRemove) {
                var linha   = btnRemove.closest('.document-row');
                if (!linha) return;
                var checkDel = linha.querySelector('input[type="checkbox"][name$="-DELETE"]');
                if (checkDel) {
                    checkDel.checked = true;
                    linha.style.display = 'none';
                } else {
                    linha.remove();
                }
                recalcularOrdemDocumentos();
                callHook('onDocumentRemoved');
            }
        });

        /* Change delegation: selection badge update and file preview */
        containerDocumentos.addEventListener('change', function (e) {
            if (e.target.classList.contains('doc-select-check')) {
                updateBatchButtonBadge();
                return;
            }
            if (e.target.matches('input[type="file"]')) {
                var row         = e.target.closest('.document-row');
                var displaySpan = row && row.querySelector('.doc-filename-display');
                var btnPreview  = row && row.querySelector('.preview-doc-btn');
                if (e.target.files.length > 0) {
                    var file = e.target.files[0];
                    if (displaySpan)
                        displaySpan.innerHTML =
                            '<i class="bi bi-file-earmark-check"></i> Anexado: ' + file.name;
                    if (file.type === 'application/pdf' && btnPreview) {
                        btnPreview.style.display = 'inline-block';
                        btnPreview.removeAttribute('data-url');
                        loadPdfIntoViewer(file);
                    }
                } else {
                    if (btnPreview) btnPreview.style.display = 'none';
                }
                callHook('onFileSelected', e.target);
            }
        });
    }

    /* ── DROPZONE: drag-and-drop file upload ─────────────────────────── */
    var dropzone        = document.getElementById('dropzone-area');
    var bulkInput       = document.getElementById('bulk-file-input');
    var dropActiveClass = (dropzone && dropzone.dataset.activeClass) || 'bg-primary';

    if (dropzone && bulkInput) {
        dropzone.addEventListener('click', function () { bulkInput.click(); });

        dropzone.addEventListener('dragover', function (e) {
            e.preventDefault();
            dropzone.classList.remove('bg-light');
            dropzone.classList.add(dropActiveClass);
        });
        dropzone.addEventListener('dragleave', function () {
            dropzone.classList.remove(dropActiveClass);
            dropzone.classList.add('bg-light');
        });
        dropzone.addEventListener('drop', function (e) {
            e.preventDefault();
            dropzone.classList.remove(dropActiveClass);
            dropzone.classList.add('bg-light');
            if (e.dataTransfer.files.length > 0) processarArquivosEmLote(e.dataTransfer.files);
        });
        bulkInput.addEventListener('change', function () {
            if (this.files.length > 0) processarArquivosEmLote(this.files);
            this.value = '';
        });
    }

    var _lastBatchRows = [];

    function processarArquivosEmLote(files) {
        if (!containerDocumentos) return;
        _lastBatchRows = [];
        Array.from(files).forEach(function (file) {
            var rows      = containerDocumentos.querySelectorAll('.document-row');
            var targetRow = rows[rows.length - 1];
            var fileInput = targetRow ? targetRow.querySelector('input[type="file"]') : null;
            var displayEl = targetRow ? targetRow.querySelector('.doc-filename-display') : null;
            var hasSaved  = displayEl && displayEl.innerText.trim() !== '';

            if (!fileInput || fileInput.files.length > 0 || hasSaved) {
                var addBtn = document.getElementById('add-doc-btn');
                if (addBtn) addBtn.click();
                var newRows   = containerDocumentos.querySelectorAll('.document-row');
                targetRow     = newRows[newRows.length - 1];
                fileInput     = targetRow ? targetRow.querySelector('input[type="file"]') : null;
            }
            if (fileInput) {
                var dt = new DataTransfer();
                dt.items.add(file);
                fileInput.files = dt.files;
                fileInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (targetRow) _lastBatchRows.push(targetRow);
        });

        var dropzoneText = dropzone && dropzone.querySelector('.dropzone-text');
        if (dropzoneText) {
            var origText = dropzoneText.dataset.originalText || dropzoneText.innerHTML;
            dropzoneText.dataset.originalText = origText;
            dropzoneText.innerHTML =
                '<i class="bi bi-check2-circle"></i> ' + files.length + ' arquivo(s) inserido(s)!';
            setTimeout(function () { dropzoneText.innerHTML = origText; }, 3000);
        }
        if (files.length > 0) abrirModalBatchTipo(files.length, true);
    }

    /* ── FORMA DE PAGAMENTO visibility ───────────────────────────────── */
    var selectFormaPagamento = document.getElementById('id_processo-forma_pagamento');
    var blocoBoleto          = document.getElementById('bloco_boleto');
    var blocoTransferencia   = document.getElementById('bloco_transferencia');
    var blocoPix             = document.getElementById('bloco_pix');

    function gerenciarVisibilidadePagamento() {
        if (!selectFormaPagamento) return;
        var formaStr = '';
        if (selectFormaPagamento.selectedIndex >= 0) {
            var opt = selectFormaPagamento.options[selectFormaPagamento.selectedIndex];
            formaStr = (opt ? opt.text : '')
                .toUpperCase()
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '');
        }
        if (blocoBoleto)        blocoBoleto.style.display        = 'none';
        if (blocoTransferencia) blocoTransferencia.style.display = 'none';
        if (blocoPix)           blocoPix.style.display           = 'none';

        var ehBoleto = formaStr.includes('BOLETO') || formaStr.includes('GERENCIADOR');
        gerenciarVisibilidadePagamento.ehBoleto = ehBoleto;

        if (ehBoleto) {
            if (blocoBoleto) blocoBoleto.style.display = 'flex';
        } else if (formaStr.includes('TRANSFERENCIA') || formaStr.includes('TED') ||
                   formaStr.includes('DOC')) {
            if (blocoTransferencia) blocoTransferencia.style.display = 'flex';
        } else if (formaStr.includes('PIX')) {
            if (blocoPix) blocoPix.style.display = 'flex';
        }

        /* Hook call is always wrapped — page-specific errors never crash shared init */
        callHook('onFormaPagamentoChanged', ehBoleto);
    }

    if (selectFormaPagamento) {
        selectFormaPagamento.addEventListener('change', gerenciarVisibilidadePagamento);
        gerenciarVisibilidadePagamento();
    }

    /* ── BOLETO PDF PROCESSOR ─────────────────────────────────────────── */
    var btnProcessarBoleto = document.getElementById('btn-processar-boleto');
    if (btnProcessarBoleto) {
        btnProcessarBoleto.addEventListener('click', function () {
            var fileInput = document.getElementById('boleto-upload-input');
            var statusEl  = document.getElementById('boleto-status');
            var apiUrl    = this.dataset.apiBoletoUrl || '';
            if (!fileInput || !fileInput.files.length) {
                if (statusEl) statusEl.innerHTML =
                    "<span class='text-danger'>Selecione um PDF primeiro.</span>";
                return;
            }
            if (statusEl) statusEl.innerHTML =
                "<span class='text-primary'>Lendo arquivo... Aguarde.</span>";
            var csrf = document.querySelector('[name="csrfmiddlewaretoken"]');
            var formData = new FormData();
            formData.append('boleto_pdf', fileInput.files[0]);
            formData.append('csrfmiddlewaretoken', csrf ? csrf.value : '');
            fetch(apiUrl, { method: 'POST', body: formData })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.sucesso) {
                        if (statusEl) statusEl.innerHTML =
                            "<span class='text-success'>Boleto lido com sucesso! Valores preenchidos.</span>";
                        var vlInput = document.querySelector('[name="processo-valor_liquido"]');
                        var vbInput = document.querySelector('[name="processo-valor_bruto"]');
                        var vcInput = document.querySelector('[name="processo-data_vencimento"]');
                        if (data.dados) {
                            if (vlInput) vlInput.value = data.dados.valor.toFixed(2);
                            if (vbInput) vbInput.value = data.dados.valor.toFixed(2);
                            if (data.dados.vencimento && vcInput) vcInput.value = data.dados.vencimento;
                        }
                    } else {
                        if (statusEl) statusEl.innerHTML =
                            "<span class='text-danger'>Erro: " + (data.erro || 'desconhecido') + '</span>';
                    }
                })
                .catch(function () {
                    if (statusEl) statusEl.innerHTML =
                        "<span class='text-danger'>Erro na requisição da API.</span>";
                });
        });
    }

    /* ── BATCH TIPO MODAL ────────────────────────────────────────────── */
    var _modalBatchTipoInstance = null;
    var _batchApplyAll          = false;

    function getModalBatchTipo() {
        if (!_modalBatchTipoInstance) {
            var el = document.getElementById('modal-batch-tipo');
            if (!el) return null;
            try {
                _modalBatchTipoInstance = new bootstrap.Modal(el);
            } catch (e) {
                /* Bootstrap not available — batch-tipo modal disabled
                   but all other features continue to work. */
                return null;
            }
        }
        return _modalBatchTipoInstance;
    }

    function getVisibleDocRows() {
        if (!containerDocumentos) return [];
        return Array.from(containerDocumentos.querySelectorAll('.document-row'))
            .filter(function (r) { return r.style.display !== 'none'; });
    }

    function getCheckedDocRows() {
        if (!containerDocumentos) return [];
        return Array.from(
            containerDocumentos.querySelectorAll('.document-row .doc-select-check:checked'))
            .map(function (cb) { return cb.closest('.document-row'); })
            .filter(function (r) { return r && r.style.display !== 'none'; });
    }

    function updateBatchButtonBadge() {
        var checked     = getCheckedDocRows();
        var visible     = getVisibleDocRows();
        var badge       = document.getElementById('batch-selection-badge');
        var countLabel  = document.getElementById('selected-count-label');
        var selectAllCb = document.getElementById('select-all-docs');

        if (badge) {
            badge.textContent   = checked.length > 0 ? checked.length : '';
            badge.style.display = checked.length > 0 ? '' : 'none';
        }
        if (countLabel)
            countLabel.textContent = checked.length > 0
                ? checked.length + ' de ' + visible.length + ' selecionado(s)'
                : '';
        if (selectAllCb) {
            selectAllCb.checked       = visible.length > 0 && checked.length === visible.length;
            selectAllCb.indeterminate = checked.length > 0 && checked.length < visible.length;
        }
    }

    function showDocSelectControls() {
        var ctrl = document.getElementById('doc-select-controls');
        if (ctrl) ctrl.style.display = 'flex';
    }

    var selectAllCb = document.getElementById('select-all-docs');
    if (selectAllCb) {
        selectAllCb.addEventListener('change', function () {
            getVisibleDocRows().forEach(function (row) {
                var cb = row.querySelector('.doc-select-check');
                if (cb) cb.checked = selectAllCb.checked;
            });
            updateBatchButtonBadge();
        });
    }

    function abrirModalBatchTipo(qtdArquivos, applyAll) {
        if (!selectTipoPagamento || !selectTipoPagamento.value) return;
        _batchApplyAll = !!applyAll;

        var selectLote     = document.getElementById('batch-tipo-select');
        var optionsCurrent = document.querySelector('#empty-doc-form select[name$="-tipo"]');
        if (optionsCurrent && selectLote) {
            selectLote.innerHTML = '';
            var defOpt = document.createElement('option');
            defOpt.value = '';
            defOpt.textContent = '-- Selecione o tipo --';
            selectLote.appendChild(defOpt);
            Array.from(optionsCurrent.options).forEach(function (opt) {
                if (!opt.value) return;
                var o = document.createElement('option');
                o.value = opt.value;
                o.textContent = opt.textContent;
                selectLote.appendChild(o);
            });
        }

        var msgEl       = document.getElementById('batch-tipo-msg');
        var btnLabel    = document.getElementById('btn-confirmar-batch-label');
        var checkedRows = getCheckedDocRows();

        if (msgEl) {
            if (_batchApplyAll) {
                msgEl.textContent = qtdArquivos > 1
                    ? qtdArquivos + ' documentos foram adicionados. Deseja definir o mesmo tipo para todos?'
                    : '1 documento foi adicionado. Deseja definir o tipo agora?';
            } else if (checkedRows.length > 0) {
                msgEl.textContent = checkedRows.length +
                    ' documento(s) selecionado(s). O tipo será aplicado apenas aos selecionados.';
            } else {
                msgEl.textContent =
                    'Nenhum documento selecionado. O tipo será aplicado a todos os ' +
                    qtdArquivos + ' documento(s) visíveis.';
            }
        }
        if (btnLabel) {
            btnLabel.textContent = (!_batchApplyAll && checkedRows.length > 0)
                ? 'Aplicar a ' + checkedRows.length + ' Selecionado(s)'
                : 'Aplicar a Todos';
        }
        var modal = getModalBatchTipo();
        if (modal) modal.show();
    }

    var btnConfirmarBatch = document.getElementById('btn-confirmar-batch-tipo');
    if (btnConfirmarBatch) {
        btnConfirmarBatch.addEventListener('click', function () {
            var selectLote = document.getElementById('batch-tipo-select');
            if (!selectLote) return;
            var valorSelecionado = selectLote.value;
            if (!valorSelecionado) { selectLote.classList.add('is-invalid'); return; }
            selectLote.classList.remove('is-invalid');

            var checkedRows = getCheckedDocRows();
            var targetRows  = _batchApplyAll
                ? _lastBatchRows
                : (checkedRows.length > 0 ? checkedRows : getVisibleDocRows());

            targetRows.forEach(function (row) {
                var sel = row.querySelector('select[name$="-tipo"]');
                if (sel) sel.value = valorSelecionado;
            });

            if (containerDocumentos) {
                containerDocumentos.querySelectorAll('.doc-select-check:checked')
                    .forEach(function (cb) { cb.checked = false; });
            }
            updateBatchButtonBadge();
            _lastBatchRows = [];
            var modal = getModalBatchTipo();
            if (modal) modal.hide();
        });
    }

    var batchSelect = document.getElementById('batch-tipo-select');
    if (batchSelect) {
        batchSelect.addEventListener('change', function () {
            this.classList.remove('is-invalid');
        });
    }

    var btnBatchTipo = document.getElementById('btn-batch-tipo');
    if (btnBatchTipo) {
        btnBatchTipo.addEventListener('click', function () {
            abrirModalBatchTipo(getVisibleDocRows().length, false);
        });
    }

}); // end DOMContentLoaded
