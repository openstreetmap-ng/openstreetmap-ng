import {
  create,
  type Message,
  type MessageValidType,
  toBinary,
} from "@bufbuild/protobuf"
import type { GenMessage } from "@bufbuild/protobuf/codegenv2"
import { base64Decode } from "@bufbuild/protobuf/wire"
import {
  STANDARD_PAGINATION_DISTANCE,
  STANDARD_PAGINATION_MAX_FULL_PAGES,
} from "@lib/config"
import { resolveDatetimeLazy } from "@lib/datetime-inputs"
import { createDisposeScope, useDisposeSignalEffect } from "@lib/dispose-scope"
import {
  type StandardPaginationState,
  StandardPaginationStateSchema,
} from "@lib/proto/shared_pb"
import { fromBinaryValid } from "@lib/rpc"
import { range } from "@lib/utils"
import {
  batch,
  type ReadonlySignal,
  type Signal,
  signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { assert, assertExists } from "@std/assert"
import { t } from "i18next"
import type { ComponentChildren } from "preact"
import { render } from "preact"
import { memo } from "preact/compat"

const SP_HEADER = "X-StandardPagination"

type PageOrder = "asc" | "asc-range" | "desc" | "desc-range"

type PaginationSchema = GenMessage<Message, { validType: Message }>

type StandardPaginationOptions = {
  initialPage?: number
  customLoader?: (renderContainer: HTMLElement, page: number) => void
  loadCallback?: (renderContainer: HTMLElement, page: number) => void
  pageOrder?: PageOrder
}

type StandardPaginationElements = {
  actionPagination: HTMLUListElement
  paginationContainers: HTMLUListElement[]
  renderContainer: HTMLElement
  numItemsTargets: Element[]
  numPagesTargets: Element[]
}

// State machine types for pagination resource
/** Preloaded page response for external injection (e.g., after POST) */
export type PaginationResponse<TData extends Message> = {
  data: TData
  state: StandardPaginationState
}

type PaginationResource<TData> =
  | { tag: "boot" }
  | { tag: "loading"; prev: TData | null }
  | { tag: "ready"; data: TData }
  | { tag: "error"; error: string; prev: TData | null }

const PaginationSpinner = memo(() => (
  <div class="sp-spinner">
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

const PaginationContent = <TData,>({
  resource,
  children,
}: {
  resource: ReadonlySignal<PaginationResource<TData>>
  children: (data: TData) => ComponentChildren
}) => {
  const r = resource.value

  switch (r.tag) {
    case "boot":
      return <PaginationSpinner />

    case "loading":
      return r.prev ? (
        <div class="sp-content-wrapper">
          <div
            class="opacity-50"
            inert
          >
            {children(r.prev)}
          </div>
          <div class="sp-loading-overlay">
            <PaginationSpinner />
          </div>
        </div>
      ) : (
        <PaginationSpinner />
      )

    case "ready":
      return (
        <div class="sp-content-wrapper">
          <div>{children(r.data)}</div>
        </div>
      )

    case "error":
      return <PaginationError error={r.error} />
  }
}

const PaginationItems = ({
  targetPage,
  currentPage,
  state,
  pages,
  pageOrder,
}: {
  targetPage: Signal<number>
  currentPage: ReadonlySignal<number>
  state: ReadonlySignal<StandardPaginationState | null>
  pages: number | null
  pageOrder: PageOrder
}) => {
  const actualPage = currentPage.value
  const currentState = state.value
  const numPagesValue = pages ?? currentState?.numPages
  const maxKnownPageValue = pages ?? currentState?.maxKnownPage ?? 1
  const showTailEllipsis = currentState !== null && numPagesValue === undefined

  const resolvedMaxPage = numPagesValue ?? maxKnownPageValue
  if (resolvedMaxPage <= 1) return null

  // For desc mode, invert page numbers: display = numPages - actual + 1
  const isDesc = pageOrder.startsWith("desc")
  const showRange = pageOrder.endsWith("-range")
  const toDisplay = (actual: number) =>
    isDesc && numPagesValue ? numPagesValue - actual + 1 : actual
  const toActual = (display: number) =>
    isDesc && numPagesValue ? numPagesValue - display + 1 : display

  const displayPage = toDisplay(actualPage)

  const pagesToRender = computePagesToRender(
    displayPage,
    isDesc ? toDisplay(1) : maxKnownPageValue,
    numPagesValue,
  )
  const tokens: Array<number | "gap"> = []
  let previousPage = 0
  for (const pageNumber of pagesToRender) {
    if (previousPage && pageNumber - previousPage > 1) tokens.push("gap")
    tokens.push(pageNumber)
    previousPage = pageNumber
  }
  if (showTailEllipsis && !isDesc) tokens.push("gap")

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

        const displayPageNum = token
        const actualPageNum = toActual(displayPageNum)
        const label =
          showRange && pageSizeValue && numItemsValue !== undefined
            ? formatPageLabel(actualPageNum, pageSizeValue, numItemsValue, isDesc)
            : displayPageNum.toString()

        if (displayPageNum === displayPage) {
          return (
            <li
              class="page-item active"
              aria-current="page"
              key={displayPageNum}
            >
              <span class="page-link">{label}</span>
            </li>
          )
        }

        return (
          <li
            class="page-item"
            key={displayPageNum}
          >
            <button
              type="button"
              class="page-link"
              onClick={() => (targetPage.value = actualPageNum)}
            >
              {label}
            </button>
          </li>
        )
      })}
    </>
  )
}

