import {
    configureActionSidebar,
    getActionSidebar,
    switchActionSidebar,
} from "@index/_action-sidebar"
import { resolveDatetimeLazy } from "@lib/datetime-inputs"
import { requestAnimationFramePolyfill } from "@lib/polyfills"
import { assert } from "@std/assert"
import type { Map as MaplibreMap } from "maplibre-gl"

let currentUrl: string | null = null
let sidebarScrollPosition = 0

export const getBaseFetchController = (
    map: MaplibreMap,
    className: string,
    loadCallback?: (sidebarContent: HTMLElement) => void | (() => void),
) => {
    const sidebar = getActionSidebar(className)
    const scrollSidebar = sidebar.closest(".sidebar")!
    const dynamicContent = sidebar.classList.contains("dynamic-content")
        ? sidebar
        : sidebar.querySelector("div.dynamic-content")!
    const loadingHtml = dynamicContent.innerHTML

    let abortController: AbortController | undefined
    let loadCallbackDispose: void | (() => void)

    const onSidebarLoading = () => {
        // On sidebar loading, display loading content
        sidebarScrollPosition = scrollSidebar.scrollTop
        console.debug("Sidebar: Saved scroll position", sidebarScrollPosition)
        dynamicContent.innerHTML = loadingHtml
    }

    const onSidebarLoaded = (html: string, newUrl: string) => {
        // On sidebar loaded, display content and call callback
        dynamicContent.innerHTML = html
        resolveDatetimeLazy(dynamicContent)
        configureActionSidebar(sidebar)

        if (currentUrl === newUrl) {
            // If reload, restore sidebar scroll position
            const startTime = performance.now()
            const tryRestoreScroll = () => {
                if (scrollSidebar.scrollHeight > sidebarScrollPosition) {
                    scrollSidebar.scrollTop = sidebarScrollPosition
                    console.debug(
                        "Sidebar: Restored scroll position",
                        sidebarScrollPosition,
                    )
                    return
                }
                if (performance.now() - startTime < 2000) {
                    requestAnimationFramePolyfill(tryRestoreScroll)
                } else {
                    console.warn("Sidebar: Failed to restore scroll position", {
                        target: sidebarScrollPosition,
                        actual: scrollSidebar.scrollHeight,
                        newUrl,
                    })
                }
            }
            requestAnimationFramePolyfill(tryRestoreScroll)
        } else {
            currentUrl = newUrl
        }
    }

    /** Fetch sidebar content from url */
    const fetchSidebar = async (url: string) => {
        abortController = new AbortController()

        try {
            const resp = await fetch(url, {
                signal: abortController.signal,
                priority: "high",
            })
            assert(resp.ok || resp.status === 404, `${resp.status} ${resp.statusText}`)
            onSidebarLoaded(await resp.text(), url)
            loadCallbackDispose = loadCallback?.(dynamicContent)
        } catch (error) {
            if (error.name === "AbortError") return
            console.error("Sidebar: Failed to fetch", url, error)
            dynamicContent.textContent = error.message
            alert(error.message)
        }
    }

    return {
        load: (url: string | null) => {
            switchActionSidebar(map, sidebar)
            if (url === null) {
                currentUrl = null
                return
            }

            onSidebarLoading()
            fetchSidebar(url)
        },
        unload: () => {
            abortController?.abort()
            if (typeof loadCallbackDispose === "function") {
                loadCallbackDispose()
                loadCallbackDispose = undefined
            }
        },
    }
}
