(function () {
  document.addEventListener("click", async function (event) {
    const button = event.target.closest("[data-copy-target]");
    if (!button) return;

    const target = document.querySelector(button.dataset.copyTarget);
    if (!target) return;

    const value = target.value || target.textContent || "";
    try {
      await navigator.clipboard.writeText(value);
      const original = button.textContent;
      button.textContent = "Скопировано";
      window.setTimeout(function () {
        button.textContent = original;
      }, 1600);
    } catch (error) {
      target.focus();
      target.select();
      document.execCommand("copy");
    }
  });

  document.addEventListener("submit", function (event) {
    const form = event.target.closest("form[data-confirm]");
    if (!form) return;
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
})();
