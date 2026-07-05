(function () {
  const mapEl = document.getElementById("stats-heatmap-map");
  const emptyEl = document.getElementById("stats-heatmap-empty");
  const statusEl = document.getElementById("stats-heatmap-status");
  if (!mapEl) return;

  const heatmapUrl = mapEl.dataset.heatmapUrl;
  const DEFAULT_VIEW = [46.5, 2.5];
  const DEFAULT_ZOOM = 5;

  function setStatus(text, visible) {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.hidden = !visible;
  }

  function boundsToLeaflet(bounds) {
    if (!bounds) return null;
    return [
      [bounds.min_lat, bounds.min_lng],
      [bounds.max_lat, bounds.max_lng],
    ];
  }

  function renderHeatmap(data) {
    if (!data.has_data || !data.points.length) {
      mapEl.hidden = true;
      if (emptyEl) emptyEl.hidden = false;
      return;
    }

    mapEl.hidden = false;
    if (emptyEl) emptyEl.hidden = true;

    const map = L.map(mapEl, { scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
      maxZoom: 19,
    }).addTo(map);

    L.heatLayer(data.points, {
      radius: 22,
      blur: 18,
      maxZoom: 14,
      minOpacity: 0.12,
      gradient: {
        0.15: "rgba(91, 141, 238, 0.25)",
        0.45: "rgba(91, 141, 238, 0.45)",
        0.75: "rgba(252, 76, 2, 0.55)",
        1.0: "rgba(255, 107, 44, 0.65)",
      },
    }).addTo(map);

    const leafletBounds = boundsToLeaflet(data.bounds);
    if (leafletBounds) {
      map.fitBounds(leafletBounds, { padding: [24, 24] });
    } else {
      map.setView(DEFAULT_VIEW, DEFAULT_ZOOM);
    }

    map.on("click", function () {
      map.scrollWheelZoom.enable();
    });

    if (window.TracksMapFullscreen) {
      window.TracksMapFullscreen.attach(mapEl, {
        title: "Where you've been",
        invalidate: function () {
          map.invalidateSize();
        },
      });
    }
  }

  setStatus("Loading heatmap…", true);
  fetch(heatmapUrl)
    .then(function (response) {
      if (!response.ok) throw new Error("Heatmap unavailable");
      return response.json();
    })
    .then(function (data) {
      setStatus("", false);
      renderHeatmap(data);
    })
    .catch(function () {
      setStatus("Could not load heatmap.", true);
      mapEl.hidden = true;
      if (emptyEl) emptyEl.hidden = false;
    });
})();
