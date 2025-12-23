import { create, fromBinary, type Message, toBinary } from "@bufbuild/protobuf"
import type { GenMessage } from "@bufbuild/protobuf/codegenv2"
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
import {
  batch,
  effect,
  type Signal,
  signal,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { assert } from "@std/assert"
import { t } from "i18next"
import type { ComponentChildren } from "preact"
import { render } from "preact"
import { memo } from "preact/compat"
import { useRef } from "preact/hooks"

const SP_HEADER = "X-StandardPagination"

type RangeDir = "asc" | "desc"

type StandardPaginationOptions = {
  initialPage?: number
  customLoader?: (renderContainer: HTMLElement, page: number) => void
  loadCallback?: (renderContainer: HTMLElement, page: number) => void
  rangeDir?: RangeDir
}

type StandardPaginationElements = {
  actionPagination: HTMLUListElement
  paginationContainers: HTMLUListElement[]
  renderContainer: HTMLElement
  numItemsTargets: HTMLElement[]
  numPagesTargets: HTMLElement[]
}

const PaginationSpinner = memo(() => (
  <div class="pagination-spinner">
    <output
      class="spinner-border text-body-secondary"
      aria-live="polite"
    >
      <span class="visually-hidden">{t("browse.start_rjs.loading")}</span>
    </output>
  </div>
))

const PaginationError = ({ error }: { error: string }) => (
  <div
    class="alert alert-danger mb-2"
    role="alert"
  >
    {error}
  </div>
)

const PaginationItems = ({
  requestedPage,
  activePage,
  state,
  pages,
  rangeDir,
}: {
  requestedPage: Signal<number>
  activePage: Signal<number>
  state: Signal<StandardPaginationState | null>
  pages: number | null
  rangeDir: RangeDir | undefined
}) => {
  const currentPageValue = activePage.value
  const currentState = state.value
  const numPagesValue = pages ?? currentState?.numPages
  const maxKnownPageValue = pages ?? currentState?.maxKnownPage ?? 1
  const showTailEllipsis = currentState !== null && numPagesValue === undefined

  const resolvedMaxPage = numPagesValue ?? maxKnownPageValue
  if (resolvedMaxPage <= 1) return null

  const pagesToRender = computePagesToRender(
    currentPageValue,
    maxKnownPageValue,
    numPagesValue,
  )
  const tokens: Array<number | "gap"> = []
  let previousPage = 0
  for (const pageNumber of pagesToRender) {
    if (previousPage && pageNumber - previousPage > 1) tokens.push("gap")
    tokens.push(pageNumber)
    previousPage = pageNumber
  }
  if (showTailEllipsis) tokens.push("gap")

  const numItemsValue = currentState?.numItems
  const pageSizeValue = currentState?.pageSize

  return (
    <>
      {tokens.map((token, index) => {
        if (token === "gap") {
          return (
            <li
              class="page-item disabled"
              aria-disabled="true"
              key={`gap-${index}`}
            >
              <span class="page-link">...</span>
            </li>
          )
        }

        const pageNumber = token
        const label =
          pageSizeValue && numItemsValue !== undefined
            ? formatPageLabel(pageNumber, pageSizeValue, numItemsValue, rangeDir)
            : pageNumber.toString()

        if (pageNumber === currentPageValue) {
          return (
            <li
              class="page-item active"
              aria-current="page"
              key={pageNumber}
            >
              <span class="page-link">{label}</span>
            </li>
          )
        }

        return (
          <li
            class="page-item"
            key={pageNumber}
          >
            <button
              type="button"
              class="page-link"
              onClick={() => {
                requestedPage.value = pageNumber
              }}
            >
              {label}
            </button>
          </li>
        )
      })}
    </>
  )
}

export const StandardPagination = <TData,>({
  action,
  label = t("alt.page_navigation"),
  initialPage = 1,
  protobuf,
  rangeDir,
  onLoad,
  children,
  navClassTop = "mb-2",
  navClassBottom = "mb-0",
}: {
  action: string
  label?: string
  initialPage?: number
  protobuf?: GenMessage<TData & Message>
  rangeDir?: RangeDir
  onLoad?: (data: TData, page: number) => void
  children: (data: TData) => ComponentChildren
  navClassTop?: string
  navClassBottom?: string
}) => {
  const requestedPage = useSignal(initialPage)
  const activePage = useSignal(initialPage)
  const state = useSignal<StandardPaginationState | null>(null)
  const error = useSignal<string | null>(null)
  const data = useSignal<TData | null>(null)

  const didInitialJumpRef = useRef(false)

  // Effect: Fetch current pagination page
  useSignalEffect(() => {
    const requestedPageValue = requestedPage.value

    const abortController = new AbortController()
    const isStale = () =>
      abortController.signal.aborted || requestedPage.value !== requestedPageValue

    batch(() => {
      error.value = null
      data.value = null
    })

    const fetchPage = async () => {
      try {
        const baseState = state.peek()
        const resp = await fetch(
          action,
          buildFetchInit(baseState, requestedPageValue, abortController.signal),
        )
        assert(resp.ok, `Pagination: ${resp.status} ${resp.statusText}`)
        if (isStale()) return

        const parsed = parsePaginationHeader(resp.headers)
        applyState(parsed, state, activePage)

        if (!didInitialJumpRef.current && initialPage !== 1) {
          didInitialJumpRef.current = true
          const maxPage = parsed.numPages ?? parsed.maxKnownPage
          const resolvedInitialPage = Math.min(initialPage, maxPage)
          if (resolvedInitialPage !== parsed.currentPage) {
            batch(() => {
              activePage.value = resolvedInitialPage
              requestedPage.value = resolvedInitialPage
            })
            return
          }
        }

        const payload = protobuf
          ? (fromBinary(protobuf, new Uint8Array(await resp.arrayBuffer())) as TData)
          : ((await resp.text()) as unknown as TData)

        if (isStale()) return
        onLoad?.(payload, parsed.currentPage)
        if (isStale()) return
        data.value = payload
      } catch (err) {
        if (err.name === "AbortError" || isStale()) return
        console.error(
          "Pagination: Failed to load page",
          requestedPageValue,
          action,
          err,
        )
        error.value = err.message
      }
    }

    fetchPage()
    return () => abortController.abort()
  })

  const currentState = state.value
  const resolvedMaxPage = currentState?.numPages ?? currentState?.maxKnownPage ?? 1
  const showNav = resolvedMaxPage > 1

  const paginationListClass = "pagination justify-content-end"
  const nav = (extraClass: string) => (
    <nav aria-label={label}>
      <ul class={`${paginationListClass} ${extraClass}`}>
        <PaginationItems
          requestedPage={requestedPage}
          activePage={activePage}
          state={state}
          pages={null}
          rangeDir={rangeDir}
        />
      </ul>
    </nav>
  )

  return (
    <>
      {showNav && nav(navClassTop)}
      {error.value ? (
        <PaginationError error={error.value} />
      ) : data.value === null ? (
        <PaginationSpinner />
      ) : (
        children(data.value)
      )}
      {showNav && nav(navClassBottom)}
    </>
  )
}

// TODO: start of remove
export const configureStandardPagination = (
  container: Element | null,
  options?: StandardPaginationOptions,
) => {
  if (!container) return () => {}

  const elements = resolvePaginationElements(container)
  return configureStandardPaginationElements(elements, options)
}

const configureStandardPaginationElements = (
  elements: StandardPaginationElements,
  options?: StandardPaginationOptions,
) => {
  const {
    actionPagination,
    paginationContainers,
    renderContainer,
    numItemsTargets,
    numPagesTargets,
  } = elements
  const customLoader = options?.customLoader
  const dataset = actionPagination.dataset
  const fetchUrl = dataset.action
  const customNumPages = dataset.pages ? Number.parseInt(dataset.pages, 10) : null
  const rangeDir = options?.rangeDir
  if (customLoader) {
    assert(dataset.pages, "Pagination: Missing data-pages for custom loader")
  }

  console.debug("Pagination: Initializing", customLoader ? "<custom>" : fetchUrl)

  const initialPage = options?.initialPage ?? 1
  const requestedPage = signal(initialPage)
  const activePage = signal(initialPage)
  const state = signal<StandardPaginationState | null>(null)

  let firstLoad = true
  let didInitialJump = false

  const renderStatus = (content: ComponentChildren) => {
    if (renderContainer.tagName === "TBODY") {
      render(
        <tr>
          <td
            colSpan={99}
            class="p-0"
          >
            {content}
          </td>
        </tr>,
        renderContainer,
      )
    } else if (renderContainer.tagName === "UL" || renderContainer.tagName === "OL") {
      render(<li class="list-unstyled">{content}</li>, renderContainer)
    } else {
      render(content, renderContainer)
    }
  }

  const setPendingState = (pending: boolean) => {
    renderContainer.style.opacity = !firstLoad && pending ? "0.5" : ""

    if (!(firstLoad && pending)) return
    firstLoad = false

    renderStatus(<PaginationSpinner />)
  }

  const afterLoad = (page: number) => {
    resolveDatetimeLazy(renderContainer)
    options?.loadCallback?.(renderContainer, page)
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

    console.debug("Pagination: Loading page", requestedPageString)
    const abortController = new AbortController()
    setPendingState(true)

    const fetchPage = async () => {
      try {
        assert(fetchUrl, "Pagination: Missing data-action")
        const baseState = state.peek()
        const resp = await fetch(
          fetchUrl,
          buildFetchInit(baseState, requestedPageValue, abortController.signal),
        )
        assert(resp.ok, `Pagination: ${resp.status} ${resp.statusText}`)

        const parsed = parsePaginationHeader(resp.headers)
        applyState(parsed, state, activePage)

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

        if (!skipRender) {
          render(null, renderContainer)
          renderContainer.innerHTML = await resp.text()
          afterLoad(parsed.currentPage)
        }
        console.debug("Pagination: Page loaded", requestedPageString)
      } catch (error) {
        if (error.name === "AbortError") return
        console.error(
          "Pagination: Failed to load page",
          requestedPageString,
          fetchUrl,
          error,
        )
        render(null, renderContainer)
        renderStatus(<PaginationError error={error.message} />)
      } finally {
        setPendingState(false)
      }
    }
    fetchPage()

    return () => abortController.abort()
  })

  // Effect: Rebuild pagination UI buttons when page counts or current page changes
  const disposePaginationEffect = effect(() => {
    const currentState = state.value
    const numPagesValue = customNumPages ?? currentState?.numPages
    const maxKnownPageValue = customNumPages ?? currentState?.maxKnownPage ?? 1
    const resolvedMaxPage = numPagesValue ?? maxKnownPageValue
    if (resolvedMaxPage <= 1) {
      for (const paginationContainer of paginationContainers) {
        paginationContainer.classList.add("d-none")
        render(null, paginationContainer)
      }
      return
    }

    for (const paginationContainer of paginationContainers) {
      paginationContainer.classList.remove("d-none")
      render(
        <PaginationItems
          requestedPage={requestedPage}
          activePage={activePage}
          state={state}
          pages={customNumPages}
          rangeDir={rangeDir}
        />,
        paginationContainer,
      )
    }
  })

  // Effect: Update pagination meta targets (num items/pages)
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
    for (const paginationContainer of paginationContainers)
      render(null, paginationContainer)
  }
}

