import type * as L from "leaflet"
import { resolveDatetime } from "../_datetime"
import { configureActionSidebar, getActionSidebar, switchActionSidebar } from "./_action-sidebar"

export interface BaseFetchController {
    load: ({ url }: { url: string | null }) => void
    unload: () => void
}

/** Create a base fetch controller */
export const getBaseFetchController = (
    map: L.Map,
    className: string,
    successCallback?: (dynamicContent: HTMLElement) => void,
): BaseFetchController => {
    const sidebar = getActionSidebar(className)
    const dynamicContent = sidebar.classList.contains("dynamic-content")
        ? sidebar
        : sidebar.querySelector("div.dynamic-content")
    const loadingHtml = dynamicContent.innerHTML

    let abortController: AbortController | null = null


    // store scroll position
    let scrollPosition: number = 0
    let sidebarScrollPosition: number = 0


    /** On sidebar loading, display loading content */
    const onSidebarLoading = () => {
        scrollPosition = window.scrollY
        sidebarScrollPosition = dynamicContent.scrollTop
        dynamicContent.innerHTML = loadingHtml
    }

    /** On sidebar loaded, display content and call callback */
    const onSidebarLoaded = (html: string): void => {
        dynamicContent.innerHTML = html
        resolveDatetime(dynamicContent)
        configureActionSidebar(sidebar)

          // Restore global scroll position
        window.setTimeout(() => {
            window.scrollTo(0, scrollPosition)
        }, 50)

        // Restore sidebar scroll position
        dynamicContent.scrollTop = sidebarScrollPosition
    }

    return {
        load: ({ url }) => {
            switchActionSidebar(map, className)
            if (!url) return

            // Abort any pending request
            abortController?.abort()
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
                    if (!resp.ok && resp.status !== 404) throw new Error(`${resp.status} ${resp.statusText}`)

                    onSidebarLoaded(await resp.text())
                    successCallback?.(dynamicContent)
                })
                .catch((error) => {
                    if (error.name === "AbortError") return
                    console.error("Failed to fetch sidebar", error)
                    dynamicContent.textContent = error.message
                    alert(error.message)
                })
        },
        unload: () => {},
    }
}
