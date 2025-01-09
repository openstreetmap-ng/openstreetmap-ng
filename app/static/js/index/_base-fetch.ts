import type * as L from "leaflet"
import { resolveDatetime } from "../_datetime"
import { requestAnimationFramePolyfill } from "../_utils"
import { configureActionSidebar, getActionSidebar, switchActionSidebar } from "./_action-sidebar"

let currentUrl: string | null = null
let sidebarScrollPosition = 0

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
    const scrollSidebar = sidebar.closest(".sidebar")
    const dynamicContent = sidebar.classList.contains("dynamic-content")
        ? sidebar
        : sidebar.querySelector("div.dynamic-content")
    const loadingHtml = dynamicContent.innerHTML

    let abortController: AbortController | null = null

    /** On sidebar loading, display loading content */
    const onSidebarLoading = () => {
        sidebarScrollPosition = scrollSidebar.scrollTop
        console.debug("Save sidebar scroll position", sidebarScrollPosition)
        dynamicContent.innerHTML = loadingHtml
    }

    /** On sidebar loaded, display content and call callback */
    const onSidebarLoaded = (html: string, newUrl: string): void => {
        dynamicContent.innerHTML = html
        resolveDatetime(dynamicContent)
        configureActionSidebar(sidebar)

        if (currentUrl === newUrl) {
            // If reload, restore sidebar scroll position
            const startTime = performance.now()
            const tryRestoreScroll = () => {
                if (scrollSidebar.scrollHeight > sidebarScrollPosition) {
                    scrollSidebar.scrollTop = sidebarScrollPosition
                    console.debug("Restore sidebar scroll position", sidebarScrollPosition)
                    return
                }
                if (performance.now() - startTime < 2000) {
                    requestAnimationFramePolyfill(tryRestoreScroll)
                } else {
                    console.warn("Failed to restore sidebar scroll: content too small", {
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

    return {
        load: ({ url }) => {
            switchActionSidebar(map, className)
            if (!url) {
                currentUrl = url
                return
            }

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

                    onSidebarLoaded(await resp.text(), url)
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
