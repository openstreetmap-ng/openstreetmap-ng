import { effect, signal } from "@preact/signals-core"
import i18next from "i18next"
import { resolveDatetimeLazy } from "./datetime"

const paginationDistance = 2

export const configureStandardPagination = (
    container?: ParentNode,
    options?: {
        initialPage?: number
        reverse?: boolean
        customLoader?: (page: number, renderContainer: HTMLElement) => void
        loadCallback?: (renderContainer: HTMLElement) => void
    },
): (() => void) => {
    if (!container) {
        console.debug("Ignored standard pagination: missing container")
        return () => {}
    }

    const renderContainer =
        container.querySelector("ul.list-unstyled") ?? container.querySelector("tbody")
    const paginationContainers = container.querySelectorAll("ul.pagination")
    if (!renderContainer || !paginationContainers.length) {
        console.debug(
            "Ignored standard pagination: missing renderContainer/paginationContainers",
        )
        return () => {}
    }

    const dataset = paginationContainers[paginationContainers.length - 1].dataset
    const totalPages = Number.parseInt(dataset.pages || "0", 10)
    let cursors = null
    try {
        cursors = dataset.cursors ? JSON.parse(dataset.cursors) : null
    } catch (e) {
        console.warn("Failed to parse cursors data:", e)
        cursors = null
    }
    
    // Determine pagination mode based on available data
    const useCursors = cursors && Array.isArray(cursors) && cursors.length > 0
    
    if (!totalPages && !useCursors) {
        console.debug("Ignored standard pagination: missing data-pages or data-cursors")
        return () => {}
    }

    const pageSize = Number.parseInt(dataset.pageSize, 10)
    const numItems = Number.parseInt(dataset.numItems, 10)
    const reverse = options?.reverse ?? true

    const endpointPattern = useCursors ? dataset.action : (dataset.fallbackAction || dataset.action)
    console.debug(
        "Initializing standard pagination",
        useCursors ? "cursor-based" : "offset-based",
        options?.customLoader ? "<custom loader>" : endpointPattern,
    )
    
    let currentPage = signal(options?.initialPage ?? (reverse ? totalPages : 1))
    let currentCursor = signal<any>(null)
    
    if (useCursors) {
        // Initialize cursor from URL or dataset
        const urlParams = new URLSearchParams(window.location.search)
        const initialCursor = urlParams.get('after') || urlParams.get('before') || cursors[0]
        currentCursor = signal(initialCursor)
    }
    
    let firstLoad = true

    const setPendingState = (state: boolean): void => {
        renderContainer.style.opacity = !firstLoad && state ? "0.5" : ""

        // Only show spinner during initial load
        if (firstLoad && state) {
            firstLoad = false
            const spinner = document.createElement("div")
            spinner.className = "text-center pagination-spinner"

            const spinnerElement = document.createElement("div")
            spinnerElement.className = "spinner-border text-body-secondary"
            spinnerElement.setAttribute("role", "status")

            const srText = document.createElement("span")
            srText.className = "visually-hidden"
            srText.textContent = i18next.t("browse.start_rjs.loading")

            spinnerElement.appendChild(srText)
            spinner.appendChild(spinnerElement)
            renderContainer.innerHTML = ""
            renderContainer.appendChild(spinner)
        }
    }

    // Update collection
    const disposeCollectionEffect = effect(() => {
        if (useCursors) {
            if (!currentCursor.value) return
            const cursorValue = currentCursor.value.toString()

            if (options?.customLoader) {
                options.customLoader(1, renderContainer) // For cursors, page is always conceptually 1
                console.debug("Navigated to cursor", cursorValue)
                return
            }

            const abortController = new AbortController()
            
            let url: string
            if (endpointPattern.includes('?')) {
                url = `${endpointPattern}&after=${encodeURIComponent(cursorValue)}`
            } else {
                url = `${endpointPattern}?after=${encodeURIComponent(cursorValue)}`
            }

            console.debug("Navigating to cursor", cursorValue)
            setPendingState(true)
            fetch(url, {
                method: "GET",
                mode: "same-origin",
                cache: "no-store",
                signal: abortController.signal,
                priority: "high",
            })
                .then(async (resp) => {
                    if (resp.ok) console.debug("Navigated to cursor", cursorValue)
                    renderContainer.innerHTML = await resp.text()
                    resolveDatetimeLazy(renderContainer)
                    options?.loadCallback?.(renderContainer)
                })
                .catch((error: Error) => {
                    if (error.name === "AbortError") return
                    console.error("Failed to navigate to cursor", cursorValue, error)
                    renderContainer.textContent = error.message
                })
                .finally(() => {
                    setPendingState(false)
                })

            return () => abortController.abort()
        } else {
            if (!currentPage.value) return
            const currentPageString = currentPage.toString()

            if (options?.customLoader) {
                options.customLoader(currentPage.value, renderContainer)
                console.debug("Navigated to page", currentPageString)
                return
            }

            const abortController = new AbortController()

            console.debug("Navigating to page", currentPageString)
            setPendingState(true)
            fetch(endpointPattern.replace("{page}", currentPageString), {
                method: "GET",
                mode: "same-origin",
                cache: "no-store",
                signal: abortController.signal,
                priority: "high",
            })
                .then(async (resp) => {
                    if (resp.ok) console.debug("Navigated to page", currentPageString)
                    renderContainer.innerHTML = await resp.text()
                    resolveDatetimeLazy(renderContainer)
                    options?.loadCallback?.(renderContainer)
                })
                .catch((error: Error) => {
                    if (error.name === "AbortError") return
                    console.error("Failed to navigate to page", currentPageString, error)
                    renderContainer.textContent = error.message
                })
                .finally(() => {
                    setPendingState(false)
                })

            return () => abortController.abort()
        }
    })

    // Update pagination
    const disposePaginationEffect = effect(() => {
        if (useCursors) {
            if (cursors.length <= 1) {
                for (const paginationContainer of paginationContainers) {
                    paginationContainer.classList.add("d-none")
                }
                return
            }

            const currentCursorValue = currentCursor.value
            const currentIndex = cursors.findIndex((c: any) => c === currentCursorValue)

            for (const paginationContainer of paginationContainers) {
                paginationContainer.classList.remove("d-none")
                const paginationFragment = document.createDocumentFragment()

                for (let i = 0; i < cursors.length; i++) {
                    const distance = Math.abs(i - currentIndex)
                    if (distance > paginationDistance && i !== 0 && i !== cursors.length - 1) {
                        if (i === 1 || i === cursors.length - 2) {
                            const li = document.createElement("li")
                            li.classList.add("page-item", "disabled")
                            li.ariaDisabled = "true"
                            li.innerHTML = `<span class="page-link">...</span>`
                            paginationFragment.appendChild(li)
                        }
                        continue
                    }

                    const li = document.createElement("li")
                    li.classList.add("page-item")

                    const button = document.createElement("button")
                    button.type = "button"
                    button.classList.add("page-link")
                    button.textContent = (i + 1).toString()

                    li.appendChild(button)

                    if (i === currentIndex) {
                        li.classList.add("active")
                        li.ariaCurrent = "page"
                    } else {
                        button.addEventListener("click", () => {
                            currentCursor.value = cursors[i]
                        })
                    }

                    paginationFragment.appendChild(li)
                }

                paginationContainer.innerHTML = ""
                paginationContainer.appendChild(paginationFragment)
            }
        } else {
            if (totalPages <= 1) {
                for (const paginationContainer of paginationContainers) {
                    paginationContainer.classList.add("d-none")
                }
                return
            }
            const currentPageValue = currentPage.value

            for (const paginationContainer of paginationContainers) {
                paginationContainer.classList.remove("d-none")
                const paginationFragment = document.createDocumentFragment()

                for (let i = 1; i <= totalPages; i++) {
                    const distance = Math.abs(i - currentPageValue)
                    if (distance > paginationDistance && i !== 1 && i !== totalPages) {
                        if (i === 2 || i === totalPages - 1) {
                            const li = document.createElement("li")
                            li.classList.add("page-item", "disabled")
                            li.ariaDisabled = "true"
                            li.innerHTML = `<span class="page-link">...</span>`
                            paginationFragment.appendChild(li)
                        }
                        continue
                    }

                    const li = document.createElement("li")
                    li.classList.add("page-item")

                    const button = document.createElement("button")
                    button.type = "button"
                    button.classList.add("page-link")

                    if (pageSize && numItems) {
                        const [limit, offset] = standardPaginationRange(
                            i,
                            pageSize,
                            numItems,
                            reverse,
                        )
                        const itemMax = numItems - offset
                        const itemMin = itemMax - limit + 1
                        button.textContent =
                            itemMax !== itemMin
                                ? `${itemMin}...${itemMax}`
                                : itemMax.toString()
                    } else {
                        button.textContent = i.toString()
                    }

                    li.appendChild(button)

                    if (i === currentPageValue) {
                        li.classList.add("active")
                        li.ariaCurrent = "page"
                    } else {
                        button.addEventListener("click", () => {
                            currentPage.value = i
                        })
                    }

                    paginationFragment.appendChild(li)
                }

                paginationContainer.innerHTML = ""
                paginationContainer.appendChild(paginationFragment)
            }
        }
    })

    return () => {
        console.debug("Disposing standard pagination", endpointPattern)
        if (useCursors) {
            currentCursor.value = null
        } else {
            currentPage.value = 0
        }
        disposeCollectionEffect()
        disposePaginationEffect()
    }
}

/**
 * Get the range of items for the given page.
 * Returns a tuple of (limit, offset).
 */
const standardPaginationRange = (
    page: number,
    pageSize: number,
    numItems: number,
    reverse: boolean,
) => {
    const numPages = Math.ceil(numItems / pageSize)
    const offset = reverse ? (numPages - page) * pageSize : (page - 1) * pageSize
    const limit = Math.min(pageSize, numItems - offset)
    return [limit, offset]
}
