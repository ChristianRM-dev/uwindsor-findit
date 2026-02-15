// static/js/password_toggle.js
// Reusable password show/hide toggler for Bootstrap forms.
// Usage: add a button with [data-password-toggle] and data-target="#inputId" or "inputId".
(() => {
  "use strict";

  function resolveTarget(el) {
    const target = el.getAttribute("data-target") || el.getAttribute("data-password-target");
    if (!target) return null;

    // Accept "#id" or "id"
    const selector = target.startsWith("#") ? target : `#${target}`;
    return document.querySelector(selector);
  }

  function setButtonState(btn, isVisible) {
    // You can customize labels/icons via data attributes:
    const showLabel = btn.getAttribute("data-label-show") || "Show";
    const hideLabel = btn.getAttribute("data-label-hide") || "Hide";

    const iconShow = btn.getAttribute("data-icon-show") || "bi-eye";
    const iconHide = btn.getAttribute("data-icon-hide") || "bi-eye-slash";

    const iconEl = btn.querySelector("[data-role='icon']");
    const labelEl = btn.querySelector("[data-role='label']");

    if (iconEl) {
      iconEl.classList.remove(iconShow, iconHide);
      iconEl.classList.add(isVisible ? iconHide : iconShow);
    }

    if (labelEl) {
      labelEl.textContent = isVisible ? hideLabel : showLabel;
    } else {
      // Fallback: set aria-label only
      btn.setAttribute("aria-label", isVisible ? hideLabel : showLabel);
    }
  }

  function togglePassword(btn) {
    const input = resolveTarget(btn);
    if (!input) return;

    const isPassword = input.getAttribute("type") === "password";
    input.setAttribute("type", isPassword ? "text" : "password");

    setButtonState(btn, isPassword);

    // Keep focus on input for better UX
    input.focus({ preventScroll: true });
  }

  function init() {
    // Event delegation: works for dynamically added forms too
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-password-toggle]");
      if (!btn) return;
      e.preventDefault();
      togglePassword(btn);
    });

    // Initialize button states on load
    document.querySelectorAll("[data-password-toggle]").forEach((btn) => {
      const input = resolveTarget(btn);
      if (!input) return;
      setButtonState(btn, input.getAttribute("type") === "text");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
