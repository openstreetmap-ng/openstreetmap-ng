import { SidebarContent, SidebarHeader, useSidebarRpc } from "@index/_action-sidebar"
import { defineRoute } from "@index/router"
import { routeParam } from "@lib/codecs"
import { API_URL } from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import { convertRenderElementsData } from "@lib/map/render-objects"
import type { LonLat } from "@lib/map/state"
import {
  type ElementData_Context_EntryValid,
  type ElementDataValid,
  ElementService,
} from "@lib/proto/element_pb"
import { type ElementIcon, ElementType } from "@lib/proto/shared_pb"
import { StandardPaginationNav } from "@lib/standard-pagination"
import { Tags } from "@lib/tags"
import { setPageTitle } from "@lib/title"
import {
  type ReadonlySignal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { type ComponentChildren, Fragment } from "preact"

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
        <StandardPaginationNav
          ariaLabel={t("alt.elements_page_navigation")}
          currentPage={page}
          targetPage={page}
          pageOrder="asc"
          maxKnownPage={totalPages}
          numPages={totalPages}
          small
          class="pagination-2ch mb-0"
        />
      )}
    </div>
  )
}

export type ElementTypeSlug = keyof typeof ElementType

export const getElementTypeSlug = (type: ElementType) =>
  ElementType[type] as ElementTypeSlug

export const ElementTypeParam = routeParam.enum(["node", "way", "relation"])
export const ElementIdParam = routeParam.positive()
export const ElementVersionParam = routeParam.positive()

const formatElementLocation = ({ lon, lat }: LonLat) =>
  `${lat.toFixed(7)}, ${lon.toFixed(7)}`

const getElementTitleText = (data: ElementDataValid) => {
  const { type, id } = data.ref
  const typeLabel = getElementTypeLabel(type)
  return data.name ? `${typeLabel}: ${data.name} (${id})` : `${typeLabel}: ${id}`
}

const ElementHeader = ({ data }: { data: ElementDataValid }) => {
  const { type, id, version } = data.ref
  const isLatest = data.nextVersion === undefined

  return (
    <SidebarHeader class="mb-1">
      <h2>
        {data.icon && (
          <img
            class="sidebar-title-icon me-2"
            src={`/static/img/element/${data.icon.icon}`}
            title={data.icon.title}
            aria-hidden="true"
          />
        )}
        <span class="sidebar-title me-1-5">
          {getElementTypeLabel(type)}:{" "}
          {data.name ? (
            <>
              <bdi>{data.name}</bdi> ({id})
            </>
          ) : (
            id
          )}
        </span>
        <span
          class={`version-badge badge ${isLatest ? "is-latest" : ""}`}
          title={
            isLatest
              ? `${t("browse.version")} ${version} (${t("state.latest")})`
              : `${t("browse.version")} ${version}`
          }
        >
          v{version}
        </span>
      </h2>
    </SidebarHeader>
  )
}

export const ElementMeta = ({ data }: { data: ElementDataValid }) => {
  const changeset = data.changeset
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
          <a href={`/changeset/${changeset.id}`}>{changeset.id}</a>
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
  location: LonLat
}) => (
  <p class="location-container mb-2">
    {t("diary_entries.form.location")}:{" "}
    <button
      class="btn btn-link stretched-link"
      type="button"
      onClick={() =>
        map.flyTo({
          center: [location.lon, location.lat],
          zoom: Math.max(map.getZoom(), 15),
        })
      }
    >
      {formatElementLocation(location)}
    </button>
  </p>
)

const ElementHistoryLinks = ({ data }: { data: ElementDataValid }) => {
  const { type, id, version } = data.ref
  const typeText = getElementTypeSlug(type)
  const prev = data.prevVersion
  const next = data.nextVersion

  return (
    <div class="section text-center">
      {(prev !== undefined || next !== undefined) && (
        <div class="mb-2">
          {prev !== undefined && (
            <a
              href={`/${typeText}/${id}/history/${prev}`}
              rel="prev"
            >
              « v{prev}
            </a>
          )}
          {prev !== undefined && " · "}
          <a href={`/${typeText}/${id}/history`}>{t("browse.view_history")}</a>
          {next !== undefined && (
            <>
              {" "}
              ·{" "}
              <a
                href={`/${typeText}/${id}/history/${next}`}
                rel="next"
              >
                v{next} »
              </a>
            </>
          )}
        </div>
      )}
      {data.visible && (
        <small>
          <a href={`${API_URL}/api/0.6/${typeText}/${id}/${version}`}>
            {t("browse.download_xml")}
          </a>
        </small>
      )}
    </div>
  )
}

