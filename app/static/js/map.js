(function () {
  const mapEl = document.getElementById("map");
  if (!mapEl) return;

  const geojsonUrl = mapEl.dataset.geojsonUrl;
  const activityType = mapEl.dataset.activityType || "hike";
  const place = mapEl.dataset.place || "";
  const traceColor = activityType === "bike" ? "#5b8dee" : "#43c78a";

  const map = L.map(mapEl, { scrollWheelZoom: false });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
    maxZoom: 19,
  }).addTo(map);

  function invalidate() {
    map.invalidateSize();
  }

  window.addEventListener("resize", invalidate);
  window.addEventListener("orientationchange", invalidate);

  async function loadTrace() {
    if (geojsonUrl) {
      const resp = await fetch(geojsonUrl);
      if (!resp.ok) return showPlaceFallback();
      const feature = await resp.json();
      const layer = L.geoJSON(feature, {
        style: { color: traceColor, weight: 4, opacity: 0.9 },
      }).addTo(map);
      map.fitBounds(layer.getBounds(), { padding: [24, 24] });
      invalidate();
      return;
    }
    showPlaceFallback();
  }

  async function showPlaceFallback() {
    if (!place.trim()) {
      map.setView([46.5, 2.5], 5);
      invalidate();
      return;
    }
    try {
      const resp = await fetch("/geocode?q=" + encodeURIComponent(place));
      const data = await resp.json();
      if (data.lat != null && data.lng != null) {
        map.setView([data.lat, data.lng], 12);
        L.marker([data.lat, data.lng]).addTo(map);
      } else {
        map.setView([46.5, 2.5], 5);
      }
    } catch {
      map.setView([46.5, 2.5], 5);
    }
    invalidate();
  }

  loadTrace();
})();
