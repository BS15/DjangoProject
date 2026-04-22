class DocumentoPreviewWidget {
  static VIEWABLE_EXTENSIONS = ["pdf", "png", "jpg", "jpeg", "gif", "bmp", "webp", "svg"];

  constructor(prefix) {
    this.prefix = prefix;
    this.widget = document.getElementById(`document-preview-widget-${prefix}`);
    this.iframe = document.getElementById(`document-preview-iframe-${prefix}`);
    this.placeholder = document.getElementById(`document-preview-placeholder-${prefix}`);
    this.openLink = document.getElementById(`document-preview-open-${prefix}`);
    this.unsupportedMessage = this.widget?.dataset?.unsupportedMessage || "Arquivo não suportado para pré-visualização.";

    if (!this.widget || !this.iframe || !this.placeholder || !this.openLink) {
      console.warn(`DocumentoPreviewWidget(${prefix}): elementos obrigatórios não encontrados.`);
      return;
    }

    this.bindEvents();
    this.selectFirstAvailable();
  }

  bindEvents() {
    document.addEventListener("click", (event) => {
      const btn = event.target.closest(`.doc-preview-btn[data-doc-prefix="${this.prefix}"]`);
      if (!btn) {
        return;
      }
      event.preventDefault();
      this.preview(btn.dataset.docUrl || btn.dataset.docLocalUrl || "", btn.dataset.docName || "", btn);
    });
  }

  selectFirstAvailable() {
    const firstBtn = Array.from(document.querySelectorAll(`.doc-preview-btn[data-doc-prefix="${this.prefix}"]`))
      .find((btn) => !!(btn.dataset.docUrl || btn.dataset.docLocalUrl));
    if (firstBtn) {
      this.preview(firstBtn.dataset.docUrl || firstBtn.dataset.docLocalUrl || "", firstBtn.dataset.docName || "", firstBtn);
    }
  }

  preview(url, name, activeBtn) {
    if (!url) {
      return;
    }

    let extensionSource = name || "";
    if (!extensionSource && url) {
      try {
        extensionSource = new URL(url, window.location.origin).pathname;
      } catch (_error) {
        extensionSource = url;
      }
    }
    const ext = (extensionSource.split(".").pop() || "").toLowerCase();

    document.querySelectorAll(`.doc-preview-btn[data-doc-prefix="${this.prefix}"]`).forEach((btn) => {
      btn.classList.remove("btn-primary", "text-white");
      btn.classList.add("btn-outline-secondary");
    });
    if (activeBtn) {
      activeBtn.classList.remove("btn-outline-secondary");
      activeBtn.classList.add("btn-primary", "text-white");
    }

    this.openLink.href = url;
    this.openLink.classList.remove("disabled");
    this.openLink.setAttribute("aria-disabled", "false");

    if (DocumentoPreviewWidget.VIEWABLE_EXTENSIONS.includes(ext)) {
      this.iframe.src = url;
      this.iframe.classList.remove("d-none");
      this.placeholder.classList.add("d-none");
      return;
    }

    this.iframe.src = "about:blank";
    this.iframe.classList.add("d-none");
    this.placeholder.classList.remove("d-none");
    this.placeholder.textContent = this.unsupportedMessage;
  }
}
