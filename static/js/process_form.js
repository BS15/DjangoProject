/**
 * static/js/process_form.js
 *
 * Shared JavaScript for the process-creation (add_process) and
 * process-editing (editar_processo) pages.
 *
 * ── Extension hooks ────────────────────────────────────────────────────────
 * Each page may define `window.processFormHooks` BEFORE this file is loaded
 * to inject page-specific behaviour without duplicating shared logic:
 *
 *   window.processFormHooks = {
 *     // Called inside the 'submit' handler BEFORE the shared formset cleanup.
 *     // Return false (or call e.preventDefault()) to abort submission.
 *     beforeSubmit(e) { … },
 *
 *     // Called after gerenciarVisibilidadePagamento() resolves the payment type.
 *     onFormaPagamentoChanged(ehBoleto) { … },
 *
 *     // Called after a document row is removed from the list.
 *     onDocumentRemoved() { … },
 *
 *     // Called after a file is chosen inside a document row.
 *     onFileSelected(fileInput) { … },
 *   };
 *
 * ── Data attributes ─────────────────────────────────────────────────────────
 * #processForm
 *   data-somente-docs="true|false"   – locks tipo-pagamento select + skips
 *                                      the tipo-change event listener
 *
 * select[name$="tipo_pagamento"]
 *   data-api-tipos-url="…"           – overrides the hardcoded
 *                                      /api/documentos-por-pagamento/ URL
 *
 * #dropzone-area
 *   data-active-class="bg-primary"   – class applied while dragging over
 *
 * .dropzone-text
 *   data-original-text="…"          – text restored after batch-drop feedback
 *
 * #btn-processar-boleto
 *   data-api-boleto-url="…"          – URL for the boleto-PDF reader API
 */

/* ═══════════════════════════════════════════════════════════════════════════
   GLOBAL UTILITY FUNCTIONS
   Declared at module scope so inline HTML (onclick="…") can call them.
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Display a PDF file (File object) or a secure-download URL in the viewer
 * iframe, hiding the placeholder text.
 * @param {File|string} source
 */
