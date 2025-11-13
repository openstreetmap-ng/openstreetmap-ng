import { batch, effect, signal } from "@preact/signals-core"
import i18next from "i18next"
import { resolveDatetimeLazy } from "./datetime"
import { qsEncode, qsParse } from "./qs"

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
    const initialPages = Number.parseInt(dataset.pages, 10)
    if (!initialPages) {
        console.debug("Ignored standard pagination: missing data-pages")
        return () => {}
    }

    const pageSize = Number.parseInt(dataset.pageSize, 10) // optional
    const reverse = options?.reverse ?? true

    const endpointPattern = dataset.action
    console.debug(
        "Initializing standard pagination",
        options?.customLoader ? "<custom loader>" : endpointPattern,
    )

    const numItems = signal(Number.parseInt(dataset.numItems, 10))
    const totalPages = signal(initialPages)
    const currentPage = signal(options?.initialPage ?? (reverse ? initialPages : 1))
    const fetchCache = new Map<string, string>()
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

    const onLoad = (html: string): void => {
        renderContainer.innerHTML = html
        resolveDatetimeLazy(renderContainer)
        options?.loadCallback?.(renderContainer)
    }

    // Update collection
    const disposeCollectionEffect = effect(() => {
        if (!currentPage.value) return
        const currentPageString = currentPage.toString()

        if (options?.customLoader) {
            options.customLoader(currentPage.value, renderContainer)
            console.debug("Navigated to page", currentPageString)
            return
        }

        // Build the endpoint
        const [path, q = ""] = endpointPattern.split("?")
        const params = qsParse(q)
        params.page = currentPageString
        params.num_items = String(numItems.peek())
        const url = `${path}?${qsEncode(params)}`

        // Serve from cache when available
        const cached = fetchCache.get(url)
        if (cached !== undefined) {
            console.debug("Loading cached page", currentPageString)
            onLoad(cached)
            return () => {}
        }

        console.debug("Navigating to page", currentPageString)
        const abortController = new AbortController()
        setPendingState(true)

        fetch(url, {
            method: "GET",
            mode: "same-origin",
            cache: "no-store",
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (resp.ok) console.debug("Navigated to page", currentPageString)
                const text = await resp.text()
                fetchCache.set(url, text)
                onLoad(text)

                // Sync headers for total items/pages
                if (numItems.value < 0) {
                    batch(() => {
                        numItems.value = Number.parseInt(
                            resp.headers.get("X-SP-NumItems"),
                            10,
                        )
                        totalPages.value = Number.parseInt(
                            resp.headers.get("X-SP-NumPages"),
                            10,
                        )
                        currentPage.value = reverse ? totalPages.value : 1
                    })
                }
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
    })

    // Update pagination
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
        pagesToRender.push(1)
        for (
            let i = currentPageValue - paginationDistance;
            i <= currentPageValue + paginationDistance;
            i++
        ) {
            if (i > 1 && i < totalPagesValue) pagesToRender.push(i)
        }
        pagesToRender.push(totalPagesValue)

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

                if (pageSize && numItemsValue) {
                    const [limit, offset] = standardPaginationRange(
                        pageNumber,
                        pageSize,
                        numItemsValue,
                        reverse,
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

    return () => {
        console.debug("Disposing standard pagination", endpointPattern)
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
