"use strict";

/* Focused adaptation of ManaSpec's vanilla shared table renderer. */
function renderStandardTable(container, config) {
  if (!container) return;

  const rows = config.rows || [];
  container.className = ["ms-table", config.tableClass].filter(Boolean).join(" ");

  if (!rows.length) {
    container.innerHTML = `<div class="empty-state compact">${tableEscapeHtml(config.emptyText || "No rows.")}</div>`;
    return;
  }

  container.innerHTML = `
    <div class="ms-table__header" role="row">
      ${config.columns.map((column) => renderStandardTableHeader(column, config)).join("")}
    </div>
    <div class="ms-table__body" role="rowgroup">
      ${rows.map((row, index) => renderStandardTableRow(row, index, config)).join("")}
    </div>
  `;

  bindStandardTableEvents(container, rows, config);
}

function renderStandardTableHeader(column, config) {
  const classes = ["ms-table__head-cell", tableAlignClass(column.align), column.headerClass]
    .filter(Boolean)
    .join(" ");
  const active = column.sortKey && config.sort?.key === column.sortKey;
  const direction = active ? config.sort.direction : null;
  const ariaSort = direction ? ` aria-sort="${direction === "asc" ? "ascending" : "descending"}"` : "";
  const content = column.sortKey
    ? `<button class="ms-table__sort" type="button" data-ms-sort="${tableEscapeAttr(column.sortKey)}">${tableEscapeHtml(column.label || "")}<span aria-hidden="true">${active ? (direction === "asc" ? "▲" : "▼") : ""}</span></button>`
    : tableEscapeHtml(column.label || "");
  return `<span class="${classes}" role="columnheader"${ariaSort}>${content}</span>`;
}

function renderStandardTableRow(row, index, config) {
  const rowId = config.getRowId ? config.getRowId(row) : index;
  const rowLabel = config.getRowLabel ? config.getRowLabel(row) : `Open row ${index + 1}`;
  const cells = config.columns.map((column) => renderStandardTableCell(row, index, column)).join("");
  return `
    <div class="ms-table__row ${config.rowClass || ""}" role="row" tabindex="0" aria-label="${tableEscapeAttr(rowLabel)}" data-ms-row="${index}" data-row-id="${tableEscapeAttr(rowId)}">
      ${cells}
    </div>
  `;
}

function renderStandardTableCell(row, index, column) {
  const extraClass = typeof column.className === "function" ? column.className(row, index) : column.className;
  const classes = ["ms-table__cell", tableAlignClass(column.align), extraClass]
    .filter(Boolean)
    .join(" ");
  const tooltipValue = column.title ? column.title(row, index) : "";
  const tooltip = tooltipValue ? ` title="${tableEscapeAttr(tooltipValue)}"` : "";

  if (column.type === "anchor") {
    const href = tableSafeUrl(column.href ? column.href(row, index) : "#");
    const value = column.value ? column.value(row, index) : "";
    return `<span class="${classes}" role="cell"><a class="link-button ms-table__link" href="${tableEscapeAttr(href)}" target="_blank" rel="noreferrer" data-ms-link${tooltip}>${tableEscapeHtml(value)}</a></span>`;
  }

  if (column.type === "action") {
    const value = column.value ? column.value(row, index) : column.label;
    return `<span class="${classes}" role="cell"><button class="link-button ms-table__action" type="button" data-ms-action="${tableEscapeAttr(column.action || "primary")}" data-ms-row="${index}"${tooltip}>${tableEscapeHtml(value)}</button></span>`;
  }

  const value = column.html
    ? column.html(row, index)
    : tableEscapeHtml(column.value ? column.value(row, index) : "");
  return `<span class="${classes}" role="cell"${tooltip}>${value}</span>`;
}

function bindStandardTableEvents(container, rows, config) {
  container.querySelectorAll("[data-ms-sort]").forEach((control) => {
    control.addEventListener("click", () => {
      if (typeof config.onSort === "function") config.onSort(control.dataset.msSort);
    });
  });

  container.querySelectorAll("[data-ms-link]").forEach((link) => {
    link.addEventListener("click", (event) => event.stopPropagation());
  });

  container.querySelectorAll("[data-ms-action]").forEach((control) => {
    control.addEventListener("click", (event) => {
      event.stopPropagation();
      const row = rows[Number(control.dataset.msRow)];
      if (row && typeof config.onAction === "function") {
        config.onAction(control.dataset.msAction, row, event);
      }
    });
  });

  if (typeof config.onRowClick !== "function") return;

  container.querySelectorAll(".ms-table__row").forEach((rowElement) => {
    const openRow = (event) => {
      if (event.target.closest("a, button, input, select, textarea")) return;
      const row = rows[Number(rowElement.dataset.msRow)];
      if (row) config.onRowClick(row, event);
    };

    rowElement.addEventListener("click", openRow);
    rowElement.addEventListener("keydown", (event) => {
      if (!["Enter", " "].includes(event.key) || event.target !== rowElement) return;
      event.preventDefault();
      openRow(event);
    });
  });
}

function tableAlignClass(align) {
  if (align === "center") return "ms-table__cell--center";
  if (align === "money") return "ms-table__cell--money";
  if (align === "actions") return "ms-table__cell--actions";
  return "";
}

function tableEscapeAttr(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function tableEscapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function tableSafeUrl(value) {
  try {
    const url = new URL(value, window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#";
  }
}
