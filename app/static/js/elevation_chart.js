(function () {
  const defaultTraceColors = {
    hike: "#43c78a",
    bike: "#5b8dee",
    skitouring: "#e8a64c",
  };
  const defaultFillColors = {
    hike: "rgba(67, 199, 138, 0.2)",
    bike: "rgba(91, 141, 238, 0.2)",
    skitouring: "rgba(232, 166, 76, 0.2)",
  };

  function hexToFill(hexColor) {
    const hex = hexColor.replace("#", "");
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return "rgba(" + r + ", " + g + ", " + b + ", 0.2)";
  }

  function formatDistanceKm(km) {
    if (km == null || Number.isNaN(km)) return "";
    if (km < 1) return km.toFixed(2) + " km";
    return km.toFixed(1) + " km";
  }

  function chartMaxKm(payload, datasets) {
    if (payload.total_distance_km != null) {
      return payload.total_distance_km;
    }
    let maxX = 0;
    datasets.forEach(function (dataset) {
      dataset.data.forEach(function (point) {
        if (point.x > maxX) maxX = point.x;
      });
    });
    return maxX;
  }

  function buildDatasets(payload, activityType) {
    const defaultColor = defaultTraceColors[activityType] || defaultTraceColors.hike;
    const defaultFill = defaultFillColors[activityType] || defaultFillColors.hike;
    const segments = payload.segments || [];

    return segments.map(function (segment, index) {
      const color = segment.color || defaultColor;
      const label = segment.label || "Track " + (index + 1);
      const distances = segment.distances_km || [];
      const elevations = segment.elevations_m || [];
      const coordinates = segment.coordinates || [];
      const data = [];

      for (let i = 0; i < distances.length; i += 1) {
        const y = elevations[i];
        if (y == null) continue;
        data.push({
          x: distances[i],
          y: y,
          coord: coordinates[i] || null,
        });
      }

      return {
        label: label,
        data: data,
        borderColor: color,
        backgroundColor: segment.color ? hexToFill(color) : defaultFill,
        fill: true,
        tension: 0.1,
        pointRadius: 0,
        borderWidth: 2,
        spanGaps: false,
      };
    });
  }

  function bindMapHover(canvas, chart, mapHover) {
    if (!mapHover) return;

    canvas._tracksChart = chart;

    function updateHover(event) {
      const activeChart = canvas._tracksChart;
      if (!activeChart) return;
      const elements = activeChart.getElementsAtEventForMode(
        event,
        "nearest",
        { intersect: false, axis: "x" },
        false
      );
      if (!elements.length) {
        mapHover.clear();
        return;
      }
      const element = elements[0];
      const point = activeChart.data.datasets[element.datasetIndex].data[element.index];
      if (point && point.coord && point.coord.length >= 2) {
        mapHover.show(point.coord[1], point.coord[0]);
      } else {
        mapHover.clear();
      }
    }

    function clearHover() {
      mapHover.clear();
    }

    if (canvas.dataset.hoverBound) return;
    canvas.dataset.hoverBound = "1";
    canvas.addEventListener("mousemove", updateHover);
    canvas.addEventListener("touchmove", updateHover, { passive: true });
    canvas.addEventListener("mouseleave", clearHover);
    canvas.addEventListener("touchend", clearHover);
  }

  function render(canvas, payload, options) {
    options = options || {};
    const activityType = options.activityType || "hike";
    const datasets = buildDatasets(payload, activityType);

    if (!datasets.length || datasets.every(function (ds) { return !ds.data.length; })) {
      return null;
    }

    const maxX = chartMaxKm(payload, datasets);

    const chart = new Chart(canvas, {
      type: "line",
      data: { datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", intersect: false, axis: "x" },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: function (items) {
                if (!items.length || items[0].parsed.x == null) return "";
                return formatDistanceKm(items[0].parsed.x);
              },
              label: function (item) {
                if (item.parsed.y == null) return item.dataset.label;
                return item.dataset.label + ": " + Math.round(item.parsed.y) + " m";
              },
            },
          },
        },
        scales: {
          x: {
            type: "linear",
            position: "bottom",
            min: 0,
            max: maxX,
            grace: 0,
            title: { display: true, text: "Distance (km)", color: "#7a82a8" },
            ticks: { color: "#7a82a8", maxTicksLimit: 8 },
            grid: { color: "#2e3350" },
          },
          y: {
            title: {
              display: true,
              text: payload.elevation_source === "dem" ? "Elevation (m)*" : "Elevation (m)",
              color: "#7a82a8",
            },
            ticks: { color: "#7a82a8" },
            grid: { color: "#2e3350" },
          },
        },
      },
    });

    bindMapHover(canvas, chart, options.mapHover);
    chart.resize();
    return chart;
  }

  function destroy(chartInstance, canvas) {
    if (canvas) {
      canvas._tracksChart = null;
    }
    if (chartInstance) {
      chartInstance.destroy();
    }
  }

  window.TracksElevationChart = {
    render: render,
    destroy: destroy,
  };
})();
