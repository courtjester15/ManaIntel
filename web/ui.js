"use strict";

/* Shared display helpers. Source records and durable reviews stay unchanged. */
window.ManaUI = {
  sourceText(value) {
    const decoder = document.createElement("textarea");
    // Decode individual entities only, never insert feed markup into the page.
    return String(value ?? "").replace(/&(?:#\d+|#x[0-9a-f]+|[a-z][a-z0-9]+);/gi, (entity) => {
      decoder.innerHTML = entity;
      return decoder.value;
    });
  },
  async copyText(button, value, successLabel, fallback) {
    try {
      await navigator.clipboard.writeText(value);
      button.textContent = successLabel;
    } catch {
      // A selectable value is useful on HTTP previews or with clipboard blocked.
      fallback.hidden = false;
      fallback.value = value;
      fallback.focus();
      fallback.select();
      button.textContent = "Select and copy below";
    }
  },
};
