// Light / dark theme toggle. The initial class is set inline in <head> (no
// flash); this wires the toggle button and re-renders charts on switch.
(function () {
  function isDark() {
    return document.documentElement.classList.contains("dark");
  }

  window.toggleTheme = function () {
    var dark = !isDark();
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("theme", dark ? "dark" : "light");
    } catch (e) {
      /* ignore */
    }
    // Recolor existing charts (axes / legend) for the new theme.
    if (window.refreshChartTheme) window.refreshChartTheme();
  };

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-theme-toggle]")) window.toggleTheme();
  });
})();
