(function () {
  const POSTER = "#8795A2";
  const LAND = "#2A3C52";
  const PROFILE_HEIGHT = 200;

  const shareBtn = document.getElementById("share-card-trigger");
  const dataEl = document.getElementById("share-card-data");
  if (!shareBtn || !dataEl) return;

  let activityData;
  try {
    activityData = JSON.parse(dataEl.textContent);
  } catch {
    return;
  }

  const MONTHS = [
    "JANUARY",
    "FEBRUARY",
    "MARCH",
    "APRIL",
    "MAY",
    "JUNE",
    "JULY",
    "AUGUST",
    "SEPTEMBER",
    "OCTOBER",
    "NOVEMBER",
    "DECEMBER",
  ];

  const viewer = document.getElementById("share-card-viewer");
  const viewerImage = viewer ? viewer.querySelector(".share-card-viewer-image") : null;
  if (viewer && viewerImage) {
    viewer.querySelector(".share-card-viewer-close").addEventListener("click", function () {
      viewer.close();
    });
    viewer.addEventListener("click", function (event) {
      if (event.target === viewer || event.target.classList.contains("share-card-viewer-stage")) {
        viewer.close();
      }
    });
    viewer.addEventListener("close", function () {
      viewerImage.removeAttribute("src");
    });
  }

  function showShareCard(url) {
    if (!viewer || !viewerImage) {
      throw new Error("Could not open share card.");
    }
    viewerImage.alt = activityData.name || "Share card";
    viewerImage.src = url;
    if (!viewer.open) viewer.showModal();
  }

  async function shareCardExists() {
    const response = await fetch(activityData.shareCardUrl, { method: "HEAD" });
    return response.ok;
  }

  async function storeShareCard(blob) {
    const body = new FormData();
    body.append("file", blob, "share-card.jpg");
    const response = await fetch(activityData.shareCardUrl, { method: "POST", body: body });
    if (!response.ok) throw new Error("Could not save share card.");
    const payload = await response.json();
    if (!payload.url) throw new Error("Could not save share card.");
    return payload.url;
  }

  function formatDate(iso) {
    if (!iso) return "";
    const parts = String(iso).split("-");
    if (parts.length !== 3) return String(iso);
    const month = MONTHS[Number(parts[1]) - 1] || "";
    return Number(parts[2]) + " " + month + " " + parts[0];
  }

  function formatDistance(km) {
    if (km == null || km === "") return "—";
    const value = Number(km);
    if (Number.isNaN(value)) return "—";
    return value.toFixed(1) + "km";
  }

  function formatTime(seconds) {
    if (seconds == null || seconds === "") return "—";
    const total = Math.round(Number(seconds));
    if (Number.isNaN(total) || total < 0) return "—";
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    return hours + ":" + String(minutes).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
  }

  function formatElevation(meters) {
    if (meters == null || meters === "") return "—";
    const value = Number(meters);
    if (Number.isNaN(value)) return "—";
    const rounded = Math.round(value / 10) * 10;
    return rounded.toLocaleString("en-US") + "m";
  }

  function buildStat(label, value) {
    const stat = document.createElement("div");
    stat.className = "share-card-stat";

    const statValue = document.createElement("div");
    statValue.className = "share-card-stat-value";
    statValue.textContent = value;

    const statLabel = document.createElement("div");
    statLabel.className = "share-card-stat-label";
    statLabel.textContent = label;

    stat.appendChild(statValue);
    stat.appendChild(statLabel);
    return stat;
  }

  function trackIsLandscape(geojson) {
    let minLng = Infinity;
    let minLat = Infinity;
    let maxLng = -Infinity;
    let maxLat = -Infinity;

    function walk(coords) {
      if (!coords || !coords.length) return;
      if (typeof coords[0] === "number") {
        const lng = coords[0];
        const lat = coords[1];
        if (lng < minLng) minLng = lng;
        if (lat < minLat) minLat = lat;
        if (lng > maxLng) maxLng = lng;
        if (lat > maxLat) maxLat = lat;
        return;
      }
      coords.forEach(walk);
    }

    const features = geojson.type === "FeatureCollection" ? geojson.features || [] : [geojson];
    features.forEach(function (feature) {
      if (feature && feature.geometry) walk(feature.geometry.coordinates);
    });
    if (!isFinite(minLng) || !isFinite(minLat)) return false;

    const midLat = ((minLat + maxLat) / 2) * (Math.PI / 180);
    const northSouth = (maxLat - minLat) * 111320;
    const eastWest = (maxLng - minLng) * 111320 * Math.cos(midLat);
    return eastWest > northSouth;
  }

  function buildCardElement(data, landscape) {
    const card = document.createElement("div");
    card.className = "share-card" + (landscape ? " share-card--landscape" : "");

    const mapHost = document.createElement("div");
    mapHost.className = "share-card-map";
    card.appendChild(mapHost);

    if (data.elevationUrl) {
      const profile = document.createElement("canvas");
      profile.className = "share-card-profile";
      card.appendChild(profile);
    }

    const footer = document.createElement("div");
    footer.className = "share-card-footer";

    const identity = document.createElement("div");
    identity.className = "share-card-identity";

    const title = document.createElement("h2");
    title.className = "share-card-title";
    title.textContent = data.name || "Activity";
    identity.appendChild(title);

    const date = document.createElement("p");
    date.className = "share-card-date";
    date.textContent = formatDate(data.date);
    identity.appendChild(date);

    const stats = document.createElement("div");
    stats.className = "share-card-stats";
    stats.appendChild(buildStat("Distance", formatDistance(data.distanceKm)));
    stats.appendChild(buildStat("Time", formatTime(data.durationSec)));
    stats.appendChild(buildStat("Elevation gain", formatElevation(data.elevationGainM)));

    footer.appendChild(identity);
    footer.appendChild(stats);
    card.appendChild(footer);
    return card;
  }

  function clampByte(value) {
    return Math.max(0, Math.min(255, Math.round(value)));
  }

  function mixColor(start, end, amount) {
    const t = Math.max(0, Math.min(1, amount));
    return [
      clampByte(start[0] + (end[0] - start[0]) * t),
      clampByte(start[1] + (end[1] - start[1]) * t),
      clampByte(start[2] + (end[2] - start[2]) * t),
    ];
  }

  function gradePixel(r, g, b) {
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;

    if (b > r + 18 && b >= g - 5 && b - r > 20) {
      const shade = 0.9 + (lum - 0.55) * 0.25;
      return [clampByte(135 * shade), clampByte(149 * shade), clampByte(162 * shade)];
    }
    if (max - min > 35 && r > g + 10 && r > b) {
      return [96, 118, 140];
    }
    if (g > r + 6 && g >= b) {
      return mixColor([24, 40, 58], [55, 76, 100], (lum - 0.4) / 0.35);
    }
    if (max - min < 32) {
      if (lum > 0.93) return [78, 98, 118];
      if (lum < 0.62) return mixColor([100, 122, 144], [146, 168, 188], 1 - lum / 0.62);
      return mixColor([30, 46, 64], [52, 70, 92], (lum - 0.62) / 0.31);
    }
    return mixColor([26, 42, 60], [64, 84, 106], (lum - 0.35) / 0.4);
  }

  function rasterStylePath(styleUrl) {
    const match = String(styleUrl || "").match(/^mapbox:\/\/styles\/([^/]+)\/([^/]+)/);
    if (!match) return "mapbox/outdoors-v12";
    return match[1] + "/" + match[2];
  }

  async function fetchJson(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error("Could not load route data.");
    return resp.json();
  }

  function waitForTiles(layer) {
    return new Promise(function (resolve) {
      let settled = false;
      function done() {
        if (settled) return;
        settled = true;
        resolve();
      }
      layer.once("load", done);
      setTimeout(done, 8000);
    });
  }

  function nextFrame() {
    return new Promise(function (resolve) {
      requestAnimationFrame(function () {
        requestAnimationFrame(resolve);
      });
    });
  }

  function destroyMap(map) {
    if (!map) return;
    try {
      map.remove();
    } catch {
      // The map container is already gone.
    }
  }

  const GradedTiles = L.TileLayer.extend({
    createTile: function (coords, done) {
      const tile = document.createElement("canvas");
      const size = this.getTileSize();
      const scale = 2;
      tile.width = size.x * scale;
      tile.height = size.y * scale;
      tile.style.width = size.x + "px";
      tile.style.height = size.y + "px";
      const ctx = tile.getContext("2d");
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.fillStyle = LAND;
      ctx.fillRect(0, 0, tile.width, tile.height);

      const img = new Image();
      img.crossOrigin = "anonymous";
      const gradeTiles = this.options.gradeTiles !== false;
      img.onload = function () {
        ctx.drawImage(img, 0, 0, tile.width, tile.height);
        if (gradeTiles) {
          const image = ctx.getImageData(0, 0, tile.width, tile.height);
          const pixels = image.data;
          for (let i = 0; i < pixels.length; i += 4) {
            const graded = gradePixel(pixels[i], pixels[i + 1], pixels[i + 2]);
            pixels[i] = graded[0];
            pixels[i + 1] = graded[1];
            pixels[i + 2] = graded[2];
          }
          ctx.putImageData(image, 0, 0);
        }
        done(null, tile);
      };
      img.onerror = function () {
        done(null, tile);
      };
      img.src = this.getTileUrl(coords);
      return tile;
    },
  });

  async function renderLeafletFallback(mapHost, geojson, data) {
    if (typeof L === "undefined") {
      throw new Error("Map library failed to load.");
    }

    const map = L.map(mapHost, {
      zoomControl: false,
      attributionControl: true,
      dragging: false,
      touchZoom: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false,
    });
    map.attributionControl.setPrefix("");

    let tiles = null;
    if (data && data.mapboxToken) {
      const stylePath = rasterStylePath(data.mapboxStyle);
      tiles = new GradedTiles(
        "https://api.mapbox.com/styles/v1/" +
          stylePath +
          "/tiles/256/{z}/{x}/{y}@2x?access_token=" +
          encodeURIComponent(data.mapboxToken),
        {
          tileSize: 256,
          maxZoom: 22,
          gradeTiles: !data.mapboxStyle,
          attribution: "&copy; Mapbox &copy; OpenStreetMap",
        }
      ).addTo(map);
    }

    const layer = L.geoJSON(geojson, {
      style: {
        color: "#FC4C02",
        weight: 8,
        opacity: 1,
        lineCap: "round",
        lineJoin: "round",
      },
    }).addTo(map);

    if (layer.getBounds().isValid()) {
      map.fitBounds(layer.getBounds(), {
        paddingTopLeft: [96, 96],
        paddingBottomRight: [96, 96],
      });
    }
    map.invalidateSize();
    if (tiles) await waitForTiles(tiles);
    return map;
  }

  function drawProfile(canvas, payload) {
    const segments = payload.segments || [];
    const width = canvas.clientWidth;
    const height = canvas.clientHeight || PROFILE_HEIGHT;
    if (!width || !height) return false;

    const series = [];
    let minY = Infinity;
    let maxY = -Infinity;
    let minX = Infinity;
    let maxX = -Infinity;

    segments.forEach(function (segment) {
      const distances = segment.distances_km || [];
      const elevations = segment.elevations_m || [];
      const points = [];
      for (let i = 0; i < distances.length; i += 1) {
        const elevation = elevations[i];
        if (elevation == null) continue;
        points.push({ x: distances[i], y: elevation });
        if (elevation < minY) minY = elevation;
        if (elevation > maxY) maxY = elevation;
        if (distances[i] < minX) minX = distances[i];
        if (distances[i] > maxX) maxX = distances[i];
      }
      if (points.length) series.push(points);
    });

    if (!series.length || !(maxX > minX)) return false;

    const scale = 2;
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    const ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);
    ctx.clearRect(0, 0, width, height);

    const range = Math.max(maxY - minY, 1);
    const span = maxX - minX;
    const padTop = height * 0.08;
    const usable = height - padTop;

    function pointAt(point) {
      return {
        px: ((point.x - minX) / span) * width,
        py: padTop + (1 - (point.y - minY) / range) * usable,
      };
    }

    series.forEach(function (points) {
      ctx.beginPath();
      points.forEach(function (point, index) {
        const plotted = pointAt(point);
        if (index === 0) ctx.moveTo(plotted.px, plotted.py);
        else ctx.lineTo(plotted.px, plotted.py);
      });
      const last = pointAt(points[points.length - 1]);
      const first = pointAt(points[0]);
      ctx.lineTo(last.px, height);
      ctx.lineTo(first.px, height);
      ctx.closePath();
      ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
      ctx.fill();

      ctx.beginPath();
      points.forEach(function (point, index) {
        const plotted = pointAt(point);
        if (index === 0) ctx.moveTo(plotted.px, plotted.py);
        else ctx.lineTo(plotted.px, plotted.py);
      });
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 5;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.stroke();
    });
    return true;
  }

  async function generateShareCard() {
    const menu = document.getElementById("activity-options");
    if (menu) menu.open = false;

    const originalText = shareBtn.textContent;
    shareBtn.disabled = true;
    shareBtn.textContent = "Opening…";

    const host = document.createElement("div");
    host.className = "share-card-export-host";
    let map = null;

    try {
      if (await shareCardExists()) {
        showShareCard(activityData.shareCardUrl);
        return;
      }

      shareBtn.textContent = "Generating…";

      let geojson = null;
      if (activityData.hasMap && activityData.geojsonUrl) {
        geojson = await fetchJson(activityData.geojsonUrl);
      }

      const card = buildCardElement(activityData, geojson ? trackIsLandscape(geojson) : false);
      host.appendChild(card);
      document.body.appendChild(host);

      const mapHost = card.querySelector(".share-card-map");
      if (geojson) {
        map = await renderLeafletFallback(mapHost, geojson, activityData);
      }

      const profile = card.querySelector(".share-card-profile");
      if (profile && activityData.elevationUrl) {
        try {
          const elevation = await fetchJson(activityData.elevationUrl);
          if (!elevation || !elevation.has_elevation || !drawProfile(profile, elevation)) {
            profile.remove();
          }
        } catch {
          profile.remove();
        }
      }

      await nextFrame();

      if (typeof htmlToImage === "undefined") {
        throw new Error("Image export library failed to load.");
      }

      const dataUrl = await htmlToImage.toJpeg(card, {
        pixelRatio: 2,
        quality: 0.85,
        cacheBust: true,
        backgroundColor: POSTER,
      });
      const resp = await fetch(dataUrl);
      const blob = await resp.blob();
      const savedUrl = await storeShareCard(blob);
      showShareCard(savedUrl);
    } catch (err) {
      alert(err.message || "Could not generate share card.");
    } finally {
      destroyMap(map);
      if (host.parentNode) host.parentNode.removeChild(host);
      shareBtn.disabled = false;
      shareBtn.textContent = originalText;
    }
  }

  shareBtn.addEventListener("click", generateShareCard);
})();
