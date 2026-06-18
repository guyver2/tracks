(function () {
  const mapEl = document.getElementById("map");
  if (!mapEl) return;

  const geojsonUrl = mapEl.dataset.geojsonUrl;
  const place = mapEl.dataset.place || "";
  const TRACE_COLOR = "#FC4C02";
  const TRACE_WEIGHT = 3;
  const INACTIVE_OPACITY = 0.4;

  const map = L.map(mapEl);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
    maxZoom: 19,
  }).addTo(map);

  let hoverMarker = null;
  let trackLayers = {};
  let activeTrackId = null;

  function invalidate() {
    map.invalidateSize();
  }

  window.addEventListener("resize", invalidate);
  window.addEventListener("orientationchange", invalidate);

  function trackOpacity(trackId) {
    if (activeTrackId == null || trackId == null) return 1;
    return Number(trackId) === activeTrackId ? 1 : INACTIVE_OPACITY;
  }

  function styleFeature(feature) {
    const trackId = feature.properties && feature.properties.track_id;
    return {
      color: TRACE_COLOR,
      weight: TRACE_WEIGHT,
      opacity: trackOpacity(trackId),
    };
  }

  function applyTrackOpacities() {
    Object.keys(trackLayers).forEach(function (id) {
      const path = trackLayers[id];
      if (!path || !path.setStyle) return;
      path.setStyle({
        color: TRACE_COLOR,
        weight: TRACE_WEIGHT,
        opacity: trackOpacity(Number(id)),
      });
    });
    if (activeTrackId != null && trackLayers[activeTrackId]) {
      trackLayers[activeTrackId].bringToFront();
    }
  }

  function highlightTrack(trackId) {
    if (Object.keys(trackLayers).length <= 1) return;
    activeTrackId = Number(trackId);
    applyTrackOpacities();
  }

  function clearHighlight() {
    if (activeTrackId == null) return;
    activeTrackId = null;
    applyTrackOpacities();
  }

  window.tracksMapHover = {
    show: function (lat, lng, trackId) {
      if (trackId != null && !Number.isNaN(Number(trackId))) {
        highlightTrack(trackId);
      }
      if (hoverMarker) {
        hoverMarker.setLatLng([lat, lng]);
        return;
      }
      hoverMarker = L.circleMarker([lat, lng], {
        radius: 7,
        color: "#ffffff",
        weight: 2,
        fillColor: "#ffffff",
        fillOpacity: 1,
      }).addTo(map);
    },
    clear: function () {
      clearHighlight();
      if (!hoverMarker) return;
      map.removeLayer(hoverMarker);
      hoverMarker = null;
    },
  };

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

      trackLayers = {};
      const group = L.featureGroup();
      features.forEach(function (feature, index) {
        const trackId =
          feature.properties && feature.properties.track_id != null
            ? Number(feature.properties.track_id)
            : index;
        L.geoJSON(feature, {
          style: styleFeature,
          onEachFeature: function (_feature, pathLayer) {
            trackLayers[trackId] = pathLayer;
          },
        }).addTo(group);
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