// Hook: manages pagination state machine
const useStandardPagination = <TSchema extends PaginationSchema>({
  action,
  initialPage,
  responseSignal,
  protobuf,
  onLoad,
}: {
  action: string
  initialPage: number
  responseSignal:
    | Signal<PaginationResponse<MessageValidType<TSchema>> | null>
    | undefined
  protobuf: TSchema
  onLoad: ((data: MessageValidType<TSchema>, page: number) => void) | undefined
}) => {
  type TData = MessageValidType<TSchema>

  const state = useSignal<StandardPaginationState | null>(null)
  const targetPage = useSignal(initialPage)
  const resource = useSignal<PaginationResource<TData>>({ tag: "boot" })

  // Effect: react to external response updates (e.g., after POST)
  useSignalEffect(() => {
    if (!responseSignal) return
    const response = responseSignal.value
    if (!response) return

    // Discard stale responses (we are a fresh instance)
    if (state.peek() === null) {
      responseSignal.value = null
      return
    }

    targetPage.value = response.state.currentPage
    onLoad?.(response.data, response.state.currentPage)
    state.value = response.state
    resource.value = { tag: "ready", data: response.data }
    responseSignal.value = null
  })

  // Derived: current page from last known pagination state
  const currentPage = useComputed(() => state.value?.currentPage ?? targetPage.value)

  // Effect: fetch page when targetPage changes
  useDisposeSignalEffect((scope) => {
    const page = targetPage.value
    const current = resource.peek()

    // Skip if already at target page (prevents double-fetch after initial jump)
    if (current.tag === "ready" && state.peek()!.currentPage === page) {
      return
    }

    // Capture prev for stale-while-revalidate
    const prev =
      current.tag === "ready"
        ? current.data
        : (current.tag === "loading" || current.tag === "error") && current.prev
          ? current.prev
          : null

    resource.value = { tag: "loading", prev }

    const fetchPage = async () => {
      try {
        const resp = await fetch(
          action,
          buildFetchInit(state.peek(), page, scope.signal),
        )
        assert(resp.ok, `Pagination: ${resp.status} ${resp.statusText}`)
        const responseState = parsePaginationHeader(resp.headers)

        // Discard stale responses
        const currentState = state.peek()
        if (currentState && responseState.snapshotMaxId < currentState.snapshotMaxId) {
          return
        }

        // Handle initial jump: if we're booting and target differs from what server returned
        if (current.tag === "boot" && initialPage !== 1) {
          const maxPage = responseState.numPages ?? responseState.maxKnownPage
          const resolvedPage = Math.min(initialPage, maxPage)
          if (resolvedPage !== responseState.currentPage) {
            batch(() => {
              state.value = responseState
              targetPage.value = resolvedPage
            })
            return // Effect will re-run with correct page
          }
        }

        const data = fromBinaryValid(protobuf, new Uint8Array(await resp.arrayBuffer()))

        scope.signal.throwIfAborted()

        batch(() => {
          onLoad?.(data, responseState.currentPage)
          state.value = responseState
          resource.value = { tag: "ready", data }
        })
      } catch (err) {
        if (err.name === "AbortError") return
        console.error("Pagination: Failed to load page", page, action, err)
        resource.value = { tag: "error", error: err.message, prev }
      }
    }

    fetchPage()
  })

  return { targetPage, resource, currentPage, state }
}

