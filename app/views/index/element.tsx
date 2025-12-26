import { fromBinary } from "@bufbuild/protobuf"
import {
  getActionSidebar,
  LoadingSpinner,
  SidebarHeader,
  switchActionSidebar,
} from "@index/_action-sidebar"
import { API_URL } from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import { convertRenderElementsData } from "@lib/map/render-objects"
import {
  type ElementData,
  ElementDataSchema,
  type PartialElementParams_Entry as ElementEntry,
  type ElementIcon,
  PartialElementParams_ElementType as ElementType,
} from "@lib/proto/shared_pb"
import { Tags } from "@lib/tags"
import { setPageTitle } from "@lib/title"
import {
  type Signal,
  signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { assert } from "@std/assert"
import { memoize } from "@std/cache/memoize"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { type ComponentChildren, Fragment, render } from "preact"

const THEME_COLOR = "#f60"
export const elementFocusPaint: FocusLayerPaint = {
  "fill-color": THEME_COLOR,
  "fill-opacity": 0.5,
  "line-color": THEME_COLOR,
  "line-opacity": 1,
  "line-width": 4,
  "circle-radius": 10,
  "circle-color": THEME_COLOR,
  "circle-opacity": 0.4,
  "circle-stroke-color": THEME_COLOR,
  "circle-stroke-opacity": 1,
  "circle-stroke-width": 3,
}

export const ELEMENTS_PER_PAGE = 15

// Pagination controls
const Pagination = ({
  page,
  totalPages,
}: {
  page: Signal<number>
  totalPages: number
}) => (
  <nav aria-label={t("alt.elements_page_navigation")}>
    <ul class="pagination pagination-sm pagination-2ch justify-content-end mb-0">
      {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
        <li
          class={`page-item ${p === page.value ? "active" : ""}`}
          key={p}
        >
          <button
            class="page-link"
            type="button"
            onClick={() => (page.value = p)}
          >
            {p}
          </button>
        </li>
      ))}
    </ul>
  </nav>
)

