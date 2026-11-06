(function () {
  "use strict";
  const button = document.getElementById("mobile-menu-btn");
  const menu = document.getElementById("app-menu");
  const backdrop = document.getElementById("menu-backdrop");
  function setOpen(open) {
    if (!button || !menu || !backdrop) return;
    menu.classList.toggle("is-open", open);
    menu.inert = !open && !window.matchMedia("(min-width: 1200px)").matches;
    backdrop.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    button.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
  }
  if (button)
    button.addEventListener("click", () =>
      setOpen(button.getAttribute("aria-expanded") !== "true"),
    );
  if (backdrop)
    backdrop.addEventListener("click", () => {
      setOpen(false);
      button.focus();
    });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      button &&
      button.getAttribute("aria-expanded") === "true"
    ) {
      setOpen(false);
      button.focus();
    }
  });
  const desktop = window.matchMedia("(min-width: 1200px)");
  desktop.addEventListener("change", () => setOpen(false));
  setOpen(false);
  function normalize(value) {
    return value
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("es");
  }
  document.querySelectorAll("[data-table-search]").forEach((input) => {
    function filter() {
      const target = document.getElementById(input.dataset.tableSearch);
      if (!target) return;
      const query = normalize(input.value.trim());
      let visible = 0;
      target.querySelectorAll("[data-search-row]").forEach((row) => {
        row.hidden = !normalize(row.textContent).includes(query);
        if (!row.hidden) visible++;
      });
      const empty = target.querySelector("[data-filter-empty]");
      if (empty) empty.hidden = visible > 0 || !query;
    }
    input.addEventListener("input", filter);
    document.body.addEventListener("htmx:afterSwap", filter);
  });
})();
