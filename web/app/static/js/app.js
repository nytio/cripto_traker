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
    container.className = "toast-container ct-toast-container position-fixed";
    container.id = "toast-container";
    document.body.appendChild(container);
    return container;
  };
  const toastIcons = {
    success: '<i class="bi bi-check-circle-fill"></i>',
    warning: '<i class="bi bi-exclamation-triangle-fill"></i>',
    danger: '<i class="bi bi-x-circle-fill"></i>',
    info: '<i class="bi bi-info-circle-fill"></i>',
  };
  const normalizeToastVariant = (variant) =>
    variant === "error" ? "danger" : variant;
  const showToast = (message, variant = "info", options = {}) => {
    if (!window.bootstrap || !bootstrap.Toast) {
      return null;
    }
    const toastContainer = getToastContainer();
    const toastEl = document.createElement("div");
    const resolvedVariant = normalizeToastVariant(variant);
    const iconMarkup = toastIcons[resolvedVariant] || toastIcons.info;
    toastEl.className = "toast ct-toast align-items-center border-0";
    toastEl.dataset.variant = resolvedVariant;
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");
    toastEl.innerHTML = `
      <div class="ct-toast-inner">
        <div class="ct-toast-icon" aria-hidden="true">
          ${iconMarkup}
        </div>
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

  const toggleForecastScopeFields = (select) => {
    const form = select.closest("form");
    if (!form) {
      return;
    }
    const scope = select.value;
    form.querySelectorAll("[data-forecast-scope]").forEach((section) => {
      const isActive = section.dataset.forecastScope === scope;
      section.hidden = !isActive;
      section.querySelectorAll("input, select, textarea").forEach((input) => {
        input.disabled = !isActive;
      });
    });
  };

  document
    .querySelectorAll("[data-forecast-scope-select='1']")
    .forEach((select) => {
      toggleForecastScopeFields(select);
      select.addEventListener("change", () =>
        toggleForecastScopeFields(select),
      );
    });

  const parseHyperparams = (raw) => {
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw);
    } catch (error) {
      return null;
    }
  };

  const normalizeParamValue = (key, value) => {
    if (value === null || typeof value === "undefined") {
      return null;
    }
    if (key === "hidden_fc_sizes" && Array.isArray(value)) {
      return value.join(", ");
    }
    return value;
  };

  const applyRunParams = (form, params) => {
    if (!params) {
      return;
    }
    form.querySelectorAll("[data-global-param]").forEach((field) => {
      const key = field.dataset.globalParam;
      if (!key || !(key in params)) {
        return;
      }
      const normalized = normalizeParamValue(key, params[key]);
      if (normalized === null || typeof normalized === "undefined") {
        return;
      }
      const value = String(normalized);
      if (field.tagName === "SELECT") {
        const option = Array.from(field.options).find(
          (item) => item.value === value,
        );
        if (option) {
          field.value = value;
        }
      } else {
        field.value = value;
      }
    });
  };

  const setParamLock = (form, locked) => {
    form.querySelectorAll("[data-global-param]").forEach((field) => {
      const section = field.closest("[data-rnn-model]");
      const isHidden = section ? section.hidden : false;
      field.disabled = locked || isHidden;
    });
  };

  const filterRunOptions = (select, modelFamily) => {
    Array.from(select.options).forEach((option) => {
      if (!option.value) {
        option.hidden = false;
        option.disabled = false;
        return;
      }
      const optionFamily = option.dataset.modelFamily || "";
      const matches = !modelFamily || optionFamily === modelFamily;
      option.hidden = !matches;
      option.disabled = !matches;
    });
  };

  const initGlobalModelSelector = (form) => {
    const select = form.querySelector("[data-global-model-select='1']");
    if (!select) {
      return;
    }

    const modelSelect = form.querySelector("[data-rnn-model-select='1']");
    const scopeSelect = form.querySelector("[data-forecast-scope-select='1']");
    const deleteButton = form.querySelector("[data-global-delete-button='1']");
    const deleteFormId = deleteButton
      ? deleteButton.dataset.globalDeleteForm
      : "";
    const deleteForm = deleteFormId
      ? document.getElementById(deleteFormId)
      : null;
    const deleteInput = deleteForm
      ? deleteForm.querySelector("input[name='model_run_id']")
      : null;
    const retrainWrapper = form.querySelector("[data-global-retrain='1']");
    const retrainInput = retrainWrapper
      ? retrainWrapper.querySelector("input[type='checkbox']")
      : null;
    const resolveModelFamily = () => {
      const value = modelSelect ? modelSelect.value : "rnn";
      return value === "block" ? "BlockRNNModel" : "RNNModel";
    };
    const isGlobalScope = () =>
      !scopeSelect || scopeSelect.value === "global_shared";
    const updateDeleteState = () => {
      const canDelete = isGlobalScope() && Boolean(select.value);
      if (deleteButton) {
        deleteButton.hidden = !canDelete;
        deleteButton.disabled = !canDelete;
      }
      if (deleteInput) {
        deleteInput.value = select.value || "";
      }
    };
    const updateRetrainState = () => {
      const show = isGlobalScope() && Boolean(select.value);
      if (retrainWrapper) {
        retrainWrapper.hidden = !show;
      }
      if (retrainInput) {
        if (!show) {
          retrainInput.checked = true;
        }
        retrainInput.disabled = !show;
      }
    };
    const updateLock = () => {
      const locked = isGlobalScope() && Boolean(select.value);
      setParamLock(form, locked);
      updateDeleteState();
      updateRetrainState();
    };

    const applySelection = () => {
      if (isGlobalScope()) {
        const option = select.options[select.selectedIndex];
        if (option && option.value) {
          const params = parseHyperparams(option.dataset.hyperparams);
          applyRunParams(form, params);
        }
      }
      updateLock();
    };

    const syncOptions = () => {
      filterRunOptions(select, resolveModelFamily());
      const selectedOption = select.options[select.selectedIndex];
      if (select.value && selectedOption && selectedOption.disabled) {
        select.value = "";
      }
      applySelection();
    };

    if (modelSelect) {
      modelSelect.addEventListener("change", () => {
        syncOptions();
      });
    }

    if (scopeSelect) {
      scopeSelect.addEventListener("change", () => {
        if (isGlobalScope()) {
          syncOptions();
        } else {
          updateLock();
        }
      });
    }

    if (deleteButton && deleteForm) {
      deleteButton.addEventListener("click", () => {
        if (!select.value) {
          return;
        }
        const confirmed = window.confirm(
          "Delete this global model? This removes stored files and forecasts.",
        );
        if (!confirmed) {
          return;
        }
        deleteForm.submit();
      });
    }

    select.addEventListener("change", () => {
      applySelection();
    });

    syncOptions();
  };

  document.querySelectorAll("form").forEach((form) => {
    initGlobalModelSelector(form);
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
