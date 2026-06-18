(function () {
  const TRACE_COLOR = "#FC4C02";

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

  function formatSpeed(speedKmh) {
    if (speedKmh == null || Number.isNaN(speedKmh)) return "";
    return speedKmh.toFixed(1) + " km/h";
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

  function buildDatasets(payload) {
    const segments = payload.segments || [];

    return segments.map(function (segment, index) {
      const color = TRACE_COLOR;
      const label = segment.label || "Track " + (index + 1);
      const distances = segment.distances_km || [];
      const speeds = segment.speeds_kmh || [];
      const coordinates = segment.coordinates || [];
      const data = [];

      for (let i = 0; i < distances.length; i += 1) {
        const y = speeds[i];
        if (y == null) continue;
        data.push({
          x: distances[i],
          y: y,
          coord: coordinates[i] || null,
        });
      }

      return {
        label: label,
        trackId: segment.track_id != null ? segment.track_id : index,
        data: data,
        borderColor: color,
        backgroundColor: hexToFill(color),
        fill: true,
        tension: 0.1,
        pointRadius: 0,
        borderWidth: 2,
        spanGaps: false,
      };
    });
  }

  function bindMapHover(canvas, chart, mapHover, trackIds) {
    if (!mapHover) return;

    canvas._tracksChart = chart;
    canvas._tracksDatasetIds = trackIds || [];

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
      const dataset = activeChart.data.datasets[element.datasetIndex];
      const point = dataset.data[element.index];
      const trackId = canvas._tracksDatasetIds[element.datasetIndex];
      if (point && point.coord && point.coord.length >= 2) {
        mapHover.show(point.coord[1], point.coord[0], trackId);
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
    const datasets = buildDatasets(payload);
    const trackIds = datasets.map(function (ds) {
      return ds.trackId;
    });

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
            displayColors: false,
            callbacks: {
              title: function (items) {
                if (!items.length || items[0].parsed.x == null) return "";
                return formatDistanceKm(items[0].parsed.x);
              },
              label: function (item) {
                if (item.parsed.y == null) return "";
                return formatSpeed(item.parsed.y);
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
            min: 0,
            grace: 0,
            title: { display: true, text: "Speed (km/h)", color: "#7a82a8" },
            ticks: { color: "#7a82a8" },
            grid: { color: "#2e3350" },
          },
        },
      },
    });

    bindMapHover(canvas, chart, options.mapHover, trackIds);
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

  window.TracksSpeedChart = {
    render: render,
    destroy: destroy,
  };
})();
