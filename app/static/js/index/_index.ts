import type * as L from "leaflet"
import { isBannerHidden, markBannerHidden } from "../_local-storage"
import { getPageTitle } from "../_title"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { FetchController } from "./_base-fetch"
import { setSearchFormQuery } from "./_search-form"

/** Create a new index controller */
export const getIndexController = (map: L.Map): FetchController => {
    const sidebar = getActionSidebar("index")
    const banners: NodeListOf<HTMLElement> = sidebar.querySelectorAll(".sidebar-banner")

    for (const banner of banners) {
        const bannerName = banner.dataset.name

        // Remove hidden banners
        if (isBannerHidden(bannerName)) {
            banner.remove()
            continue
        }

        console.debug("Showing banner", bannerName)
        banner.classList.remove("d-none")

        const closeButton = banner.querySelector(".btn-close")
        closeButton.addEventListener("click", () => {
            // On close button click, hide the banner
            markBannerHidden(bannerName)
            banner.remove()
        })
    }

    return {
        load: () => {
            switchActionSidebar(map, "index")
            document.title = getPageTitle()
            setSearchFormQuery("")
        },
        unload: () => {}, // do nothing
    }
}
