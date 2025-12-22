document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-loading='1']").forEach((form) => {
    form.addEventListener("submit", () => {
      form.querySelectorAll("button[type='submit']").forEach((button) => {
        const loadingText = button.getAttribute("data-loading-text");
        if (loadingText) {
          button.dataset.originalText = button.textContent;
          button.textContent = loadingText;
        }
        button.disabled = true;
      });
    });
  });
});