export const StandardPagination = <TSchema extends PaginationSchema>({
  action,
  label = t("alt.page_navigation"),
  initialPage = 1,
  pageOrder = "asc",
  small = false,
  navTop = false,
  navClassTop = "mb-2",
  navBottom = true,
  navClassBottom = "",
  protobuf,
  responseSignal,
  onLoad,
  children,
}: {
  action: string
  label?: string
  initialPage?: number
  pageOrder?: PageOrder
  small?: boolean
  navTop?: boolean
  navClassTop?: string
  navBottom?: boolean
  navClassBottom?: string
  protobuf: TSchema
  responseSignal?: Signal<PaginationResponse<MessageValidType<TSchema>> | null>
  onLoad?: (data: MessageValidType<TSchema>, page: number) => void
  children: (data: MessageValidType<TSchema>) => ComponentChildren
}) => {
  const { targetPage, resource, currentPage, state } = useStandardPagination({
    action,
    initialPage,
    responseSignal,
    protobuf,
    onLoad,
  })

  const currentState = state.value
  const resolvedMaxPage = currentState?.numPages ?? currentState?.maxKnownPage
  const showNav = resolvedMaxPage && resolvedMaxPage > 1

  const paginationListClass = `pagination justify-content-end ${small ? "pagination-sm" : ""}`
  const nav = (extraClass: string) => (
    <nav aria-label={label}>
      <ul class={`${paginationListClass} ${extraClass}`}>
        <PaginationItems
          targetPage={targetPage}
          currentPage={currentPage}
          state={state}
          pages={null}
          pageOrder={pageOrder}
        />
      </ul>
    </nav>
  )

  return (
    <>
      {showNav && navTop && nav(navClassTop)}
      <PaginationContent
        resource={resource}
        children={children}
      />
      {showNav && navBottom && nav(navClassBottom)}
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
  const {
    initialPage = 1,
    customLoader,
    loadCallback,
    pageOrder = "asc",
  } = options ?? {}
  const dataset = actionPagination.dataset
  const fetchUrl = dataset.action
  const customNumPages = dataset.pages ? Number.parseInt(dataset.pages, 10) : null
  if (customLoader) {
    assertExists(dataset.pages, "Pagination: Missing data-pages for custom loader")
  }

  console.debug("Pagination: Initializing", customLoader ? "<custom>" : fetchUrl)

  const scope = createDisposeScope()
  scope.defer(() => {
    for (const paginationContainer of paginationContainers)
      render(null, paginationContainer)
  })

  const targetPage = signal(initialPage)
  const currentPage = signal(initialPage)
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
    loadCallback?.(renderContainer, page)
  }

  // Effect: Load and render page content when targetPage changes (fetches or uses cache)
  scope.effect(() => {
    const targetPageValue = targetPage.value
    const targetPageString = targetPageValue.toString()

    if (customLoader) {
      const resolvedPage = Math.min(targetPageValue, customNumPages!)
      currentPage.value = resolvedPage
      customLoader(renderContainer, resolvedPage)
      afterLoad(resolvedPage)
      console.debug("Pagination: Page loaded (custom)", targetPageString)
      return
    }

    console.debug("Pagination: Loading page", targetPageString)
    const abortController = new AbortController()
    setPendingState(true)

    const fetchPage = async () => {
      try {
        assertExists(fetchUrl, "Pagination: Missing data-action")
        const baseState = state.peek()
        const resp = await fetch(
          fetchUrl,
          buildFetchInit(baseState, targetPageValue, abortController.signal),
        )
        assert(resp.ok, `Pagination: ${resp.status} ${resp.statusText}`)

        const parsed = parsePaginationHeader(resp.headers)
        applyState(parsed, state, currentPage)

        let skipRender = false
        if (!didInitialJump && initialPage !== 1) {
          didInitialJump = true
          const maxPage = parsed.numPages ?? parsed.maxKnownPage
          const resolvedInitialPage = Math.min(initialPage, maxPage)
          if (resolvedInitialPage !== parsed.currentPage) {
            // Avoid rendering an intermediate "page 1" snapshot when we immediately
            // jump to another page after receiving the initial pagination state.
            batch(() => {
              currentPage.value = resolvedInitialPage
              targetPage.value = resolvedInitialPage
            })
            skipRender = true
          }
        }

        if (!skipRender) {
          render(null, renderContainer)
          renderContainer.innerHTML = await resp.text()
          afterLoad(parsed.currentPage)
        }
        console.debug("Pagination: Page loaded", targetPageString)
      } catch (error) {
        if (error.name === "AbortError") return
        console.error(
          "Pagination: Failed to load page",
          targetPageString,
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
  scope.effect(() => {
    const currentState = state.value
    const numPagesValue = customNumPages ?? currentState?.numPages
    const maxKnownPageValue = customNumPages ?? currentState?.maxKnownPage ?? 1
    const resolvedMaxPage = numPagesValue ?? maxKnownPageValue
    if (resolvedMaxPage <= 1) {
      for (const paginationContainer of paginationContainers) {
        paginationContainer.hidden = true
        render(null, paginationContainer)
      }
      return
    }

    for (const paginationContainer of paginationContainers) {
      paginationContainer.hidden = false
      render(
        <PaginationItems
          targetPage={targetPage}
          currentPage={currentPage}
          state={state}
          pages={customNumPages}
          pageOrder={pageOrder}
        />,
        paginationContainer,
      )
    }
  })

  // Effect: Update pagination meta targets (num items/pages)
  scope.effect(() => {
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

  return scope.dispose
}

const resolvePaginationElements = (container: Element): StandardPaginationElements => {
  const actionPagination = container.querySelector(
    "ul.pagination[data-action], ul.pagination[data-pages]",
  )
  assertExists(actionPagination, "Pagination: Missing action pagination")
  const actionNav = actionPagination.closest("nav")
  assertExists(actionNav, "Pagination: Missing action nav")
  const paginationRoot = actionNav.parentElement
  assertExists(paginationRoot, "Pagination: Missing pagination root")
  const paginationContainers = Array.from(
    paginationRoot.querySelectorAll(":scope > nav > ul.pagination"),
  )

  const renderSibling = (actionNav.previousElementSibling ??
    paginationRoot.previousElementSibling) as HTMLElement | null
  assertExists(renderSibling, "Pagination: Missing render container")

  const renderContainer = renderSibling.matches("tbody, ul.list-unstyled")
    ? renderSibling
    : (renderSibling.querySelector("tbody, ul.list-unstyled") ?? renderSibling)

  const numItemsTargets = Array.from(container.querySelectorAll("[data-sp-num-items]"))
  const numPagesTargets = Array.from(container.querySelectorAll("[data-sp-num-pages]"))

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
  currentPageSignal: Signal<number>,
) => {
  batch(() => {
    state.value = value
    currentPageSignal.value = value.currentPage
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

  const pages = [1]

  const windowStart = Math.max(2, currentPage - STANDARD_PAGINATION_DISTANCE)
  const windowEnd = Math.min(
    resolvedMaxPage,
    currentPage + STANDARD_PAGINATION_DISTANCE,
  )
  for (let i = windowStart; i <= windowEnd; i++) pages.push(i)

  if (numPages !== undefined && pages.at(-1) !== numPages) pages.push(numPages)

  return pages
}

const formatPageLabel = (
  pageNumber: number,
  pageSize: number,
  numItems: number,
  isDesc: boolean,
) => {
  const offset = (pageNumber - 1) * pageSize
  const itemMax = numItems - offset
  const itemMin = itemMax - Math.min(pageSize, itemMax) + 1
  if (itemMax === itemMin) return itemMax.toString()
  return isDesc ? `${itemMax}‐${itemMin}` : `${itemMin}‐${itemMax}`
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
  assertExists(header, `Pagination: Missing ${SP_HEADER} header`)
  return fromBinaryValid(StandardPaginationStateSchema, base64Decode(header))
}

export const toPaginationResponse = <TData extends Message>(
  data: TData,
  headers: Headers,
): PaginationResponse<TData> => ({
  data,
  state: parsePaginationHeader(headers),
})
