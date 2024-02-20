import { getActionSidebar, switchActionSidebar } from "../_action-sidebar.js"

/**
 * Create a base fetch controller
 * @param {string} className Class name of the sidebar
 * @param {function} loadedCallback Callback when loaded
 * @returns {object} Controller
 */
export const getBaseFetchController = (className, loadedCallback) => {
    const sidebar = getActionSidebar(className)
    const dynamicContent = sidebar.querySelector(".dynamic-content")
    const loadingHtml = dynamicContent.innerHTML

    let abortController = null

    // On sidebar loading, display loading content
    const onSidebarLoading = () => {
        dynamicContent.innerHTML = loadingHtml
    }

    // On sidebar loaded, display content and call callback
    const onSidebarLoaded = (html) => {
        dynamicContent.innerHTML = html
        if (loadedCallback) loadedCallback(dynamicContent)
    }

    return {
        load: ({ url }) => {
            switchActionSidebar(className)

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
                    // TODO: handle exceptions nicely
                    onSidebarLoaded(await resp.text())
                })
                .catch((error) => {
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
