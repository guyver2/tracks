(function () {
  const dialog = document.getElementById("activities-map-dialog");
  const openBtn = document.getElementById("activities-map-open");
  const closeBtn = dialog && dialog.querySelector(".activities-map-close");
  const mapEl = document.getElementById("activities-map");
  const emptyEl = document.getElementById("activities-map-empty");
  if (!dialog || !openBtn || !closeBtn || !mapEl) return;

  const geojsonUrl = mapEl.dataset.geojsonUrl;
  const TRACE_WEIGHT = 3;
  let map = null;
  let layerGroup = null;
  let loaded = false;

  function invalidate() {
    if (!map) return;
    map.invalidateSize();
  }

  function styleFeature(feature) {
    const color =
      feature.properties && feature.properties.color
        ? feature.properties.color
        : "#FC4C02";
    return {
      color: color,
      weight: TRACE_WEIGHT,
      opacity: 0.9,
    };
  }

  function bindFeature(feature, layer) {
    const label = feature.properties && feature.properties.label;
    const activityId = feature.properties && feature.properties.activity_id;
    if (label) {
      layer.bindTooltip(label, { sticky: true, opacity: 0.92 });
    }
    layer.on("click", function () {
      if (activityId != null) {
        window.location.href = "/activities/" + activityId;
      }
    });
  }

  async function loadTracks() {
    if (!geojsonUrl) return showEmpty();
    const resp = await fetch(geojsonUrl);
    if (!resp.ok) return showEmpty();
    const data = await resp.json();
    const features =
      data.type === "FeatureCollection"
        ? data.features || []
        : data.type === "Feature"
          ? [data]
          : [];

    if (!features.length) return showEmpty();

    if (emptyEl) emptyEl.hidden = true;
    mapEl.hidden = false;

    if (layerGroup) {
      map.removeLayer(layerGroup);
      layerGroup = null;
    }

    layerGroup = L.featureGroup();
    features.forEach(function (feature) {
      L.geoJSON(feature, {
        style: styleFeature,
        onEachFeature: bindFeature,
      }).addTo(layerGroup);
    });
    layerGroup.addTo(map);
    map.fitBounds(layerGroup.getBounds(), { padding: [24, 24] });
    invalidate();
  }

  function showEmpty() {
    if (layerGroup) {
      map.removeLayer(layerGroup);
      layerGroup = null;
    }
    mapEl.hidden = true;
    if (emptyEl) emptyEl.hidden = false;
    map.setView([46.5, 2.5], 5);
    invalidate();
  }

  function ensureMap() {
    if (map) return;
    map = L.map(mapEl);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
      maxZoom: 19,
    }).addTo(map);
    window.addEventListener("resize", invalidate);
    window.addEventListener("orientationchange", invalidate);
  }

  async function openDialog() {
    dialog.showModal();
    ensureMap();
    invalidate();
    if (!loaded) {
      loaded = true;
      await loadTracks();
    } else {
      invalidate();
    }
  }

  openBtn.addEventListener("click", openDialog);
  closeBtn.addEventListener("click", function () {
    dialog.close();
  });
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", invalidate);
})();
