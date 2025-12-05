import { getActionSidebar, switchActionSidebar } from "@index/_action-sidebar"
import { setSearchFormQuery } from "@index/search-form"
import { isBannerHidden, markBannerHidden } from "@lib/local-storage"
import { setPageTitle } from "@lib/title"
import type { Map as MaplibreMap } from "maplibre-gl"

/** Create a new index controller */
export const getIndexController = (map: MaplibreMap) => {
    const sidebar = getActionSidebar("index")
    const banners = sidebar.querySelectorAll("div.sidebar-banner")

    for (const banner of banners) {
        const bannerName = banner.dataset.name

        // Remove hidden banners
        if (isBannerHidden(bannerName)) {
            banner.remove()
            continue
        }

        console.debug("Showing banner", bannerName)
        banner.classList.remove("d-none")

        // On close button click, hide the banner
        const closeButton = banner.querySelector(".btn-close")
        closeButton.addEventListener("click", () => {
            markBannerHidden(bannerName)
            banner.remove()
        })
    }

    return {
        load: () => {
            switchActionSidebar(map, sidebar)
            setPageTitle()
            setSearchFormQuery("")
        },
        unload: () => {},
    }
}
