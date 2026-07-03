(function () {
  const gallery = document.querySelector("[data-photo-gallery]");
  const dialog = document.getElementById("photo-lightbox");
  if (!gallery || !dialog) return;

  const imageEl = dialog.querySelector(".photo-lightbox-image");
  const counterEl = dialog.querySelector(".photo-lightbox-counter");
  const footerEl = dialog.querySelector(".photo-lightbox-footer");
  const titleEl = dialog.querySelector(".photo-lightbox-title");
  const prevBtn = dialog.querySelector(".photo-lightbox-prev");
  const nextBtn = dialog.querySelector(".photo-lightbox-next");
  const closeBtn = dialog.querySelector(".photo-lightbox-close");
  const buttons = Array.from(gallery.querySelectorAll(".activity-photo-btn"));
  const sources = buttons.map(function (btn) {
    return btn.dataset.photoSrc;
  });

  let currentIndex = 0;

  function showNav() {
    const multiple = sources.length > 1;
    prevBtn.hidden = !multiple;
    nextBtn.hidden = !multiple;
    counterEl.hidden = !multiple;
    if (footerEl) footerEl.hidden = !multiple;
  }

  function render(index) {
    currentIndex = (index + sources.length) % sources.length;
    imageEl.src = sources[currentIndex];
    imageEl.alt = "Activity photo " + (currentIndex + 1);
    if (titleEl) {
      titleEl.textContent = sources.length > 1
        ? "Photo " + (currentIndex + 1) + " of " + sources.length
        : "Photo";
    }
    counterEl.textContent = currentIndex + 1 + " / " + sources.length;
  }

  function open(index) {
    render(index);
    showNav();
    dialog.showModal();
  }

  function close() {
    dialog.close();
    imageEl.removeAttribute("src");
  }

  function step(delta) {
    render(currentIndex + delta);
  }

  buttons.forEach(function (btn, index) {
    btn.addEventListener("click", function () {
      open(index);
    });
  });

  closeBtn.addEventListener("click", close);

  prevBtn.addEventListener("click", function () {
    step(-1);
  });

  nextBtn.addEventListener("click", function () {
    step(1);
  });

  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) close();
  });

  dialog.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      step(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      step(1);
    }
  });
})();
