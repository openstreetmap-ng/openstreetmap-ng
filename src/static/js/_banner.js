import { isBannerHidden, markBannerHidden } from "./_local-storage.js"

const banners = document.querySelectorAll(".sidebar-banner")

// Show banners that are not explicitly hidden and listen for events
for (const banner of banners) {
    const bannerName = banner.dataset.name
    if (!isBannerHidden(bannerName)) {
        banner.addEventListener("close.bs.alert", () => markBannerHidden(bannerName))
        banner.classList.remove("d-none")
    }
}
