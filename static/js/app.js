(function () {
  function syncOtherField(group, focusInput) {
    if (!group) return;
    const toggle = group.querySelector('input[value="other"]');
    const field = group.querySelector("[data-other-field]");
    if (!toggle || !field) return;

    field.hidden = !toggle.checked;
    if (toggle.checked && focusInput) {
      const input = field.querySelector('input[type="text"]');
      if (input) input.focus();
    }
  }

  function initOtherFields() {
    document.querySelectorAll("[data-other-field]").forEach(function (field) {
      syncOtherField(field.closest(".public-options"), false);
    });
  }

  document.addEventListener("change", function (event) {
    const input = event.target;
    if (!(input instanceof HTMLInputElement)) return;
    if (!input.matches('input[type="radio"], input[type="checkbox"]')) return;
    if (!input.name || !input.name.startsWith("q_")) return;

    const group = input.closest(".public-options");
    if (!group || !group.querySelector("[data-other-field]")) return;
    syncOtherField(group, input.value === "other" && input.checked);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initOtherFields);
  } else {
    initOtherFields();
  }

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
