import type { DescMessage, DescMethodUnary, MessageInitShape } from "@bufbuild/protobuf"
import { create, type MessageValidType, toBinary } from "@bufbuild/protobuf"
import { Code, ConnectError } from "@connectrpc/connect"
import { queryParam } from "@lib/codecs"
import {
  STANDARD_PAGINATION_DISTANCE,
  STANDARD_PAGINATION_MAX_FULL_PAGES,
} from "@lib/config"
import { resolveDatetimeLazy } from "@lib/datetime-inputs"
import { createDisposeScope, useDisposeSignalEffect } from "@lib/dispose-scope"
import {
  type StandardPaginationRequest,
  StandardPaginationRequestSchema,
  type StandardPaginationState,
  StandardPaginationStateSchema,
} from "@lib/proto/shared_pb"
import {
  connectErrorToMessage,
  fromBase64Valid,
  type LooseMessageInitShape,
  rpcUnary,
} from "@lib/rpc"
import {
  currentUrlSignal,
  readUrlQueryParam,
  updateUrlQueryParam,
  type UrlUpdateMode,
} from "@lib/url-state"
import { encodeAscii, range, throwAbortError } from "@lib/utils"
import {
  batch,
  type ReadonlySignal,
  type Signal,
  signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { assert } from "@std/assert"
import { t } from "i18next"
import type { ComponentChildren } from "preact"
import { render } from "preact"

const SP_HEADER = "X-StandardPagination"

export enum PageOrder {
  asc,
  asc_range,
  desc,
  desc_range,
}

type StandardPaginationOptions = {
  initialPage?: number
  loadCallback?: (renderContainer: HTMLElement, page: number) => void
  pageOrder?: PageOrder
  urlKey?: string
}

type StandardPaginationElements = {
  actionPagination: HTMLUListElement
  paginationContainers: HTMLUListElement[]
  renderContainer: HTMLElement
  numItemsTargets: Element[]
  numPagesTargets: Element[]
}

type PaginationResponse = {
  state: StandardPaginationState
}

type PaginationLoader<TData extends PaginationResponse> = (
  baseState: StandardPaginationState | null,
  requestedPage: number,
  abortSignal: AbortSignal,
) => Promise<TData>

type PaginationResource<TData> =
  | { tag: "boot" }
  | { tag: "loading"; prev: TData | null }
  | { tag: "ready"; data: TData }
  | { tag: "error"; error: string; prev: TData | null }

const paginationKnownTotal = (state: StandardPaginationState | null | undefined) =>
  state?.totalExtent.case === "knownTotal" ? state.totalExtent.value : undefined

const paginationNumPages = (state: StandardPaginationState | null | undefined) =>
  paginationKnownTotal(state)?.numPages

const paginationNumItems = (state: StandardPaginationState | null | undefined) =>
  paginationKnownTotal(state)?.numItems

const paginationMaxPage = (state: StandardPaginationState | null | undefined) =>
  paginationKnownTotal(state)?.numPages ??
  (state?.totalExtent.case === "maxDiscoveredPage" ? state.totalExtent.value : 1)

const paginationRequest = (
  requestedPage: number,
  state: StandardPaginationState | undefined,
): StandardPaginationRequest => ({
  $typeName: "StandardPaginationRequest",
  // TODO: simplify after types update
  ...(state === undefined ? {} : { state }),
  requestedPage,
})

const PAGE_QUERY = queryParam.positiveInt()

const getUrlPage = (urlKey: string) => readUrlQueryParam(urlKey, PAGE_QUERY)

const updateUrlPage = (urlKey: string, page: number, mode: UrlUpdateMode) =>
  updateUrlQueryParam(urlKey, PAGE_QUERY, page <= 1 ? undefined : page, mode)

const PaginationSpinner = ({ class: className = "" }: { class?: string }) => (
  <div class={`sp-spinner ${className}`}>
    <output
      class="spinner-border text-body-secondary"
      aria-live="polite"
    >
      <span class="visually-hidden">{t("browse.start_rjs.loading")}</span>
    </output>
  </div>
)

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
  spinnerClass,
  children,
}: {
  resource: ReadonlySignal<PaginationResource<TData>>
  spinnerClass: string
  children: (data: TData) => ComponentChildren
}) => {
  const r = resource.value

  switch (r.tag) {
    case "boot":
      return <PaginationSpinner class={spinnerClass} />

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
        <PaginationSpinner class={spinnerClass} />
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
  currentPage,
  setTargetPage,
  pageOrder,
  maxPage,
  numPages,
  numItems,
  pageSize,
  showTailEllipsis,
}: {
  currentPage: ReadonlySignal<number>
  setTargetPage: (page: number) => void
  pageOrder: PageOrder
  maxPage: number
  numPages: number | undefined
  numItems: number | undefined
  pageSize: number | undefined
  showTailEllipsis: boolean
}) => {
  const actualPage = currentPage.value

  if ((numPages ?? maxPage) <= 1) return null

  // For desc mode, invert page numbers: display = numPages - actual + 1
  const isDesc = pageOrder === PageOrder.desc || pageOrder === PageOrder.desc_range
  const showRange =
    pageOrder === PageOrder.asc_range || pageOrder === PageOrder.desc_range
  const toDisplay = (actual: number) =>
    isDesc && numPages ? numPages - actual + 1 : actual
  const toActual = (display: number) =>
    isDesc && numPages ? numPages - display + 1 : display

  const displayPage = toDisplay(actualPage)

  const pagesToRender = computePagesToRender(
    displayPage,
    isDesc ? toDisplay(1) : maxPage,
    numPages,
  )
  const tokens: (number | "gap")[] = []
  let previousPage = 0
  for (const pageNumber of pagesToRender) {
    if (previousPage && pageNumber - previousPage > 1) tokens.push("gap")
    tokens.push(pageNumber)
    previousPage = pageNumber
  }
  if (showTailEllipsis && !isDesc) tokens.push("gap")

  return (
    <>
      {tokens.map((token, index) => {
        if (token === "gap") {
          return (
            <li
              // oxlint-disable-next-line react/no-array-index-key
              key={`gap-${tokens[index - 1]}-${tokens[index + 1]}`}
              class="page-item disabled"
            >
              <span class="page-link">...</span>
            </li>
          )
        }

        const displayPageNum = token
        const actualPageNum = toActual(displayPageNum)
        const label =
          showRange && pageSize && numItems !== undefined
            ? formatPageLabel(actualPageNum, pageSize, numItems, isDesc)
            : displayPageNum.toString()

        if (displayPageNum === displayPage) {
          return (
            <li
              key={displayPageNum}
              class="page-item active"
              aria-current="page"
            >
              <span class="page-link">{label}</span>
            </li>
          )
        }

        return (
          <li
            key={displayPageNum}
            class="page-item"
          >
            <button
              class="page-link"
              type="button"
              onClick={() => setTargetPage(actualPageNum)}
            >
              {label}
            </button>
          </li>
        )
      })}
    </>
  )
}

