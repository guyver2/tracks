(function () {
  const dialog = document.getElementById("activities-map-dialog");
  const openBtn = document.getElementById("activities-map-open");
  const closeBtn = dialog && dialog.querySelector(".activities-map-close");
  const mapEl = document.getElementById("activities-map");
  const emptyEl = document.getElementById("activities-map-empty");
  const statusEl = document.getElementById("activities-map-status");
  if (!dialog || !openBtn || !closeBtn || !mapEl) return;

  const manifestUrl = mapEl.dataset.manifestUrl;
  const TRACE_WEIGHT = 3;
  const LOAD_CONCURRENCY = 4;
  const DEFAULT_VIEW = [46.5, 2.5];
  const DEFAULT_ZOOM = 5;

  let map = null;
  let layerGroup = null;
  let loaded = false;
  let trackMetaById = {};

  function invalidate() {
    if (!map) return;
    map.invalidateSize();
  }

  function setStatus(text, visible) {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.hidden = !visible;
  }

  function styleFeature(feature) {
    const trackId = feature.properties && feature.properties.track_id;
    const meta = trackId != null ? trackMetaById[trackId] : null;
    const color = (meta && meta.color) || "#FC4C02";
    return {
      color: color,
      weight: TRACE_WEIGHT,
      opacity: 0.9,
    };
  }

  function bindFeature(feature, layer) {
    const trackId = feature.properties && feature.properties.track_id;
    const meta = trackId != null ? trackMetaById[trackId] : null;
    const label = meta && meta.label;
    const activityId = meta && meta.activity_id;
    if (label) {
      layer.bindTooltip(label, { sticky: true, opacity: 0.92 });
    }
    layer.on("click", function () {
      if (activityId != null) {
        window.location.href = "/activities/" + activityId;
      }
    });
  }

  function boundsToLeaflet(bounds) {
    if (!bounds) return null;
    return [
      [bounds.min_lat, bounds.min_lng],
      [bounds.max_lat, bounds.max_lng],
    ];
  }

  function fitToBounds(bounds) {
    const leafletBounds = boundsToLeaflet(bounds);
    if (leafletBounds) {
      map.fitBounds(leafletBounds, { padding: [24, 24] });
      return;
    }
    map.setView(DEFAULT_VIEW, DEFAULT_ZOOM);
  }

  function boundsIntersect(trackBounds, mapBounds) {
    if (!trackBounds || !mapBounds) return false;
    return !(
      trackBounds.max_lat < mapBounds.getSouth() ||
      trackBounds.min_lat > mapBounds.getNorth() ||
      trackBounds.max_lng < mapBounds.getWest() ||
      trackBounds.min_lng > mapBounds.getEast()
    );
  }

  function boundsCenterDistance(trackBounds, center) {
    if (!trackBounds) return Number.POSITIVE_INFINITY;
    const lat = (trackBounds.min_lat + trackBounds.max_lat) / 2;
    const lng = (trackBounds.min_lng + trackBounds.max_lng) / 2;
    const dLat = lat - center.lat;
    const dLng = lng - center.lng;
    return dLat * dLat + dLng * dLng;
  }

  function sortTracksForViewport(tracks, mapBounds) {
    const center = mapBounds.getCenter();
    return tracks.slice().sort(function (a, b) {
      const aVisible = boundsIntersect(a.bounds, mapBounds);
      const bVisible = boundsIntersect(b.bounds, mapBounds);
      if (aVisible !== bVisible) return aVisible ? -1 : 1;
      return boundsCenterDistance(a.bounds, center) - boundsCenterDistance(b.bounds, center);
    });
  }

  function waitForMapBounds() {
    return new Promise(function (resolve) {
      requestAnimationFrame(function () {
        requestAnimationFrame(resolve);
      });
    });
  }

  function ensureLayerGroup() {
    if (layerGroup) return layerGroup;
    layerGroup = L.featureGroup().addTo(map);
    return layerGroup;
  }

  function addFeature(feature) {
    L.geoJSON(feature, {
      style: styleFeature,
      onEachFeature: bindFeature,
    }).addTo(ensureLayerGroup());
  }

  async function fetchTrackFeature(trackId) {
    const resp = await fetch("/activities/map/tracks/" + trackId + ".geojson");
    if (!resp.ok) return null;
    return resp.json();
  }

  async function loadTracksProgressive(tracks) {
    let loadedCount = 0;
    let nextIndex = 0;
    const total = tracks.length;

    setStatus("Loading tracks 0 / " + total + "…", true);

    async function worker() {
      while (nextIndex < total) {
        const track = tracks[nextIndex];
        nextIndex += 1;
        try {
          const feature = await fetchTrackFeature(track.track_id);
          if (feature) addFeature(feature);
        } catch {
          // Skip failed tracks and continue loading the rest.
        }
        loadedCount += 1;
        setStatus("Loading tracks " + loadedCount + " / " + total + "…", loadedCount < total);
      }
    }

    const workerCount = Math.min(LOAD_CONCURRENCY, total);
    await Promise.all(Array.from({ length: workerCount }, worker));
    setStatus("", false);
    invalidate();
  }

  async function loadTracks() {
    if (!manifestUrl) return showEmpty();

    setStatus("Loading map…", true);
    const resp = await fetch(manifestUrl);
    if (!resp.ok) return showEmpty();

    const manifest = await resp.json();
    const tracks = manifest.tracks || [];
    trackMetaById = {};
    tracks.forEach(function (track) {
      trackMetaById[track.track_id] = track;
    });

    if (!tracks.length) return showEmpty();

    if (emptyEl) emptyEl.hidden = true;
    mapEl.hidden = false;

    if (layerGroup) {
      map.removeLayer(layerGroup);
      layerGroup = null;
    }

    fitToBounds(manifest.bounds);
    invalidate();
    await waitForMapBounds();
    const sortedTracks = sortTracksForViewport(tracks, map.getBounds());
    await loadTracksProgressive(sortedTracks);
  }

  function showEmpty() {
    trackMetaById = {};
    if (layerGroup) {
      map.removeLayer(layerGroup);
      layerGroup = null;
    }
    mapEl.hidden = true;
    if (emptyEl) emptyEl.hidden = false;
    setStatus("", false);
    map.setView(DEFAULT_VIEW, DEFAULT_ZOOM);
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
    setupExpandButton();
  }

  function setupExpandButton() {
    const header = dialog.querySelector(".activities-map-header");
    if (!header || header.querySelector(".activities-map-expand")) return;

    const expandBtn = document.createElement("button");
    expandBtn.type = "button";
    expandBtn.className = "btn btn-secondary btn-icon activities-map-expand desktop-only-control";
    expandBtn.setAttribute("aria-label", "Expand map");
    expandBtn.title = "Expand";
    expandBtn.innerHTML = '<span aria-hidden="true">⤢</span>';
    header.insertBefore(expandBtn, closeBtn);

    expandBtn.addEventListener("click", function () {
      const expanded = dialog.classList.toggle("activities-map-dialog--expanded");
      expandBtn.setAttribute("aria-label", expanded ? "Restore map size" : "Expand map");
      expandBtn.title = expanded ? "Restore" : "Expand";
      invalidate();
    });
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
  dialog.addEventListener("close", function () {
    dialog.classList.remove("activities-map-dialog--expanded");
    invalidate();
  });
})();
