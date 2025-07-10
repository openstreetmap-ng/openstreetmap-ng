import { effect, signal } from "@preact/signals-core"
import i18next from "i18next"
import { resolveDatetimeLazy } from "./datetime"

const paginationDistance = 2

export const configureStandardPagination = (
    container?: ParentNode,
    options?: {
        initialPage?: number
        customLoader?: (page: number, renderContainer: HTMLElement) => void
        loadCallback?: () => void
    },
): (() => void) => {
    if (!container) return () => {}
    const renderContainer =
        container.querySelector("ul.list-unstyled") ?? container.querySelector("tbody")
    const paginationContainers = container.querySelectorAll("ul.pagination")

    const dataset = paginationContainers[paginationContainers.length - 1].dataset
    const totalPages = Number.parseInt(dataset.pages, 10)
    if (!totalPages) return () => {}

    const pageSize = Number.parseInt(dataset.pageSize, 10)
    const numItems = Number.parseInt(dataset.numItems, 10)

    const endpointPattern = dataset.action
    console.debug(
        "Initializing standard pagination",
        options?.customLoader ? "<custom loader>" : endpointPattern,
    )
    const currentPage = signal(options?.initialPage ?? totalPages)
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
                options?.loadCallback?.()
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
    })

    return () => {
        console.debug("Disposing standard pagination", endpointPattern)
        currentPage.value = 0
        disposeCollectionEffect()
        disposePaginationEffect()
    }
}

/**
 * Get the range of items for the given page.
 * The last page returns an offset of 0.
 * Returns a tuple of (limit, offset).
 */
const standardPaginationRange = (page: number, pageSize: number, numItems: number) => {
    const numPages = Math.ceil(numItems / pageSize)
    const offset = (numPages - page) * pageSize
    const limit = Math.min(pageSize, numItems - offset)
    return [limit, offset]
}
