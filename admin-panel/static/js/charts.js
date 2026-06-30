// Dashboard charts. Built ONCE, then updated in place via chart.update() so
// htmx polling never destroys/recreates canvases (which caused the doughnuts to
// blow up and the layout to jump). Data arrives as JSON; KPIs update too.
(function () {
  if (typeof Chart === "undefined") return;

  Chart.defaults.font.family =
    "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

  var INDIGO = "#6366f1";
  var PALETTE = [
    "#6366f1", "#22c55e", "#f59e0b", "#ef4444",
    "#06b6d4", "#a855f7", "#ec4899", "#84cc16",
  ];
  var TOOLTIP = {
    backgroundColor: "#0f172a",
    titleColor: "#f8fafc",
    bodyColor: "#e2e8f0",
    padding: 10,
    cornerRadius: 8,
    displayColors: false,
    titleFont: { weight: "600" },
  };

  var charts = {};

  function isDark() {
    return document.documentElement.classList.contains("dark");
  }
  function tickColor() {
    return isDark() ? "#94a3b8" : "#64748b";
  }
  function gridColor() {
    return isDark() ? "rgba(148,163,184,0.18)" : "rgba(148,163,184,0.15)";
  }
  function doughnutBorder() {
    return isDark() ? "#1e293b" : "#ffffff";
  }

  function buildLine(canvas, rows) {
    charts.day = new Chart(canvas, {
      type: "line",
      data: {
        labels: rows.map(function (d) { return d.day; }),
        datasets: [{
          label: "Clicks",
          data: rows.map(function (d) { return d.clicks; }),
          borderColor: INDIGO,
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 3,
          pointBackgroundColor: INDIGO,
          pointHoverRadius: 5,
          backgroundColor: function (c) {
            var area = c.chart.chartArea;
            if (!area) return "rgba(99,102,241,0)";
            var g = c.chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
            g.addColorStop(0, "rgba(99,102,241,0.35)");
            g.addColorStop(1, "rgba(99,102,241,0.00)");
            return g;
          },
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 400 },
        plugins: { legend: { display: false }, tooltip: TOOLTIP },
        scales: {
          x: { grid: { display: false }, border: { display: false }, ticks: { color: tickColor() } },
          y: {
            beginAtZero: true,
            border: { display: false },
            grid: { color: gridColor() },
            ticks: { color: tickColor(), precision: 0, maxTicksLimit: 5 },
          },
        },
      },
    });
  }

  function buildDoughnut(key, canvas, rows) {
    charts[key] = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: rows.map(function (i) { return i.name; }),
        datasets: [{
          data: rows.map(function (i) { return i.clicks; }),
          backgroundColor: PALETTE,
          borderWidth: 2,
          borderColor: doughnutBorder(),
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        animation: { duration: 400 },
        plugins: {
          tooltip: TOOLTIP,
          legend: {
            position: "bottom",
            labels: { color: tickColor(), usePointStyle: true, pointStyle: "circle", padding: 14, boxWidth: 8 },
          },
        },
      },
    });
  }

  function build(stats) {
    var day = document.getElementById("chart-by-day");
    if (day) buildLine(day, stats.clicks_by_day || []);
    var dev = document.getElementById("chart-devices");
    if (dev) buildDoughnut("devices", dev, stats.devices || []);
    var brw = document.getElementById("chart-browsers");
    if (brw) buildDoughnut("browsers", brw, stats.browsers || []);
  }

  function updateLine(stats) {
    if (!charts.day) return;
    var rows = stats.clicks_by_day || [];
    charts.day.data.labels = rows.map(function (d) { return d.day; });
    charts.day.data.datasets[0].data = rows.map(function (d) { return d.clicks; });
    charts.day.update();
  }
  function updateDoughnut(key, rows) {
    if (!charts[key]) return;
    charts[key].data.labels = rows.map(function (i) { return i.name; });
    charts[key].data.datasets[0].data = rows.map(function (i) { return i.clicks; });
    charts[key].update();
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }
  function updateKpis(stats) {
    var byDay = stats.clicks_by_day || [];
    var today = byDay.length ? byDay[byDay.length - 1].clicks : 0;
    var top = (stats.top_links || [])[0];
    setText("kpi-total", stats.total_clicks != null ? stats.total_clicks : 0);
    setText("kpi-today", today);
    setText("kpi-top", top ? top.short_code : "—");
    setText("kpi-top-clicks", top ? top.clicks + " clicks" : "");
  }

  // Public: apply a fresh stats payload (builds charts once, then updates).
  window.applyStats = function (stats) {
    if (!stats) return;
    if (!charts.day && !charts.devices && !charts.browsers) {
      build(stats);
    } else {
      updateLine(stats);
      updateDoughnut("devices", stats.devices || []);
      updateDoughnut("browsers", stats.browsers || []);
    }
    updateKpis(stats);
  };

  // Public: recolor existing charts when the theme toggles.
  window.refreshChartTheme = function () {
    if (charts.day) {
      charts.day.options.scales.x.ticks.color = tickColor();
      charts.day.options.scales.y.ticks.color = tickColor();
      charts.day.options.scales.y.grid.color = gridColor();
      charts.day.update();
    }
    ["devices", "browsers"].forEach(function (k) {
      if (!charts[k]) return;
      charts[k].options.plugins.legend.labels.color = tickColor();
      charts[k].data.datasets[0].borderColor = doughnutBorder();
      charts[k].update();
    });
  };

  function init() {
    var el = document.getElementById("stats-data");
    if (!el) return;
    try {
      window.applyStats(JSON.parse(el.textContent || "{}"));
    } catch (e) {
      /* ignore malformed payload */
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
