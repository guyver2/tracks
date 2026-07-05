(function () {
  const editor = document.getElementById("track-editor");
  if (!editor) return;

  const previewUrl = editor.dataset.previewUrl;
  const activityType = editor.dataset.activityType || "hike";
  const mapEl = document.getElementById("track-editor-map");
  const canvas = document.getElementById("track-editor-elevation");
  const chartErrorEl = document.getElementById("track-editor-chart-error");
  const statDistance = editor.querySelector("[data-stat-distance]");
  const statDistanceUnit = editor.querySelector("[data-stat-distance-unit]");
  const statDuration = editor.querySelector("[data-stat-duration]");
  const statElevation = editor.querySelector("[data-stat-elevation]");
  const statElevationUnit = editor.querySelector("[data-stat-elevation-unit]");

  let map = null;
  let layerGroup = null;
  let elevationChart = null;
  let activeTrackId = null;
  let previewTimer = null;
  let isDragging = false;

  function formatDuration(seconds) {
    if (seconds == null) return "—";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return hours + "h " + minutes + "m";
    return minutes + "m";
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  let hoverMarker = null;
  const mapHover = {
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

  function initMap() {
    map = L.map(mapEl);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
      maxZoom: 19,
    }).addTo(map);
    layerGroup = L.featureGroup().addTo(map);
    window.addEventListener("resize", function () {
      map.invalidateSize();
    });
    if (window.TracksMapFullscreen) {
      window.TracksMapFullscreen.attach(mapEl, {
        title: "Track preview",
        invalidate: function () {
          map.invalidateSize();
        },
      });
    }
  }

  function styleFeature(feature) {
    const props = feature.properties || {};
    const role = props.role || "kept";
    const opacity = props.opacity != null ? props.opacity : 1;
    if (role === "trimmed") {
      return {
        color: props.color || "#7a82a8",
        weight: 3,
        opacity: opacity,
        dashArray: "6 8",
      };
    }
    if (role === "cut-marker") {
      return {
        color: props.color || "#ffffff",
        weight: 2,
        opacity: opacity,
        fillColor: props.color || "#ffffff",
        fillOpacity: opacity,
        radius: 6,
      };
    }
    return {
      color: props.color || "#FC4C02",
      weight: props.weight || 3,
      opacity: opacity,
    };
  }

  function pointToLayer(feature, latlng) {
    if (feature.properties && feature.properties.role === "cut-marker") {
      return L.circleMarker(latlng, styleFeature(feature));
    }
    return L.marker(latlng);
  }

  function renderMap(geojson, preserveView) {
    layerGroup.clearLayers();
    const features = geojson.features || [];
    if (!features.length) return;

    features.forEach(function (feature) {
      const role = feature.properties && feature.properties.role;
      if (role === "cut-marker") {
        L.geoJSON(feature, {
          pointToLayer: pointToLayer,
        }).addTo(layerGroup);
      } else {
        L.geoJSON(feature, {
          style: styleFeature,
        }).addTo(layerGroup);
      }
    });

    if (!preserveView && layerGroup.getLayers().length) {
      map.fitBounds(layerGroup.getBounds(), { padding: [24, 24] });
    }
    map.invalidateSize();
  }

  function renderStats(stats, elevation) {
    if (!stats) return;
    if (statDistance) {
      statDistance.textContent = stats.distance_km != null ? stats.distance_km : "—";
    }
    if (statDistanceUnit) {
      statDistanceUnit.textContent = stats.distance_km != null ? "km" : "";
    }
    if (statDuration) {
      statDuration.textContent = formatDuration(stats.duration_sec);
    }
    const gain = elevation && elevation.elevation_gain_m != null
      ? elevation.elevation_gain_m
      : stats.elevation_gain_m;
    if (statElevation) {
      statElevation.textContent = gain != null ? gain : "—";
    }
    if (statElevationUnit) {
      statElevationUnit.textContent = gain != null ? "m" : "";
    }
  }

  function renderElevation(elevation) {
    if (chartErrorEl) chartErrorEl.hidden = true;
    window.TracksElevationChart.destroy(elevationChart, canvas);
    elevationChart = null;

    if (!elevation || !elevation.has_elevation || !(elevation.segments || []).length) {
      return;
    }

    requestAnimationFrame(function () {
      try {
        elevationChart = window.TracksElevationChart.render(canvas, elevation, {
          activityType: activityType,
          mapHover: mapHover,
        });
      } catch (err) {
        if (chartErrorEl) {
          chartErrorEl.textContent = "Could not render elevation preview.";
          chartErrorEl.hidden = false;
        }
        console.error(err);
      }
    });
  }

  function buildPreviewQuery() {
    const params = new URLSearchParams();
    editor.querySelectorAll(".track-item").forEach(function (item) {
      const trackId = item.dataset.trackId;
      const removed = item.querySelector(".track-remove-input");
      if (removed && removed.checked) {
        params.set("remove_track_" + trackId, "1");
        return;
      }
      const trimStart = item.querySelector(".trim-start-input");
      const trimEnd = item.querySelector(".trim-end-input");
      if (trimStart) params.set("track_" + trackId + "_trim_start", trimStart.value);
      if (trimEnd) params.set("track_" + trackId + "_trim_end", trimEnd.value);
    });
    if (activeTrackId != null) {
      params.set("active_track_id", String(activeTrackId));
    }
    return params.toString();
  }

  async function refreshPreview(preserveView) {
    try {
      const query = buildPreviewQuery();
      const resp = await fetch(previewUrl + "?" + query);
      if (!resp.ok) return;
      const data = await resp.json();
      renderMap(
        data.geojson || { type: "FeatureCollection", features: [] },
        preserveView != null ? preserveView : isDragging
      );
      renderStats(data.stats, data.elevation);
      renderElevation(data.elevation);
    } catch (err) {
      console.error(err);
    }
  }

  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(function () {
      refreshPreview(isDragging);
    }, 250);
  }

  function getSnapStep(rawPoints) {
    return Math.max(1, Math.round(rawPoints / 120));
  }

  function snapValue(value, step) {
    return Math.round(value / step) * step;
  }

  function getTrimValues(item) {
    const trimStartInput = item.querySelector(".trim-start-input");
    const trimEndInput = item.querySelector(".trim-end-input");
    return {
      trimStart: parseInt(trimStartInput.value, 10) || 0,
      trimEnd: parseInt(trimEndInput.value, 10) || 0,
    };
  }

  function setTrimValues(item, trimStart, trimEnd) {
    item.querySelector(".trim-start-input").value = String(trimStart);
    item.querySelector(".trim-end-input").value = String(trimEnd);
  }

  function updateClipVisual(item) {
    const rawPoints = parseInt(item.dataset.rawPoints, 10) || 0;
    const activeEl = item.querySelector(".clip-active");
    const startKnob = item.querySelector(".clip-handle-start");
    const endKnob = item.querySelector(".clip-handle-end");
    const pointCountEl = item.querySelector("[data-point-count]");
    const values = getTrimValues(item);

    const kept = Math.max(0, rawPoints - values.trimStart - values.trimEnd);
    if (pointCountEl) {
      pointCountEl.textContent = kept + " points (of " + rawPoints + ")";
    }

    if (rawPoints <= 0) return;

    const startPct = (values.trimStart / rawPoints) * 100;
    const endPct = (values.trimEnd / rawPoints) * 100;

    if (activeEl) {
      activeEl.style.left = startPct + "%";
      activeEl.style.right = endPct + "%";
    }
    if (startKnob) {
      startKnob.style.left = startPct + "%";
    }
    if (endKnob) {
      endKnob.style.left = 100 - endPct + "%";
    }
  }

  function applyStartTrim(item, trimStart) {
    const rawPoints = parseInt(item.dataset.rawPoints, 10) || 0;
    const step = getSnapStep(rawPoints);
    const values = getTrimValues(item);
    const maxStart = Math.max(0, rawPoints - values.trimEnd - 2);
    const snapped = clamp(snapValue(trimStart, step), 0, maxStart);
    setTrimValues(item, snapped, values.trimEnd);
    updateClipVisual(item);
  }

  function applyEndTrim(item, trimEnd) {
    const rawPoints = parseInt(item.dataset.rawPoints, 10) || 0;
    const step = getSnapStep(rawPoints);
    const values = getTrimValues(item);
    const maxEnd = Math.max(0, rawPoints - values.trimStart - 2);
    const snapped = clamp(snapValue(trimEnd, step), 0, maxEnd);
    setTrimValues(item, values.trimStart, snapped);
    updateClipVisual(item);
  }

  function trimFromPointer(item, handle, clientX) {
    const track = item.querySelector(".clip-track");
    if (!track) return;

    const rawPoints = parseInt(item.dataset.rawPoints, 10) || 0;
    if (rawPoints <= 0) return;

    const rect = track.getBoundingClientRect();
    if (rect.width <= 0) return;

    const ratio = clamp((clientX - rect.left) / rect.width, 0, 1);

    if (handle === "start") {
      applyStartTrim(item, ratio * rawPoints);
    } else {
      applyEndTrim(item, (1 - ratio) * rawPoints);
    }
  }

  function bindClipHandle(item, knob, handle) {
    function onPointerDown(event) {
      event.preventDefault();
      isDragging = true;
      knob.setPointerCapture(event.pointerId);
      activeTrackId = parseInt(item.dataset.trackId, 10);
      editor.querySelectorAll(".track-item").forEach(function (el) {
        el.classList.toggle("track-item-active", el === item);
      });
      trimFromPointer(item, handle, event.clientX);
    }

    function onPointerMove(event) {
      if (!isDragging) return;
      trimFromPointer(item, handle, event.clientX);
      schedulePreview();
    }

    function onPointerUp(event) {
      if (!isDragging) return;
      isDragging = false;
      knob.releasePointerCapture(event.pointerId);
      refreshPreview(true);
    }

    function onKeyDown(event) {
      const rawPoints = parseInt(item.dataset.rawPoints, 10) || 0;
      const step = getSnapStep(rawPoints);
      const values = getTrimValues(item);

      if (handle === "start") {
        if (event.key === "ArrowLeft") {
          event.preventDefault();
          applyStartTrim(item, values.trimStart - step);
          schedulePreview();
        } else if (event.key === "ArrowRight") {
          event.preventDefault();
          applyStartTrim(item, values.trimStart + step);
          schedulePreview();
        }
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        applyEndTrim(item, values.trimEnd + step);
        schedulePreview();
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        applyEndTrim(item, values.trimEnd - step);
        schedulePreview();
      }
    }

    knob.addEventListener("pointerdown", onPointerDown);
    knob.addEventListener("pointermove", onPointerMove);
    knob.addEventListener("pointerup", onPointerUp);
    knob.addEventListener("pointercancel", onPointerUp);
    knob.addEventListener("keydown", onKeyDown);
  }

  function bindTrackItem(item) {
    const startKnob = item.querySelector(".clip-handle-start");
    const endKnob = item.querySelector(".clip-handle-end");
    const removeInput = item.querySelector(".track-remove-input");

    bindClipHandle(item, startKnob, "start");
    bindClipHandle(item, endKnob, "end");

    removeInput.addEventListener("change", function () {
      item.classList.toggle("track-item-removed", removeInput.checked);
      refreshPreview(false);
    });

    item.addEventListener("focusin", function (event) {
      if (!event.target.classList.contains("clip-handle-knob")) return;
      activeTrackId = parseInt(item.dataset.trackId, 10);
      editor.querySelectorAll(".track-item").forEach(function (el) {
        el.classList.toggle("track-item-active", el === item);
      });
      schedulePreview();
    });

    updateClipVisual(item);
  }

  initMap();
  editor.querySelectorAll(".track-item").forEach(bindTrackItem);
  if (editor.querySelector(".track-item")) {
    editor.querySelector(".track-item").classList.add("track-item-active");
    activeTrackId = parseInt(editor.querySelector(".track-item").dataset.trackId, 10);
  }
  refreshPreview(false);
})();
