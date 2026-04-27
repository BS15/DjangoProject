class SortableRowsManager {
  constructor(options) {
    this.containerSelector = options.containerSelector;
    this.rowSelector = options.rowSelector || '.sortable-row';
    this.handleSelector = options.handleSelector || '.drag-handle';
    this.dragClass = options.dragClass || 'opacity-50';
    this.midpointDivisor = options.midpointDivisor || 2;
    this.onReorder = typeof options.onReorder === 'function' ? options.onReorder : null;
    this.draggedRow = null;

    this.init();
  }

  init() {
    const container = $(this.containerSelector);
    if (!container.length) {
      return;
    }

    this.ensureRowsDraggable();
    if (container.data('sortable-rows-bound')) {
      return;
    }

    container.data('sortable-rows-bound', true);
    this.bindContainerEvents(container);
  }

  ensureRowsDraggable() {
    const rows = $(this.containerSelector).find(this.rowSelector);
    rows.each((_, rowEl) => {
      const row = $(rowEl);
      const handle = row.find(this.handleSelector).first();
      if (!handle.length) {
        return;
      }
      handle.css('cursor', 'grab');
      row.attr('draggable', true);
    });
  }

  bindContainerEvents(container) {
    container.on('dragstart', this.rowSelector, (e) => {
      const isHandle = $(e.target).closest(this.handleSelector).length > 0;
      if (!isHandle) {
        e.preventDefault();
        return;
      }

      this.draggedRow = e.currentTarget;
      if (e.originalEvent && e.originalEvent.dataTransfer) {
        e.originalEvent.dataTransfer.effectAllowed = 'move';
        const dragToken = this.draggedRow.dataset.docId
          || this.draggedRow.dataset.formIndex
          || `row-${Date.now()}`;
        e.originalEvent.dataTransfer.setData('text/plain', dragToken);
      }
      $(this.draggedRow).addClass(this.dragClass);
    });

    container.on('dragend', this.rowSelector, () => {
      if (this.draggedRow) {
        $(this.draggedRow).removeClass(this.dragClass);
      }
      this.draggedRow = null;
      this.handleReorder();
    });

    container.on('dragover', this.rowSelector, (e) => {
      e.preventDefault();
      if (!this.draggedRow || this.draggedRow === e.currentTarget) {
        return;
      }

      const target = e.currentTarget;
      const targetRect = target.getBoundingClientRect();
      const halfHeight = targetRect.height / this.midpointDivisor;
      const shouldInsertAfter = e.originalEvent.clientY > targetRect.top + halfHeight;

      if (shouldInsertAfter) {
        target.parentNode.insertBefore(this.draggedRow, target.nextSibling);
      } else {
        target.parentNode.insertBefore(this.draggedRow, target);
      }
    });
  }

  handleReorder() {
    if (this.onReorder) {
      this.onReorder();
    }
  }
}
