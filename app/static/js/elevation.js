(function () {
  const mapEl = document.getElementById("map");
  if (!mapEl) return;

  const elevationUrl = mapEl.dataset.elevationUrl;
  if (!elevationUrl) return;

  const chartCard = document.getElementById("elevation-chart-card");
  const canvas = document.getElementById("elevation-chart");
  if (!chartCard || !canvas) return;

  const activityType = mapEl.dataset.activityType || "hike";
  const traceColors = {
    hike: "#43c78a",
    bike: "#5b8dee",
    skitouring: "#e8a64c",
  };
  const fillColors = {
    hike: "rgba(67, 199, 138, 0.2)",
    bike: "rgba(91, 141, 238, 0.2)",
    skitouring: "rgba(232, 166, 76, 0.2)",
  };
  const traceColor = traceColors[activityType] || traceColors.hike;
  const fillColor = fillColors[activityType] || fillColors.hike;

  async function loadElevation() {
    try {
      const resp = await fetch(elevationUrl);
      if (!resp.ok) return;
      const data = await resp.json();
      if (!data.has_elevation) return;

      chartCard.hidden = false;

      new Chart(canvas, {
        type: "line",
        data: {
          labels: data.distances_km,
          datasets: [{
            label: "Elevation (m)",
            data: data.elevations_m,
            borderColor: traceColor,
            backgroundColor: fillColor,
            fill: true,
            tension: 0.1,
            pointRadius: 0,
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: (items) => items[0].label + " km",
                label: (item) => item.parsed.y + " m",
              },
            },
          },
          scales: {
            x: {
              title: { display: true, text: "Distance (km)", color: "#7a82a8" },
              ticks: { color: "#7a82a8", maxTicksLimit: 8 },
              grid: { color: "#2e3350" },
            },
            y: {
              title: { display: true, text: "Elevation (m)", color: "#7a82a8" },
              ticks: { color: "#7a82a8" },
              grid: { color: "#2e3350" },
            },
          },
        },
      });
    } catch {
      /* no chart */
    }
  }

  loadElevation();
})();
