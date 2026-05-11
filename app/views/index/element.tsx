import { SidebarContent, SidebarHeader, useSidebar } from "@index/_action-sidebar"
import { defineRoute } from "@index/router"
import { pathParam } from "@lib/codecs"
import { API_URL, isLoggedIn } from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import { convertRenderElementsData } from "@lib/map/render-objects"
import type { LonLat } from "@lib/map/state"
import {
  type Data_Context_EntryValid,
  type DataValid,
  Service,
} from "@lib/proto/element_pb"
import { type ElementIconValid, ElementType } from "@lib/proto/shared_pb"
import { PageOrder, StandardPaginationNav } from "@lib/standard-pagination"
import { Tags } from "@lib/tags"
import { setPageTitle } from "@lib/title"
import {
  type ReadonlySignal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { type ComponentChildren, Fragment, type SubmitEventHandler } from "preact"

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

const ELEMENTS_PER_PAGE = 15

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
          setTargetPage={(nextPage) => (page.value = nextPage)}
          pageOrder={PageOrder.asc}
          maxPage={totalPages}
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

export const ElementTypeParam = pathParam.enum(["node", "way", "relation"])
export const ElementIdParam = pathParam.positive()
const ElementVersionParam = pathParam.positive()

const formatElementLocation = ({ lon, lat }: LonLat) =>
  `${lat.toFixed(7)}, ${lon.toFixed(7)}`

const serializeXml = (doc: XMLDocument) => new XMLSerializer().serializeToString(doc)

const createOsmDocument = () =>
  document.implementation.createDocument("", "osm", null)

const appendTagElements = (
  doc: XMLDocument,
  parent: Element,
  tags: Record<string, string>,
) => {
  for (const key of Object.keys(tags).sort((a, b) => a.localeCompare(b))) {
    const tag = doc.createElement("tag")
    tag.setAttribute("k", key)
    tag.setAttribute("v", tags[key]!)
    parent.append(tag)
  }
}

const formatTagsText = (tags: Record<string, string>) =>
  Object.keys(tags)
    .sort((a, b) => a.localeCompare(b))
    .map((key) => `${key}=${tags[key]}`)
    .join("\n")

const parseTagsText = (text: string) => {
  const tags: Record<string, string> = {}
  const duplicateKeys = new Set<string>()

  for (const [index, rawLine] of text.split(/\r?\n/).entries()) {
    const line = rawLine.trim()
    if (!line) continue

    const separatorIndex = line.indexOf("=")
    if (separatorIndex <= 0) {
      throw new Error(`Line ${index + 1} must use key=value format.`)
    }

    const key = line.slice(0, separatorIndex).trim()
    const value = line.slice(separatorIndex + 1).trim()
    if (!key || !value) {
      throw new Error(`Line ${index + 1} must include a key and value.`)
    }
    if (Object.hasOwn(tags, key)) duplicateKeys.add(key)
    tags[key] = value
  }

  if (duplicateKeys.size) {
    throw new Error(`Duplicate tag keys: ${[...duplicateKeys].join(", ")}`)
  }

  return tags
}

const responseError = async (response: Response) => {
  const contentType = response.headers.get("content-type")
  let message: string

  if (contentType?.includes("application/json")) {
    const data = await response.json()
    message = typeof data.detail === "string" ? data.detail : JSON.stringify(data)
  } else {
    message = await response.text()
  }

  throw new Error(message || `${response.status} ${response.statusText}`)
}

const createTagEditChangeset = async (comment: string) => {
  const doc = createOsmDocument()
  const changeset = doc.createElement("changeset")
  appendTagElements(doc, changeset, {
    comment,
    created_by: "OpenStreetMap-NG",
  })
  doc.documentElement.append(changeset)

  const response = await fetch(`${API_URL}/api/0.6/changeset/create`, {
    method: "PUT",
    headers: { "Content-Type": "application/xml" },
    body: serializeXml(doc),
  })
  if (!response.ok) await responseError(response)
  return (await response.text()).trim()
}

const closeChangeset = async (changesetId: string) => {
  const response = await fetch(`${API_URL}/api/0.6/changeset/${changesetId}/close`, {
    method: "PUT",
  })
  if (!response.ok) await responseError(response)
}

const buildElementUpdateXml = (
  data: DataValid,
  tags: Record<string, string>,
  changesetId: string,
) => {
  const doc = createOsmDocument()
  const typeSlug = getElementTypeSlug(data.ref.type)
  const element = doc.createElement(typeSlug)

  element.setAttribute("id", data.ref.id.toString())
  element.setAttribute("version", data.ref.version.toString())
  element.setAttribute("changeset", changesetId)

  if (data.ref.type === ElementType.node) {
    const location = data.location
    if (!location) throw new Error("Node location is missing.")
    element.setAttribute("lat", location.lat.toFixed(7))
    element.setAttribute("lon", location.lon.toFixed(7))
  } else if (data.ref.type === ElementType.way) {
    for (const member of data.context.members) {
      const node = doc.createElement("nd")
      node.setAttribute("ref", member.ref.id.toString())
      element.append(node)
    }
  } else if (data.ref.type === ElementType.relation) {
    for (const member of data.context.members) {
      const relationMember = doc.createElement("member")
      relationMember.setAttribute("type", getElementTypeSlug(member.ref.type))
      relationMember.setAttribute("ref", member.ref.id.toString())
      relationMember.setAttribute("role", member.roles[0] ?? "")
      element.append(relationMember)
    }
  }

  appendTagElements(doc, element, tags)
  doc.documentElement.append(element)
  return serializeXml(doc)
}

const updateElementTags = async (
  data: DataValid,
  tags: Record<string, string>,
  changesetId: string,
) => {
  const { type, id } = data.ref
  const typeSlug = getElementTypeSlug(type)
  const response = await fetch(`${API_URL}/api/0.6/${typeSlug}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/xml" },
    body: buildElementUpdateXml(data, tags, changesetId),
  })
  if (!response.ok) await responseError(response)
}

const saveElementTags = async (
  data: DataValid,
  tags: Record<string, string>,
  comment: string,
) => {
  let changesetId: string | undefined
  let saved = false
  try {
    changesetId = await createTagEditChangeset(comment)
    await updateElementTags(data, tags, changesetId)
    saved = true
  } catch (error) {
    if (changesetId) {
      try {
        await closeChangeset(changesetId)
      } catch {
        // Preserve the original save failure.
      }
    }
    throw error
  }

  if (saved && changesetId) await closeChangeset(changesetId)
}

const getElementTitleText = (data: DataValid) => {
  const { type, id } = data.ref
  const typeLabel = getElementTypeLabel(type)
  return data.name ? `${typeLabel}: ${data.name} (${id})` : `${typeLabel}: ${id}`
}

const ElementHeader = ({ data }: { data: DataValid }) => {
  const { type, id, version } = data.ref
  const isLatest = !data.nextVersion

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

export const ElementMeta = ({ data }: { data: DataValid }) => {
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

const ElementTagsSection = ({ data }: { data: DataValid }) => {
  const editing = useSignal(false)
  const saving = useSignal(false)
  const error = useSignal<string | null>(null)
  const canEdit = isLoggedIn && data.visible && !data.nextVersion
  const hasTags = Object.keys(data.tags).length > 0

  if (!hasTags && !canEdit) return null

  const onSubmit: SubmitEventHandler<HTMLFormElement> = async (event) => {
    event.preventDefault()
    const form = event.currentTarget
    const formData = new FormData(form)

    error.value = null
    saving.value = true
    try {
      const tags = parseTagsText(String(formData.get("tags") ?? ""))
      const comment = String(formData.get("comment") ?? "").trim()
      if (!comment) throw new Error(t("validation.required"))
      await saveElementTags(data, tags, comment)
      window.location.assign(`/${getElementTypeSlug(data.ref.type)}/${data.ref.id}`)
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      saving.value = false
    }
  }

  return (
    <section
      class="element-tags"
      data-tags={JSON.stringify(data.tags)}
    >
      <div class="element-tags-header">
        <h4>{t("browse.tag_details.tags")}</h4>
        {canEdit && !editing.value && (
          <button
            class="btn btn-link btn-sm"
            type="button"
            onClick={() => {
              error.value = null
              editing.value = true
            }}
          >
            {t("element.edit_tags_text")}
          </button>
        )}
      </div>

      {editing.value ? (
        <form
          class="tag-edit-form"
          onSubmit={onSubmit}
        >
          {error.value && <div class="alert alert-danger py-2">{error.value}</div>}
          <label class="form-label">
            <span>{t("browse.tag_details.tags")}</span>
            <textarea
              class="form-control font-monospace"
              name="tags"
              rows={Math.max(4, Object.keys(data.tags).length)}
              defaultValue={formatTagsText(data.tags)}
              disabled={saving.value}
            />
          </label>
          <label class="form-label">
            <span>{t("action.comment")}</span>
            <input
              class="form-control"
              name="comment"
              type="text"
              required
              disabled={saving.value}
            />
          </label>
          <div class="d-flex justify-content-end gap-2">
            <button
              class="btn btn-secondary btn-sm"
              type="button"
              disabled={saving.value}
              onClick={() => {
                error.value = null
                editing.value = false
              }}
            >
              {t("action.cancel")}
            </button>
            <button
              class="btn btn-primary btn-sm"
              type="submit"
              disabled={saving.value}
            >
              {saving.value ? t("state.saving") : t("action.save")}
            </button>
          </div>
        </form>
      ) : (
        <Tags tags={data.tags} />
      )}
    </section>
  )
}

const ElementHistoryLinks = ({ data }: { data: DataValid }) => {
  const { type, id, version } = data.ref
  const typeText = getElementTypeSlug(type)
  const prev = data.prevVersion
  const next = data.nextVersion

  return (
    <div class="section text-center">
      {(prev || next) && (
        <div class="mb-2">
          {prev && (
            <a
              href={`/${typeText}/${id}/history/${prev}`}
              rel="prev"
            >
              « v{prev}
            </a>
          )}
          {prev && (
            <span
              class="mx-1"
              aria-hidden="true"
            >
              ·
            </span>
          )}
          <a href={`/${typeText}/${id}/history`}>{t("browse.view_history")}</a>
          {next && (
            <>
              <span
                class="mx-1"
                aria-hidden="true"
              >
                ·
              </span>
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
  const { resource, data } = useSidebar(
    useComputed(() => {
      const typeValue = ElementType[type.value]
      const idValue = id.value
      const versionValue = version.value
      return versionValue
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
    Service.method.get,
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
        const idLabel = versionValue
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

              <ElementTagsSection data={d} />

              {hasRelations && (
                <div class="elements mt-3">
                  <ElementsSection
                    keyFn={(el) =>
                      `${el.ref.type}-${el.ref.id}-${el.roles.join("\x1F")}`
                    }
                    items={parents}
                    title={(count) => `${t("browse.part_of")} (${count})`}
                    renderRow={(el) => <ElementRow element={el} />}
                  />
                  <ElementsSection
                    keyFn={(el) =>
                      `${el.ref.type}-${el.ref.id}-${el.roles.join("\x1F")}`
                    }
                    items={members}
                    title={(count) =>
                      d.ref.type === ElementType.way
                        ? t("browse.changeset.node", { count })
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
    version: pathParam.optional(ElementVersionParam),
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
  icon: ElementIconValid | undefined
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

const ElementRow = ({ element }: { element: Data_Context_EntryValid }) => {
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
          {element.roles.length > 0 && (
            <>
              <span
                class="mx-1"
                aria-hidden="true"
              >
                ·
              </span>
              <span>{element.roles.join(", ")}</span>
            </>
          )}
        </>
      }
    />
  )
}

export const getElementTypeLabel = (type: ElementType) => {
  switch (type) {
    case ElementType.node:
      return t("javascripts.query.node")
    case ElementType.way:
      return t("javascripts.query.way")
    case ElementType.relation:
      return t("javascripts.query.relation")
  }
}

const getPaginationCountLabel = (page: number, totalItems: number) => {
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
