(function () {
  const DESKTOP_QUERY = window.matchMedia("(min-width: 701px)");

  function attach(mapEl, options) {
    if (!mapEl || mapEl.dataset.fullscreenBound === "1") return;
    mapEl.dataset.fullscreenBound = "1";

    options = options || {};
    const title = options.title || "Map";
    const invalidate =
      options.invalidate ||
      function () {
        if (mapEl._leaflet_id && mapEl.parentElement) {
          const map = L.map.getMap ? L.map.getMap(mapEl) : null;
          if (map) map.invalidateSize();
        }
      };

    const shell = document.createElement("div");
    shell.className = "map-shell";
    mapEl.parentNode.insertBefore(shell, mapEl);
    shell.appendChild(mapEl);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "map-fullscreen-btn desktop-only-control";
    button.setAttribute("aria-label", "Open map fullscreen");
    button.title = "Fullscreen";
    button.innerHTML = '<span aria-hidden="true">⤢</span>';
    shell.appendChild(button);

    let dialog = null;
    let body = null;

    function refreshSize() {
      requestAnimationFrame(function () {
        invalidate();
        requestAnimationFrame(invalidate);
      });
    }

    function restore() {
      shell.appendChild(mapEl);
      refreshSize();
      if (typeof options.onClose === "function") options.onClose();
    }

    function ensureDialog() {
      if (dialog) return;
      dialog = document.createElement("dialog");
      dialog.className = "map-fullscreen-dialog";
      dialog.innerHTML =
        '<div class="map-fullscreen-card card">' +
        '  <div class="map-fullscreen-header">' +
        '    <h2 class="section-title map-fullscreen-title"></h2>' +
        '    <button type="button" class="btn btn-secondary btn-icon map-fullscreen-close" aria-label="Close fullscreen">&times;</button>' +
        "  </div>" +
        '  <div class="map-fullscreen-body"></div>' +
        "</div>";
      document.body.appendChild(dialog);
      dialog.querySelector(".map-fullscreen-title").textContent = title;
      body = dialog.querySelector(".map-fullscreen-body");
      dialog.querySelector(".map-fullscreen-close").addEventListener("click", function () {
        dialog.close();
      });
      dialog.addEventListener("click", function (event) {
        if (event.target === dialog) dialog.close();
      });
      dialog.addEventListener("close", restore);
    }

    function open() {
      if (!DESKTOP_QUERY.matches) return;
      ensureDialog();
      body.appendChild(mapEl);
      dialog.showModal();
      refreshSize();
    }

    button.addEventListener("click", open);
  }

  window.TracksMapFullscreen = { attach: attach };
})();