export const StandardPaginationNav = ({
  ariaLabel,
  currentPage,
  setTargetPage,
  pageOrder,
  maxPage,
  numPages,
  numItems,
  pageSize,
  showTailEllipsis = false,
  small = false,
  class: className = "",
}: {
  ariaLabel: string
  currentPage: ReadonlySignal<number>
  setTargetPage: (page: number) => void
  pageOrder: PageOrder
  maxPage: number
  numPages: number | undefined
  numItems?: number | undefined
  pageSize?: number | undefined
  showTailEllipsis?: boolean
  small?: boolean
  class?: string
}) => {
  if ((numPages ?? maxPage) <= 1) return null

  const paginationClass =
    `pagination justify-content-end ${small ? "pagination-sm" : ""} ${className}`.trim()
  return (
    <nav aria-label={ariaLabel}>
      <ul class={paginationClass}>
        <PaginationItems
          currentPage={currentPage}
          setTargetPage={setTargetPage}
          pageOrder={pageOrder}
          maxPage={maxPage}
          numPages={numPages}
          numItems={numItems}
          pageSize={pageSize}
          showTailEllipsis={showTailEllipsis}
        />
      </ul>
    </nav>
  )
}

// Hook: manages pagination state machine
const useStandardPagination = <TData extends PaginationResponse>({
  loadPage,
  initialPage,
  responseSignal,
  onLoad,
  urlKey,
}: {
  loadPage: PaginationLoader<TData>
  initialPage: number
  responseSignal: Signal<TData | null> | undefined
  onLoad: ((data: TData, page: number) => void) | undefined
  urlKey: string | undefined
}) => {
  const state = useSignal<StandardPaginationState | null>(null)
  const targetPage = useSignal(initialPage)
  const resource = useSignal<PaginationResource<TData>>({ tag: "boot" })
  const setTargetPage = (page: number, urlMode?: UrlUpdateMode) => {
    if (urlKey && urlMode) updateUrlPage(urlKey, page, urlMode)
    targetPage.value = page
  }

  useSignalEffect(() => {
    if (!urlKey) return
    const page = readUrlQueryParam(urlKey, PAGE_QUERY, currentUrlSignal.value)
    const resolvedPage = page ?? 1
    if (targetPage.peek() !== resolvedPage) targetPage.value = resolvedPage
  })

  // Effect: react to external response updates (e.g., after POST)
  useSignalEffect(() => {
    if (!responseSignal) return
    const data = responseSignal.value
    if (!data) return

    setTargetPage(data.state.currentPage, "replace")
    onLoad?.(data, data.state.currentPage)
    state.value = data.state
    resource.value = { tag: "ready", data }
    responseSignal.value = null
  })

  // Derived: current page from last known pagination state
  const currentPage = useComputed(() => state.value?.currentPage ?? targetPage.value)

  // Effect: fetch page when targetPage changes
  useDisposeSignalEffect((scope) => {
    const page = targetPage.value
    const current = resource.peek()
    const currentState = state.peek()

    // Skip if already at target page (prevents double-fetch after initial jump)
    if (current.tag === "ready" && currentState?.currentPage === page) {
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
        const data = await loadPage(currentState, page, scope.signal)
        const responseState = data.state

        // Handle initial jump: if we're booting and target differs from what server returned
        if (current.tag === "boot" && initialPage !== 1) {
          const maxPage = paginationMaxPage(responseState)
          const resolvedPage = Math.min(initialPage, maxPage)
          if (resolvedPage !== responseState.currentPage) {
            if (urlKey) updateUrlPage(urlKey, resolvedPage, "replace")
            batch(() => {
              state.value = responseState
              targetPage.value = resolvedPage
            })
            return // Effect will re-run with correct page
          }
        }

        scope.signal.throwIfAborted()

        batch(() => {
          onLoad?.(data, responseState.currentPage)
          state.value = responseState
          resource.value = { tag: "ready", data }
        })
      } catch (error) {
        if (error.name === "AbortError") return
        console.error("Pagination: Failed to load page", page, error)
        resource.value = { tag: "error", error: error.message, prev }
      }
    }
    void fetchPage()
  })

  return { targetPage, setTargetPage, resource, currentPage, state }
}

