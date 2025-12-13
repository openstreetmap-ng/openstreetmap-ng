import { resolveDatetimeLazy } from "@lib/datetime-inputs"
import { qsEncode, qsParse } from "@lib/qs"
import { batch, effect, signal } from "@preact/signals-core"
import i18next from "i18next"

const PAGINATION_DISTANCE = 2
const PAGINATION_MAX_FULL_PAGES = 15

export const configureStandardPagination = (
    container: ParentNode | null,
    options?: {
        startFromEnd?: boolean
        initialPage?: number
        customLoader?: (renderContainer: HTMLElement, page: number) => void
        loadCallback?: (renderContainer: HTMLElement, page: number) => void
    },
) => {
    if (!container) return () => {}

    const renderContainer =
        container.querySelector("ul.list-unstyled") ?? container.querySelector("tbody")
    const paginationContainers = Array.from(container.querySelectorAll("ul.pagination"))
    if (!(renderContainer && paginationContainers.length)) return () => {}

    const dataset = paginationContainers.at(-1)!.dataset
    const parsedPages = dataset.pages ? Number.parseInt(dataset.pages, 10) : Number.NaN
    const initialPages = Number.isFinite(parsedPages) ? Math.max(1, parsedPages) : 1
    const pageSize = dataset.pageSize ? Number.parseInt(dataset.pageSize, 10) : null // optional
    const startFromEnd = options?.startFromEnd ?? true

    const endpointPattern = dataset.action
    if (!(endpointPattern || options?.customLoader)) return () => {}
    console.debug(
        "Pagination: Initializing",
        options?.customLoader ? "<custom>" : endpointPattern,
    )

    const parsedNumItems = dataset.numItems
        ? Number.parseInt(dataset.numItems, 10)
        : Number.NaN
    const initialNumItems = Number.isFinite(parsedNumItems) ? parsedNumItems : -1
    const numItems = signal(initialNumItems)
    const totalPages = signal(initialPages)
    const initialCurrentPage =
        options?.initialPage ??
        (startFromEnd
            ? initialPages > 1
                ? initialPages
                : initialNumItems < 0
                  ? 0
                  : 1
            : 1)
    const currentPage = signal(initialCurrentPage)
    const parsedSnapshotId = dataset.snapshotId
        ? Number.parseInt(dataset.snapshotId, 10)
        : Number.NaN
    const snapshotId = signal<number | null>(
        Number.isFinite(parsedSnapshotId) ? parsedSnapshotId : null,
    )
    const fetchCache = new Map<string, string>()
    let lastRenderedUrl: string | null = null
    let firstLoad = true

    const numItemsTargets = Array.from(
        container.querySelectorAll<HTMLElement>("[data-sp-num-items]"),
    )
    const numPagesTargets = Array.from(
        container.querySelectorAll<HTMLElement>("[data-sp-num-pages]"),
    )

    const setPendingState = (state: boolean) => {
        renderContainer.style.opacity = !firstLoad && state ? "0.5" : ""

        // Only show spinner during initial load
        if (firstLoad && state) {
            firstLoad = false
            const spinner = document.createElement("div")
            spinner.className = "text-center pagination-spinner"

            const spinnerElement = document.createElement("div")
            spinnerElement.className = "spinner-border text-body-secondary"
            spinnerElement.role = "status"

            const srText = document.createElement("span")
            srText.className = "visually-hidden"
            srText.textContent = i18next.t("browse.start_rjs.loading")

            spinnerElement.appendChild(srText)
            spinner.appendChild(spinnerElement)
            renderContainer.innerHTML = ""
            renderContainer.appendChild(spinner)
        }
    }

    const onLoad = (html: string) => {
        renderContainer.innerHTML = html
        resolveDatetimeLazy(renderContainer)
        options?.loadCallback?.(renderContainer, currentPage.peek())
    }

    const buildUrl = (
        page: number,
        numItemsValue: number,
        snapshotIdValue: number | null,
    ) => {
        if (!endpointPattern) throw new Error("Pagination: Missing data-action")
        const [path, q = ""] = endpointPattern.split("?")
        const params: Record<string, string | undefined> = qsParse(q)
        params.page = page.toString()
        if (numItemsValue >= 0) {
            params.num_items = numItemsValue.toString()
        } else {
            params.num_items = undefined
        }
        if (snapshotIdValue !== null) params.snapshot_id = snapshotIdValue.toString()
        return `${path}${qsEncode(params)}`
    }

    // Effect: Load and render page content when currentPage changes (fetches or uses cache)
    const disposeCollectionEffect = effect(() => {
        const requestedPage = currentPage.value
        if (requestedPage < 0) return
        const requestedPageString = currentPage.toString()

        if (options?.customLoader) {
            options.customLoader(renderContainer, requestedPage)
            console.debug("Pagination: Page loaded (custom)", requestedPageString)
            return
        }

        if (requestedPage === 0 && numItems.value >= 0) {
            currentPage.value = totalPages.value
            return
        }

        // Build the endpoint
        const snapshotIdValue = snapshotId.peek()
        const url = buildUrl(requestedPage, numItems.peek(), snapshotIdValue)

        // Serve from cache when available
        const cached = fetchCache.get(url)
        if (cached !== undefined) {
            console.debug("Pagination: Page loaded (cached)", requestedPageString)
            if (lastRenderedUrl !== url) {
                lastRenderedUrl = url
                onLoad(cached)
            }
            return () => {}
        }

        console.debug("Pagination: Loading page", requestedPageString)
        const abortController = new AbortController()
        setPendingState(true)

        const fetchPage = async () => {
            try {
                const resp = await fetch(url, {
                    signal: abortController.signal,
                    priority: "high",
                })
                const text = await resp.text()
                console.debug("Pagination: Page loaded", requestedPageString)
                fetchCache.set(url, text)
                let renderUrl = url

                // Sync headers for total items/pages
                if (numItems.value < 0) {
                    const serverNumItems = Number.parseInt(
                        resp.headers.get("X-SP-NumItems")!,
                        10,
                    )
                    const serverTotalPages = Math.max(
                        1,
                        Number.parseInt(resp.headers.get("X-SP-NumPages")!, 10),
                    )

                    const snapshotHeader = resp.headers.get("X-SP-SnapshotId")
                    const parsedHeaderSnapshotId = snapshotHeader
                        ? Number.parseInt(snapshotHeader, 10)
                        : Number.NaN
                    const serverSnapshotId = Number.isFinite(parsedHeaderSnapshotId)
                        ? parsedHeaderSnapshotId
                        : snapshotId.peek()

                    const resolvedPage = Math.min(
                        requestedPage === 0
                            ? serverTotalPages
                            : Math.max(1, requestedPage),
                        serverTotalPages,
                    )

                    const resolvedUrl = buildUrl(
                        resolvedPage,
                        serverNumItems,
                        serverSnapshotId,
                    )
                    fetchCache.set(resolvedUrl, text)
                    renderUrl = resolvedUrl

                    batch(() => {
                        numItems.value = serverNumItems
                        totalPages.value = serverTotalPages
                        snapshotId.value = serverSnapshotId
                        currentPage.value = resolvedPage
                    })
                }

                if (lastRenderedUrl !== renderUrl) {
                    lastRenderedUrl = renderUrl
                    onLoad(text)
                }
            } catch (error) {
                if (error.name === "AbortError") return
                console.error(
                    "Pagination: Failed to load page",
                    requestedPageString,
                    endpointPattern,
                    error,
                )
                renderContainer.textContent = error.message
            } finally {
                setPendingState(false)
            }
        }
        fetchPage()

        return () => abortController.abort()
    })

    // Effect: Rebuild pagination UI buttons when page count or current page changes
    const disposePaginationEffect = effect(() => {
        const numItemsValue = numItems.value
        const totalPagesValue = totalPages.value
        const currentPageValue = currentPage.value

        if (totalPagesValue <= 1) {
            for (const paginationContainer of paginationContainers) {
                paginationContainer.classList.add("d-none")
            }
            return
        }

        const pagesToRender: number[] = []
        if (totalPagesValue <= PAGINATION_MAX_FULL_PAGES) {
            for (let i = 1; i <= totalPagesValue; i++) pagesToRender.push(i)
        } else {
            pagesToRender.push(1)
            for (
                let i = currentPageValue - PAGINATION_DISTANCE;
                i <= currentPageValue + PAGINATION_DISTANCE;
                i++
            ) {
                if (i > 1 && i < totalPagesValue) pagesToRender.push(i)
            }
            pagesToRender.push(totalPagesValue)
        }

        for (const paginationContainer of paginationContainers) {
            paginationContainer.classList.remove("d-none")
            const paginationFragment = document.createDocumentFragment()

            let previousPage = 0
            for (const pageNumber of pagesToRender) {
                if (previousPage && pageNumber - previousPage > 1) {
                    const gap = document.createElement("li")
                    gap.classList.add("page-item", "disabled")
                    gap.ariaDisabled = "true"
                    gap.innerHTML = `<span class="page-link">...</span>`
                    paginationFragment.appendChild(gap)
                }

                const li = document.createElement("li")
                li.classList.add("page-item")

                const button = document.createElement("button")
                button.type = "button"
                button.classList.add("page-link")

                if (pageSize && numItemsValue > 0) {
                    const [limit, offset] = standardPaginationRange(
                        pageNumber,
                        pageSize,
                        numItemsValue,
                        startFromEnd,
                    )
                    const itemMax = numItemsValue - offset
                    const itemMin = itemMax - limit + 1
                    button.textContent =
                        itemMax !== itemMin
                            ? `${itemMin}...${itemMax}`
                            : itemMax.toString()
                } else {
                    button.textContent = pageNumber.toString()
                }

                li.appendChild(button)

                if (pageNumber === currentPageValue) {
                    li.classList.add("active")
                    li.ariaCurrent = "page"
                } else {
                    button.addEventListener("click", () => {
                        currentPage.value = pageNumber
                    })
                }

                paginationFragment.appendChild(li)
                previousPage = pageNumber
            }

            paginationContainer.innerHTML = ""
            paginationContainer.appendChild(paginationFragment)
        }
    })

    const disposeMetaEffect = effect(() => {
        const numItemsValue = numItems.value
        const totalPagesValue = totalPages.value

        if (numItemsValue >= 0) {
            for (const element of numItemsTargets) {
                element.textContent = numItemsValue.toString()
            }
        }
        if (numItemsValue >= 0 && totalPagesValue >= 1) {
            for (const element of numPagesTargets) {
                element.textContent = totalPagesValue.toString()
            }
        }
    })

    return () => {
        disposeCollectionEffect()
        disposePaginationEffect()
        disposeMetaEffect()
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
    startFromEnd: boolean,
) => {
    const numPages = Math.ceil(numItems / pageSize)
    const offset = startFromEnd ? (numPages - page) * pageSize : (page - 1) * pageSize
    const limit = Math.min(pageSize, numItems - offset)
    return [limit, offset]
}
