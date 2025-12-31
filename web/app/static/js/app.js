document.addEventListener("DOMContentLoaded", () => {
  const storageKey = "pending-toast";
  const readPendingToast = () => {
    try {
      const raw = window.sessionStorage.getItem(storageKey);
      if (!raw) {
        return null;
      }
      return JSON.parse(raw);
    } catch (error) {
      return null;
    }
  };
  const writePendingToast = (toast) => {
    try {
      window.sessionStorage.setItem(storageKey, JSON.stringify(toast));
    } catch (error) {
      // Ignore storage failures.
    }
  };
  const clearPendingToast = () => {
    try {
      window.sessionStorage.removeItem(storageKey);
    } catch (error) {
      // Ignore storage failures.
    }
  };
  const setFormLoading = (form, isLoading) => {
    form.querySelectorAll("button[type='submit']").forEach((button) => {
      const loadingText = button.getAttribute("data-loading-text");
      if (isLoading) {
        if (loadingText) {
          button.dataset.originalHtml = button.innerHTML;
          const showSpinner = button.dataset.loadingSpinner === "1";
          const spinner = showSpinner
            ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>'
            : "";
          button.innerHTML = `${spinner}${loadingText}`;
        }
        button.disabled = true;
      } else {
        const originalHtml = button.dataset.originalHtml;
        if (originalHtml) {
          button.innerHTML = originalHtml;
          delete button.dataset.originalHtml;
        }
        button.disabled = false;
      }
    });
  };
  const getToastContainer = () => {
    const existing = document.getElementById("toast-container");
    if (existing) {
      return existing;
    }
    const container = document.createElement("div");
    container.className = "toast-container position-fixed bottom-0 end-0 p-3";
    container.id = "toast-container";
    document.body.appendChild(container);
    return container;
  };
  const showToast = (message, variant = "info") => {
    if (!window.bootstrap || !bootstrap.Toast) {
      return;
    }
    const toastContainer = getToastContainer();
    const toastEl = document.createElement("div");
    toastEl.className = `toast align-items-center text-bg-${variant} border-0`;
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");
    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${message}</div>
      </div>
    `;
    toastContainer.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, {
      autohide: true,
      delay: 5000,
    });
    toastEl.addEventListener("hidden.bs.toast", () => {
      toastEl.remove();
    });
    toast.show();
  };

  document.querySelectorAll("form[data-loading='1']").forEach((form) => {
    if (form.dataset.async === "1") {
      return;
    }
    form.addEventListener("submit", () => {
      setFormLoading(form, true);
    });
  });

  document.querySelectorAll("form[data-async='1']").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      setFormLoading(form, true);
      const message =
        form.dataset.asyncMessage ||
        "Calculations are running in the background.";
      showToast(message, form.dataset.asyncVariant || "info");
      try {
        const response = await fetch(form.action, {
          method: form.method || "POST",
          body: new FormData(form),
        });
        if (!response.ok) {
          showToast("Update failed. Refresh and try again.", "danger");
          setFormLoading(form, false);
          return;
        }
        const doneMessage =
          form.dataset.asyncDoneMessage || "Done. Refreshing chart.";
        writePendingToast({
          message: doneMessage,
          variant: form.dataset.asyncDoneVariant || "success",
        });
        window.location.reload();
      } catch (error) {
        showToast("Update failed. Refresh and try again.", "danger");
        setFormLoading(form, false);
      } finally {
        // Reload handles the end-state on success.
      }
    });
  });

  if (window.bootstrap && bootstrap.Toast) {
    document.querySelectorAll(".toast").forEach((toastEl) => {
      const toast = new bootstrap.Toast(toastEl, {
        autohide: true,
        delay: 5000,
      });
      toastEl.addEventListener("hidden.bs.toast", () => {
        toastEl.remove();
      });
      toast.show();
    });
  }

  const pendingToast = readPendingToast();
  if (pendingToast && pendingToast.message) {
    showToast(pendingToast.message, pendingToast.variant || "info");
    clearPendingToast();
  }

  document.querySelectorAll("form[data-validate='1']").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    });
  });

  if (window.bootstrap && bootstrap.Tooltip) {
    document.querySelectorAll("[data-ct-tooltip]").forEach((el) => {
      const tooltipText = el.getAttribute("data-ct-tooltip");
      if (tooltipText && !el.getAttribute("title")) {
        el.setAttribute("title", tooltipText);
      }
      new bootstrap.Tooltip(el);
    });
  }

  const removeModal = document.getElementById("remove-modal");
  if (removeModal && window.bootstrap) {
    removeModal.addEventListener("show.bs.modal", (event) => {
      const trigger = event.relatedTarget;
      if (!trigger) {
        return;
      }
      const name = trigger.getAttribute("data-remove-name") || "this crypto";
      const symbol = trigger.getAttribute("data-remove-symbol") || "";
      const action = trigger.getAttribute("data-remove-action") || "";
      const assetLabel = symbol ? `${name} (${symbol})` : name;
      const target = removeModal.querySelector("[data-remove-target='asset']");
      if (target) {
        target.textContent = assetLabel;
      }
      const form = removeModal.querySelector("[data-remove-form]");
      if (form && action) {
        form.setAttribute("action", action);
      }
    });
  }

  document.querySelectorAll("[data-search-input]").forEach((input) => {
    const targetSelector = input.dataset.searchTarget;
    if (!targetSelector) {
      return;
    }
    const table = document.querySelector(targetSelector);
    if (!table) {
      return;
    }
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    const getRowText = (row) =>
      (row.dataset.searchText || row.textContent || "").toLowerCase();
    const filterRows = () => {
      const term = input.value.trim().toLowerCase();
      rows.forEach((row) => {
        const matches = !term || getRowText(row).includes(term);
        row.classList.toggle("d-none", !matches);
      });
    };
    input.addEventListener("input", filterRows);
    filterRows();
  });
});
