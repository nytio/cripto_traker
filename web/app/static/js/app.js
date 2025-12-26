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
          button.dataset.originalText = button.textContent;
          button.textContent = loadingText;
        }
        button.disabled = true;
      } else {
        const originalText = button.dataset.originalText;
        if (originalText) {
          button.textContent = originalText;
          delete button.dataset.originalText;
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
});
