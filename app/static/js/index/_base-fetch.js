import * as L from "leaflet"
import { configureActionSidebar, getActionSidebar, switchActionSidebar } from "./_action-sidebar.js"

/**
 * Create a base fetch controller
 * @param {L.Map} map Leaflet map
 * @param {string} className Class name of the sidebar
 * @param {function} successCallback Successful load callback
 * @returns {object} Controller
 */
export const getBaseFetchController = (map, className, successCallback) => {
    const sidebar = getActionSidebar(className)
    const dynamicContent = sidebar.classList.contains("dynamic-content")
        ? sidebar
        : sidebar.querySelector(".dynamic-content")
    const loadingHtml = dynamicContent.innerHTML

    let abortController = null

    // On sidebar loading, display loading content
    const onSidebarLoading = () => {
        dynamicContent.innerHTML = loadingHtml
    }

    // On sidebar loaded, display content and call callback
    const onSidebarLoaded = (html) => {
        dynamicContent.innerHTML = html
        configureActionSidebar(sidebar)
    }

    return {
        load: ({ url }) => {
            switchActionSidebar(map, className)

            // Abort any pending request
            if (abortController) abortController.abort()
            abortController = new AbortController()

            onSidebarLoading()

            fetch(url, {
                method: "GET",
                mode: "same-origin",
                cache: "no-store",
                signal: abortController.signal,
                priority: "high",
            })
                .then(async (resp) => {
                    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

                    onSidebarLoaded(await resp.text())
                    if (successCallback) successCallback(dynamicContent)
                })
                .catch((error) => {
                    // TODO: handle exceptions nicely
                    if (error.name === "AbortError") return
                    console.error("Failed to fetch sidebar", error)
                    alert(error.message)
                })
        },
        unload: () => {
            // do nothing
        },
    }
}