const resolvePaginationElements = (container: Element): StandardPaginationElements => {
  const actionPagination = container.querySelector(
    "ul.pagination[data-action], ul.pagination[data-pages]",
  )
  assert(actionPagination, "Pagination: Missing action pagination")
  const actionNav = actionPagination.closest("nav")
  assert(actionNav, "Pagination: Missing action nav")
  const paginationRoot = actionNav.parentElement
  assert(paginationRoot, "Pagination: Missing pagination root")
  const paginationContainers = Array.from(
    paginationRoot.querySelectorAll(":scope > nav > ul.pagination"),
  )

  const renderSibling = (actionNav.previousElementSibling ??
    paginationRoot.previousElementSibling) as HTMLElement | null
  assert(renderSibling, "Pagination: Missing render container")

  const renderContainer = renderSibling.matches("tbody, ul.list-unstyled")
    ? renderSibling
    : (renderSibling.querySelector("tbody, ul.list-unstyled") ?? renderSibling)

  const numItemsTargets = Array.from(
    container.querySelectorAll<HTMLElement>("[data-sp-num-items]"),
  )
  const numPagesTargets = Array.from(
    container.querySelectorAll<HTMLElement>("[data-sp-num-pages]"),
  )

  return {
    actionPagination,
    paginationContainers,
    renderContainer,
    numItemsTargets,
    numPagesTargets,
  }
}
// TODO: end of remove

