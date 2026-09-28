(function () {
  const TRACE_COLOR = "#FC4C02";
  const TRACE_HALO = "#ffffff";
  const CARD_WIDTH = 1080;
  const CARD_HEIGHT = 1350;
  const TILE_URL = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";

  const shareBtn = document.getElementById("share-card-trigger");
  const dataEl = document.getElementById("share-card-data");
  if (!shareBtn || !dataEl) return;

  let activityData;
  try {
    activityData = JSON.parse(dataEl.textContent);
  } catch {
    return;
  }

  function slugify(text) {
    return (
      text
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || "activity"
    );
  }

  function getFilename() {
    const dateText = activityData.date || "";
    return slugify(activityData.name || "activity") + (dateText ? "-" + dateText : "") + ".png";
  }

  function metaParts(data) {
    const parts = [data.date];
    if (data.startTime) parts.push(data.startTime);
    if (data.place) parts.push(data.place);
    return parts.filter(Boolean);
  }

  function buildStat(label, value, unit) {
    const stat = document.createElement("div");
    stat.className = "share-card-stat";

    const statLabel = document.createElement("div");
    statLabel.className = "share-card-stat-label";
    statLabel.textContent = label;

    const statValue = document.createElement("div");
    statValue.className = "share-card-stat-value";
    statValue.textContent = value;

    if (unit) {
      const statUnit = document.createElement("span");
      statUnit.className = "share-card-stat-unit";
      statUnit.textContent = unit;
      statValue.appendChild(statUnit);
    }

    stat.appendChild(statLabel);
    stat.appendChild(statValue);
    return stat;
  }

  function buildCardElement(data) {
    const card = document.createElement("div");
    card.className = "share-card" + (data.hasMap ? "" : " share-card--no-map");
    if (data.activityType) {
      card.dataset.activityType = data.activityType;
    }

    const mapHost = document.createElement("div");
    mapHost.className = "share-card-map";
    mapHost.id = "share-card-map";
    card.appendChild(mapHost);

    const topOverlay = document.createElement("div");
    topOverlay.className = "share-card-overlay share-card-overlay-top";

    const badge = document.createElement("span");
    badge.className = "badge badge-" + (data.activityType || "hike");
    const sourceIcon = document.querySelector(".activity-icon");
    if (sourceIcon) {
      badge.appendChild(sourceIcon.cloneNode(true));
    }
    badge.appendChild(document.createTextNode(data.typeLabel || data.activityType || "Activity"));
    topOverlay.appendChild(badge);

    const title = document.createElement("h2");
    title.className = "share-card-title";
    title.textContent = data.name || "Activity";
    topOverlay.appendChild(title);

    const meta = document.createElement("p");
    meta.className = "share-card-meta";
    meta.textContent = metaParts(data).join(" · ");
    topOverlay.appendChild(meta);
    card.appendChild(topOverlay);

    const bottomOverlay = document.createElement("div");
    bottomOverlay.className = "share-card-overlay share-card-overlay-bottom";

    const stats = document.createElement("div");
    stats.className = "share-card-stats";

    if (data.distanceKm != null) {
      stats.appendChild(buildStat("Distance", String(data.distanceKm), "km"));
    }
    if (data.duration) {
      stats.appendChild(buildStat("Duration", data.duration, ""));
    }
    if (data.elevationDisplay) {
      stats.appendChild(buildStat("Elevation", data.elevationDisplay, ""));
    }

    bottomOverlay.appendChild(stats);
    card.appendChild(bottomOverlay);

    const watermark = document.createElement("div");
    watermark.className = "share-card-watermark";
    watermark.textContent = "Tracks";
    card.appendChild(watermark);

    return card;
  }

  async function fetchGeojson(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error("Could not load route data.");
    return resp.json();
  }

  function waitForMapReady(map, tileLayer) {
    return new Promise(function (resolve) {
      let settled = false;
      function done() {
        if (settled) return;
        settled = true;
        resolve();
      }

      map.whenReady(function () {
        tileLayer.on("load", done);
        setTimeout(done, 2500);
      });
    });
  }

  async function renderRouteMap(mapHost, geojsonUrl) {
    if (typeof L === "undefined") {
      throw new Error("Map library failed to load.");
    }

    const geojson = await fetchGeojson(geojsonUrl);
    const map = L.map(mapHost, {
      zoomControl: false,
      attributionControl: false,
      dragging: false,
      touchZoom: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false,
    });

    const tileLayer = L.tileLayer(TILE_URL, {
      subdomains: "abcd",
      maxZoom: 19,
      crossOrigin: true,
    }).addTo(map);

    const routeStyle = {
      color: TRACE_COLOR,
      weight: 6,
      opacity: 1,
      lineCap: "round",
      lineJoin: "round",
    };
    const haloStyle = {
      color: TRACE_HALO,
      weight: 10,
      opacity: 0.55,
      lineCap: "round",
      lineJoin: "round",
    };

    const group = L.geoJSON(geojson, { style: haloStyle }).addTo(map);
    L.geoJSON(geojson, { style: routeStyle }).addTo(map);
    map.fitBounds(group.getBounds(), { padding: [72, 72] });
    map.invalidateSize();

    await waitForMapReady(map, tileLayer);
    return map;
  }

  async function downloadOrShare(blob, filename) {
    const file = new File([blob], filename, { type: "image/png" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: filename });
      return;
    }
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function generateShareCard() {
    const menu = document.getElementById("activity-options");
    if (menu) menu.open = false;

    const originalText = shareBtn.textContent;
    shareBtn.disabled = true;
    shareBtn.textContent = "Generating…";

    const host = document.createElement("div");
    host.className = "share-card-export-host";
    let map = null;

    try {
      const card = buildCardElement(activityData);
      host.appendChild(card);
      document.body.appendChild(host);

      if (activityData.hasMap && activityData.geojsonUrl) {
        const mapHost = card.querySelector("#share-card-map");
        map = await renderRouteMap(mapHost, activityData.geojsonUrl);
      }

      await new Promise(function (resolve) {
        requestAnimationFrame(function () {
          requestAnimationFrame(resolve);
        });
      });

      if (typeof htmlToImage === "undefined") {
        throw new Error("Image export library failed to load.");
      }

      const dataUrl = await htmlToImage.toPng(card, {
        pixelRatio: 1,
        cacheBust: true,
      });
      const resp = await fetch(dataUrl);
      const blob = await resp.blob();
      await downloadOrShare(blob, getFilename());
    } catch (err) {
      alert(err.message || "Could not generate share card.");
    } finally {
      if (map) map.remove();
      if (host.parentNode) host.parentNode.removeChild(host);
      shareBtn.disabled = false;
      shareBtn.textContent = originalText;
    }
  }

  shareBtn.addEventListener("click", generateShareCard);
})();
