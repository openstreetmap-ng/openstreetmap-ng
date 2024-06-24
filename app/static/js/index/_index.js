import * as L from "leaflet"
import { isBannerHidden, markBannerHidden } from "../_local-storage.js"
import { getPageTitle } from "../_title.js"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar.js"
import { setSearchFormQuery } from "./_search-form.js"

/**
 * Create a new index controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getIndexController = (map) => {
    const sidebar = getActionSidebar("index")
    const banners = sidebar.querySelectorAll(".sidebar-banner")

    for (const banner of banners) {
        const bannerName = banner.dataset.name

        // Remove hidden banners
        if (isBannerHidden(bannerName)) {
            banner.remove()
            continue
        }

        console.debug("Showing banner", bannerName)
        const closeButton = banner.querySelector(".btn-close")

        // On close button click, hide the banner
        const onClose = () => {
            console.debug("Hiding banner", bannerName)
            markBannerHidden(bannerName)
            banner.remove()
        }

        closeButton.addEventListener("click", onClose)
        banner.classList.remove("d-none")
    }

    return {
        load: () => {
            switchActionSidebar(map, "index")
            document.title = getPageTitle()
            setSearchFormQuery("")
        },
        unload: () => {
            // do nothing
        },
    }
}