type PaginatedRequestInit<I extends DescMessage> =
  "state" extends keyof MessageInitShape<I> ? LooseMessageInitShape<I> : never

type PaginatedResponse<O extends DescMessage> =
  MessageValidType<O> extends PaginationResponse ? MessageValidType<O> : never

type StandardPaginationProps<I extends DescMessage, O extends DescMessage> = {
  method: DescMethodUnary<I, O>
  request: Omit<PaginatedRequestInit<I>, "state">
  ariaLabel?: string
  pageOrder?: PageOrder
  initialPage?: number
  urlKey?: string
  responseSignal?: Signal<PaginatedResponse<O> | null>
  onLoad?: (data: PaginatedResponse<O>, page: number) => void
  small?: boolean
  navTop?: boolean
  navClassTop?: string
  navBottom?: boolean
  navClassBottom?: string
  spinnerClass?: string
  children: (data: PaginatedResponse<O>) => ComponentChildren
}

const StandardPaginationInstance = <I extends DescMessage, O extends DescMessage>({
  method,
  request,
  ariaLabel = t("alt.page_navigation"),
  pageOrder = PageOrder.asc,
  initialPage = 1,
  urlKey,
  responseSignal,
  onLoad,
  small = false,
  navTop = false,
  navClassTop = "mb-2",
  navBottom = true,
  navClassBottom = "",
  spinnerClass = "",
  children,
}: StandardPaginationProps<I, O>) => {
  type TRequest = PaginatedRequestInit<I>
  type TResponse = PaginatedResponse<O>

  const loadPage: PaginationLoader<TResponse> = async (
    baseState,
    requestedPage,
    abortSignal,
  ) => {
    try {
      return (await rpcUnary(method)(
        {
          ...request,
          state: paginationRequest(
            requestedPage,
            baseState === null ? undefined : baseState,
          ),
        } as unknown as TRequest,
        { signal: abortSignal },
      )) as TResponse
    } catch (error) {
      const err = ConnectError.from(error)
      if (err.code === Code.Canceled) throwAbortError()
      throw new Error(connectErrorToMessage(err), {
        cause: error,
      })
    }
  }

  const { resource, currentPage, setTargetPage, state } = useStandardPagination({
    loadPage,
    initialPage: urlKey ? (getUrlPage(urlKey) ?? initialPage) : initialPage,
    responseSignal,
    onLoad,
    urlKey,
  })

  const currentState = state.value
  const maxPage = paginationMaxPage(currentState)
  const numPages = paginationNumPages(currentState)
  const showNav = (numPages ?? maxPage) > 1
  const showTailEllipsis = currentState !== null && numPages === undefined

  return (
    <>
      {showNav && navTop && (
        <StandardPaginationNav
          ariaLabel={ariaLabel}
          currentPage={currentPage}
          setTargetPage={(page) => setTargetPage(page, "push")}
          pageOrder={pageOrder}
          maxPage={maxPage}
          numPages={numPages}
          numItems={paginationNumItems(currentState)}
          pageSize={currentState?.pageSize}
          showTailEllipsis={showTailEllipsis}
          small={small}
          class={navClassTop}
        />
      )}
      <PaginationContent
        resource={resource}
        spinnerClass={spinnerClass}
      >
        {children}
      </PaginationContent>
      {showNav && navBottom && (
        <StandardPaginationNav
          ariaLabel={ariaLabel}
          currentPage={currentPage}
          setTargetPage={(page) => setTargetPage(page, "push")}
          pageOrder={pageOrder}
          maxPage={maxPage}
          numPages={numPages}
          numItems={paginationNumItems(currentState)}
          pageSize={currentState?.pageSize}
          showTailEllipsis={showTailEllipsis}
          small={small}
          class={navClassBottom}
        />
      )}
    </>
  )
}

