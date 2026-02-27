import { getBaseFetchController } from "@index/_base-fetch"
import { resolveDatetimeLazy } from "@lib/datetime-inputs"
import { setPageTitle } from "@lib/title"
import type { Map as MaplibreMap } from "maplibre-gl"
import type { IndexController } from "./router"

/** Create a new element deep history controller */
export const getElementDeepHistoryController = (map: MaplibreMap) => {
    const base = getBaseFetchController(map, "element-deep-history", (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        if (sidebarTitleElement) {
            setPageTitle(sidebarTitleElement.textContent)
        }

        // Handle version limit selector
        const limitSelect = sidebarContent.querySelector("select.version-limit") as HTMLSelectElement | null
        if (limitSelect) {
            limitSelect.addEventListener("change", () => {
                const newLimit = limitSelect.value
                const currentUrl = new URL(window.location.href)
                currentUrl.searchParams.set("limit", newLimit)
                window.location.href = currentUrl.toString()
            })
        }

        // Handle clickable rows
        const rows = sidebarContent.querySelectorAll("tr.version-row[data-href]")
        for (const row of rows) {
            row.addEventListener("click", (e) => {
                const target = e.target as HTMLElement
                // Don't navigate if clicking on a link inside the row
                if (target.closest("a")) return
                const href = (row as HTMLElement).dataset.href
                if (href) window.location.href = href
            })
            // Add pointer cursor
            ;(row as HTMLElement).style.cursor = "pointer"
        }

        // Resolve datetime elements
        resolveDatetimeLazy(sidebarContent)
    })

    const controller: IndexController = {
        load: ({ type, id }) => {
            const params = new URLSearchParams(window.location.search)
            const limit = params.get("limit") || ""
            const limitParam = limit ? `?limit=${limit}` : ""
            base.load(`/partial/${type}/${id}/deep-history${limitParam}`)
        },
        unload: base.unload,
    }
    return controller
}
