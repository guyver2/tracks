(function () {
  const mapEl = document.getElementById("map");
  if (!mapEl) return;

  const elevationUrl = mapEl.dataset.elevationUrl;
  const speedUrl = mapEl.dataset.speedUrl;
  if (!elevationUrl && !speedUrl) return;

  const chartCard = document.getElementById("profile-chart-card");
  const elevationCanvas = document.getElementById("elevation-chart");
  const speedCanvas = document.getElementById("speed-chart");
  const errorEl = document.getElementById("profile-chart-error");
  const elevationPanel = document.getElementById("profile-panel-elevation");
  const speedPanel = document.getElementById("profile-panel-speed");
  const tabs = chartCard ? chartCard.querySelectorAll(".profile-tab") : [];

  if (!chartCard || !elevationCanvas || !speedCanvas) return;

  const activityType = mapEl.dataset.activityType || "hike";
  let elevationChart = null;
  let speedChart = null;
  let elevationData = null;
  let speedData = null;
  let activeTab = "elevation";

  function showError(message) {
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.hidden = false;
    }
  }

  function setActiveTab(tabName) {
    activeTab = tabName;
    tabs.forEach(function (tab) {
      const isActive = tab.dataset.tab === tabName;
      tab.classList.toggle("active", isActive);
      tab.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    if (elevationPanel) elevationPanel.hidden = tabName !== "elevation";
    if (speedPanel) speedPanel.hidden = tabName !== "speed";
    if (window.tracksMapHover) window.tracksMapHover.clear();
  }

  function renderCharts() {
    if (elevationData && elevationData.has_elevation) {
      if (elevationCanvas.dataset.hoverBound) delete elevationCanvas.dataset.hoverBound;
      window.TracksElevationChart.destroy(elevationChart, elevationCanvas);
      elevationChart = window.TracksElevationChart.render(elevationCanvas, elevationData, {
        activityType: activityType,
        mapHover: activeTab === "elevation" ? window.tracksMapHover : null,
      });
    }
    if (speedData && speedData.has_speed) {
      if (speedCanvas.dataset.hoverBound) delete speedCanvas.dataset.hoverBound;
      window.TracksSpeedChart.destroy(speedChart, speedCanvas);
      speedChart = window.TracksSpeedChart.render(speedCanvas, speedData, {
        activityType: activityType,
        mapHover: activeTab === "speed" ? window.tracksMapHover : null,
      });
    }
  }

  function refreshProfileVisibility() {
    const hasElevation = elevationData && elevationData.has_elevation;
    const hasSpeed = speedData && speedData.has_speed;
    if (!hasElevation && !hasSpeed) {
      chartCard.hidden = true;
      return;
    }

    chartCard.hidden = false;
    tabs.forEach(function (tab) {
      if (tab.dataset.tab === "speed") {
        tab.hidden = !hasSpeed;
      }
      if (tab.dataset.tab === "elevation") {
        tab.hidden = !hasElevation;
      }
    });

    if (hasElevation) {
      activeTab = "elevation";
    } else if (hasSpeed) {
      activeTab = "speed";
    }
    setActiveTab(activeTab);

    requestAnimationFrame(function () {
      try {
        renderCharts();
      } catch (err) {
        showError("Could not render profile chart.");
        console.error(err);
      }
    });
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      const tabName = tab.dataset.tab;
      if (!tabName || tabName === activeTab) return;
      if (tabName === "speed" && (!speedData || !speedData.has_speed)) return;
      if (tabName === "elevation" && (!elevationData || !elevationData.has_elevation)) return;
      setActiveTab(tabName);
      if (window.tracksMapHover) window.tracksMapHover.clear();
      renderCharts();
    });
  });

  async function loadProfiles() {
    try {
      const requests = [];
      if (elevationUrl) {
        requests.push(fetch(elevationUrl).then(function (r) { return r.ok ? r.json() : null; }));
      } else {
        requests.push(Promise.resolve(null));
      }
      if (speedUrl) {
        requests.push(fetch(speedUrl).then(function (r) { return r.ok ? r.json() : null; }));
      } else {
        requests.push(Promise.resolve(null));
      }

      const results = await Promise.all(requests);
      elevationData = results[0];
      speedData = results[1];
      refreshProfileVisibility();
    } catch (err) {
      showError("Could not load profile data.");
      console.error(err);
    }
  }

  loadProfiles();
})();