const standardPaginationRequestKey = <I extends DescMessage, O extends DescMessage>(
  method: DescMethodUnary<I, O>,
  request: Omit<PaginatedRequestInit<I>, "state">,
) =>
  `${method.parent.typeName}.${method.localName}:${encodeAscii(
    toBinary(
      method.input,
      create(method.input, request as unknown as MessageInitShape<I>),
    ),
  )}`

export const StandardPagination = <I extends DescMessage, O extends DescMessage>(
  props: StandardPaginationProps<I, O>,
) => (
  <StandardPaginationInstance
    key={standardPaginationRequestKey(props.method, props.request)}
    {...props}
  />
)

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
    loadCallback,
    pageOrder = PageOrder.asc,
    urlKey,
  } = options ?? {}
  const fetchUrl = actionPagination.dataset.action!
  const resolvedInitialPage = urlKey ? (getUrlPage(urlKey) ?? initialPage) : initialPage

  console.debug("Pagination: Initializing", fetchUrl)

  const scope = createDisposeScope()
  scope.defer(() => {
    for (const paginationContainer of paginationContainers)
      render(null, paginationContainer)
  })

  const targetPage = signal(resolvedInitialPage)
  const currentPage = signal(targetPage.value)
  const state = signal<StandardPaginationState | null>(null)
  const setTargetPage = (page: number, urlMode?: UrlUpdateMode) => {
    if (urlKey && urlMode) updateUrlPage(urlKey, page, urlMode)
    targetPage.value = page
  }

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

  scope.effect(() => {
    if (!urlKey) return
    const page = readUrlQueryParam(urlKey, PAGE_QUERY, currentUrlSignal.value)
    const resolvedPage = page ?? 1
    if (targetPage.peek() !== resolvedPage) targetPage.value = resolvedPage
  })

  // Effect: Load and render page content when targetPage changes (fetches or uses cache)
  scope.effect(() => {
    const targetPageValue = targetPage.value
    const targetPageString = targetPageValue.toString()

    console.debug("Pagination: Loading page", targetPageString)
    const abortController = new AbortController()
    setPendingState(true)

    const fetchPage = async () => {
      try {
        const baseState = state.peek()
        const resp = await fetch(
          fetchUrl,
          buildFetchInit(baseState, targetPageValue, abortController.signal),
        )
        assert(resp.ok, `Pagination: ${resp.status} ${resp.statusText}`)

        const parsed = parsePaginationHeader(resp.headers)
        applyState(parsed, state, currentPage)

        let skipRender = false
        if (!didInitialJump && resolvedInitialPage !== 1) {
          didInitialJump = true
          const maxPage = paginationMaxPage(parsed)
          const resolvedPage = Math.min(resolvedInitialPage, maxPage)
          if (resolvedPage !== parsed.currentPage) {
            if (urlKey) updateUrlPage(urlKey, resolvedPage, "replace")
            // Avoid rendering an intermediate "page 1" snapshot when we immediately
            // jump to another page after receiving the initial pagination state.
            batch(() => {
              currentPage.value = resolvedPage
              targetPage.value = resolvedPage
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
    void fetchPage()

    return () => abortController.abort()
  })

  // Effect: Rebuild pagination UI buttons when page counts or current page changes
  scope.effect(() => {
    const currentState = state.value
    const numPagesValue = paginationNumPages(currentState)
    const maxPageValue = paginationMaxPage(currentState)
    const showTailEllipsis = currentState !== null && numPagesValue === undefined
    if ((numPagesValue ?? maxPageValue) <= 1) {
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
          setTargetPage={(page) => setTargetPage(page, "push")}
          currentPage={currentPage}
          maxPage={maxPageValue}
          numPages={numPagesValue}
          numItems={paginationNumItems(currentState)}
          pageSize={currentState?.pageSize}
          pageOrder={pageOrder}
          showTailEllipsis={showTailEllipsis}
        />,
        paginationContainer,
      )
    }
  })

  // Effect: Update pagination meta targets (num items/pages)
  scope.effect(() => {
    const currentState = state.value
    const numItemsValue = paginationNumItems(currentState)
    const numPagesValue = paginationNumPages(currentState)

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
  const actionPagination = container.querySelector("ul.pagination[data-action]")!
  const actionNav = actionPagination.closest("nav")!
  const paginationRoot = actionNav.parentElement!
  const paginationContainers = [
    ...paginationRoot.querySelectorAll(":scope > nav > ul.pagination"),
  ]

  const renderSibling = (actionNav.previousElementSibling ??
    paginationRoot.previousElementSibling) as HTMLElement

  const renderContainer = renderSibling.matches("tbody, ul.list-unstyled")
    ? renderSibling
    : (renderSibling.querySelector("tbody, ul.list-unstyled") ?? renderSibling)

  const numItemsTargets = [...container.querySelectorAll("[data-sp-num-items]")]
  const numPagesTargets = [...container.querySelectorAll("[data-sp-num-pages]")]

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
  maxPage: number,
  numPages: number | undefined,
) => {
  const resolvedMaxPage = numPages ?? maxPage

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

  if (baseState !== null || requestedPage !== 1) {
    const requestBytes = toBinary(
      StandardPaginationRequestSchema,
      paginationRequest(requestedPage, baseState === null ? undefined : baseState),
    )
    fetchInit.body = new Blob([requestBytes], {
      type: "application/x-protobuf",
    })
  }

  return fetchInit
}

const parsePaginationHeader = (headers: Headers) =>
  fromBase64Valid(StandardPaginationStateSchema, headers.get(SP_HEADER)!)