const applyState = (
  value: StandardPaginationState,
  state: Signal<StandardPaginationState | null>,
  activePage: Signal<number>,
) => {
  batch(() => {
    state.value = value
    activePage.value = value.currentPage
  })
}

const computePagesToRender = (
  currentPage: number,
  maxKnownPage: number,
  numPages: number | undefined,
) => {
  const resolvedMaxPage = numPages ?? maxKnownPage

  if (resolvedMaxPage <= STANDARD_PAGINATION_MAX_FULL_PAGES) {
    return range(1, resolvedMaxPage + 1)
  }

  const pages = new Set<number>()
  pages.add(1)

  const windowStart = Math.max(2, currentPage - STANDARD_PAGINATION_DISTANCE)
  const windowEnd = Math.min(
    resolvedMaxPage,
    currentPage + STANDARD_PAGINATION_DISTANCE,
  )
  for (let i = windowStart; i <= windowEnd; i++) pages.add(i)

  if (numPages !== undefined) pages.add(numPages)
  return Array.from(pages).sort((a, b) => a - b)
}

const formatPageLabel = (
  pageNumber: number,
  pageSize: number,
  numItems: number,
  rangeDir: RangeDir | undefined,
) => {
  const offset = (pageNumber - 1) * pageSize
  const itemMax = numItems - offset
  const itemMin = itemMax - Math.min(pageSize, itemMax) + 1
  if (itemMax === itemMin) return itemMax.toString()
  return rangeDir === "desc" ? `${itemMax}‐${itemMin}` : `${itemMin}‐${itemMax}`
}

const buildFetchInit = (
  baseState: StandardPaginationState | null,
  requestedPage: number,
  abortSignal: AbortSignal,
) => {
  const fetchInit: RequestInit = {
    signal: abortSignal,
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
        requestedPage,
      }),
    )
    fetchInit.body = new Blob([requestBytes], {
      type: "application/x-protobuf",
    })
  }

  return fetchInit
}

const parsePaginationHeader = (headers: Headers) => {
  const header = headers.get(SP_HEADER)
  assert(header, `Pagination: Missing ${SP_HEADER} header`)
  return fromBinary(StandardPaginationStateSchema, base64Decode(header))
}
