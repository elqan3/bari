const navToggleButton = document.querySelector(".nav-toggle");
const navLinksContainer = document.querySelector(".nav-links");
const navLinks = document.querySelectorAll(".nav-links a");

if (navToggleButton && navLinksContainer) {
    navToggleButton.addEventListener("click", () => {
        const isOpen = navLinksContainer.classList.toggle("is-open");
        navToggleButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });

    navLinks.forEach((link) => {
        link.addEventListener("click", () => {
            navLinksContainer.classList.remove("is-open");
            navToggleButton.setAttribute("aria-expanded", "false");
        });
    });
}

const lightbox = document.getElementById("portfolio-lightbox");
const lightboxImage = document.getElementById("lightbox-image");
const openImageButtons = document.querySelectorAll(".work-image-btn");
const closeLightboxElements = document.querySelectorAll("[data-close-lightbox]");

function closeLightbox() {
    if (!lightbox) return;
    lightbox.classList.remove("is-open");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("no-scroll");
}

if (lightbox && lightboxImage) {
    openImageButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const imageSrc = button.dataset.imageSrc;
            const imageAlt = button.dataset.imageAlt || "صورة من معرض الأعمال";

            lightboxImage.src = imageSrc;
            lightboxImage.alt = imageAlt;
            lightbox.classList.add("is-open");
            lightbox.setAttribute("aria-hidden", "false");
            document.body.classList.add("no-scroll");
        });
    });

    closeLightboxElements.forEach((element) => {
        element.addEventListener("click", closeLightbox);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeLightbox();
        }
    });
}