// Paginated element list section
export const ElementsSection = <T,>({
  items,
  title,
  renderRow,
  keyFn,
  class: extraClass,
}: {
  items: T[]
  title: (count: string) => string
  renderRow: (item: T) => ComponentChildren
  keyFn: (item: T) => string
  class?: string
}) => {
  if (!items.length) return null
  const page = useSignal(1)
  const totalPages = Math.ceil(items.length / ELEMENTS_PER_PAGE)
  const pageItems = items.slice(
    (page.value - 1) * ELEMENTS_PER_PAGE,
    page.value * ELEMENTS_PER_PAGE,
  )

  return (
    <div class={extraClass}>
      <h4 class="mt-3">{title(getPaginationCountLabel(page.value, items.length))}</h4>
      <div class="elements-list mb-2">
        <table class="table table-sm align-middle mb-0">
          <tbody>
            {pageItems.map((item) => (
              <Fragment key={keyFn(item)}>{renderRow(item)}</Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <Pagination
          page={page}
          totalPages={totalPages}
        />
      )}
    </div>
  )
}

type ElementTypeSlug = "node" | "way" | "relation"
type ElementLocationData = NonNullable<ElementData["location"]>

export const getElementTypeSlug = (type: ElementType) =>
  ElementType[type] as ElementTypeSlug

export const parseElementType = (value: string | null): ElementType | null => {
  if (value === "node") return ElementType.node
  if (value === "way") return ElementType.way
  if (value === "relation") return ElementType.relation
  return null
}

const formatElementLocation = (location: ElementLocationData) =>
  `${location.lat.toFixed(7)}, ${location.lon.toFixed(7)}`

const getElementTitleText = (data: ElementData) => {
  const idText = data.id.toString()
  const typeLabel = getElementTypeLabel(data.type)
  return data.name
    ? `${typeLabel}: ${data.name} (${idText})`
    : `${typeLabel}: ${idText}`
}

const ElementHeader = ({ data }: { data: ElementData }) => {
  const idText = data.id.toString()
  const typeLabel = getElementTypeLabel(data.type)
  const versionText = data.version.toString()
  const isLatest = data.nextVersion === undefined
  const badgeTitle = isLatest
    ? `${t("browse.version")} ${versionText} (${t("state.latest")})`
    : `${t("browse.version")} ${versionText}`

  return (
    <SidebarHeader class="mb-1">
      <h2>
        {data.icon && (
          <img
            class="sidebar-title-icon"
            src={`/static/img/element/${data.icon.icon}`}
            title={data.icon.title}
            aria-hidden="true"
          />
        )}
        <span class="sidebar-title">
          {typeLabel}:{" "}
          {data.name ? (
            <>
              <bdi>{data.name}</bdi> ({idText})
            </>
          ) : (
            idText
          )}
        </span>
        <span
          class={`version-badge badge ${isLatest ? "is-latest" : ""}`}
          title={badgeTitle}
        >
          v{versionText}
        </span>
      </h2>
    </SidebarHeader>
  )
}

export const ElementMeta = ({ data }: { data: ElementData }) => {
  const changeset = data.changeset!
  const user = changeset.user
  return (
    <div class="social-entry">
      <p class="header text-muted d-flex justify-content-between">
        <span>
          {user ? (
            <a href={`/user/${user.displayName}`}>
              <img
                class="avatar"
                src={user.avatarUrl}
                alt={t("alt.profile_picture")}
                loading="lazy"
              />
              {user.displayName}
            </a>
          ) : (
            t("browse.anonymous")
          )}{" "}
          {data.visible ? t("action.edited") : t("action.deleted")}{" "}
          <Time
            unix={changeset.createdAt}
            relativeStyle="long"
          />
        </span>
        {!data.visible && (
          <span class="badge text-bg-secondary">
            <i class="bi bi-trash-fill" />
          </span>
        )}
      </p>
      <div class="body">
        <p class="position-relative mb-1">
          {t("browse.in_changeset")} #
          <a href={`/changeset/${changeset.id.toString()}`}>
            {changeset.id.toString()}
          </a>
        </p>
        <div
          class="fst-italic"
          dangerouslySetInnerHTML={{ __html: changeset.commentRich }}
        />
      </div>
    </div>
  )
}

export const ElementLocation = ({
  map,
  location,
}: {
  map: MaplibreMap
  location: ElementLocationData
}) => (
  <p class="location-container mb-2">
    {t("diary_entries.form.location")}:{" "}
    <button
      class="btn btn-link stretched-link"
      type="button"
      onClick={() => {
        map.flyTo({
          center: [location.lon, location.lat],
          zoom: Math.max(map.getZoom(), 15),
        })
      }}
    >
      {formatElementLocation(location)}
    </button>
  </p>
)

const ElementHistoryLinks = ({ data }: { data: ElementData }) => {
  const idText = data.id.toString()
  const typeSlug = getElementTypeSlug(data.type)
  const prev = data.prevVersion
  const next = data.nextVersion

  return (
    <div class="section text-center">
      {(prev !== undefined || next !== undefined) && (
        <div class="mb-2">
          {prev !== undefined && (
            <a
              href={`/${typeSlug}/${idText}/history/${prev.toString()}`}
              rel="prev"
            >
              « v{prev.toString()}
            </a>
          )}
          {prev !== undefined && " · "}
          <a href={`/${typeSlug}/${idText}/history`}>{t("browse.view_history")}</a>
          {next !== undefined && (
            <>
              {" "}
              ·{" "}
              <a
                href={`/${typeSlug}/${idText}/history/${next.toString()}`}
                rel="next"
              >
                v{next.toString()} »
              </a>
            </>
          )}
        </div>
      )}
      {data.visible && (
        <small>
          <a
            href={`${API_URL}/api/0.6/${typeSlug}/${idText}/${data.version.toString()}`}
          >
            {t("browse.download_xml")}
          </a>
        </small>
      )}
    </div>
  )
}

export const ElementNotFound = ({
  type,
  id,
}: {
  type: ElementType | null
  id: string
}) => {
  const typeLabel = type !== null ? getElementTypeLabel(type).toLowerCase() : ""
  return (
    <div class="section">
      <SidebarHeader title={t("browse.not_found.title")} />
      <p>
        {type !== null
          ? t("browse.not_found.sorry", { type: typeLabel, id })
          : t("browse.not_found.title")}
      </p>
    </div>
  )
}

const ElementSidebar = ({
  map,
  type,
  id,
  version,
  sidebar,
}: {
  map: MaplibreMap
  type: Signal<string | null>
  id: Signal<string | null>
  version: Signal<string | null>
  sidebar: HTMLElement
}) => {
  const data = useSignal<ElementData | null>(null)
  const loading = useSignal(false)
  const error = useSignal<string | null>(null)
  const notFound = useSignal(false)
  const params = useComputed(() => data.value?.params ?? null)
  const renderElements = useComputed(() =>
    convertRenderElementsData(params.value?.render),
  )

  // Effect: Fetch element data
  useSignalEffect(() => {
    const etype = type.value
    const eid = id.value
    const v = version.value

    if (!(etype && eid)) {
      data.value = null
      loading.value = false
      error.value = null
      notFound.value = false
      return
    }

    loading.value = true
    error.value = null
    notFound.value = false
    const abortController = new AbortController()
    const url = v
      ? `/api/web/element/${etype}/${eid}/history/${v}`
      : `/api/web/element/${etype}/${eid}`

    fetch(url, { signal: abortController.signal, priority: "high" })
      .then(async (resp) => {
        if (resp.status === 404) {
          notFound.value = true
          data.value = null
          return
        }
        assert(resp.ok, `${resp.status} ${resp.statusText}`)

        const buffer = await resp.arrayBuffer()
        abortController.signal.throwIfAborted()
        data.value = fromBinary(ElementDataSchema, new Uint8Array(buffer))
      })
      .catch((err) => {
        if (err.name === "AbortError") return
        error.value = err.message
      })
      .finally(() => {
        if (!abortController.signal.aborted) loading.value = false
      })

    return () => abortController.abort()
  })

  // Effect: Page title
  useSignalEffect(() => {
    if (notFound.value) {
      setPageTitle(t("browse.not_found.title"))
      return
    }
    if (data.value) setPageTitle(getElementTitleText(data.value))
  })

  // Effect: Map focus
  useSignalEffect(() => {
    focusObjects(map, renderElements.value, elementFocusPaint)
    return () => focusObjects(map)
  })

  // Effect: Sidebar visibility
  useSignalEffect(() => {
    if (id.value) switchActionSidebar(map, sidebar)
  })

  const notFoundId = version.value
    ? `${id.value} ${t("browse.version").toLowerCase()} ${version.value}`
    : (id.value ?? "")
  const notFoundType = parseElementType(type.value)

  const d = data.value
  const paramsValue = params.value
  const hasRelations = paramsValue
    ? paramsValue.parents.length > 0 || paramsValue.members.length > 0
    : false

  return (
    <div class="sidebar-content">
      {loading.value && <LoadingSpinner />}
      {error.value && (
        <div
          class="alert alert-danger"
          role="alert"
        >
          {error.value}
        </div>
      )}
      {notFound.value && (
        <ElementNotFound
          type={notFoundType}
          id={notFoundId}
        />
      )}
      {d && (
        <>
          <div class="section">
            <ElementHeader data={d} />
            <ElementMeta data={d} />

            {d.location && (
              <ElementLocation
                map={map}
                location={d.location}
              />
            )}

            <Tags tags={d.tags} />

            {paramsValue && hasRelations && (
              <div class="elements mt-3">
                <ElementsSection
                  items={paramsValue.parents}
                  title={(count) => `${t("browse.part_of")} (${count})`}
                  renderRow={(el) => <ElementRow element={el} />}
                  keyFn={(el) => `${el.type}-${el.id}-${el.role ?? ""}`}
                />
                <ElementsSection
                  items={paramsValue.members}
                  title={(count) =>
                    paramsValue.type === ElementType.way
                      ? // @ts-expect-error
                        t("browse.changeset.node", { count })
                      : `${t("browse.relation.members")} (${count})`
                  }
                  renderRow={(el) => <ElementRow element={el} />}
                  keyFn={(el) => `${el.type}-${el.id}-${el.role ?? ""}`}
                />
              </div>
            )}
          </div>
          <ElementHistoryLinks data={d} />
        </>
      )}
    </div>
  )
}

export const getElementController = (map: MaplibreMap) => {
  const sidebar = getActionSidebar("element")
  const type = signal<string | null>(null)
  const id = signal<string | null>(null)
  const version = signal<string | null>(null)

  render(
    <ElementSidebar
      map={map}
      type={type}
      id={id}
      version={version}
      sidebar={sidebar}
    />,
    sidebar,
  )

  return {
    load: (matchGroups: Record<string, string>) => {
      type.value = matchGroups.type
      id.value = matchGroups.id
      version.value = matchGroups.version ?? null
    },
    unload: () => {
      id.value = null
    },
  }
}

export const ElementsListRow = ({
  href,
  icon,
  title,
  meta,
  class: extraClass,
}: {
  href: string
  icon: ElementIcon | undefined
  title: ComponentChildren
  meta: ComponentChildren
  class?: string
}) => (
  <tr class={extraClass}>
    <td>
      {icon && (
        <img
          loading="lazy"
          src={`/static/img/element/${icon.icon}`}
          title={icon.title}
          aria-hidden="true"
        />
      )}
    </td>

    <td>
      <div class="element-row-title">
        <a href={href}>
          <bdi>{title}</bdi>
        </a>
      </div>
      <div class="element-row-meta">{meta}</div>
    </td>
  </tr>
)

const ElementRow = ({ element }: { element: ElementEntry }) => {
  const idStr = element.id.toString()
  const href = `/${getElementTypeSlug(element.type)}/${idStr}`

  return (
    <ElementsListRow
      href={href}
      icon={element.icon}
      title={element.name || idStr}
      meta={
        <>
          <span>{getElementTypeLabel(element.type)}</span>
          {element.name && <span>{`#${idStr}`}</span>}
          {element.role && (
            <>
              <span aria-hidden="true"> · </span>
              <span>{element.role}</span>
            </>
          )}
        </>
      }
    />
  )
}

export const getElementTypeLabel = memoize((type: ElementType) => {
  if (type === ElementType.node) return t("javascripts.query.node")
  if (type === ElementType.way) return t("javascripts.query.way")
  return t("javascripts.query.relation")
})

export const getPaginationCountLabel = (page: number, totalItems: number) => {
  if (totalItems > ELEMENTS_PER_PAGE) {
    const from = (page - 1) * ELEMENTS_PER_PAGE + 1
    const to = Math.min(page * ELEMENTS_PER_PAGE, totalItems)
    return t("pagination.range", {
      x: `${from}-${to}`,
      y: totalItems,
    })
  }
  return totalItems.toString()
}
