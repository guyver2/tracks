(function () {
  const mapEl = document.getElementById("map");
  if (!mapEl) return;

  const geojsonUrl = mapEl.dataset.geojsonUrl;
  const activityType = mapEl.dataset.activityType || "hike";
  const place = mapEl.dataset.place || "";
  const defaultTraceColors = {
    hike: "#43c78a",
    bike: "#5b8dee",
    skitouring: "#e8a64c",
  };
  const defaultTraceColor = defaultTraceColors[activityType] || defaultTraceColors.hike;

  const map = L.map(mapEl, { scrollWheelZoom: false });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
    maxZoom: 19,
  }).addTo(map);

  let hoverMarker = null;

  function invalidate() {
    map.invalidateSize();
  }

  window.addEventListener("resize", invalidate);
  window.addEventListener("orientationchange", invalidate);

  window.tracksMapHover = {
    show: function (lat, lng) {
      if (hoverMarker) {
        hoverMarker.setLatLng([lat, lng]);
        return;
      }
      hoverMarker = L.circleMarker([lat, lng], {
        radius: 8,
        color: "#ffffff",
        weight: 2,
        fillColor: "#ffffff",
        fillOpacity: 0.95,
      }).addTo(map);
    },
    clear: function () {
      if (!hoverMarker) return;
      map.removeLayer(hoverMarker);
      hoverMarker = null;
    },
  };

  function styleFeature(feature) {
    const color = feature.properties && feature.properties.color
      ? feature.properties.color
      : defaultTraceColor;
    return { color: color, weight: 4, opacity: 0.9 };
  }

  async function loadTrace() {
    if (geojsonUrl) {
      const resp = await fetch(geojsonUrl);
      if (!resp.ok) return showPlaceFallback();
      const data = await resp.json();
      const features =
        data.type === "FeatureCollection"
          ? data.features || []
          : data.type === "Feature"
            ? [data]
            : [];

      if (!features.length) return showPlaceFallback();

      const group = L.featureGroup();
      features.forEach(function (feature) {
        L.geoJSON(feature, { style: styleFeature }).addTo(group);
      });
      group.addTo(map);
      map.fitBounds(group.getBounds(), { padding: [24, 24] });
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