const ElementSidebar = ({
  map,
  type,
  id,
  version,
}: {
  map: MaplibreMap
  type: ReadonlySignal<ElementTypeSlug>
  id: ReadonlySignal<bigint>
  version: ReadonlySignal<bigint | undefined>
}) => {
  const { resource, data } = useSidebarRpc(
    useComputed(() => {
      const typeValue = ElementType[type.value]
      const idValue = id.value
      const versionValue = version.value
      return versionValue !== undefined
        ? {
            ref: {
              case: "version" as const,
              value: { type: typeValue, id: idValue, version: versionValue },
            },
          }
        : {
            ref: {
              case: "element" as const,
              value: { type: typeValue, id: idValue },
            },
          }
    }),
    ElementService.method.getElement,
    (r) => r.element,
  )
  const renderElements = useComputed(() =>
    convertRenderElementsData(data.value?.context.render),
  )

  // Effect: Sync derived state
  useSignalEffect(() => {
    const r = resource.value
    if (r.tag === "not-found") {
      setPageTitle(t("browse.not_found.title"))
    } else {
      const d = data.value
      if (d) setPageTitle(getElementTitleText(d))
    }
  })

  // Effect: Map focus
  useSignalEffect(() => {
    focusObjects(map, renderElements.value, elementFocusPaint)
    return () => focusObjects(map)
  })

  return (
    <SidebarContent
      resource={resource}
      notFound={() => {
        const typeLabel = getElementTypeLabel(ElementType[type.value]).toLowerCase()
        const versionValue = version.value
        const idLabel =
          versionValue !== undefined
            ? `${id.value} ${t("browse.version").toLowerCase()} ${versionValue}`
            : id.toString()
        return t("browse.not_found.sorry", { type: typeLabel, id: idLabel })
      }}
    >
      {(d) => {
        const { parents, members } = d.context
        const hasRelations = parents.length > 0 || members.length > 0

        return (
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

              {hasRelations && (
                <div class="elements mt-3">
                  <ElementsSection
                    keyFn={(el) => `${el.ref.type}-${el.ref.id}-${el.role ?? ""}`}
                    items={parents}
                    title={(count) => `${t("browse.part_of")} (${count})`}
                    renderRow={(el) => <ElementRow element={el} />}
                  />
                  <ElementsSection
                    keyFn={(el) => `${el.ref.type}-${el.ref.id}-${el.role ?? ""}`}
                    items={members}
                    title={(count) =>
                      d.ref.type === ElementType.way
                        ? // @ts-expect-error
                          t("browse.changeset.node", { count })
                        : `${t("browse.relation.members")} (${count})`
                    }
                    renderRow={(el) => <ElementRow element={el} />}
                  />
                </div>
              )}
            </div>
            <ElementHistoryLinks data={d} />
          </>
        )
      }}
    </SidebarContent>
  )
}

export const ElementRoute = defineRoute({
  id: "element",
  path: ["/:type/:id", "/:type/:id/history/:version"],
  params: {
    type: ElementTypeParam,
    id: ElementIdParam,
    version: routeParam.optional(ElementVersionParam),
  },
  Component: ElementSidebar,
})

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

const ElementRow = ({ element }: { element: ElementData_Context_EntryValid }) => {
  const { type, id } = element.ref
  return (
    <ElementsListRow
      href={`/${getElementTypeSlug(type)}/${id}`}
      icon={element.icon}
      title={element.name || id}
      meta={
        <>
          <span>{getElementTypeLabel(type)}</span>
          {element.name && <span>{`#${id}`}</span>}
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
  switch (type) {
    case ElementType.node:
      return t("javascripts.query.node")
    case ElementType.way:
      return t("javascripts.query.way")
    case ElementType.relation:
      return t("javascripts.query.relation")
  }
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
