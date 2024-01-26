import { getActionSidebar, switchActionSidebar } from "../_action-sidebar.js"

/**
 * Create a base fetch controller
 * @param {string} className Class name of the sidebar
 * @returns {object} Controller
 */
export const getBaseFetchController = (className, { loadedCallback = null }) => {
    const sidebar = getActionSidebar(className)
    const sidebarContent = sidebar.querySelector(".sidebar-content")
    const sidebarLoadingContent = sidebarContent

    let abortController = null

    // On sidebar loading, display loading content
    const onSidebarLoading = () => {
        sidebarContent.replaceWith(sidebarLoadingContent.cloneNode(true))
    }

    // On sidebar loaded, display content and call callback
    const onSidebarLoaded = (html) => {
        sidebarContent.innerHTML = html
        if (loadedCallback) loadedCallback(sidebarContent)
    }

    return {
        load: ({ url }) => {
            switchActionSidebar(className)

            // Abort any pending request
            if (abortController) abortController.abort()
            abortController = new AbortController()

            onSidebarLoading()

            fetch(url, {
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

                    console.error(error)
                    alert(error.message)
                })
        },
        unload: () => {
            // do nothing
        },
    }
}
