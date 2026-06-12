(function () {
  function scrollToToday() {
    document.querySelectorAll(".calendar-scroll").forEach((scroll) => {
      const today = scroll.querySelector(".calendar-cell-today");
      if (!today) return;

      const scrollRect = scroll.getBoundingClientRect();
      const todayRect = today.getBoundingClientRect();
      scroll.scrollLeft += todayRect.right - scrollRect.right;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scrollToToday);
  } else {
    scrollToToday();
  }
})();
