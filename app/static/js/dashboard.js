(function () {
  const section = document.querySelector(".dashboard-highlights");
  if (!section) return;

  const tabs = section.querySelectorAll(".profile-tab");
  const recentPanel = document.getElementById("dashboard-panel-recent");
  const recordsPanel = document.getElementById("dashboard-panel-records");
  const links = section.querySelectorAll(".dashboard-highlights-link");

  function setActiveTab(tabName) {
    tabs.forEach(function (tab) {
      const isActive = tab.dataset.tab === tabName;
      tab.classList.toggle("active", isActive);
      tab.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    if (recentPanel) recentPanel.hidden = tabName !== "recent";
    if (recordsPanel) recordsPanel.hidden = tabName !== "records";
    links.forEach(function (link) {
      link.hidden = link.dataset.tabLink !== tabName;
    });
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      setActiveTab(tab.dataset.tab);
    });
  });
})();