function loadPdfIntoViewer(source) {
    const viewer = document.getElementById('pdf-viewer');
    const placeholder = document.getElementById('pdf-placeholder');
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
 * Copy a barcode/digitável string to the clipboard and briefly show a
 * tick icon on the triggering button.
 * @param {HTMLElement} btn  — must have data-code attribute
 */
function copiarCodigoBarras(btn) {
    const code = btn.dataset.code;
    if (!code) return;
    navigator.clipboard.writeText(code).then(function () {
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check2"></i>';
        setTimeout(function () { btn.innerHTML = orig; }, 2000);
    });
}

/**
 * Populate the #previewModal with the currently selected creditor and
 * net value before showing the save-confirmation dialog.
 * Called from the "Salvar e Continuar" button via onclick="check_information_alert()".
 */
window.check_information_alert = function () {
    const credorEl = document.getElementById('id_processo-credor');
    const prevCreedor = document.getElementById('prev_credor');
    const prevVal = document.getElementById('prev_val');

    if (credorEl && credorEl.selectedIndex >= 0 && prevCreedor) {
        prevCreedor.innerText = credorEl.options[credorEl.selectedIndex].text;
    } else if (prevCreedor) {
        prevCreedor.innerText = '---';
    }

    const valEl = document.getElementById('id_processo-valor_liquido');
    if (prevVal) prevVal.innerText = valEl ? valEl.value : '0,00';
};

/* ═══════════════════════════════════════════════════════════════════════════
   DOM-READY INITIALISATION
   ═══════════════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', function () {

    const processForm        = document.getElementById('processForm');
    const somenteDocs        = processForm && processForm.dataset.somenteDocs === 'true';
    const docTotalInput      = document.getElementById('id_documento-TOTAL_FORMS');
    const containerDocumentos = document.getElementById('document-list');
    const hooks              = window.processFormHooks || {};

    /* ─── FORM SUBMIT: run hook then shared formset cleanup ─────────────── */
    if (processForm) {
        processForm.addEventListener('submit', function (e) {
            // Page-specific validation — returning false or calling
            // e.preventDefault() will abort submission.
            if (typeof hooks.beforeSubmit === 'function') {
                const ok = hooks.beforeSubmit(e);
                if (ok === false || e.defaultPrevented) return;
            }

            // Cleanup: remove empty (unsaved) document rows and re-index.
            if (containerDocumentos) {
                containerDocumentos.querySelectorAll('.document-row').forEach(function (row) {
                    if (row.style.display === 'none') return;
                    const fileInput = row.querySelector('input[type="file"]');
                    const hasSaved  = row.querySelector('.doc-filename-display') &&
                                      row.querySelector('.doc-filename-display').innerText.trim() !== '';
                    if (!fileInput || (fileInput.files.length === 0 && !hasSaved)) {
                        const idInput = row.querySelector('input[type="hidden"][name$="-id"]');
                        if (!idInput || !idInput.value) row.remove();
                    }
                });
                const remaining = containerDocumentos.querySelectorAll('.document-row');
                remaining.forEach(function (row, i) {
                    row.querySelectorAll('input, select').forEach(function (el) {
                        if (el.name) el.name = el.name.replace(/-\d+-/, '-' + i + '-');
                        if (el.id)   el.id   = el.id.replace(/-\d+-/, '-' + i + '-');
                    });
                });
                document.getElementById('id_documento-TOTAL_FORMS').value = remaining.length;
            }

            // Cleanup: remove empty (unsaved) pendência rows and re-index.
            const penList = document.getElementById('pendencia-list');
            if (penList) {
                penList.querySelectorAll('.pendencia-row').forEach(function (row) {
                    if (row.style.display === 'none') return;
                    const descInput = row.querySelector('input[name$="-descricao"]');
                    if (!descInput || !descInput.value.trim()) {
                        const idInput = row.querySelector('input[type="hidden"][name$="-id"]');
                        if (!idInput || !idInput.value) row.remove();
                    }
                });
                const remainingPen = penList.querySelectorAll('.pendencia-row');
                remainingPen.forEach(function (row, i) {
                    row.querySelectorAll('input, select').forEach(function (el) {
                        if (el.name) el.name = el.name.replace(/-\d+-/, '-' + i + '-');
                        if (el.id)   el.id   = el.id.replace(/-\d+-/, '-' + i + '-');
                    });
                });
                document.getElementById('id_pendencia-TOTAL_FORMS').value = remainingPen.length;
            }
        });
    }

    /* ─── PENDÊNCIAS DINÂMICAS ──────────────────────────────────────────── */
    var pendenciaList       = document.getElementById('pendencia-list');
    var pendenciaTotalInput = document.getElementById('id_pendencia-TOTAL_FORMS');
    var btnAddPendencia     = document.getElementById('add-pendencia-btn');

    if (btnAddPendencia && pendenciaList) {
        btnAddPendencia.addEventListener('click', function () {
            var count   = parseInt(pendenciaTotalInput.value);
            var newHtml = document.getElementById('empty-pendencia-form')
                              .innerHTML.replace(/__prefix__/g, count);
            var div = document.createElement('div');
            div.innerHTML = newHtml;
            pendenciaList.appendChild(div.firstElementChild);
            pendenciaTotalInput.value = count + 1;
        });

        pendenciaList.addEventListener('click', function (e) {
            var btnRemove = e.target.closest('.remove-pendencia-btn');
            if (btnRemove) {
                var linha          = btnRemove.closest('.pendencia-row');
                var checkboxDelete = linha.querySelector('input[type="checkbox"][name$="-DELETE"]');
                if (checkboxDelete) {
                    checkboxDelete.checked = true;
                    linha.style.display = 'none';
                } else {
                    linha.remove();
                }
            }
        });
    }

    /* ─── TIPO DE PAGAMENTO: unlock document section ────────────────────── */
    var selectTipoPagamento = document.querySelector('[name="processo-tipo_pagamento"]');
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
        if (avisoDocumentos) {
            avisoDocumentos.innerHTML =
                '<span class="spinner-border spinner-border-sm"></span> Carregando documentos...';
            avisoDocumentos.style.display = 'block';
        }
        var apiUrl = (selectTipoPagamento.dataset.apiTiposUrl || '/api/documentos-por-pagamento/');
        fetch(apiUrl + '?tipo_pagamento_id=' + tipoId)
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (!data.sucesso) return;
                var templateSelect = document.querySelector('#empty-doc-form select[name$="-tipo"]');
                if (templateSelect) templateSelect.innerHTML = '<option value="">---------</option>';
                data.tipos.forEach(function (tipo) {
                    var option = document.createElement('option');
                    option.value = tipo.id;
                    option.textContent = tipo.tipo_de_documento;
                    if (templateSelect) templateSelect.appendChild(option);
                });
                if (containerDocumentos) {
                    containerDocumentos.querySelectorAll('select[name$="-tipo"]').forEach(function (sel) {
                        var valorAntigo = sel.value;
                        if (templateSelect) sel.innerHTML = templateSelect.innerHTML;
                        if (!isUserChange) sel.value = valorAntigo;
                    });
                }
                if (avisoDocumentos) avisoDocumentos.style.display = 'none';
                if (blocoDocumentos) blocoDocumentos.style.display = 'block';
                showDocSelectControls();
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
        if (selectTipoPagamento.value) atualizarTiposDeDocumento(false);
    }

    /* ─── DOCUMENTOS: Sortable, add/remove, file preview ───────────────── */
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
        new Sortable(containerDocumentos, {
            handle: '.drag-handle',
            ghostClass: 'bg-light',
            onEnd: recalcularOrdemDocumentos,
        });
        recalcularOrdemDocumentos();

        document.getElementById('add-doc-btn').addEventListener('click', function () {
            var count   = parseInt(docTotalInput.value);
            var newHtml = document.getElementById('empty-doc-form')
                              .innerHTML.replace(/__prefix__/g, count);
            var div = document.createElement('div');
            div.innerHTML = newHtml;
            containerDocumentos.appendChild(div.firstElementChild);
            docTotalInput.value = count + 1;
            recalcularOrdemDocumentos();
            var optionsCurrent = document.querySelector('#empty-doc-form select[name$="-tipo"]').innerHTML;
            var selectNew = containerDocumentos.lastElementChild.querySelector('select[name$="-tipo"]');
            if (selectNew) selectNew.innerHTML = optionsCurrent;
        });

        containerDocumentos.addEventListener('click', function (e) {
            var btnPreview = e.target.closest('.preview-doc-btn');
            if (btnPreview) {
                var remoteUrl = btnPreview.getAttribute('data-url');
                if (remoteUrl) { loadPdfIntoViewer(remoteUrl); return; }
                var fileInput = btnPreview.closest('.document-row').querySelector('input[type="file"]');
                if (fileInput && fileInput.files.length > 0) loadPdfIntoViewer(fileInput.files[0]);
            }
            var btnRemove = e.target.closest('.remove-doc-btn');
            if (btnRemove) {
                var linha   = btnRemove.closest('.document-row');
                var checkDel = linha.querySelector('input[type="checkbox"][name$="-DELETE"]');
                if (checkDel) {
                    checkDel.checked = true;
                    linha.style.display = 'none';
                } else {
                    linha.remove();
                }
                recalcularOrdemDocumentos();
                if (typeof hooks.onDocumentRemoved === 'function') hooks.onDocumentRemoved();
            }
        });

        containerDocumentos.addEventListener('change', function (e) {
            if (e.target.classList.contains('doc-select-check')) {
                updateBatchButtonBadge();
                return;
            }
            if (e.target.matches('input[type="file"]')) {
                var row         = e.target.closest('.document-row');
                var displaySpan = row.querySelector('.doc-filename-display');
                var btnPreview  = row.querySelector('.preview-doc-btn');
                if (e.target.files.length > 0) {
                    var file = e.target.files[0];
                    if (displaySpan)
                        displaySpan.innerHTML =
                            '<i class="bi bi-file-earmark-check"></i> Anexado: ' + file.name;
                    if (file.type === 'application/pdf') {
                        if (btnPreview) {
                            btnPreview.style.display = 'inline-block';
                            btnPreview.removeAttribute('data-url');
                        }
                        loadPdfIntoViewer(file);
                    }
                } else {
                    if (btnPreview) btnPreview.style.display = 'none';
                }
                if (typeof hooks.onFileSelected === 'function') hooks.onFileSelected(e.target);
            }
        });
    }

    /* ─── DROPZONE ──────────────────────────────────────────────────────── */
    var dropzone     = document.getElementById('dropzone-area');
    var bulkInput    = document.getElementById('bulk-file-input');
    var dropActiveClass = (dropzone && dropzone.dataset.activeClass) || 'bg-primary';

    if (dropzone && bulkInput) {
        dropzone.addEventListener('click', function () { bulkInput.click(); });
        dropzone.addEventListener('dragover', function (e) {
            e.preventDefault();
            dropzone.classList.replace('bg-light', dropActiveClass);
        });
        dropzone.addEventListener('dragleave', function (e) {
            e.preventDefault();
            dropzone.classList.replace(dropActiveClass, 'bg-light');
        });
        dropzone.addEventListener('drop', function (e) {
            e.preventDefault();
            dropzone.classList.replace(dropActiveClass, 'bg-light');
            if (e.dataTransfer.files.length > 0) processarArquivosEmLote(e.dataTransfer.files);
        });
        bulkInput.addEventListener('change', function () {
            if (this.files.length > 0) processarArquivosEmLote(this.files);
            this.value = '';
        });
    }

    function processarArquivosEmLote(files) {
        _lastBatchRows = [];
        Array.from(files).forEach(function (file) {
            var rows     = containerDocumentos.querySelectorAll('.document-row');
            var targetRow = rows[rows.length - 1];
            var fileInput = targetRow ? targetRow.querySelector('input[type="file"]') : null;
            var hasSaved  = targetRow
                ? (targetRow.querySelector('.doc-filename-display') &&
                   targetRow.querySelector('.doc-filename-display').innerText.trim() !== '')
                : false;

            if (!fileInput || fileInput.files.length > 0 || hasSaved) {
                document.getElementById('add-doc-btn').click();
                var newRows = containerDocumentos.querySelectorAll('.document-row');
                targetRow   = newRows[newRows.length - 1];
                fileInput   = targetRow.querySelector('input[type="file"]');
            }
            if (fileInput) {
                var dt = new DataTransfer();
                dt.items.add(file);
                fileInput.files = dt.files;
                fileInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (targetRow) _lastBatchRows.push(targetRow);
        });

        var dropzoneText = dropzone.querySelector('.dropzone-text');
        if (dropzoneText) {
            var origText = dropzoneText.dataset.originalText || dropzoneText.innerHTML;
            dropzoneText.dataset.originalText = origText;
            dropzoneText.innerHTML =
                '<i class="bi bi-check2-circle"></i> ' + files.length + ' arquivo(s) inserido(s)!';
            setTimeout(function () { dropzoneText.innerHTML = origText; }, 3000);
        }
        if (files.length > 0) abrirModalBatchTipo(files.length, true);
    }

    /* ─── FORMA DE PAGAMENTO visibility ─────────────────────────────────── */
    var selectFormaPagamento = document.getElementById('id_processo-forma_pagamento');
    var blocoBoleto          = document.getElementById('bloco_boleto');
    var blocoTransferencia   = document.getElementById('bloco_transferencia');
    var blocoPix             = document.getElementById('bloco_pix');

    function gerenciarVisibilidadePagamento() {
        if (!selectFormaPagamento) return;
        var formaStr = '';
        if (selectFormaPagamento.selectedIndex >= 0) {
            formaStr = selectFormaPagamento.options[selectFormaPagamento.selectedIndex].text
                .toUpperCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
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

        if (typeof hooks.onFormaPagamentoChanged === 'function') {
            hooks.onFormaPagamentoChanged(ehBoleto);
        }
    }

    if (selectFormaPagamento) {
        selectFormaPagamento.addEventListener('change', gerenciarVisibilidadePagamento);
        gerenciarVisibilidadePagamento();
    }

    /* ─── SHARED BOLETO PDF PROCESSOR ───────────────────────────────────── */
    // Both pages use: id="btn-processar-boleto" / id="boleto-upload-input" /
    // id="boleto-status" and data-api-boleto-url on the button.
    var btnProcessarBoleto = document.getElementById('btn-processar-boleto');
    if (btnProcessarBoleto) {
        btnProcessarBoleto.addEventListener('click', function () {
            var fileInput = document.getElementById('boleto-upload-input');
            var statusEl  = document.getElementById('boleto-status');
            var apiUrl    = this.dataset.apiBoletoUrl || '';
            if (!fileInput || !fileInput.files.length) {
                if (statusEl) statusEl.innerHTML = "<span class='text-danger'>Selecione um PDF primeiro.</span>";
                return;
            }
            if (statusEl) statusEl.innerHTML = "<span class='text-primary'>Lendo arquivo... Aguarde.</span>";
            var formData = new FormData();
            formData.append('boleto_pdf', fileInput.files[0]);
            formData.append('csrfmiddlewaretoken',
                document.querySelector('[name="csrfmiddlewaretoken"]').value);
            fetch(apiUrl, { method: 'POST', body: formData })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.sucesso) {
                        if (statusEl)
                            statusEl.innerHTML =
                                "<span class='text-success'>Boleto lido com sucesso! Valores preenchidos.</span>";
                        var vlInput = document.querySelector('[name="processo-valor_liquido"]');
                        var vbInput = document.querySelector('[name="processo-valor_bruto"]');
                        var vcInput = document.querySelector('[name="processo-data_vencimento"]');
                        if (vlInput) vlInput.value = data.dados.valor.toFixed(2);
                        if (vbInput) vbInput.value = data.dados.valor.toFixed(2);
                        if (data.dados.vencimento && vcInput) vcInput.value = data.dados.vencimento;
                    } else {
                        if (statusEl)
                            statusEl.innerHTML =
                                "<span class='text-danger'>Erro: " + data.erro + '</span>';
                    }
                })
                .catch(function () {
                    if (statusEl)
                        statusEl.innerHTML =
                            "<span class='text-danger'>Erro na requisição da API.</span>";
                });
        });
    }

    /* ─── BATCH TIPO MODAL ───────────────────────────────────────────────── */
    var _modalBatchTipoInstance = null;
    var _batchApplyAll  = false;
    var _lastBatchRows  = [];

    function getModalBatchTipo() {
        if (!_modalBatchTipoInstance)
            _modalBatchTipoInstance = new bootstrap.Modal(
                document.getElementById('modal-batch-tipo'));
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
            badge.textContent  = checked.length > 0 ? checked.length : '';
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

        var selectLote      = document.getElementById('batch-tipo-select');
        var optionsCurrent  = document.querySelector('#empty-doc-form select[name$="-tipo"]');
        if (optionsCurrent && selectLote) {
            selectLote.innerHTML = '';
            var defaultOpt = document.createElement('option');
            defaultOpt.value = '';
            defaultOpt.textContent = '-- Selecione o tipo --';
            selectLote.appendChild(defaultOpt);
            Array.from(optionsCurrent.options).forEach(function (opt) {
                if (!opt.value) return;
                var newOpt = document.createElement('option');
                newOpt.value = opt.value;
                newOpt.textContent = opt.textContent;
                selectLote.appendChild(newOpt);
            });
        }

        var msgEl      = document.getElementById('batch-tipo-msg');
        var btnLabel   = document.getElementById('btn-confirmar-batch-label');
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
        getModalBatchTipo().show();
    }

    var btnConfirmarBatch = document.getElementById('btn-confirmar-batch-tipo');
    if (btnConfirmarBatch) {
        btnConfirmarBatch.addEventListener('click', function () {
            var selectLote       = document.getElementById('batch-tipo-select');
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

            containerDocumentos.querySelectorAll('.doc-select-check:checked')
                .forEach(function (cb) { cb.checked = false; });
            updateBatchButtonBadge();
            _lastBatchRows = [];
            getModalBatchTipo().hide();
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
