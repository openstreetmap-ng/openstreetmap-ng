import { isBannerHidden, markBannerHidden } from "../_local-storage"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"
import { setSearchFormQuery } from "./_search-form"
import { setPageTitle } from "../_title"

/** Create a new index controller */
export const getIndexController = (map: MaplibreMap): IndexController => {
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
            switchActionSidebar(map, "index")
            setPageTitle()
            setSearchFormQuery("")
        },
        unload: () => {},
    }
}
