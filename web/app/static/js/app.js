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
  const showToast = (message, variant = "info", options = {}) => {
    if (!window.bootstrap || !bootstrap.Toast) {
      return null;
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
      autohide: options.autohide !== false,
      delay: options.delay ?? 5000,
    });
    toastEl.addEventListener("hidden.bs.toast", () => {
      toastEl.remove();
    });
    toast.show();
    return { element: toastEl, toast };
  };

  const jobPollers = new Map();
  const jobToasts = new Map();
  const jobSpinnerHtml =
    '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>';
  const setFormControlsDisabled = (form, disabled) => {
    form.querySelectorAll("input, select, textarea").forEach((control) => {
      control.disabled = disabled;
    });
    form
      .querySelectorAll("button[type='submit']")
      .forEach((button) => {
        button.disabled = disabled;
      });
  };
  const setJobGroupDisabled = (group, disabled) => {
    if (!group) {
      return;
    }
    document.querySelectorAll(`[data-job-group='${group}']`).forEach((el) => {
      if (el.tagName === "FORM") {
        setFormControlsDisabled(el, disabled);
        return;
      }
      if ("disabled" in el) {
        el.disabled = disabled;
      }
    });
  };
  const getStatusUrlForType = (jobType) => {
    const form = document.querySelector(
      `form[data-job-type='${jobType}'][data-job-status-url]`,
    );
    return form ? form.dataset.jobStatusUrl : "";
  };
  const stopJobPolling = (jobType) => {
    const poller = jobPollers.get(jobType);
    if (poller) {
      clearInterval(poller);
      jobPollers.delete(jobType);
    }
    const toast = jobToasts.get(jobType);
    if (toast && toast.toast) {
      toast.toast.hide();
    }
    jobToasts.delete(jobType);
  };
  const startJobPolling = ({
    jobType,
    statusUrl,
    runningMessage,
    doneMessage,
    errorMessage,
    jobGroup,
  }) => {
    if (!jobType || !statusUrl || jobPollers.has(jobType)) {
      return;
    }
    const toast = showToast(`${jobSpinnerHtml}${runningMessage}`, "info", {
      autohide: false,
    });
    if (toast) {
      jobToasts.set(jobType, toast);
    }
    setJobGroupDisabled(jobGroup, true);

    const poll = async () => {
      try {
        const response = await fetch(statusUrl, {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        if (!payload || payload.state === "running") {
          return;
        }
        stopJobPolling(jobType);
        if (payload.state === "done") {
          showToast(payload.message || doneMessage, "success");
          window.location.reload();
          return;
        }
        if (payload.state === "error") {
          showToast(payload.message || errorMessage, "danger");
        }
        setJobGroupDisabled(jobGroup, false);
      } catch (error) {
        stopJobPolling(jobType);
        showToast(errorMessage, "danger");
        setJobGroupDisabled(jobGroup, false);
      }
    };

    const interval = setInterval(poll, 3000);
    jobPollers.set(jobType, interval);
    poll();
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
      try {
        const response = await fetch(form.action, {
          method: form.method || "POST",
          body: new FormData(form),
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          showToast("Update failed. Refresh and try again.", "danger");
          setFormLoading(form, false);
          return;
        }
        const payload = await response.json().catch(() => null);
        if (!payload || !payload.state) {
          window.location.reload();
          return;
        }
        setFormLoading(form, false);
        const jobType = payload.job_type || form.dataset.jobType;
        const jobGroup = form.dataset.jobGroup;
        const runningMessage =
          form.dataset.asyncMessage ||
          "Calculations are running in the background.";
        const doneMessage =
          form.dataset.asyncDoneMessage || "Done. Refreshing chart.";
        const errorMessage =
          form.dataset.asyncErrorMessage || "Update failed. Refresh and try again.";
        if (payload.state === "busy") {
          showToast(payload.message || "Update already running.", "warning");
          const activeType = payload.active_job_type;
          const activeStatusUrl = getStatusUrlForType(activeType);
          if (activeType && activeStatusUrl) {
            startJobPolling({
              jobType: activeType,
              statusUrl: activeStatusUrl,
              runningMessage: `${payload.active_label || activeType} update running.`,
              doneMessage,
              errorMessage,
              jobGroup,
            });
          }
          return;
        }
        if (payload.state === "error") {
          showToast(payload.message || errorMessage, "danger");
          setJobGroupDisabled(jobGroup, false);
          return;
        }
        if (payload.state === "done") {
          showToast(payload.message || doneMessage, "success");
          window.location.reload();
          return;
        }
        startJobPolling({
          jobType,
          statusUrl: form.dataset.jobStatusUrl,
          runningMessage,
          doneMessage,
          errorMessage,
          jobGroup,
        });
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

  const toggleRnnModelFields = (select) => {
    const form = select.closest("form");
    if (!form) {
      return;
    }
    const model = select.value;
    form.querySelectorAll("[data-rnn-model]").forEach((section) => {
      const isActive = section.dataset.rnnModel === model;
      section.hidden = !isActive;
      section.querySelectorAll("input, select, textarea").forEach((input) => {
        input.disabled = !isActive;
      });
    });
  };

  document
    .querySelectorAll("[data-rnn-model-select='1']")
    .forEach((select) => {
      toggleRnnModelFields(select);
      select.addEventListener("change", () => toggleRnnModelFields(select));
    });

  document.querySelectorAll("input[data-range-output]").forEach((input) => {
    const selector = input.dataset.rangeOutput;
    if (!selector) {
      return;
    }
    const output = document.querySelector(selector);
    if (!output) {
      return;
    }
    const sync = () => {
      output.textContent = input.value;
    };
    sync();
    input.addEventListener("input", sync);
  });

  const jobForms = document.querySelectorAll(
    "form[data-job-type][data-job-status-url]",
  );
  const seenJobTypes = new Set();
  jobForms.forEach((form) => {
    const jobType = form.dataset.jobType;
    if (!jobType || seenJobTypes.has(jobType)) {
      return;
    }
    seenJobTypes.add(jobType);
    const statusUrl = form.dataset.jobStatusUrl;
    if (!statusUrl) {
      return;
    }
    fetch(statusUrl, { headers: { Accept: "application/json" } })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (!payload || payload.state !== "running") {
          return;
        }
        const runningMessage =
          form.dataset.asyncMessage ||
          "Calculations are running in the background.";
        const doneMessage =
          form.dataset.asyncDoneMessage || "Done. Refreshing chart.";
        const errorMessage =
          form.dataset.asyncErrorMessage || "Update failed. Refresh and try again.";
        startJobPolling({
          jobType,
          statusUrl,
          runningMessage,
          doneMessage,
          errorMessage,
          jobGroup: form.dataset.jobGroup,
        });
      })
      .catch(() => {});
  });

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

  const navbarCollapse = document.getElementById("ct-navbar");
  if (navbarCollapse) {
    const navbarOverlay = document.querySelector("[data-ct-navbar-overlay]");
    const showOverlay = () => {
      if (navbarOverlay) {
        navbarOverlay.classList.add("is-active");
      }
    };
    const hideOverlay = () => {
      if (navbarOverlay) {
        navbarOverlay.classList.remove("is-active");
      }
    };

    navbarCollapse.addEventListener("show.bs.collapse", showOverlay);
    navbarCollapse.addEventListener("hidden.bs.collapse", hideOverlay);
    navbarCollapse.addEventListener("hide.bs.collapse", hideOverlay);

    const syncOverlay = () => {
      if (!navbarOverlay) {
        return;
      }
      const isMobile = window.matchMedia("(max-width: 991.98px)").matches;
      if (isMobile && navbarCollapse.classList.contains("show")) {
        showOverlay();
      } else {
        hideOverlay();
      }
    };

    if (navbarOverlay) {
      navbarOverlay.addEventListener("click", () => {
        if (window.bootstrap && bootstrap.Collapse) {
          const instance = bootstrap.Collapse.getOrCreateInstance(
            navbarCollapse,
          );
          instance.hide();
        } else {
          navbarCollapse.classList.remove("show");
          hideOverlay();
        }
      });
    }

    const desktopMedia = window.matchMedia("(min-width: 992px)");
    if (desktopMedia.addEventListener) {
      desktopMedia.addEventListener("change", syncOverlay);
    } else {
      desktopMedia.addListener(syncOverlay);
    }
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

  const navbar = document.querySelector(".ct-navbar");
  if (navbar) {
    let lastScrollY = window.scrollY;
    let ticking = false;
    const updateNavbar = () => {
      const currentScrollY = window.scrollY;
      const isScrollingDown = currentScrollY > lastScrollY;
      if (currentScrollY <= 8 || !isScrollingDown) {
        navbar.classList.remove("ct-navbar-hidden");
      } else if (currentScrollY > 64) {
        navbar.classList.add("ct-navbar-hidden");
      }
      lastScrollY = currentScrollY;
      ticking = false;
    };
    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(updateNavbar);
        ticking = true;
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
  }
});
