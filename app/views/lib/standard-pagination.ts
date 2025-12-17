import { create, fromBinary, toBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import {
    STANDARD_PAGINATION_DISTANCE,
    STANDARD_PAGINATION_MAX_FULL_PAGES,
} from "@lib/config"
import { resolveDatetimeLazy } from "@lib/datetime-inputs"
import {
    type StandardPaginationState,
    StandardPaginationStateSchema,
} from "@lib/proto/shared_pb"
import { range } from "@lib/utils"
import { batch, effect, signal } from "@preact/signals-core"
import { assert, assertExists } from "@std/assert"
import i18next from "i18next"

const SP_HEADER = "X-StandardPagination"

export const configureStandardPagination = (
    container: ParentNode | null,
    options?: {
        initialPage?: number
        customLoader?: (renderContainer: HTMLElement, page: number) => void
        loadCallback?: (renderContainer: HTMLElement, page: number) => void
    },
) => {
    if (!container) return () => {}

    const actionCandidates = Array.from(
        container.querySelectorAll("ul.pagination"),
    ).filter((ul) => ul.dataset.action || ul.dataset.pages)
    assert(actionCandidates.length, "Pagination: Missing action pagination")

    const directCandidates =
        actionCandidates.length === 1
            ? actionCandidates
            : actionCandidates.filter(
                  (ul) => ul.closest("nav")?.parentNode === container,
              )

    const actionPagination = directCandidates[0]
    const actionNav = actionPagination.closest("nav")!
    const paginationRoot = actionNav.parentNode as ParentNode

    const paginationContainers = Array.from(
        paginationRoot.querySelectorAll("ul.pagination"),
    ).filter((ul) => ul.closest("nav")?.parentNode === paginationRoot)
    assert(paginationContainers.length, "Pagination: Missing pagination controls")

    const renderSibling = actionNav.previousElementSibling! as HTMLElement
    const renderContainer = renderSibling.querySelector("tbody") ?? renderSibling

    const customLoader = options?.customLoader
    const dataset = actionPagination.dataset
    const fetchUrl = dataset.action
    const pageSize = dataset.pageSize ? Number.parseInt(dataset.pageSize, 10) : null
    const customNumPages = dataset.pages ? Number.parseInt(dataset.pages, 10) : null
    if (customLoader)
        assert(dataset.pages, "Pagination: Missing data-pages for custom loader")

    console.debug("Pagination: Initializing", customLoader ? "<custom>" : fetchUrl)

    const initialPage = options?.initialPage ?? 1
    const requestedPage = signal(initialPage)
    const activePage = signal(initialPage)
    const state = signal<StandardPaginationState | null>(null)

    const cache = new Map<string, { html: string; state: StandardPaginationState }>()
    let lastRenderedKey: string | undefined
    let firstLoad = true
    let didInitialJump = false

    const numItemsTargets = Array.from(
        container.querySelectorAll("[data-sp-num-items]"),
    )
    const numPagesTargets = Array.from(
        container.querySelectorAll("[data-sp-num-pages]"),
    )

    const setPendingState = (pending: boolean) => {
        renderContainer.style.opacity = !firstLoad && pending ? "0.5" : ""

        // Only show spinner during initial load
        if (firstLoad && pending) {
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
            renderContainer.replaceChildren(spinner)
        }
    }

    const afterLoad = (page: number) => {
        resolveDatetimeLazy(renderContainer)
        options?.loadCallback?.(renderContainer, page)
    }

    const onLoad = (html: string, page: number) => {
        renderContainer.innerHTML = html
        afterLoad(page)
    }

    const snapshotKeyFromState = (value: StandardPaginationState) => {
        const cursor = value.cursors
        assertExists(cursor.case, "Pagination: Missing cursor snapshot")
        const cursorKey =
            cursor.case === "u64"
                ? `u64:${cursor.value.snapshot.toString()}`
                : `text:${cursor.value.snapshot}`
        return `${cursorKey}:${value.snapshotMaxId.toString()}`
    }

    const cacheKey = (url: string, snapshotKey: string, page: number) =>
        `${url}#${snapshotKey}#${page}`

    const applyState = (value: StandardPaginationState) => {
        batch(() => {
            state.value = value
            activePage.value = value.currentPage
        })
    }

    const computePagesToRender = (
        currentPageValue: number,
        maxKnownPageValue: number,
        numPagesValue: number | undefined,
    ) => {
        const resolvedMaxPage = numPagesValue ?? maxKnownPageValue

        if (resolvedMaxPage <= STANDARD_PAGINATION_MAX_FULL_PAGES) {
            return range(1, resolvedMaxPage + 1)
        }

        const pages = new Set<number>()
        pages.add(1)

        const windowStart = Math.max(2, currentPageValue - STANDARD_PAGINATION_DISTANCE)
        const windowEnd = Math.min(
            resolvedMaxPage,
            currentPageValue + STANDARD_PAGINATION_DISTANCE,
        )
        for (let i = windowStart; i <= windowEnd; i++) pages.add(i)

        if (numPagesValue !== undefined) pages.add(numPagesValue)
        return Array.from(pages).sort((a, b) => a - b)
    }

    // Effect: Load and render page content when requestedPage changes (fetches or uses cache)
    const disposeCollectionEffect = effect(() => {
        const requestedPageValue = requestedPage.value
        const requestedPageString = requestedPageValue.toString()

        if (customLoader) {
            const resolvedPage = Math.min(requestedPageValue, customNumPages!)
            if (activePage.peek() !== resolvedPage) activePage.value = resolvedPage
            customLoader(renderContainer, resolvedPage)
            afterLoad(resolvedPage)
            console.debug("Pagination: Page loaded (custom)", requestedPageString)
            return
        }

        const fetchUrlResolved = fetchUrl!

        const currentState = state.peek()
        const currentSnapshotKey = currentState
            ? snapshotKeyFromState(currentState)
            : ""
        const requestKey = cacheKey(
            fetchUrlResolved,
            currentSnapshotKey,
            requestedPageValue,
        )

        const cached = cache.get(requestKey)
        if (cached) {
            console.debug("Pagination: Page loaded (cached)", requestedPageString)
            if (lastRenderedKey !== requestKey) {
                applyState(cached.state)
                lastRenderedKey = requestKey
                onLoad(cached.html, cached.state.currentPage)
            }
            return () => {}
        }

        console.debug("Pagination: Loading page", requestedPageString)
        const abortController = new AbortController()
        setPendingState(true)

        const fetchPage = async () => {
            try {
                const baseState = state.peek()
                const fetchInit: RequestInit = {
                    signal: abortController.signal,
                    priority: "high",
                    method: "POST",
                }

                // For the initial request (no state yet), omit the body entirely.
                // The backend defaults `sp_state` to `b''`, so missing body and empty body are equivalent.
                if (baseState !== null) {
                    const requestBytes = toBinary(
                        StandardPaginationStateSchema,
                        create(StandardPaginationStateSchema, {
                            ...baseState,
                            requestedPage: requestedPageValue,
                        }),
                    )
                    fetchInit.body = new Blob([requestBytes], {
                        type: "application/x-protobuf",
                    })
                }

                const resp = await fetch(fetchUrlResolved, fetchInit)
                const text = await resp.text()
                assert(resp.ok, `Pagination: ${resp.status} ${resp.statusText}`)

                const newStateHeader = resp.headers.get(SP_HEADER)
                assert(newStateHeader, `Pagination: Missing ${SP_HEADER} header`)

                const parsed = fromBinary(
                    StandardPaginationStateSchema,
                    base64Decode(newStateHeader),
                )
                const newSnapshotKey = snapshotKeyFromState(parsed)
                const resolvedKey = cacheKey(
                    fetchUrlResolved,
                    newSnapshotKey,
                    parsed.currentPage,
                )

                applyState(parsed)
                cache.set(resolvedKey, { html: text, state: parsed })

                let skipRender = false
                if (!didInitialJump && initialPage !== 1) {
                    didInitialJump = true
                    const maxPage = parsed.numPages ?? parsed.maxKnownPage
                    const resolvedInitialPage = Math.min(initialPage, maxPage)
                    if (resolvedInitialPage !== parsed.currentPage) {
                        // Avoid rendering an intermediate "page 1" snapshot when we immediately
                        // jump to another page after receiving the initial pagination state.
                        batch(() => {
                            activePage.value = resolvedInitialPage
                            requestedPage.value = resolvedInitialPage
                        })
                        skipRender = true
                    }
                }

                if (!skipRender && lastRenderedKey !== resolvedKey) {
                    lastRenderedKey = resolvedKey
                    onLoad(text, parsed.currentPage)
                }
                console.debug("Pagination: Page loaded", requestedPageString)
            } catch (error) {
                if (error.name === "AbortError") return
                console.error(
                    "Pagination: Failed to load page",
                    requestedPageString,
                    fetchUrlResolved,
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

    // Effect: Rebuild pagination UI buttons when page counts or current page changes
    const disposePaginationEffect = effect(() => {
        const currentPageValue = activePage.value
        const currentState = state.value
        const numPagesValue = customNumPages ?? currentState?.numPages
        const maxKnownPageValue = customNumPages ?? currentState?.maxKnownPage ?? 1
        const showTailEllipsis = currentState !== null && numPagesValue === undefined

        const resolvedMaxPage = numPagesValue ?? maxKnownPageValue
        if (resolvedMaxPage <= 1) {
            for (const paginationContainer of paginationContainers) {
                paginationContainer.classList.add("d-none")
            }
            return
        }

        const pagesToRender = computePagesToRender(
            currentPageValue,
            maxKnownPageValue,
            numPagesValue,
        )

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

                const numItemsValue = currentState?.numItems
                if (pageSize && numItemsValue !== undefined) {
                    const [itemMin, itemMax] = standardPaginationItemRange(
                        pageNumber,
                        pageSize,
                        numItemsValue,
                    )
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
                        requestedPage.value = pageNumber
                    })
                }

                paginationFragment.appendChild(li)
                previousPage = pageNumber
            }

            if (showTailEllipsis) {
                const gap = document.createElement("li")
                gap.classList.add("page-item", "disabled")
                gap.ariaDisabled = "true"
                gap.innerHTML = `<span class="page-link">...</span>`
                paginationFragment.appendChild(gap)
            }

            paginationContainer.replaceChildren(paginationFragment)
        }
    })

    const disposeMetaEffect = effect(() => {
        const currentState = state.value
        const numItemsValue = currentState?.numItems
        const numPagesValue = customNumPages ?? currentState?.numPages

        if (numItemsValue !== undefined) {
            for (const element of numItemsTargets) {
                element.textContent = numItemsValue.toString()
            }
        }
        if (numPagesValue !== undefined) {
            for (const element of numPagesTargets) {
                element.textContent = numPagesValue.toString()
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
 * Item range labels for a 1-based "newest page is 1" pagination scheme.
 * Returns a tuple of (itemMin, itemMax), inclusive.
 */
const standardPaginationItemRange = (
    page: number,
    pageSize: number,
    numItems: number,
) => {
    const offset = (page - 1) * pageSize
    const itemMax = numItems - offset
    const itemMin = itemMax - Math.min(pageSize, itemMax) + 1
    return [itemMin, itemMax]
}
